import importlib.metadata
import subprocess

import pytest

from royale_mind.diagnostics import (
    CheckStatus,
    check_adb_executable,
    check_python_dependencies,
    diagnose_devices,
)


def test_python_dependency_check_reports_missing_distribution(monkeypatch) -> None:
    def version(distribution: str) -> str:
        if distribution == "Pillow":
            raise importlib.metadata.PackageNotFoundError(distribution)
        return "2.0"

    monkeypatch.setattr(importlib.metadata, "version", version)

    checks = check_python_dependencies()

    assert [check.status for check in checks] == [CheckStatus.OK, CheckStatus.ERROR]
    assert "pip install -e '.[dev]'" in checks[1].message


def test_adb_health_check_reports_missing_executable(monkeypatch) -> None:
    monkeypatch.setattr("royale_mind.diagnostics.shutil.which", lambda executable: None)

    check = check_adb_executable("missing-adb")

    assert check.status is CheckStatus.WARNING
    assert "replay mode remains available" in check.message


def test_device_diagnostic_reports_authorized_and_unauthorized_devices() -> None:
    def runner(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        assert command == ["adb", "devices", "-l"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "List of devices attached\n"
                "serial-good device product:phone\n"
                "serial-pending unauthorized usb:1-2\n"
                "serial-offline offline transport_id:3\n"
            ),
            stderr="",
        )

    devices = diagnose_devices(runner=runner)

    assert [(device.serial, device.authorized) for device in devices] == [
        ("serial-good", True),
        ("serial-pending", False),
        ("serial-offline", False),
    ]
    assert "approve the USB debugging prompt" in devices[1].message
    assert devices[2].status == "offline"


def test_device_diagnostic_handles_empty_list_and_adb_errors() -> None:
    def no_devices(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            command, 0, stdout="List of devices attached\n", stderr=""
        )

    assert diagnose_devices(runner=no_devices) == []

    def missing(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("adb missing")

    with pytest.raises(RuntimeError, match="executable 'adb' was not found"):
        diagnose_devices(runner=missing)

    def failed(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="server unavailable")

    with pytest.raises(RuntimeError, match="server unavailable"):
        diagnose_devices(runner=failed)


def test_device_diagnostic_maps_timeout() -> None:
    def timed_out(command: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    with pytest.raises(RuntimeError, match="Timed out"):
        diagnose_devices(runner=timed_out)
