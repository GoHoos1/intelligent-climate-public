"""Phase 1 observation and diagnostic sensors."""

from __future__ import annotations

from typing import Any, override

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME, SUBENTRY_TYPE_ZONE
from .coordinator import IntelligentClimateCoordinator
from .entity import IntelligentClimateZoneEntity
from .models import (
    ActivityRecord,
    RuntimeConfigurationState,
    ThermostatCapabilityDiscoveryStatus,
    ZoneConfig,
)
from .type_aliases import IntelligentClimateConfigEntry

_ZONE_MODEL = "Climate zone"
_GROUP_MODEL = "Equipment group"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the exact applicable Phase 1 sensor inventory."""
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
    async_add_entities(
        [
            IntelligentClimateEquipmentRelationshipSensor(coordinator),
            IntelligentClimateThermostatCapabilityStatusSensor(coordinator),
        ]
    )

    for zone, subentry in matched_subentries:
        entities: list[SensorEntity] = [
            IntelligentClimateEffectiveTemperatureSensor(coordinator, zone),
            IntelligentClimateValidTemperatureSourcesSensor(coordinator, zone),
            IntelligentClimateOperatingModeSensor(coordinator, zone),
            IntelligentClimateLatestActivitySensor(coordinator, zone),
        ]
        if zone.humidity_sources:
            entities.append(
                IntelligentClimateEffectiveHumiditySensor(coordinator, zone)
            )
        if sum(source.enabled for source in zone.temperature_sources) >= 2:
            entities.append(
                IntelligentClimateTemperatureSpreadSensor(coordinator, zone)
            )
        async_add_entities(
            entities,
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


class _ZoneSensor(IntelligentClimateZoneEntity, SensorEntity):
    """Common stable zone sensor placement."""

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


class IntelligentClimateEffectiveTemperatureSensor(_ZoneSensor):
    """Calculated effective zone temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "effective_temperature"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        super().__init__(coordinator, zone, "effective_temperature")

    @property
    @override
    def native_value(self) -> float | None:
        observation = self.zone_observation
        return None if observation is None else observation.effective_temperature_c


class IntelligentClimateEffectiveHumiditySensor(_ZoneSensor):
    """Calculated effective zone humidity."""

    _attr_device_class = SensorDeviceClass.HUMIDITY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_translation_key = "effective_humidity"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        super().__init__(coordinator, zone, "effective_humidity")

    @property
    @override
    def native_value(self) -> float | None:
        observation = self.zone_observation
        return None if observation is None else observation.effective_humidity_pct


class IntelligentClimateTemperatureSpreadSensor(_ZoneSensor):
    """Current spread across valid zone temperature sources."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_translation_key = "temperature_spread"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        super().__init__(coordinator, zone, "temperature_spread")

    @property
    @override
    def native_value(self) -> float | None:
        observation = self.zone_observation
        return None if observation is None else observation.temperature_spread_c


class IntelligentClimateValidTemperatureSourcesSensor(_ZoneSensor):
    """Number of currently valid zone temperature sources."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_translation_key = "valid_temperature_sources"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        super().__init__(coordinator, zone, "valid_temperature_sources")

    @property
    @override
    def native_value(self) -> int:
        observation = self.zone_observation
        return (
            0 if observation is None else len(observation.valid_temperature_source_ids)
        )


class IntelligentClimateOperatingModeSensor(_ZoneSensor):
    """Current Phase 1 operating mode and runtime reason."""

    _attr_translation_key = "operating_mode"

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        super().__init__(coordinator, zone, "operating_mode")

    @property
    @override
    def native_value(self) -> str:
        return (
            "observe_only"
            if self.coordinator.configuration.options.observation_enabled
            else "disabled"
        )

    @property
    @override
    def extra_state_attributes(self) -> dict[str, str]:
        return {"reason_code": self.coordinator.data.control_state.value}


class IntelligentClimateEquipmentRelationshipSensor(
    CoordinatorEntity[IntelligentClimateCoordinator],
    SensorEntity,
):
    """Descriptive equipment relationship, disabled by default."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "equipment_relationship"

    def __init__(self, coordinator: IntelligentClimateCoordinator) -> None:
        super().__init__(coordinator)
        group = coordinator.configuration.equipment_group
        self._attr_unique_id = f"{group.equipment_group_id}:equipment_relationship"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(group.equipment_group_id))},
            manufacturer=NAME,
            model=_GROUP_MODEL,
            name=group.name,
        )

    @property
    @override
    def native_value(self) -> str:
        return self.coordinator.configuration.equipment_group.relationship.value


class IntelligentClimateThermostatCapabilityStatusSensor(
    CoordinatorEntity[IntelligentClimateCoordinator],
    SensorEntity,
):
    """Bounded aggregate thermostat-capability health."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_translation_key = "thermostat_capability_status"

    def __init__(self, coordinator: IntelligentClimateCoordinator) -> None:
        super().__init__(coordinator)
        group = coordinator.configuration.equipment_group
        self._attr_unique_id = (
            f"{group.equipment_group_id}:thermostat_capability_status"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(group.equipment_group_id))},
            manufacturer=NAME,
            model=_GROUP_MODEL,
            name=group.name,
        )

    @property
    @override
    def native_value(self) -> str:
        statuses = tuple(
            thermostat.capability_discovery.status
            for thermostat in self.coordinator.data.thermostats
        )
        if statuses and all(
            item is ThermostatCapabilityDiscoveryStatus.COMPLETE for item in statuses
        ):
            return ThermostatCapabilityDiscoveryStatus.COMPLETE.value
        if not statuses or all(
            item is ThermostatCapabilityDiscoveryStatus.UNAVAILABLE for item in statuses
        ):
            return ThermostatCapabilityDiscoveryStatus.UNAVAILABLE.value
        return ThermostatCapabilityDiscoveryStatus.PARTIAL.value


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
