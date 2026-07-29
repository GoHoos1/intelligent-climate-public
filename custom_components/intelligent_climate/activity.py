"""Entry-scoped activity creation and Home Assistant event publication."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime

from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from .const import EVENT_ACTIVITY
from .history import ActivityHistory
from .models import (
    ActivityReason,
    ActivityRecord,
    ActivitySeverity,
    ActivityType,
    EquipmentGroupId,
    ZoneId,
)
from .models.activity import ActivityScalar

type NowFunction = Callable[[], datetime]

_REPAIR_REASONS = {
    "no_zones_configured": ActivityReason.NO_ZONES_CONFIGURED,
    "missing_entity": ActivityReason.MISSING_ENTITY,
    "incompatible_entity": ActivityReason.INCOMPATIBLE_ENTITY,
    "migration_failed": ActivityReason.MIGRATION_FAILED,
    "store_write_failed": ActivityReason.STORE_WRITE_FAILED,
    "command_boundary_violation": ActivityReason.COMMAND_BOUNDARY_VIOLATION,
}


class ActivityPublisher:
    """Create safe records and fire one exact bus event per accepted record."""

    __slots__ = (
        "_entry_id",
        "_equipment_group_id",
        "_hass",
        "_history",
        "_now_fn",
        "_unsubscribe",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry_id: str,
        equipment_group_id: EquipmentGroupId,
        history: ActivityHistory,
        now_fn: NowFunction = utcnow,
    ) -> None:
        """Initialize and subscribe only to newly accepted history records."""
        self._hass = hass
        self._entry_id = entry_id
        self._equipment_group_id = equipment_group_id
        self._history = history
        self._now_fn = now_fn
        self._unsubscribe = history.async_add_listener(self._async_publish)

    def record(
        self,
        *,
        activity_type: ActivityType,
        reason_code: ActivityReason,
        severity: ActivitySeverity,
        explanation: str,
        zone_id: ZoneId | None = None,
        detail: Mapping[str, ActivityScalar] | None = None,
        timestamp: datetime | None = None,
    ) -> ActivityRecord:
        """Create and accept one activity through the bounded history."""
        occurred_at = self._now_fn() if timestamp is None else timestamp
        record = ActivityRecord.new(
            timestamp=occurred_at,
            equipment_group_id=self._equipment_group_id,
            zone_id=zone_id,
            activity_type=activity_type,
            reason_code=reason_code,
            severity=severity,
            explanation=explanation,
            detail=detail,
        )
        self._history.add(record, now=occurred_at)
        return record

    def async_report_repair_activity(self, issue_code: str, *, created: bool) -> None:
        """Report an actual Repairs registry creation or resolution."""
        reason = _REPAIR_REASONS[issue_code]
        self.record(
            activity_type=(
                ActivityType.REPAIR_ISSUE_CREATED
                if created
                else ActivityType.REPAIR_ISSUE_RESOLVED
            ),
            reason_code=reason,
            severity=(ActivitySeverity.ERROR if created else ActivitySeverity.INFO),
            explanation=(
                "An actionable integration issue was reported."
                if created
                else "An actionable integration issue was resolved."
            ),
            detail={"issue_code": issue_code},
        )

    def async_report_command_boundary_violation(self) -> None:
        """Record only the stable boundary reason, never the intent payload."""
        self.record(
            activity_type=ActivityType.UNSUPPORTED_CONTROL_ATTEMPT,
            reason_code=ActivityReason.COMMAND_BOUNDARY_VIOLATION,
            severity=ActivitySeverity.ERROR,
            explanation="An unexpected control intent was safely suppressed.",
        )

    def close(self) -> None:
        """Stop bus publication without changing retained history."""
        self._unsubscribe()

    def _async_publish(self, record: ActivityRecord) -> None:
        self._hass.bus.async_fire(
            EVENT_ACTIVITY,
            {
                "entry_id": self._entry_id,
                "equipment_group_id": str(record.equipment_group_id),
                "zone_id": None if record.zone_id is None else str(record.zone_id),
                "activity_type": record.activity_type.value,
                "reason_code": record.reason_code.value,
                "severity": record.severity.value,
                "timestamp": record.timestamp.isoformat(),
                "explanation": record.explanation,
            },
        )
