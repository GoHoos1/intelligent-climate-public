"""Typed, entry-scoped Home Assistant Repairs boundary."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .const import DOMAIN
from .models import (
    EntryRuntimeConfiguration,
    HumiditySource,
    RuntimeConfigurationState,
    TemperatureSource,
)

_ENTRY_SCOPE_HEX_LENGTH = 12
_MAX_ISSUE_COUNT = 9999
_TRANSIENT_STATES = frozenset({STATE_UNKNOWN, STATE_UNAVAILABLE})


class IssueCode(StrEnum):
    """Stable Intelligent Climate issue-code vocabulary."""

    NO_ZONES_CONFIGURED = "no_zones_configured"
    MISSING_ENTITY = "missing_entity"
    INCOMPATIBLE_ENTITY = "incompatible_entity"
    MIGRATION_FAILED = "migration_failed"
    STORE_WRITE_FAILED = "store_write_failed"
    COMMAND_BOUNDARY_VIOLATION = "command_boundary_violation"


class MigrationFailureCategory(StrEnum):
    """Bounded migration and persisted-validation failure categories."""

    SCHEMA_MIGRATION = "schema_migration"
    SCHEMA_VALIDATION = "schema_validation"
    ENTITY_VALIDATION = "entity_validation"
    RUNTIME_VALIDATION = "runtime_validation"
    STORE_LOAD = "store_load"
    STORE_VALIDATION = "store_validation"
    STORE_VERSION = "store_version"


@dataclass(frozen=True, slots=True)
class IssuePolicy:
    """Immutable Home Assistant issue-registry policy."""

    severity: ir.IssueSeverity
    is_persistent: bool
    is_fixable: bool = False


class ActivityReporter(Protocol):
    """Narrow optional activity boundary for actual Repairs transitions."""

    def async_report_repair_activity(self, issue_code: str, *, created: bool) -> None:
        """Report one actual issue-registry creation or resolution."""

    def async_report_command_boundary_violation(self) -> None:
        """Report one payload-free unexpected command intent."""


def issue_policy(code: IssueCode) -> IssuePolicy:
    """Return the documented policy for one Task 13 issue."""
    return IssuePolicy(
        severity=ir.IssueSeverity.ERROR,
        is_persistent=code
        in {
            IssueCode.MIGRATION_FAILED,
            IssueCode.STORE_WRITE_FAILED,
            IssueCode.COMMAND_BOUNDARY_VIOLATION,
        },
    )


def issue_id(entry_id: str, code: IssueCode) -> str:
    """Return a deterministic privacy-bounded issue ID."""
    if not entry_id:
        raise ValueError("config-entry ID must not be empty")
    entry_scope = hashlib.sha256(
        f"{DOMAIN}\0{entry_id}".encode(),
    ).hexdigest()[:_ENTRY_SCOPE_HEX_LENGTH]
    return f"entry_{entry_scope}_{code.value}"


def active_issue_codes(
    hass: HomeAssistant,
    entry_id: str,
) -> tuple[IssueCode, ...]:
    """Return an immutable sorted view of active entry-scoped issues."""
    registry = ir.async_get(hass)
    return tuple(
        sorted(
            (
                code
                for code in IssueCode
                if (
                    issue := registry.async_get_issue(
                        DOMAIN,
                        issue_id(entry_id, code),
                    )
                )
                is not None
                and issue.active
            ),
            key=str,
        )
    )


class RepairsManager:
    """Synchronize one config entry's bounded Repairs issues."""

    __slots__ = ("_activity_reporter", "_entry_id", "_hass")

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        activity_reporter: ActivityReporter | None = None,
    ) -> None:
        """Initialize the entry-scoped issue boundary."""
        if not entry_id:
            raise ValueError("config-entry ID must not be empty")
        self._hass = hass
        self._entry_id = entry_id
        self._activity_reporter = activity_reporter

    def set_activity_reporter(self, reporter: ActivityReporter) -> None:
        """Attach the entry-scoped activity boundary after safe Store loading."""
        self._activity_reporter = reporter

    @property
    def active_issue_codes(self) -> tuple[IssueCode, ...]:
        """Return an immutable sorted view without exposing issue IDs."""
        return active_issue_codes(self._hass, self._entry_id)

    def async_prepare_clean_setup(
        self,
        *,
        preserve_migration_failure: bool = False,
    ) -> None:
        """Clear setup-rechecked and stale command-event issues."""
        codes = [
            IssueCode.MISSING_ENTITY,
            IssueCode.INCOMPATIBLE_ENTITY,
            IssueCode.COMMAND_BOUNDARY_VIOLATION,
        ]
        if not preserve_migration_failure:
            codes.append(IssueCode.MIGRATION_FAILED)
        for code in codes:
            self.async_delete_issue(code)

    def async_clear_migration_failure(self) -> None:
        """Clear a recovered persisted-data failure."""
        self.async_delete_issue(IssueCode.MIGRATION_FAILED)

    def async_sync_entity_conditions(
        self,
        configuration: EntryRuntimeConfiguration,
    ) -> None:
        """Synchronize actionable entity failures after reconciliation."""
        if (
            not configuration.options.observation_enabled
            or configuration.state is not RuntimeConfigurationState.CONFIGURED
        ):
            return
        missing_count, incompatible_count = _entity_condition_counts(
            self._hass,
            configuration,
        )
        self._async_sync_counted_issue(IssueCode.MISSING_ENTITY, missing_count)
        self._async_sync_counted_issue(
            IssueCode.INCOMPATIBLE_ENTITY,
            incompatible_count,
        )

    def async_sync_zone_presence(self, *, has_zones: bool) -> None:
        """Keep the actionable final-zone-removal issue synchronized."""
        if has_zones:
            self.async_delete_issue(IssueCode.NO_ZONES_CONFIGURED)
            return
        self._async_create_issue(
            IssueCode.NO_ZONES_CONFIGURED,
            {"issue_code": IssueCode.NO_ZONES_CONFIGURED.value},
        )

    def async_report_migration_failure(
        self,
        category: MigrationFailureCategory,
    ) -> None:
        """Create or retain a bounded migration-failure issue."""
        self._async_create_issue(
            IssueCode.MIGRATION_FAILED,
            {
                "issue_code": IssueCode.MIGRATION_FAILED.value,
                "failure_category": category.value,
            },
        )

    def async_notify_store_write_failures(
        self,
        consecutive_failures: int,
    ) -> None:
        """Synchronize the future Store hook without performing Store I/O."""
        if (
            not isinstance(consecutive_failures, int)
            or isinstance(consecutive_failures, bool)
            or consecutive_failures < 0
        ):
            raise ValueError("consecutive Store failures must be a nonnegative integer")
        if consecutive_failures == 0:
            self.async_delete_issue(IssueCode.STORE_WRITE_FAILED)
        elif consecutive_failures >= 3:
            self._async_create_issue(
                IssueCode.STORE_WRITE_FAILED,
                {
                    "issue_code": IssueCode.STORE_WRITE_FAILED.value,
                    "failure_threshold": 3,
                },
            )

    def async_report_command_boundary_violation(self) -> None:
        """Create the persistent unexpected-command issue without payload data."""
        if self._activity_reporter is not None:
            self._activity_reporter.async_report_command_boundary_violation()
        self._async_create_issue(
            IssueCode.COMMAND_BOUNDARY_VIOLATION,
            {
                "issue_code": IssueCode.COMMAND_BOUNDARY_VIOLATION.value,
                "reason_category": "unexpected_control_intent",
            },
        )

    def async_delete_issue(self, code: IssueCode) -> None:
        """Delete an issue if present; an absent issue is harmless."""
        registry = ir.async_get(self._hass)
        current_id = issue_id(self._entry_id, code)
        if registry.async_get_issue(DOMAIN, current_id) is None:
            return
        ir.async_delete_issue(self._hass, DOMAIN, current_id)
        if self._activity_reporter is not None:
            self._activity_reporter.async_report_repair_activity(
                code.value,
                created=False,
            )

    def _async_sync_counted_issue(self, code: IssueCode, count: int) -> None:
        if count == 0:
            self.async_delete_issue(code)
            return
        self._async_create_issue(
            code,
            {
                "issue_code": code.value,
                "affected_reference_count": min(count, _MAX_ISSUE_COUNT),
            },
        )

    def _async_create_issue(
        self,
        code: IssueCode,
        data: dict[str, str | int | float | None],
    ) -> None:
        policy = issue_policy(code)
        registry = ir.async_get(self._hass)
        current_id = issue_id(self._entry_id, code)
        existing = registry.async_get_issue(DOMAIN, current_id)
        if (
            existing is not None
            and existing.data == data
            and existing.is_fixable is policy.is_fixable
            and existing.is_persistent is policy.is_persistent
            and existing.severity is policy.severity
            and existing.translation_key == code.value
            and existing.translation_placeholders is None
        ):
            return
        ir.async_create_issue(
            self._hass,
            DOMAIN,
            current_id,
            data=data,
            is_fixable=policy.is_fixable,
            is_persistent=policy.is_persistent,
            severity=policy.severity,
            translation_key=code.value,
        )
        if existing is None and self._activity_reporter is not None:
            self._activity_reporter.async_report_repair_activity(
                code.value,
                created=True,
            )


def _entity_condition_counts(
    hass: HomeAssistant,
    configuration: EntryRuntimeConfiguration,
) -> tuple[int, int]:
    """Return missing and definitively incompatible binding counts."""
    missing_count = 0
    incompatible_count = 0

    for thermostat in configuration.equipment_group.thermostats:
        if hass.states.get(thermostat.entity_id) is None:
            missing_count += 1

    for zone in configuration.zones:
        sources: tuple[TemperatureSource | HumiditySource, ...] = (
            *zone.temperature_sources,
            *zone.humidity_sources,
        )
        for source in sources:
            if not source.enabled:
                continue
            state = hass.states.get(source.entity_id)
            if state is None:
                missing_count += 1
                continue
            if state.state in _TRANSIENT_STATES:
                continue
            if _source_is_incompatible(source, state.attributes.get(ATTR_DEVICE_CLASS)):
                incompatible_count += 1
    return missing_count, incompatible_count


def _source_is_incompatible(
    source: TemperatureSource | HumiditySource,
    device_class: object,
) -> bool:
    """Return whether an existing, nontransient source is definitively invalid."""
    domain = source.entity_id.partition(".")[0]
    if isinstance(source, TemperatureSource):
        if domain == "climate":
            return source.attribute != "current_temperature"
        return (
            domain != "sensor"
            or source.attribute is not None
            or device_class != SensorDeviceClass.TEMPERATURE
        )
    if domain == "climate":
        return source.attribute != "current_humidity"
    return (
        domain != "sensor"
        or source.attribute is not None
        or device_class != SensorDeviceClass.HUMIDITY
    )
