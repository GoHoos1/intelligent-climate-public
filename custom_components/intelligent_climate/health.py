"""Pure Task 8 source freshness and health evaluation."""

from __future__ import annotations

import math
from dataclasses import replace
from datetime import datetime

from .models import (
    ExclusionReason,
    PendingJumpCandidate,
    SourceBaseline,
    SourceHealthEvaluation,
    SourceObservation,
    SourceQuality,
)

JUMP_CONFIRMATION_DELAY_SECONDS = 30
"""Minimum source-update separation required to confirm a new temperature range."""

HUMIDITY_PLAUSIBLE_MIN = 0.0
HUMIDITY_PLAUSIBLE_MAX = 100.0


def evaluate_temperature_health(
    observation: SourceObservation[float],
    *,
    baseline: SourceBaseline | None,
    pending_jump: PendingJumpCandidate | None,
    stale_after_seconds: int,
    plausible_min_c: float,
    plausible_max_c: float,
    jump_limit_c_per_5_minutes: float,
) -> SourceHealthEvaluation:
    """Evaluate one normalized temperature without clocks, mutation, or I/O."""
    _validate_common_inputs(
        observation,
        baseline=baseline,
        pending_jump=pending_jump,
        stale_after_seconds=stale_after_seconds,
    )
    _validate_temperature_policy(
        plausible_min_c,
        plausible_max_c,
        jump_limit_c_per_5_minutes,
    )

    if observation.quality is not SourceQuality.VALID:
        return SourceHealthEvaluation(observation, baseline, None)

    value, source_last_reported = _valid_value_and_timestamp(observation)
    exclusion = _pre_jump_exclusion(
        observation,
        value=value,
        plausible_min=plausible_min_c,
        plausible_max=plausible_max_c,
        stale_after_seconds=stale_after_seconds,
    )
    if exclusion is not None:
        return SourceHealthEvaluation(exclusion, baseline, None)

    if baseline is None:
        return _accepted(observation, value, source_last_reported)

    baseline_elapsed_seconds = max(
        0.0,
        (source_last_reported - baseline.last_accepted_at).total_seconds(),
    )
    baseline_allowed_change = _allowed_change(
        jump_limit_c_per_5_minutes,
        baseline_elapsed_seconds,
    )
    if _within_allowed_change(
        value,
        baseline.last_accepted_value,
        baseline_allowed_change,
    ):
        return _accepted(observation, value, source_last_reported)

    if pending_jump is None:
        return _jump_rejected(
            observation,
            baseline,
            PendingJumpCandidate(
                source_id=observation.source_id,
                candidate_value=value,
                first_seen_at=source_last_reported,
            ),
        )

    candidate_elapsed_seconds = max(
        0.0,
        (source_last_reported - pending_jump.first_seen_at).total_seconds(),
    )
    candidate_allowed_change = _allowed_change(
        jump_limit_c_per_5_minutes,
        candidate_elapsed_seconds,
    )
    within_candidate_range = _within_allowed_change(
        value,
        pending_jump.candidate_value,
        candidate_allowed_change,
    )
    if (
        candidate_elapsed_seconds >= JUMP_CONFIRMATION_DELAY_SECONDS
        and within_candidate_range
    ):
        return _accepted(observation, value, source_last_reported)
    if within_candidate_range:
        return _jump_rejected(observation, baseline, pending_jump)
    return _jump_rejected(
        observation,
        baseline,
        PendingJumpCandidate(
            source_id=observation.source_id,
            candidate_value=value,
            first_seen_at=source_last_reported,
        ),
    )


def evaluate_humidity_health(
    observation: SourceObservation[float],
    *,
    stale_after_seconds: int,
    baseline: SourceBaseline | None = None,
) -> SourceHealthEvaluation:
    """Evaluate one normalized humidity value with fixed physical bounds."""
    _validate_common_inputs(
        observation,
        baseline=baseline,
        pending_jump=None,
        stale_after_seconds=stale_after_seconds,
    )
    if observation.quality is not SourceQuality.VALID:
        return SourceHealthEvaluation(observation, baseline, None)

    value, source_last_reported = _valid_value_and_timestamp(observation)
    exclusion = _pre_jump_exclusion(
        observation,
        value=value,
        plausible_min=HUMIDITY_PLAUSIBLE_MIN,
        plausible_max=HUMIDITY_PLAUSIBLE_MAX,
        stale_after_seconds=stale_after_seconds,
    )
    if exclusion is not None:
        return SourceHealthEvaluation(exclusion, baseline, None)
    return _accepted(observation, value, source_last_reported)


def _validate_common_inputs(
    observation: SourceObservation[float],
    *,
    baseline: SourceBaseline | None,
    pending_jump: PendingJumpCandidate | None,
    stale_after_seconds: int,
) -> None:
    _require_aware(observation.observed_at, "observation.observed_at")
    if observation.source_last_reported is not None:
        _require_aware(
            observation.source_last_reported,
            "observation.source_last_reported",
        )
    if stale_after_seconds < 0:
        raise ValueError("stale_after_seconds must be nonnegative")
    if observation.quality is SourceQuality.VALID:
        _valid_value_and_timestamp(observation)
    elif observation.normalized_value is not None and not math.isfinite(
        observation.normalized_value
    ):
        raise ValueError("observation normalized value must be finite")

    if baseline is not None:
        if not math.isfinite(baseline.last_accepted_value):
            raise ValueError("baseline.last_accepted_value must be finite")
        _require_aware(baseline.last_accepted_at, "baseline.last_accepted_at")

    if pending_jump is not None:
        if pending_jump.source_id != observation.source_id:
            raise ValueError("pending_jump.source_id must match observation.source_id")
        if not math.isfinite(pending_jump.candidate_value):
            raise ValueError("pending_jump.candidate_value must be finite")
        _require_aware(pending_jump.first_seen_at, "pending_jump.first_seen_at")


def _validate_temperature_policy(
    plausible_min_c: float,
    plausible_max_c: float,
    jump_limit_c_per_5_minutes: float,
) -> None:
    if not math.isfinite(plausible_min_c):
        raise ValueError("plausible_min_c must be finite")
    if not math.isfinite(plausible_max_c):
        raise ValueError("plausible_max_c must be finite")
    if plausible_min_c > plausible_max_c:
        raise ValueError("plausible_min_c must not exceed plausible_max_c")
    if not math.isfinite(jump_limit_c_per_5_minutes) or jump_limit_c_per_5_minutes <= 0:
        raise ValueError("jump_limit_c_per_5_minutes must be finite and positive")


def _valid_value_and_timestamp(
    observation: SourceObservation[float],
) -> tuple[float, datetime]:
    value = observation.normalized_value
    if value is None:
        raise ValueError("VALID observation must have a normalized value")
    if not math.isfinite(value):
        raise ValueError("VALID observation normalized value must be finite")
    source_last_reported = observation.source_last_reported
    if source_last_reported is None:
        raise ValueError("VALID observation must have source_last_reported")
    return value, source_last_reported


def _pre_jump_exclusion(
    observation: SourceObservation[float],
    *,
    value: float,
    plausible_min: float,
    plausible_max: float,
    stale_after_seconds: int,
) -> SourceObservation[float] | None:
    if not plausible_min <= value <= plausible_max:
        return _excluded(observation, SourceQuality.IMPLAUSIBLE)
    if observation.restored:
        return _excluded(observation, SourceQuality.RESTORED_NOT_CONFIRMED)

    source_last_reported = observation.source_last_reported
    assert source_last_reported is not None
    age_seconds = max(
        0.0,
        (observation.observed_at - source_last_reported).total_seconds(),
    )
    if age_seconds > stale_after_seconds:
        return _excluded(observation, SourceQuality.STALE)
    return None


def _allowed_change(rate_c_per_5_minutes: float, elapsed_seconds: float) -> float:
    return rate_c_per_5_minutes * elapsed_seconds / 300


def _within_allowed_change(
    value: float,
    reference_value: float,
    allowed_change: float,
) -> bool:
    difference = abs(value - reference_value)
    return difference <= allowed_change or math.isclose(
        difference,
        allowed_change,
        rel_tol=1e-12,
        abs_tol=1e-12,
    )


def _accepted(
    observation: SourceObservation[float],
    value: float,
    source_last_reported: datetime,
) -> SourceHealthEvaluation:
    return SourceHealthEvaluation(
        observation=observation,
        next_baseline=SourceBaseline(
            last_accepted_value=value,
            last_accepted_at=source_last_reported,
        ),
        pending_jump=None,
    )


def _jump_rejected(
    observation: SourceObservation[float],
    baseline: SourceBaseline,
    pending_jump: PendingJumpCandidate,
) -> SourceHealthEvaluation:
    return SourceHealthEvaluation(
        observation=_excluded(observation, SourceQuality.JUMP_REJECTED),
        next_baseline=baseline,
        pending_jump=pending_jump,
    )


def _excluded(
    observation: SourceObservation[float],
    quality: SourceQuality,
) -> SourceObservation[float]:
    return replace(
        observation,
        normalized_value=None,
        quality=quality,
        exclusion_reason=ExclusionReason(quality.value),
    )


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
