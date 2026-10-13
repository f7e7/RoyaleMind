"""Pinned public JSON sources selected for small, metadata-only local research."""

from dataclasses import dataclass

CR_API_DATA_REVISION = "d5461b0a59bff33c4da2fc845b07275b66b2d6ff"
CR_API_DATA_COMMIT_DATE = "2023-10-18T00:23:16Z"
CR_API_DATA_REPOSITORY = "https://github.com/RoyaleAPI/cr-api-data"


@dataclass(frozen=True, slots=True)
class JsonSource:
    name: str
    relative_path: str
    repository_size_bytes: int
    category: str

    @property
    def url(self) -> str:
        return (
            f"https://raw.githubusercontent.com/RoyaleAPI/cr-api-data/"
            f"{CR_API_DATA_REVISION}/{self.relative_path}"
        )


SOURCES = (
    JsonSource("cards", "docs/json/cards.json", 52_777, "cards"),
    JsonSource("cards_evo", "docs/json/cards_evo.json", 56_568, "cards_and_evolutions"),
    JsonSource("cards_i18n_evo", "docs/json/cards_i18n_evo.json", 1_060_300, "card_localization"),
    JsonSource("cards_stats", "docs/json/cards_stats.json", 3_501_243, "card_statistics"),
    JsonSource("cards_stats_troop", "docs/json/cards_stats_troop.json", 270_499, "card_statistics"),
    JsonSource(
        "cards_stats_building",
        "docs/json/cards_stats_building.json",
        934_695,
        "card_statistics",
    ),
    JsonSource("cards_stats_spell", "docs/json/cards_stats_spell.json", 320_139, "card_statistics"),
    JsonSource(
        "cards_stats_characters",
        "docs/json/cards_stats_characters.json",
        1_302_904,
        "unit_statistics",
    ),
    JsonSource(
        "cards_stats_character_buff",
        "docs/json/cards_stats_character_buff.json",
        132_910,
        "unit_statistics",
    ),
    JsonSource(
        "cards_stats_projectile",
        "docs/json/cards_stats_projectile.json",
        161_802,
        "projectile_statistics",
    ),
    JsonSource("buildings_evo", "docs/json/buildings_evo.json", 1_932, "evolution_mechanics"),
    JsonSource("projectiles_evo", "docs/json/projectiles_evo.json", 3_189, "evolution_mechanics"),
    JsonSource("spell_sets", "docs/json/spell_sets.json", 270_450, "gameplay_mechanics"),
    JsonSource("arenas", "docs/json/arenas.json", 127_375, "arena_metadata"),
    JsonSource("game_modes", "docs/json/game_modes.json", 1_754_660, "game_modes"),
    JsonSource("battle_timelines", "docs/json/battle_timelines.json", 12_928, "gameplay_timing"),
)

MAX_SOURCE_BYTES = 10_000_000
MAX_TOTAL_BYTES = 10_000_000
LICENSE_STATUS = "unknown; local research only; redistribution not cleared"
