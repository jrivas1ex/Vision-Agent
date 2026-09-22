"""
SwatchCatalog / ValidateSwatch -- compares the fabric visible in a
capture against the reference image for the expected fabric in
``swatches/`` (matched by filename, per LEAME.txt: "La validacion visual
compara la tela del QR contra la imagen con el mismo nombre en
swatches").

BuildSignature / SwatchScore / SwatchStatus / MatchThreshold are the
recovered names. The signature here is an APPROXIMATION: a coarse color
+ brightness + contrast fingerprint (a small grid of average RGB cells
plus global brightness/contrast), compared by weighted Euclidean
distance. It intentionally avoids anything resembling an object
detector -- consistent with the "sin YOLO, sin API, sin internet" design
goal in CHANGELOG.txt.

Status values mirror the three-way outcome implied by CHANGELOG/LEAME
("...para proteger falsos positivos" pattern used elsewhere): OK,
MISMATCH, REVIEW (borderline -- neither confidently OK nor confidently
wrong).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image

GRID = 4  # 4x4 color grid fingerprint
REVIEW_BAND = 0.35  # APPROXIMATION: fraction above threshold still counted "review" not "mismatch"


@dataclass
class SwatchSignature:
    grid_rgb: list[tuple[float, float, float]]
    brightness: float
    contrast: float


@dataclass
class SwatchValidationResult:
    status: str          # "OK" | "MISMATCH" | "REVIEW" | "NO_SWATCH"
    score: float          # distance; lower = closer match
    swatch_path: str | None
    recommendation: str


def build_signature(image: Image.Image) -> SwatchSignature:
    img = image.convert("RGB")
    w, h = img.size
    cell_w, cell_h = max(1, w // GRID), max(1, h // GRID)
    px = img.load()

    grid_rgb: list[tuple[float, float, float]] = []
    lum_values: list[float] = []
    for gy in range(GRID):
        for gx in range(GRID):
            r_sum = g_sum = b_sum = 0
            count = 0
            x0, y0 = gx * cell_w, gy * cell_h
            x1 = w if gx == GRID - 1 else x0 + cell_w
            y1 = h if gy == GRID - 1 else y0 + cell_h
            for y in range(y0, y1):
                for x in range(x0, x1):
                    r, g, b = px[x, y]
                    r_sum += r
                    g_sum += g
                    b_sum += b
                    count += 1
                    lum_values.append(0.299 * r + 0.587 * g + 0.114 * b)
            count = max(1, count)
            grid_rgb.append((r_sum / count, g_sum / count, b_sum / count))

    mean_lum = sum(lum_values) / max(1, len(lum_values))
    variance = sum((v - mean_lum) ** 2 for v in lum_values) / max(1, len(lum_values))
    return SwatchSignature(grid_rgb=grid_rgb, brightness=mean_lum, contrast=variance ** 0.5)


def signature_distance(a: SwatchSignature, b: SwatchSignature) -> float:
    """Weighted Euclidean distance: color grid dominates, brightness/
    contrast add a smaller correction term. APPROXIMATION weights."""
    color_term = 0.0
    for (r1, g1, b1), (r2, g2, b2) in zip(a.grid_rgb, b.grid_rgb):
        color_term += (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2
    color_term = (color_term / len(a.grid_rgb)) ** 0.5

    brightness_term = abs(a.brightness - b.brightness)
    contrast_term = abs(a.contrast - b.contrast)
    return color_term + 0.25 * brightness_term + 0.15 * contrast_term


class SwatchCatalog:
    """Loads and caches swatch reference images from swatch_root, keyed
    by normalized fabric name (filename without extension)."""

    def __init__(self, swatch_root: Path):
        self.swatch_root = Path(swatch_root)
        self._signature_cache: dict[str, SwatchSignature] = {}

    def find_swatch_path(self, normalized_fabric: str) -> Path | None:
        if not self.swatch_root.is_dir():
            return None
        for ext in (".jpg", ".jpeg", ".png", ".bmp", ".webp"):
            candidate = self.swatch_root / f"{normalized_fabric}{ext}"
            if candidate.exists():
                return candidate
        # fall back to a case-insensitive scan
        for f in self.swatch_root.iterdir():
            if f.is_file() and f.stem.upper() == normalized_fabric.upper():
                return f
        return None

    def get_signature(self, path: Path) -> SwatchSignature:
        key = str(path)
        if key not in self._signature_cache:
            with Image.open(path) as img:
                self._signature_cache[key] = build_signature(img)
        return self._signature_cache[key]


def validate_swatch(
    capture: Image.Image,
    normalized_fabric: str,
    catalog: SwatchCatalog,
    match_threshold: float,
) -> SwatchValidationResult:
    """ValidateSwatch: compares `capture` against the reference swatch
    image for `normalized_fabric`."""
    swatch_path = catalog.find_swatch_path(normalized_fabric)
    if swatch_path is None:
        return SwatchValidationResult(
            status="NO_SWATCH",
            score=0.0,
            swatch_path=None,
            recommendation=(
                "No hay swatch de referencia para esta tela. Agregar imagen en "
                f"swatches/{normalized_fabric}.jpg."
            ),
        )

    capture_sig = build_signature(capture)
    swatch_sig = catalog.get_signature(swatch_path)
    score = signature_distance(capture_sig, swatch_sig)

    if score <= match_threshold:
        status = "OK"
        recommendation = "Tela validada contra swatch."
    elif score <= match_threshold * (1 + REVIEW_BAND):
        status = "REVIEW"
        recommendation = (
            "La captura se aleja del swatch esperado: validar tela fisica, "
            "iluminacion y acomodo antes de aprobar."
        )
    else:
        status = "MISMATCH"
        recommendation = (
            "Mismatch visual de tela: validar swatch, iluminacion y que la tela "
            "fisica corresponda al QR antes de continuar."
        )

    return SwatchValidationResult(
        status=status, score=score, swatch_path=str(swatch_path), recommendation=recommendation
    )
