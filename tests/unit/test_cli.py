import subprocess

from royale_mind import cli, diagnostics
from royale_mind.config import Settings, SettingsError
from royale_mind.diagnostics import CheckStatus, Diagnostic


def test_health_command_reports_missing_adb_but_keeps_replay_available(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_load_settings", lambda: Settings())
    monkeypatch.setattr(cli, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(cli, "check_python_dependencies", lambda: [])
    monkeypatch.setattr(
        cli,
        "check_adb_executable",
        lambda adb_path: Diagnostic(
            name="adb",
            status=CheckStatus.WARNING,
            message="ADB missing; replay mode remains available",
        ),
    )

    result = cli.main(["health"])

    assert result == 0
    assert "WARNING: adb" in capsys.readouterr().out


def test_devices_command_reports_connection_state_with_mocked_runner(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_load_settings", lambda: Settings())
    monkeypatch.setattr(cli, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        diagnostics.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command,
            0,
            stdout="List of devices attached\nphone-1 device model:Android\n",
            stderr="",
        ),
    )

    result = cli.main(["devices"])

    assert result == 0
    assert "phone-1: device (authorized)" in capsys.readouterr().out


def test_devices_command_reports_no_device_as_failure(monkeypatch, capsys) -> None:
    monkeypatch.setattr(cli, "_load_settings", lambda: Settings())
    monkeypatch.setattr(cli, "configure_logging", lambda **kwargs: None)
    monkeypatch.setattr(
        diagnostics.subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout="List of devices attached\n", stderr=""
        ),
    )

    result = cli.main(["devices"])

    assert result == 1
    assert "No Android devices are connected" in capsys.readouterr().out


def test_invalid_settings_have_actionable_cli_error(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "_load_settings",
        lambda: (_ for _ in ()).throw(SettingsError("invalid log_level")),
    )

    result = cli.main(["health"])

    assert result == 2
    assert "Configuration error: invalid log_level" in capsys.readouterr().err


def test_default_command_runs_health_and_log_level_can_be_overridden(monkeypatch) -> None:
    settings = Settings(log_level="WARNING", log_json=False)
    configured: dict[str, object] = {}
    monkeypatch.setattr(cli, "_load_settings", lambda: settings)
    monkeypatch.setattr(cli, "configure_logging", lambda **kwargs: configured.update(kwargs))
    monkeypatch.setattr(cli, "check_python_dependencies", lambda: [])
    monkeypatch.setattr(
        cli,
        "check_adb_executable",
        lambda adb_path: Diagnostic(name="adb", status=CheckStatus.OK, message="ADB available"),
    )

    result = cli.main(["--log-level", "DEBUG"])

    assert result == 0
    assert configured == {"level": "DEBUG", "json_output": False}


def test_missing_python_dependency_stops_startup_with_install_instructions(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(
        cli,
        "check_python_dependencies",
        lambda: [
            Diagnostic(
                name="pydantic",
                status=CheckStatus.ERROR,
                message="Required Python dependency 'pydantic' is missing. Install with pip.",
            )
        ],
    )

    result = cli.main(["health"])

    assert result == 1
    assert "ERROR: pydantic" in capsys.readouterr().out
