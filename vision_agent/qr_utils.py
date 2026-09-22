"""
QR / label text parsing.

The part-number regex below (``\\d{2}-\\d{6,7}-\\d{4}``) is the literal
pattern found embedded in VisionAgent.exe, e.g. matching a fabric part
number like ``26-023508-0119`` (the exact PN referenced in LEAME.txt).

``ExtractFabricName`` / ``ExtractWorkOrder`` / ``ExtractPart`` /
``NormalizeFabric`` / ``CleanFabric`` are method names recovered from the
binary; their exact tokenizing rules were not recoverable (the string
heap only stores literals, not IL logic), so the implementations below
are a documented reconstruction based on the label formats shown in
IV4 inspector's own CHANGELOG.md, e.g.:

    2011_FS33SBP_Mocha_Performance_Boucle_BTO_3292655.3.1.x.2
    2011.FS33SBP.<fabric>.<...>.<sales order>...

Adjust ``FIELD_SEPARATORS`` / ``KNOWN_MODEL_PREFIXES`` once you have real
QR samples from the floor.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

PART_NUMBER_RE = re.compile(r"\d{2}-\d{6,7}-\d{4}")

# QR bodies seen in both packages use '.' or '_' interchangeably as field
# separators (IV4 inspector CHANGELOG 0.10.0 note).
FIELD_SEPARATORS = re.compile(r"[._]")

# KOVA 3.5 QR routing prefix + furniture code, per IV4 inspector
# CHANGELOG 0.13.0 notes ("2011." model prefix plus FS... furniture code).
MODEL_PREFIX = "2011"


@dataclass
class QrInfo:
    raw: str
    model_prefix: str | None
    furniture_code: str | None
    fabric_name: str | None
    work_order: str | None
    part_number: str | None


def extract_part_number(text: str) -> str | None:
    m = PART_NUMBER_RE.search(text or "")
    return m.group(0) if m else None


def clean_fabric(name: str) -> str:
    """CleanFabric: trim separators/whitespace noise from a raw token."""
    return re.sub(r"\s+", " ", (name or "").replace("_", " ").replace(".", " ")).strip()


def normalize_fabric(name: str) -> str:
    """NormalizeFabric: canonical key used to match against fabrics.csv /
    swatches / fabric_part_images folder names."""
    cleaned = clean_fabric(name).upper()
    cleaned = re.sub(r"[^A-Z0-9]+", "_", cleaned).strip("_")
    return cleaned


def extract_work_order(qr_text: str) -> str | None:
    """ExtractWorkOrder: work order / sales order tail of the label QR,
    per IV4 inspector 0.10.0 ("work order/Sales Order is read from the
    label QR when present")."""
    tokens = [t for t in FIELD_SEPARATORS.split(qr_text or "") if t]
    for t in reversed(tokens):
        if re.fullmatch(r"\d{6,}(\.\d+)*", t):
            return t
    return None


def extract_fabric_name(qr_text: str) -> str | None:
    """ExtractFabricName: pulls the fabric-name segment out of a full QR
    body, e.g. 'Mocha Performance Boucle' out of
    2011_FS33SBP_Mocha_Performance_Boucle_BTO_3292655.3.1.x.2 --
    everything between the model/furniture code and the BTO/sales-order
    tail."""
    tokens = [t for t in FIELD_SEPARATORS.split(qr_text or "") if t]
    if len(tokens) < 3:
        return clean_fabric(qr_text) or None

    start = 2 if tokens[0] == MODEL_PREFIX else 0
    end = len(tokens)
    for i, t in enumerate(tokens[start:], start=start):
        if t.upper() == "BTO" or re.fullmatch(r"\d{6,}(\.\d+)*", t):
            end = i
            break
    fabric_tokens = tokens[start:end]
    return clean_fabric(" ".join(fabric_tokens)) or None


def parse_qr(raw: str) -> QrInfo:
    """ParseQr: best-effort structured parse of a scanned QR/label body."""
    tokens = [t for t in FIELD_SEPARATORS.split(raw or "") if t]
    model_prefix = tokens[0] if tokens and tokens[0] == MODEL_PREFIX else None
    furniture_code = tokens[1] if model_prefix and len(tokens) > 1 else (tokens[0] if tokens else None)
    return QrInfo(
        raw=raw,
        model_prefix=model_prefix,
        furniture_code=furniture_code,
        fabric_name=extract_fabric_name(raw),
        work_order=extract_work_order(raw),
        part_number=extract_part_number(raw),
    )
