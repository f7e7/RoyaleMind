"""Coverage summaries for imported card records and documented unknown fields."""

from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from royale_mind.data_acquisition.models import CardRecord

CARD_FIELDS = (
    "stable_id",
    "card_type",
    "rarity",
    "elixir_cost",
    "unlock_arena",
    "is_evolved",
    "evolution_level",
    "description",
    "hitpoints",
    "damage",
    "dps",
    "hit_speed",
    "range",
    "movement_speed",
    "target_types",
    "deployment_time",
    "attack_radius",
    "projectile_properties",
    "lifetime",
    "spawn_count",
    "level_statistics",
    "special_mechanics",
    "image_references",
    "localization",
)

SOURCE_KEYS_BY_FIELD = {
    "hitpoints": ("hitpoints", "hitpoints_per_level", "hitpointsPerLevel"),
    "damage": ("damage", "damage_per_level", "damagePerLevel", "instant_damage"),
    "dps": ("dps", "dps_per_level", "dpsPerLevel"),
    "hit_speed": ("hit_speed", "hitSpeed", "projectile_interval"),
    "range": ("range", "radius"),
    "movement_speed": ("movement_speed", "speed", "walking_speed"),
    "target_types": ("target_types", "targetType", "only_own_troops", "only_enemies"),
    "deployment_time": ("custom_deploy_time", "summon_deploy_delay"),
    "attack_radius": ("attack_radius", "radius"),
    "projectile_properties": ("projectile", "projectile_interval", "multiple_projectiles"),
    "lifetime": ("duration_seconds", "lifetime"),
    "spawn_count": ("summon_number", "summon_number_second"),
    "level_statistics": ("hitpoints_per_level", "damage_per_level", "dps_per_level"),
    "special_mechanics": ("hero_ability", "passive_ability", "buff_type", "evolved_spells"),
}


def build_coverage_report(
    card_records: list[CardRecord],
    dataset_reports: list[dict[str, Any]] | None = None,
    *,
    imported_source_count: int = 0,
) -> dict[str, Any]:
    present_counts: Counter[str] = Counter()
    for record in card_records:
        direct_fields = {
            "stable_id": record.stable_id,
            "card_type": record.card_type,
            "rarity": record.rarity,
            "elixir_cost": record.elixir_cost,
            "unlock_arena": record.unlock_arena,
            "is_evolved": record.is_evolved,
            "evolution_level": record.evolution_level,
            "description": record.description,
            "image_references": record.image_references,
            "localization": record.localized_names,
        }
        for field_name, value in direct_fields.items():
            if value is not None and value != [] and value != {}:
                present_counts[field_name] += 1
        source_values = [record.source_fields, *record.stat_sources.values()]
        for field_name, source_keys in SOURCE_KEYS_BY_FIELD.items():
            if any(
                source_key in source and source[source_key] is not None
                for source in source_values
                for source_key in source_keys
            ):
                present_counts[field_name] += 1
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "schema_version": 1,
        "coverage_scope": {
            "card_record_count": len(card_records),
            "card_field_coverage": {
                field: {
                    "records_with_value": present_counts[field],
                    "records_total": len(card_records),
                }
                for field in CARD_FIELDS
            },
            "statistics_source_count": len(
                {source for record in card_records for source in record.stat_sources}
            ),
            "imported_source_file_count": imported_source_count,
            "dataset_reports": dataset_reports or [],
        },
        "limitations": [
            "Coverage is scoped to imported pinned sources, not all current game data.",
            "Missing mechanics/stat fields remain unknown pending current verification.",
            "Dataset coverage is unknown until a dataset is supplied and inspected.",
        ],
    }


def write_coverage_report(report: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_human_coverage_report(report: dict[str, Any], output_path: Path) -> None:
    coverage = report["coverage_scope"]
    lines = [
        "# Local Data Coverage",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"Normalized card/variant records: {coverage['card_record_count']}",
        f"Statistics source tables represented: {coverage['statistics_source_count']}",
        "",
        "Coverage is scoped to imported records, not all current game content.",
        "A field is present when at least one retained source record has a non-null value.",
        "",
        "## Card Fields",
        "",
    ]
    for field_name, counts in coverage["card_field_coverage"].items():
        lines.append(
            f"- `{field_name}`: {counts['records_with_value']} / {counts['records_total']} records"
        )
    lines.extend(["", "## Limitations", ""])
    lines.extend(f"- {limitation}" for limitation in report["limitations"])
    lines.append("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines), encoding="utf-8")


def write_normalized_validation(records: list[CardRecord], output_path: Path) -> list[str]:
    from royale_mind.data_acquisition.validate import validate_cards

    errors = validate_cards(records)
    result = {
        "generated_at": datetime.now(UTC).isoformat(),
        "record_count": len(records),
        "errors": errors,
        "valid": not errors,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return errors
