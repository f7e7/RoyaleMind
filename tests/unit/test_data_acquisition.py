import hashlib
import json
from datetime import UTC, datetime
from http.client import HTTPMessage
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError

import pytest
from PIL import Image

from royale_mind.data_acquisition.acquire import AcquisitionError, acquire_catalog
from royale_mind.data_acquisition.arena import CalibrationError, fit_arena_mapper
from royale_mind.data_acquisition.catalog import SOURCES
from royale_mind.data_acquisition.models import ArenaCorrespondence, CoordinatePoint
from royale_mind.data_acquisition.normalize import normalize_cards
from royale_mind.data_acquisition.validate import (
    ingest_annotations,
    inspect_dataset,
    validate_cards,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (20, 10), color=(20, 30, 40)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_catalog_acquisition_requires_explicit_unknown_license_acknowledgement(
    tmp_path: Path,
) -> None:
    with pytest.raises(AcquisitionError, match="no declared repository license"):
        acquire_catalog(tmp_path)


def test_catalog_limits_before_network_and_rejects_changed_existing_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    calls: list[str] = []

    def fake_download(url: str, timeout_seconds: float, retries: int, max_bytes: int) -> bytes:
        calls.append(url)
        return b"[]"

    monkeypatch.setattr("royale_mind.data_acquisition.acquire._download", fake_download)
    manifest = acquire_catalog(tmp_path, accept_unknown_license_local_only=True)
    assert len(manifest.files) == len(SOURCES)
    assert len(calls) == len(SOURCES)
    assert manifest.files[0].license_status.startswith("unknown")

    # A complete verified local snapshot must not trigger another download.
    assert acquire_catalog(tmp_path, accept_unknown_license_local_only=True) == manifest
    assert len(calls) == len(SOURCES)

    existing = Path(manifest.files[0].raw_path)
    existing.write_bytes(b"changed by local owner")
    with pytest.raises(AcquisitionError, match="Existing snapshot is unreadable"):
        acquire_catalog(tmp_path, accept_unknown_license_local_only=True)


def test_retry_policy_retries_transient_http_failure(tmp_path: Path, monkeypatch) -> None:
    calls = 0

    class Response(BytesIO):
        headers = HTTPMessage()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    def fake_urlopen(request, timeout: float):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPError(request.full_url, 503, "busy", {}, None)
        return Response(b"[]")

    monkeypatch.setattr("royale_mind.data_acquisition.acquire.urlopen", fake_urlopen)
    monkeypatch.setattr("royale_mind.data_acquisition.acquire.time.sleep", lambda delay: None)
    acquire_catalog(tmp_path, accept_unknown_license_local_only=True)
    assert calls == len(SOURCES) + 1


def test_card_normalization_preserves_unknowns_and_source_provenance(tmp_path: Path) -> None:
    raw_root = tmp_path / "raw"
    raw_root.mkdir()
    cards = [
        {
            "key": "knight",
            "name": "Knight",
            "sc_key": "Knight",
            "id": 26000000,
            "type": "Troop",
            "rarity": "Common",
            "elixir": 3,
            "arena": 0,
            "is_evolved": False,
        }
    ]
    evolution = cards + [
        {**cards[0], "key": "knight-ev1", "is_evolved": True, "evolution_level": 1}
    ]
    localized = [{**cards[0], "_lang": {"name": {"en": "Knight", "fr": "Chevalier"}}}]
    stats = {
        "troop": [
            {
                "key": "knight",
                "name_en": "Knight",
                "hitpoints_per_level": None,
                "damage_per_level": None,
                "highres_image_filename": "image/chr/knight.png",
            }
        ]
    }
    source_defs = [
        ("cards", "cards.json", cards),
        ("cards_evo", "cards_evo.json", evolution),
        ("cards_i18n_evo", "cards_i18n_evo.json", localized),
        ("cards_stats", "cards_stats.json", stats),
    ]
    manifest_files = []
    for name, filename, payload in source_defs:
        raw_path = raw_root / filename
        raw_bytes = json.dumps(payload).encode()
        raw_path.write_bytes(raw_bytes)
        manifest_files.append(
            {
                "name": name,
                "category": "card_statistics" if "stats" in name else "cards",
                "url": f"https://source.invalid/{filename}",
                "repository_revision": "revision-1",
                "repository_commit_date": "2025-01-01T00:00:00Z",
                "license": None,
                "license_status": "unknown; local research only",
                "repository_reported_size_bytes": len(raw_bytes),
                "retrieved_at": NOW.isoformat(),
                "downloaded_size_bytes": len(raw_bytes),
                "sha256": hashlib.sha256(raw_bytes).hexdigest(),
                "raw_path": str(raw_path),
            }
        )
    manifest_path = tmp_path / "manifests" / "source.json"
    manifest_path.parent.mkdir()
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "source_repository": "https://source.invalid",
                "retrieved_at": NOW.isoformat(),
                "files": manifest_files,
            }
        ),
        encoding="utf-8",
    )

    output_path = tmp_path / "processed" / "cards.json"
    records = normalize_cards(manifest_path, output_path)

    assert {record.key for record in records} == {"knight", "knight-ev1"}
    base = next(record for record in records if record.key == "knight")
    assert base.localized_names["fr"] == "Chevalier"
    assert base.elixir_cost == 3
    assert base.stat_sources
    assert base.image_references == ["image/chr/knight.png"]
    assert base.provenance[0].license_status.startswith("unknown")
    assert validate_cards(records) == []
    assert output_path.exists()


def test_dataset_audit_detects_corruption_invalid_boxes_duplicates_and_split_leak(tmp_path: Path):
    train_dir = tmp_path / "train"
    test_dir = tmp_path / "test"
    train_dir.mkdir()
    test_dir.mkdir()

    buffer = BytesIO()
    Image.new("RGB", (20, 10), color=(20, 30, 40)).save(buffer, format="PNG")
    image_data = buffer.getvalue()
    (train_dir / "frame.png").write_bytes(image_data)
    (test_dir / "copy.png").write_bytes(image_data)
    (train_dir / "frame.txt").write_text("0 0.5 0.5 1.2 0.2\n", encoding="utf-8")
    (train_dir / "bad.png").write_bytes(b"broken")
    (train_dir / "other.bin").write_bytes(b"unsupported")

    inspection = inspect_dataset(tmp_path)

    assert inspection.image_count == 3
    assert inspection.annotation_count == 1
    assert len(inspection.corrupt_images) == 1
    assert len(inspection.duplicate_image_groups) == 1
    assert len(inspection.split_leaks) == 1
    assert inspection.malformed_annotations
    assert inspection.annotation_formats == {"yolo": 1}
    assert any(path.endswith("other.bin") for path in inspection.unsupported_files)


def test_dataset_label_ingestion_preserves_original_classes_and_provenance(tmp_path: Path) -> None:
    image_path = tmp_path / "frame.png"
    image_path.write_bytes(png_bytes())
    label_path = tmp_path / "frame.txt"
    label_path.write_text("17 0.5 0.5 0.4 0.2 1 0 0 0 0 0 0\n", encoding="utf-8")

    output_path = tmp_path / "processed" / "labels.json"
    annotations = ingest_annotations(tmp_path, output_path)

    assert len(annotations) == 1
    assert annotations[0].source_class_id == 17
    assert annotations[0].canonical_class_id is None
    assert annotations[0].affiliation == 1
    assert annotations[0].x_min == pytest.approx(0.3)
    assert annotations[0].y_max == pytest.approx(0.6)
    assert annotations[0].image_sha256 == hashlib.sha256(image_path.read_bytes()).hexdigest()
    assert output_path.exists()


def test_dataset_label_ingestion_does_not_guess_unknown_yolo_extensions(tmp_path: Path) -> None:
    (tmp_path / "frame.png").write_bytes(png_bytes())
    (tmp_path / "frame.txt").write_text("0 0.5 0.5 0.2 0.2 1 9\n", encoding="utf-8")

    with pytest.raises(ValueError, match="audit it first"):
        ingest_annotations(tmp_path, tmp_path / "labels.json")


def test_dataset_audit_accepts_two_formats_for_one_image(tmp_path: Path) -> None:
    (tmp_path / "frame.png").write_bytes(png_bytes())
    (tmp_path / "frame.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (tmp_path / "frame.json").write_text(
        json.dumps({"shapes": [{"label": "source-label", "points": [[1, 1], [5, 5]]}]}),
        encoding="utf-8",
    )
    inspection = inspect_dataset(tmp_path)
    assert inspection.image_count == 1
    assert inspection.annotation_count == 2
    assert inspection.annotation_formats == {"labelme": 1, "yolo": 1}
    assert inspection.malformed_annotations == []


def test_arena_mapper_requires_non_degenerate_measured_correspondences(tmp_path: Path) -> None:
    image_path = tmp_path / "screen.png"
    image_path.write_bytes(b"user-provided image hash source")
    correspondences = [
        ArenaCorrespondence(
            label=f"p{index}",
            screenshot_point=CoordinatePoint(x=x, y=y),
            arena_point=CoordinatePoint(x=x, y=y),
            provenance="manual measurement",
        )
        for index, (x, y) in enumerate(((0.1, 0.1), (0.8, 0.1), (0.1, 0.8)))
    ]
    mapper = fit_arena_mapper(
        screenshot_path=image_path,
        width=1000,
        height=2000,
        correspondences=correspondences,
        arena_key="unverified-layout",
    )
    result = mapper.to_arena(CoordinatePoint(x=0.4, y=0.6))
    assert result.x == pytest.approx(0.4)
    assert result.y == pytest.approx(0.6)
    assert mapper.calibration.confidence is not None

    with pytest.raises(CalibrationError, match="At least three"):
        fit_arena_mapper(
            screenshot_path=image_path,
            width=1000,
            height=2000,
            correspondences=correspondences[:2],
        )


def test_calibration_rejects_collinear_points(tmp_path: Path) -> None:
    image_path = tmp_path / "screenshot.png"
    image_path.write_bytes(b"not interpreted; only fingerprinted")
    correspondences = [
        ArenaCorrespondence(
            label=str(index),
            screenshot_point=CoordinatePoint(x=value, y=value),
            arena_point=CoordinatePoint(x=value, y=value),
            provenance="manual measurement",
        )
        for index, value in enumerate((0.1, 0.4, 0.8))
    ]
    with pytest.raises(CalibrationError, match="degenerate"):
        fit_arena_mapper(
            screenshot_path=image_path,
            width=1,
            height=1,
            correspondences=correspondences,
        )
