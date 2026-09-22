"""
Optional standalone mode: watches a VisionStation-style
`registro_inspeccion.csv` log file and calls `VisionAgentCore.handle_layer_event`
for each new line, the same way the original VisionAgent.exe worked
(PollLog / ParseInspectionRecord / SplitCsvLine / PendingCaptureQueue /
DequeueDue recovered names).

Use this ONLY if you don't have (or don't yet want) a direct code hook
into IV4 inspector. If you do have the hook, call
`VisionAgentCore.handle_layer_event(...)` directly instead -- it's
strictly better (no polling delay, no guessing).

*** REAL LOG FORMAT (confirmed from a real registro_inspeccion.csv,
42,599 rows, VisionStation build 2026-08) ***

    Timestamp,Código,Modelo,Cushion,Capa,Programa,Resultado
    2026-02-20 10:11:08,2010.FS17.CUSH01.SS1.P3.Sand Performance Basketweave.BTO,Armless C1,CUSH01,1,4,PW_ERR

- `Código` is the full scanned QR body: `<qr_prefix>.<furniture_code>.<cushion_slot>.<ss_code>.<size?>.<fabric name>.BTO`
  e.g. `2010.FS17.CUSH01.SS1.P3.Sand Performance Basketweave.BTO`.
  `ss_code` (SS1/SS6/OS4/OS5...) is the reliable key into kova_models.csv
  for the model name and required layer count -- NOT the free-text
  `Modelo` column, which carries cosmetic suffixes like "C1"/"C2" that
  don't affect layer count.
- `Resultado` observed values: OK, NG, PW_ERR (power/comm error --
  mapped to VisionAgentCore's SYSTEM_ERROR bucket).
- There is NO work-order / sales-order field in this VisionStation log
  (unlike IV4 inspector's own QR, which does carry one per its
  CHANGELOG). When running standalone against a VisionStation log, we
  synthesize a work-order key from `Código + Cushion` so products can
  still be grouped -- this is a standalone-mode-only fallback; when
  integrated directly into IV4 inspector, always pass the real
  work_order from its own label QR instead.
"""

from __future__ import annotations

import csv
import re
import time
from dataclasses import dataclass
from pathlib import Path

from .core import VisionAgentCore

RESULT_MAP = {
    "OK": "OK",
    "NG": "NG",
    "PW_ERR": "SYSTEM_ERROR",
}

SS_CODE_RE = re.compile(r"^SS\d+$|^OS\d+$")


@dataclass
class InspectionRecord:
    work_order: str
    model: str
    fabric_raw: str
    layer: int
    program: str
    result: str
    raw_code: str


def parse_codigo(codigo: str) -> tuple[str | None, str | None]:
    """Splits a VisionStation `Código` QR body on '.' and returns
    (ss_code, fabric_name). Format:
    <prefix>.<furniture_code>.<cushion_slot>.<ss_code>.<size>.<fabric name>.BTO
    """
    tokens = codigo.split(".")
    ss_code = next((t for t in tokens if SS_CODE_RE.match(t)), None)
    fabric_name = None
    if ss_code and ss_code in tokens:
        idx = tokens.index(ss_code)
        # skip one size/spec token (e.g. "P3"), then the fabric name is
        # everything up to the trailing "BTO" tag.
        rest = tokens[idx + 1:]
        if rest and rest[-1].upper() == "BTO":
            rest = rest[:-1]
        if rest:
            # first remaining token after ss_code is usually a size code
            # (P3, etc.) -- if there's more than one token left, drop it;
            # if there's exactly one, it *is* the fabric name.
            fabric_name = ".".join(rest[1:]) if len(rest) > 1 else rest[0]
    return ss_code, fabric_name


def parse_inspection_record(fields: list[str]) -> InspectionRecord | None:
    """ParseInspectionRecord -- fields already split by a real CSV reader
    (not naive comma-split, since fabric names could in principle
    contain commas even though none do in the confirmed sample)."""
    if len(fields) < 7:
        return None
    timestamp, codigo, modelo, cushion, capa, programa, resultado = fields[:7]
    result = RESULT_MAP.get(resultado.strip().upper())
    if result is None:
        return None
    try:
        layer = int(capa.strip())
    except ValueError:
        return None

    ss_code, fabric_name = parse_codigo(codigo)
    model = ss_code or modelo  # prefer the reliable ss_code as the model key
    work_order = f"{codigo}|{cushion}"  # synthetic -- see module docstring

    return InspectionRecord(
        work_order=work_order,
        model=model,
        fabric_raw=fabric_name or codigo,
        layer=layer,
        program=programa.strip(),
        result=result,
        raw_code=codigo,
    )


class LogWatcher:
    def __init__(self, agent: VisionAgentCore, log_path: Path, poll_interval_s: float = 0.5):
        self.agent = agent
        self.log_path = Path(log_path)
        self.poll_interval_s = poll_interval_s
        self._last_size = 0
        self._header_skipped = False
        self._running = False

    def start(self) -> None:
        """StartMonitoring."""
        self._running = True
        if self.log_path.exists():
            self._last_size = self.log_path.stat().st_size
        while self._running:
            self._poll_once()
            time.sleep(self.poll_interval_s)

    def stop(self) -> None:
        """PauseMonitoring."""
        self._running = False

    def _poll_once(self) -> None:
        """PollLog: reads any bytes appended since the last poll."""
        if not self.log_path.exists():
            return
        size = self.log_path.stat().st_size
        if size <= self._last_size:
            return
        with self.log_path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            f.seek(self._last_size)
            chunk = f.read()
        self._last_size = size

        for fields in csv.reader(chunk.splitlines()):
            if not fields or not fields[0].strip():
                continue
            if fields[0].strip().lower() in ("timestamp",):
                continue  # header line (can reappear if file was recreated)
            record = parse_inspection_record(fields)
            if record is None:
                continue
            # capture_delay_ms is applied inside handle_layer_event via
            # capture_screen_after_delay() when no screenshot is supplied.
            self.agent.handle_layer_event(
                work_order=record.work_order,
                model=record.model,
                fabric_raw=record.fabric_raw,
                layer=record.layer,
                program=record.program,
                result=record.result,
                raw_code=record.raw_code,
            )

