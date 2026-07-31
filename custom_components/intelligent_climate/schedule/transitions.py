"""Circular weekly boundary and material-transition calculation."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from itertools import groupby
from operator import attrgetter
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..models.schedule import (
    WEEKDAYS,
    SchedulePeriod,
    TargetSpec,
    WeeklyScheduleProfile,
)
from .time import normalize_aware_instant, resolve_local_boundary

_PAST_SEARCH_DAYS = 8
_FUTURE_SEARCH_DAYS = 15


@dataclass(frozen=True, slots=True)
class ScheduleBoundary:
    """One nominal local weekly period resolved to a real UTC instant."""

    local_date: date
    period: SchedulePeriod
    occurs_at_utc: datetime


@dataclass(frozen=True, slots=True)
class CircularSchedulePosition:
    """Active, next, and next target-changing circular boundaries."""

    active_boundary: ScheduleBoundary
    next_boundary: ScheduleBoundary
    next_material_boundary: ScheduleBoundary | None


def locate_circular_schedule(
    profile: WeeklyScheduleProfile,
    *,
    time_zone: str,
    at: datetime,
) -> CircularSchedulePosition:
    """Locate current and future boundaries in a repeating weekly profile."""
    evaluation_utc = normalize_aware_instant(at)
    try:
        local_date = evaluation_utc.astimezone(ZoneInfo(time_zone)).date()
    except (ValueError, ZoneInfoNotFoundError) as err:
        raise ValueError("schedule time zone is invalid") from err

    if not any(profile.days.values()):
        raise ValueError("schedule profile has no weekly periods")

    boundaries = tuple(
        _resolved_boundaries(
            profile,
            time_zone=time_zone,
            first_date=local_date - timedelta(days=_PAST_SEARCH_DAYS),
            last_date=local_date + timedelta(days=_FUTURE_SEARCH_DAYS),
        )
    )
    active_candidates = tuple(
        boundary for boundary in boundaries if boundary.occurs_at_utc <= evaluation_utc
    )
    future_boundaries = tuple(
        boundary for boundary in boundaries if boundary.occurs_at_utc > evaluation_utc
    )
    active = active_candidates[-1]
    return CircularSchedulePosition(
        active_boundary=active,
        next_boundary=future_boundaries[0],
        next_material_boundary=_next_material_boundary(
            future_boundaries,
            current_target=active.period.target,
        ),
    )


def _resolved_boundaries(
    profile: WeeklyScheduleProfile,
    *,
    time_zone: str,
    first_date: date,
    last_date: date,
) -> Iterable[ScheduleBoundary]:
    boundaries: list[ScheduleBoundary] = []
    current_date = first_date
    while current_date <= last_date:
        weekday = WEEKDAYS[current_date.weekday()]
        boundaries.extend(
            ScheduleBoundary(
                local_date=current_date,
                period=period,
                occurs_at_utc=resolve_local_boundary(
                    current_date,
                    period.local_start,
                    time_zone=time_zone,
                ),
            )
            for period in profile.days[weekday]
        )
        current_date += timedelta(days=1)
    return sorted(
        boundaries,
        key=lambda item: (
            item.occurs_at_utc,
            item.local_date,
            item.period.local_start,
        ),
    )


def _next_material_boundary(
    future_boundaries: tuple[ScheduleBoundary, ...],
    *,
    current_target: TargetSpec,
) -> ScheduleBoundary | None:
    for _, same_instant in groupby(
        future_boundaries,
        key=attrgetter("occurs_at_utc"),
    ):
        final_boundary = tuple(same_instant)[-1]
        if final_boundary.period.target != current_target:
            return final_boundary
    return None
