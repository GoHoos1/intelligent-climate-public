"""Task 23 authoritative schedule preview and DST-warning tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from custom_components.intelligent_climate.models import (
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
from custom_components.intelligent_climate.schedule.evaluate import (
    ScheduleEvaluationError,
)
from custom_components.intelligent_climate.schedule.preview import (
    DstWarningKind,
    build_schedule_preview,
)

ZONE_ID = ZoneId.parse("11111111-1111-4111-8111-111111111111")
PROFILE_ID = ScheduleProfileId.parse("22222222-2222-4222-8222-222222222222")
PERIOD_ID = SchedulePeriodId.parse("33333333-3333-4333-8333-333333333333")


def _document(*, day: Weekday, local_start: str) -> ScheduleDocument:
    days: dict[Weekday, tuple[SchedulePeriod, ...]] = dict.fromkeys(Weekday, ())
    days[day] = (
        SchedulePeriod(
            period_id=PERIOD_ID,
            local_start=LocalTime.parse(local_start),
            label="Comfort",
            occupancy_label=ScheduleOccupancyLabel.HOME,
            target=TargetSpec(
                kind=TargetKind.SINGLE,
                target_c=21.0,
                heat_target_c=None,
                cool_target_c=None,
            ),
            tolerance_c=0.5,
        ),
    )
    profile = WeeklyScheduleProfile(
        profile_id=PROFILE_ID,
        name="Normal",
        enabled=True,
        days=days,
    )
    return ScheduleDocument(
        schedule_schema_version=1,
        entry_id="entry-1",
        equipment_group_id=EquipmentGroupId.parse(
            "44444444-4444-4444-8444-444444444444"
        ),
        time_zone="America/New_York",
        revision=1,
        zones={
            ZONE_ID: ZoneScheduleSet(
                zone_id=ZONE_ID,
                enabled=True,
                selected_profile_id=PROFILE_ID,
                profiles=(profile,),
            )
        },
        saved_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_preview_reports_exact_spring_gap_behavior() -> None:
    preview = build_schedule_preview(
        _document(day=Weekday.SUNDAY, local_start="02:30"),
        at=datetime(2026, 3, 2, 12, tzinfo=UTC),
    )

    assert preview.preview_week_start_local.isoformat() == "2026-03-02"
    assert len(preview.zones) == 1
    assert preview.zones[0].inherited_from_previous_day is True
    assert preview.zones[0].next_target is None
    assert len(preview.dst_warnings) == 1
    warning = preview.dst_warnings[0]
    assert warning.kind is DstWarningKind.GAP
    assert warning.local_date.isoformat() == "2026-03-08"
    assert warning.occurs_at_utc == datetime(2026, 3, 8, 7, tzinfo=UTC)
    assert "first valid local minute, 03:00" in warning.explanation


def test_preview_reports_first_occurrence_for_fall_fold() -> None:
    preview = build_schedule_preview(
        _document(day=Weekday.SUNDAY, local_start="01:30"),
        at=datetime(2026, 10, 26, 12, tzinfo=UTC),
    )

    assert preview.preview_week_start_local.isoformat() == "2026-10-26"
    assert len(preview.dst_warnings) == 1
    warning = preview.dst_warnings[0]
    assert warning.kind is DstWarningKind.FOLD
    assert warning.local_date.isoformat() == "2026-11-01"
    assert warning.occurs_at_utc == datetime(2026, 11, 1, 5, 30, tzinfo=UTC)
    assert "uses only the first occurrence" in warning.explanation


def test_preview_has_no_warning_for_ordinary_week() -> None:
    preview = build_schedule_preview(
        _document(day=Weekday.MONDAY, local_start="06:30"),
        at=datetime(2026, 7, 27, 12, tzinfo=UTC),
    )

    assert preview.dst_warnings == ()
    assert preview.zones[0].period_id == PERIOD_ID


def test_preview_omits_disabled_zones() -> None:
    document = _document(day=Weekday.MONDAY, local_start="06:30")
    disabled = replace(document.zones[ZONE_ID], enabled=False)
    preview = build_schedule_preview(
        replace(document, zones={ZONE_ID: disabled}),
        at=datetime(2026, 7, 27, 12, tzinfo=UTC),
    )

    assert preview.zones == ()
    assert preview.dst_warnings == ()


@pytest.mark.parametrize(
    "document, at",
    [
        (
            replace(
                _document(day=Weekday.MONDAY, local_start="06:30"),
                time_zone="Mars/Olympus",
            ),
            datetime(2026, 7, 27, 12, tzinfo=UTC),
        ),
        (
            _document(day=Weekday.MONDAY, local_start="06:30"),
            datetime(2026, 7, 27, 12),
        ),
    ],
)
def test_preview_rejects_invalid_clock_context(
    document: ScheduleDocument,
    at: datetime,
) -> None:
    with pytest.raises(ScheduleEvaluationError):
        build_schedule_preview(document, at=at)
