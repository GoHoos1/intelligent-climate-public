"""UI configuration, options, and parent reconfiguration."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    EntityFilterSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_EQUIPMENT_GROUP_NAME,
    CONF_EQUIPMENT_RELATIONSHIP,
    CONF_EQUIPMENT_TYPE,
    CONF_TEMPERATURE_SOURCES,
    CONF_THERMOSTAT_ENTITY_IDS,
    CONF_ZONE_NAME,
    CONF_ZONE_THERMOSTAT_ENTITY_IDS,
    DOMAIN,
    SUBENTRY_TYPE_ZONE,
)
from .models import (
    DEFAULT_OPTIONS,
    PHASE2_CONFIG_MAJOR_VERSION,
    PHASE2_CONFIG_MINOR_VERSION,
    PHASE2_ZONE_DATA_VERSION,
    AggregationStrategy,
    EquipmentGroupConfig,
    EquipmentGroupDocument,
    EquipmentGroupId,
    EquipmentRelationship,
    EquipmentType,
    IntegrationOptions,
    LogLevelDetail,
    ObservationSourceId,
    SchemaValidationError,
    SharedEquipmentPolicy,
    TemperatureSource,
    ThermostatBinding,
    ThermostatRole,
    ZoneConfig,
    ZoneId,
    decode_configuration_graph,
    encode_equipment_group_document,
    encode_options,
    encode_zone_config,
)
from .schema_compat import (
    decode_active_equipment_group,
    decode_active_observation_options,
    encode_active_equipment_group,
    encode_active_observation_options,
    encode_active_zone,
)
from .validation import (
    CLIMATE_DOMAIN,
    EntityValidationCode,
    EntityValidationError,
    TemperatureBinding,
    validate_live_temperature_selection,
    validate_live_thermostat_selections,
)
from .zone_flow import ZoneSubentryFlowHandler, decode_zone_subentry

_USER_FIELDS = {CONF_EQUIPMENT_GROUP_NAME, CONF_EQUIPMENT_TYPE}
_THERMOSTAT_FIELDS = {CONF_THERMOSTAT_ENTITY_IDS}
_RELATIONSHIP_FIELDS = {CONF_EQUIPMENT_RELATIONSHIP}
_FIRST_ZONE_FIELDS = {
    CONF_ZONE_NAME,
    CONF_ZONE_THERMOSTAT_ENTITY_IDS,
    CONF_TEMPERATURE_SOURCES,
}
_RECONFIGURE_FIELDS = {
    CONF_EQUIPMENT_GROUP_NAME,
    CONF_EQUIPMENT_TYPE,
    CONF_EQUIPMENT_RELATIONSHIP,
    CONF_THERMOSTAT_ENTITY_IDS,
}
_ZONE_MEMBERSHIP_FIELDS = {CONF_ZONE_THERMOSTAT_ENTITY_IDS}

_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EQUIPMENT_GROUP_NAME): TextSelector(),
        vol.Required(CONF_EQUIPMENT_TYPE): SelectSelector(
            SelectSelectorConfig(
                options=[equipment_type.value for equipment_type in EquipmentType],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="equipment_type",
            )
        ),
    }
)

_THERMOSTATS_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_THERMOSTAT_ENTITY_IDS): EntitySelector(
            EntitySelectorConfig(
                multiple=True,
                filter=EntityFilterSelectorConfig(domain=CLIMATE_DOMAIN),
            )
        )
    }
)

_RELATIONSHIP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EQUIPMENT_RELATIONSHIP): SelectSelector(
            SelectSelectorConfig(
                options=[
                    EquipmentRelationship.INDEPENDENT.value,
                    EquipmentRelationship.SHARED_ZONED.value,
                ],
                mode=SelectSelectorMode.DROPDOWN,
                translation_key="equipment_relationship",
            )
        )
    }
)

_FIRST_ZONE_SCHEMA = vol.Schema(
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
                        domain="sensor",
                        device_class="temperature",
                    ),
                ],
            )
        ),
    }
)

_CONFIRM_SCHEMA = vol.Schema({})


def _name(value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError
    return value.strip()


def _equipment_type(value: object) -> EquipmentType:
    if not isinstance(value, str):
        raise ValueError
    return EquipmentType(value)


def _relationship(value: object) -> EquipmentRelationship:
    if not isinstance(value, str):
        raise ValueError
    return EquipmentRelationship(value)


def _positive_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 1 or not numeric.is_integer():
        raise ValueError
    return int(numeric)


def _thermostat_bindings(entity_ids: tuple[str, ...]) -> tuple[ThermostatBinding, ...]:
    return tuple(
        ThermostatBinding(
            entity_id=entity_id,
            role=(ThermostatRole.PRIMARY if index == 0 else ThermostatRole.SECONDARY),
        )
        for index, entity_id in enumerate(entity_ids)
    )


def _temperature_sources(
    bindings: tuple[TemperatureBinding, ...],
) -> tuple[TemperatureSource, ...]:
    return tuple(
        TemperatureSource(
            source_id=ObservationSourceId.new(),
            entity_id=binding.entity_id,
            attribute=binding.attribute,
            offset_c=0.0,
            weight=1.0,
            priority=0,
            enabled=True,
        )
        for binding in bindings
    )


class IntelligentClimateConfigFlow(  # type: ignore[call-arg, unused-ignore]
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Create and reconfigure a complete observation-only equipment graph."""

    VERSION = PHASE2_CONFIG_MAJOR_VERSION
    MINOR_VERSION = PHASE2_CONFIG_MINOR_VERSION

    _pending_name: str
    _pending_equipment_type: EquipmentType
    _pending_thermostats: tuple[str, ...]
    _pending_relationship: EquipmentRelationship
    _pending_zone_name: str
    _pending_zone_thermostats: tuple[str, ...]
    _pending_temperature_bindings: tuple[TemperatureBinding, ...]
    _pending_reconfigure_zones: tuple[ZoneConfig, ...]
    _pending_zone_memberships: dict[ZoneId, tuple[str, ...]]
    _pending_zone_index: int

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: config_entries.ConfigEntry,
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Return the supported child configuration flows."""
        return {SUBENTRY_TYPE_ZONE: ZoneSubentryFlowHandler}

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return the entry-scoped observation options flow."""
        return IntelligentClimateOptionsFlow()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Collect equipment-group descriptive fields."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if set(user_input) != _USER_FIELDS:
                errors["base"] = "invalid_input"
            try:
                name = _name(user_input.get(CONF_EQUIPMENT_GROUP_NAME))
            except ValueError:
                errors[CONF_EQUIPMENT_GROUP_NAME] = "invalid_name"
            try:
                equipment_type = _equipment_type(user_input.get(CONF_EQUIPMENT_TYPE))
            except ValueError:
                errors[CONF_EQUIPMENT_TYPE] = "invalid_equipment_type"
            if not errors:
                self._pending_name = name
                self._pending_equipment_type = equipment_type
                return await self.async_step_thermostats()
        return self.async_show_form(
            step_id="user",
            data_schema=_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_thermostats(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Collect one or more exclusively owned climate entities."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if set(user_input) != _THERMOSTAT_FIELDS:
                errors["base"] = "invalid_input"
            if not errors:
                try:
                    thermostats = validate_live_thermostat_selections(
                        self.hass,
                        user_input.get(CONF_THERMOSTAT_ENTITY_IDS),
                    )
                except EntityValidationError as err:
                    if err.code is EntityValidationCode.INVALID_EXISTING_CONFIGURATION:
                        errors["base"] = err.code.value
                    else:
                        errors[CONF_THERMOSTAT_ENTITY_IDS] = err.code.value
            if not errors:
                self._pending_thermostats = thermostats
                if len(thermostats) == 1:
                    self._pending_relationship = EquipmentRelationship.SINGLE_SYSTEM
                    return await self.async_step_first_zone()
                return await self.async_step_relationship()
        return self.async_show_form(
            step_id="thermostats",
            data_schema=_THERMOSTATS_SCHEMA,
            errors=errors,
        )

    async def async_step_relationship(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Require an explicit relationship for multiple thermostats."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if set(user_input) != _RELATIONSHIP_FIELDS:
                errors["base"] = "invalid_input"
            try:
                relationship = _relationship(
                    user_input.get(CONF_EQUIPMENT_RELATIONSHIP)
                )
            except ValueError:
                errors[CONF_EQUIPMENT_RELATIONSHIP] = "invalid_relationship"
            else:
                if relationship is EquipmentRelationship.SINGLE_SYSTEM:
                    errors[CONF_EQUIPMENT_RELATIONSHIP] = "invalid_relationship"
            if not errors:
                self._pending_relationship = relationship
                return await self.async_step_first_zone()
        return self.async_show_form(
            step_id="relationship",
            data_schema=_RELATIONSHIP_SCHEMA,
            errors=errors,
        )

    async def async_step_first_zone(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Collect the first complete zone before creating the parent entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            if set(user_input) != _FIRST_ZONE_FIELDS:
                errors["base"] = "invalid_input"
            try:
                zone_name = _name(user_input.get(CONF_ZONE_NAME))
            except ValueError:
                errors[CONF_ZONE_NAME] = "invalid_name"
            try:
                zone_thermostats = validate_live_thermostat_selections(
                    self.hass,
                    user_input.get(CONF_ZONE_THERMOSTAT_ENTITY_IDS),
                )
            except EntityValidationError as err:
                errors[CONF_ZONE_THERMOSTAT_ENTITY_IDS] = err.code.value
            else:
                if not set(zone_thermostats).issubset(self._pending_thermostats):
                    errors[CONF_ZONE_THERMOSTAT_ENTITY_IDS] = "thermostat_outside_group"
                elif set(zone_thermostats) != set(self._pending_thermostats):
                    errors[CONF_ZONE_THERMOSTAT_ENTITY_IDS] = "unassigned_thermostat"
            try:
                temperature_bindings = validate_live_temperature_selection(
                    self.hass,
                    user_input.get(CONF_TEMPERATURE_SOURCES),
                )
            except EntityValidationError as err:
                errors[CONF_TEMPERATURE_SOURCES] = err.code.value
            if not errors:
                self._pending_zone_name = zone_name
                self._pending_zone_thermostats = zone_thermostats
                self._pending_temperature_bindings = temperature_bindings
                return await self.async_step_confirm()
        suggested = self.add_suggested_values_to_schema(
            _FIRST_ZONE_SCHEMA,
            {CONF_ZONE_THERMOSTAT_ENTITY_IDS: list(self._pending_thermostats)},
        )
        return self.async_show_form(
            step_id="first_zone",
            data_schema=suggested,
            errors=errors,
        )

    async def async_step_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Create the parent and first subentry as one atomic flow result."""
        if user_input is None:
            return self.async_show_form(
                step_id="confirm",
                data_schema=_CONFIRM_SCHEMA,
                description_placeholders={
                    "equipment_group": self._pending_name,
                    "thermostat_count": str(len(self._pending_thermostats)),
                    "zone": self._pending_zone_name,
                    "relationship": self._pending_relationship.value,
                },
            )
        if user_input:
            return self.async_show_form(
                step_id="confirm",
                data_schema=_CONFIRM_SCHEMA,
                errors={"base": "invalid_input"},
            )

        group_id = EquipmentGroupId.new()
        zone_id = ZoneId.new()
        shared_policy = (
            SharedEquipmentPolicy(
                zone_priority_order=(zone_id,),
                conflict_policy="priority_order",
            )
            if self._pending_relationship is EquipmentRelationship.SHARED_ZONED
            else None
        )
        group = EquipmentGroupConfig(
            equipment_group_id=group_id,
            name=self._pending_name,
            equipment_type=self._pending_equipment_type,
            relationship=self._pending_relationship,
            thermostats=_thermostat_bindings(self._pending_thermostats),
            shared_policy=shared_policy,
        )
        zone = ZoneConfig(
            zone_id=zone_id,
            name=self._pending_zone_name,
            thermostat_entity_ids=self._pending_zone_thermostats,
            temperature_sources=_temperature_sources(
                self._pending_temperature_bindings
            ),
            humidity_sources=(),
            window_door_entity_ids=(),
            occupancy_entity_ids=(),
            stage_entity_ids=(),
            fan_entity_ids=(),
        )
        data = encode_active_equipment_group(
            group,
            version=self.VERSION,
            minor_version=self.MINOR_VERSION,
            current_data=None,
            time_zone=self.hass.config.time_zone,
        )
        zone_data = encode_active_zone(
            zone,
            target_data_version=PHASE2_ZONE_DATA_VERSION,
            current_data=None,
        )
        try:
            decode_configuration_graph(
                dict(encode_equipment_group_document(EquipmentGroupDocument(group))),
                [dict(encode_zone_config(zone))],
            )
        except SchemaValidationError:
            return self.async_abort(reason="invalid_input")
        await self.async_set_unique_id(str(group_id))
        return self.async_create_entry(
            title=self._pending_name,
            data=data,
            options=encode_active_observation_options(
                DEFAULT_OPTIONS,
                version=self.VERSION,
                minor_version=self.MINOR_VERSION,
                current_data=None,
            ),
            subentries=[
                config_entries.ConfigSubentryData(
                    data=zone_data,
                    subentry_type=SUBENTRY_TYPE_ZONE,
                    title=zone.name,
                    unique_id=str(zone.zone_id),
                )
            ],
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Change parent equipment metadata and thermostat membership."""
        entry = self._get_reconfigure_entry()
        try:
            group = decode_active_equipment_group(
                entry.data,
                version=entry.version,
                minor_version=entry.minor_version,
            )
            zones = tuple(
                decode_zone_subentry(subentry)
                for subentry in entry.subentries.values()
                if subentry.subentry_type == SUBENTRY_TYPE_ZONE
            )
        except KeyError, SchemaValidationError:
            return self.async_abort(reason="invalid_existing_configuration")

        errors: dict[str, str] = {}
        if user_input is not None:
            thermostats: tuple[str, ...] = ()
            if set(user_input) != _RECONFIGURE_FIELDS:
                errors["base"] = "invalid_input"
            try:
                name = _name(user_input.get(CONF_EQUIPMENT_GROUP_NAME))
            except ValueError:
                errors[CONF_EQUIPMENT_GROUP_NAME] = "invalid_name"
            try:
                equipment_type = _equipment_type(user_input.get(CONF_EQUIPMENT_TYPE))
            except ValueError:
                errors[CONF_EQUIPMENT_TYPE] = "invalid_equipment_type"
            try:
                thermostats = validate_live_thermostat_selections(
                    self.hass,
                    user_input.get(CONF_THERMOSTAT_ENTITY_IDS),
                    exclude_entry_id=entry.entry_id,
                )
            except EntityValidationError as err:
                errors[CONF_THERMOSTAT_ENTITY_IDS] = err.code.value
            try:
                relationship = _relationship(
                    user_input.get(CONF_EQUIPMENT_RELATIONSHIP)
                )
            except ValueError:
                errors[CONF_EQUIPMENT_RELATIONSHIP] = "invalid_relationship"
            else:
                if thermostats and (len(thermostats) == 1) != (
                    relationship is EquipmentRelationship.SINGLE_SYSTEM
                ):
                    errors[CONF_EQUIPMENT_RELATIONSHIP] = "invalid_relationship"
                if not zones and relationship is EquipmentRelationship.SHARED_ZONED:
                    errors[CONF_EQUIPMENT_RELATIONSHIP] = "shared_requires_zone"

            if not errors:
                self._pending_name = name
                self._pending_equipment_type = equipment_type
                self._pending_thermostats = thermostats
                self._pending_relationship = relationship
                self._pending_reconfigure_zones = zones
                self._pending_zone_memberships = {}
                self._pending_zone_index = 0
                if len(thermostats) == 1 or not zones:
                    for zone in zones:
                        self._pending_zone_memberships[zone.zone_id] = thermostats
                    return self._finish_parent_reconfigure(entry, group)
                return await self.async_step_reconfigure_zone()

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    **_USER_SCHEMA.schema,
                    vol.Required(CONF_EQUIPMENT_RELATIONSHIP): SelectSelector(
                        SelectSelectorConfig(
                            options=[
                                relationship.value
                                for relationship in EquipmentRelationship
                            ],
                            mode=SelectSelectorMode.DROPDOWN,
                            translation_key="equipment_relationship",
                        )
                    ),
                    **_THERMOSTATS_SCHEMA.schema,
                }
            ),
            {
                CONF_EQUIPMENT_GROUP_NAME: group.name,
                CONF_EQUIPMENT_TYPE: group.equipment_type.value,
                CONF_EQUIPMENT_RELATIONSHIP: group.relationship.value,
                CONF_THERMOSTAT_ENTITY_IDS: [
                    item.entity_id for item in group.thermostats
                ],
            },
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reconfigure_zone(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Assign selected parent thermostats to each existing zone."""
        entry = self._get_reconfigure_entry()
        group = decode_active_equipment_group(
            entry.data,
            version=entry.version,
            minor_version=entry.minor_version,
        )
        zone = self._pending_reconfigure_zones[self._pending_zone_index]
        errors: dict[str, str] = {}
        if user_input is not None:
            if set(user_input) != _ZONE_MEMBERSHIP_FIELDS:
                errors["base"] = "invalid_input"
            try:
                selected = validate_live_thermostat_selections(
                    self.hass,
                    user_input.get(CONF_ZONE_THERMOSTAT_ENTITY_IDS),
                    exclude_entry_id=entry.entry_id,
                )
            except EntityValidationError as err:
                errors[CONF_ZONE_THERMOSTAT_ENTITY_IDS] = err.code.value
            else:
                if not set(selected).issubset(self._pending_thermostats):
                    errors[CONF_ZONE_THERMOSTAT_ENTITY_IDS] = "thermostat_outside_group"
            if not errors:
                self._pending_zone_memberships[zone.zone_id] = selected
                self._pending_zone_index += 1
                if self._pending_zone_index < len(self._pending_reconfigure_zones):
                    return await self.async_step_reconfigure_zone()
                assigned = {
                    item
                    for membership in self._pending_zone_memberships.values()
                    for item in membership
                }
                if assigned != set(self._pending_thermostats):
                    self._pending_zone_index = 0
                    self._pending_zone_memberships.clear()
                    return self.async_show_form(
                        step_id="reconfigure_zone",
                        data_schema=self._zone_membership_schema(zone),
                        errors={"base": "unassigned_thermostat"},
                        description_placeholders={"zone": zone.name},
                    )
                return self._finish_parent_reconfigure(entry, group)
        return self.async_show_form(
            step_id="reconfigure_zone",
            data_schema=self._zone_membership_schema(zone),
            errors=errors,
            description_placeholders={"zone": zone.name},
        )

    def _zone_membership_schema(self, zone: ZoneConfig) -> vol.Schema:
        return self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_ZONE_THERMOSTAT_ENTITY_IDS): EntitySelector(
                        EntitySelectorConfig(
                            multiple=True,
                            filter=EntityFilterSelectorConfig(domain=CLIMATE_DOMAIN),
                        )
                    )
                }
            ),
            {
                CONF_ZONE_THERMOSTAT_ENTITY_IDS: [
                    item
                    for item in zone.thermostat_entity_ids
                    if item in self._pending_thermostats
                ]
                or list(self._pending_thermostats)
            },
        )

    def _finish_parent_reconfigure(
        self,
        entry: config_entries.ConfigEntry,
        existing_group: EquipmentGroupConfig,
    ) -> config_entries.ConfigFlowResult:
        zones = tuple(
            replace(
                zone,
                thermostat_entity_ids=self._pending_zone_memberships[zone.zone_id],
            )
            for zone in self._pending_reconfigure_zones
        )
        shared_policy = (
            SharedEquipmentPolicy(
                zone_priority_order=tuple(zone.zone_id for zone in zones),
                conflict_policy=(
                    existing_group.shared_policy.conflict_policy
                    if existing_group.shared_policy is not None
                    else "priority_order"
                ),
            )
            if self._pending_relationship is EquipmentRelationship.SHARED_ZONED
            else None
        )
        group = EquipmentGroupConfig(
            equipment_group_id=existing_group.equipment_group_id,
            name=self._pending_name,
            equipment_type=self._pending_equipment_type,
            relationship=self._pending_relationship,
            thermostats=_thermostat_bindings(self._pending_thermostats),
            shared_policy=shared_policy,
        )
        data = encode_active_equipment_group(
            group,
            version=entry.version,
            minor_version=entry.minor_version,
            current_data=entry.data,
            time_zone=self.hass.config.time_zone,
        )
        subentries_by_zone = {
            decode_zone_subentry(subentry).zone_id: subentry
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_ZONE
        }
        zone_data = [
            encode_active_zone(
                zone,
                target_data_version=(
                    PHASE2_ZONE_DATA_VERSION
                    if entry.version == PHASE2_CONFIG_MAJOR_VERSION
                    else 1
                ),
                current_data=subentries_by_zone[zone.zone_id].data,
            )
            for zone in zones
        ]
        try:
            if zones:
                decode_configuration_graph(
                    dict(
                        encode_equipment_group_document(EquipmentGroupDocument(group))
                    ),
                    [dict(encode_zone_config(zone)) for zone in zones],
                )
        except SchemaValidationError:
            return self.async_abort(reason="invalid_input")

        for zone, encoded in zip(zones, zone_data, strict=True):
            self.hass.config_entries.async_update_subentry(
                entry,
                subentries_by_zone[zone.zone_id],
                data=encoded,
            )
        return self.async_update_reload_and_abort(
            entry,
            title=self._pending_name,
            data=data,
            reload_even_if_entry_is_unchanged=False,
        )


class IntelligentClimateOptionsFlow(config_entries.OptionsFlowWithReload):
    """Edit all Phase 1 observation preferences through the UI."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Validate and save one complete options document."""
        current = (
            decode_active_observation_options(
                self.config_entry.options,
                version=self.config_entry.version,
                minor_version=self.config_entry.minor_version,
            )
            if self.config_entry.options
            else DEFAULT_OPTIONS
        )
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                options = IntegrationOptions(
                    observation_enabled=user_input["observation_enabled"],
                    temperature_strategy=AggregationStrategy(
                        user_input["temperature_strategy"]
                    ),
                    humidity_strategy=AggregationStrategy(
                        user_input["humidity_strategy"]
                    ),
                    min_valid_temperature_sources=_positive_integer(
                        user_input["min_valid_temperature_sources"]
                    ),
                    min_valid_humidity_sources=_positive_integer(
                        user_input["min_valid_humidity_sources"]
                    ),
                    source_stale_after_seconds=_positive_integer(
                        user_input["source_stale_after_seconds"]
                    ),
                    startup_reconciliation_seconds=_positive_integer(
                        user_input["startup_reconciliation_seconds"]
                    ),
                    jump_limit_c_per_5_minutes=user_input["jump_limit_c_per_5_minutes"],
                    outlier_floor_c=user_input["outlier_floor_c"],
                    indoor_temperature_min_c=user_input["indoor_temperature_min_c"],
                    indoor_temperature_max_c=user_input["indoor_temperature_max_c"],
                    history_max_records=_positive_integer(
                        user_input["history_max_records"]
                    ),
                    history_max_age_days=_positive_integer(
                        user_input["history_max_age_days"]
                    ),
                    log_level_detail=LogLevelDetail(user_input["log_level_detail"]),
                )
                encoded = encode_active_observation_options(
                    options,
                    version=self.config_entry.version,
                    minor_version=self.config_entry.minor_version,
                    current_data=self.config_entry.options,
                )
                decode_active_observation_options(
                    encoded,
                    version=self.config_entry.version,
                    minor_version=self.config_entry.minor_version,
                )
            except KeyError, SchemaValidationError, TypeError, ValueError:
                errors["base"] = "invalid_options"
            else:
                return self.async_create_entry(title="", data=encoded)

        schema = self.add_suggested_values_to_schema(
            _options_schema(),
            dict(encode_options(current)),
        )
        return self.async_show_form(
            step_id="init",
            data_schema=schema,
            errors=errors,
        )


def _options_schema() -> vol.Schema:
    strategy = SelectSelector(
        SelectSelectorConfig(
            options=[item.value for item in AggregationStrategy],
            mode=SelectSelectorMode.DROPDOWN,
            translation_key="aggregation_strategy",
        )
    )
    positive_integer = NumberSelector(
        NumberSelectorConfig(
            min=1,
            mode=NumberSelectorMode.BOX,
            step=1,
        )
    )
    positive_number = NumberSelector(
        NumberSelectorConfig(min=0.1, mode=NumberSelectorMode.BOX, step=0.1)
    )
    temperature = NumberSelector(
        NumberSelectorConfig(min=-50, max=100, mode=NumberSelectorMode.BOX, step=0.1)
    )
    return vol.Schema(
        {
            vol.Required("observation_enabled"): BooleanSelector(),
            vol.Required("temperature_strategy"): strategy,
            vol.Required("humidity_strategy"): strategy,
            vol.Required("min_valid_temperature_sources"): positive_integer,
            vol.Required("min_valid_humidity_sources"): positive_integer,
            vol.Required("source_stale_after_seconds"): positive_integer,
            vol.Required("startup_reconciliation_seconds"): positive_integer,
            vol.Required("jump_limit_c_per_5_minutes"): positive_number,
            vol.Required("outlier_floor_c"): positive_number,
            vol.Required("indoor_temperature_min_c"): temperature,
            vol.Required("indoor_temperature_max_c"): temperature,
            vol.Required("history_max_records"): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=500,
                    mode=NumberSelectorMode.BOX,
                    step=1,
                )
            ),
            vol.Required("history_max_age_days"): positive_integer,
            vol.Required("log_level_detail"): SelectSelector(
                SelectSelectorConfig(
                    options=[item.value for item in LogLevelDetail],
                    mode=SelectSelectorMode.DROPDOWN,
                    translation_key="log_level_detail",
                )
            ),
        }
    )
