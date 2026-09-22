"""
FabricImageClassifier -- predicts a fabric part number (PN) from a
capture by nearest-neighbor matching against reference photos in
``fabric_part_images/<PN>/`` (per LEAME.txt / manifest.csv layout).

Recovered names: ClassifyFabric, InferPartNumber, FabricImageSample,
FabricImageSignature, SelectFabricDataset, NormalizeDatasetFolder,
DatasetImages, Confidence.

Matching reuses the same coarse color-grid signature as swatch.py (the
binary's SwatchSignature/FabricImageSignature property lists overlap
heavily, suggesting a shared fingerprint approach in the original too).
Confidence is an APPROXIMATION: 1 - (best_distance / (best_distance +
second_best_distance)), i.e. how much closer the winning PN is than the
runner-up -- low confidence when two PNs look almost equally close,
which is exactly the "leave as review" case CHANGELOG.txt describes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image

from .swatch import SwatchSignature, build_signature, signature_distance

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".bmp", ".webp")


@dataclass
class FabricClassificationResult:
    status: str                  # "MATCH" | "MISMATCH" | "REVIEW" | "NO_DATASET"
    predicted_part_number: str | None
    confidence: float
    dataset_images: int
    recommendation: str


@dataclass
class _PnDataset:
    signatures: list[SwatchSignature] = field(default_factory=list)
    image_count: int = 0


class FabricImageClassifier:
    def __init__(self, fabric_image_root: Path):
        self.root = Path(fabric_image_root)
        self._cache: dict[str, _PnDataset] = {}

    def _load_pn(self, part_number: str) -> _PnDataset:
        if part_number in self._cache:
            return self._cache[part_number]
        folder = self.root / part_number
        dataset = _PnDataset()
        if folder.is_dir():
            for f in sorted(folder.iterdir()):
                if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                    try:
                        with Image.open(f) as img:
                            dataset.signatures.append(build_signature(img))
                        dataset.image_count += 1
                    except Exception:
                        # SelectFabricDataset: skip unreadable images, keep going
                        continue
        self._cache[part_number] = dataset
        return dataset

    def known_part_numbers(self) -> list[str]:
        if not self.root.is_dir():
            return []
        return sorted(p.name for p in self.root.iterdir() if p.is_dir())

    def classify(
        self,
        capture: Image.Image,
        expected_part_number: str | None,
        min_confidence: float,
    ) -> FabricClassificationResult:
        """ClassifyFabric: predicts the closest PN in the whole known
        catalog, then compares it against `expected_part_number` (from
        fabrics.csv / the QR) to decide MATCH vs MISMATCH vs REVIEW."""
        candidates = self.known_part_numbers()
        if not candidates:
            return FabricClassificationResult(
                status="NO_DATASET",
                predicted_part_number=None,
                confidence=0.0,
                dataset_images=0,
                recommendation=(
                    "Sin fotos de entrenamiento en fabric_part_images/. Agregar "
                    "imagenes por PN para habilitar la clasificacion visual."
                ),
            )

        capture_sig = build_signature(capture)
        best_pn, best_dist = None, float("inf")
        second_dist = float("inf")
        total_images = 0

        for pn in candidates:
            dataset = self._load_pn(pn)
            total_images += dataset.image_count
            if not dataset.signatures:
                continue
            pn_best = min(signature_distance(capture_sig, s) for s in dataset.signatures)
            if pn_best < best_dist:
                second_dist = best_dist
                best_dist, best_pn = pn_best, pn
            elif pn_best < second_dist:
                second_dist = pn_best

        if best_pn is None:
            return FabricClassificationResult(
                status="NO_DATASET",
                predicted_part_number=None,
                confidence=0.0,
                dataset_images=total_images,
                recommendation="Ninguna carpeta de PN tiene imagenes legibles todavia.",
            )

        if second_dist == float("inf"):
            confidence = 1.0  # only one PN has any data at all
        else:
            confidence = 1.0 - (best_dist / (best_dist + second_dist + 1e-6))
            confidence = max(0.0, min(1.0, confidence))

        expected_dataset_images = self._load_pn(expected_part_number).image_count if expected_part_number else 0

        if expected_part_number and best_pn == expected_part_number and confidence >= min_confidence:
            status = "MATCH"
            recommendation = "La tela clasifica al PN esperado."
        elif expected_part_number and best_pn == expected_part_number and confidence < min_confidence:
            status = "REVIEW"
            recommendation = (
                "La tela clasifica al PN esperado, pero con baja confianza. Revisar "
                "iluminacion, enfoque y encuadre."
            )
        elif expected_part_number and confidence < min_confidence:
            status = "REVIEW"
            recommendation = (
                "Clasificacion visual poco clara: revisar iluminacion, enfoque y "
                "encuadre antes de decidir."
            )
        elif expected_part_number:
            status = "MISMATCH"
            recommendation = (
                f"La tela visible clasifica como PN {best_pn}, distinto al esperado "
                f"{expected_part_number}. Confirmar tela fisica antes de continuar."
            )
        else:
            status = "REVIEW"
            recommendation = "Sin PN esperado para comparar; solo se registra la prediccion visual."

        return FabricClassificationResult(
            status=status,
            predicted_part_number=best_pn,
            confidence=confidence,
            dataset_images=expected_dataset_images or total_images,
            recommendation=recommendation,
        )
