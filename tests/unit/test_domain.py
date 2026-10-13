from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from royale_mind.domain import (
    BoundingBox,
    CandidateActionType,
    CardObservation,
    ElixirObservation,
    Estimate,
    Freshness,
    GamePhase,
    GamePhaseObservation,
    GameState,
    ImagePoint,
    ObservationMetadata,
    ObservationProvenance,
    TacticalCandidateAction,
    TacticalRecommendation,
    Team,
    TowerObservation,
    UnitObservation,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def metadata(*, confidence: float = 0.9, freshness: Freshness = Freshness.FRESH):
    return ObservationMetadata(
        observed_at=NOW,
        provenance=ObservationProvenance(
            source="replay:test-frame",
            method="fixture",
            method_version="1",
        ),
        confidence=confidence,
        freshness=freshness,
    )


def test_valid_observations_and_recommendation() -> None:
    card = CardObservation(metadata=metadata(), card_name="Knight", hand_slot=0, ready=True)
    unit = UnitObservation(
        metadata=metadata(),
        name="Knight",
        team=Team.PLAYER,
        position=ImagePoint(x=0.25, y=0.75),
        bounds=BoundingBox(x_min=0.2, y_min=0.7, x_max=0.3, y_max=0.8),
    )
    tower = TowerObservation(
        metadata=metadata(),
        name="Princess Tower",
        team=Team.PLAYER,
        hitpoints=1200,
        max_hitpoints=3000,
    )
    elixir = ElixirObservation(metadata=metadata(), team=Team.PLAYER, amount=6.5)
    phase = GamePhaseObservation(metadata=metadata(), phase=GamePhase.BATTLE)
    action = TacticalCandidateAction(
        action_type=CandidateActionType.DEFEND,
        card_name="Knight",
        description="Defend the visible unit",
    )
    recommendation = TacticalRecommendation(
        action=action,
        rank=1,
        explanation="The unit is approaching the tower.",
        confidence=0.7,
        generated_at=NOW + timedelta(seconds=1),
        state_as_of=NOW,
        assumptions=["The visible unit is hostile"],
    )
    state = GameState(
        game_phase=phase,
        cards=[card],
        units=[unit],
        towers=[tower],
        elixir=[elixir],
    )

    assert state.cards == [card]
    assert state.units[0].position == ImagePoint(x=0.25, y=0.75)
    assert state.game_phase.phase is GamePhase.BATTLE
    assert recommendation.action is action


@pytest.mark.parametrize("value", [-0.01, 1.01])
def test_confidence_must_be_between_zero_and_one(value: float) -> None:
    with pytest.raises(ValidationError):
        metadata(confidence=value)


@pytest.mark.parametrize(
    "coords",
    [
        {"x": -0.1, "y": 0.5},
        {"x": 0.5, "y": 1.1},
    ],
)
def test_image_coordinates_must_be_normalized(coords: dict[str, float]) -> None:
    with pytest.raises(ValidationError):
        ImagePoint(**coords)


def test_bounding_box_coordinates_must_be_ordered() -> None:
    with pytest.raises(ValidationError, match="minimum coordinates"):
        BoundingBox(x_min=0.8, y_min=0.2, x_max=0.3, y_max=0.9)


def test_invalid_observed_values_are_rejected() -> None:
    with pytest.raises(ValidationError):
        ElixirObservation(metadata=metadata(), amount=10.1)
    with pytest.raises(ValidationError, match="cannot exceed"):
        TowerObservation(metadata=metadata(), hitpoints=101, max_hitpoints=100)


def test_missing_observations_remain_unknown_and_collections_are_independent() -> None:
    first = GameState()
    second = GameState()

    assert first.frame is None
    assert first.game_phase is None
    assert first.cards == []
    assert first.elixir == []
    assert first.estimated_opponent_elixir is None
    assert first.estimated_opponent_card_cycle is None
    assert first.cards is not second.cards


def test_timestamped_evidence_requires_timezone_information() -> None:
    with pytest.raises(ValidationError):
        ObservationMetadata(
            observed_at=datetime(2026, 1, 1),
            provenance=ObservationProvenance(
                source="replay:test-frame",
                method="fixture",
                method_version="1",
            ),
            confidence=0.9,
        )


def test_uncertain_estimate_is_separate_from_visible_observation() -> None:
    estimate = Estimate[float](
        value=4.0,
        confidence=0.35,
        estimated_at=NOW,
        provenance=ObservationProvenance(
            source="state",
            method="elixir_model",
            method_version="0.1",
        ),
        freshness=Freshness.STALE,
        assumptions=["No elixir-spending event was observed"],
    )
    state = GameState(estimated_opponent_elixir=estimate)

    assert state.elixir == []
    assert state.estimated_opponent_elixir is estimate
    assert state.estimated_opponent_elixir.confidence == 0.35
    assert state.estimated_opponent_elixir.freshness is Freshness.STALE
    assert state.estimated_opponent_elixir.assumptions


def test_estimated_elixir_range_is_validated() -> None:
    estimate = Estimate[float](
        value=11.0,
        confidence=0.5,
        estimated_at=NOW,
        provenance=ObservationProvenance(source="state", method="estimate", method_version="1"),
    )
    with pytest.raises(ValidationError, match="estimated elixir"):
        GameState(estimated_opponent_elixir=estimate)
