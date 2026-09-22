"""
ProductTracker / ProductState -- tracks one work order across its
layers until complete, accumulating the counters that end up in
vision_agent_products.csv.

Recovered names: ProductTracker, ProductState, LayerResults,
InferRequiredLayers, IsComplete, RequiredLayers, NgCount,
SystemErrorCount, FalsePositiveCandidates, RealRejectCount,
FalseNegativeCount, YieldPass.

InferRequiredLayers now prefers a real `kova_models.csv` (confirmed
format, ss_code,model_name,required_fabrics -- e.g. SS1,Armless,4)
when one is available next to the config file. This is the same file
FabricVision uses, so both tools can share one source of truth instead
of drifting. If no kova_models.csv is found, it falls back to the
KOVA 3.5 APPROXIMATION matrix from IV4 inspector's changelog (ARMLESS/
CLUB CHAIR/OTTOMAN/CORNER), since that's the newer model family this
is meant to scale to.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# APPROXIMATION fallback -- used only when no kova_models.csv is found.
# Cross-check against IV4 inspector's real config/model_program_matrix.csv
# for the KOVA 3.5 family when available.
MODEL_REQUIRED_LAYERS_FALLBACK = {
    "ARMLESS": 4,
    "CLUB CHAIR": 6,
    "ARM CHAIR": 6,
    "OTTOMAN": 2,
    "CORNER": 5,
}


def load_kova_models(path: Path) -> dict[str, int]:
    """Loads a real kova_models.csv (ss_code,model_name,required_fabrics)
    into {SS_CODE: required_layers, MODEL_NAME_UPPER: required_layers}
    so lookups work by either key."""
    mapping: dict[str, int] = {}
    if not path.is_file():
        return mapping
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            try:
                layers = int(row["required_fabrics"])
            except (KeyError, ValueError):
                continue
            if row.get("ss_code"):
                mapping[row["ss_code"].strip().upper()] = layers
            if row.get("model_name"):
                mapping[row["model_name"].strip().upper()] = layers
    return mapping


class LayerCatalog:
    """Holds whichever required-layers source is active (real
    kova_models.csv if found, else the fallback matrix) so it's loaded
    once and reused by every ProductTracker.infer_required_layers call."""

    dynamic = False

    def __init__(self, kova_models_path: Path | None = None):
        self._real = load_kova_models(kova_models_path) if kova_models_path else {}

    def infer_required_layers(self, model_name: str) -> int:
        key = (model_name or "").strip().upper()
        if key in self._real:
            return self._real[key]
        for name, layers in MODEL_REQUIRED_LAYERS_FALLBACK.items():
            if name in key:
                return layers
        return 1  # unknown model: don't assume more layers than seen


# Module-level default catalog (no real file) -- used when a
# ProductTracker is built without an explicit LayerCatalog, keeping the
# old free-function call sites working.
_default_catalog = LayerCatalog()


def infer_required_layers(model_name: str) -> int:
    return _default_catalog.infer_required_layers(model_name)


class ObservedLayerCatalog:
    """Required-layers source for VisionStation's OWN registro_inspeccion.csv
    standalone mode.

    IMPORTANT: `kova_models.csv`'s `required_fabrics` is FabricVision's
    concept (how many distinct fabric/label passes a model needs) and is
    NOT the same as VisionStation's `Capa` field -- confirmed against a
    real 42,599-row registro_inspeccion.csv, `Capa` only ever takes the
    values 1 or 2, regardless of model. Using kova_models.csv here would
    silently claim products need 4-6 layers when the real station only
    ever records 1-2, and no product would ever "complete".

    This catalog instead tracks, live, the highest layer number seen so
    far for each model key and treats that as the current requirement --
    self-correcting as more of the real log is observed, and matching
    what this specific station actually does instead of a borrowed
    number from a different tool.

    When integrating directly into IV4 inspector via `handle_layer_event`
    (not this standalone log-watching mode), use `LayerCatalog` with a
    real IV4-inspector model/program matrix instead -- IV4 inspector's
    own "capas" genuinely do mean KOVA-family program counts (see
    tracker.py's MODEL_REQUIRED_LAYERS_FALLBACK), unlike VisionStation's.
    """

    dynamic = True

    def __init__(self, initial_default: int = 2) -> None:
        # Defaults to 2, not 1: confirmed against the real 42,599-row
        # registro_inspeccion.csv that `Capa` only ever takes values 1 or
        # 2 for every model in this station. Starting at 1 would close
        # (and report/complete) a product the instant its first layer
        # arrived, before a likely second layer for the same work order
        # showed up -- silently under-counting almost every product.
        self._seen_max: dict[str, int] = {}
        self._initial_default = initial_default

    def infer_required_layers(self, model_name: str, layer: int | None = None) -> int:
        key = (model_name or "").strip().upper()
        if layer is not None:
            current = self._seen_max.get(key, self._initial_default)
            self._seen_max[key] = max(current, layer)
        return self._seen_max.get(key, self._initial_default)


@dataclass
class LayerResult:
    layer: int
    program: str
    result: str            # "OK" | "NG" | "SYSTEM_ERROR"
    fabric_status: str | None = None


@dataclass
class ProductState:
    work_order: str
    model: str
    fabric: str
    required_layers: int
    started_at: datetime = field(default_factory=datetime.now)
    layer_results: dict[int, LayerResult] = field(default_factory=dict)
    false_positive_candidates: int = 0
    real_reject_count: int = 0
    false_negative_count: int = 0

    def record_layer(self, result: LayerResult) -> None:
        # AppendLearningFeedback/retry semantics: a re-scan of the same
        # layer replaces the previous result instead of stacking it (this
        # mirrors IV4 inspector's own 0.14.2 fix for the same problem).
        self.layer_results[result.layer] = result

    @property
    def completed_layers(self) -> int:
        return len(self.layer_results)

    @property
    def is_complete(self) -> bool:
        return self.completed_layers >= self.required_layers

    @property
    def ng_count(self) -> int:
        return sum(1 for r in self.layer_results.values() if r.result == "NG")

    @property
    def system_error_count(self) -> int:
        return sum(1 for r in self.layer_results.values() if r.result == "SYSTEM_ERROR")

    @property
    def product_result(self) -> str:
        if self.system_error_count:
            return "SYSTEM_ERROR"
        return "NG" if self.ng_count else "OK"

    @property
    def yield_pass(self) -> bool:
        return self.product_result == "OK"

    def mark_feedback(self, classification: str) -> None:
        """MarkFeedback: operator-confirmed classification for the whole
        product, used by the shift report's suggestion engine."""
        classification = classification.upper()
        if classification == "FALSE_POSITIVE":
            self.false_positive_candidates += 1
        elif classification == "REAL_REJECT":
            self.real_reject_count += 1
        elif classification == "FALSE_NEGATIVE":
            self.false_negative_count += 1


class ProductTracker:
    """Holds all in-progress ProductState objects, keyed by work order."""

    def __init__(self, layer_catalog: LayerCatalog | None = None) -> None:
        self._products: dict[str, ProductState] = {}
        self._catalog = layer_catalog or _default_catalog

    def get_or_create(self, work_order: str, model: str, fabric: str) -> ProductState:
        state = self._products.get(work_order)
        if state is None:
            state = ProductState(
                work_order=work_order,
                model=model,
                fabric=fabric,
                required_layers=self._catalog.infer_required_layers(model),
            )
            self._products[work_order] = state
        return state

    def update_required_layers(self, product: ProductState, layer: int) -> None:
        """For a dynamic (ObservedLayerCatalog) source: bump the
        product's required_layers if this event's layer number is the
        highest seen so far for its model. No-op for a static catalog
        (real kova_models.csv or the fallback matrix)."""
        if getattr(self._catalog, "dynamic", False):
            product.required_layers = self._catalog.infer_required_layers(product.model, layer)

    def pop_if_complete(self, work_order: str) -> ProductState | None:
        state = self._products.get(work_order)
        if state and state.is_complete:
            del self._products[work_order]
            return state
        return None

    def active(self) -> list[ProductState]:
        return list(self._products.values())
