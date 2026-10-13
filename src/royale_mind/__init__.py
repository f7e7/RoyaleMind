"""RoyaleMind public interfaces, loaded lazily for dependency diagnostics."""

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "AdbScreenshotSource": "capture",
    "BoundingBox": "domain",
    "BuildingObservation": "domain",
    "CardObservation": "domain",
    "CaptureError": "capture",
    "CaptureTimeout": "capture",
    "DeviceUnavailable": "capture",
    "Estimate": "domain",
    "ElixirObservation": "domain",
    "Frame": "capture",
    "FrameMetadata": "domain",
    "FrameSource": "capture",
    "Freshness": "domain",
    "GamePhase": "domain",
    "GamePhaseObservation": "domain",
    "GameState": "domain",
    "ImagePoint": "domain",
    "InvalidFrame": "capture",
    "ObservationMetadata": "domain",
    "ObservationProvenance": "domain",
    "ReplayFrameSource": "capture",
    "Settings": "config",
    "SettingsError": "config",
    "TacticalCandidateAction": "domain",
    "TacticalRecommendation": "domain",
    "Team": "domain",
    "TowerObservation": "domain",
    "UnitObservation": "domain",
    "configure_logging": "logging_setup",
    "load_settings": "config",
}

__all__ = [
    *_EXPORT_MODULES,
]


def __getattr__(name: str) -> Any:
    """Load public APIs on demand so the CLI can diagnose missing dependencies."""

    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{module_name}")
    value = getattr(module, name)
    globals()[name] = value
    return value
