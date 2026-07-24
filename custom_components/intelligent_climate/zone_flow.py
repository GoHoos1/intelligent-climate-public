"""Zone config-subentry flow for Intelligent Climate."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    EntityFilterSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    TextSelector,
)

from .const import CONF_TEMPERATURE_SOURCES, CONF_ZONE_NAME, SUBENTRY_TYPE_ZONE
from .models import (
    ObservationSourceId,
    SchemaValidationError,
    TemperatureSource,
    ZoneConfig,
    ZoneId,
    decode_zone_config,
    encode_zone_config,
)
from .validation import (
    CLIMATE_DOMAIN,
    SENSOR_DOMAIN,
    EntityValidationCode,
    EntityValidationError,
    TemperatureBinding,
    parent_thermostat_entity_id,
    validate_live_temperature_selection,
    validate_live_thermostat_selection,
)

_ZONE_FIELDS = {CONF_ZONE_NAME, CONF_TEMPERATURE_SOURCES}
_PERSISTED_ZONE_ERRORS = (KeyError, SchemaValidationError)

_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE_NAME): TextSelector(),
        vol.Required(CONF_TEMPERATURE_SOURCES): EntitySelector(
            EntitySelectorConfig(
                multiple=True,
                filter=[
                    EntityFilterSelectorConfig(domain=CLIMATE_DOMAIN),
                    EntityFilterSelectorConfig(
                        domain=SENSOR_DOMAIN,
                        device_class=SensorDeviceClass.TEMPERATURE,
                    ),
                ],
            )
        ),
    }
)


def decode_zone_subentry(subentry: config_entries.ConfigSubentry) -> ZoneConfig:
    """Decode a zone subentry and verify its persisted stable identity."""
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
    return zone


def _normalized_name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("zone name must be a nonblank string")
    return value.strip()


def _has_duplicate_name(
    entry: config_entries.ConfigEntry,
    name: str,
    *,
    exclude_subentry_id: str | None = None,
) -> bool:
    normalized_name = name.casefold()
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            raise SchemaValidationError(
                "subentry_type",
                "unsupported config subentry type",
            )
        if subentry.subentry_id == exclude_subentry_id:
            continue
        if decode_zone_subentry(subentry).name.casefold() == normalized_name:
            return True
    return False


def _parent_thermostat(
    hass: Any,
    entry: config_entries.ConfigEntry,
) -> str:
    """Validate the owning parent's one Task 5 thermostat."""
    entity_id = parent_thermostat_entity_id(entry)
    validate_live_thermostat_selection(
        hass,
        entity_id,
        exclude_entry_id=entry.entry_id,
    )
    return entity_id


def _new_temperature_source(binding: TemperatureBinding) -> TemperatureSource:
    """Create one source only after its complete submission has validated."""
    return TemperatureSource(
        source_id=ObservationSourceId.new(),
        entity_id=binding.entity_id,
        attribute=binding.attribute,
        offset_c=0.0,
        weight=1.0,
        priority=0,
        enabled=True,
    )


def _new_zone(
    name: str,
    thermostat_entity_id: str,
    bindings: tuple[TemperatureBinding, ...],
) -> tuple[ZoneConfig, dict[str, Any]]:
    zone = ZoneConfig(
        zone_id=ZoneId.new(),
        name=name,
        thermostat_entity_ids=(thermostat_entity_id,),
        temperature_sources=tuple(_new_temperature_source(item) for item in bindings),
        humidity_sources=(),
        window_door_entity_ids=(),
        occupancy_entity_ids=(),
        stage_entity_ids=(),
        fan_entity_ids=(),
    )
    data = dict(encode_zone_config(zone))
    return decode_zone_config(data), data


def _updated_temperature_sources(
    existing: tuple[TemperatureSource, ...],
    selected: tuple[TemperatureBinding, ...],
) -> tuple[TemperatureSource, ...]:
    """Keep retained source identity/metadata and append only new bindings."""
    selected_by_key = {
        (binding.entity_id, binding.attribute): binding for binding in selected
    }
    retained = tuple(
        source
        for source in existing
        if (source.entity_id, source.attribute) in selected_by_key
    )
    existing_keys = {(source.entity_id, source.attribute) for source in retained}
    added = tuple(
        _new_temperature_source(binding)
        for binding in selected
        if (binding.entity_id, binding.attribute) not in existing_keys
    )
    return (*retained, *added)


def _set_parent_error(errors: dict[str, str], err: Exception) -> None:
    """Map malformed or unsupported persisted parent data to a base error."""
    if (
        isinstance(err, EntityValidationError)
        and err.code is EntityValidationCode.INVALID_EXISTING_CONFIGURATION
    ):
        errors["base"] = err.code.value
    elif isinstance(err, SchemaValidationError | KeyError):
        errors["base"] = EntityValidationCode.INVALID_EXISTING_CONFIGURATION.value
    else:
        errors["base"] = EntityValidationCode.INVALID_PARENT_THERMOSTAT.value


async def _async_reload_after_zone_commit(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
    zone_id: str,
) -> None:
    """Reload only after the flow manager has committed the new subentry."""
    if not any(
        subentry.subentry_type == SUBENTRY_TYPE_ZONE and subentry.unique_id == zone_id
        for subentry in entry.subentries.values()
    ):
        return
    hass.config_entries.async_schedule_reload(entry.entry_id)


class ZoneSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add and reconfigure fully bound observation-only zones."""

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.SubentryFlowResult:
        """Add a fully selected zone beneath its equipment group."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if set(user_input) != _ZONE_FIELDS:
                errors["base"] = "invalid_input"

            try:
                name = _normalized_name(user_input.get(CONF_ZONE_NAME))
            except ValueError:
                errors[CONF_ZONE_NAME] = "invalid_name"

            if not errors:
                try:
                    entry = self._get_entry()
                except config_entries.ConfigError:
                    errors["base"] = "invalid_zone_data"
                else:
                    try:
                        thermostat_entity_id = _parent_thermostat(self.hass, entry)
                    except (
                        KeyError,
                        SchemaValidationError,
                        EntityValidationError,
                    ) as err:
                        _set_parent_error(errors, err)

            if not errors:
                try:
                    duplicate_name = _has_duplicate_name(entry, name)
                except _PERSISTED_ZONE_ERRORS:
                    errors["base"] = "invalid_zone_data"
                else:
                    if duplicate_name:
                        errors[CONF_ZONE_NAME] = "duplicate_name"

            if not errors:
                try:
                    bindings = validate_live_temperature_selection(
                        self.hass,
                        user_input.get(CONF_TEMPERATURE_SOURCES),
                    )
                except EntityValidationError as err:
                    errors[CONF_TEMPERATURE_SOURCES] = err.code.value

            if not errors:
                try:
                    zone, data = _new_zone(name, thermostat_entity_id, bindings)
                except SchemaValidationError:
                    errors["base"] = "invalid_zone_data"
                else:
                    result = self.async_create_entry(
                        title=name,
                        data=data,
                        unique_id=str(zone.zone_id),
                    )
                    entry.async_create_task(
                        self.hass,
                        _async_reload_after_zone_commit(
                            self.hass,
                            entry,
                            str(zone.zone_id),
                        ),
                        name="reload after zone creation",
                        eager_start=False,
                    )
                    return result

        return self.async_show_form(
            step_id="user",
            data_schema=_ZONE_SCHEMA,
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.SubentryFlowResult:
        """Update zone name and selected temperature sources."""
        try:
            entry = self._get_entry()
            subentry = self._get_reconfigure_subentry()
        except config_entries.ConfigError:
            return self.async_abort(reason="invalid_zone_data")

        try:
            zone = decode_zone_subentry(subentry)
            thermostat_entity_id = _parent_thermostat(self.hass, entry)
        except _PERSISTED_ZONE_ERRORS:
            return self.async_abort(reason="invalid_zone_data")
        except EntityValidationError as err:
            return self.async_abort(reason=err.code.value)

        if zone.thermostat_entity_ids != (thermostat_entity_id,):
            return self.async_abort(
                reason=EntityValidationCode.INVALID_EXISTING_CONFIGURATION.value
            )

        errors: dict[str, str] = {}
        if user_input is not None:
            if set(user_input) != _ZONE_FIELDS:
                errors["base"] = "invalid_input"

            try:
                name = _normalized_name(user_input.get(CONF_ZONE_NAME))
            except ValueError:
                errors[CONF_ZONE_NAME] = "invalid_name"

            if not errors:
                try:
                    duplicate_name = _has_duplicate_name(
                        entry,
                        name,
                        exclude_subentry_id=subentry.subentry_id,
                    )
                except _PERSISTED_ZONE_ERRORS:
                    errors["base"] = "invalid_zone_data"
                else:
                    if duplicate_name:
                        errors[CONF_ZONE_NAME] = "duplicate_name"

            if not errors:
                try:
                    bindings = validate_live_temperature_selection(
                        self.hass,
                        user_input.get(CONF_TEMPERATURE_SOURCES),
                    )
                except EntityValidationError as err:
                    errors[CONF_TEMPERATURE_SOURCES] = err.code.value

            if not errors:
                updated_zone = ZoneConfig(
                    zone_id=zone.zone_id,
                    name=name,
                    thermostat_entity_ids=zone.thermostat_entity_ids,
                    temperature_sources=_updated_temperature_sources(
                        zone.temperature_sources,
                        bindings,
                    ),
                    humidity_sources=zone.humidity_sources,
                    window_door_entity_ids=zone.window_door_entity_ids,
                    occupancy_entity_ids=zone.occupancy_entity_ids,
                    stage_entity_ids=zone.stage_entity_ids,
                    fan_entity_ids=zone.fan_entity_ids,
                )
                try:
                    updated_data = dict(encode_zone_config(updated_zone))
                    decoded_updated_zone = decode_zone_config(updated_data)
                    if decoded_updated_zone != updated_zone:
                        raise SchemaValidationError(
                            "zone",
                            "must match the encoded zone",
                        )
                except _PERSISTED_ZONE_ERRORS:
                    errors["base"] = "invalid_zone_data"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        subentry,
                        title=name,
                        data=updated_data,
                        reload_even_if_entry_is_unchanged=False,
                    )

        data_schema = self.add_suggested_values_to_schema(
            _ZONE_SCHEMA,
            {
                CONF_ZONE_NAME: zone.name,
                CONF_TEMPERATURE_SOURCES: [
                    source.entity_id for source in zone.temperature_sources
                ],
            },
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=data_schema,
            errors=errors,
        )
