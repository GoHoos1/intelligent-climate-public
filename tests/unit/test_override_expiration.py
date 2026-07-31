"""Deterministic matrix for every Task 10 override-expiration policy."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from zoneinfo import ZoneInfo

import pytest

from custom_components.intelligent_climate.models.identifiers import (
    EquipmentGroupId,
    SchedulePeriodId,
    ScheduleProfileId,
    ZoneId,
)
from custom_components.intelligent_climate.models.override import (
    OverrideExpirationKind,
    OverrideExpirationPolicy,
)
from custom_components.intelligent_climate.models.schedule import (
    SCHEDULE_SCHEMA_VERSION,
    WEEKDAYS,
    LocalTime,
    ScheduleDocument,
    ScheduleOccupancyLabel,
    SchedulePeriod,
    TargetKind,
    TargetSpec,
    Weekday,
    WeeklyScheduleProfile,
    ZoneScheduleSet,
)
from custom_components.intelligent_climate.override.expiration import (
    EffectiveScheduleTransition,
    ExpirationReasonCode,
    OccupancyTransition,
    OccupancyTransitionKind,
    OverrideExpirationInputs,
    calculate_override_expiration,
)

ZONE_ID = ZoneId.parse("10000000-0000-4000-8000-000000000001")
PROFILE_ID = ScheduleProfileId.parse("20000000-0000-4000-8000-000000000001")
GROUP_ID = EquipmentGroupId.parse("30000000-0000-4000-8000-000000000001")


def _target(value: float) -> TargetSpec:
    return TargetSpec(
        kind=TargetKind.SINGLE,
        target_c=value,
        heat_target_c=None,
        cool_target_c=None,
    )


def _period(identifier: int, start: str, target: float) -> SchedulePeriod:
    return SchedulePeriod(
        period_id=SchedulePeriodId.parse(f"40000000-0000-4000-8000-{identifier:012d}"),
        local_start=LocalTime.parse(start),
        label="",
        occupancy_label=ScheduleOccupancyLabel.NONE,
        target=_target(target),
        tolerance_c=0.3,
    )


def _document(
    days: dict[Weekday, tuple[SchedulePeriod, ...]],
    *,
    time_zone: str = "UTC",
) -> ScheduleDocument:
    profile = WeeklyScheduleProfile(
        profile_id=PROFILE_ID,
        name="Normal",
        enabled=True,
        days={weekday: days.get(weekday, ()) for weekday in WEEKDAYS},
    )
    return ScheduleDocument(
        schedule_schema_version=SCHEDULE_SCHEMA_VERSION,
        entry_id="entry-1",
        equipment_group_id=GROUP_ID,
        time_zone=time_zone,
        revision=1,
        zones={
            ZONE_ID: ZoneScheduleSet(
                zone_id=ZONE_ID,
                enabled=True,
                selected_profile_id=PROFILE_ID,
                profiles=(profile,),
            )
        },
        saved_at_utc=datetime(2026, 7, 30, tzinfo=UTC),
    )


def _inputs(
    at: datetime,
    *,
    time_zone: str = "UTC",
    document: ScheduleDocument | None = None,
    **changes: Any,
) -> OverrideExpirationInputs:
    return OverrideExpirationInputs(
        at_utc=at,
        time_zone=time_zone,
        schedule_document=document,
        zone_id=ZONE_ID if document is not None else None,
        **changes,
    )


def test_duration_uses_only_injected_clock_and_stores_one_utc_deadline() -> None:
    at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    result = calculate_override_expiration(
        OverrideExpirationPolicy(
            OverrideExpirationKind.DURATION,
            duration_seconds=90 * 60,
        ),
        inputs=_inputs(at),
    )

    assert result.expires_at_utc == datetime(2026, 7, 30, 13, 30, tzinfo=UTC)
    assert result.anchor_transition_key is None
    assert result.reason_code is ExpirationReasonCode.DURATION_ELAPSED


def test_next_material_transition_skips_same_target_boundaries() -> None:
    morning = _period(1, "06:00", 20.0)
    relabel = _period(2, "12:00", 20.0)
    evening = _period(3, "18:00", 22.0)
    document = _document({Weekday.MONDAY: (morning, relabel, evening)})

    result = calculate_override_expiration(
        OverrideExpirationPolicy(
            OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
        ),
        inputs=_inputs(
            datetime(2026, 7, 27, 8, tzinfo=UTC),
            document=document,
        ),
    )

    assert result.expires_at_utc == datetime(2026, 7, 27, 18, tzinfo=UTC)
    assert result.reason_code is (
        ExpirationReasonCode.NEXT_MATERIAL_SCHEDULE_TRANSITION
    )


def test_next_material_transition_wraps_circular_week_and_empty_days() -> None:
    sunday = _period(1, "22:00", 19.0)
    friday = _period(2, "07:00", 21.0)
    document = _document(
        {
            Weekday.SUNDAY: (sunday,),
            Weekday.FRIDAY: (friday,),
        }
    )

    result = calculate_override_expiration(
        OverrideExpirationPolicy(
            OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
        ),
        inputs=_inputs(
            datetime(2026, 7, 26, 23, tzinfo=UTC),
            document=document,
        ),
    )

    assert result.expires_at_utc == datetime(2026, 7, 31, 7, tzinfo=UTC)


def test_constant_circular_schedule_returns_unresolved_not_false_expiry() -> None:
    document = _document(
        {
            Weekday.MONDAY: (_period(1, "06:00", 20.0),),
            Weekday.FRIDAY: (_period(2, "18:00", 20.0),),
        }
    )

    result = calculate_override_expiration(
        OverrideExpirationPolicy(
            OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
        ),
        inputs=_inputs(
            datetime(2026, 7, 27, 8, tzinfo=UTC),
            document=document,
        ),
    )

    assert result.expires_at_utc is None
    assert result.reason_code is (ExpirationReasonCode.NO_MATERIAL_SCHEDULE_TRANSITION)


def test_occupancy_adjusted_materiality_uses_final_same_instant_target() -> None:
    at = datetime(2026, 3, 8, 6, 30, tzinfo=UTC)
    gap = datetime(2026, 3, 8, 7, tzinfo=UTC)
    later = datetime(2026, 3, 8, 8, tzinfo=UTC)
    transitions = (
        EffectiveScheduleTransition(gap, _target(20.0), "gap-first"),
        EffectiveScheduleTransition(gap, _target(20.0), "gap-final-same"),
        EffectiveScheduleTransition(later, _target(21.0), "later-change"),
    )

    result = calculate_override_expiration(
        OverrideExpirationPolicy(
            OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
        ),
        inputs=_inputs(
            at,
            current_effective_target=_target(20.0),
            effective_schedule_transitions=transitions,
        ),
    )

    assert result.expires_at_utc == later
    assert result.anchor_transition_key == "later-change"


def test_occupancy_adjusted_target_can_make_base_boundary_material() -> None:
    at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    transition = EffectiveScheduleTransition(
        at + timedelta(hours=1),
        _target(18.0),
        "occupancy-adjusted",
    )

    result = calculate_override_expiration(
        OverrideExpirationPolicy(
            OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
        ),
        inputs=_inputs(
            at,
            current_effective_target=_target(20.0),
            effective_schedule_transitions=(transition,),
        ),
    )

    assert result.expires_at_utc == transition.occurs_at_utc
    assert result.anchor_transition_key == "occupancy-adjusted"


def test_next_occupancy_transition_ignores_startup_bounce_and_same_mode() -> None:
    at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    transitions = (
        OccupancyTransition(
            at + timedelta(minutes=1),
            OccupancyTransitionKind.STARTUP_RESOLUTION,
            "unknown",
            "home",
        ),
        OccupancyTransition(
            at + timedelta(minutes=2),
            OccupancyTransitionKind.SOURCE_BOUNCE,
            "home",
            "away",
        ),
        OccupancyTransition(
            at + timedelta(minutes=3),
            OccupancyTransitionKind.ACCEPTED_DEBOUNCED_CHANGE,
            "home",
            "home",
        ),
        OccupancyTransition(
            at + timedelta(minutes=4),
            OccupancyTransitionKind.ACCEPTED_DEBOUNCED_CHANGE,
            "home",
            "away",
        ),
    )

    result = calculate_override_expiration(
        OverrideExpirationPolicy(OverrideExpirationKind.NEXT_OCCUPANCY_TRANSITION),
        inputs=_inputs(at, occupancy_transitions=transitions),
    )

    assert result.expires_at_utc == at + timedelta(minutes=4)
    assert result.reason_code is (
        ExpirationReasonCode.NEXT_ACCEPTED_OCCUPANCY_TRANSITION
    )


def test_no_accepted_occupancy_transition_is_restart_safe_unresolved() -> None:
    at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    result = calculate_override_expiration(
        OverrideExpirationPolicy(OverrideExpirationKind.NEXT_OCCUPANCY_TRANSITION),
        inputs=_inputs(at),
    )

    assert result.expires_at_utc is None
    assert result.reason_code is (ExpirationReasonCode.NO_ACCEPTED_OCCUPANCY_TRANSITION)


def test_specified_clock_time_uses_next_day_when_exact_boundary_passed() -> None:
    policy = OverrideExpirationPolicy(
        OverrideExpirationKind.SPECIFIED_LOCAL_TIME,
        local_time=LocalTime(8, 0),
    )

    exact = calculate_override_expiration(
        policy,
        inputs=_inputs(datetime(2026, 7, 30, 8, tzinfo=UTC)),
    )
    before = calculate_override_expiration(
        policy,
        inputs=_inputs(datetime(2026, 7, 30, 7, 59, tzinfo=UTC)),
    )

    assert exact.expires_at_utc == datetime(2026, 7, 31, 8, tzinfo=UTC)
    assert before.expires_at_utc == datetime(2026, 7, 30, 8, tzinfo=UTC)


def test_specified_clock_time_resolves_spring_gap_once() -> None:
    result = calculate_override_expiration(
        OverrideExpirationPolicy(
            OverrideExpirationKind.SPECIFIED_LOCAL_TIME,
            local_time=LocalTime(2, 30),
        ),
        inputs=_inputs(
            datetime(2026, 3, 8, 5, tzinfo=UTC),
            time_zone="America/New_York",
        ),
    )

    assert result.expires_at_utc == datetime(2026, 3, 8, 7, tzinfo=UTC)


def test_specified_clock_time_fall_fold_uses_first_occurrence_only() -> None:
    policy = OverrideExpirationPolicy(
        OverrideExpirationKind.SPECIFIED_LOCAL_TIME,
        local_time=LocalTime(1, 30),
    )
    before = calculate_override_expiration(
        policy,
        inputs=_inputs(
            datetime(2026, 11, 1, 4, 30, tzinfo=UTC),
            time_zone="America/New_York",
        ),
    )
    between_folds = calculate_override_expiration(
        policy,
        inputs=_inputs(
            datetime(2026, 11, 1, 6, 0, tzinfo=UTC),
            time_zone="America/New_York",
        ),
    )

    assert before.expires_at_utc == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert before.expires_at_utc.astimezone(ZoneInfo("America/New_York")).fold == 0
    assert between_folds.expires_at_utc == datetime(
        2026,
        11,
        2,
        6,
        30,
        tzinfo=UTC,
    )


def test_manual_cancellation_has_no_automatic_deadline() -> None:
    result = calculate_override_expiration(
        OverrideExpirationPolicy(OverrideExpirationKind.MANUAL_CANCELLATION),
        inputs=_inputs(datetime(2026, 7, 30, 12, tzinfo=UTC)),
    )

    assert result.expires_at_utc is None
    assert result.reason_code is (ExpirationReasonCode.MANUAL_CANCELLATION_REQUIRED)


def test_next_day_schedule_uses_first_configured_boundary() -> None:
    document = _document(
        {
            Weekday.FRIDAY: (
                _period(1, "06:30", 20.0),
                _period(2, "18:00", 22.0),
            )
        }
    )

    result = calculate_override_expiration(
        OverrideExpirationPolicy(OverrideExpirationKind.NEXT_DAY_SCHEDULE_START),
        inputs=_inputs(
            datetime(2026, 7, 30, 12, tzinfo=UTC),
            document=document,
        ),
    )

    assert result.expires_at_utc == datetime(2026, 7, 31, 6, 30, tzinfo=UTC)
    assert result.reason_code is (ExpirationReasonCode.NEXT_DAY_SCHEDULE_BOUNDARY)


def test_next_day_empty_schedule_uses_local_midnight_fallback() -> None:
    document = _document(
        {Weekday.THURSDAY: (_period(1, "06:30", 20.0),)},
        time_zone="America/New_York",
    )

    result = calculate_override_expiration(
        OverrideExpirationPolicy(OverrideExpirationKind.NEXT_DAY_SCHEDULE_START),
        inputs=_inputs(
            datetime(2026, 7, 30, 16, tzinfo=UTC),
            time_zone="America/New_York",
            document=document,
        ),
    )

    assert result.expires_at_utc == datetime(2026, 7, 31, 4, tzinfo=UTC)
    assert result.reason_code is (ExpirationReasonCode.NEXT_DAY_MIDNIGHT_FALLBACK)


@pytest.mark.parametrize(
    ("inputs", "message"),
    [
        (
            OverrideExpirationInputs(
                at_utc=datetime(2026, 7, 30, 12),
                time_zone="UTC",
            ),
            "timezone-aware",
        ),
        (
            OverrideExpirationInputs(
                at_utc=datetime(2026, 7, 30, 12, tzinfo=UTC),
                time_zone="Invalid/Zone",
            ),
            "invalid",
        ),
        (
            OverrideExpirationInputs(
                at_utc=datetime(2026, 7, 30, 12, tzinfo=UTC),
                time_zone="UTC",
                effective_schedule_transitions=(
                    EffectiveScheduleTransition(
                        datetime(2026, 7, 30, 13, tzinfo=UTC),
                        _target(21.0),
                        "key",
                    ),
                ),
            ),
            "current_effective_target",
        ),
    ],
)
def test_malformed_or_incomplete_inputs_fail_closed(
    inputs: OverrideExpirationInputs,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        calculate_override_expiration(
            OverrideExpirationPolicy(
                OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
            ),
            inputs=inputs,
        )


def test_stale_reordered_and_duplicate_occupancy_inputs_are_rejected() -> None:
    at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    duplicate = (
        OccupancyTransition(
            at + timedelta(minutes=2),
            OccupancyTransitionKind.SOURCE_BOUNCE,
            "home",
            "away",
        ),
        OccupancyTransition(
            at + timedelta(minutes=2),
            OccupancyTransitionKind.ACCEPTED_DEBOUNCED_CHANGE,
            "home",
            "away",
        ),
    )
    with pytest.raises(ValueError, match="strictly ordered"):
        calculate_override_expiration(
            OverrideExpirationPolicy(OverrideExpirationKind.NEXT_OCCUPANCY_TRANSITION),
            inputs=_inputs(at, occupancy_transitions=duplicate),
        )


def test_restart_reevaluation_returns_identical_deadline_and_reason() -> None:
    document = _document(
        {
            Weekday.THURSDAY: (_period(1, "06:00", 20.0),),
            Weekday.FRIDAY: (_period(2, "06:00", 22.0),),
        }
    )
    inputs = _inputs(
        datetime(2026, 7, 30, 12, tzinfo=UTC),
        document=document,
    )
    policy = OverrideExpirationPolicy(
        OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
    )

    assert calculate_override_expiration(
        policy,
        inputs=inputs,
    ) == calculate_override_expiration(policy, inputs=inputs)


def test_effective_transition_input_validation_matrix() -> None:
    at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    valid = EffectiveScheduleTransition(
        at + timedelta(hours=2),
        _target(20.0),
        "valid",
    )
    cases = (
        (
            EffectiveScheduleTransition(at, _target(20.0), "stale"),
            valid,
        ),
        (
            valid,
            EffectiveScheduleTransition(
                at + timedelta(hours=1),
                _target(21.0),
                "reordered",
            ),
        ),
        (
            EffectiveScheduleTransition(
                at + timedelta(hours=1),
                _target(21.0),
                "",
            ),
        ),
    )
    policy = OverrideExpirationPolicy(
        OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
    )
    for transitions in cases:
        with pytest.raises(ValueError):
            calculate_override_expiration(
                policy,
                inputs=_inputs(
                    at,
                    current_effective_target=_target(20.0),
                    effective_schedule_transitions=transitions,
                ),
            )

    no_change = calculate_override_expiration(
        policy,
        inputs=_inputs(
            at,
            current_effective_target=_target(20.0),
            effective_schedule_transitions=(valid,),
        ),
    )
    assert no_change.reason_code is (
        ExpirationReasonCode.NO_MATERIAL_SCHEDULE_TRANSITION
    )


def test_occupancy_input_validation_matrix() -> None:
    at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    invalid = (
        OccupancyTransition(
            at,
            OccupancyTransitionKind.ACCEPTED_DEBOUNCED_CHANGE,
            "home",
            "away",
        ),
        OccupancyTransition(
            at + timedelta(minutes=1),
            cast(Any, "unsupported"),
            "home",
            "away",
        ),
        OccupancyTransition(
            at + timedelta(minutes=1),
            OccupancyTransitionKind.ACCEPTED_DEBOUNCED_CHANGE,
            "",
            "away",
        ),
    )
    for transition in invalid:
        with pytest.raises(ValueError):
            calculate_override_expiration(
                OverrideExpirationPolicy(
                    OverrideExpirationKind.NEXT_OCCUPANCY_TRANSITION
                ),
                inputs=_inputs(at, occupancy_transitions=(transition,)),
            )


def test_schedule_failure_and_required_input_branches() -> None:
    at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    policy = OverrideExpirationPolicy(
        OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
    )
    with pytest.raises(ValueError, match="required"):
        calculate_override_expiration(policy, inputs=_inputs(at))

    utc_document = _document({Weekday.THURSDAY: (_period(1, "06:00", 20.0),)})
    with pytest.raises(ValueError, match="must match"):
        calculate_override_expiration(
            policy,
            inputs=_inputs(
                at,
                time_zone="America/New_York",
                document=utc_document,
            ),
        )
    disabled_zone = replace(
        utc_document.zones[ZONE_ID],
        enabled=False,
    )
    disabled = replace(utc_document, zones={ZONE_ID: disabled_zone})
    with pytest.raises(ValueError, match="disabled"):
        calculate_override_expiration(
            policy,
            inputs=_inputs(at, document=disabled),
        )


def test_next_day_schedule_validation_branches() -> None:
    at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    policy = OverrideExpirationPolicy(OverrideExpirationKind.NEXT_DAY_SCHEDULE_START)
    document = _document({Weekday.FRIDAY: (_period(1, "06:00", 20.0),)})
    foreign_zone = ZoneId.new()
    with pytest.raises(ValueError, match="missing or disabled"):
        calculate_override_expiration(
            policy,
            inputs=OverrideExpirationInputs(
                at_utc=at,
                time_zone="UTC",
                schedule_document=document,
                zone_id=foreign_zone,
            ),
        )
    with pytest.raises(ValueError, match="profile"):
        calculate_override_expiration(
            policy,
            inputs=OverrideExpirationInputs(
                at_utc=at,
                time_zone="UTC",
                schedule_document=document,
                zone_id=ZONE_ID,
                profile_id=ScheduleProfileId.new(),
            ),
        )
    invalid_zone_document = replace(document, time_zone="Invalid/Zone")
    with pytest.raises(ValueError, match="invalid"):
        calculate_override_expiration(
            policy,
            inputs=OverrideExpirationInputs(
                at_utc=at,
                time_zone="Invalid/Zone",
                schedule_document=invalid_zone_document,
                zone_id=ZONE_ID,
            ),
        )


def test_non_utc_transition_timestamp_is_rejected() -> None:
    local = ZoneInfo("America/New_York")
    at = datetime(2026, 7, 30, 12, tzinfo=UTC)
    transition = EffectiveScheduleTransition(
        datetime(2026, 7, 30, 9, tzinfo=local),
        _target(21.0),
        "local",
    )
    with pytest.raises(ValueError, match="expressed in UTC"):
        calculate_override_expiration(
            OverrideExpirationPolicy(
                OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
            ),
            inputs=_inputs(
                at,
                current_effective_target=_target(20.0),
                effective_schedule_transitions=(transition,),
            ),
        )
