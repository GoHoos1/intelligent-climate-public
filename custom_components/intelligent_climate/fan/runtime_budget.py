"""Deterministic rolling-hour fan runtime accounting."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import ceil

from ..models.fan import FanRuntimeBudget, validate_fan_runtime_budget
from ..models.schema import SchemaValidationError


@dataclass(frozen=True, slots=True)
class FanRuntimeBudgetState:
    """One rolling-hour budget calculation."""

    runtime_seconds_last_hour: int
    remaining_seconds: int
    exhausted: bool
    next_release_at_utc: datetime | None


def calculate_fan_runtime_budget(
    budget: FanRuntimeBudget,
    *,
    at_utc: datetime,
    maximum_runtime_per_hour_seconds: int,
    running_since_utc: datetime | None = None,
) -> FanRuntimeBudgetState:
    """Calculate overlap with the strict trailing-hour window."""
    validate_fan_runtime_budget(budget)
    at = _utc(at_utc, "at_utc")
    if (
        not isinstance(maximum_runtime_per_hour_seconds, int)
        or isinstance(maximum_runtime_per_hour_seconds, bool)
        or not 1 <= maximum_runtime_per_hour_seconds <= 3600
    ):
        raise SchemaValidationError(
            "maximum_runtime_per_hour_seconds",
            "must be a whole number from 1 through 3600",
        )
    running_since = (
        None
        if running_since_utc is None
        else _utc(running_since_utc, "running_since_utc")
    )
    if running_since is not None and running_since > at:
        raise SchemaValidationError("running_since_utc", "must not be in the future")
    if budget.intervals and budget.intervals[-1].ended_at_utc.astimezone(UTC) > at:
        raise SchemaValidationError(
            "fan_runtime_budget", "must not contain a future interval"
        )
    if (
        running_since is not None
        and budget.intervals
        and budget.intervals[-1].ended_at_utc.astimezone(UTC) > running_since
    ):
        raise SchemaValidationError(
            "running_since_utc", "must not overlap a completed interval"
        )

    window_start = at - timedelta(hours=1)
    total = 0.0
    release_candidates: list[datetime] = []
    for interval in budget.intervals:
        started = interval.started_at_utc.astimezone(UTC)
        ended = interval.ended_at_utc.astimezone(UTC)
        overlap_start = max(started, window_start)
        overlap_end = min(ended, at)
        if overlap_start < overlap_end:
            total += (overlap_end - overlap_start).total_seconds()
            release_at = started + timedelta(hours=1)
            if release_at > at:
                release_candidates.append(release_at)
            else:
                release_candidates.append(at + timedelta(seconds=1))
    if running_since is not None:
        total += (at - max(running_since, window_start)).total_seconds()

    runtime = min(3600, max(0, ceil(total)))
    remaining = max(0, maximum_runtime_per_hour_seconds - runtime)
    return FanRuntimeBudgetState(
        runtime_seconds_last_hour=runtime,
        remaining_seconds=remaining,
        exhausted=remaining == 0,
        next_release_at_utc=(
            min(release_candidates) if release_candidates and remaining == 0 else None
        ),
    )


def _utc(value: object, path: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise SchemaValidationError(path, "must be an aware datetime")
    return value.astimezone(UTC)
