"""Config flow for Intelligent Climate."""

from __future__ import annotations

from contextlib import suppress
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    EntityFilterSelectorConfig,
    EntitySelector,
    EntitySelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
)

from .const import (
    CONF_EQUIPMENT_GROUP_NAME,
    CONF_EQUIPMENT_TYPE,
    CONF_THERMOSTAT_ENTITY_ID,
    DOMAIN,
    SUBENTRY_TYPE_ZONE,
)
from .models import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
    EquipmentGroupConfig,
    EquipmentGroupDocument,
    EquipmentGroupId,
    EquipmentRelationship,
    EquipmentType,
    SchemaValidationError,
    ThermostatBinding,
    ThermostatRole,
    decode_equipment_group_document,
    encode_equipment_group_document,
)
from .validation import (
    CLIMATE_DOMAIN,
    EntityValidationCode,
    EntityValidationError,
    validate_thermostat_selection,
)
from .zone_flow import ZoneSubentryFlowHandler

_USER_FIELDS = {CONF_EQUIPMENT_GROUP_NAME, CONF_EQUIPMENT_TYPE}
_THERMOSTAT_FIELDS = {CONF_THERMOSTAT_ENTITY_ID}

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

_THERMOSTAT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_THERMOSTAT_ENTITY_ID): EntitySelector(
            EntitySelectorConfig(
                filter=EntityFilterSelectorConfig(domain=CLIMATE_DOMAIN)
            )
        )
    }
)


class IntelligentClimateConfigFlow(  # type: ignore[call-arg, unused-ignore]
    config_entries.ConfigFlow,
    domain=DOMAIN,
):
    """Create an observation-only equipment group with one thermostat."""

    VERSION = CONFIG_ENTRY_MAJOR_VERSION
    MINOR_VERSION = CONFIG_ENTRY_MINOR_VERSION

    _pending_name: str
    _pending_equipment_type: EquipmentType

    @classmethod
    @callback
    def async_get_supported_subentry_types(
        cls,
        config_entry: config_entries.ConfigEntry,
    ) -> dict[str, type[config_entries.ConfigSubentryFlow]]:
        """Return the supported child configuration flows."""
        return {SUBENTRY_TYPE_ZONE: ZoneSubentryFlowHandler}

    async def async_on_create_entry(
        self,
        result: config_entries.ConfigFlowResult,
    ) -> config_entries.ConfigFlowResult:
        """Start first-zone configuration after the parent entry exists."""
        subentry_result = await self.hass.config_entries.subentries.async_init(
            (result["result"].entry_id, SUBENTRY_TYPE_ZONE),
            context=config_entries.SubentryFlowContext(
                source=config_entries.SOURCE_USER
            ),
        )
        result["next_flow"] = (
            config_entries.FlowType.CONFIG_SUBENTRIES_FLOW,
            subentry_result["flow_id"],
        )
        return result

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Collect equipment-group descriptive fields."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if set(user_input) != _USER_FIELDS:
                errors["base"] = "invalid_input"

            raw_name = user_input.get(CONF_EQUIPMENT_GROUP_NAME)
            if not isinstance(raw_name, str) or not raw_name.strip():
                errors[CONF_EQUIPMENT_GROUP_NAME] = "invalid_name"

            raw_equipment_type = user_input.get(CONF_EQUIPMENT_TYPE)
            equipment_type: EquipmentType | None = None
            if isinstance(raw_equipment_type, str):
                with suppress(ValueError):
                    equipment_type = EquipmentType(raw_equipment_type)
            if equipment_type is None:
                errors[CONF_EQUIPMENT_TYPE] = "invalid_equipment_type"

            if not errors:
                assert isinstance(raw_name, str)
                assert equipment_type is not None
                self._pending_name = raw_name.strip()
                self._pending_equipment_type = equipment_type
                return await self.async_step_thermostat()

        return self.async_show_form(
            step_id="user",
            data_schema=_USER_SCHEMA,
            errors=errors,
        )

    async def async_step_thermostat(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Collect and validate the equipment group's one climate entity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if set(user_input) != _THERMOSTAT_FIELDS:
                errors["base"] = "invalid_input"

            if not errors:
                try:
                    selected_entity_id = validate_thermostat_selection(
                        self.hass,
                        user_input.get(CONF_THERMOSTAT_ENTITY_ID),
                    )
                except EntityValidationError as err:
                    if err.code is EntityValidationCode.INVALID_EXISTING_CONFIGURATION:
                        errors["base"] = err.code.value
                    else:
                        errors[CONF_THERMOSTAT_ENTITY_ID] = err.code.value

            if not errors:
                name = self._pending_name
                equipment_group_id = EquipmentGroupId.new()
                document = EquipmentGroupDocument(
                    equipment_group=EquipmentGroupConfig(
                        equipment_group_id=equipment_group_id,
                        name=name,
                        equipment_type=self._pending_equipment_type,
                        relationship=EquipmentRelationship.SINGLE_SYSTEM,
                        thermostats=(
                            ThermostatBinding(
                                entity_id=selected_entity_id,
                                role=ThermostatRole.PRIMARY,
                            ),
                        ),
                        shared_policy=None,
                    )
                )
                try:
                    data = dict(encode_equipment_group_document(document))
                    decode_equipment_group_document(data)
                except SchemaValidationError:
                    errors["base"] = "invalid_input"
                else:
                    await self.async_set_unique_id(str(equipment_group_id))
                    return self.async_create_entry(title=name, data=data)

        return self.async_show_form(
            step_id="thermostat",
            data_schema=_THERMOSTAT_SCHEMA,
            errors=errors,
        )
