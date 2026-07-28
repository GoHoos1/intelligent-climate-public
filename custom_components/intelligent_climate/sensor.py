"""Diagnostic Latest Activity sensors."""

from __future__ import annotations

from typing import Any, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, NAME, SUBENTRY_TYPE_ZONE
from .coordinator import IntelligentClimateCoordinator
from .models import ActivityRecord, RuntimeConfigurationState, ZoneConfig
from .type_aliases import IntelligentClimateConfigEntry

_ZONE_MODEL = "Climate zone"
_GROUP_MODEL = "Equipment group"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up exactly one Latest Activity sensor per configured zone."""
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

    for zone, subentry in matched_subentries:
        async_add_entities(
            [IntelligentClimateLatestActivitySensor(coordinator, zone)],
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


class IntelligentClimateLatestActivitySensor(SensorEntity):
    """Present the concise newest zone-scoped material activity."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    _attr_translation_key = "latest_activity"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        """Initialize stable identity and zone device placement."""
        self.coordinator = coordinator
        self.zone = zone
        group = coordinator.configuration.equipment_group
        self._attr_unique_id = f"{zone.zone_id}:latest_activity"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(zone.zone_id))},
            manufacturer=NAME,
            model=_ZONE_MODEL,
            name=zone.name,
            via_device=(DOMAIN, str(group.equipment_group_id)),
        )

    @property
    def _latest(self) -> ActivityRecord | None:
        return self.coordinator.history.latest_for_zone(self.zone.zone_id)

    @property
    @override
    def native_value(self) -> str | None:
        """Return only the newest concise zone explanation."""
        latest = self._latest
        return None if latest is None else latest.explanation

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose the strict latest-activity allowlist."""
        latest = self._latest
        if latest is None:
            return None
        return {
            "activity_type": latest.activity_type.value,
            "reason_code": latest.reason_code.value,
            "severity": latest.severity.value,
            "timestamp": latest.timestamp.isoformat(),
            "record_id": str(latest.record_id),
        }

    @override
    async def async_added_to_hass(self) -> None:
        """Subscribe to coordinator and non-coordinator history activity."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.coordinator.history.async_add_listener(self._activity_accepted)
        )

    @callback
    def _activity_accepted(self, record: ActivityRecord) -> None:
        if record.zone_id != self.zone.zone_id:
            return
        self.async_write_ha_state()
