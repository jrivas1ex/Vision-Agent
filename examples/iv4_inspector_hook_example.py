"""
EXAMPLE ONLY -- illustrates where/how to wire VisionAgentCore into
IV4 inspector once you have its Python source (v0.14.5, Tkinter/PyInstaller).

This is not runnable as-is: it shows the shape of the integration, not
IV4 inspector's real class/method names (which we don't have -- only its
CHANGELOG.md is available, not its source).

Based on CHANGELOG.md, IV4 inspector already has, per layer:
  - work order / model / fabric (from the scanned QR)
  - layer number and the IV4 program used for it (readback via `PR`,
    added in 0.14.4)
  - the IV4 result for that layer (OK/NG)
  - it already captures a screenshot per layer for its own evidence
    report (0.5.0: "Layer screenshot capture")

So the integration point is: wherever IV4 inspector currently does its
own "save this layer's screenshot + append to its own event log" step,
add one call to `agent.handle_layer_event(...)`, passing the screenshot
it already captured (as a PIL.Image) so nothing is captured twice.
"""

from pathlib import Path

from vision_agent.config import VisionAgentConfig
from vision_agent.core import VisionAgentCore

# --- app startup (once) -------------------------------------------------

config = VisionAgentConfig.load(Path(__file__).parent.parent / "vision_agent_config.ini")
vision_agent = VisionAgentCore(config)


# --- inside IV4 inspector's own "on layer result received" handler -----
def on_iv4_layer_result(work_order, model, fabric_qr_text, layer, program, iv4_result, raw_code, layer_screenshot):
    """
    `layer_screenshot` should be the PIL.Image (or a path) IV4 inspector
    already captured for its own evidence report -- pass it straight
    through so Vision Agent's visual checks run on the exact same frame,
    with zero extra delay/race risk.
    """
    outcome = vision_agent.handle_layer_event(
        work_order=work_order,
        model=model,
        fabric_raw=fabric_qr_text,
        layer=layer,
        program=program,
        result=iv4_result,
        raw_code=raw_code,
        screenshot=layer_screenshot,
    )

    # Surface the result in IV4 inspector's own UI immediately:
    if outcome.swatch_status == "MISMATCH":
        show_operator_warning(outcome.recommendation)  # your own UI call
    if outcome.fabric_classification_status == "MISMATCH":
        show_operator_warning(
            f"Tela clasificada como PN {outcome.predicted_part_number}, no coincide con lo esperado."
        )
    if outcome.product_completed:
        open_report_button_target = outcome.report_path  # wire to your "Abrir reportes" button


def show_operator_warning(message: str) -> None:
    raise NotImplementedError("Wire this to IV4 inspector's own message/prompt widget.")
