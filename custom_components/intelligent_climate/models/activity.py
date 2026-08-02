"""Strict privacy-bounded activity records."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from uuid import UUID, uuid4

from .identifiers import EquipmentGroupId, ZoneId

type ActivityScalar = str | int | float | bool | None

_MAX_EXPLANATION_LENGTH = 240
_MAX_DETAIL_STRING_LENGTH = 64
_ENTITY_ID_PATTERN = re.compile(r"\b[a-z_]+\.[a-z0-9_]+\b")
_FORBIDDEN_EXPLANATION_FRAGMENTS = ("//", "\\", "://")
_DETAIL_KEYS = frozenset(
    {
        "issue_code",
        "new_exclusion_reason",
        "new_hvac_mode",
        "new_quality",
        "new_state",
        "new_target_high_c",
        "new_target_low_c",
        "new_target_temperature_c",
        "previous_exclusion_reason",
        "previous_hvac_mode",
        "previous_quality",
        "previous_state",
        "previous_target_high_c",
        "previous_target_low_c",
        "previous_target_temperature_c",
        "source_id",
    }
)


class ActivityType(StrEnum):
    """Stable Task 14 material-activity vocabulary."""

    LIFECYCLE = "lifecycle"
    RUNTIME_STATE_CHANGED = "runtime_state_changed"
    SOURCE_QUALITY_CHANGED = "source_quality_changed"
    THERMOSTAT_OBSERVATION_CHANGED = "thermostat_observation_changed"
    THERMOSTAT_CAPABILITIES_CHANGED = "thermostat_capabilities_changed"
    REPAIR_ISSUE_CREATED = "repair_issue_created"
    REPAIR_ISSUE_RESOLVED = "repair_issue_resolved"
    UNSUPPORTED_CONTROL_ATTEMPT = "unsupported_control_attempt"
    STORE_WRITE_FAILED = "store_write_failed"
    STORE_WRITE_RECOVERED = "store_write_recovered"


class ActivityReason(StrEnum):
    """Stable, payload-free reasons for material Task 14 activity."""

    SETUP_STARTED = "setup_started"
    SETUP_COMPLETED = "setup_completed"
    STORE_MIGRATED = "store_migrated"
    UNCLEAN_SHUTDOWN_DETECTED = "unclean_shutdown_detected"
    RECONCILIATION_COMPLETED = "reconciliation_completed"
    UNLOAD = "unload"
    CONTROL_STATE_CHANGED = "control_state_changed"
    SOURCE_EXCLUDED = "source_excluded"
    SOURCE_EXCLUSION_CHANGED = "source_exclusion_changed"
    SOURCE_RECOVERED = "source_recovered"
    THERMOSTAT_MODE_CHANGED = "thermostat_mode_changed"
    THERMOSTAT_TARGET_CHANGED = "thermostat_target_changed"
    THERMOSTAT_CAPABILITIES_CHANGED = "thermostat_capabilities_changed"
    NO_ZONES_CONFIGURED = "no_zones_configured"
    MISSING_ENTITY = "missing_entity"
    INCOMPATIBLE_ENTITY = "incompatible_entity"
    MIGRATION_FAILED = "migration_failed"
    STORE_WRITE_FAILED = "store_write_failed"
    COMMAND_BOUNDARY_VIOLATION = "command_boundary_violation"
    UNSUPPORTED_CONTROL_ATTEMPT = "unsupported_control_attempt"
    STORE_WRITE_RECOVERED = "store_write_recovered"


class ActivitySeverity(StrEnum):
    """Stable activity severity values."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


_REASONS_BY_TYPE: Mapping[ActivityType, frozenset[ActivityReason]] = {
    ActivityType.LIFECYCLE: frozenset(
        {
            ActivityReason.SETUP_STARTED,
            ActivityReason.SETUP_COMPLETED,
            ActivityReason.STORE_MIGRATED,
            ActivityReason.UNCLEAN_SHUTDOWN_DETECTED,
            ActivityReason.RECONCILIATION_COMPLETED,
            ActivityReason.UNLOAD,
        }
    ),
    ActivityType.RUNTIME_STATE_CHANGED: frozenset(
        {ActivityReason.CONTROL_STATE_CHANGED}
    ),
    ActivityType.SOURCE_QUALITY_CHANGED: frozenset(
        {
            ActivityReason.SOURCE_EXCLUDED,
            ActivityReason.SOURCE_EXCLUSION_CHANGED,
            ActivityReason.SOURCE_RECOVERED,
        }
    ),
    ActivityType.THERMOSTAT_OBSERVATION_CHANGED: frozenset(
        {
            ActivityReason.THERMOSTAT_MODE_CHANGED,
            ActivityReason.THERMOSTAT_TARGET_CHANGED,
        }
    ),
    ActivityType.THERMOSTAT_CAPABILITIES_CHANGED: frozenset(
        {ActivityReason.THERMOSTAT_CAPABILITIES_CHANGED}
    ),
    ActivityType.REPAIR_ISSUE_CREATED: frozenset(
        {
            ActivityReason.NO_ZONES_CONFIGURED,
            ActivityReason.MISSING_ENTITY,
            ActivityReason.INCOMPATIBLE_ENTITY,
            ActivityReason.MIGRATION_FAILED,
            ActivityReason.STORE_WRITE_FAILED,
            ActivityReason.COMMAND_BOUNDARY_VIOLATION,
        }
    ),
    ActivityType.REPAIR_ISSUE_RESOLVED: frozenset(
        {
            ActivityReason.NO_ZONES_CONFIGURED,
            ActivityReason.MISSING_ENTITY,
            ActivityReason.INCOMPATIBLE_ENTITY,
            ActivityReason.MIGRATION_FAILED,
            ActivityReason.STORE_WRITE_FAILED,
            ActivityReason.COMMAND_BOUNDARY_VIOLATION,
        }
    ),
    ActivityType.UNSUPPORTED_CONTROL_ATTEMPT: frozenset(
        {
            ActivityReason.UNSUPPORTED_CONTROL_ATTEMPT,
            ActivityReason.COMMAND_BOUNDARY_VIOLATION,
        }
    ),
    ActivityType.STORE_WRITE_FAILED: frozenset({ActivityReason.STORE_WRITE_FAILED}),
    ActivityType.STORE_WRITE_RECOVERED: frozenset(
        {ActivityReason.STORE_WRITE_RECOVERED}
    ),
}


@dataclass(frozen=True, slots=True)
class ActivityRecord:
    """One immutable material activity with a strict scalar detail projection."""

    record_id: UUID
    timestamp: datetime
    equipment_group_id: EquipmentGroupId
    zone_id: ZoneId | None
    activity_type: ActivityType
    reason_code: ActivityReason
    severity: ActivitySeverity
    explanation: str
    detail: Mapping[str, ActivityScalar]

    def __post_init__(self) -> None:
        """Validate timestamps, compatible vocabularies, text, and detail."""
        if not isinstance(self.record_id, UUID):
            raise ValueError("activity record_id must be a UUID")
        if not isinstance(self.timestamp, datetime):
            raise ValueError("activity timestamp must be a datetime")
        if self.timestamp.tzinfo is None or self.timestamp.utcoffset() is None:
            raise ValueError("activity timestamp must be timezone-aware")
        if not isinstance(self.equipment_group_id, EquipmentGroupId):
            raise ValueError("activity equipment_group_id must be stable")
        if self.zone_id is not None and not isinstance(self.zone_id, ZoneId):
            raise ValueError("activity zone_id must be stable")
        if (
            not isinstance(self.activity_type, ActivityType)
            or not isinstance(self.reason_code, ActivityReason)
            or not isinstance(self.severity, ActivitySeverity)
        ):
            raise ValueError("activity vocabulary values must be stable enums")
        if self.reason_code not in _REASONS_BY_TYPE[self.activity_type]:
            raise ValueError("activity reason is not valid for activity type")
        if (
            not self.explanation
            or self.explanation != self.explanation.strip()
            or len(self.explanation) > _MAX_EXPLANATION_LENGTH
            or any(character in self.explanation for character in "\r\n\t")
            or any(
                fragment in self.explanation
                for fragment in _FORBIDDEN_EXPLANATION_FRAGMENTS
            )
            or _ENTITY_ID_PATTERN.search(self.explanation)
        ):
            raise ValueError("activity explanation must be concise and privacy-safe")
        detail = dict(self.detail)
        unknown = set(detail) - _DETAIL_KEYS
        if unknown:
            raise ValueError("activity detail contains a non-allowlisted field")
        for key, value in detail.items():
            if not isinstance(key, str) or not _valid_scalar(value):
                raise ValueError("activity detail values must be bounded scalars")
        object.__setattr__(self, "detail", MappingProxyType(detail))

    @classmethod
    def new(
        cls,
        *,
        timestamp: datetime,
        equipment_group_id: EquipmentGroupId,
        zone_id: ZoneId | None,
        activity_type: ActivityType,
        reason_code: ActivityReason,
        severity: ActivitySeverity,
        explanation: str,
        detail: Mapping[str, ActivityScalar] | None = None,
    ) -> ActivityRecord:
        """Create a record with a new stable UUID."""
        return cls(
            record_id=uuid4(),
            timestamp=timestamp,
            equipment_group_id=equipment_group_id,
            zone_id=zone_id,
            activity_type=activity_type,
            reason_code=reason_code,
            severity=severity,
            explanation=explanation,
            detail={} if detail is None else detail,
        )


def _valid_scalar(value: object) -> bool:
    if value is None or isinstance(value, bool | int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    return (
        isinstance(value, str)
        and bool(value)
        and len(value) <= _MAX_DETAIL_STRING_LENGTH
        and value == value.strip()
        and not any(character in value for character in "\r\n\t")
    )
