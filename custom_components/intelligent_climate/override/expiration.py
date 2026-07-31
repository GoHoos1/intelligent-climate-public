"""Deterministic caller-clock override expiration calculations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from itertools import groupby
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..models.identifiers import ScheduleProfileId, ZoneId
from ..models.override import (
    OverrideExpirationKind,
    OverrideExpirationPolicy,
    validate_expiration_policy,
)
from ..models.schedule import (
    WEEKDAYS,
    LocalTime,
    ScheduleDocument,
    TargetSpec,
)
from ..schedule.evaluate import ScheduleEvaluationError, evaluate_schedule
from ..schedule.time import normalize_aware_instant, resolve_local_boundary


class ExpirationReasonCode(StrEnum):
    """Privacy-safe reason for one expiration calculation."""

    NEXT_MATERIAL_SCHEDULE_TRANSITION = "next_material_schedule_transition"
    NO_MATERIAL_SCHEDULE_TRANSITION = "no_material_schedule_transition"
    DURATION_ELAPSED = "duration_elapsed"
    NEXT_ACCEPTED_OCCUPANCY_TRANSITION = "next_accepted_occupancy_transition"
    NO_ACCEPTED_OCCUPANCY_TRANSITION = "no_accepted_occupancy_transition"
    SPECIFIED_LOCAL_TIME = "specified_local_time"
    MANUAL_CANCELLATION_REQUIRED = "manual_cancellation_required"
    NEXT_DAY_SCHEDULE_BOUNDARY = "next_day_schedule_boundary"
    NEXT_DAY_MIDNIGHT_FALLBACK = "next_day_midnight_fallback"


class OccupancyTransitionKind(StrEnum):
    """Whether a future occupancy observation can expire an override."""

    ACCEPTED_DEBOUNCED_CHANGE = "accepted_debounced_change"
    STARTUP_RESOLUTION = "startup_resolution"
    SOURCE_BOUNCE = "source_bounce"


@dataclass(frozen=True, slots=True)
class EffectiveScheduleTransition:
    """Caller-supplied, occupancy-adjusted target after one schedule boundary."""

    occurs_at_utc: datetime
    effective_target: TargetSpec
    transition_key: str


@dataclass(frozen=True, slots=True)
class OccupancyTransition:
    """Caller-supplied future occupancy resolution."""

    occurs_at_utc: datetime
    kind: OccupancyTransitionKind
    previous_mode: str
    next_mode: str


@dataclass(frozen=True, slots=True)
class OverrideExpirationInputs:
    """All pure caller inputs used by expiration calculation."""

    at_utc: datetime
    time_zone: str
    schedule_document: ScheduleDocument | None = None
    zone_id: ZoneId | None = None
    profile_id: ScheduleProfileId | None = None
    current_effective_target: TargetSpec | None = None
    effective_schedule_transitions: tuple[EffectiveScheduleTransition, ...] = ()
    occupancy_transitions: tuple[OccupancyTransition, ...] = ()


@dataclass(frozen=True, slots=True)
class ExpirationCalculation:
    """Resolved UTC deadline and fixed privacy-safe explanation."""

    expires_at_utc: datetime | None
    anchor_transition_key: str | None
    reason_code: ExpirationReasonCode
    explanation: str


def calculate_override_expiration(
    policy: OverrideExpirationPolicy,
    *,
    inputs: OverrideExpirationInputs,
) -> ExpirationCalculation:
    """Calculate one policy without reading clocks, state, or Home Assistant."""
    validate_expiration_policy(policy)
    at_utc = _utc(inputs.at_utc, "at_utc")
    _zone(inputs.time_zone)

    if policy.kind is OverrideExpirationKind.DURATION:
        assert policy.duration_seconds is not None
        return _result(
            at_utc + timedelta(seconds=policy.duration_seconds),
            None,
            ExpirationReasonCode.DURATION_ELAPSED,
        )
    if policy.kind is OverrideExpirationKind.SPECIFIED_LOCAL_TIME:
        assert policy.local_time is not None
        local_now = at_utc.astimezone(ZoneInfo(inputs.time_zone))
        candidate_date = local_now.date()
        deadline = resolve_local_boundary(
            candidate_date,
            policy.local_time,
            time_zone=inputs.time_zone,
        )
        if deadline <= at_utc:
            deadline = resolve_local_boundary(
                candidate_date + timedelta(days=1),
                policy.local_time,
                time_zone=inputs.time_zone,
            )
        return _result(deadline, None, ExpirationReasonCode.SPECIFIED_LOCAL_TIME)
    if policy.kind is OverrideExpirationKind.MANUAL_CANCELLATION:
        return _result(
            None,
            None,
            ExpirationReasonCode.MANUAL_CANCELLATION_REQUIRED,
        )
    if policy.kind is OverrideExpirationKind.NEXT_OCCUPANCY_TRANSITION:
        return _next_occupancy_transition(at_utc, inputs.occupancy_transitions)
    if policy.kind is OverrideExpirationKind.NEXT_DAY_SCHEDULE_START:
        document, zone_id, profile = _schedule_inputs(inputs)
        return _next_day_schedule_start(
            at_utc,
            document=document,
            zone_id=zone_id,
            profile_id=profile,
        )
    if inputs.effective_schedule_transitions:
        if inputs.current_effective_target is None:
            raise ValueError(
                "current_effective_target is required with effective transitions"
            )
        return _next_effective_material_transition(
            at_utc,
            current_target=inputs.current_effective_target,
            transitions=inputs.effective_schedule_transitions,
        )
    document, zone_id, profile = _schedule_inputs(inputs)
    try:
        evaluation = evaluate_schedule(
            document,
            zone_id=zone_id,
            at=at_utc,
            profile_id=profile,
        )
    except ScheduleEvaluationError as err:
        raise ValueError(str(err)) from err
    if evaluation.next_material_transition_utc is None:
        return _result(
            None,
            None,
            ExpirationReasonCode.NO_MATERIAL_SCHEDULE_TRANSITION,
        )
    key = (
        f"{zone_id}:{evaluation.profile_id}:"
        f"{evaluation.next_material_transition_utc.isoformat()}"
    )
    return _result(
        evaluation.next_material_transition_utc,
        key,
        ExpirationReasonCode.NEXT_MATERIAL_SCHEDULE_TRANSITION,
    )


def _next_effective_material_transition(
    at_utc: datetime,
    *,
    current_target: TargetSpec,
    transitions: tuple[EffectiveScheduleTransition, ...],
) -> ExpirationCalculation:
    previous: datetime | None = None
    validated: list[EffectiveScheduleTransition] = []
    for index, transition in enumerate(transitions):
        occurs_at = _utc(
            transition.occurs_at_utc,
            f"effective_schedule_transitions[{index}].occurs_at_utc",
        )
        if occurs_at <= at_utc:
            raise ValueError("effective schedule transitions must be strict future")
        if previous is not None and occurs_at < previous:
            raise ValueError("effective schedule transitions must be ordered")
        if not transition.transition_key or len(transition.transition_key) > 255:
            raise ValueError("transition key must be nonempty and bounded")
        previous = occurs_at
        validated.append(transition)
    for _, same_instant in groupby(
        validated,
        key=lambda item: item.occurs_at_utc,
    ):
        final = tuple(same_instant)[-1]
        if final.effective_target != current_target:
            return _result(
                final.occurs_at_utc,
                final.transition_key,
                ExpirationReasonCode.NEXT_MATERIAL_SCHEDULE_TRANSITION,
            )
    return _result(
        None,
        None,
        ExpirationReasonCode.NO_MATERIAL_SCHEDULE_TRANSITION,
    )


def _next_occupancy_transition(
    at_utc: datetime,
    transitions: tuple[OccupancyTransition, ...],
) -> ExpirationCalculation:
    previous: datetime | None = None
    for index, transition in enumerate(transitions):
        occurs_at = _utc(
            transition.occurs_at_utc,
            f"occupancy_transitions[{index}].occurs_at_utc",
        )
        if occurs_at <= at_utc:
            raise ValueError("occupancy transitions must be strict future")
        if previous is not None and occurs_at <= previous:
            raise ValueError("occupancy transitions must be strictly ordered")
        if not isinstance(transition.kind, OccupancyTransitionKind):
            raise ValueError("occupancy transition kind is unsupported")
        if not transition.previous_mode or not transition.next_mode:
            raise ValueError("occupancy transition modes must be nonempty")
        previous = occurs_at
        if (
            transition.kind is OccupancyTransitionKind.ACCEPTED_DEBOUNCED_CHANGE
            and transition.previous_mode != transition.next_mode
        ):
            return _result(
                occurs_at,
                None,
                ExpirationReasonCode.NEXT_ACCEPTED_OCCUPANCY_TRANSITION,
            )
    return _result(
        None,
        None,
        ExpirationReasonCode.NO_ACCEPTED_OCCUPANCY_TRANSITION,
    )


def _next_day_schedule_start(
    at_utc: datetime,
    *,
    document: ScheduleDocument,
    zone_id: ZoneId,
    profile_id: ScheduleProfileId | None,
) -> ExpirationCalculation:
    zone = ZoneInfo(document.time_zone)
    zone_set = document.zones.get(zone_id)
    if zone_set is None or not zone_set.enabled:
        raise ValueError("zone schedule is missing or disabled")
    selected = profile_id or zone_set.selected_profile_id
    profile = next(
        (item for item in zone_set.profiles if item.profile_id == selected),
        None,
    )
    if profile is None or not profile.enabled:
        raise ValueError("schedule profile is missing or disabled")
    next_date = at_utc.astimezone(zone).date() + timedelta(days=1)
    periods = profile.days[WEEKDAYS[next_date.weekday()]]
    if periods:
        boundary = resolve_local_boundary(
            next_date,
            periods[0].local_start,
            time_zone=document.time_zone,
        )
        key = f"{zone_id}:{profile.profile_id}:{periods[0].period_id}:{next_date}"
        return _result(
            boundary,
            key,
            ExpirationReasonCode.NEXT_DAY_SCHEDULE_BOUNDARY,
        )
    midnight = resolve_local_boundary(
        next_date,
        LocalTime(0, 0),
        time_zone=document.time_zone,
    )
    return _result(
        midnight,
        None,
        ExpirationReasonCode.NEXT_DAY_MIDNIGHT_FALLBACK,
    )


def _schedule_inputs(
    inputs: OverrideExpirationInputs,
) -> tuple[ScheduleDocument, ZoneId, ScheduleProfileId | None]:
    if inputs.schedule_document is None or inputs.zone_id is None:
        raise ValueError("schedule_document and zone_id are required")
    if inputs.schedule_document.time_zone != inputs.time_zone:
        raise ValueError("schedule and expiration time zones must match")
    return inputs.schedule_document, inputs.zone_id, inputs.profile_id


def _result(
    deadline: datetime | None,
    key: str | None,
    code: ExpirationReasonCode,
) -> ExpirationCalculation:
    explanations = {
        ExpirationReasonCode.NEXT_MATERIAL_SCHEDULE_TRANSITION: (
            "Expires at the next effective scheduled target change."
        ),
        ExpirationReasonCode.NO_MATERIAL_SCHEDULE_TRANSITION: (
            "No future effective scheduled target change is currently available."
        ),
        ExpirationReasonCode.DURATION_ELAPSED: (
            "Expires when the selected duration has elapsed."
        ),
        ExpirationReasonCode.NEXT_ACCEPTED_OCCUPANCY_TRANSITION: (
            "Expires at the next accepted occupancy-mode change."
        ),
        ExpirationReasonCode.NO_ACCEPTED_OCCUPANCY_TRANSITION: (
            "No accepted future occupancy-mode change is currently available."
        ),
        ExpirationReasonCode.SPECIFIED_LOCAL_TIME: (
            "Expires at the next occurrence of the selected local time."
        ),
        ExpirationReasonCode.MANUAL_CANCELLATION_REQUIRED: (
            "Remains active until it is manually cancelled."
        ),
        ExpirationReasonCode.NEXT_DAY_SCHEDULE_BOUNDARY: (
            "Expires when the next local day schedule begins."
        ),
        ExpirationReasonCode.NEXT_DAY_MIDNIGHT_FALLBACK: (
            "Expires at next local midnight because the next day has no boundary."
        ),
    }
    return ExpirationCalculation(
        expires_at_utc=deadline,
        anchor_transition_key=key,
        reason_code=code,
        explanation=explanations[code],
    )


def _utc(value: datetime, path: str) -> datetime:
    try:
        normalized = normalize_aware_instant(value)
    except ValueError as err:
        raise ValueError(f"{path} must be timezone-aware") from err
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError(f"{path} must be expressed in UTC")
    return normalized


def _zone(value: str) -> None:
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError) as err:
        raise ValueError("time_zone is invalid") from err
