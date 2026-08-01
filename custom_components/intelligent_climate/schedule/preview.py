"""Pure, nonauthoritative schedule-preview and DST-warning projection."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..models.identifiers import SchedulePeriodId, ScheduleProfileId, ZoneId
from ..models.schedule import LocalTime, ScheduleDocument, TargetSpec, Weekday
from .evaluate import ScheduleEvaluationError, evaluate_schedule
from .time import normalize_aware_instant, resolve_local_boundary


class DstWarningKind(StrEnum):
    """Schedule-boundary behavior during a local clock transition."""

    GAP = "gap"
    FOLD = "fold"


@dataclass(frozen=True, slots=True)
class SchedulePreviewZone:
    """Current and next material target for one enabled zone."""

    zone_id: ZoneId
    profile_id: ScheduleProfileId
    period_id: SchedulePeriodId
    target: TargetSpec
    next_target: TargetSpec | None
    next_boundary_utc: datetime
    next_material_transition_utc: datetime | None
    inherited_from_previous_day: bool


@dataclass(frozen=True, slots=True)
class ScheduleDstWarning:
    """Exact behavior of one period boundary in a previewed DST week."""

    zone_id: ZoneId
    profile_id: ScheduleProfileId
    period_id: SchedulePeriodId
    local_date: date
    local_start: LocalTime
    kind: DstWarningKind
    occurs_at_utc: datetime
    explanation: str


@dataclass(frozen=True, slots=True)
class SchedulePreview:
    """Complete nonauthoritative preview for one explicit instant."""

    at_utc: datetime
    time_zone: str
    preview_week_start_local: date
    zones: tuple[SchedulePreviewZone, ...]
    dst_warnings: tuple[ScheduleDstWarning, ...]


def build_schedule_preview(
    document: ScheduleDocument,
    *,
    at: datetime,
) -> SchedulePreview:
    """Evaluate enabled zones and classify boundaries in their local week."""
    try:
        at_utc = normalize_aware_instant(at)
        time_zone = ZoneInfo(document.time_zone)
    except (ValueError, ZoneInfoNotFoundError) as err:
        raise ScheduleEvaluationError("schedule time zone is invalid") from err

    local_date = at_utc.astimezone(time_zone).date()
    week_start = local_date - timedelta(days=local_date.weekday())
    zones: list[SchedulePreviewZone] = []
    warnings: list[ScheduleDstWarning] = []

    for zone_id in sorted(document.zones, key=str):
        zone = document.zones[zone_id]
        if not zone.enabled:
            continue
        evaluation = evaluate_schedule(document, zone_id=zone_id, at=at_utc)
        zones.append(
            SchedulePreviewZone(
                zone_id=zone_id,
                profile_id=evaluation.profile_id,
                period_id=evaluation.base_period_id,
                target=evaluation.base_target,
                next_target=evaluation.next_material_target,
                next_boundary_utc=evaluation.next_boundary_utc,
                next_material_transition_utc=(evaluation.next_material_transition_utc),
                inherited_from_previous_day=(evaluation.inherited_from_previous_day),
            )
        )
        profile = next(
            item
            for item in zone.profiles
            if item.profile_id == zone.selected_profile_id
        )
        for day_offset, weekday in enumerate(Weekday):
            boundary_date = week_start + timedelta(days=day_offset)
            for period in profile.days[weekday]:
                warning = _classify_boundary(
                    zone_id=zone_id,
                    profile_id=profile.profile_id,
                    period_id=period.period_id,
                    local_date=boundary_date,
                    local_start=period.local_start,
                    time_zone=document.time_zone,
                    zone=time_zone,
                )
                if warning is not None:
                    warnings.append(warning)

    return SchedulePreview(
        at_utc=at_utc,
        time_zone=document.time_zone,
        preview_week_start_local=week_start,
        zones=tuple(zones),
        dst_warnings=tuple(warnings),
    )


def _classify_boundary(
    *,
    zone_id: ZoneId,
    profile_id: ScheduleProfileId,
    period_id: SchedulePeriodId,
    local_date: date,
    local_start: LocalTime,
    time_zone: str,
    zone: ZoneInfo,
) -> ScheduleDstWarning | None:
    nominal = datetime.combine(
        local_date,
        datetime.min.time(),
    ).replace(hour=local_start.hour, minute=local_start.minute)
    fold_zero = _round_trips(nominal, zone, fold=0)
    fold_one = _round_trips(nominal, zone, fold=1)
    occurs_at = resolve_local_boundary(
        local_date,
        local_start,
        time_zone=time_zone,
    )
    if not fold_zero and not fold_one:
        local_occurrence = occurs_at.astimezone(zone)
        return ScheduleDstWarning(
            zone_id=zone_id,
            profile_id=profile_id,
            period_id=period_id,
            local_date=local_date,
            local_start=local_start,
            kind=DstWarningKind.GAP,
            occurs_at_utc=occurs_at,
            explanation=(
                f"{local_start} does not exist on {local_date.isoformat()}; "
                "it occurs once at the first valid local minute, "
                f"{local_occurrence:%H:%M}."
            ),
        )
    if fold_zero and fold_one:
        first = nominal.replace(tzinfo=zone, fold=0).astimezone(UTC)
        second = nominal.replace(tzinfo=zone, fold=1).astimezone(UTC)
        if first != second:
            return ScheduleDstWarning(
                zone_id=zone_id,
                profile_id=profile_id,
                period_id=period_id,
                local_date=local_date,
                local_start=local_start,
                kind=DstWarningKind.FOLD,
                occurs_at_utc=first,
                explanation=(
                    f"{local_start} occurs twice on {local_date.isoformat()}; "
                    "the schedule uses only the first occurrence."
                ),
            )
    return None


def _round_trips(nominal: datetime, zone: ZoneInfo, *, fold: int) -> bool:
    candidate = nominal.replace(tzinfo=zone, fold=fold)
    round_trip = candidate.astimezone(UTC).astimezone(zone)
    return round_trip.replace(tzinfo=None) == nominal and round_trip.fold == fold
