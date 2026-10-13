from pathlib import Path

import pytest
from pydantic import ValidationError

from royale_mind.config import Settings, SettingsError, load_settings


def test_defaults_load_when_configuration_is_absent(tmp_path: Path) -> None:
    settings = load_settings(tmp_path / "missing.toml")

    assert settings.log_level == "INFO"
    assert settings.log_json is True
    assert settings.data_dir == Path("data")


def test_valid_toml_configuration_loads(tmp_path: Path) -> None:
    config_path = tmp_path / "settings.toml"
    config_path.write_text(
        'log_level = "DEBUG"\nlog_json = false\ndata_dir = "local-data"\n',
        encoding="utf-8",
    )

    settings = load_settings(config_path)

    assert settings == Settings(log_level="DEBUG", log_json=False, data_dir=Path("local-data"))


def test_invalid_configuration_fails_with_path_context(tmp_path: Path) -> None:
    config_path = tmp_path / "invalid.toml"
    config_path.write_text('log_level = "TRACE"\n', encoding="utf-8")

    with pytest.raises(SettingsError, match=str(config_path)):
        load_settings(config_path)


def test_unknown_configuration_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({"log_level": "INFO", "send_screenshots": True})


def test_capture_configuration_is_validated() -> None:
    with pytest.raises(ValidationError):
        Settings(adb_timeout_seconds=0)
    with pytest.raises(ValidationError):
        Settings(device_serial="")


def test_malformed_toml_fails_safely(tmp_path: Path) -> None:
    config_path = tmp_path / "malformed.toml"
    config_path.write_text("log_level = [", encoding="utf-8")

    with pytest.raises(SettingsError, match="Invalid RoyaleMind configuration"):
        load_settings(config_path)
