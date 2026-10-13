"""Read-only startup and Android Debug Bridge diagnostics."""

from __future__ import annotations

import importlib.metadata
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum


class CheckStatus(StrEnum):
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class Diagnostic:
    name: str
    status: CheckStatus
    message: str


@dataclass(frozen=True, slots=True)
class DeviceDiagnostic:
    serial: str
    status: str
    authorized: bool
    message: str


Runner = Callable[..., subprocess.CompletedProcess[str]]


def check_python_dependencies() -> list[Diagnostic]:
    """Report required Python distributions and the optional Pillow capture dependency."""

    checks: list[Diagnostic] = []
    for distribution in ("pydantic", "Pillow"):
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            checks.append(
                Diagnostic(
                    name=distribution,
                    status=CheckStatus.ERROR,
                    message=(
                        f"Required Python dependency '{distribution}' is missing. "
                        "Install RoyaleMind with: python -m pip install -e '.[dev]'"
                    ),
                )
            )
        else:
            checks.append(
                Diagnostic(
                    name=distribution,
                    status=CheckStatus.OK,
                    message=f"{distribution} {version} is installed",
                )
            )
    return checks


def check_adb_executable(adb_path: str = "adb") -> Diagnostic:
    """Report whether the configured ADB executable can be resolved."""

    executable = shutil.which(adb_path)
    if executable is None:
        return Diagnostic(
            name="adb",
            status=CheckStatus.WARNING,
            message=(
                f"Android Debug Bridge executable '{adb_path}' was not found. "
                "Install Android Platform Tools manually or configure adb_path; "
                "replay mode remains available."
            ),
        )
    return Diagnostic(
        name="adb",
        status=CheckStatus.OK,
        message=f"Android Debug Bridge found at {executable}",
    )


def diagnose_devices(
    adb_path: str = "adb",
    timeout_seconds: float = 5.0,
    runner: Runner | None = None,
) -> list[DeviceDiagnostic]:
    """Inspect `adb devices -l`; do not alter device state or settings."""

    run = runner or subprocess.run
    try:
        result = run(
            [adb_path, "devices", "-l"],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            f"Android Debug Bridge executable '{adb_path}' was not found. "
            "Install Android Platform Tools manually or use replay mode."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Timed out while checking connected Android devices") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not run Android Debug Bridge: {exc}") from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or "ADB exited with a non-zero status"
        raise RuntimeError(f"Could not list Android devices: {detail}")

    devices: list[DeviceDiagnostic] = []
    for line in result.stdout.splitlines()[1:]:
        fields = line.split()
        if len(fields) < 2:
            continue
        serial, device_status = fields[:2]
        if device_status == "device":
            message = "Connected and authorized"
            authorized = True
        elif device_status == "unauthorized":
            message = "Connected but unauthorized; approve the USB debugging prompt on the device"
            authorized = False
        elif device_status == "offline":
            message = "Device is connected but offline"
            authorized = False
        else:
            message = f"Device is not ready (ADB status: {device_status})"
            authorized = False
        devices.append(
            DeviceDiagnostic(
                serial=serial,
                status=device_status,
                authorized=authorized,
                message=message,
            )
        )

    return devices
