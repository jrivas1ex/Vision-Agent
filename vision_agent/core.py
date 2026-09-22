"""
VisionAgentCore -- ties every module together. This is the class an
external app (IV4 inspector, or anything else) should import and call
directly, one call per layer result, instead of watching a log file.

This is the key structural difference from the original VisionAgent.exe:
the original had to poll registro_inspeccion.csv and guess a
capture_delay_ms because it ran as a separate process outside
VisionStation. If you call `handle_layer_event` directly from inside
IV4 inspector's own result handler, you already have the event the
instant it happens -- no polling, no delay heuristics, no risk of
capturing the screen before IV4 repaints it.

`capture_delay_ms` / `capture_screen_after_delay` are kept and still
usable for the case where you don't have a ready `screenshot` at call
time and want core.py to grab one after IV4 inspector's own configured
delay (see FromVisionStationFolder / ProcessRecordAfterDelay names
recovered from the binary) -- useful if IV4 inspector's paint isn't
finished the instant its own result event fires either.
"""

from __future__ import annotations

import threading
import time as _time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageGrab

from .config import VisionAgentConfig
from .fabric_classifier import FabricImageClassifier
from .qr_utils import extract_fabric_name, extract_part_number, normalize_fabric
from .report import write_report
from .shift_report import ShiftReportManager
from .stats import LocalStatisticalModel
from .storage import (
    append_event,
    append_fabric_classification,
    append_inspection_time,
    append_learning_feedback,
    append_product_completion,
    append_swatch_validation,
    append_visual_features,
)
from .swatch import SwatchCatalog, validate_swatch
from .tracker import LayerCatalog, LayerResult, ProductTracker
from .visual_features import extract_visual_features


@dataclass
class LayerEventOutcome:
    """Everything computed for one layer event -- handy for a caller
    that wants to show results in its own UI immediately."""
    swatch_status: str | None
    swatch_score: float | None
    fabric_classification_status: str | None
    predicted_part_number: str | None
    fabric_confidence: float | None
    recommendation: str
    product_completed: bool
    report_path: str | None


class VisionAgentCore:
    def __init__(self, config: VisionAgentConfig, layer_catalog: LayerCatalog | None = None):
        """`layer_catalog` defaults to the real kova_models.csv (or the
        KOVA 3.5 fallback matrix) -- the right choice when integrated
        directly into IV4 inspector, whose own "capas" mean KOVA-family
        program counts. If running standalone against VisionStation's
        OWN registro_inspeccion.csv via log_watcher.LogWatcher, pass
        `tracker.ObservedLayerCatalog()` instead -- see its docstring for
        why (VisionStation's `Capa` field is a different, smaller
        concept than kova_models.csv's `required_fabrics`)."""
        self.config = config
        self.config.ensure_dirs()

        self.swatch_catalog = SwatchCatalog(config.swatch_path)
        self.fabric_classifier = FabricImageClassifier(config.fabric_image_path)
        self.stats = LocalStatisticalModel()
        self.tracker = ProductTracker(layer_catalog or LayerCatalog(config.kova_models_path))
        self.shift_manager = ShiftReportManager(config.shift_reports_dir)

        # per-work-order accumulators for the WO_<orden>.html report
        self._order_events: dict[str, list[dict]] = {}
        self._order_swatch_rows: dict[str, list[dict]] = {}
        self._order_fabric_rows: dict[str, list[dict]] = {}
        self._order_screenshots: dict[str, list[str]] = {}

        self._lock = threading.Lock()

    # -- capture -----------------------------------------------------

    def capture_screen(self) -> Image.Image:
        """CaptureDesktop / CopyFromScreen."""
        return ImageGrab.grab()

    def capture_screen_after_delay(self) -> Image.Image:
        """ProcessRecordAfterDelay: sleeps `capture_delay_ms` (only useful
        if you're calling this from a background thread, e.g. a log
        watcher -- never sleep on the caller's real-time event thread)."""
        _time.sleep(self.config.capture_delay_ms / 1000.0)
        return self.capture_screen()

    def save_screenshot(self, image: Image.Image, work_order: str, layer: int) -> str:
        folder = self.config.screenshots_dir / f"WO_{work_order}"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"layer{layer}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        image.convert("RGB").save(path, "JPEG", quality=85)
        return str(path)

    # -- main integration entry point ---------------------------------

    def handle_layer_event(
        self,
        *,
        work_order: str,
        model: str,
        fabric_raw: str,
        layer: int,
        program: str,
        result: str,
        raw_code: str = "",
        screenshot: Image.Image | None = None,
        screenshot_path: str | None = None,
        expected_part_number: str | None = None,
    ) -> LayerEventOutcome:
        """Call this once per layer result. Everything else (CSV
        writes, HTML reports, shift report refresh) happens here.

        - `result` should be "OK", "NG", or "SYSTEM_ERROR".
        - `screenshot` is a PIL.Image you already have (preferred --
          avoids any delay/race). If omitted and `screenshot_path` is
          also omitted, this method captures the screen itself after
          `capture_delay_ms` (only do this off your UI thread).
        - `expected_part_number`: pass this if you already resolved the
          fabric's PN from fabrics.csv; otherwise it's extracted from
          `fabric_raw` when it matches the `\\d{2}-\\d{6,7}-\\d{4}` pattern.
        - `fabric_raw` can be either an already-resolved fabric name
          (e.g. "Mocha Performance Boucle") or a full raw QR/label body
          (e.g. "2011_FS33SBP_Mocha_Performance_Boucle_BTO_3292655...");
          the fabric-name segment is extracted automatically either way.
        """
        with self._lock:
            fabric_name = extract_fabric_name(fabric_raw) or fabric_raw
            fabric_normalized = normalize_fabric(fabric_name)
            expected_pn = expected_part_number or extract_part_number(fabric_raw)

            if screenshot is None and screenshot_path:
                screenshot = Image.open(screenshot_path)
            elif screenshot is None:
                screenshot = self.capture_screen_after_delay()

            should_validate = layer in self.config.visual_validation_layers

            swatch_result = None
            fabric_result = None
            saved_path = screenshot_path

            if should_validate:
                if saved_path is None:
                    saved_path = self.save_screenshot(screenshot, work_order, layer)

                swatch_result = validate_swatch(
                    screenshot, fabric_normalized, self.swatch_catalog, self.config.swatch_match_threshold
                )
                fabric_result = self.fabric_classifier.classify(
                    screenshot, expected_pn, self.config.fabric_min_confidence
                )
                features = extract_visual_features(screenshot)

            product = self.tracker.get_or_create(work_order, model, fabric_normalized)
            product.record_layer(LayerResult(layer=layer, program=program, result=result.upper()))
            self.tracker.update_required_layers(product, layer)

            bucket = self.stats.update_metrics(
                model, fabric_normalized, layer, program,
                is_ng=result.upper() != "OK",
                is_dark=should_validate and features.dark_ratio > 0.4,
                is_red_alert=should_validate and features.red_alert_ratio > 0.1,
            )
            recommendation = self.stats.build_recommendation(bucket)
            if should_validate and swatch_result and swatch_result.status != "OK":
                recommendation = swatch_result.recommendation

            timestamp = datetime.now().isoformat(timespec="seconds")

            event_row = dict(
                Timestamp=timestamp, WorkOrder=work_order, Model=model, Fabric=fabric_normalized,
                Layer=layer, Program=program, Result=result.upper(),
                ProductResult=product.product_result, RequiredLayers=product.required_layers,
                NgCount=product.ng_count, SystemErrorCount=product.system_error_count,
                FalsePositiveCandidates=product.false_positive_candidates,
                Screenshot=saved_path or "", RawCode=raw_code, Suggestion=recommendation,
            )
            append_event(self.config.events_csv_path, **event_row)
            self.shift_manager.record_event(event_row)
            self._order_events.setdefault(work_order, []).append(event_row)
            if saved_path:
                self._order_screenshots.setdefault(work_order, []).append(saved_path)

            if should_validate:
                append_visual_features(
                    self.config.visual_features_csv_path,
                    Timestamp=timestamp, WorkOrder=work_order, Model=model, Fabric=fabric_normalized,
                    Layer=layer, Program=program, Result=result.upper(),
                    FabricStatus=swatch_result.status,
                    **{
                        "Brightness": f"{features.brightness:.2f}",
                        "Contrast": f"{features.contrast:.2f}",
                        "DarkRatio": f"{features.dark_ratio:.4f}",
                        "SaturatedRatio": f"{features.saturated_ratio:.4f}",
                        "RedAlertRatio": f"{features.red_alert_ratio:.4f}",
                    },
                    NgRate=f"{bucket.ng_rate:.4f}", FalsePositiveRate=f"{bucket.false_positive_rate:.4f}",
                    Recommendation=recommendation, Screenshot=saved_path or "",
                )

                swatch_row = dict(
                    Timestamp=timestamp, WorkOrder=work_order, Model=model, Fabric=fabric_normalized,
                    Layer=layer, Program=program, Result=result.upper(),
                    FabricStatus=swatch_result.status, SwatchStatus=swatch_result.status,
                    SwatchScore=f"{swatch_result.score:.3f}", SwatchPath=swatch_result.swatch_path or "",
                    CapturePath=saved_path or "", Recommendation=swatch_result.recommendation, RawCode=raw_code,
                )
                append_swatch_validation(self.config.swatch_validation_csv_path, **swatch_row)
                self.shift_manager.record_visual(swatch_row)
                self._order_swatch_rows.setdefault(work_order, []).append(swatch_row)

                fabric_row = dict(
                    Timestamp=timestamp, WorkOrder=work_order, Model=model, Fabric=fabric_normalized,
                    Layer=layer, Program=program, Result=result.upper(),
                    FabricStatus=swatch_result.status, ExpectedPartNumber=expected_pn or "",
                    ClassificationStatus=fabric_result.status,
                    PredictedPartNumber=fabric_result.predicted_part_number or "",
                    Confidence=f"{fabric_result.confidence:.3f}", DatasetImages=fabric_result.dataset_images,
                    CapturePath=saved_path or "", Recommendation=fabric_result.recommendation, RawCode=raw_code,
                )
                append_fabric_classification(self.config.fabric_classification_csv_path, **fabric_row)
                self._order_fabric_rows.setdefault(work_order, []).append(fabric_row)

            report_path = None
            product_completed = False
            if product.is_complete:
                product_completed = True
                completed = self.tracker.pop_if_complete(work_order)
                report_path = str(self.config.reports_dir / f"WO_{work_order}.html")
                write_report(
                    Path(report_path), completed,
                    self._order_events.pop(work_order, []),
                    self._order_swatch_rows.pop(work_order, []),
                    self._order_fabric_rows.pop(work_order, []),
                    self._order_screenshots.pop(work_order, []),
                )
                product_row = dict(
                    CompletedAt=timestamp, WorkOrder=work_order, Model=model, Fabric=fabric_normalized,
                    RequiredLayers=completed.required_layers, CompletedLayers=completed.completed_layers,
                    ProductResult=completed.product_result, YieldPass=completed.yield_pass,
                    NgCount=completed.ng_count, SystemErrorCount=completed.system_error_count,
                    FalsePositiveCandidates=completed.false_positive_candidates,
                    RealRejectCount=completed.real_reject_count, FalseNegativeCount=completed.false_negative_count,
                    ReportHtml=report_path,
                )
                append_product_completion(self.config.products_csv_path, **product_row)
                self.shift_manager.record_product(product_row)

                elapsed_seconds = (datetime.now() - completed.started_at).total_seconds()
                append_inspection_time(
                    self.config.inspection_time_csv_path,
                    WorkOrder=work_order, Model=model, Fabric=fabric_normalized,
                    StartedAt=completed.started_at.isoformat(timespec="seconds"),
                    CompletedAt=timestamp, ElapsedSeconds=f"{elapsed_seconds:.1f}",
                    RequiredLayers=completed.required_layers, ProductResult=completed.product_result,
                )

            self.shift_manager.try_update()

            return LayerEventOutcome(
                swatch_status=swatch_result.status if swatch_result else None,
                swatch_score=swatch_result.score if swatch_result else None,
                fabric_classification_status=fabric_result.status if fabric_result else None,
                predicted_part_number=fabric_result.predicted_part_number if fabric_result else None,
                fabric_confidence=fabric_result.confidence if fabric_result else None,
                recommendation=recommendation,
                product_completed=product_completed,
                report_path=report_path,
            )

    # -- manual feedback (RecordFeedback / MarkFeedback) ---------------

    def record_feedback(
        self, *, work_order: str, model: str, layer: int, program: str,
        original_result: str, classification: str, raw_code: str = "",
    ) -> None:
        """RecordFeedback: operator-confirmed classification of a past
        event ("false_positive" | "real_reject" | "false_negative").

        If `work_order` is still active (not yet completed), its running
        counters are updated too; a completed product's confirmed counts
        already went into vision_agent_products.csv at completion time,
        so feedback about it only lands in vision_agent_learning.csv --
        this avoids silently resurrecting a finished product's state.
        """
        for product in self.tracker.active():
            if product.work_order == work_order:
                product.mark_feedback(classification)
                break
        append_learning_feedback(
            self.config.learning_csv_path,
            Timestamp=datetime.now().isoformat(timespec="seconds"),
            WorkOrder=work_order, Model=model, Layer=layer, Program=program,
            OriginalResult=original_result, Classification=classification, RawCode=raw_code,
        )
        self.shift_manager.try_update()

    # -- manual shift report trigger ("Reporte turno" button) ----------

    def generate_shift_report_now(self) -> str | None:
        path = self.shift_manager.try_update()
        return str(path) if path else None
