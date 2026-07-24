"""Pure source outlier rejection and effective-value aggregation."""

from __future__ import annotations

import math
import statistics
from dataclasses import replace
from datetime import datetime

from .models import (
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

_BOUNDARY_REL_TOL = 1e-12
_BOUNDARY_ABS_TOL = 1e-12

_REASON_ORDER = (
    AggregationReason.SOURCE_EXCLUDED,
    AggregationReason.OUTLIER_EXCLUDED,
    AggregationReason.TWO_SOURCE_CONTRADICTION,
    AggregationReason.BELOW_MINIMUM_VALID_SOURCES,
    AggregationReason.NO_ENABLED_SOURCES,
    AggregationReason.NO_VALID_SOURCES,
    AggregationReason.PRIORITY_NOT_CONFIGURED,
    AggregationReason.PRIORITY_AMBIGUOUS,
    AggregationReason.PRIORITY_FALLBACK,
)

type _Source = TemperatureSource | HumiditySource


def aggregate_temperature_sources(
    sources: tuple[TemperatureSource, ...],
    observations: tuple[SourceObservation[float], ...],
    *,
    strategy: AggregationStrategy,
    min_valid_sources: int,
    outlier_floor_c: float,
    calculated_at: datetime,
) -> SourceAggregationResult:
    """Calculate effective Celsius temperature from Task 8 observations.

    A successfully calculated value is rounded with Python's ``round(value, 1)``
    only after filtering and aggregation. Source values and spread are never
    rounded by this boundary.
    """
    _validate_policy(
        strategy=strategy,
        min_valid_sources=min_valid_sources,
        calculated_at=calculated_at,
    )
    if (
        isinstance(outlier_floor_c, bool)
        or not isinstance(outlier_floor_c, int | float)
        or not math.isfinite(outlier_floor_c)
        or outlier_floor_c <= 0
    ):
        raise ValueError("outlier_floor_c must be a finite positive number")

    enabled, ordered_observations = _match_inputs(sources, observations)
    if not enabled:
        return _unavailable(
            calculated_at=calculated_at,
            reasons={AggregationReason.NO_ENABLED_SOURCES},
        )

    valid, excluded = _partition_observations(ordered_observations)
    reasons: set[AggregationReason] = set()
    if excluded:
        reasons.add(AggregationReason.SOURCE_EXCLUDED)

    original_valid_count = len(valid)
    if original_valid_count == 2:
        first = _normalized_value(valid[0])
        second = _normalized_value(valid[1])
        spread_c = abs(first - second)
        contradiction_threshold_c = 2 * float(outlier_floor_c)
        if not _at_or_below(spread_c, contradiction_threshold_c):
            return _contradictory_temperature_result(
                sources=enabled,
                valid=valid,
                excluded=excluded,
                min_valid_sources=min_valid_sources,
                calculated_at=calculated_at,
                reasons=reasons,
            )
    elif original_valid_count >= 3:
        valid, outliers = _reject_temperature_outliers(
            valid,
            outlier_floor_c=float(outlier_floor_c),
        )
        if outliers:
            excluded.extend(outliers)
            reasons.add(AggregationReason.OUTLIER_EXCLUDED)

    return _normal_result(
        sources=enabled,
        valid=valid,
        excluded=excluded,
        strategy=strategy,
        min_valid_sources=min_valid_sources,
        calculated_at=calculated_at,
        reasons=reasons,
        round_temperature=True,
    )


def aggregate_humidity_sources(
    sources: tuple[HumiditySource, ...],
    observations: tuple[SourceObservation[float], ...],
    *,
    strategy: AggregationStrategy,
    min_valid_sources: int,
    calculated_at: datetime,
) -> SourceAggregationResult:
    """Calculate effective humidity without temperature-specific filtering."""
    _validate_policy(
        strategy=strategy,
        min_valid_sources=min_valid_sources,
        calculated_at=calculated_at,
    )
    enabled, ordered_observations = _match_inputs(sources, observations)
    if not enabled:
        return _unavailable(
            calculated_at=calculated_at,
            reasons={AggregationReason.NO_ENABLED_SOURCES},
        )

    valid, excluded = _partition_observations(ordered_observations)
    reasons: set[AggregationReason] = set()
    if excluded:
        reasons.add(AggregationReason.SOURCE_EXCLUDED)
    return _normal_result(
        sources=enabled,
        valid=valid,
        excluded=excluded,
        strategy=strategy,
        min_valid_sources=min_valid_sources,
        calculated_at=calculated_at,
        reasons=reasons,
        round_temperature=False,
    )


def _validate_policy(
    *,
    strategy: AggregationStrategy,
    min_valid_sources: int,
    calculated_at: datetime,
) -> None:
    if not isinstance(strategy, AggregationStrategy):
        raise ValueError("strategy must be an AggregationStrategy")
    if (
        isinstance(min_valid_sources, bool)
        or not isinstance(min_valid_sources, int)
        or min_valid_sources <= 0
    ):
        raise ValueError("min_valid_sources must be a positive integer")
    _require_aware(calculated_at, "calculated_at")


def _match_inputs[SourceT: (TemperatureSource, HumiditySource)](
    sources: tuple[SourceT, ...],
    observations: tuple[SourceObservation[float], ...],
) -> tuple[tuple[SourceT, ...], tuple[SourceObservation[float], ...]]:
    source_by_id: dict[ObservationSourceId, SourceT] = {}
    for source in sources:
        if source.source_id in source_by_id:
            raise ValueError("configured source IDs must be unique")
        _validate_source_policy(source)
        source_by_id[source.source_id] = source

    observation_by_id: dict[ObservationSourceId, SourceObservation[float]] = {}
    for observation in observations:
        if observation.source_id in observation_by_id:
            raise ValueError("observation source IDs must be unique")
        configured_source = source_by_id.get(observation.source_id)
        if configured_source is None:
            raise ValueError("observation source_id is not configured")
        if not configured_source.enabled:
            raise ValueError("observation supplied for a disabled source")
        _validate_observation(observation)
        observation_by_id[observation.source_id] = observation

    enabled = tuple(source for source in sources if source.enabled)
    missing = tuple(
        source.source_id
        for source in enabled
        if source.source_id not in observation_by_id
    )
    if missing:
        raise ValueError("every enabled source must have exactly one observation")
    ordered = tuple(observation_by_id[source.source_id] for source in enabled)
    return enabled, ordered


def _validate_source_policy(source: _Source) -> None:
    if not isinstance(source.enabled, bool):
        raise ValueError("source enabled flags must be booleans")
    if isinstance(source.weight, bool) or not isinstance(source.weight, int | float):
        raise ValueError("source weights must be finite positive numbers")
    try:
        finite_weight = math.isfinite(source.weight)
    except OverflowError as err:
        raise ValueError("source weights must be finite positive numbers") from err
    if not finite_weight or source.weight <= 0:
        raise ValueError("source weights must be finite positive numbers")
    if (
        isinstance(source.priority, bool)
        or not isinstance(source.priority, int)
        or source.priority < 0
    ):
        raise ValueError("source priorities must be nonnegative integers")


def _validate_observation(observation: SourceObservation[float]) -> None:
    _require_aware(observation.observed_at, "observation.observed_at")
    if observation.source_last_reported is not None:
        _require_aware(
            observation.source_last_reported,
            "observation.source_last_reported",
        )
    if not isinstance(observation.quality, SourceQuality):
        raise ValueError("observation quality must be a SourceQuality")

    if observation.quality is SourceQuality.VALID:
        _normalized_value(observation)
        if observation.exclusion_reason is not None:
            raise ValueError("VALID observation cannot have an exclusion reason")
        if observation.source_last_reported is None:
            raise ValueError("VALID observation must have source_last_reported")
        return

    if observation.normalized_value is not None:
        raise ValueError("excluded observation cannot have a normalized value")
    expected_reason = ExclusionReason(observation.quality.value)
    if observation.exclusion_reason is not expected_reason:
        raise ValueError("excluded observation reason must match its quality")


def _partition_observations(
    observations: tuple[SourceObservation[float], ...],
) -> tuple[
    list[SourceObservation[float]],
    list[SourceObservation[float]],
]:
    valid: list[SourceObservation[float]] = []
    excluded: list[SourceObservation[float]] = []
    for observation in observations:
        if observation.quality is SourceQuality.VALID:
            valid.append(observation)
        else:
            excluded.append(observation)
    return valid, excluded


def _reject_temperature_outliers(
    valid: list[SourceObservation[float]],
    *,
    outlier_floor_c: float,
) -> tuple[
    list[SourceObservation[float]],
    list[SourceObservation[float]],
]:
    values = tuple(_normalized_value(observation) for observation in valid)
    median_value = statistics.median(values)
    deviations = tuple(abs(value - median_value) for value in values)
    mad = statistics.median(deviations)
    threshold = max(outlier_floor_c, 3 * 1.4826 * mad)

    retained: list[SourceObservation[float]] = []
    outliers: list[SourceObservation[float]] = []
    for observation, deviation in zip(valid, deviations, strict=True):
        if deviation > threshold and not math.isclose(
            deviation,
            threshold,
            rel_tol=_BOUNDARY_REL_TOL,
            abs_tol=_BOUNDARY_ABS_TOL,
        ):
            outliers.append(_task_9_exclusion(observation, SourceQuality.OUTLIER))
        else:
            retained.append(observation)
    return retained, outliers


def _contradictory_temperature_result(
    *,
    sources: tuple[TemperatureSource, ...],
    valid: list[SourceObservation[float]],
    excluded: list[SourceObservation[float]],
    min_valid_sources: int,
    calculated_at: datetime,
    reasons: set[AggregationReason],
) -> SourceAggregationResult:
    contradictory = [
        _task_9_exclusion(observation, SourceQuality.CONTRADICTORY)
        for observation in valid
    ]
    ordered_excluded = _ordered_exclusions(
        sources,
        [*excluded, *contradictory],
    )
    reasons.add(AggregationReason.TWO_SOURCE_CONTRADICTION)
    selected, priority_reason = _priority_source(sources, valid)

    if selected is not None and min_valid_sources <= 1:
        value = round(_normalized_value(selected), 1)
        reasons.add(AggregationReason.PRIORITY_FALLBACK)
        return SourceAggregationResult(
            effective_value=value,
            spread=None,
            valid_source_ids=(),
            contributing_source_ids=(selected.source_id,),
            fallback_source_id=selected.source_id,
            excluded_observations=ordered_excluded,
            status=AggregationStatus.DEGRADED,
            reasons=_ordered_reasons(reasons),
            calculated_at=calculated_at,
        )

    if selected is None:
        assert priority_reason is not None
        reasons.add(priority_reason)
    if min_valid_sources > 1:
        reasons.add(AggregationReason.BELOW_MINIMUM_VALID_SOURCES)
    return SourceAggregationResult(
        effective_value=None,
        spread=None,
        valid_source_ids=(),
        contributing_source_ids=(),
        fallback_source_id=None,
        excluded_observations=ordered_excluded,
        status=AggregationStatus.UNAVAILABLE,
        reasons=_ordered_reasons(reasons),
        calculated_at=calculated_at,
    )


def _normal_result[SourceT: (TemperatureSource, HumiditySource)](
    *,
    sources: tuple[SourceT, ...],
    valid: list[SourceObservation[float]],
    excluded: list[SourceObservation[float]],
    strategy: AggregationStrategy,
    min_valid_sources: int,
    calculated_at: datetime,
    reasons: set[AggregationReason],
    round_temperature: bool,
) -> SourceAggregationResult:
    valid_ids = tuple(observation.source_id for observation in valid)
    values = tuple(_normalized_value(observation) for observation in valid)
    spread = max(values) - min(values) if values else None
    ordered_excluded = _ordered_exclusions(sources, excluded)

    if not valid:
        reasons.add(AggregationReason.NO_VALID_SOURCES)
        return SourceAggregationResult(
            effective_value=None,
            spread=None,
            valid_source_ids=(),
            contributing_source_ids=(),
            fallback_source_id=None,
            excluded_observations=ordered_excluded,
            status=AggregationStatus.UNAVAILABLE,
            reasons=_ordered_reasons(reasons),
            calculated_at=calculated_at,
        )
    if len(valid) < min_valid_sources:
        reasons.add(AggregationReason.BELOW_MINIMUM_VALID_SOURCES)
        return SourceAggregationResult(
            effective_value=None,
            spread=spread,
            valid_source_ids=valid_ids,
            contributing_source_ids=(),
            fallback_source_id=None,
            excluded_observations=ordered_excluded,
            status=AggregationStatus.UNAVAILABLE,
            reasons=_ordered_reasons(reasons),
            calculated_at=calculated_at,
        )

    contributing = valid
    if strategy is AggregationStrategy.PRIORITY:
        selected, priority_reason = _priority_source(sources, valid)
        if selected is None:
            assert priority_reason is not None
            reasons.add(priority_reason)
            return SourceAggregationResult(
                effective_value=None,
                spread=spread,
                valid_source_ids=valid_ids,
                contributing_source_ids=(),
                fallback_source_id=None,
                excluded_observations=ordered_excluded,
                status=AggregationStatus.UNAVAILABLE,
                reasons=_ordered_reasons(reasons),
                calculated_at=calculated_at,
            )
        value = _normalized_value(selected)
        contributing = [selected]
    else:
        value = _calculate_strategy(sources, valid, strategy)

    if round_temperature:
        value = round(value, 1)
    return SourceAggregationResult(
        effective_value=value,
        spread=spread,
        valid_source_ids=valid_ids,
        contributing_source_ids=tuple(
            observation.source_id for observation in contributing
        ),
        fallback_source_id=None,
        excluded_observations=ordered_excluded,
        status=(
            AggregationStatus.DEGRADED
            if ordered_excluded
            else AggregationStatus.HEALTHY
        ),
        reasons=_ordered_reasons(reasons),
        calculated_at=calculated_at,
    )


def _calculate_strategy[SourceT: (TemperatureSource, HumiditySource)](
    sources: tuple[SourceT, ...],
    valid: list[SourceObservation[float]],
    strategy: AggregationStrategy,
) -> float:
    values = tuple(_normalized_value(observation) for observation in valid)
    if strategy is AggregationStrategy.MEAN:
        return statistics.fmean(values)
    if strategy is AggregationStrategy.MEDIAN:
        return statistics.median(values)
    if strategy is AggregationStrategy.WEIGHTED_AVERAGE:
        source_by_id = {source.source_id: source for source in sources}
        weights = tuple(source_by_id[item.source_id].weight for item in valid)
        scale = max(weights)
        normalized_weights = tuple(weight / scale for weight in weights)
        numerator = math.fsum(
            value * weight
            for value, weight in zip(values, normalized_weights, strict=True)
        )
        return numerator / math.fsum(normalized_weights)
    raise ValueError("unsupported aggregation strategy")


def _priority_source[SourceT: (TemperatureSource, HumiditySource)](
    sources: tuple[SourceT, ...],
    valid: list[SourceObservation[float]],
) -> tuple[
    SourceObservation[float] | None,
    AggregationReason | None,
]:
    source_by_id = {source.source_id: source for source in sources}
    explicit = [
        observation
        for observation in valid
        if source_by_id[observation.source_id].priority > 0
    ]
    if not explicit:
        return None, AggregationReason.PRIORITY_NOT_CONFIGURED
    best = min(source_by_id[item.source_id].priority for item in explicit)
    selected = [
        observation
        for observation in explicit
        if source_by_id[observation.source_id].priority == best
    ]
    if len(selected) != 1:
        return None, AggregationReason.PRIORITY_AMBIGUOUS
    return selected[0], None


def _task_9_exclusion(
    observation: SourceObservation[float],
    quality: SourceQuality,
) -> SourceObservation[float]:
    if quality not in {SourceQuality.OUTLIER, SourceQuality.CONTRADICTORY}:
        raise ValueError("Task 9 can only create outlier or contradictory exclusions")
    return replace(
        observation,
        normalized_value=None,
        quality=quality,
        exclusion_reason=ExclusionReason(quality.value),
    )


def _ordered_exclusions[SourceT: (TemperatureSource, HumiditySource)](
    sources: tuple[SourceT, ...],
    exclusions: list[SourceObservation[float]],
) -> tuple[SourceObservation[float], ...]:
    by_id = {observation.source_id: observation for observation in exclusions}
    ordered: list[SourceObservation[float]] = []
    for source in sources:
        observation = by_id.get(source.source_id)
        if observation is not None:
            ordered.append(observation)
    return tuple(ordered)


def _ordered_reasons(
    reasons: set[AggregationReason],
) -> tuple[AggregationReason, ...]:
    return tuple(reason for reason in _REASON_ORDER if reason in reasons)


def _unavailable(
    *,
    calculated_at: datetime,
    reasons: set[AggregationReason],
) -> SourceAggregationResult:
    return SourceAggregationResult(
        effective_value=None,
        spread=None,
        valid_source_ids=(),
        contributing_source_ids=(),
        fallback_source_id=None,
        excluded_observations=(),
        status=AggregationStatus.UNAVAILABLE,
        reasons=_ordered_reasons(reasons),
        calculated_at=calculated_at,
    )


def _normalized_value(observation: SourceObservation[float]) -> float:
    value = observation.normalized_value
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError("VALID observation must have a finite numeric value")
    try:
        numeric = float(value)
    except OverflowError as err:
        raise ValueError("VALID observation must have a finite numeric value") from err
    if not math.isfinite(numeric):
        raise ValueError("VALID observation must have a finite numeric value")
    return numeric


def _at_or_below(value: float, boundary: float) -> bool:
    return value <= boundary or math.isclose(
        value,
        boundary,
        rel_tol=_BOUNDARY_REL_TOL,
        abs_tol=_BOUNDARY_ABS_TOL,
    )


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
