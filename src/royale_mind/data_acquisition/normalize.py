"""Normalize pinned card metadata without inventing unavailable fields."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from royale_mind.data_acquisition.acquire import AcquisitionManifest
from royale_mind.data_acquisition.models import CardRecord, DataProvenance


def _provenance(manifest: AcquisitionManifest, filename: str, record_key: str) -> DataProvenance:
    source_file = next(item for item in manifest.files if Path(item.raw_path).name == filename)
    return DataProvenance(
        source_name="RoyaleAPI cr-api-data",
        source_url=source_file.url,
        source_revision=source_file.repository_revision,
        source_record_key=record_key,
        retrieved_at=source_file.retrieved_at,
        source_updated_at=datetime.fromisoformat(
            source_file.repository_commit_date.replace("Z", "+00:00")
        ),
        apparent_game_version="unknown; repository commit 2023-10-18",
        license=None,
        license_status=source_file.license_status,
        content_sha256=source_file.sha256,
        method="pinned_json_normalization",
    )


def _rows(value: Any, source_name: str) -> list[dict[str, Any]]:
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    if isinstance(value, dict):
        for child in value.values():
            if isinstance(child, list) and all(isinstance(item, dict) for item in child):
                return child
    raise ValueError(f"Unsupported JSON structure in {source_name}; expected object records")


def normalize_cards(manifest_path: Path, output_path: Path) -> list[CardRecord]:
    """Merge card, evolution, and card-stat records by exact source key."""

    manifest = AcquisitionManifest.model_validate_json(manifest_path.read_bytes())
    card_rows: dict[str, dict[str, Any]] = {}
    localized_rows: dict[str, dict[str, Any]] = {}
    provenance_by_key: dict[str, list[DataProvenance]] = {}
    stat_rows: dict[str, dict[str, dict[str, Any]]] = {}
    image_refs: dict[str, list[str]] = {}

    for filename in ("cards.json", "cards_evo.json", "cards_i18n_evo.json"):
        path = next(Path(item.raw_path) for item in manifest.files if item.name == filename[:-5])
        values = json.loads(path.read_text(encoding="utf-8"))
        for row in _rows(values, filename):
            key = row.get("key")
            if not isinstance(key, str) or not key:
                continue
            if filename == "cards_i18n_evo.json":
                localized_rows[key] = row
                provenance_by_key.setdefault(key, []).append(_provenance(manifest, filename, key))
                continue
            if key in card_rows and card_rows[key] != row:
                raise ValueError(f"Conflicting duplicate source card key: {key}")
            card_rows[key] = row
            provenance_by_key.setdefault(key, []).append(_provenance(manifest, filename, key))

    for source_file in manifest.files:
        if not source_file.category.endswith("statistics"):
            continue
        path = Path(source_file.raw_path)
        records = _rows(json.loads(path.read_text(encoding="utf-8")), path.name)
        for row in records:
            key = row.get("key")
            if isinstance(key, str) and key:
                stat_rows.setdefault(key, {})[source_file.name] = row
                if row.get("highres_image_filename"):
                    image_refs.setdefault(key, []).append(row["highres_image_filename"])

    normalized: list[CardRecord] = []
    for key, row in card_rows.items():
        stats = stat_rows.get(key, {})
        primary_stats = next(iter(stats.values()), {})
        name = row.get("name") or primary_stats.get("name_en") or key
        localized = localized_rows.get(key, {}).get("_lang", {})
        localized_names = localized.get("name", {}) if isinstance(localized, dict) else {}
        localized_names = {
            language: value
            for language, value in localized_names.items()
            if language not in {"name", "sc_key"} and isinstance(value, str)
        }
        aliases = sorted(
            {
                alias
                for alias in (
                    row.get("sc_key"),
                    primary_stats.get("name"),
                    primary_stats.get("name_en"),
                )
                if isinstance(alias, str) and alias and alias != name
            }
        )
        normalized.append(
            CardRecord(
                key=key,
                canonical_name=name,
                stable_id=row.get("id"),
                aliases=aliases,
                localized_names=localized_names,
                card_type=row.get("type"),
                rarity=row.get("rarity"),
                elixir_cost=row.get("elixir"),
                unlock_arena=row.get("arena"),
                is_evolved=row.get("is_evolved"),
                evolution_level=row.get("evolution_level"),
                description=row.get("description"),
                image_references=sorted(set(image_refs.get(key, []))),
                source_fields=row,
                stat_sources=stats,
                provenance=provenance_by_key[key]
                + [
                    _provenance(manifest, Path(item.raw_path).name, key)
                    for item in manifest.files
                    if item.name in stats
                ],
            )
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [record.model_dump(mode="json") for record in normalized]
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    return normalized


def normalize_reference_sources(manifest_path: Path, output_root: Path) -> list[Path]:
    """Write provenance-wrapped arena, mode, and timeline records without inventing fields."""

    manifest = AcquisitionManifest.model_validate_json(manifest_path.read_bytes())
    destinations = {
        "arenas": "arena_geometry/arena-source-records.json",
        "game_modes": "game_modes/game-modes.json",
        "battle_timelines": "game_modes/battle-timelines.json",
        "spell_sets": "mechanics/spell-sets.json",
        "cards_stats_character_buff": "card_stats/character-buffs.json",
    }
    written: list[Path] = []
    evolution_sources = {
        item.name: item for item in manifest.files if item.category == "evolution_mechanics"
    }
    if evolution_sources:
        first_source = next(iter(evolution_sources.values()))
        evolution_payload = {
            "source_name": "RoyaleAPI cr-api-data",
            "source_revision": first_source.repository_revision,
            "retrieved_at": manifest.retrieved_at.isoformat(),
            "license": None,
            "license_status": first_source.license_status,
            "sources": {
                name: {
                    "url": source.url,
                    "sha256": source.sha256,
                    "records": json.loads(Path(source.raw_path).read_text(encoding="utf-8")),
                }
                for name, source in evolution_sources.items()
            },
        }
        evolution_path = output_root / "processed" / "mechanics" / "evolution-mechanics.json"
        evolution_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = evolution_path.with_suffix(evolution_path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(evolution_payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(evolution_path)
        written.append(evolution_path)

    for source_file in manifest.files:
        relative_output = destinations.get(source_file.name)
        if relative_output is None:
            continue
        source_path = Path(source_file.raw_path)
        payload = {
            "source_name": "RoyaleAPI cr-api-data",
            "source_url": source_file.url,
            "source_revision": source_file.repository_revision,
            "source_commit_date": source_file.repository_commit_date,
            "retrieved_at": source_file.retrieved_at.isoformat(),
            "license": source_file.license,
            "license_status": source_file.license_status,
            "source_sha256": source_file.sha256,
            "records": json.loads(source_path.read_text(encoding="utf-8")),
        }
        output_path = output_root / "processed" / relative_output
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(output_path)
        written.append(output_path)
    return written
