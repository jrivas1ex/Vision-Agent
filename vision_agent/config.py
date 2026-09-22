"""
Config loading for Vision Agent.

Keys below match the shipped ``vision_agent_config.ini`` exactly
(recovered as literal property names inside VisionAgent.exe: GetIni,
ReadIni, ToConfigString, VisionStationFolder, OutputRoot, SwatchRoot,
CaptureDelayMs, CaptureMode, VisualValidationLayers, FabricImageRoot):

    [VisionAgent]
    visionstation_folder = .
    output_root = VisionAgentData
    swatch_root = swatches
    capture_delay_ms = 100
    capture_mode = all
    visual_validation_layers = 1,2,3
    fabric_image_root = fabric_part_images
"""

from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class VisionAgentConfig:
    visionstation_folder: str = "."
    output_root: str = "VisionAgentData"
    swatch_root: str = "swatches"
    capture_delay_ms: int = 100
    capture_mode: str = "all"
    visual_validation_layers: list[int] = field(default_factory=lambda: [1, 2, 3])
    fabric_image_root: str = "fabric_part_images"

    # Not present in the shipped .ini but referenced by the reconstructed
    # swatch/fabric matchers -- exposed here so they're easy to tune
    # without touching code. Defaults are APPROXIMATIONs (see swatch.py /
    # fabric_classifier.py docstrings).
    swatch_match_threshold: float = 18.0
    fabric_min_confidence: float = 0.55

    base_dir: Path = field(default_factory=Path, repr=False)

    @classmethod
    def load(cls, path: str | Path) -> "VisionAgentConfig":
        path = Path(path)
        parser = configparser.ConfigParser()
        parser.read(path, encoding="utf-8")
        section = parser["VisionAgent"] if parser.has_section("VisionAgent") else parser[parser.default_section]

        layers_raw = section.get("visual_validation_layers", "1,2,3")
        layers = [int(x.strip()) for x in layers_raw.split(",") if x.strip()]

        return cls(
            visionstation_folder=section.get("visionstation_folder", "."),
            output_root=section.get("output_root", "VisionAgentData"),
            swatch_root=section.get("swatch_root", "swatches"),
            capture_delay_ms=section.getint("capture_delay_ms", fallback=100),
            capture_mode=section.get("capture_mode", "all"),
            visual_validation_layers=layers,
            fabric_image_root=section.get("fabric_image_root", "fabric_part_images"),
            swatch_match_threshold=section.getfloat("swatch_match_threshold", fallback=18.0),
            fabric_min_confidence=section.getfloat("fabric_min_confidence", fallback=0.55),
            base_dir=path.resolve().parent,
        )

    def to_config_string(self) -> str:
        """Mirrors ``ToConfigString`` -- round-trips back to .ini text."""
        layers = ",".join(str(x) for x in self.visual_validation_layers)
        return (
            "[VisionAgent]\n"
            f"visionstation_folder = {self.visionstation_folder}\n"
            f"output_root = {self.output_root}\n"
            f"swatch_root = {self.swatch_root}\n"
            f"capture_delay_ms = {self.capture_delay_ms}\n"
            f"capture_mode = {self.capture_mode}\n"
            f"visual_validation_layers = {layers}\n"
            f"fabric_image_root = {self.fabric_image_root}\n"
        )

    # --- resolved paths -------------------------------------------------

    def resolve(self, relative: str) -> Path:
        p = Path(relative)
        return p if p.is_absolute() else self.base_dir / p

    @property
    def swatch_path(self) -> Path:
        return self.resolve(self.swatch_root)

    @property
    def fabric_image_path(self) -> Path:
        return self.resolve(self.fabric_image_root)

    @property
    def output_path(self) -> Path:
        return self.resolve(self.output_root)

    @property
    def events_csv_path(self) -> Path:
        return self.output_path / "vision_agent_events.csv"

    @property
    def products_csv_path(self) -> Path:
        return self.output_path / "vision_agent_products.csv"

    @property
    def visual_features_csv_path(self) -> Path:
        return self.output_path / "vision_agent_visual_features.csv"

    @property
    def swatch_validation_csv_path(self) -> Path:
        return self.output_path / "vision_agent_swatch_validation.csv"

    @property
    def fabric_classification_csv_path(self) -> Path:
        return self.output_path / "vision_agent_fabric_classification.csv"

    @property
    def learning_csv_path(self) -> Path:
        return self.output_path / "vision_agent_learning.csv"

    @property
    def inspection_time_csv_path(self) -> Path:
        return self.output_path / "vision_agent_inspection_time.csv"

    @property
    def kova_models_path(self) -> Path:
        """Real kova_models.csv (ss_code,model_name,required_fabrics),
        expected next to vision_agent_config.ini -- same file FabricVision
        uses. Falls back to the approximated matrix if not found."""
        return self.resolve("kova_models.csv")

    @property
    def reports_dir(self) -> Path:
        return self.output_path / "reports"

    @property
    def shift_reports_dir(self) -> Path:
        return self.output_path / "shift_reports"

    @property
    def screenshots_dir(self) -> Path:
        return self.output_path / "screenshots"

    def ensure_dirs(self) -> None:
        for d in (self.output_path, self.reports_dir, self.shift_reports_dir, self.screenshots_dir):
            d.mkdir(parents=True, exist_ok=True)
