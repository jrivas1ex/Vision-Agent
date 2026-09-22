"""
ShiftReportGenerator -- "Reporte de inspeccion de presencia <fecha> Turno
<n>.html", regenerated on GenerateShiftReport() / TryUpdateShiftReport()
whenever a product completes or feedback is saved (per CHANGELOG.txt).

The <h1> title, empty-state row texts ("Sin eventos en este turno.",
"Sin productos completados en este turno.", "Sin validaciones visuales
en este turno.") and CSS below are LITERAL fragments recovered from
VisionAgent.exe.
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from .shift_schedule import ShiftSchedule, ShiftWindow
from .stats import RECOMMENDATIONS

_HEAD = (
    "<!doctype html><html><head><meta charset=\"utf-8\">"
    "<title>Reporte de inspeccion de presencia {fecha}</title>"
    "<style>body{{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f5f7fb;"
    "color:#172033}}h1{{margin-bottom:4px}}.muted{{color:#58657d}}"
    ".card{{background:white;border:1px solid #d8deea;border-radius:8px;padding:16px;margin:14px 0}}"
    ".metric{{display:inline-block;vertical-align:top;margin:8px 22px 8px 0}}"
    ".metric b{{display:block;font-size:24px}}"
    "table{{border-collapse:collapse;width:100%;background:white;margin-top:10px}}"
    "th,td{{border:1px solid #d8deea;padding:8px;text-align:left;font-size:13px}}"
    "th{{background:#e8eef6}}.bad{{color:#b00020;font-weight:700}}"
    ".good{{color:#087a33;font-weight:700}}</style></head><body>"
    "<h1>Reporte de inspeccion de presencia</h1>"
    '<p class="muted">{fecha} | Turno {turno}</p>'
)


def _metric(label: str, value) -> str:
    return f'<div class="metric"><span class="muted">{html.escape(label)}</span><b>{html.escape(str(value))}</b></div>'


def _events_table(events: list[dict]) -> str:
    if not events:
        return '<table><tr><td colspan="4">Sin eventos en este turno.</td></tr></table>'
    head = "<table><tr><th>Orden</th><th>Modelo</th><th>Capa</th><th>Resultado</th></tr>"
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(e.get('WorkOrder','')))}</td>"
        f"<td>{html.escape(str(e.get('Model','')))}</td>"
        f"<td>{html.escape(str(e.get('Layer','')))}</td>"
        f"<td class=\"{'good' if e.get('Result')=='OK' else 'bad'}\">{html.escape(str(e.get('Result','')))}</td>"
        "</tr>"
        for e in events
    )
    return head + rows + "</table>"


def _products_table(products: list[dict]) -> str:
    if not products:
        return '<table><tr><td colspan="4">Sin productos completados en este turno.</td></tr></table>'
    head = "<table><tr><th>Orden</th><th>Modelo</th><th>Tela</th><th>Resultado</th></tr>"
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(p.get('WorkOrder','')))}</td>"
        f"<td>{html.escape(str(p.get('Model','')))}</td>"
        f"<td>{html.escape(str(p.get('Fabric','')))}</td>"
        f"<td class=\"{'good' if p.get('ProductResult')=='OK' else 'bad'}\">{html.escape(str(p.get('ProductResult','')))}</td>"
        "</tr>"
        for p in products
    )
    return head + rows + "</table>"


def _visual_table(visual_rows: list[dict]) -> str:
    if not visual_rows:
        return '<table><tr><td colspan="4">Sin validaciones visuales en este turno.</td></tr></table>'
    head = "<table><tr><th>Orden</th><th>Capa</th><th>Estado swatch</th><th>Recomendacion</th></tr>"
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(str(v.get('WorkOrder','')))}</td>"
        f"<td>{html.escape(str(v.get('Layer','')))}</td>"
        f"<td class=\"{'good' if v.get('SwatchStatus')=='OK' else 'bad'}\">{html.escape(str(v.get('SwatchStatus','')))}</td>"
        f"<td>{html.escape(str(v.get('Recommendation','')))}</td>"
        "</tr>"
        for v in visual_rows
    )
    return head + rows + "</table>"


def build_suggestions(products: list[dict]) -> list[str]:
    """AppendShiftSuggestions: canned recommendations depending on what
    the shift's data looks like -- reuses the exact recommendation
    strings recovered from the binary (see stats.py)."""
    if not products:
        return [RECOMMENDATIONS["insufficient_history"]]
    suggestions = []
    ng_ratio = sum(1 for p in products if p.get("ProductResult") != "OK") / len(products)
    if ng_ratio > 0.2:
        suggestions.append(RECOMMENDATIONS["abnormal_event"])
    if any(p.get("ProductResult") == "SYSTEM_ERROR" for p in products):
        suggestions.append(RECOMMENDATIONS["comm_error"])
    if not suggestions:
        suggestions.append(RECOMMENDATIONS["ok"])
    return suggestions


def generate_shift_report(
    output_dir: Path,
    shift: ShiftWindow,
    moment: datetime,
    events: list[dict],
    products: list[dict],
    visual_rows: list[dict],
) -> Path:
    """GenerateShiftReport: writes
    'Reporte de inspeccion de presencia <fecha> Turno <n>.html'."""
    fecha = moment.strftime("%Y-%m-%d")
    filename = f"Reporte de inspeccion de presencia {fecha} Turno {shift.number}.html"
    path = output_dir / filename

    total = len(products)
    passed = sum(1 for p in products if p.get("ProductResult") == "OK")
    yield_pct = f"{(passed / total * 100):.1f}%" if total else "N/A"

    per_model: dict[str, list[bool]] = {}
    per_fabric: dict[str, list[bool]] = {}
    for p in products:
        per_model.setdefault(p.get("Model", "?"), []).append(p.get("ProductResult") == "OK")
        per_fabric.setdefault(p.get("Fabric", "?"), []).append(p.get("ProductResult") == "OK")

    def _yield_rows(bucket: dict[str, list[bool]], label: str) -> str:
        if not bucket:
            return f"<p class=\"muted\">Sin datos por {label} en este turno.</p>"
        head = f"<table><tr><th>{html.escape(label.capitalize())}</th><th>Yield</th><th>Total</th></tr>"
        rows = "".join(
            f"<tr><td>{html.escape(k)}</td><td>{(sum(v)/len(v)*100):.1f}%</td><td>{len(v)}</td></tr>"
            for k, v in bucket.items()
        )
        return head + rows + "</table>"

    parts = [_HEAD.format(fecha=fecha, turno=shift.number)]
    parts.append(
        '<div class="card">'
        + _metric("Yield general", yield_pct)
        + _metric("Productos completados", total)
        + _metric("Eventos", len(events))
        + "</div>"
    )
    parts.append(f'<div class="card"><h3>Yield por modelo</h3>{_yield_rows(per_model, "modelo")}</div>')
    parts.append(f'<div class="card"><h3>Yield por tela</h3>{_yield_rows(per_fabric, "tela")}</div>')
    parts.append(f'<div class="card"><h3>Eventos del turno</h3>{_events_table(events)}</div>')
    parts.append(f'<div class="card"><h3>Productos completados</h3>{_products_table(products)}</div>')
    parts.append(f'<div class="card"><h3>Mismatch visual de tela</h3>{_visual_table(visual_rows)}</div>')

    suggestions = build_suggestions(products)
    parts.append(
        '<div class="card"><h3>Sugerencias de mejora</h3><ul>'
        + "".join(f"<li>{html.escape(s)}</li>" for s in suggestions)
        + "</ul></div>"
    )
    parts.append("</body></html>")

    output_dir.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(parts), encoding="utf-8")
    return path


class ShiftReportManager:
    def __init__(self, output_dir: Path, schedule: ShiftSchedule | None = None):
        self.output_dir = output_dir
        self.schedule = schedule or ShiftSchedule()
        self._events: list[dict] = []
        self._products: list[dict] = []
        self._visual: list[dict] = []

    def record_event(self, row: dict) -> None:
        self._events.append(row)

    def record_product(self, row: dict) -> None:
        self._products.append(row)

    def record_visual(self, row: dict) -> None:
        self._visual.append(row)

    def try_update(self, moment: datetime | None = None) -> Path | None:
        """TryUpdateShiftReport: regenerate the current shift's report
        file with everything recorded so far this shift."""
        moment = moment or datetime.now()
        shift = self.schedule.current_shift(moment)
        window_start, _ = shift.window_for(moment)

        def _in_shift(ts_field: str, rows: list[dict]) -> list[dict]:
            out = []
            for r in rows:
                ts = r.get(ts_field)
                if isinstance(ts, str):
                    try:
                        ts = datetime.fromisoformat(ts)
                    except ValueError:
                        continue
                if ts and ts >= window_start:
                    out.append(r)
            return out

        events = _in_shift("Timestamp", self._events)
        products = _in_shift("CompletedAt", self._products)
        visual = _in_shift("Timestamp", self._visual)

        try:
            return generate_shift_report(self.output_dir, shift, moment, events, products, visual)
        except OSError:
            # "No se pudo actualizar reporte de turno: ..." -- swallow and
            # let the caller decide whether to surface it to the operator.
            return None
