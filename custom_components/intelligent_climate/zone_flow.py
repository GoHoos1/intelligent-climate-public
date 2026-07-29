"""Zone config-subentry flow for Intelligent Climate."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntityFilterSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
)

from .const import (
    CONF_SOURCE_ENABLED,
    CONF_SOURCE_OFFSET_C,
    CONF_SOURCE_PRIORITY,
    CONF_SOURCE_WEIGHT,
    CONF_TEMPERATURE_SOURCES,
    CONF_ZONE_NAME,
    CONF_ZONE_THERMOSTAT_ENTITY_IDS,
    SUBENTRY_TYPE_ZONE,
)
from .models import (
    EquipmentGroupDocument,
    EquipmentRelationship,
    ObservationSourceId,
    SchemaValidationError,
    SharedEquipmentPolicy,
    TemperatureSource,
    ZoneConfig,
    ZoneId,
    decode_equipment_group_document,
    decode_zone_config,
    encode_equipment_group_document,
    encode_zone_config,
)
from .validation import (
    CLIMATE_DOMAIN,
    SENSOR_DOMAIN,
    EntityValidationCode,
    EntityValidationError,
    TemperatureBinding,
    parent_thermostat_entity_ids,
    validate_live_temperature_selection,
    validate_live_thermostat_selections,
)

_ZONE_FIELDS = {
    CONF_ZONE_NAME,
    CONF_ZONE_THERMOSTAT_ENTITY_IDS,
    CONF_TEMPERATURE_SOURCES,
}
_SOURCE_FIELDS = {
    CONF_SOURCE_OFFSET_C,
    CONF_SOURCE_WEIGHT,
    CONF_SOURCE_PRIORITY,
    CONF_SOURCE_ENABLED,
}
_PERSISTED_ZONE_ERRORS = (KeyError, SchemaValidationError)

_ZONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ZONE_NAME): TextSelector(),
        vol.Required(CONF_ZONE_THERMOSTAT_ENTITY_IDS): EntitySelector(
            EntitySelectorConfig(
                multiple=True,
                filter=EntityFilterSelectorConfig(domain=CLIMATE_DOMAIN),
            )
        ),
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

_SOURCE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_SOURCE_OFFSET_C): NumberSelector(
            NumberSelectorConfig(
                min=-20,
                max=20,
                step=0.1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_SOURCE_WEIGHT): NumberSelector(
            NumberSelectorConfig(
                min=0.1,
                step=0.1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_SOURCE_PRIORITY): NumberSelector(
            NumberSelectorConfig(
                min=0,
                step=1,
                mode=NumberSelectorMode.BOX,
            )
        ),
        vol.Required(CONF_SOURCE_ENABLED): BooleanSelector(),
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


def _parent_thermostats(
    hass: Any,
    entry: config_entries.ConfigEntry,
) -> tuple[str, ...]:
    """Validate every live thermostat owned by the parent entry."""
    entity_ids = parent_thermostat_entity_ids(entry)
    selected = validate_live_thermostat_selections(
        hass,
        list(entity_ids),
        exclude_entry_id=entry.entry_id,
    )
    if selected != entity_ids:
        raise EntityValidationError(EntityValidationCode.INVALID_PARENT_THERMOSTAT)
    return selected


def _zone_thermostats(
    hass: Any,
    value: object,
    *,
    parent_entity_ids: tuple[str, ...],
    entry_id: str,
) -> tuple[str, ...]:
    """Validate one nonempty configured-order subset of parent thermostats."""
    selected = validate_live_thermostat_selections(
        hass,
        value,
        exclude_entry_id=entry_id,
    )
    if not set(selected).issubset(parent_entity_ids):
        raise EntityValidationError(EntityValidationCode.INVALID_ENTITY_SELECTION)
    return tuple(item for item in parent_entity_ids if item in selected)


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
    thermostat_entity_ids: tuple[str, ...],
    bindings: tuple[TemperatureBinding, ...],
) -> tuple[ZoneConfig, dict[str, Any]]:
    zone = ZoneConfig(
        zone_id=ZoneId.new(),
        name=name,
        thermostat_entity_ids=thermostat_entity_ids,
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
    """Normalize shared priority metadata, then complete the committed reload."""
    matching = tuple(
        subentry
        for subentry in entry.subentries.values()
        if subentry.subentry_type == SUBENTRY_TYPE_ZONE
        and subentry.unique_id == zone_id
    )
    if len(matching) != 1:
        return
    document = decode_equipment_group_document(
        entry.data,
        version=entry.version,
        minor_version=entry.minor_version,
    )
    group = document.equipment_group
    if group.relationship is EquipmentRelationship.SHARED_ZONED:
        zone_ids = tuple(
            decode_zone_subentry(subentry).zone_id
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_ZONE
        )
        existing_policy = group.shared_policy
        assert existing_policy is not None
        retained = tuple(
            item for item in existing_policy.zone_priority_order if item in zone_ids
        )
        added = tuple(item for item in zone_ids if item not in retained)
        updated_group = replace(
            group,
            shared_policy=SharedEquipmentPolicy(
                zone_priority_order=(*retained, *added),
                conflict_policy=existing_policy.conflict_policy,
            ),
        )
        hass.config_entries.async_update_entry(
            entry,
            data=dict(
                encode_equipment_group_document(EquipmentGroupDocument(updated_group))
            ),
        )
    if (
        entry.state
        not in (
            config_entries.ConfigEntryState.LOADED,
            config_entries.ConfigEntryState.SETUP_RETRY,
        )
        or hass.is_stopping
    ):
        return
    entry.async_cancel_retry_setup()
    await hass.config_entries.async_reload(entry.entry_id)


class ZoneSubentryFlowHandler(config_entries.ConfigSubentryFlow):
    """Add and reconfigure fully bound observation-only zones."""

    _pending_action: str
    _pending_zone: ZoneConfig
    _pending_sources: list[TemperatureSource]
    _pending_source_index: int

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.SubentryFlowResult:
        """Add a fully selected zone beneath its equipment group."""
        errors: dict[str, str] = {}
        entry: config_entries.ConfigEntry | None = None
        parent_thermostats: tuple[str, ...] = ()

        try:
            entry = self._get_entry()
            parent_thermostats = _parent_thermostats(self.hass, entry)
        except config_entries.ConfigError:
            errors["base"] = "invalid_zone_data"
        except (KeyError, SchemaValidationError, EntityValidationError) as err:
            _set_parent_error(errors, err)

        if user_input is not None and entry is not None and not errors:
            if set(user_input) != _ZONE_FIELDS:
                errors["base"] = "invalid_input"
            try:
                name = _normalized_name(user_input.get(CONF_ZONE_NAME))
            except ValueError:
                errors[CONF_ZONE_NAME] = "invalid_name"
            try:
                zone_thermostats = _zone_thermostats(
                    self.hass,
                    user_input.get(CONF_ZONE_THERMOSTAT_ENTITY_IDS),
                    parent_entity_ids=parent_thermostats,
                    entry_id=entry.entry_id,
                )
            except EntityValidationError as err:
                errors[CONF_ZONE_THERMOSTAT_ENTITY_IDS] = err.code.value
            try:
                bindings = validate_live_temperature_selection(
                    self.hass,
                    user_input.get(CONF_TEMPERATURE_SOURCES),
                )
            except EntityValidationError as err:
                errors[CONF_TEMPERATURE_SOURCES] = err.code.value
            if not errors:
                try:
                    if _has_duplicate_name(entry, name):
                        errors[CONF_ZONE_NAME] = "duplicate_name"
                except _PERSISTED_ZONE_ERRORS:
                    errors["base"] = "invalid_zone_data"
            if not errors:
                try:
                    zone, _data = _new_zone(name, zone_thermostats, bindings)
                except SchemaValidationError:
                    errors["base"] = "invalid_zone_data"
                else:
                    self._begin_source_configuration("add", zone)
                    return await self.async_step_source()

        return self.async_show_form(
            step_id="user",
            data_schema=self._zone_schema(
                zone=None,
                parent_thermostats=parent_thermostats,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.SubentryFlowResult:
        """Update zone membership, sources, and per-source metadata."""
        try:
            entry = self._get_entry()
            subentry = self._get_reconfigure_subentry()
            zone = decode_zone_subentry(subentry)
            parent_thermostats = _parent_thermostats(self.hass, entry)
        except config_entries.ConfigError:
            return self.async_abort(reason="invalid_zone_data")
        except _PERSISTED_ZONE_ERRORS:
            return self.async_abort(reason="invalid_zone_data")
        except EntityValidationError as err:
            return self.async_abort(reason=err.code.value)

        if not set(zone.thermostat_entity_ids).issubset(parent_thermostats):
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
            try:
                zone_thermostats = _zone_thermostats(
                    self.hass,
                    user_input.get(CONF_ZONE_THERMOSTAT_ENTITY_IDS),
                    parent_entity_ids=parent_thermostats,
                    entry_id=entry.entry_id,
                )
            except EntityValidationError as err:
                errors[CONF_ZONE_THERMOSTAT_ENTITY_IDS] = err.code.value
            try:
                bindings = validate_live_temperature_selection(
                    self.hass,
                    user_input.get(CONF_TEMPERATURE_SOURCES),
                )
            except EntityValidationError as err:
                errors[CONF_TEMPERATURE_SOURCES] = err.code.value
            if not errors:
                try:
                    if _has_duplicate_name(
                        entry,
                        name,
                        exclude_subentry_id=subentry.subentry_id,
                    ):
                        errors[CONF_ZONE_NAME] = "duplicate_name"
                except _PERSISTED_ZONE_ERRORS:
                    errors["base"] = "invalid_zone_data"
            if not errors:
                updated_zone = replace(
                    zone,
                    name=name,
                    thermostat_entity_ids=zone_thermostats,
                    temperature_sources=_updated_temperature_sources(
                        zone.temperature_sources,
                        bindings,
                    ),
                )
                if not self._all_parent_thermostats_assigned(
                    entry,
                    updated_zone,
                    replacing_subentry_id=subentry.subentry_id,
                ):
                    errors[CONF_ZONE_THERMOSTAT_ENTITY_IDS] = "unassigned_thermostat"
                else:
                    self._begin_source_configuration("reconfigure", updated_zone)
                    return await self.async_step_source()

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._zone_schema(
                zone=zone,
                parent_thermostats=parent_thermostats,
            ),
            errors=errors,
        )

    async def async_step_source(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.SubentryFlowResult:
        """Edit one configured temperature source without raw-file changes."""
        source = self._pending_sources[self._pending_source_index]
        errors: dict[str, str] = {}
        if user_input is not None:
            if set(user_input) != _SOURCE_FIELDS:
                errors["base"] = "invalid_input"
            try:
                offset = _finite_number(user_input.get(CONF_SOURCE_OFFSET_C))
            except ValueError:
                errors[CONF_SOURCE_OFFSET_C] = "invalid_source_offset"
            try:
                weight = _finite_number(user_input.get(CONF_SOURCE_WEIGHT))
                if weight <= 0:
                    raise ValueError
            except ValueError:
                errors[CONF_SOURCE_WEIGHT] = "invalid_source_weight"
            try:
                priority = _nonnegative_integer(user_input.get(CONF_SOURCE_PRIORITY))
            except ValueError:
                errors[CONF_SOURCE_PRIORITY] = "invalid_source_priority"
            enabled_value = user_input.get(CONF_SOURCE_ENABLED)
            if not isinstance(enabled_value, bool):
                errors[CONF_SOURCE_ENABLED] = "invalid_source_enabled"
            if not errors:
                assert isinstance(enabled_value, bool)
                self._pending_sources[self._pending_source_index] = replace(
                    source,
                    offset_c=offset,
                    weight=weight,
                    priority=priority,
                    enabled=enabled_value,
                )
                self._pending_source_index += 1
                if self._pending_source_index < len(self._pending_sources):
                    return await self.async_step_source()
                self._pending_zone = replace(
                    self._pending_zone,
                    temperature_sources=tuple(self._pending_sources),
                )
                return self._finish_pending_zone()

        schema = self.add_suggested_values_to_schema(
            _SOURCE_SCHEMA,
            {
                CONF_SOURCE_OFFSET_C: source.offset_c,
                CONF_SOURCE_WEIGHT: source.weight,
                CONF_SOURCE_PRIORITY: source.priority,
                CONF_SOURCE_ENABLED: source.enabled,
            },
        )
        return self.async_show_form(
            step_id="source",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "source": source.entity_id,
                "position": str(self._pending_source_index + 1),
                "count": str(len(self._pending_sources)),
            },
        )

    def _zone_schema(
        self,
        *,
        zone: ZoneConfig | None,
        parent_thermostats: tuple[str, ...],
    ) -> vol.Schema:
        values: dict[str, object] = {
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: (
                list(parent_thermostats)
                if zone is None
                else list(zone.thermostat_entity_ids)
            )
        }
        if zone is not None:
            values[CONF_ZONE_NAME] = zone.name
            values[CONF_TEMPERATURE_SOURCES] = [
                source.entity_id for source in zone.temperature_sources
            ]
        return self.add_suggested_values_to_schema(_ZONE_SCHEMA, values)

    def _begin_source_configuration(self, action: str, zone: ZoneConfig) -> None:
        self._pending_action = action
        self._pending_zone = zone
        self._pending_sources = list(zone.temperature_sources)
        self._pending_source_index = 0

    def _finish_pending_zone(self) -> config_entries.SubentryFlowResult:
        try:
            encoded = dict(encode_zone_config(self._pending_zone))
            if decode_zone_config(encoded) != self._pending_zone:
                raise SchemaValidationError("zone", "must round-trip")
            entry = self._get_entry()
            group = decode_equipment_group_document(
                entry.data,
                version=entry.version,
                minor_version=entry.minor_version,
            ).equipment_group
        except config_entries.ConfigError, KeyError, SchemaValidationError:
            return self.async_abort(reason="invalid_zone_data")

        if self._pending_action == "add":
            result = self.async_create_entry(
                title=self._pending_zone.name,
                data=encoded,
                unique_id=str(self._pending_zone.zone_id),
            )
            if (
                entry.state
                in (
                    config_entries.ConfigEntryState.LOADED,
                    config_entries.ConfigEntryState.SETUP_RETRY,
                )
                or group.relationship is EquipmentRelationship.SHARED_ZONED
            ):
                self.hass.async_create_task(
                    _async_reload_after_zone_commit(
                        self.hass,
                        entry,
                        str(self._pending_zone.zone_id),
                    ),
                    name="reload after zone creation",
                    eager_start=False,
                )
            return result

        try:
            subentry = self._get_reconfigure_subentry()
        except config_entries.ConfigError:
            return self.async_abort(reason="invalid_zone_data")
        return self.async_update_reload_and_abort(
            entry,
            subentry,
            title=self._pending_zone.name,
            data=encoded,
            reload_even_if_entry_is_unchanged=False,
        )

    def _all_parent_thermostats_assigned(
        self,
        entry: config_entries.ConfigEntry,
        updated_zone: ZoneConfig,
        *,
        replacing_subentry_id: str,
    ) -> bool:
        parent = set(parent_thermostat_entity_ids(entry))
        assigned = set(updated_zone.thermostat_entity_ids)
        for subentry in entry.subentries.values():
            if (
                subentry.subentry_type != SUBENTRY_TYPE_ZONE
                or subentry.subentry_id == replacing_subentry_id
            ):
                continue
            assigned.update(decode_zone_subentry(subentry).thermostat_entity_ids)
        return assigned == parent


def _finite_number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError
    result = float(value)
    if not math.isfinite(result):
        raise ValueError
    return result


def _nonnegative_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError
    result = float(value)
    if not math.isfinite(result) or result < 0 or not result.is_integer():
        raise ValueError
    return int(result)
