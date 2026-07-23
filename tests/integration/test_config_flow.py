"""Test the equipment-group config flow with Home Assistant's flow harness."""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from unittest.mock import patch
from uuid import UUID

import pytest

pytest.importorskip(
    "homeassistant",
    reason="CI installs Home Assistant 2026.7 under Python 3.14.",
)
pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="CI installs the Home Assistant custom-component test harness.",
)

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers.selector import EntitySelector, SelectSelector, TextSelector
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate.config_flow import (
    IntelligentClimateConfigFlow,
)
from custom_components.intelligent_climate.const import (
    CONF_EQUIPMENT_GROUP_NAME,
    CONF_EQUIPMENT_TYPE,
    CONF_THERMOSTAT_ENTITY_ID,
    DOMAIN,
    SUBENTRY_TYPE_ZONE,
)
from custom_components.intelligent_climate.models import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
    EquipmentGroupId,
    EquipmentRelationship,
    EquipmentType,
    SchemaValidationError,
    ThermostatRole,
    decode_equipment_group_document,
)

ROOT = Path(__file__).parents[2]
INTEGRATION_DIR = ROOT / "custom_components" / DOMAIN
THERMOSTAT = "climate.main_floor"


def _parent_data(
    thermostat: str = THERMOSTAT,
) -> dict[str, object]:
    return {
        "equipment_group": {
            "equipment_group_id": "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3",
            "name": "Existing",
            "equipment_type": EquipmentType.BOILER.value,
            "relationship": EquipmentRelationship.SINGLE_SYSTEM.value,
            "thermostats": [{"entity_id": thermostat, "role": "primary"}],
            "shared_policy": None,
        }
    }


async def _start_user_flow(hass: HomeAssistant) -> ConfigFlowResult:
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )


async def _submit_user(
    hass: HomeAssistant,
    *,
    name: object = "Main Floor HVAC",
    equipment_type: object = EquipmentType.AIR_SOURCE_HEAT_PUMP.value,
) -> ConfigFlowResult:
    initial = await _start_user_flow(hass)
    return await hass.config_entries.flow.async_configure(
        initial["flow_id"],
        user_input={
            CONF_EQUIPMENT_GROUP_NAME: name,
            CONF_EQUIPMENT_TYPE: equipment_type,
        },
    )


async def _submit_thermostat(
    hass: HomeAssistant,
    flow: ConfigFlowResult,
    value: object = THERMOSTAT,
) -> ConfigFlowResult:
    return await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={CONF_THERMOSTAT_ENTITY_ID: value},
    )


async def _create_entry(
    hass: HomeAssistant,
    *,
    thermostat: str = THERMOSTAT,
    state: str = "heat",
    equipment_type: EquipmentType = EquipmentType.AIR_SOURCE_HEAT_PUMP,
) -> ConfigFlowResult:
    hass.states.async_set(thermostat, state)
    thermostat_form = await _submit_user(
        hass,
        equipment_type=equipment_type.value,
    )
    return await _submit_thermostat(hass, thermostat_form, thermostat)


def _errors(result: ConfigFlowResult) -> dict[str, str]:
    assert result["type"] is FlowResultType.FORM
    errors: dict[str, str] | None = result["errors"]
    assert errors is not None
    return errors


def _assert_json_compatible(value: object) -> None:
    assert not isinstance(value, Enum | UUID | tuple)
    if isinstance(value, Mapping):
        for item in value.values():
            _assert_json_compatible(item)
    elif isinstance(value, list):
        for item in value:
            _assert_json_compatible(item)
    else:
        assert value is None or type(value) in {str, int, float, bool}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_initial_user_flow_displays_expected_form(hass: HomeAssistant) -> None:
    result = await _start_user_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    schema = result["data_schema"]
    assert isinstance(schema, vol.Schema)
    assert {marker.schema for marker in schema.schema} == {
        CONF_EQUIPMENT_GROUP_NAME,
        CONF_EQUIPMENT_TYPE,
    }
    selectors = {marker.schema: selector for marker, selector in schema.schema.items()}
    assert isinstance(selectors[CONF_EQUIPMENT_GROUP_NAME], TextSelector)
    assert isinstance(selectors[CONF_EQUIPMENT_TYPE], SelectSelector)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_user_step_continues_to_filtered_thermostat_form(
    hass: HomeAssistant,
) -> None:
    result = await _submit_user(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "thermostat"
    schema = result["data_schema"]
    assert isinstance(schema, vol.Schema)
    marker, selector = next(iter(schema.schema.items()))
    assert marker.schema == CONF_THERMOSTAT_ENTITY_ID
    assert isinstance(marker, vol.Required)
    assert isinstance(selector, EntitySelector)
    assert selector.config["multiple"] is False
    assert selector.config["filter"] == [{"domain": ["climate"]}]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_cancel_before_entry_creation_leaves_no_entry(
    hass: HomeAssistant,
) -> None:
    form = await _submit_user(hass)

    hass.config_entries.flow.async_abort(form["flow_id"])

    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_missing_thermostat_state_is_rejected(hass: HomeAssistant) -> None:
    result = await _submit_thermostat(hass, await _submit_user(hass))

    assert _errors(result)[CONF_THERMOSTAT_ENTITY_ID] == "missing_entity"
    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_wrong_thermostat_domain_is_rejected(hass: HomeAssistant) -> None:
    hass.states.async_set("sensor.room", "20")
    result = await _submit_thermostat(
        hass,
        await _submit_user(hass),
        "sensor.room",
    )

    assert _errors(result)[CONF_THERMOSTAT_ENTITY_ID] == "wrong_domain"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_duplicate_thermostat_owner_is_rejected(hass: HomeAssistant) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    existing = MockConfigEntry(
        domain=DOMAIN,
        data=_parent_data(),
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    existing.add_to_hass(hass)

    result = await _submit_thermostat(hass, await _submit_user(hass))

    assert _errors(result)[CONF_THERMOSTAT_ENTITY_ID] == ("duplicate_thermostat_owner")
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_malformed_existing_parent_stops_ownership_scan(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    malformed = MockConfigEntry(
        domain=DOMAIN,
        data={"equipment_group": {"name": "Broken"}},
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    malformed.add_to_hass(hass)

    result = await _submit_thermostat(hass, await _submit_user(hass))

    assert _errors(result)["base"] == "invalid_existing_configuration"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_existing_unavailable_thermostat_is_accepted(
    hass: HomeAssistant,
) -> None:
    result = await _create_entry(hass, state="unavailable")

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.parametrize("equipment_type", list(EquipmentType))
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_valid_entry_has_stable_identity_and_primary_binding(
    hass: HomeAssistant,
    equipment_type: EquipmentType,
) -> None:
    result = await _create_entry(hass, equipment_type=equipment_type)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.version == CONFIG_ENTRY_MAJOR_VERSION
    assert entry.minor_version == CONFIG_ENTRY_MINOR_VERSION
    assert entry.unique_id is not None
    group_id = EquipmentGroupId.parse(entry.unique_id)
    assert group_id.value.version == 4
    document = decode_equipment_group_document(
        entry.data,
        version=entry.version,
        minor_version=entry.minor_version,
    )
    group = document.equipment_group
    assert group.equipment_group_id == group_id
    assert group.equipment_type is equipment_type
    assert group.relationship is EquipmentRelationship.SINGLE_SYSTEM
    assert group.shared_policy is None
    assert len(group.thermostats) == 1
    assert group.thermostats[0].entity_id == THERMOSTAT
    assert group.thermostats[0].role is ThermostatRole.PRIMARY
    _assert_json_compatible(entry.data)
    json.dumps(dict(entry.data))


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_valid_entry_starts_native_first_zone_flow(
    hass: HomeAssistant,
) -> None:
    result = await _create_entry(hass)
    entry = result["result"]

    flow_type, flow_id = result["next_flow"]
    assert flow_type is config_entries.FlowType.CONFIG_SUBENTRIES_FLOW
    assert hass.config_entries.subentries.async_get(flow_id)["handler"] == (
        entry.entry_id,
        SUBENTRY_TYPE_ZONE,
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_thermostat_submission_creates_no_entry(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set("sensor.room", "20")
    form = await _submit_user(hass)
    first = await _submit_thermostat(hass, form, "sensor.room")
    second = await _submit_thermostat(hass, first, THERMOSTAT)

    assert _errors(first)[CONF_THERMOSTAT_ENTITY_ID] == "wrong_domain"
    assert _errors(second)[CONF_THERMOSTAT_ENTITY_ID] == "missing_entity"
    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_flow_manager_rejects_inexact_thermostat_fields(
    hass: HomeAssistant,
) -> None:
    form = await _submit_user(hass)

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            form["flow_id"],
            user_input={CONF_THERMOSTAT_ENTITY_ID: THERMOSTAT, "future": True},
        )
    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_schema_boundary_failure_is_a_form_error(hass: HomeAssistant) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    form = await _submit_user(hass)
    with patch(
        "custom_components.intelligent_climate.config_flow."
        "decode_equipment_group_document",
        side_effect=SchemaValidationError("equipment_group", "invalid"),
    ):
        result = await _submit_thermostat(hass, form)

    assert _errors(result)["base"] == "invalid_input"
    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.parametrize(
    ("user_input", "error_key"),
    [
        ({}, "base"),
        (
            {
                CONF_EQUIPMENT_GROUP_NAME: "HVAC",
                CONF_EQUIPMENT_TYPE: EquipmentType.BOILER.value,
                "future": True,
            },
            "base",
        ),
        (
            {
                CONF_EQUIPMENT_GROUP_NAME: "   ",
                CONF_EQUIPMENT_TYPE: EquipmentType.BOILER.value,
            },
            CONF_EQUIPMENT_GROUP_NAME,
        ),
        (
            {
                CONF_EQUIPMENT_GROUP_NAME: "HVAC",
                CONF_EQUIPMENT_TYPE: "unsupported",
            },
            CONF_EQUIPMENT_TYPE,
        ),
        (
            {
                CONF_EQUIPMENT_GROUP_NAME: "HVAC",
                CONF_EQUIPMENT_TYPE: 123,
            },
            CONF_EQUIPMENT_TYPE,
        ),
    ],
)
async def test_direct_user_step_contains_defensive_input_errors(
    user_input: dict[str, object],
    error_key: str,
) -> None:
    flow = IntelligentClimateConfigFlow()

    result = await flow.async_step_user(user_input)

    assert error_key in _errors(result)


@pytest.mark.parametrize(
    ("user_input", "expected"),
    [
        ({}, "invalid_input"),
        (
            {CONF_THERMOSTAT_ENTITY_ID: THERMOSTAT, "future": True},
            "invalid_input",
        ),
        ({CONF_THERMOSTAT_ENTITY_ID: "not_an_entity"}, "invalid_entity_selection"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_direct_thermostat_step_contains_defensive_input_errors(
    hass: HomeAssistant,
    user_input: dict[str, object],
    expected: str,
) -> None:
    flow = IntelligentClimateConfigFlow()
    flow.hass = hass
    flow._pending_name = "HVAC"
    flow._pending_equipment_type = EquipmentType.BOILER

    result = await flow.async_step_thermostat(user_input)

    assert expected in _errors(result).values()


def test_flow_exposes_only_task_5_parent_surfaces() -> None:
    members = IntelligentClimateConfigFlow.__dict__
    assert {"async_step_user", "async_step_thermostat"} <= set(members)
    assert "async_step_reconfigure" not in members
    assert "async_get_options_flow" not in members


def test_custom_integration_translations_are_complete() -> None:
    translations = json.loads(
        (INTEGRATION_DIR / "translations" / "en.json").read_text()
    )
    assert translations["title"] == "Intelligent Climate"
    assert set(translations["config"]["step"]) == {"user", "thermostat"}
    thermostat_step = translations["config"]["step"]["thermostat"]
    assert set(thermostat_step["data"]) == {CONF_THERMOSTAT_ENTITY_ID}
    assert set(translations["config"]["error"]) >= {
        "missing_entity",
        "wrong_domain",
        "duplicate_thermostat_owner",
        "invalid_existing_configuration",
        "invalid_entity_selection",
    }
    zone = translations["config_subentries"][SUBENTRY_TYPE_ZONE]
    assert set(zone) == {"entry_type", "initiate_flow", "step", "error", "abort"}
    assert set(zone["error"]) >= {
        "missing_entity",
        "wrong_domain",
        "wrong_device_class",
        "duplicate_temperature_source",
        "no_temperature_sources",
        "invalid_parent_thermostat",
        "invalid_existing_configuration",
        "invalid_entity_selection",
    }
    assert translations["exceptions"]["observation_only"]["message"] == (
        "Intelligent Climate is observation-only and cannot change HVAC equipment."
    )
    assert not (INTEGRATION_DIR / "strings.json").exists()
