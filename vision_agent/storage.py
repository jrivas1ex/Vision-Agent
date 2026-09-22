"""
CSV append helpers -- headers below are the LITERAL strings recovered
from VisionAgent.exe's UTF-16 string table (not reconstructed/guessed).

AppendEvent / AppendProductCompletion / AppendVisualFeatures /
AppendSwatchValidation / AppendFabricClassification /
AppendLearningFeedback / CsvEscape are the recovered method names.
"""

from __future__ import annotations

import csv
from pathlib import Path

HEADERS = {
    "events": [
        "Timestamp", "WorkOrder", "Model", "Fabric", "Layer", "Program", "Result",
        "ProductResult", "RequiredLayers", "NgCount", "SystemErrorCount",
        "FalsePositiveCandidates", "Screenshot", "RawCode", "Suggestion",
    ],
    "products": [
        "CompletedAt", "WorkOrder", "Model", "Fabric", "RequiredLayers",
        "CompletedLayers", "ProductResult", "YieldPass", "NgCount",
        "SystemErrorCount", "FalsePositiveCandidates", "RealRejectCount",
        "FalseNegativeCount", "ReportHtml",
    ],
    "visual_features": [
        "Timestamp", "WorkOrder", "Model", "Fabric", "Layer", "Program", "Result",
        "FabricStatus", "Brightness", "Contrast", "DarkRatio", "SaturatedRatio",
        "RedAlertRatio", "NgRate", "FalsePositiveRate", "Recommendation", "Screenshot",
    ],
    "swatch_validation": [
        "Timestamp", "WorkOrder", "Model", "Fabric", "Layer", "Program", "Result",
        "FabricStatus", "SwatchStatus", "SwatchScore", "SwatchPath", "CapturePath",
        "Recommendation", "RawCode",
    ],
    "fabric_classification": [
        "Timestamp", "WorkOrder", "Model", "Fabric", "Layer", "Program", "Result",
        "FabricStatus", "ExpectedPartNumber", "ClassificationStatus",
        "PredictedPartNumber", "Confidence", "DatasetImages", "CapturePath",
        "Recommendation", "RawCode",
    ],
    "learning": [
        "Timestamp", "WorkOrder", "Model", "Layer", "Program", "OriginalResult",
        "Classification", "RawCode",
    ],
    # NEW -- not part of the reverse-engineered VisionAgent.exe schema.
    # Added to directly serve the stated goal: prove inspection time is
    # actually going down, and give a single place that replaces the
    # manual SharePoint mobile-scan record for "how long did this
    # product take".
    "inspection_time": [
        "WorkOrder", "Model", "Fabric", "StartedAt", "CompletedAt",
        "ElapsedSeconds", "RequiredLayers", "ProductResult",
    ],
}


def _append_row(path: Path, kind: str, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    headers = HEADERS[kind]
    is_new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow({h: row.get(h, "") for h in headers})


def append_event(path: Path, **row) -> None:
    _append_row(path, "events", row)


def append_product_completion(path: Path, **row) -> None:
    _append_row(path, "products", row)


def append_visual_features(path: Path, **row) -> None:
    _append_row(path, "visual_features", row)


def append_swatch_validation(path: Path, **row) -> None:
    _append_row(path, "swatch_validation", row)


def append_fabric_classification(path: Path, **row) -> None:
    _append_row(path, "fabric_classification", row)


def append_learning_feedback(path: Path, **row) -> None:
    _append_row(path, "learning", row)


def append_inspection_time(path: Path, **row) -> None:
    _append_row(path, "inspection_time", row)
