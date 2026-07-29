"""Phase 1 observation-health binary sensors."""

from __future__ import annotations

from typing import override

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, SUBENTRY_TYPE_ZONE
from .coordinator import IntelligentClimateCoordinator
from .entity import IntelligentClimateZoneEntity
from .models import RuntimeConfigurationState, ZoneConfig
from .repairs import IssueCode
from .type_aliases import IntelligentClimateConfigEntry

_GROUP_MODEL = "Equipment group"
_ZONE_MODEL = "Climate zone"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the exact applicable Phase 1 binary-sensor inventory."""
    coordinator = entry.runtime_data
    group = coordinator.configuration.equipment_group
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(group.equipment_group_id))},
        manufacturer=NAME,
        model=_GROUP_MODEL,
        name=group.name,
    )
    async_add_entities([IntelligentClimateConfigurationDegradedSensor(coordinator)])

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
            [
                IntelligentClimateSensorDataDegradedSensor(coordinator, zone),
                IntelligentClimateThermostatDataDegradedSensor(coordinator, zone),
                IntelligentClimateReconcilingSensor(coordinator, zone),
            ],
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


class _ZoneBinarySensor(IntelligentClimateZoneEntity, BinarySensorEntity):
    """Common stable zone binary-sensor placement."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
        key: str,
    ) -> None:
        super().__init__(coordinator, zone)
        group = coordinator.configuration.equipment_group
        self._attr_unique_id = f"{zone.zone_id}:{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(zone.zone_id))},
            manufacturer=NAME,
            model=_ZONE_MODEL,
            name=zone.name,
            via_device=(DOMAIN, str(group.equipment_group_id)),
        )


class IntelligentClimateSensorDataDegradedSensor(_ZoneBinarySensor):
    """Whether required source quality/count is degraded."""

    _attr_translation_key = "sensor_data_degraded"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        super().__init__(coordinator, zone, "sensor_data_degraded")

    @property
    @override
    def is_on(self) -> bool:
        observation = self.zone_observation
        return observation is None or observation.sensor_data_degraded


class IntelligentClimateThermostatDataDegradedSensor(_ZoneBinarySensor):
    """Whether required thermostat data is degraded."""

    _attr_translation_key = "thermostat_data_degraded"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        super().__init__(coordinator, zone, "thermostat_data_degraded")

    @property
    @override
    def is_on(self) -> bool:
        observation = self.zone_observation
        return observation is None or observation.thermostat_data_degraded


class IntelligentClimateReconcilingSensor(_ZoneBinarySensor):
    """Whether startup/reload reconciliation is active."""

    _attr_translation_key = "reconciling"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        super().__init__(coordinator, zone, "reconciling")

    @property
    @override
    def is_on(self) -> bool:
        return self.coordinator.data.reconciling


class IntelligentClimateConfigurationDegradedSensor(
    CoordinatorEntity[IntelligentClimateCoordinator],
    BinarySensorEntity,
):
    """Whether the entry has an actionable configuration issue."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "configuration_degraded"

    def __init__(self, coordinator: IntelligentClimateCoordinator) -> None:
        super().__init__(coordinator)
        group = coordinator.configuration.equipment_group
        self._attr_unique_id = f"{group.equipment_group_id}:configuration_degraded"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(group.equipment_group_id))},
            manufacturer=NAME,
            model=_GROUP_MODEL,
            name=group.name,
        )

    @property
    @override
    def is_on(self) -> bool:
        actionable = {
            IssueCode.NO_ZONES_CONFIGURED,
            IssueCode.MISSING_ENTITY,
            IssueCode.INCOMPATIBLE_ENTITY,
            IssueCode.MIGRATION_FAILED,
        }
        return (
            self.coordinator.configuration.state
            is not RuntimeConfigurationState.CONFIGURED
            or bool(actionable & set(self.coordinator.issue_manager.active_issue_codes))
        )
