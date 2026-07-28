"""Test strict material activity records and publication."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from uuid import UUID

import pytest
from homeassistant.core import HomeAssistant

from custom_components.intelligent_climate.activity import ActivityPublisher
from custom_components.intelligent_climate.const import EVENT_ACTIVITY
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
ZONE_ID = ZoneId.parse("99246285-6f02-4e8a-94ed-bdfd4a5e62c4")


def _record(**changes: object) -> ActivityRecord:
    values: dict[str, object] = {
        "record_id": UUID("37eaa5de-8a48-47ea-9988-bb0fc2e10a24"),
        "timestamp": NOW,
        "equipment_group_id": GROUP_ID,
        "zone_id": ZONE_ID,
        "activity_type": ActivityType.SOURCE_QUALITY_CHANGED,
        "reason_code": ActivityReason.SOURCE_EXCLUDED,
        "severity": ActivitySeverity.WARNING,
        "explanation": "A configured observation source was excluded.",
        "detail": {
            "source_id": "f15f73b1-ea59-4b28-819f-7b99acf065bf",
            "new_quality": "stale",
        },
    }
    values.update(changes)
    return ActivityRecord(**values)  # type: ignore[arg-type]


def test_activity_record_is_frozen_slotted_and_strict() -> None:
    """A valid record has stable identity and immutable bounded detail."""
    record = _record()

    assert str(record.record_id) == "37eaa5de-8a48-47ea-9988-bb0fc2e10a24"
    assert record.timestamp is NOW
    assert not hasattr(record, "__dict__")
    with pytest.raises(FrozenInstanceError):
        record.explanation = "changed"  # type: ignore[misc]
    with pytest.raises(TypeError):
        record.detail["new_quality"] = "valid"  # type: ignore[index]


def test_activity_vocabularies_are_stable_and_complete() -> None:
    """Task 14 exposes exactly the approved activity types and severities."""
    assert tuple(item.value for item in ActivityType) == (
        "lifecycle",
        "runtime_state_changed",
        "source_quality_changed",
        "thermostat_observation_changed",
        "thermostat_capabilities_changed",
        "repair_issue_created",
        "repair_issue_resolved",
        "unsupported_control_attempt",
        "store_write_failed",
        "store_write_recovered",
    )
    assert tuple(item.value for item in ActivitySeverity) == (
        "info",
        "warning",
        "error",
    )


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"timestamp": datetime(2026, 7, 27, 12)}, "timezone-aware"),
        ({"record_id": "not-a-uuid"}, "record_id must be a UUID"),
        ({"timestamp": "not-a-datetime"}, "timestamp must be a datetime"),
        (
            {"equipment_group_id": "not-a-group-id"},
            "equipment_group_id must be stable",
        ),
        ({"zone_id": "not-a-zone-id"}, "zone_id must be stable"),
        ({"activity_type": "source_quality_changed"}, "stable enums"),
        ({"reason_code": "source_excluded"}, "stable enums"),
        ({"severity": "warning"}, "stable enums"),
        (
            {
                "activity_type": ActivityType.LIFECYCLE,
                "reason_code": ActivityReason.SOURCE_EXCLUDED,
            },
            "not valid",
        ),
        ({"explanation": "Source sensor.private_temperature failed."}, "privacy-safe"),
        ({"explanation": "https://private.invalid"}, "privacy-safe"),
        ({"detail": {"entity_id": "sensor.private"}}, "non-allowlisted"),
        ({"detail": {"new_quality": float("inf")}}, "bounded scalars"),
        ({"detail": {"new_quality": ["stale"]}}, "bounded scalars"),
    ],
)
def test_activity_record_rejects_invalid_or_private_values(
    changes: dict[str, object],
    match: str,
) -> None:
    """Invalid vocabularies, timestamps, and detail fail closed."""
    with pytest.raises(ValueError, match=match):
        _record(**changes)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_publisher_fires_exact_payload_once_per_accepted_record(
    hass: HomeAssistant,
) -> None:
    """The bus receives exactly the documented allowlist without detail."""
    history = ActivityHistory(max_records=10, max_age_days=30)
    events: list[dict[str, object]] = []
    unsubscribe = hass.bus.async_listen(
        EVENT_ACTIVITY,
        lambda event: events.append(dict(event.data)),
    )
    publisher = ActivityPublisher(
        hass,
        entry_id="entry-1",
        equipment_group_id=GROUP_ID,
        history=history,
        now_fn=lambda: NOW,
    )

    record = publisher.record(
        activity_type=ActivityType.SOURCE_QUALITY_CHANGED,
        reason_code=ActivityReason.SOURCE_EXCLUDED,
        severity=ActivitySeverity.WARNING,
        explanation="A configured observation source was excluded.",
        zone_id=ZONE_ID,
        detail={"source_id": "f15f73b1-ea59-4b28-819f-7b99acf065bf"},
    )
    assert history.add(record, now=NOW) is False
    await hass.async_block_till_done()

    assert events == [
        {
            "entry_id": "entry-1",
            "equipment_group_id": str(GROUP_ID),
            "zone_id": str(ZONE_ID),
            "activity_type": "source_quality_changed",
            "reason_code": "source_excluded",
            "severity": "warning",
            "timestamp": NOW.isoformat(),
            "explanation": "A configured observation source was excluded.",
        }
    ]
    assert "detail" not in events[0]
    assert "record_id" not in events[0]

    publisher.close()
    unsubscribe()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_restored_history_does_not_fire_bus_activity(
    hass: HomeAssistant,
) -> None:
    """Silent restore establishes history without republishing it."""
    history = ActivityHistory(max_records=10, max_age_days=30)
    events: list[object] = []
    unsubscribe = hass.bus.async_listen(EVENT_ACTIVITY, events.append)
    publisher = ActivityPublisher(
        hass,
        entry_id="entry-1",
        equipment_group_id=GROUP_ID,
        history=history,
        now_fn=lambda: NOW,
    )

    history.restore([_record()], now=NOW)
    await hass.async_block_till_done()

    assert events == []
    publisher.close()
    unsubscribe()
