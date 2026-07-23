"""Set up the Intelligent Climate observe-only runtime."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .const import PLATFORMS, SUBENTRY_TYPE_ZONE
from .models import (
    DEFAULT_OPTIONS,
    EntryRuntimeConfiguration,
    EquipmentRelationship,
    ObservationSourceId,
    SchemaValidationError,
    ThermostatRole,
    ZoneConfig,
    decode_equipment_group_document,
    decode_options,
    decode_zone_config,
)
from .type_aliases import IntelligentClimateConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _is_empty_zone_skeleton(zone: ZoneConfig) -> bool:
    """Return whether every Task 4 zone binding collection remains empty."""
    return not any(
        (
            zone.thermostat_entity_ids,
            zone.temperature_sources,
            zone.humidity_sources,
            zone.window_door_entity_ids,
            zone.occupancy_entity_ids,
            zone.stage_entity_ids,
            zone.fan_entity_ids,
        )
    )


def _decode_runtime_configuration(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
) -> EntryRuntimeConfiguration:
    """Decode and validate one complete persisted config-entry hierarchy."""
    from .validation import (
        validate_persisted_temperature_sources,
        validate_thermostat_selection,
    )

    equipment_group = decode_equipment_group_document(
        entry.data,
        version=entry.version,
        minor_version=entry.minor_version,
    ).equipment_group
    zone_ids: set[str] = set()
    normalized_names: set[str] = set()
    source_ids: set[ObservationSourceId] = set()
    zones: list[ZoneConfig] = []
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            raise SchemaValidationError(
                "subentry_type",
                "unsupported config subentry type",
            )
        zone = decode_zone_config(subentry.data)
        zone_id = str(zone.zone_id)
        if subentry.unique_id != zone_id or subentry.data.get("zone_id") != zone_id:
            raise SchemaValidationError(
                "zone_id",
                "must match the config subentry unique ID",
            )
        if subentry.title != zone.name:
            raise SchemaValidationError(
                "title",
                "must match the encoded zone name",
            )
        normalized_name = zone.name.casefold()
        if zone_id in zone_ids:
            raise SchemaValidationError("zones", "duplicate zone_id")
        if normalized_name in normalized_names:
            raise SchemaValidationError("zones", "duplicate zone name")
        zone_ids.add(zone_id)
        normalized_names.add(normalized_name)
        zones.append(zone)

    options = (
        decode_options(
            entry.options,
            version=entry.version,
            minor_version=entry.minor_version,
        )
        if entry.options
        else DEFAULT_OPTIONS
    )

    if not equipment_group.thermostats:
        if any(not _is_empty_zone_skeleton(zone) for zone in zones):
            raise SchemaValidationError(
                "zones",
                "partially bound legacy configuration is not supported",
            )
        return EntryRuntimeConfiguration(
            equipment_group=equipment_group,
            zones=tuple(zones),
            options=options,
            transitional_empty_skeleton=True,
        )
    if not zones:
        raise SchemaValidationError(
            "zones",
            "partially bound configuration is not supported",
        )

    if (
        equipment_group.relationship is not EquipmentRelationship.SINGLE_SYSTEM
        or equipment_group.shared_policy is not None
        or len(equipment_group.thermostats) != 1
        or equipment_group.thermostats[0].role is not ThermostatRole.PRIMARY
    ):
        raise SchemaValidationError(
            "equipment_group.thermostats",
            "invalid parent thermostat",
        )
    thermostat_entity_id = equipment_group.thermostats[0].entity_id
    validate_thermostat_selection(
        hass,
        thermostat_entity_id,
        exclude_entry_id=entry.entry_id,
    )
    for zone in zones:
        if zone.thermostat_entity_ids != (thermostat_entity_id,):
            raise SchemaValidationError(
                "thermostat_entity_ids",
                "must contain the owning parent thermostat exactly once",
            )
        validate_persisted_temperature_sources(hass, zone.temperature_sources)
        for source in zone.temperature_sources:
            if source.source_id in source_ids:
                raise SchemaValidationError(
                    "temperature_sources",
                    "duplicate observation source_id",
                )
            source_ids.add(source.source_id)
        for humidity_source in zone.humidity_sources:
            if humidity_source.source_id in source_ids:
                raise SchemaValidationError(
                    "temperature_sources",
                    "duplicate observation source_id",
                )
            source_ids.add(humidity_source.source_id)
    return EntryRuntimeConfiguration(
        equipment_group=equipment_group,
        zones=tuple(zones),
        options=options,
        transitional_empty_skeleton=False,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
) -> bool:
    """Set up an Intelligent Climate config entry."""
    from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

    from .coordinator import IntelligentClimateCoordinator

    try:
        configuration = _decode_runtime_configuration(hass, entry)
    except (KeyError, ValueError) as err:
        raise ConfigEntryError("Invalid Intelligent Climate configuration") from err

    coordinator: IntelligentClimateCoordinator | None = None
    try:
        coordinator = IntelligentClimateCoordinator(hass, entry, configuration)
        await coordinator.async_start()
    except ConfigEntryNotReady as err:
        if coordinator is not None:
            await coordinator.async_shutdown()
        cause = err.__cause__ or err
        raise ConfigEntryError(
            "Invalid Intelligent Climate runtime configuration"
        ) from cause
    except (KeyError, ValueError) as err:
        if coordinator is not None:
            await coordinator.async_shutdown()
        raise ConfigEntryError(
            "Invalid Intelligent Climate runtime configuration"
        ) from err
    assert coordinator is not None
    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as err:
        await coordinator.async_shutdown()
        object.__delattr__(entry, "runtime_data")
        raise ConfigEntryError(
            "Unable to set up the Intelligent Climate climate platform"
        ) from err
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
) -> bool:
    """Unload an Intelligent Climate config entry."""
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return True
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await coordinator.async_shutdown()
    return True
