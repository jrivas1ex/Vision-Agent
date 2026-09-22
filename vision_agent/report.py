"""
ReportWriter -- per work order HTML evidence report
(``reports/WO_<orden>.html``), including the Validacion Visual de Tela
and Clasificacion Visual de Tela sections added in the SWATCH DATASET
release.

The CSS/head markup and the <h1> title below are LITERAL fragments
recovered from VisionAgent.exe's UTF-16 string table -- reused verbatim
so generated reports look identical to the original tool's output.
Recovered method names: WriteReport, WriteHtml, AppendEvent(Group)Table,
AppendProductCompletion, AppendSwatchSection, AppendSwatchMismatchTable,
AppendFabricClassificationSection, AppendFabricDatasetSample,
AppendStatisticalSection, HtmlEscape.
"""

from __future__ import annotations

import html
from pathlib import Path

from .tracker import ProductState

_HEAD = (
    "<!doctype html><html><head><meta charset=\"utf-8\">"
    "<title>Vision Agent Reporte de Inspeccion</title>"
    "<style>body{font-family:Segoe UI,Arial,sans-serif;margin:24px;background:#f5f7fb;"
    "color:#172033}h1{margin-bottom:4px}.card{background:white;border:1px solid #d8deea;"
    "border-radius:8px;padding:16px;margin:14px 0}.metric{display:inline-block;margin:6px 16px 6px 0}"
    ".metric b{display:block;font-size:20px}table{border-collapse:collapse;width:100%;background:white}"
    "th,td{border:1px solid #d8deea;padding:8px;text-align:left;font-size:13px}"
    "th{background:#e8eef6}.ok{color:#087a33;font-weight:700}.ng{color:#b00020;font-weight:700}"
    ".review{color:#925400;font-weight:700}img{max-width:100%;border:1px solid #ccd3df}</style></head><body>"
    "<h1>Vision Agent Reporte de Inspeccion</h1>"
)


def _status_class(status: str) -> str:
    status = (status or "").upper()
    if status in ("OK", "MATCH"):
        return "ok"
    if status in ("MISMATCH", "NG"):
        return "ng"
    return "review"


def _metric(label: str, value) -> str:
    return f'<div class="metric"><span>{html.escape(label)}</span><b>{html.escape(str(value))}</b></div>'


def _append_event_group_table(rows: list[dict]) -> str:
    if not rows:
        return "<tr><td colspan=\"4\">Sin eventos.</td></tr>"
    body = []
    for r in rows:
        cls = _status_class(r.get("Result", ""))
        body.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('Layer', '')))}</td>"
            f"<td>{html.escape(str(r.get('Program', '')))}</td>"
            f"<td class=\"{cls}\">{html.escape(str(r.get('Result', '')))}</td>"
            f"<td>{html.escape(str(r.get('Timestamp', '')))}</td>"
            "</tr>"
        )
    return "".join(body)


def _append_swatch_section(rows: list[dict]) -> str:
    if not rows:
        return "<p class=\"muted\">Sin validaciones de swatch en esta orden.</p>"
    head = "<table><tr><th>Capa</th><th>Estado</th><th>Score</th><th>Recomendacion</th></tr>"
    body = []
    for r in rows:
        cls = _status_class(r.get("SwatchStatus", ""))
        body.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('Layer', '')))}</td>"
            f"<td class=\"{cls}\">{html.escape(str(r.get('SwatchStatus', '')))}</td>"
            f"<td>{html.escape(str(r.get('SwatchScore', '')))}</td>"
            f"<td>{html.escape(str(r.get('Recommendation', '')))}</td>"
            "</tr>"
        )
    return head + "".join(body) + "</table>"


def _append_fabric_classification_section(rows: list[dict]) -> str:
    if not rows:
        return "<p class=\"muted\">Sin clasificacion visual de tela en esta orden.</p>"
    head = (
        "<table><tr><th>Capa</th><th>PN esperado</th><th>Estado</th><th>PN predicho</th>"
        "<th>Confianza</th><th>Imagenes dataset</th><th>Recomendacion</th></tr>"
    )
    body = []
    for r in rows:
        cls = _status_class(r.get("ClassificationStatus", ""))
        body.append(
            "<tr>"
            f"<td>{html.escape(str(r.get('Layer', '')))}</td>"
            f"<td>{html.escape(str(r.get('ExpectedPartNumber', '')))}</td>"
            f"<td class=\"{cls}\">{html.escape(str(r.get('ClassificationStatus', '')))}</td>"
            f"<td>{html.escape(str(r.get('PredictedPartNumber', '')))}</td>"
            f"<td>{html.escape(str(r.get('Confidence', '')))}</td>"
            f"<td>{html.escape(str(r.get('DatasetImages', '')))}</td>"
            f"<td>{html.escape(str(r.get('Recommendation', '')))}</td>"
            "</tr>"
        )
    return head + "".join(body) + "</table>"


def write_report(
    output_path: Path,
    product: ProductState,
    event_rows: list[dict],
    swatch_rows: list[dict],
    fabric_rows: list[dict],
    screenshots: list[str] | None = None,
) -> None:
    """WriteReport / WriteHtml: builds reports/WO_<orden>.html."""
    parts = [_HEAD]
    parts.append(
        '<div class="card">'
        f'<h2>Orden {html.escape(product.work_order)}</h2>'
        + _metric("Modelo", product.model)
        + _metric("Tela", product.fabric)
        + _metric("Resultado", product.product_result)
        + _metric("Capas", f"{product.completed_layers}/{product.required_layers}")
        + _metric("NG", product.ng_count)
        + _metric("Falsos positivos candidatos", product.false_positive_candidates)
        + "</div>"
    )
    parts.append('<div class="card"><h3>Eventos por capa</h3><table>'
                 "<tr><th>Capa</th><th>Programa</th><th>Resultado</th><th>Hora</th></tr>"
                 + _append_event_group_table(event_rows) + "</table></div>")
    parts.append('<div class="card"><h3>Validacion Visual de Tela</h3>' + _append_swatch_section(swatch_rows) + "</div>")
    parts.append(
        '<div class="card"><h3>Clasificacion Visual de Tela</h3>'
        + _append_fabric_classification_section(fabric_rows)
        + "</div>"
    )
    if screenshots:
        imgs = "".join(f'<img src="{html.escape(s)}">' for s in screenshots)
        parts.append(f'<div class="card"><h3>Capturas</h3>{imgs}</div>')
    parts.append("</body></html>")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("".join(parts), encoding="utf-8")
