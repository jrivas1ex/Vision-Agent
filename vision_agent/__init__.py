"""
Vision Agent (Python reconstruction)
====================================

This package is a from-scratch, Python re-implementation of the behavior
observed in ``VisionAgent.exe`` (release "SWATCH DATASET", 2026-09-11).

No original source code was available. The CSV schemas, config keys,
class names and validation logic below were reverse engineered from the
compiled .NET assembly's metadata/string tables (method names, property
names, embedded CSV header literals, HTML template fragments and regex
patterns were all present as plain text inside the binary) plus the
behavior documented in CHANGELOG.txt and LEAME.txt.

Anything that could not be recovered exactly from those sources (e.g. the
precise pixel-level thresholds used for brightness/contrast scoring, or
the exact swatch-signature distance formula) has been re-implemented with
a reasonable, documented approximation -- these are flagged with
``# APPROXIMATION`` comments throughout the code so they're easy to find
and tune against real plant data.

Public entry point for integration into another app (e.g. IV4 inspector):

    from vision_agent.core import VisionAgentCore
    from vision_agent.config import VisionAgentConfig

    config = VisionAgentConfig.load("vision_agent_config.ini")
    agent = VisionAgentCore(config)

    # Call this once per layer result, right when your own app receives
    # the IV4 response for that layer -- no log-polling needed if you
    # already know the event in real time.
    agent.handle_layer_event(
        work_order="WO12345",
        model="ARMLESS",
        fabric_raw="2011_FS33SBP_Mocha_Performance_Boucle_BTO_3292655.3.1.x.2",
        layer=1,
        program="P000",
        result="OK",
        raw_code="...",
        screenshot_path=None,  # or a path/PIL.Image you already captured
    )

See README.md for the full integration guide and for how to run this as
a standalone watcher (polling a VisionStation-style CSV log) exactly like
the original VisionAgent.exe did.
"""

from .core import VisionAgentCore
from .config import VisionAgentConfig

__all__ = ["VisionAgentCore", "VisionAgentConfig"]
