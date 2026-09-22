"""
VisualFeatureExtractor -- local, offline pixel statistics on a captured
screenshot/crop.

Class name and property names (Brightness, Contrast, DarkRatio,
SaturatedRatio, RedAlertRatio, ColorfulRatio, TexturedRatio,
BrightnessSum, ContrastSum) were recovered from VisionAgent.exe's
metadata. The exact per-pixel math was not recoverable from a compiled
binary, so the formulas below are a documented, tunable APPROXIMATION
using plain Pillow + a numpy-free running-stats pass (matching the
"no YOLO, no API, no internet" design goal: pure local pixel math).

RedAlertRatio in particular is designed to catch the case CHANGELOG
warns about ("Aparecen pantallas rojas/error con frecuencia") -- IV4's
own red error/fail overlay dominating the captured frame.
"""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image


@dataclass
class VisualFeatures:
    brightness: float          # 0-255 average luminance
    contrast: float            # stdev of luminance
    dark_ratio: float          # fraction of near-black pixels
    saturated_ratio: float     # fraction of near-white / blown-out pixels
    red_alert_ratio: float     # fraction of pixels where red strongly dominates
    colorful_ratio: float      # fraction of pixels with meaningful saturation
    textured_ratio: float      # fraction of pixels differing sharply from neighbor (edge density)

    def as_row(self) -> list[str]:
        return [
            f"{self.brightness:.2f}",
            f"{self.contrast:.2f}",
            f"{self.dark_ratio:.4f}",
            f"{self.saturated_ratio:.4f}",
            f"{self.red_alert_ratio:.4f}",
        ]


# APPROXIMATION thresholds -- tune against real captures.
DARK_THRESHOLD = 40
SATURATED_THRESHOLD = 235
RED_DOMINANCE_MARGIN = 40
SAT_MIN = 60
EDGE_DELTA = 25
MAX_SAMPLE_DIM = 240  # downsample for speed; ratios are scale-invariant enough


def extract_visual_features(image: Image.Image) -> VisualFeatures:
    """ExtractVisualFeatures: single pass over (a downsampled copy of)
    the image computing all ratios/statistics at once."""
    img = image.convert("RGB")
    w, h = img.size
    scale = min(1.0, MAX_SAMPLE_DIM / max(w, h))
    if scale < 1.0:
        img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))))
    w, h = img.size
    px = img.load()

    n = w * h
    brightness_sum = 0.0
    contrast_sq_sum = 0.0  # accumulate luminance^2 for a single-pass stdev
    dark = saturated = red_alert = colorful = 0
    textured = 0

    lum_row_prev = None
    for y in range(h):
        lum_row = [0.0] * w
        for x in range(w):
            r, g, b = px[x, y]
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            lum_row[x] = lum
            brightness_sum += lum
            contrast_sq_sum += lum * lum

            if lum <= DARK_THRESHOLD:
                dark += 1
            if lum >= SATURATED_THRESHOLD:
                saturated += 1

            mx, mn = max(r, g, b), min(r, g, b)
            if mx - mn >= SAT_MIN:
                colorful += 1
            if r - max(g, b) >= RED_DOMINANCE_MARGIN:
                red_alert += 1

            if x > 0 and abs(lum - lum_row[x - 1]) >= EDGE_DELTA:
                textured += 1
            elif lum_row_prev is not None and abs(lum - lum_row_prev[x]) >= EDGE_DELTA:
                textured += 1
        lum_row_prev = lum_row

    mean = brightness_sum / n
    variance = max(0.0, contrast_sq_sum / n - mean * mean)
    contrast = variance ** 0.5

    return VisualFeatures(
        brightness=mean,
        contrast=contrast,
        dark_ratio=dark / n,
        saturated_ratio=saturated / n,
        red_alert_ratio=red_alert / n,
        colorful_ratio=colorful / n,
        textured_ratio=textured / n,
    )
