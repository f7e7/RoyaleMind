"""Command-line entry point for RoyaleMind local diagnostics."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from royale_mind.capture import AdbScreenshotSource, CaptureError, save_frame
from royale_mind.data_acquisition.acquire import AcquisitionError, acquire_catalog
from royale_mind.data_acquisition.coverage import (
    build_coverage_report,
    write_coverage_report,
    write_human_coverage_report,
    write_normalized_validation,
)
from royale_mind.data_acquisition.normalize import normalize_cards, normalize_reference_sources
from royale_mind.data_acquisition.schemas import export_schemas
from royale_mind.data_acquisition.validate import (
    ingest_annotations,
    inspect_dataset,
    validate_cards,
    validate_source_manifest,
    write_dataset_inspection,
)
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
    capture_parser = subparsers.add_parser(
        "capture-frame", help="Save one read-only ADB screenshot and metadata locally"
    )
    capture_parser.add_argument("--output-dir", type=Path, default=Path("data/captures"))
    capture_parser.add_argument("--serial", help="ADB device serial; overrides local configuration")
    acquire_parser = subparsers.add_parser(
        "acquire-data", help="Acquire bounded, pinned metadata and generate local reports"
    )
    acquire_parser.add_argument("--output", type=Path, default=Path("data"))
    acquire_parser.add_argument(
        "--accept-unknown-license-local-only",
        action="store_true",
        help="Acknowledge that cr-api-data has no declared license; keep output private/local",
    )
    audit_parser = subparsers.add_parser(
        "audit-dataset", help="Audit user-supplied image and Labelme/YOLO dataset files"
    )
    audit_parser.add_argument("dataset", type=Path)
    audit_parser.add_argument(
        "--output", type=Path, default=Path("reports/dataset-inspection.json")
    )
    import_parser = subparsers.add_parser(
        "import-dataset-labels",
        help="Convert supported user-provided Labelme/YOLO boxes, preserving source classes",
    )
    import_parser.add_argument("dataset", type=Path)
    import_parser.add_argument(
        "--output", type=Path, default=Path("data/processed/visual_labels/annotations.json")
    )
    schema_parser = subparsers.add_parser(
        "export-data-schemas", help="Export JSON Schemas for acquisition records"
    )
    schema_parser.add_argument("--output", type=Path, default=Path("docs/schemas"))
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


def _capture_frame(settings: Settings, output_dir: Path, serial: str | None) -> int:
    try:
        frame = AdbScreenshotSource(
            adb_path=settings.adb_path,
            timeout_seconds=settings.adb_timeout_seconds,
            device_serial=serial or settings.device_serial,
        ).capture()
        image_path, metadata_path = save_frame(frame, output_dir)
    except (CaptureError, OSError) as exc:
        print(
            f"Capture failed: {exc}. Check `royalemind devices` and the output directory.",
            file=sys.stderr,
        )
        return 1
    print(f"Saved {image_path} and {metadata_path}")
    return 0


def _acquire_data(output_root: Path, accept_unknown_license: bool) -> int:
    try:
        manifest = acquire_catalog(
            output_root,
            accept_unknown_license_local_only=accept_unknown_license,
        )
        manifest_path = output_root / "manifests" / "cr-api-data.json"
        source_errors = validate_source_manifest(manifest_path)
        if source_errors:
            for error in source_errors:
                print(f"SOURCE VALIDATION ERROR: {error}")
            return 1
        normalized_path = output_root / "processed" / "cards" / "cards.json"
        records = normalize_cards(manifest_path, normalized_path)
        normalize_reference_sources(manifest_path, output_root)
        errors = validate_cards(records)
        write_normalized_validation(records, output_root / "reports" / "validation.json")
        coverage = build_coverage_report(
            records,
            imported_source_count=len(manifest.files),
        )
        write_coverage_report(coverage, output_root / "reports" / "coverage.json")
        write_human_coverage_report(coverage, output_root / "reports" / "coverage.md")
    except (AcquisitionError, OSError, ValueError) as exc:
        print(f"Data acquisition failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Verified {len(manifest.files)} pinned JSON sources and normalized "
        f"{len(records)} card/variant records into {normalized_path}."
    )
    if errors:
        for error in errors:
            print(f"VALIDATION ERROR: {error}")
        return 1
    print(f"Validation and coverage reports written under {output_root / 'reports'}.")
    return 0


def _audit_dataset(dataset_path: Path, output_path: Path) -> int:
    try:
        inspection = inspect_dataset(dataset_path)
        write_dataset_inspection(inspection, output_path)
    except (OSError, ValueError) as exc:
        print(f"Dataset audit failed: {exc}", file=sys.stderr)
        return 1

    print(
        f"Inspected {inspection.image_count} images and {inspection.annotation_count} annotations; "
        f"report: {output_path}"
    )
    print(
        f"Corrupt images: {len(inspection.corrupt_images)}; malformed annotations: "
        f"{len(inspection.malformed_annotations)}; duplicate groups: "
        f"{len(inspection.duplicate_image_groups)}; split leaks: {len(inspection.split_leaks)}"
    )
    return 1 if inspection.corrupt_images or inspection.malformed_annotations else 0


def _import_dataset_labels(dataset_path: Path, output_path: Path) -> int:
    try:
        annotations = ingest_annotations(dataset_path, output_path)
    except (OSError, ValueError) as exc:
        print(f"Dataset label import failed: {exc}", file=sys.stderr)
        return 1
    print(
        f"Imported {len(annotations)} source labels without canonical class mapping "
        f"to {output_path}."
    )
    return 0


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
    if args.command == "capture-frame":
        return _capture_frame(settings, args.output_dir, args.serial)
    if args.command == "acquire-data":
        return _acquire_data(args.output, args.accept_unknown_license_local_only)
    if args.command == "audit-dataset":
        return _audit_dataset(args.dataset, args.output)
    if args.command == "import-dataset-labels":
        return _import_dataset_labels(args.dataset, args.output)
    if args.command == "export-data-schemas":
        try:
            paths = export_schemas(args.output)
        except OSError as exc:
            print(f"Could not export data schemas: {exc}", file=sys.stderr)
            return 1
        for path in paths:
            print(path)
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
