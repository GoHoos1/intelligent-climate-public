"""Test the Task 5 schedule clock, DST, and circular-week matrix."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.intelligent_climate.models import (
    SCHEDULE_SCHEMA_VERSION,
    WEEKDAYS,
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
from custom_components.intelligent_climate.schedule import evaluate_schedule
from custom_components.intelligent_climate.schedule.time import resolve_local_boundary

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


def _period(identifier: int, start: str, target_c: float) -> SchedulePeriod:
    return SchedulePeriod(
        period_id=SchedulePeriodId.parse(f"40000000-0000-4000-8000-{identifier:012d}"),
        local_start=LocalTime.parse(start),
        label="",
        occupancy_label=ScheduleOccupancyLabel.NONE,
        target=_target(target_c),
        tolerance_c=0.3,
    )


def _document(
    days: dict[Weekday, tuple[SchedulePeriod, ...]],
    *,
    time_zone: str,
) -> ScheduleDocument:
    profile = WeeklyScheduleProfile(
        profile_id=PROFILE_ID,
        name="Normal",
        enabled=True,
        days={weekday: days.get(weekday, ()) for weekday in WEEKDAYS},
    )
    zone = ZoneScheduleSet(
        zone_id=ZONE_ID,
        enabled=True,
        selected_profile_id=PROFILE_ID,
        profiles=(profile,),
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


@pytest.mark.parametrize(
    ("local_time", "expected"),
    [
        ("01:59", datetime(2026, 3, 8, 6, 59, tzinfo=UTC)),
        ("02:00", datetime(2026, 3, 8, 7, 0, tzinfo=UTC)),
        ("02:10", datetime(2026, 3, 8, 7, 0, tzinfo=UTC)),
        ("02:40", datetime(2026, 3, 8, 7, 0, tzinfo=UTC)),
        ("02:59", datetime(2026, 3, 8, 7, 0, tzinfo=UTC)),
        ("03:00", datetime(2026, 3, 8, 7, 0, tzinfo=UTC)),
    ],
)
def test_new_york_spring_gap_resolves_to_first_valid_instant(
    local_time: str,
    expected: datetime,
) -> None:
    assert (
        resolve_local_boundary(
            datetime(2026, 3, 8).date(),
            LocalTime.parse(local_time),
            time_zone="America/New_York",
        )
        == expected
    )


def test_spring_gap_collapses_skipped_periods_to_final_configured_target() -> None:
    before = _period(1, "01:00", 18.0)
    skipped_first = _period(2, "02:10", 19.0)
    skipped_final = _period(3, "02:40", 20.0)
    after = _period(4, "04:00", 21.0)
    document = _document(
        {
            Weekday.SUNDAY: (
                before,
                skipped_first,
                skipped_final,
                after,
            )
        },
        time_zone="America/New_York",
    )

    before_gap = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 3, 8, 6, 30, tzinfo=UTC),
    )
    at_gap_resolution = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 3, 8, 7, 0, tzinfo=UTC),
    )

    assert before_gap.base_period_id == before.period_id
    assert before_gap.next_boundary_utc == datetime(2026, 3, 8, 7, tzinfo=UTC)
    assert before_gap.next_material_transition_utc == datetime(
        2026,
        3,
        8,
        7,
        tzinfo=UTC,
    )
    assert before_gap.next_material_target == skipped_final.target
    assert at_gap_resolution.base_period_id == skipped_final.period_id
    assert at_gap_resolution.base_target == skipped_final.target
    assert at_gap_resolution.next_boundary_utc == datetime(
        2026,
        3,
        8,
        8,
        tzinfo=UTC,
    )


def test_new_york_fall_fold_uses_only_first_occurrence() -> None:
    resolved = resolve_local_boundary(
        datetime(2026, 11, 1).date(),
        LocalTime.parse("01:30"),
        time_zone="America/New_York",
    )

    assert resolved == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert resolved.astimezone(ZoneInfo("America/New_York")).fold == 0


def test_second_fall_fold_keeps_target_from_first_occurrence() -> None:
    before = _period(1, "00:30", 18.0)
    folded = _period(2, "01:30", 20.0)
    after = _period(3, "02:30", 21.0)
    document = _document(
        {Weekday.SUNDAY: (before, folded, after)},
        time_zone="America/New_York",
    )

    first_occurrence = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 11, 1, 5, 45, tzinfo=UTC),
    )
    second_occurrence = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 11, 1, 6, 45, tzinfo=UTC),
    )

    assert first_occurrence.current_local_fold == 0
    assert second_occurrence.current_local_fold == 1
    assert first_occurrence.base_period_id == folded.period_id
    assert second_occurrence.base_period_id == folded.period_id
    assert first_occurrence.next_boundary_utc == datetime(
        2026,
        11,
        1,
        7,
        30,
        tzinfo=UTC,
    )
    assert second_occurrence.next_boundary_utc == first_occurrence.next_boundary_utc


def test_midnight_has_no_synthetic_boundary() -> None:
    sunday = _period(1, "22:00", 18.0)
    monday = _period(2, "06:00", 20.0)
    document = _document(
        {
            Weekday.SUNDAY: (sunday,),
            Weekday.MONDAY: (monday,),
        },
        time_zone="UTC",
    )

    result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 7, 27, 0, tzinfo=UTC),
    )

    assert result.base_period_id == sunday.period_id
    assert result.inherited_from_previous_day is True
    assert result.next_boundary_utc == datetime(2026, 7, 27, 6, tzinfo=UTC)


def test_explicit_midnight_period_becomes_active_at_midnight() -> None:
    sunday = _period(1, "22:00", 18.0)
    monday_midnight = _period(2, "00:00", 20.0)
    document = _document(
        {
            Weekday.SUNDAY: (sunday,),
            Weekday.MONDAY: (monday_midnight,),
        },
        time_zone="UTC",
    )

    before = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 7, 26, 23, 59, 59, tzinfo=UTC),
    )
    at_midnight = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 7, 27, 0, tzinfo=UTC),
    )

    assert before.base_period_id == sunday.period_id
    assert before.next_boundary_utc == datetime(2026, 7, 27, 0, tzinfo=UTC)
    assert at_midnight.base_period_id == monday_midnight.period_id
    assert at_midnight.inherited_from_previous_day is False


def test_sunday_wraps_to_monday_and_empty_days_inherit() -> None:
    monday = _period(1, "07:00", 20.0)
    sunday = _period(2, "21:00", 18.0)
    document = _document(
        {
            Weekday.MONDAY: (monday,),
            Weekday.SUNDAY: (sunday,),
        },
        time_zone="UTC",
    )

    sunday_result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 8, 2, 23, tzinfo=UTC),
    )
    monday_result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 8, 3, 6, 59, tzinfo=UTC),
    )
    thursday_result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2026, 8, 6, 12, tzinfo=UTC),
    )

    assert sunday_result.base_period_id == sunday.period_id
    assert sunday_result.next_boundary_utc == datetime(
        2026,
        8,
        3,
        7,
        tzinfo=UTC,
    )
    assert monday_result.base_period_id == sunday.period_id
    assert monday_result.inherited_from_previous_day is True
    assert thursday_result.base_period_id == monday.period_id
    assert thursday_result.inherited_from_previous_day is True


def test_leap_day_uses_its_actual_weekday() -> None:
    monday = _period(1, "08:00", 20.0)
    tuesday = _period(2, "08:00", 21.0)
    document = _document(
        {
            Weekday.MONDAY: (monday,),
            Weekday.TUESDAY: (tuesday,),
        },
        time_zone="UTC",
    )

    result = evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=datetime(2028, 2, 29, 9, tzinfo=UTC),
    )

    assert result.current_local_date.isoformat() == "2028-02-29"
    assert result.base_period_id == tuesday.period_id


@pytest.mark.parametrize(
    ("local_time", "expected"),
    [
        ("01:59", datetime(2026, 10, 3, 15, 29, tzinfo=UTC)),
        ("02:00", datetime(2026, 10, 3, 15, 30, tzinfo=UTC)),
        ("02:15", datetime(2026, 10, 3, 15, 30, tzinfo=UTC)),
        ("02:29", datetime(2026, 10, 3, 15, 30, tzinfo=UTC)),
        ("02:30", datetime(2026, 10, 3, 15, 30, tzinfo=UTC)),
    ],
)
def test_lord_howe_half_hour_spring_gap(
    local_time: str,
    expected: datetime,
) -> None:
    assert (
        resolve_local_boundary(
            datetime(2026, 10, 4).date(),
            LocalTime.parse(local_time),
            time_zone="Australia/Lord_Howe",
        )
        == expected
    )


def test_lord_howe_half_hour_fall_fold_uses_first_occurrence() -> None:
    resolved = resolve_local_boundary(
        datetime(2026, 4, 5).date(),
        LocalTime.parse("01:45"),
        time_zone="Australia/Lord_Howe",
    )

    assert resolved == datetime(2026, 4, 4, 14, 45, tzinfo=UTC)
    assert resolved.astimezone(ZoneInfo("Australia/Lord_Howe")).fold == 0


def test_no_dst_zone_keeps_local_boundaries_stable_across_seasons() -> None:
    winter = resolve_local_boundary(
        datetime(2026, 1, 15).date(),
        LocalTime.parse("08:00"),
        time_zone="Asia/Kolkata",
    )
    summer = resolve_local_boundary(
        datetime(2026, 7, 15).date(),
        LocalTime.parse("08:00"),
        time_zone="Asia/Kolkata",
    )

    assert winter == datetime(2026, 1, 15, 2, 30, tzinfo=UTC)
    assert summer == datetime(2026, 7, 15, 2, 30, tzinfo=UTC)


def test_timezone_change_rerenders_wall_time_without_mutating_document() -> None:
    morning = _period(1, "08:00", 20.0)
    original = _document(
        {Weekday.MONDAY: (morning,)},
        time_zone="America/New_York",
    )
    changed = replace(original, time_zone="America/Los_Angeles")
    evaluation_instant = datetime(2026, 7, 27, 11, 30, tzinfo=UTC)

    eastern = evaluate_schedule(
        original,
        zone_id=ZONE_ID,
        at=evaluation_instant,
    )
    pacific = evaluate_schedule(
        changed,
        zone_id=ZONE_ID,
        at=evaluation_instant,
    )

    assert original.time_zone == "America/New_York"
    assert changed.time_zone == "America/Los_Angeles"
    assert eastern.current_local_time.isoformat() == "07:30:00"
    assert eastern.next_boundary_utc == datetime(2026, 7, 27, 12, tzinfo=UTC)
    assert pacific.current_local_time.isoformat() == "04:30:00"
    assert pacific.next_boundary_utc == datetime(2026, 7, 27, 15, tzinfo=UTC)


def test_evaluation_instant_timezone_does_not_change_schedule_semantics() -> None:
    morning = _period(1, "08:00", 20.0)
    document = _document(
        {Weekday.MONDAY: (morning,)},
        time_zone="America/New_York",
    )
    instant_utc = datetime(2026, 7, 27, 13, tzinfo=UTC)
    instant_tokyo = instant_utc.astimezone(ZoneInfo("Asia/Tokyo"))

    assert evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=instant_utc,
    ) == evaluate_schedule(
        document,
        zone_id=ZONE_ID,
        at=instant_tokyo,
    )
