"""Validated, image-library-independent RoyaleMind domain models."""

from __future__ import annotations

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator


class DomainModel(BaseModel):
    """Base policy for stable, validated domain data."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Freshness(StrEnum):
    """Freshness assessment supplied by state fusion, not inferred by a model."""

    UNKNOWN = "unknown"
    FRESH = "fresh"
    STALE = "stale"


class Team(StrEnum):
    PLAYER = "player"
    OPPONENT = "opponent"


class GamePhase(StrEnum):
    PRE_BATTLE = "pre_battle"
    BATTLE = "battle"
    OVERTIME = "overtime"
    ENDED = "ended"


class ObservationProvenance(DomainModel):
    """Identifies where an observation came from and how it was produced."""

    source: str = Field(min_length=1)
    method: str = Field(min_length=1)
    method_version: str = Field(min_length=1)
    details: str | None = None


class ObservationMetadata(DomainModel):
    """Evidence metadata shared by all observations."""

    observed_at: AwareDatetime
    provenance: ObservationProvenance
    confidence: float = Field(ge=0.0, le=1.0)
    freshness: Freshness = Freshness.UNKNOWN


class Estimate[T](DomainModel):
    """An uncertain inferred value, kept separate from visible observations."""

    value: T | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    estimated_at: AwareDatetime
    provenance: ObservationProvenance
    freshness: Freshness = Freshness.UNKNOWN
    assumptions: list[str] = Field(default_factory=list)


class ImagePoint(DomainModel):
    """Normalized image coordinate in the inclusive range [0, 1]."""

    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)


class BoundingBox(DomainModel):
    """Normalized image rectangle with ordered corners."""

    x_min: float = Field(ge=0.0, le=1.0)
    y_min: float = Field(ge=0.0, le=1.0)
    x_max: float = Field(ge=0.0, le=1.0)
    y_max: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def corners_are_ordered(self) -> BoundingBox:
        if self.x_min > self.x_max or self.y_min > self.y_max:
            raise ValueError("bounding-box minimum coordinates must not exceed maxima")
        return self


class FrameMetadata(DomainModel):
    """Metadata for one captured or replayed frame; pixel data stays out of the domain."""

    captured_at: AwareDatetime
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    source: str = Field(min_length=1)
    freshness: Freshness = Freshness.UNKNOWN


class CardObservation(DomainModel):
    """Visible evidence about a card or hand slot."""

    metadata: ObservationMetadata
    card_name: str | None = None
    hand_slot: int | None = Field(default=None, ge=0, le=7)
    ready: bool | None = None


class UnitObservation(DomainModel):
    """Visible evidence about a unit; absent attributes remain unknown."""

    metadata: ObservationMetadata
    entity_id: str | None = None
    name: str | None = None
    team: Team | None = None
    position: ImagePoint | None = None
    bounds: BoundingBox | None = None
    hitpoints: float | None = Field(default=None, ge=0.0)


class BuildingObservation(DomainModel):
    """Visible evidence about a non-tower building."""

    metadata: ObservationMetadata
    entity_id: str | None = None
    name: str | None = None
    team: Team | None = None
    position: ImagePoint | None = None
    bounds: BoundingBox | None = None
    hitpoints: float | None = Field(default=None, ge=0.0)


class TowerObservation(DomainModel):
    """Visible evidence about a tower and its observed health, if readable."""

    metadata: ObservationMetadata
    name: str | None = None
    team: Team | None = None
    position: ImagePoint | None = None
    hitpoints: float | None = Field(default=None, ge=0.0)
    max_hitpoints: float | None = Field(default=None, gt=0.0)

    @model_validator(mode="after")
    def observed_hitpoints_do_not_exceed_maximum(self) -> TowerObservation:
        if (
            self.hitpoints is not None
            and self.max_hitpoints is not None
            and self.hitpoints > self.max_hitpoints
        ):
            raise ValueError("observed tower hitpoints cannot exceed maximum hitpoints")
        return self


class ElixirObservation(DomainModel):
    """Visible elixir reading; missing amount is explicitly unknown."""

    metadata: ObservationMetadata
    team: Team | None = None
    amount: float | None = Field(default=None, ge=0.0, le=10.0)


class GamePhaseObservation(DomainModel):
    """Observed game phase, with phase omitted when it is not visible."""

    metadata: ObservationMetadata
    phase: GamePhase | None = None


class GameState(DomainModel):
    """Snapshot of observations and estimates without merging their semantics."""

    state_as_of: AwareDatetime | None = None
    frame: FrameMetadata | None = None
    game_phase: GamePhaseObservation | None = None
    cards: list[CardObservation] = Field(default_factory=list)
    units: list[UnitObservation] = Field(default_factory=list)
    buildings: list[BuildingObservation] = Field(default_factory=list)
    towers: list[TowerObservation] = Field(default_factory=list)
    elixir: list[ElixirObservation] = Field(default_factory=list)
    estimated_opponent_elixir: Estimate[float] | None = None
    estimated_opponent_card_cycle: Estimate[list[str]] | None = None

    @field_validator("estimated_opponent_elixir")
    @classmethod
    def estimated_elixir_is_in_range(
        cls, estimate: Estimate[float] | None
    ) -> Estimate[float] | None:
        if (
            estimate is not None
            and estimate.value is not None
            and not 0.0 <= estimate.value <= 10.0
        ):
            raise ValueError("estimated elixir must be between 0 and 10")
        return estimate


class CandidateActionType(StrEnum):
    DEPLOY_CARD = "deploy_card"
    DEFEND = "defend"
    WAIT = "wait"
    CYCLE = "cycle"


class TacticalCandidateAction(DomainModel):
    """Advisory candidate only; this model has no execution semantics."""

    action_type: CandidateActionType
    card_name: str | None = None
    target: str | None = None
    position: ImagePoint | None = None
    description: str = Field(min_length=1)


class TacticalRecommendation(DomainModel):
    """Ranked explanation produced by a future strategy component."""

    action: TacticalCandidateAction
    rank: int = Field(ge=1)
    explanation: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    generated_at: AwareDatetime
    state_as_of: AwareDatetime
    assumptions: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def state_cannot_postdate_recommendation(self) -> TacticalRecommendation:
        if self.state_as_of > self.generated_at:
            raise ValueError("state_as_of cannot be later than generated_at")
        return self
