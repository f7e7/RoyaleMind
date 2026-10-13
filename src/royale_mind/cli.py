"""Command-line entry point for RoyaleMind local diagnostics."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING

from royale_mind.diagnostics import (
    CheckStatus,
    check_adb_executable,
    check_python_dependencies,
    diagnose_devices,
)
from royale_mind.logging_setup import configure_logging

logger = logging.getLogger("royale_mind")

if TYPE_CHECKING:
    from royale_mind.config import Settings


def _load_settings() -> Settings:
    from royale_mind.config import load_settings

    return load_settings()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="royalemind",
        description="Local read-only Clash Royale analysis foundations and diagnostics.",
    )
    parser.add_argument(
        "--log-level",
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
        help="Override the configured log level",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("health", help="Check Python dependencies and optional ADB availability")
    subparsers.add_parser("devices", help="Report connected Android devices and authorization")
    parser.set_defaults(command="health")
    return parser


def _print_health(settings: Settings) -> int:
    checks = [*check_python_dependencies(), check_adb_executable(settings.adb_path)]
    has_errors = False
    for check in checks:
        print(f"{check.status.value.upper()}: {check.name}: {check.message}")
        has_errors |= check.status is CheckStatus.ERROR
    if not has_errors:
        print("RoyaleMind startup health check passed; vision and dashboard are not implemented.")
    return 1 if has_errors else 0


def _print_devices(settings: Settings) -> int:
    try:
        devices = diagnose_devices(
            adb_path=settings.adb_path,
            timeout_seconds=settings.adb_timeout_seconds,
        )
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if not devices:
        print("No Android devices are connected.")
        return 1

    for device in devices:
        state = "authorized" if device.authorized else "not authorized"
        print(f"{device.serial}: {device.status} ({state}) - {device.message}")

    return 0 if all(device.authorized for device in devices) else 1


def main(argv: Sequence[str] | None = None) -> int:
    """Load settings, configure logs, run a diagnostic command, and return a process code."""

    args = _parser().parse_args(argv)
    dependency_checks = check_python_dependencies()
    missing_dependencies = [
        check for check in dependency_checks if check.status is CheckStatus.ERROR
    ]
    if missing_dependencies:
        for check in dependency_checks:
            print(f"{check.status.value.upper()}: {check.name}: {check.message}")
        return 1

    try:
        settings = _load_settings()
    except ModuleNotFoundError as exc:
        print(
            f"Required Python dependency '{exc.name}' is missing. "
            "Install RoyaleMind with: python -m pip install -e '.[dev]'",
            file=sys.stderr,
        )
        return 1
    except ValueError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2

    configure_logging(level=args.log_level or settings.log_level, json_output=settings.log_json)
    logger.debug("starting diagnostic command", extra={"command": args.command})
    adb_check = check_adb_executable(settings.adb_path)
    if adb_check.status is CheckStatus.WARNING:
        logger.warning(adb_check.message)

    if args.command == "health":
        return _print_health(settings)
    if args.command == "devices":
        return _print_devices(settings)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
