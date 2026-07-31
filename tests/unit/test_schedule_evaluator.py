"""Test the pure circular schedule evaluator added by Phase 2 Task 4."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from custom_components.intelligent_climate.models import (
    SCHEDULE_SCHEMA_VERSION,
    WEEKDAYS,
    ControlReason,
    EquipmentGroupId,
    LocalTime,
    ScheduleDocument,
    ScheduleOccupancyLabel,
    SchedulePeriod,
    SchedulePeriodId,
    ScheduleProfileId,
    TargetKind,
    TargetSpec,
    Weekday,
    WeeklyScheduleProfile,
    ZoneId,
    ZoneScheduleSet,
)
from custom_components.intelligent_climate.schedule import (
    ScheduleEvaluationError,
    evaluate_schedule,
    locate_circular_schedule,
)
from custom_components.intelligent_climate.schedule.time import (
    normalize_aware_instant,
    resolve_local_boundary,
)

ROOT = Path(__file__).parents[2]
INTEGRATION_DIR = ROOT / "custom_components" / "intelligent_climate"

ZONE_ID = ZoneId.parse("10000000-0000-4000-8000-000000000001")
OTHER_ZONE_ID = ZoneId.parse("10000000-0000-4000-8000-000000000002")
PROFILE_ID = ScheduleProfileId.parse("20000000-0000-4000-8000-000000000001")
OTHER_PROFILE_ID = ScheduleProfileId.parse("20000000-0000-4000-8000-000000000002")
GROUP_ID = EquipmentGroupId.parse("30000000-0000-4000-8000-000000000001")


def _target(value: float) -> TargetSpec:
    return TargetSpec(
        kind=TargetKind.SINGLE,
        target_c=value,
        heat_target_c=None,
        cool_target_c=None,
    )


def _range_target(heat: float, cool: float) -> TargetSpec:
    return TargetSpec(
        kind=TargetKind.RANGE,
        target_c=None,
        heat_target_c=heat,
        cool_target_c=cool,
    )


def _period(
    identifier: int,
    start: str,
    target: TargetSpec,
    *,
    label: str = "",
    tolerance_c: float = 0.3,
) -> SchedulePeriod:
    return SchedulePeriod(
        period_id=SchedulePeriodId.parse(f"40000000-0000-4000-8000-{identifier:012d}"),
        local_start=LocalTime.parse(start),
        label=label,
        occupancy_label=ScheduleOccupancyLabel.NONE,
        target=target,
        tolerance_c=tolerance_c,
    )


def _profile(
    days: dict[Weekday, tuple[SchedulePeriod, ...]],
    *,
    profile_id: ScheduleProfileId = PROFILE_ID,
    enabled: bool = True,
) -> WeeklyScheduleProfile:
    return WeeklyScheduleProfile(
        profile_id=profile_id,
        name=f"Profile {str(profile_id)[-1]}",
        enabled=enabled,
        days={weekday: days.get(weekday, ()) for weekday in WEEKDAYS},
    )


def _document(
    profiles: tuple[WeeklyScheduleProfile, ...],
    *,
    selected_profile_id: ScheduleProfileId = PROFILE_ID,
    zone_enabled: bool = True,
    time_zone: str = "UTC",
) -> ScheduleDocument:
    zone = ZoneScheduleSet(
        zone_id=ZONE_ID,
        enabled=zone_enabled,
        selected_profile_id=selected_profile_id,
        profiles=profiles,
    )
    return ScheduleDocument(
        schedule_schema_version=SCHEDULE_SCHEMA_VERSION,
        entry_id="entry-1",
        equipment_group_id=GROUP_ID,
        time_zone=time_zone,
        revision=1,
        zones={ZONE_ID: zone},
        saved_at_utc=datetime(2026, 7, 30, tzinfo=UTC),
    )


def test_evaluate_current_period_and_next_material_boundary() -> None:
    morning = _period(1, "06:00", _target(20.0), label="Morning")
    evening = _period(2, "18:00", _target(22.0), label="Evening")
    document = _document((_profile({Weekday.MONDAY: (morning, evening)}),))

    result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 7, 27, 12, 34, 56, tzinfo=UTC),
    )

    assert result.zone_id == ZONE_ID
    assert result.profile_id == PROFILE_ID
    assert result.base_period_id == morning.period_id
    assert result.base_target == _target(20.0)
    assert result.effective_target is result.base_target
    assert result.current_local_date.isoformat() == "2026-07-27"
    assert result.current_local_time.isoformat() == "12:34:56"
    assert result.current_local_fold == 0
    assert result.inherited_from_previous_day is False
    assert result.next_boundary_utc == datetime(2026, 7, 27, 18, tzinfo=UTC)
    assert result.next_material_transition_utc == datetime(
        2026,
        7,
        27,
        18,
        tzinfo=UTC,
    )
    assert result.next_material_target == _target(22.0)
    assert result.reason_code is ControlReason.SCHEDULE_EVALUATION


def test_before_first_period_inherits_across_empty_days() -> None:
    friday = _period(1, "21:00", _target(19.0))
    monday = _period(2, "06:00", _target(21.0))
    document = _document(
        (
            _profile(
                {
                    Weekday.FRIDAY: (friday,),
                    Weekday.MONDAY: (monday,),
                }
            ),
        )
    )

    result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 7, 27, 5, 30, tzinfo=UTC),
    )

    assert result.base_period_id == friday.period_id
    assert result.inherited_from_previous_day is True
    assert result.next_boundary_utc == datetime(2026, 7, 27, 6, tzinfo=UTC)
    assert result.next_material_transition_utc == datetime(
        2026,
        7,
        27,
        6,
        tzinfo=UTC,
    )


def test_label_and_tolerance_only_boundaries_are_not_material() -> None:
    morning = _period(1, "06:00", _target(20.0), label="Morning")
    midday = _period(
        2,
        "12:00",
        _target(20.0),
        label="Still home",
        tolerance_c=0.8,
    )
    evening = _period(3, "18:00", _target(22.0), label="Evening")
    document = _document((_profile({Weekday.MONDAY: (morning, midday, evening)}),))

    result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 7, 27, 7, tzinfo=UTC),
    )

    assert result.next_boundary_utc == datetime(2026, 7, 27, 12, tzinfo=UTC)
    assert result.next_material_transition_utc == datetime(
        2026,
        7,
        27,
        18,
        tzinfo=UTC,
    )
    assert result.next_material_target == evening.target


def test_boundary_at_evaluation_instant_is_already_active() -> None:
    morning = _period(1, "06:00", _target(20.0))
    evening = _period(2, "18:00", _target(22.0))
    document = _document((_profile({Weekday.MONDAY: (morning, evening)}),))

    result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 7, 27, 18, tzinfo=UTC),
    )

    assert result.base_period_id == evening.period_id
    assert result.next_boundary_utc == datetime(2026, 8, 3, 6, tzinfo=UTC)
    assert result.next_material_transition_utc == datetime(
        2026,
        8,
        3,
        6,
        tzinfo=UTC,
    )
    assert result.next_material_target == morning.target


def test_one_repeating_target_has_no_material_transition() -> None:
    monday = _period(1, "06:00", _target(20.0))
    thursday = _period(2, "09:00", _target(20.0), label="Same target")
    document = _document(
        (
            _profile(
                {
                    Weekday.MONDAY: (monday,),
                    Weekday.THURSDAY: (thursday,),
                }
            ),
        )
    )

    result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 7, 27, 7, tzinfo=UTC),
    )

    assert result.next_boundary_utc == datetime(2026, 7, 30, 9, tzinfo=UTC)
    assert result.next_material_transition_utc is None
    assert result.next_material_target is None


def test_range_targets_are_compared_as_the_complete_controlled_value() -> None:
    first = _period(1, "06:00", _range_target(19.0, 24.0))
    same = _period(2, "12:00", _range_target(19.0, 24.0))
    changed = _period(3, "18:00", _range_target(18.0, 25.0))
    document = _document((_profile({Weekday.MONDAY: (first, same, changed)}),))

    result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 7, 27, 8, tzinfo=UTC),
    )

    assert result.next_boundary_utc == datetime(2026, 7, 27, 12, tzinfo=UTC)
    assert result.next_material_transition_utc == datetime(
        2026,
        7,
        27,
        18,
        tzinfo=UTC,
    )
    assert result.next_material_target == changed.target


def test_explicit_enabled_profile_selection_overrides_zone_default() -> None:
    normal = _profile({Weekday.MONDAY: (_period(1, "00:00", _target(20.0)),)})
    vacation_period = _period(2, "00:00", _target(17.0))
    vacation = _profile(
        {Weekday.MONDAY: (vacation_period,)},
        profile_id=OTHER_PROFILE_ID,
    )
    document = _document((normal, vacation))

    result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        profile_id=OTHER_PROFILE_ID,
        at=datetime(2026, 7, 27, 12, tzinfo=UTC),
    )

    assert result.profile_id == OTHER_PROFILE_ID
    assert result.base_period_id == vacation_period.period_id
    assert result.base_target == _target(17.0)


def test_local_display_fields_use_schedule_timezone_but_deadlines_use_utc() -> None:
    morning = _period(1, "08:00", _target(20.0))
    evening = _period(2, "18:00", _target(22.0))
    document = _document(
        (_profile({Weekday.MONDAY: (morning, evening)}),),
        time_zone="America/New_York",
    )

    result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(
            2026,
            7,
            27,
            12,
            30,
            tzinfo=ZoneInfo("Europe/London"),
        ),
    )

    assert result.current_local_time.isoformat() == "07:30:00"
    assert result.base_period_id != morning.period_id
    assert result.inherited_from_previous_day is True
    assert result.next_boundary_utc == datetime(2026, 7, 27, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    ("zone_enabled", "zone_id", "profile_id", "message"),
    [
        (True, OTHER_ZONE_ID, None, "zone is not present"),
        (False, ZONE_ID, None, "zone schedule is disabled"),
        (True, ZONE_ID, OTHER_PROFILE_ID, "profile is not present"),
    ],
)
def test_evaluator_rejects_ineligible_zone_or_profile(
    zone_enabled: bool,
    zone_id: ZoneId,
    profile_id: ScheduleProfileId | None,
    message: str,
) -> None:
    profile = _profile({Weekday.MONDAY: (_period(1, "06:00", _target(20.0)),)})
    document = _document((profile,), zone_enabled=zone_enabled)

    with pytest.raises(ScheduleEvaluationError, match=message):
        evaluate_schedule(
            document,
            zone_id=zone_id,
            profile_id=profile_id,
            at=datetime(2026, 7, 27, 12, tzinfo=UTC),
        )


def test_evaluator_rejects_disabled_or_empty_profile_and_invalid_timezone() -> None:
    period = _period(1, "06:00", _target(20.0))
    disabled = _profile({Weekday.MONDAY: (period,)}, enabled=False)
    with pytest.raises(ScheduleEvaluationError, match="profile is disabled"):
        evaluate_schedule(
            _document((disabled,)),
            zone_id=ZONE_ID,
            at=datetime(2026, 7, 27, 12, tzinfo=UTC),
        )

    empty = _profile({})
    with pytest.raises(ScheduleEvaluationError, match="no weekly periods"):
        evaluate_schedule(
            _document((empty,)),
            zone_id=ZONE_ID,
            at=datetime(2026, 7, 27, 12, tzinfo=UTC),
        )

    with pytest.raises(ScheduleEvaluationError, match="time zone is invalid"):
        evaluate_schedule(
            _document((_profile({Weekday.MONDAY: (period,)}),), time_zone="Bad/Zone"),
            zone_id=ZONE_ID,
            at=datetime(2026, 7, 27, 12, tzinfo=UTC),
        )


def test_clock_boundary_rejects_naive_instants_and_invalid_zone() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        normalize_aware_instant(datetime(2026, 7, 27, 12))

    document = _document(
        (_profile({Weekday.MONDAY: (_period(1, "12:00", _target(20.0)),)}),)
    )
    with pytest.raises(ScheduleEvaluationError, match="timezone-aware"):
        evaluate_schedule(
            document,
            zone_id=ZONE_ID,
            at=datetime(2026, 7, 27, 12),
        )

    with pytest.raises(ValueError, match="time zone is invalid"):
        resolve_local_boundary(
            datetime(2026, 7, 27).date(),
            LocalTime.parse("12:00"),
            time_zone="Bad/Zone",
        )

    profile = _profile({Weekday.MONDAY: (_period(1, "12:00", _target(20.0)),)})
    with pytest.raises(ValueError, match="time zone is invalid"):
        locate_circular_schedule(
            profile,
            time_zone="Bad/Zone",
            at=datetime(2026, 7, 27, 12, tzinfo=UTC),
        )


def test_nonexistent_boundary_moves_to_first_valid_minute_after_gap() -> None:
    """Task 4 implements the policy; Task 5 supplies its exhaustive matrix."""
    resolved = resolve_local_boundary(
        datetime(2026, 3, 8).date(),
        LocalTime.parse("02:30"),
        time_zone="America/New_York",
    )

    assert resolved == datetime(2026, 3, 8, 7, tzinfo=UTC)


def test_position_calculator_is_deterministic_and_has_no_side_effects() -> None:
    period = _period(1, "06:00", _target(20.0))
    profile = _profile({Weekday.MONDAY: (period,)})
    first = locate_circular_schedule(
        profile,
        time_zone="UTC",
        at=datetime(2026, 7, 27, 12, tzinfo=UTC),
    )
    second = locate_circular_schedule(
        profile,
        time_zone="UTC",
        at=datetime(2026, 7, 27, 12, tzinfo=UTC),
    )

    assert first == second
    assert first.active_boundary.period is period
    assert first.next_boundary.local_date.isoformat() == "2026-08-03"
    assert first.next_material_boundary is None


def test_task_4_evaluator_is_pure_and_unwired() -> None:
    """The evaluator cannot read clocks, schedule work, persist, or command."""
    schedule_sources = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (INTEGRATION_DIR / "schedule").glob("*.py")
    )
    prohibited = {
        "homeassistant",
        "datetime.now",
        "datetime.utcnow",
        "async_call",
        "async_track",
        "asyncio",
        "Coordinator",
        "Store(",
        "async_save",
        "CommandSink",
        "command_adapter",
    }

    assert all(term not in schedule_sources for term in prohibited)
    assert "intelligent_climate.schedule" not in (
        INTEGRATION_DIR / "coordinator.py"
    ).read_text(encoding="utf-8")
    assert "schedule_storage" not in (INTEGRATION_DIR / "coordinator.py").read_text(
        encoding="utf-8"
    )


def test_hand_constructed_document_does_not_mutate_during_evaluation() -> None:
    period = _period(1, "06:00", _target(20.0))
    profile = _profile({Weekday.MONDAY: (period,)})
    document = _document((profile,))
    original = replace(document)

    evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 7, 27, 12, tzinfo=UTC),
    )

    assert document == original
