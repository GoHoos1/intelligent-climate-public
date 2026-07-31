"""Pure evaluation of one zone's circular weekly schedule."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..models.control import ControlReason
from ..models.identifiers import (
    SchedulePeriodId,
    ScheduleProfileId,
    ZoneId,
)
from ..models.schedule import (
    ScheduleDocument,
    TargetSpec,
    WeeklyScheduleProfile,
)
from .time import normalize_aware_instant
from .transitions import locate_circular_schedule


class ScheduleEvaluationError(ValueError):
    """Raised when a schedule cannot be safely evaluated."""


@dataclass(frozen=True, slots=True)
class ScheduleEvaluation:
    """Current base schedule result and its next circular deadlines."""

    zone_id: ZoneId
    profile_id: ScheduleProfileId
    base_period_id: SchedulePeriodId
    base_target: TargetSpec
    effective_target: TargetSpec
    current_local_date: date
    current_local_time: time
    current_local_fold: int
    inherited_from_previous_day: bool
    next_boundary_utc: datetime
    next_material_transition_utc: datetime | None
    next_material_target: TargetSpec | None
    reason_code: ControlReason


def evaluate_schedule(
    document: ScheduleDocument,
    *,
    zone_id: ZoneId,
    at: datetime,
    profile_id: ScheduleProfileId | None = None,
) -> ScheduleEvaluation:
    """Evaluate an enabled zone/profile at one explicit aware instant.

    Task 4 has no occupancy, override, or protection overlay. The effective
    target therefore equals the base target. Later pure policy layers may
    replace it without changing the circular schedule calculation.
    """
    try:
        evaluation_utc = normalize_aware_instant(at)
    except ValueError as err:
        raise ScheduleEvaluationError(str(err)) from err
    try:
        time_zone = ZoneInfo(document.time_zone)
    except (ValueError, ZoneInfoNotFoundError) as err:
        raise ScheduleEvaluationError("schedule time zone is invalid") from err

    zone_set = document.zones.get(zone_id)
    if zone_set is None:
        raise ScheduleEvaluationError("zone is not present in the schedule")
    if not zone_set.enabled:
        raise ScheduleEvaluationError("zone schedule is disabled")

    selected_profile_id = profile_id or zone_set.selected_profile_id
    profile = _find_profile(zone_set.profiles, selected_profile_id)
    if profile is None:
        raise ScheduleEvaluationError("profile is not present in the zone schedule")
    if not profile.enabled:
        raise ScheduleEvaluationError("schedule profile is disabled")

    try:
        position = locate_circular_schedule(
            profile,
            time_zone=document.time_zone,
            at=evaluation_utc,
        )
    except ValueError as err:
        raise ScheduleEvaluationError(str(err)) from err

    current_local = evaluation_utc.astimezone(time_zone)
    active = position.active_boundary
    material = position.next_material_boundary
    return ScheduleEvaluation(
        zone_id=zone_id,
        profile_id=profile.profile_id,
        base_period_id=active.period.period_id,
        base_target=active.period.target,
        effective_target=active.period.target,
        current_local_date=current_local.date(),
        current_local_time=current_local.time(),
        current_local_fold=current_local.fold,
        inherited_from_previous_day=active.local_date != current_local.date(),
        next_boundary_utc=position.next_boundary.occurs_at_utc,
        next_material_transition_utc=(
            material.occurs_at_utc if material is not None else None
        ),
        next_material_target=(material.period.target if material is not None else None),
        reason_code=ControlReason.SCHEDULE_EVALUATION,
    )


def _find_profile(
    profiles: tuple[WeeklyScheduleProfile, ...],
    profile_id: ScheduleProfileId,
) -> WeeklyScheduleProfile | None:
    return next(
        (profile for profile in profiles if profile.profile_id == profile_id),
        None,
    )
