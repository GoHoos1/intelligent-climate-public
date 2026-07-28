"""Diagnostic material-activity Event entities."""

from __future__ import annotations

from typing import override

from homeassistant.components.event import EventEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, NAME, SUBENTRY_TYPE_ZONE
from .coordinator import IntelligentClimateCoordinator
from .models import (
    ActivityRecord,
    ActivityType,
    RuntimeConfigurationState,
    ZoneConfig,
    ZoneId,
)
from .type_aliases import IntelligentClimateConfigEntry

_GROUP_MODEL = "Equipment group"
_ZONE_MODEL = "Climate zone"

_GROUP_EVENT_TYPES = [
    ActivityType.LIFECYCLE.value,
    ActivityType.RUNTIME_STATE_CHANGED.value,
    ActivityType.REPAIR_ISSUE_CREATED.value,
    ActivityType.REPAIR_ISSUE_RESOLVED.value,
    ActivityType.UNSUPPORTED_CONTROL_ATTEMPT.value,
    ActivityType.STORE_WRITE_FAILED.value,
    ActivityType.STORE_WRITE_RECOVERED.value,
]
_ZONE_EVENT_TYPES = [
    ActivityType.SOURCE_QUALITY_CHANGED.value,
    ActivityType.THERMOSTAT_OBSERVATION_CHANGED.value,
    ActivityType.THERMOSTAT_CAPABILITIES_CHANGED.value,
    ActivityType.UNSUPPORTED_CONTROL_ATTEMPT.value,
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up exactly one group and one per-zone activity Event entity."""
    coordinator = entry.runtime_data
    subentries = _zone_subentries_by_id(entry)
    matched_subentries: list[tuple[ZoneConfig, ConfigSubentry]] = []
    configured_zones = (
        coordinator.configuration.zones
        if coordinator.configuration.state is RuntimeConfigurationState.CONFIGURED
        else ()
    )
    for zone in configured_zones:
        matches = subentries.get(str(zone.zone_id), ())
        if len(matches) != 1:
            raise ConfigEntryError(
                f"Zone {zone.zone_id} must match exactly one config subentry"
            )
        matched_subentries.append((zone, matches[0]))

    group = coordinator.configuration.equipment_group
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(group.equipment_group_id))},
        manufacturer=NAME,
        model=_GROUP_MODEL,
        name=group.name,
    )
    async_add_entities([IntelligentClimateGroupActivityEvent(coordinator)])

    for zone, subentry in matched_subentries:
        async_add_entities(
            [IntelligentClimateZoneActivityEvent(coordinator, zone)],
            config_subentry_id=subentry.subentry_id,
        )


def _zone_subentries_by_id(
    entry: IntelligentClimateConfigEntry,
) -> dict[str, list[ConfigSubentry]]:
    result: dict[str, list[ConfigSubentry]] = {}
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            continue
        if subentry.unique_id is None:
            raise ConfigEntryError("Zone config subentry is missing its stable ID")
        result.setdefault(subentry.unique_id, []).append(subentry)
    return result


class _ActivityEvent(EventEntity):
    """Common safe EventEntity adapter over newly accepted activity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_translation_key = "activity"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        *,
        zone_id: ZoneId | None,
    ) -> None:
        self.coordinator = coordinator
        self._zone_id = zone_id

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe after add; restored history is deliberately not replayed."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.history.async_add_listener(self._activity_accepted)
        )

    @callback
    def _activity_accepted(self, record: ActivityRecord) -> None:
        if record.zone_id != self._zone_id:
            return
        self._trigger_event(
            record.activity_type.value,
            {
                "reason_code": record.reason_code.value,
                "severity": record.severity.value,
                "timestamp": record.timestamp.isoformat(),
                "explanation": record.explanation,
                "record_id": str(record.record_id),
                "equipment_group_id": str(record.equipment_group_id),
                "zone_id": (None if record.zone_id is None else str(record.zone_id)),
            },
        )
        self.async_write_ha_state()


class IntelligentClimateGroupActivityEvent(_ActivityEvent):
    """Equipment-group-scoped material activity."""

    _attr_event_types = _GROUP_EVENT_TYPES

    def __init__(self, coordinator: IntelligentClimateCoordinator) -> None:
        """Initialize stable group identity and diagnostic device placement."""
        super().__init__(coordinator, zone_id=None)
        group = coordinator.configuration.equipment_group
        self._attr_unique_id = f"{group.equipment_group_id}:activity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(group.equipment_group_id))},
            manufacturer=NAME,
            model=_GROUP_MODEL,
            name=group.name,
        )


class IntelligentClimateZoneActivityEvent(_ActivityEvent):
    """Zone-scoped material activity."""

    _attr_event_types = _ZONE_EVENT_TYPES

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        """Initialize stable zone identity and child-device placement."""
        super().__init__(coordinator, zone_id=zone.zone_id)
        group = coordinator.configuration.equipment_group
        self._attr_unique_id = f"{zone.zone_id}:activity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(zone.zone_id))},
            manufacturer=NAME,
            model=_ZONE_MODEL,
            name=zone.name,
            via_device=(DOMAIN, str(group.equipment_group_id)),
        )
