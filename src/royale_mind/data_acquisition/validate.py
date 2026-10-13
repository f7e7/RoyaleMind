"""Structural, identity, numeric, and annotation validation utilities."""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from royale_mind.data_acquisition.acquire import AcquisitionManifest
from royale_mind.data_acquisition.models import CardRecord, DatasetInspection, VisualAnnotation

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
ANNOTATION_SUFFIXES = {".json", ".txt"}
SPLIT_NAMES = {"train", "training", "val", "valid", "validation", "test", "testing"}


def validate_cards(records: list[CardRecord]) -> list[str]:
    errors: list[str] = []
    keys = [record.key for record in records]
    duplicate_keys = sorted(key for key, count in Counter(keys).items() if count > 1)
    if duplicate_keys:
        errors.append(f"duplicate card keys: {', '.join(duplicate_keys)}")

    ids_to_keys: dict[int, set[str]] = defaultdict(set)
    for record in records:
        if record.stable_id is not None:
            ids_to_keys[record.stable_id].add(record.key)
        if record.elixir_cost is not None and not 0 <= record.elixir_cost <= 10:
            errors.append(f"{record.key}: elixir cost outside [0, 10]")
        for stats_source, stats in record.stat_sources.items():
            for numeric_key, value in stats.items():
                normalized_field = numeric_key.casefold().replace("_", "")
                must_be_nonnegative = normalized_field in {
                    "hitpoints",
                    "hitpointsperlevel",
                    "damage",
                    "damageperlevel",
                    "dps",
                    "dpsperlevel",
                    "manacost",
                    "elixircost",
                    "hitspeed",
                    "hitinterval",
                    "range",
                    "summonnumber",
                    "durationseconds",
                    "radius",
                    "projectileinterval",
                }
                if (
                    must_be_nonnegative
                    and isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and value < 0
                ):
                    errors.append(
                        f"{record.key}: negative nonnegative field {stats_source}.{numeric_key}"
                    )
    records_by_key = {record.key: record for record in records}
    for stable_id, keys_for_id in sorted(ids_to_keys.items()):
        if len(keys_for_id) <= 1:
            continue
        variants = [records_by_key[key] for key in keys_for_id]
        canonical_names = {record.canonical_name.casefold() for record in variants}
        evolution_states = {record.is_evolved for record in variants}
        if len(canonical_names) > 1 or len(evolution_states) == 1:
            errors.append(
                f"stable id {stable_id} maps to conflicting keys: {', '.join(sorted(keys_for_id))}"
            )
    return errors


def validate_source_manifest(manifest_path: Path) -> list[str]:
    """Verify source checksums and JSON syntax before consuming acquired files."""

    manifest = AcquisitionManifest.model_validate_json(manifest_path.read_bytes())
    errors: list[str] = []
    for source_file in manifest.files:
        path = Path(source_file.raw_path)
        try:
            content = path.read_bytes()
        except OSError as exc:
            errors.append(f"{source_file.name}: cannot read {path}: {exc}")
            continue
        if hashlib.sha256(content).hexdigest() != source_file.sha256:
            errors.append(f"{source_file.name}: SHA-256 mismatch for {path}")
            continue
        if len(content) != source_file.downloaded_size_bytes:
            errors.append(f"{source_file.name}: byte length mismatch for {path}")
            continue
        try:
            json.loads(content)
        except (json.JSONDecodeError, UnicodeDecodeError):
            errors.append(f"{source_file.name}: source snapshot is no longer valid JSON")
    return errors


def _split_name(path: Path, root: Path) -> str | None:
    for part in path.relative_to(root).parts[:-1]:
        if part.lower() in SPLIT_NAMES:
            return part.lower()
    return None


def _validate_labelme(
    path: Path, image_width: int, image_height: int
) -> tuple[Counter[str], str | None]:
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return Counter(), f"{path}: invalid Labelme JSON: {exc}"
    if not isinstance(document, dict) or not isinstance(document.get("shapes"), list):
        return Counter(), f"{path}: expected Labelme object with a shapes list"

    class_counts: Counter[str] = Counter()
    for index, shape in enumerate(document["shapes"]):
        if not isinstance(shape, dict) or not isinstance(shape.get("label"), str):
            return class_counts, f"{path}: shape {index} has no string label"
        class_counts[shape["label"]] += 1
        points = shape.get("points")
        if not isinstance(points, list) or len(points) < 2:
            return class_counts, f"{path}: shape {index} has invalid points"
        for point in points:
            if (
                not isinstance(point, list)
                or len(point) != 2
                or not all(
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and math.isfinite(value)
                    for value in point
                )
                or not 0 <= point[0] <= image_width
                or not 0 <= point[1] <= image_height
            ):
                return class_counts, f"{path}: shape {index} has out-of-image coordinates"
    return class_counts, None


def _validate_yolo(path: Path) -> tuple[Counter[str], str | None]:
    class_counts: Counter[str] = Counter()
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        return class_counts, f"{path}: cannot read YOLO labels: {exc}"

    for index, line in enumerate(lines):
        if not line.strip():
            continue
        fields = line.split()
        if len(fields) not in {5, 12}:
            return class_counts, f"{path}: line {index + 1} must have 5 or 12 fields"
        try:
            class_id = int(fields[0])
            coordinates = [float(value) for value in fields[1:5]]
        except ValueError:
            return class_counts, f"{path}: line {index + 1} has non-numeric fields"
        center_x, center_y, width, height = coordinates
        if (
            class_id < 0
            or not all(math.isfinite(value) for value in coordinates)
            or width <= 0
            or height <= 0
            or center_x - width / 2 < 0
            or center_y - height / 2 < 0
            or center_x + width / 2 > 1
            or center_y + height / 2 > 1
        ):
            return class_counts, f"{path}: line {index + 1} has invalid normalized bounds"
        if len(fields) == 12:
            try:
                affiliation = int(fields[5])
                trailing_zeros = [int(value) for value in fields[6:]]
            except ValueError:
                return class_counts, f"{path}: line {index + 1} has malformed extension fields"
            if (
                affiliation not in {0, 1}
                or len(trailing_zeros) != 6
                or any(value != 0 for value in trailing_zeros)
            ):
                return class_counts, f"{path}: line {index + 1} unsupported extended label format"
        class_counts[str(class_id)] += 1
    return class_counts, None


def inspect_dataset(root: Path, *, max_files: int = 100_000) -> DatasetInspection:
    """Audit supported image and Labelme/YOLO files without modifying the dataset."""

    root = root.resolve()
    if not root.is_dir():
        raise ValueError(f"Dataset root is not a directory: {root}")
    paths = sorted(path for path in root.rglob("*") if path.is_file())
    if len(paths) > max_files:
        raise ValueError(f"Dataset has {len(paths)} files; configured maximum is {max_files}")

    images = [path for path in paths if path.suffix.lower() in IMAGE_SUFFIXES]
    annotations = [path for path in paths if path.suffix.lower() in ANNOTATION_SUFFIXES]
    supported_suffixes = IMAGE_SUFFIXES | ANNOTATION_SUFFIXES
    unsupported = [path for path in paths if path.suffix.lower() not in supported_suffixes]
    images_by_stem: dict[Path, Path] = {image.with_suffix(""): image for image in images}
    corrupt: list[str] = []
    malformed: list[str] = []
    duplicates: dict[str, list[str]] = defaultdict(list)
    split_locations: dict[str, set[str]] = defaultdict(set)
    class_counts: Counter[str] = Counter()
    formats: Counter[str] = Counter()

    image_dimensions: dict[Path, tuple[int, int]] = {}
    for image_path in images:
        try:
            with Image.open(image_path) as image:
                image.verify()
            with Image.open(image_path) as image:
                image_dimensions[image_path] = image.size
            digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
            duplicates[digest].append(str(image_path.relative_to(root)))
            split = _split_name(image_path, root)
            if split:
                split_locations[digest].add(split)
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            corrupt.append(f"{image_path.relative_to(root)}: {exc}")

    for annotation in annotations:
        formats["labelme" if annotation.suffix.lower() == ".json" else "yolo"] += 1
        if annotation.suffix.lower() == ".json":
            source_image = images_by_stem.get(annotation.with_suffix(""))
            if source_image is None or source_image not in image_dimensions:
                malformed.append(
                    f"{annotation.relative_to(root)}: matching readable image not found"
                )
                continue
            counts, error = _validate_labelme(annotation, *image_dimensions[source_image])
        else:
            counts, error = _validate_yolo(annotation)
            source_image = images_by_stem.get(annotation.with_suffix(""))
            if source_image is None or source_image not in image_dimensions:
                error = (
                    error or f"{annotation.relative_to(root)}: matching readable image not found"
                )
        class_counts.update(counts)
        if error:
            malformed.append(error)

    duplicate_groups = [
        paths_for_hash for paths_for_hash in duplicates.values() if len(paths_for_hash) > 1
    ]
    split_leaks = [
        paths_for_hash
        for digest, paths_for_hash in duplicates.items()
        if len(paths_for_hash) > 1 and len(split_locations[digest]) > 1
    ]
    return DatasetInspection(
        root=root,
        inspected_at=datetime.now(UTC),
        image_count=len(images),
        annotation_count=len(annotations),
        corrupt_images=corrupt,
        unsupported_files=[str(path.relative_to(root)) for path in unsupported],
        malformed_annotations=malformed,
        duplicate_image_groups=duplicate_groups,
        split_leaks=split_leaks,
        class_counts=dict(sorted(class_counts.items())),
        annotation_formats=dict(sorted(formats.items())),
    )


def write_dataset_inspection(inspection: DatasetInspection, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(inspection.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def ingest_annotations(root: Path, output_path: Path) -> list[VisualAnnotation]:
    """Normalize Labelme and supported YOLO boxes without mapping source classes."""

    root = root.resolve()
    inspection = inspect_dataset(root)
    if inspection.corrupt_images or inspection.malformed_annotations:
        raise ValueError("Dataset has corrupt images or malformed annotations; audit it first")
    image_by_stem = {
        path.with_suffix(""): path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    }
    records: list[VisualAnnotation] = []

    for annotation_path in sorted(
        path for path in root.rglob("*") if path.suffix.lower() in ANNOTATION_SUFFIXES
    ):
        image_path = image_by_stem.get(annotation_path.with_suffix(""))
        if image_path is None:
            raise ValueError(f"No matching image for annotation {annotation_path}")
        with Image.open(image_path) as image:
            image_width, image_height = image.size
        image_hash = hashlib.sha256(image_path.read_bytes()).hexdigest()
        annotation_hash = hashlib.sha256(annotation_path.read_bytes()).hexdigest()
        relative_image = str(image_path.relative_to(root))
        relative_annotation = str(annotation_path.relative_to(root))
        split = _split_name(image_path, root)

        if annotation_path.suffix.lower() == ".json":
            document = json.loads(annotation_path.read_text(encoding="utf-8"))
            shapes = document["shapes"]
            for shape in shapes:
                points = shape["points"]
                x_values = [float(point[0]) / image_width for point in points]
                y_values = [float(point[1]) / image_height for point in points]
                records.append(
                    VisualAnnotation(
                        image_path=relative_image,
                        image_sha256=image_hash,
                        annotation_path=relative_annotation,
                        annotation_sha256=annotation_hash,
                        annotation_format="labelme",
                        source_label=shape["label"],
                        x_min=min(x_values),
                        y_min=min(y_values),
                        x_max=max(x_values),
                        y_max=max(y_values),
                        split=split,
                    )
                )
            continue

        for line_number, line in enumerate(
            annotation_path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if not line.strip():
                continue
            fields = line.split()
            if len(fields) not in {5, 12}:
                raise ValueError(
                    f"{relative_annotation}:{line_number}: unsupported YOLO row with "
                    f"{len(fields)} fields"
                )
            class_id = int(fields[0])
            center_x, center_y, box_width, box_height = (float(value) for value in fields[1:5])
            affiliation = int(fields[5]) if len(fields) == 12 else None
            records.append(
                VisualAnnotation(
                    image_path=relative_image,
                    image_sha256=image_hash,
                    annotation_path=relative_annotation,
                    annotation_sha256=annotation_hash,
                    annotation_format="yolo_extended" if affiliation is not None else "yolo",
                    source_class_id=class_id,
                    affiliation=affiliation,
                    x_min=center_x - box_width / 2,
                    y_min=center_y - box_height / 2,
                    x_max=center_x + box_width / 2,
                    y_max=center_y + box_height / 2,
                    split=split,
                )
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps([record.model_dump(mode="json") for record in records], indent=2) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    return records
