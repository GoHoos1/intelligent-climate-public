"""Configuration-time validation for Home Assistant entity references."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant, split_entity_id, valid_entity_id

from .const import DOMAIN
from .models import (
    EquipmentRelationship,
    SchemaValidationError,
    TemperatureSource,
    ThermostatRole,
    decode_equipment_group_document,
)

CLIMATE_DOMAIN = "climate"
SENSOR_DOMAIN = "sensor"
CURRENT_TEMPERATURE_ATTRIBUTE = "current_temperature"


class EntityValidationCode(StrEnum):
    """Translated validation failures exposed by config flows."""

    MISSING_ENTITY = "missing_entity"
    WRONG_DOMAIN = "wrong_domain"
    WRONG_DEVICE_CLASS = "wrong_device_class"
    DUPLICATE_THERMOSTAT_OWNER = "duplicate_thermostat_owner"
    DUPLICATE_TEMPERATURE_SOURCE = "duplicate_temperature_source"
    NO_TEMPERATURE_SOURCES = "no_temperature_sources"
    INVALID_PARENT_THERMOSTAT = "invalid_parent_thermostat"
    INVALID_EXISTING_CONFIGURATION = "invalid_existing_configuration"
    INVALID_ENTITY_SELECTION = "invalid_entity_selection"


class EntityValidationError(ValueError):
    """An entity reference failed configuration-time validation."""

    def __init__(self, code: EntityValidationCode) -> None:
        """Initialize a translated validation failure."""
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True, slots=True)
class TemperatureBinding:
    """A validated temperature entity and its authoritative attribute."""

    entity_id: str
    attribute: str | None


def parent_thermostat_entity_id(entry: config_entries.ConfigEntry) -> str:
    """Decode and return the one supported Task 5 parent thermostat."""
    group = decode_equipment_group_document(
        entry.data,
        version=entry.version,
        minor_version=entry.minor_version,
    ).equipment_group
    if (
        group.relationship is not EquipmentRelationship.SINGLE_SYSTEM
        or group.shared_policy is not None
        or len(group.thermostats) != 1
        or group.thermostats[0].role is not ThermostatRole.PRIMARY
    ):
        raise EntityValidationError(EntityValidationCode.INVALID_PARENT_THERMOSTAT)
    return group.thermostats[0].entity_id


def validate_live_thermostat_selection(
    hass: HomeAssistant,
    value: object,
    *,
    exclude_entry_id: str | None = None,
) -> str:
    """Validate a current interactive climate selection and exclusive ownership."""
    entity_id = _entity_id(value)
    if split_entity_id(entity_id)[0] != CLIMATE_DOMAIN:
        raise EntityValidationError(EntityValidationCode.WRONG_DOMAIN)
    if hass.states.get(entity_id) is None:
        raise EntityValidationError(EntityValidationCode.MISSING_ENTITY)
    _validate_thermostat_ownership(
        hass,
        entity_id,
        exclude_entry_id=exclude_entry_id,
    )
    return entity_id


def validate_persisted_thermostat_reference(
    hass: HomeAssistant,
    value: object,
    *,
    exclude_entry_id: str,
) -> str:
    """Validate a persisted climate reference without requiring a live state."""
    entity_id = _entity_id(value)
    if split_entity_id(entity_id)[0] != CLIMATE_DOMAIN:
        raise EntityValidationError(EntityValidationCode.WRONG_DOMAIN)
    _validate_thermostat_ownership(
        hass,
        entity_id,
        exclude_entry_id=exclude_entry_id,
    )
    return entity_id


def _validate_thermostat_ownership(
    hass: HomeAssistant,
    entity_id: str,
    *,
    exclude_entry_id: str | None,
) -> None:
    """Reject ownership by another structurally valid integration entry."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.entry_id == exclude_entry_id:
            continue
        try:
            group = decode_equipment_group_document(
                entry.data,
                version=entry.version,
                minor_version=entry.minor_version,
            ).equipment_group
        except (KeyError, SchemaValidationError) as err:
            raise EntityValidationError(
                EntityValidationCode.INVALID_EXISTING_CONFIGURATION
            ) from err
        if any(binding.entity_id == entity_id for binding in group.thermostats):
            raise EntityValidationError(EntityValidationCode.DUPLICATE_THERMOSTAT_OWNER)


def validate_live_temperature_selection(
    hass: HomeAssistant,
    value: object,
) -> tuple[TemperatureBinding, ...]:
    """Validate one or more selected temperature-source entities."""
    if not isinstance(value, list):
        raise EntityValidationError(EntityValidationCode.INVALID_ENTITY_SELECTION)
    if not value:
        raise EntityValidationError(EntityValidationCode.NO_TEMPERATURE_SOURCES)

    bindings: list[TemperatureBinding] = []
    seen: set[tuple[str, str | None]] = set()
    for raw_entity_id in value:
        entity_id = _entity_id(raw_entity_id)
        domain = split_entity_id(entity_id)[0]
        state = hass.states.get(entity_id)
        if state is None:
            raise EntityValidationError(EntityValidationCode.MISSING_ENTITY)
        if domain == CLIMATE_DOMAIN:
            attribute = CURRENT_TEMPERATURE_ATTRIBUTE
        elif domain == SENSOR_DOMAIN:
            if state.attributes.get(ATTR_DEVICE_CLASS) != SensorDeviceClass.TEMPERATURE:
                raise EntityValidationError(EntityValidationCode.WRONG_DEVICE_CLASS)
            attribute = None
        else:
            raise EntityValidationError(EntityValidationCode.WRONG_DOMAIN)

        key = (entity_id, attribute)
        if key in seen:
            raise EntityValidationError(
                EntityValidationCode.DUPLICATE_TEMPERATURE_SOURCE
            )
        seen.add(key)
        bindings.append(TemperatureBinding(entity_id, attribute))
    return tuple(bindings)


def validate_persisted_temperature_sources(
    sources: tuple[TemperatureSource, ...],
) -> None:
    """Validate persisted source structure without requiring live states."""
    if not sources:
        raise EntityValidationError(EntityValidationCode.NO_TEMPERATURE_SOURCES)

    seen: set[tuple[str, str | None]] = set()
    for source in sources:
        entity_id = _entity_id(source.entity_id)
        domain = split_entity_id(entity_id)[0]
        if domain == CLIMATE_DOMAIN:
            if source.attribute != CURRENT_TEMPERATURE_ATTRIBUTE:
                raise EntityValidationError(
                    EntityValidationCode.INVALID_ENTITY_SELECTION
                )
        elif domain == SENSOR_DOMAIN:
            if source.attribute is not None:
                raise EntityValidationError(
                    EntityValidationCode.INVALID_ENTITY_SELECTION
                )
        else:
            raise EntityValidationError(EntityValidationCode.WRONG_DOMAIN)

        key = (entity_id, source.attribute)
        if key in seen:
            raise EntityValidationError(
                EntityValidationCode.DUPLICATE_TEMPERATURE_SOURCE
            )
        seen.add(key)


def _entity_id(value: object) -> str:
    """Require a concrete Home Assistant entity ID rather than a registry UUID."""
    if not isinstance(value, str) or not valid_entity_id(value):
        raise EntityValidationError(EntityValidationCode.INVALID_ENTITY_SELECTION)
    return value
