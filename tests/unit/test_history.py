"""Test bounded material activity history semantics."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from custom_components.intelligent_climate.history import ActivityHistory
from custom_components.intelligent_climate.models import (
    ActivityReason,
    ActivityRecord,
    ActivitySeverity,
    ActivityType,
    EquipmentGroupId,
    ZoneId,
)

NOW = datetime(2026, 7, 27, 12, tzinfo=UTC)
GROUP_ID = EquipmentGroupId.parse("b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3")
ZONE_IDS = (
    ZoneId.parse("99246285-6f02-4e8a-94ed-bdfd4a5e62c4"),
    ZoneId.parse("7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"),
)


def _record(index: int, timestamp: datetime, *, zone_index: int = 0) -> ActivityRecord:
    return ActivityRecord(
        record_id=UUID(int=index + 1),
        timestamp=timestamp,
        equipment_group_id=GROUP_ID,
        zone_id=ZONE_IDS[zone_index],
        activity_type=ActivityType.SOURCE_QUALITY_CHANGED,
        reason_code=ActivityReason.SOURCE_EXCLUDED,
        severity=ActivitySeverity.WARNING,
        explanation="A configured observation source was excluded.",
        detail={},
    )


def test_exact_count_pruning_keeps_newest_oldest_to_newest() -> None:
    """Configured count pruning retains the newest records deterministically."""
    history = ActivityHistory(max_records=3, max_age_days=30)
    records = [_record(index, NOW + timedelta(seconds=index)) for index in range(5)]
    for record in records:
        assert history.add(record, now=record.timestamp)

    assert history.records == tuple(records[-3:])
    assert history.latest is records[-1]


def test_exact_age_cutoff_is_inclusive() -> None:
    """Only records strictly older than the age cutoff are removed."""
    history = ActivityHistory(max_records=10, max_age_days=30)
    before = _record(0, NOW - timedelta(days=30, microseconds=1))
    cutoff = _record(1, NOW - timedelta(days=30))
    after = _record(2, NOW - timedelta(days=29))

    history.restore((after, before, cutoff), now=NOW)

    assert history.records == (cutoff, after)


def test_restore_sorts_and_deduplicates_deterministically_without_notifications() -> (
    None
):
    """Validated loaded records are ordered and duplicate IDs are accepted once."""
    history = ActivityHistory(max_records=10, max_age_days=30)
    accepted: list[ActivityRecord] = []
    history.async_add_listener(accepted.append)
    first = _record(0, NOW - timedelta(minutes=1))
    duplicate = ActivityRecord(
        record_id=first.record_id,
        timestamp=NOW,
        equipment_group_id=GROUP_ID,
        zone_id=ZONE_IDS[1],
        activity_type=ActivityType.SOURCE_QUALITY_CHANGED,
        reason_code=ActivityReason.SOURCE_RECOVERED,
        severity=ActivitySeverity.INFO,
        explanation="A configured observation source recovered.",
        detail={},
    )
    second = _record(1, NOW - timedelta(seconds=30), zone_index=1)

    history.restore((duplicate, second, first), now=NOW)

    assert history.records == (first, second)
    assert history.latest_for_zone(ZONE_IDS[0]) is first
    assert history.latest_for_zone(ZONE_IDS[1]) is second
    assert accepted == []


def test_duplicate_new_record_id_is_rejected_without_notification() -> None:
    """Only newly accepted record IDs notify listeners."""
    history = ActivityHistory(max_records=10, max_age_days=30)
    accepted: list[ActivityRecord] = []
    unsubscribe = history.async_add_listener(accepted.append)
    record = _record(0, NOW)

    assert history.add(record, now=NOW)
    assert history.add(record, now=NOW) is False
    assert accepted == [record]
    assert history.listener_count == 1
    unsubscribe()
    assert history.listener_count == 0


def test_hard_limit_is_500_even_when_configured_higher() -> None:
    """The immutable history never exceeds the absolute Task 14 cap."""
    history = ActivityHistory(max_records=9999, max_age_days=30)
    records = tuple(
        _record(index, NOW + timedelta(microseconds=index)) for index in range(550)
    )

    history.restore(records, now=records[-1].timestamp)

    assert history.max_records == 500
    assert len(history.records) == 500
    assert history.records == records[-500:]


def test_bounded_diagnostic_view_does_not_mutate_history() -> None:
    """A current diagnostic view applies age pruning without changing state."""
    history = ActivityHistory(max_records=10, max_age_days=30)
    old = _record(0, NOW)
    history.add(old, now=NOW)

    assert history.bounded_records(now=NOW + timedelta(days=31)) == ()
    assert history.records == (old,)


@pytest.mark.parametrize(
    ("arguments", "match"),
    [
        ({"max_records": 0, "max_age_days": 30}, "max_records"),
        ({"max_records": 10, "max_age_days": 0}, "max_age_days"),
    ],
)
def test_history_bounds_must_be_positive_integers(
    arguments: dict[str, int],
    match: str,
) -> None:
    """Invalid configured bounds fail closed."""
    with pytest.raises(ValueError, match=match):
        ActivityHistory(**arguments)


def test_old_new_record_is_rejected_and_listener_removal_is_idempotent() -> None:
    """An already-expired new record is not accepted or published."""
    history = ActivityHistory(max_records=10, max_age_days=30)
    accepted: list[ActivityRecord] = []
    unsubscribe = history.async_add_listener(accepted.append)

    assert history.add(_record(0, NOW - timedelta(days=31)), now=NOW) is False
    assert accepted == []
    unsubscribe()
    unsubscribe()
    assert history.listener_count == 0


def test_history_cutoffs_must_be_timezone_aware() -> None:
    """Naive pruning timestamps cannot silently change retention semantics."""
    history = ActivityHistory(max_records=10, max_age_days=30)

    with pytest.raises(ValueError, match="timezone-aware"):
        history.prune(now=datetime(2026, 7, 27, 12))
