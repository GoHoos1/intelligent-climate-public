"""Test pure Task 9 outlier rejection and source aggregation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from math import inf, nan
from typing import Any

import pytest

from custom_components.intelligent_climate.aggregation import (
    aggregate_humidity_sources,
    aggregate_temperature_sources,
)
from custom_components.intelligent_climate.models import (
    AggregationReason,
    AggregationStatus,
    AggregationStrategy,
    ExclusionReason,
    HumiditySource,
    ObservationSourceId,
    SourceAggregationResult,
    SourceObservation,
    SourceQuality,
    TemperatureSource,
)

CALCULATED_AT = datetime(2026, 7, 23, 16, 0, tzinfo=UTC)
OBSERVED_AT = datetime(2026, 7, 23, 15, 59, tzinfo=UTC)
SOURCE_IDS = tuple(
    ObservationSourceId.parse(value)
    for value in (
        "f15f73b1-ea59-4b28-819f-7b99acf065bf",
        "ce30dafc-fadd-4cc4-b261-8a896d5a6d12",
        "3d59d933-a9f3-4dfd-bdf7-5288cd9f228a",
        "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8",
        "d3c35ab0-b97c-4570-8b61-a22479c2dd10",
    )
)


def _temperature_source(
    index: int,
    *,
    weight: float = 1.0,
    priority: int = 0,
    enabled: bool = True,
) -> TemperatureSource:
    return TemperatureSource(
        source_id=SOURCE_IDS[index],
        entity_id=f"sensor.temperature_{index}",
        attribute=None,
        offset_c=0.0,
        weight=weight,
        priority=priority,
        enabled=enabled,
    )


def _humidity_source(
    index: int,
    *,
    weight: float = 1.0,
    priority: int = 0,
    enabled: bool = True,
) -> HumiditySource:
    return HumiditySource(
        source_id=SOURCE_IDS[index],
        entity_id=f"sensor.humidity_{index}",
        attribute=None,
        offset_pct=0.0,
        weight=weight,
        priority=priority,
        enabled=enabled,
    )


def _observation(
    index: int,
    value: float | None,
    *,
    quality: SourceQuality = SourceQuality.VALID,
    raw_value: object | None = None,
    restored: bool = False,
) -> SourceObservation[float]:
    return SourceObservation(
        source_id=SOURCE_IDS[index],
        raw_value=value if raw_value is None else raw_value,
        normalized_value=value if quality is SourceQuality.VALID else None,
        observed_at=OBSERVED_AT,
        source_last_updated=OBSERVED_AT,
        quality=quality,
        exclusion_reason=(
            None if quality is SourceQuality.VALID else ExclusionReason(quality.value)
        ),
        restored=restored,
    )


def _temperature(
    sources: tuple[TemperatureSource, ...],
    observations: tuple[SourceObservation[float], ...],
    *,
    strategy: AggregationStrategy = AggregationStrategy.MEAN,
    minimum: int = 1,
    floor: float = 1.7,
) -> SourceAggregationResult:
    return aggregate_temperature_sources(
        sources,
        observations,
        strategy=strategy,
        min_valid_sources=minimum,
        outlier_floor_c=floor,
        calculated_at=CALCULATED_AT,
    )


def _humidity(
    sources: tuple[HumiditySource, ...],
    observations: tuple[SourceObservation[float], ...],
    *,
    strategy: AggregationStrategy = AggregationStrategy.MEAN,
    minimum: int = 1,
) -> SourceAggregationResult:
    return aggregate_humidity_sources(
        sources,
        observations,
        strategy=strategy,
        min_valid_sources=minimum,
        calculated_at=CALCULATED_AT,
    )


def test_result_models_are_frozen_slotted_and_retain_calculated_at() -> None:
    result = _temperature((_temperature_source(0),), (_observation(0, 20.0),))

    assert result.calculated_at is CALCULATED_AT
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        result.effective_value = 22.0  # type: ignore[misc]


@pytest.mark.parametrize("function", ["temperature", "humidity"])
def test_naive_calculated_at_is_rejected(function: str) -> None:
    naive = datetime(2026, 7, 23, 16, 0)
    with pytest.raises(ValueError, match="calculated_at must be timezone-aware"):
        if function == "temperature":
            aggregate_temperature_sources(
                (),
                (),
                strategy=AggregationStrategy.MEAN,
                min_valid_sources=1,
                outlier_floor_c=1.7,
                calculated_at=naive,
            )
        else:
            aggregate_humidity_sources(
                (),
                (),
                strategy=AggregationStrategy.MEAN,
                min_valid_sources=1,
                calculated_at=naive,
            )


def test_inputs_are_not_mutated_and_existing_exclusion_object_is_preserved() -> None:
    sources = (_temperature_source(0), _temperature_source(1))
    valid = _observation(0, 20.0)
    invalid = _observation(1, None, quality=SourceQuality.STALE, raw_value="old")
    observations = (valid, invalid)

    result = _temperature(sources, observations)

    assert sources == (_temperature_source(0), _temperature_source(1))
    assert observations == (valid, invalid)
    assert result.excluded_observations == (invalid,)
    assert result.excluded_observations[0] is invalid


def test_output_accounting_follows_configured_order_not_observation_order() -> None:
    sources = tuple(_temperature_source(index) for index in range(3))
    observations = (
        _observation(2, None, quality=SourceQuality.STALE),
        _observation(1, 21.0),
        _observation(0, 20.0),
    )

    result = _temperature(sources, observations)

    assert result.valid_source_ids == SOURCE_IDS[:2]
    assert tuple(item.source_id for item in result.excluded_observations) == (
        SOURCE_IDS[2],
    )


def test_no_sources_and_all_disabled_are_unavailable() -> None:
    no_sources = _temperature((), ())
    disabled = _temperature(
        (_temperature_source(0, enabled=False),),
        (),
    )

    for result in (no_sources, disabled):
        assert result.status is AggregationStatus.UNAVAILABLE
        assert result.reasons == (AggregationReason.NO_ENABLED_SOURCES,)
        assert result.effective_value is None
        assert result.valid_source_ids == ()
        assert result.excluded_observations == ()


def test_disabled_source_needs_no_observation_and_is_absent_from_accounting() -> None:
    result = _temperature(
        (_temperature_source(0), _temperature_source(1, enabled=False)),
        (_observation(0, 20.0),),
    )

    assert result.valid_source_ids == (SOURCE_IDS[0],)
    assert result.contributing_source_ids == (SOURCE_IDS[0],)
    assert SOURCE_IDS[1] not in result.valid_source_ids


@pytest.mark.parametrize(
    ("sources", "observations", "message"),
    [
        (
            (_temperature_source(0, enabled=False),),
            (_observation(0, 20.0),),
            "disabled",
        ),
        (
            (_temperature_source(0), _temperature_source(0)),
            (_observation(0, 20.0),),
            "configured source IDs",
        ),
        (
            (_temperature_source(0),),
            (_observation(0, 20.0), _observation(0, 20.0)),
            "observation source IDs",
        ),
        (
            (_temperature_source(0),),
            (_observation(1, 20.0),),
            "not configured",
        ),
        (
            (_temperature_source(0), _temperature_source(1)),
            (_observation(0, 20.0),),
            "every enabled source",
        ),
    ],
)
def test_source_observation_matching_errors(
    sources: tuple[TemperatureSource, ...],
    observations: tuple[SourceObservation[float], ...],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _temperature(sources, observations)


@pytest.mark.parametrize(
    ("observation", "message"),
    [
        (
            replace(_observation(0, 20.0), normalized_value=None),
            "finite numeric",
        ),
        (
            replace(_observation(0, 20.0), normalized_value=nan),
            "finite numeric",
        ),
        (
            replace(_observation(0, 20.0), normalized_value=inf),
            "finite numeric",
        ),
        (
            replace(_observation(0, 20.0), normalized_value=True),
            "finite numeric",
        ),
        (
            replace(
                _observation(0, 20.0),
                exclusion_reason=ExclusionReason.STALE,
            ),
            "cannot have an exclusion",
        ),
        (
            replace(_observation(0, 20.0), source_last_updated=None),
            "source_last_updated",
        ),
        (
            replace(
                _observation(0, None, quality=SourceQuality.STALE),
                normalized_value=20.0,
            ),
            "cannot have a normalized",
        ),
        (
            replace(
                _observation(0, None, quality=SourceQuality.STALE),
                exclusion_reason=ExclusionReason.UNKNOWN,
            ),
            "reason must match",
        ),
    ],
)
def test_malformed_observation_invariants_are_rejected(
    observation: SourceObservation[float],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        _temperature((_temperature_source(0),), (observation,))


def test_naive_observation_timestamps_are_rejected() -> None:
    naive = datetime(2026, 7, 23, 15, 59)
    for observation in (
        replace(_observation(0, 20.0), observed_at=naive),
        replace(_observation(0, 20.0), source_last_updated=naive),
    ):
        with pytest.raises(ValueError, match="timezone-aware"):
            _temperature((_temperature_source(0),), (observation,))


@pytest.mark.parametrize("minimum", [True, False, 0, -1, 1.5])
def test_invalid_minimum_count_is_rejected(minimum: Any) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        _temperature((), (), minimum=minimum)


@pytest.mark.parametrize("floor", [True, False, 0, -1, nan, inf, "1.7"])
def test_invalid_temperature_outlier_floor_is_rejected(floor: Any) -> None:
    with pytest.raises(ValueError, match="finite positive"):
        _temperature((), (), floor=floor)


@pytest.mark.parametrize("weight", [True, False, 0, -1, nan, inf])
def test_invalid_source_weights_are_rejected(weight: Any) -> None:
    source = replace(_temperature_source(0), weight=weight)
    with pytest.raises(ValueError, match="weights"):
        _temperature((source,), (_observation(0, 20.0),))


@pytest.mark.parametrize("priority", [True, False, -1, 1.5])
def test_invalid_source_priorities_are_rejected(priority: Any) -> None:
    source = replace(_temperature_source(0), priority=priority)
    with pytest.raises(ValueError, match="priorities"):
        _temperature((source,), (_observation(0, 20.0),))


def test_invalid_source_enabled_flag_is_rejected() -> None:
    source = replace(_temperature_source(0), enabled="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="enabled flags"):
        _temperature((source,), (_observation(0, 20.0),))


def test_invalid_strategy_is_rejected() -> None:
    with pytest.raises(ValueError, match="AggregationStrategy"):
        aggregate_temperature_sources(
            (),
            (),
            strategy="mean",  # type: ignore[arg-type]
            min_valid_sources=1,
            outlier_floor_c=1.7,
            calculated_at=CALCULATED_AT,
        )


@pytest.mark.parametrize(
    "quality",
    [
        SourceQuality.UNAVAILABLE,
        SourceQuality.UNKNOWN,
        SourceQuality.NON_NUMERIC,
        SourceQuality.NON_FINITE,
        SourceQuality.UNIT_UNSUPPORTED,
        SourceQuality.IMPLAUSIBLE,
        SourceQuality.STALE,
        SourceQuality.RESTORED_NOT_CONFIRMED,
        SourceQuality.JUMP_REJECTED,
    ],
)
def test_every_earlier_exclusion_passes_through_unchanged(
    quality: SourceQuality,
) -> None:
    excluded = _observation(1, None, quality=quality, raw_value={"original": quality})
    result = _temperature(
        (_temperature_source(0), _temperature_source(1)),
        (_observation(0, 20.0), excluded),
    )

    assert result.effective_value == 20.0
    assert result.status is AggregationStatus.DEGRADED
    assert result.reasons == (AggregationReason.SOURCE_EXCLUDED,)
    assert result.excluded_observations == (excluded,)
    assert result.excluded_observations[0] is excluded
    assert excluded.quality is quality
    assert excluded.exclusion_reason is ExclusionReason(quality.value)


def test_one_temperature_source_minimum_rounding_and_spread() -> None:
    source = (_temperature_source(0),)
    observation = (_observation(0, 20.25),)

    accepted = _temperature(source, observation, minimum=1)
    unavailable = _temperature(source, observation, minimum=2)

    assert accepted.effective_value == round(20.25, 1) == 20.2
    assert accepted.spread == 0.0
    assert accepted.status is AggregationStatus.HEALTHY
    assert unavailable.effective_value is None
    assert unavailable.spread == 0.0
    assert unavailable.valid_source_ids == (SOURCE_IDS[0],)
    assert unavailable.reasons == (AggregationReason.BELOW_MINIMUM_VALID_SOURCES,)


@pytest.mark.parametrize(
    ("second", "expected_spread"),
    [(20.0, 0.0), (23.0, 3.0), (23.4, 3.4)],
)
def test_two_temperatures_at_or_within_contradiction_boundary_are_valid(
    second: float,
    expected_spread: float,
) -> None:
    result = _temperature(
        (_temperature_source(0), _temperature_source(1)),
        (_observation(0, 20.0), _observation(1, second)),
    )

    assert result.status is AggregationStatus.HEALTHY
    assert result.valid_source_ids == SOURCE_IDS[:2]
    assert result.spread == pytest.approx(expected_spread)
    assert result.excluded_observations == ()


def test_two_sources_just_above_threshold_are_both_contradictory() -> None:
    originals = (_observation(0, 20.0), _observation(1, 23.400001))
    result = _temperature(
        (_temperature_source(0), _temperature_source(1)),
        originals,
    )

    assert result.status is AggregationStatus.UNAVAILABLE
    assert result.effective_value is None
    assert result.spread is None
    assert result.valid_source_ids == ()
    assert result.reasons == (
        AggregationReason.TWO_SOURCE_CONTRADICTION,
        AggregationReason.PRIORITY_NOT_CONFIGURED,
    )
    assert tuple(item.quality for item in result.excluded_observations) == (
        SourceQuality.CONTRADICTORY,
        SourceQuality.CONTRADICTORY,
    )
    for transformed, original in zip(
        result.excluded_observations,
        originals,
        strict=True,
    ):
        assert transformed is not original
        assert transformed.raw_value == original.raw_value
        assert transformed.observed_at is original.observed_at
        assert transformed.source_last_updated is original.source_last_updated
        assert transformed.restored is original.restored
        assert transformed.normalized_value is None
        assert transformed.exclusion_reason is ExclusionReason.CONTRADICTORY


def test_contradiction_unique_priority_produces_degraded_rounded_fallback() -> None:
    sources = (
        _temperature_source(0, priority=2),
        _temperature_source(1, priority=1),
    )
    result = _temperature(
        sources,
        (_observation(0, 20.0), _observation(1, 23.45)),
    )

    assert result.effective_value == round(23.45, 1)
    assert result.status is AggregationStatus.DEGRADED
    assert result.valid_source_ids == ()
    assert result.contributing_source_ids == (SOURCE_IDS[1],)
    assert result.fallback_source_id == SOURCE_IDS[1]
    assert result.spread is None
    assert result.reasons == (
        AggregationReason.TWO_SOURCE_CONTRADICTION,
        AggregationReason.PRIORITY_FALLBACK,
    )
    assert all(
        item.quality is SourceQuality.CONTRADICTORY
        for item in result.excluded_observations
    )


@pytest.mark.parametrize(
    ("priorities", "reason"),
    [
        ((0, 0), AggregationReason.PRIORITY_NOT_CONFIGURED),
        ((1, 1), AggregationReason.PRIORITY_AMBIGUOUS),
    ],
)
def test_contradiction_without_unique_explicit_priority_is_unavailable(
    priorities: tuple[int, int],
    reason: AggregationReason,
) -> None:
    result = _temperature(
        (
            _temperature_source(0, priority=priorities[0]),
            _temperature_source(1, priority=priorities[1]),
        ),
        (_observation(0, 20.0), _observation(1, 24.0)),
    )

    assert result.effective_value is None
    assert result.fallback_source_id is None
    assert result.reasons == (
        AggregationReason.TWO_SOURCE_CONTRADICTION,
        reason,
    )


def test_contradiction_fallback_is_prohibited_when_minimum_is_two() -> None:
    result = _temperature(
        (
            _temperature_source(0, priority=1),
            _temperature_source(1, priority=2),
        ),
        (_observation(0, 20.0), _observation(1, 24.0)),
        minimum=2,
    )

    assert result.effective_value is None
    assert result.fallback_source_id is None
    assert result.contributing_source_ids == ()
    assert result.reasons == (
        AggregationReason.TWO_SOURCE_CONTRADICTION,
        AggregationReason.BELOW_MINIMUM_VALID_SOURCES,
    )


def test_three_temperature_sources_without_outlier_aggregate_normally() -> None:
    result = _temperature(
        tuple(_temperature_source(index) for index in range(3)),
        tuple(_observation(index, value) for index, value in enumerate((20, 21, 22))),
    )

    assert result.effective_value == 21.0
    assert result.spread == 2.0
    assert result.status is AggregationStatus.HEALTHY


def test_zero_mad_clear_outlier_is_transformed_immutably() -> None:
    sources = tuple(_temperature_source(index) for index in range(3))
    originals = tuple(
        _observation(index, value, raw_value=f"raw-{value}")
        for index, value in enumerate((20.0, 20.0, 30.0))
    )

    result = _temperature(sources, originals, minimum=2)

    assert result.effective_value == 20.0
    assert result.spread == 0.0
    assert result.valid_source_ids == SOURCE_IDS[:2]
    assert result.status is AggregationStatus.DEGRADED
    assert result.reasons == (AggregationReason.OUTLIER_EXCLUDED,)
    outlier = result.excluded_observations[0]
    assert outlier.source_id == SOURCE_IDS[2]
    assert outlier.raw_value == "raw-30.0"
    assert outlier.quality is SourceQuality.OUTLIER
    assert outlier.exclusion_reason is ExclusionReason.OUTLIER
    assert outlier.normalized_value is None
    assert originals[2].quality is SourceQuality.VALID
    assert originals[2].normalized_value == 30.0


@pytest.mark.parametrize(
    ("value", "is_outlier"),
    [(5.4478, False), (5.447800001, True)],
)
def test_mad_threshold_is_inclusive_and_just_beyond_is_rejected(
    value: float,
    is_outlier: bool,
) -> None:
    result = _temperature(
        tuple(_temperature_source(index) for index in range(3)),
        (
            _observation(0, 0.0),
            _observation(1, 1.0),
            _observation(2, value),
        ),
        floor=0.1,
    )

    qualities = tuple(item.quality for item in result.excluded_observations)
    assert (SourceQuality.OUTLIER in qualities) is is_outlier


def test_mad_is_one_pass_over_original_otherwise_valid_set() -> None:
    result = _temperature(
        tuple(_temperature_source(index) for index in range(5)),
        tuple(
            _observation(index, value)
            for index, value in enumerate((0.0, 0.0, 0.0, 2.0, 10.0))
        ),
        floor=1.7,
    )

    assert result.valid_source_ids == SOURCE_IDS[:3]
    assert tuple(item.source_id for item in result.excluded_observations) == (
        SOURCE_IDS[3],
        SOURCE_IDS[4],
    )


def test_post_outlier_minimum_success_and_failure_preserve_accounting() -> None:
    sources = tuple(_temperature_source(index) for index in range(3))
    observations = tuple(
        _observation(index, value) for index, value in enumerate((20, 20, 30))
    )

    success = _temperature(sources, observations, minimum=2)
    failure = _temperature(sources, observations, minimum=3)

    assert success.effective_value == 20.0
    assert failure.effective_value is None
    assert failure.valid_source_ids == SOURCE_IDS[:2]
    assert tuple(item.source_id for item in failure.excluded_observations) == (
        SOURCE_IDS[2],
    )
    assert failure.reasons == (
        AggregationReason.OUTLIER_EXCLUDED,
        AggregationReason.BELOW_MINIMUM_VALID_SOURCES,
    )


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((1.0,), 1.0),
        ((1.0, 2.0, 3.0), 2.0),
        ((-3.0, -1.0), -2.0),
        ((0.1, 0.2, 0.3), 0.2),
    ],
)
def test_mean_strategy(values: tuple[float, ...], expected: float) -> None:
    result = _humidity(
        tuple(_humidity_source(index) for index in range(len(values))),
        tuple(_observation(index, value) for index, value in enumerate(values)),
    )

    assert result.effective_value == pytest.approx(expected)
    assert result.contributing_source_ids == SOURCE_IDS[: len(values)]


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ((1.0, 9.0, 2.0), 2.0),
        ((1.0, 9.0, 2.0, 4.0), 3.0),
        ((2.0, 2.0, 8.0), 2.0),
    ],
)
def test_median_strategy(values: tuple[float, ...], expected: float) -> None:
    count = len(values)
    forward = _humidity(
        tuple(_humidity_source(index) for index in range(count)),
        tuple(_observation(index, value) for index, value in enumerate(values)),
        strategy=AggregationStrategy.MEDIAN,
    )
    reverse = _humidity(
        tuple(_humidity_source(index) for index in reversed(range(count))),
        tuple(_observation(index, values[index]) for index in range(count)),
        strategy=AggregationStrategy.MEDIAN,
    )

    assert forward.effective_value == expected
    assert reverse.effective_value == expected


@pytest.mark.parametrize(
    ("weights", "expected"),
    [
        ((1.0, 1.0), 20.0),
        ((1.0, 3.0), 25.0),
        ((10.0, 30.0), 25.0),
        ((1e308, 1e308), 20.0),
    ],
)
def test_weighted_average_normalizes_finite_weights(
    weights: tuple[float, float],
    expected: float,
) -> None:
    result = _humidity(
        (
            _humidity_source(0, weight=weights[0]),
            _humidity_source(1, weight=weights[1]),
        ),
        (_observation(0, 10.0), _observation(1, 30.0)),
        strategy=AggregationStrategy.WEIGHTED_AVERAGE,
    )

    assert result.effective_value == pytest.approx(expected)


def test_excluded_source_is_removed_before_weighting_without_premature_rounding() -> (
    None
):
    result = _temperature(
        (
            _temperature_source(0, weight=1.0),
            _temperature_source(1, weight=1e10),
            _temperature_source(2, weight=2.0),
        ),
        (
            _observation(0, 20.04),
            _observation(1, None, quality=SourceQuality.STALE),
            _observation(2, 20.14),
        ),
        strategy=AggregationStrategy.WEIGHTED_AVERAGE,
    )

    assert result.effective_value == round((20.04 + 2 * 20.14) / 3, 1)
    assert result.contributing_source_ids == (SOURCE_IDS[0], SOURCE_IDS[2])


def test_priority_strategy_uses_unique_smallest_positive_priority() -> None:
    sources = (
        _humidity_source(0, priority=2),
        _humidity_source(1, priority=1),
        _humidity_source(2, priority=0),
    )
    result = _humidity(
        sources,
        tuple(_observation(index, value) for index, value in enumerate((10, 20, 30))),
        strategy=AggregationStrategy.PRIORITY,
    )

    assert result.effective_value == 20.0
    assert result.valid_source_ids == SOURCE_IDS[:3]
    assert result.contributing_source_ids == (SOURCE_IDS[1],)
    assert result.fallback_source_id is None
    assert result.status is AggregationStatus.HEALTHY


@pytest.mark.parametrize(
    ("priorities", "reason"),
    [
        ((0, 0), AggregationReason.PRIORITY_NOT_CONFIGURED),
        ((1, 1), AggregationReason.PRIORITY_AMBIGUOUS),
    ],
)
def test_priority_strategy_requires_unique_explicit_priority(
    priorities: tuple[int, int],
    reason: AggregationReason,
) -> None:
    result = _humidity(
        tuple(
            _humidity_source(index, priority=priority)
            for index, priority in enumerate(priorities)
        ),
        (_observation(0, 10.0), _observation(1, 20.0)),
        strategy=AggregationStrategy.PRIORITY,
    )

    assert result.effective_value is None
    assert result.status is AggregationStatus.UNAVAILABLE
    assert result.valid_source_ids == SOURCE_IDS[:2]
    assert result.reasons == (reason,)


def test_excluded_priority_source_cannot_be_selected() -> None:
    result = _humidity(
        (
            _humidity_source(0, priority=1),
            _humidity_source(1, priority=2),
        ),
        (
            _observation(0, None, quality=SourceQuality.STALE),
            _observation(1, 45.0),
        ),
        strategy=AggregationStrategy.PRIORITY,
    )

    assert result.effective_value == 45.0
    assert result.contributing_source_ids == (SOURCE_IDS[1],)
    assert result.status is AggregationStatus.DEGRADED


@pytest.mark.parametrize(
    ("strategy", "expected"),
    [
        (AggregationStrategy.MEAN, 50.0),
        (AggregationStrategy.MEDIAN, 50.0),
        (AggregationStrategy.WEIGHTED_AVERAGE, 70.0),
        (AggregationStrategy.PRIORITY, 90.0),
    ],
)
def test_humidity_supports_all_strategies_without_temperature_rules(
    strategy: AggregationStrategy,
    expected: float,
) -> None:
    result = _humidity(
        (
            _humidity_source(0, weight=1.0, priority=2),
            _humidity_source(1, weight=3.0, priority=1),
        ),
        (_observation(0, 10.0), _observation(1, 90.0)),
        strategy=strategy,
    )

    assert result.effective_value == expected
    assert result.valid_source_ids == SOURCE_IDS[:2]
    assert result.excluded_observations == ()
    assert result.spread == 80.0
    assert result.status is AggregationStatus.HEALTHY


def test_humidity_has_no_temperature_rounding_mad_or_contradiction() -> None:
    result = _humidity(
        tuple(_humidity_source(index) for index in range(3)),
        (
            _observation(0, 0.123),
            _observation(1, 0.123),
            _observation(2, 99.999),
        ),
    )

    assert result.effective_value == pytest.approx((0.123 + 0.123 + 99.999) / 3)
    assert result.spread == pytest.approx(99.876)
    assert result.valid_source_ids == SOURCE_IDS[:3]
    assert result.excluded_observations == ()


def test_humidity_minimum_and_prior_health_exclusion() -> None:
    result = _humidity(
        (_humidity_source(0), _humidity_source(1)),
        (
            _observation(0, 40.0),
            _observation(1, None, quality=SourceQuality.IMPLAUSIBLE),
        ),
        minimum=2,
    )

    assert result.effective_value is None
    assert result.valid_source_ids == (SOURCE_IDS[0],)
    assert result.status is AggregationStatus.UNAVAILABLE
    assert result.reasons == (
        AggregationReason.SOURCE_EXCLUDED,
        AggregationReason.BELOW_MINIMUM_VALID_SOURCES,
    )


def test_no_valid_sources_is_distinct_from_below_minimum() -> None:
    excluded = _observation(0, None, quality=SourceQuality.UNAVAILABLE)
    result = _temperature((_temperature_source(0),), (excluded,))

    assert result.status is AggregationStatus.UNAVAILABLE
    assert result.reasons == (
        AggregationReason.SOURCE_EXCLUDED,
        AggregationReason.NO_VALID_SOURCES,
    )
    assert result.excluded_observations == (excluded,)


def test_reasons_are_deterministic_unique_and_accurate() -> None:
    result = _temperature(
        tuple(_temperature_source(index) for index in range(4)),
        (
            _observation(0, 20.0),
            _observation(1, 20.0),
            _observation(2, 30.0),
            _observation(3, None, quality=SourceQuality.STALE),
        ),
        minimum=3,
    )

    assert result.reasons == (
        AggregationReason.SOURCE_EXCLUDED,
        AggregationReason.OUTLIER_EXCLUDED,
        AggregationReason.BELOW_MINIMUM_VALID_SOURCES,
    )
    assert len(result.reasons) == len(set(result.reasons))
    assert AggregationReason.TWO_SOURCE_CONTRADICTION not in result.reasons


def test_task_9_only_creates_outlier_and_contradictory_quality_codes() -> None:
    outlier = _temperature(
        tuple(_temperature_source(index) for index in range(3)),
        tuple(_observation(index, value) for index, value in enumerate((20, 20, 30))),
    )
    contradiction = _temperature(
        (_temperature_source(0), _temperature_source(1)),
        (_observation(0, 20.0), _observation(1, 30.0)),
    )

    produced = {
        item.quality
        for result in (outlier, contradiction)
        for item in result.excluded_observations
    }
    assert produced == {SourceQuality.OUTLIER, SourceQuality.CONTRADICTORY}
