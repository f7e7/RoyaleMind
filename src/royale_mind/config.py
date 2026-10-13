"""Validated local configuration loading."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class Settings(BaseModel):
    """Small local settings surface for the initial application foundation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_json: bool = True
    data_dir: Path = Field(default=Path("data"))
    adb_path: str = Field(default="adb", min_length=1)
    adb_timeout_seconds: float = Field(default=10.0, gt=0.0, le=120.0)
    device_serial: str | None = Field(default=None, min_length=1)


class SettingsError(ValueError):
    """Raised when a local settings file cannot be loaded or validated."""


def load_settings(path: Path | None = None) -> Settings:
    """Load optional TOML settings and validate them; no file means safe defaults."""

    config_path = path or Path(os.environ.get("ROYALEMIND_CONFIG", "royalemind.toml"))
    if not config_path.exists():
        return Settings()

    try:
        with config_path.open("rb") as config_file:
            values = tomllib.load(config_file)
        return Settings.model_validate(values)
    except (OSError, tomllib.TOMLDecodeError, ValidationError) as exc:
        raise SettingsError(f"Invalid RoyaleMind configuration at {config_path}: {exc}") from exc
