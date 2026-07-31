"""Observation-enable configuration switches."""

from __future__ import annotations

from dataclasses import replace
from typing import override

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, NAME, SUBENTRY_TYPE_ZONE
from .coordinator import IntelligentClimateCoordinator
from .entity import IntelligentClimateZoneEntity
from .models import RuntimeConfigurationState, ZoneConfig
from .schema_compat import encode_active_observation_options
from .type_aliases import IntelligentClimateConfigEntry

_ZONE_MODEL = "Climate zone"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up one observation-enable switch per configured zone."""
    coordinator = entry.runtime_data
    subentries = _zone_subentries_by_id(entry)
    zones = (
        coordinator.configuration.zones
        if coordinator.configuration.state is RuntimeConfigurationState.CONFIGURED
        else ()
    )
    for zone in zones:
        matches = subentries.get(str(zone.zone_id), ())
        if len(matches) != 1:
            raise ConfigEntryError(
                f"Zone {zone.zone_id} must match exactly one config subentry"
            )
        async_add_entities(
            [IntelligentClimateObservationEnabledSwitch(coordinator, zone)],
            config_subentry_id=matches[0].subentry_id,
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


class IntelligentClimateObservationEnabledSwitch(
    IntelligentClimateZoneEntity,
    SwitchEntity,
):
    """Entry-wide observation toggle represented on each zone device."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "observation_enabled"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        super().__init__(coordinator, zone)
        group = coordinator.configuration.equipment_group
        self._attr_unique_id = f"{zone.zone_id}:observation_enabled"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(zone.zone_id))},
            manufacturer=NAME,
            model=_ZONE_MODEL,
            name=zone.name,
            via_device=(DOMAIN, str(group.equipment_group_id)),
        )

    @property
    @override
    def is_on(self) -> bool:
        return self.coordinator.configuration.options.observation_enabled

    @override
    async def async_turn_on(self, **kwargs: object) -> None:
        await self._async_set_enabled(True)

    @override
    async def async_turn_off(self, **kwargs: object) -> None:
        await self._async_set_enabled(False)

    async def _async_set_enabled(self, enabled: bool) -> None:
        entry = self.coordinator.entry
        current = self.coordinator.configuration.options
        if current.observation_enabled is enabled:
            return
        self.hass.config_entries.async_update_entry(
            entry,
            options=encode_active_observation_options(
                replace(current, observation_enabled=enabled),
                version=entry.version,
                minor_version=entry.minor_version,
                current_data=entry.options,
            ),
        )
        await self.hass.config_entries.async_reload(entry.entry_id)
