"""Schemas for normalized records, provenance, geometry, and dataset audits."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class CatalogModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class DataProvenance(CatalogModel):
    source_name: str = Field(min_length=1)
    source_url: str = Field(min_length=1)
    source_revision: str | None = None
    source_record_key: str | None = None
    retrieved_at: AwareDatetime
    source_updated_at: AwareDatetime | None = None
    apparent_game_version: str | None = None
    license: str | None = None
    license_status: str = Field(min_length=1)
    content_sha256: str | None = None
    method: str = Field(min_length=1)


class CardRecord(CatalogModel):
    """Normalized card metadata while preserving source-specific fields."""

    key: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    stable_id: int | None = Field(default=None, gt=0)
    aliases: list[str] = Field(default_factory=list)
    localized_names: dict[str, str] = Field(default_factory=dict)
    card_type: str | None = None
    rarity: str | None = None
    elixir_cost: int | None = Field(default=None, ge=0, le=10)
    unlock_arena: int | str | None = None
    is_evolved: bool | None = None
    evolution_level: int | None = Field(default=None, ge=1)
    description: str | None = None
    image_references: list[str] = Field(default_factory=list)
    source_fields: dict[str, Any] = Field(default_factory=dict)
    stat_sources: dict[str, dict[str, Any]] = Field(default_factory=dict)
    provenance: list[DataProvenance] = Field(min_length=1)


class CoordinatePoint(CatalogModel):
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class ArenaDefinition(CatalogModel):
    """Versioned arena facts; unmeasured geometry remains absent."""

    key: str = Field(min_length=1)
    name: str = Field(min_length=1)
    source_game_version: str | None = None
    coordinate_space: str = "normalized_screenshot"
    geometry: dict[str, list[CoordinatePoint]] = Field(default_factory=dict)
    provenance: list[DataProvenance] = Field(min_length=1)


class ArenaCalibration(CatalogModel):
    """Per-image mapping evidence; no exact game coordinates are assumed."""

    screenshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    screenshot_width: int = Field(gt=0)
    screenshot_height: int = Field(gt=0)
    arena_key: str | None = None
    correspondences: list[ArenaCorrespondence] = Field(default_factory=list)
    mapping_method: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    fit_rmse: float | None = Field(default=None, ge=0.0)
    calibrated_at: AwareDatetime | None = None
    notes: str | None = None


class ArenaCorrespondence(CatalogModel):
    label: str = Field(min_length=1)
    screenshot_point: CoordinatePoint
    arena_point: CoordinatePoint
    provenance: str = Field(min_length=1)


class DatasetInspection(CatalogModel):
    root: Path
    inspected_at: AwareDatetime
    image_count: int = Field(ge=0)
    annotation_count: int = Field(ge=0)
    corrupt_images: list[str] = Field(default_factory=list)
    unsupported_files: list[str] = Field(default_factory=list)
    malformed_annotations: list[str] = Field(default_factory=list)
    duplicate_image_groups: list[list[str]] = Field(default_factory=list)
    split_leaks: list[list[str]] = Field(default_factory=list)
    class_counts: dict[str, int] = Field(default_factory=dict)
    annotation_formats: dict[str, int] = Field(default_factory=dict)


class VisualAnnotation(CatalogModel):
    """Normalized box record that retains original labels until reviewed mapping."""

    image_path: str = Field(min_length=1)
    image_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    annotation_path: str = Field(min_length=1)
    annotation_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    annotation_format: str = Field(min_length=1)
    source_label: str | None = None
    source_class_id: int | None = Field(default=None, ge=0)
    canonical_class_id: str | None = None
    affiliation: int | None = Field(default=None, ge=0, le=1)
    x_min: float = Field(ge=0.0, le=1.0)
    y_min: float = Field(ge=0.0, le=1.0)
    x_max: float = Field(ge=0.0, le=1.0)
    y_max: float = Field(ge=0.0, le=1.0)
    split: str | None = None

    @model_validator(mode="after")
    def ordered_bounds(self) -> VisualAnnotation:
        if self.x_min > self.x_max or self.y_min > self.y_max:
            raise ValueError("annotation minimum coordinates must not exceed maxima")
        return self
