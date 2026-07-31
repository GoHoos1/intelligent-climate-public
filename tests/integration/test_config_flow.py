"""Acceptance tests for equipment-group, options, and reconfigure flows."""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from pathlib import Path
from types import MappingProxyType
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest

pytest.importorskip("homeassistant", reason="CI installs Home Assistant 2026.7.")
pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="CI installs the Home Assistant custom-component test harness.",
)

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers.selector import EntitySelector, SelectSelector, TextSelector
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate import config_flow as config_flow_module
from custom_components.intelligent_climate.config_flow import (
    IntelligentClimateConfigFlow,
)
from custom_components.intelligent_climate.const import (
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
from custom_components.intelligent_climate.models import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
    DEFAULT_OPTIONS,
    PHASE2_CONFIG_MAJOR_VERSION,
    PHASE2_CONFIG_MINOR_VERSION,
    AggregationStrategy,
    EquipmentGroupId,
    EquipmentRelationship,
    EquipmentType,
    LogLevelDetail,
    SchemaValidationError,
    ThermostatRole,
    decode_phase2_equipment_group_document,
    decode_phase2_options,
    decode_phase2_zone_config,
    encode_options,
)

ROOT = Path(__file__).parents[2]
INTEGRATION_DIR = ROOT / "custom_components" / DOMAIN
THERMOSTAT = "climate.main_floor"
SECOND_THERMOSTAT = "climate.upstairs"
SENSOR = "sensor.dining_room_temperature"


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


def _set_entities(
    hass: HomeAssistant,
    thermostats: tuple[str, ...] = (THERMOSTAT,),
) -> None:
    for thermostat in thermostats:
        hass.states.async_set(thermostat, "cool")
    hass.states.async_set(
        SENSOR,
        "23.7",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    )


async def _start_user_flow(hass: HomeAssistant) -> config_entries.ConfigFlowResult:
    return await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )


async def _submit_user(
    hass: HomeAssistant,
    *,
    name: object = "Main Floor HVAC",
    equipment_type: object = EquipmentType.AIR_SOURCE_HEAT_PUMP.value,
) -> config_entries.ConfigFlowResult:
    initial = await _start_user_flow(hass)
    return await hass.config_entries.flow.async_configure(
        initial["flow_id"],
        user_input={
            CONF_EQUIPMENT_GROUP_NAME: name,
            CONF_EQUIPMENT_TYPE: equipment_type,
        },
    )


async def _submit_thermostats(
    hass: HomeAssistant,
    flow: config_entries.ConfigFlowResult,
    thermostats: object,
) -> config_entries.ConfigFlowResult:
    return await hass.config_entries.flow.async_configure(
        flow["flow_id"],
        user_input={CONF_THERMOSTAT_ENTITY_IDS: thermostats},
    )


async def _create_entry(
    hass: HomeAssistant,
    *,
    thermostats: tuple[str, ...] = (THERMOSTAT,),
    relationship: EquipmentRelationship = EquipmentRelationship.SINGLE_SYSTEM,
    equipment_type: EquipmentType = EquipmentType.AIR_SOURCE_HEAT_PUMP,
) -> config_entries.ConfigFlowResult:
    _set_entities(hass, thermostats)
    result = await _submit_thermostats(
        hass,
        await _submit_user(hass, equipment_type=equipment_type.value),
        list(thermostats),
    )
    if len(thermostats) > 1:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_EQUIPMENT_RELATIONSHIP: relationship.value},
        )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_ZONE_NAME: "Dining Room",
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: list(thermostats),
            CONF_TEMPERATURE_SOURCES: [SENSOR],
        },
    )
    assert result["step_id"] == "confirm"
    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )


def _add_second_zone(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
) -> None:
    first = next(iter(entry.subentries.values()))
    data = dict(first.data)
    data["zone_id"] = "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"
    data["name"] = "Upstairs"
    sources = [dict(item) for item in data["temperature_sources"]]
    sources[0]["source_id"] = "ce30dafc-fadd-4cc4-b261-8a896d5a6d12"
    data["temperature_sources"] = sources
    hass.config_entries.async_add_subentry(
        entry,
        config_entries.ConfigSubentry(
            data=MappingProxyType(data),
            subentry_type=SUBENTRY_TYPE_ZONE,
            title="Upstairs",
            unique_id=str(data["zone_id"]),
        ),
    )


def _direct_reconfigure_flow(
    hass: HomeAssistant,
    entry: config_entries.ConfigEntry,
) -> IntelligentClimateConfigFlow:
    flow = IntelligentClimateConfigFlow()
    flow.hass = hass
    flow.context = {
        "source": config_entries.SOURCE_RECONFIGURE,
        "entry_id": entry.entry_id,
    }
    return flow


def _errors(result: config_entries.ConfigFlowResult) -> dict[str, str]:
    assert result["type"] is FlowResultType.FORM
    errors = result["errors"]
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
async def test_initial_flow_uses_filtered_multi_entity_selectors(
    hass: HomeAssistant,
) -> None:
    result = await _start_user_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    schema = result["data_schema"]
    assert isinstance(schema, vol.Schema)
    selectors = {marker.schema: selector for marker, selector in schema.schema.items()}
    assert isinstance(selectors[CONF_EQUIPMENT_GROUP_NAME], TextSelector)
    assert isinstance(selectors[CONF_EQUIPMENT_TYPE], SelectSelector)

    result = await _submit_user(hass)
    assert result["step_id"] == "thermostats"
    schema = result["data_schema"]
    assert isinstance(schema, vol.Schema)
    marker, selector = next(iter(schema.schema.items()))
    assert marker.schema == CONF_THERMOSTAT_ENTITY_IDS
    assert isinstance(selector, EntitySelector)
    assert selector.config["multiple"] is True
    assert selector.config["filter"] == [{"domain": ["climate"]}]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_cancel_any_time_before_confirm_creates_nothing(
    hass: HomeAssistant,
) -> None:
    form = await _submit_user(hass)
    hass.config_entries.flow.async_abort(form["flow_id"])
    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.parametrize(
    ("value", "state_domain", "error"),
    [
        ([THERMOSTAT], None, "missing_entity"),
        (["sensor.room"], "sensor.room", "wrong_domain"),
        ([THERMOSTAT, THERMOSTAT], THERMOSTAT, "duplicate_thermostat_selection"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_thermostat_validation_is_fail_closed(
    hass: HomeAssistant,
    value: object,
    state_domain: str | None,
    error: str,
) -> None:
    if state_domain is not None:
        hass.states.async_set(state_domain, "heat")
    result = await _submit_thermostats(hass, await _submit_user(hass), value)
    assert _errors(result)[CONF_THERMOSTAT_ENTITY_IDS] == error
    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_duplicate_owner_and_malformed_owner_scan_are_rejected(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    existing = MockConfigEntry(
        domain=DOMAIN,
        data=_parent_data(),
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    existing.add_to_hass(hass)
    result = await _submit_thermostats(
        hass,
        await _submit_user(hass),
        [THERMOSTAT],
    )
    assert _errors(result)[CONF_THERMOSTAT_ENTITY_IDS] == ("duplicate_thermostat_owner")

    await hass.config_entries.async_remove(existing.entry_id)
    malformed = MockConfigEntry(
        domain=DOMAIN,
        data={"equipment_group": {"name": "Broken"}},
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    malformed.add_to_hass(hass)
    result = await _submit_thermostats(
        hass,
        await _submit_user(hass),
        [THERMOSTAT],
    )
    assert _errors(result)["base"] == "invalid_existing_configuration"


@pytest.mark.parametrize("equipment_type", list(EquipmentType))
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_single_system_creation_is_atomic_and_schema_valid(
    hass: HomeAssistant,
    equipment_type: EquipmentType,
) -> None:
    result = await _create_entry(hass, equipment_type=equipment_type)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.version == PHASE2_CONFIG_MAJOR_VERSION
    assert entry.minor_version == PHASE2_CONFIG_MINOR_VERSION
    phase2_options = decode_phase2_options(entry.options)
    assert phase2_options.observation == DEFAULT_OPTIONS
    assert len(entry.subentries) == 1

    assert entry.unique_id is not None
    group_id = EquipmentGroupId.parse(entry.unique_id)
    group_document = decode_phase2_equipment_group_document(entry.data)
    group = group_document.equipment_group
    zone = decode_phase2_zone_config(next(iter(entry.subentries.values())).data).zone
    assert group.equipment_group_id == group_id
    assert group.equipment_type is equipment_type
    assert group.relationship is EquipmentRelationship.SINGLE_SYSTEM
    assert group.shared_policy is None
    assert group.thermostats[0].role is ThermostatRole.PRIMARY
    assert group_document.automation_enabled is False
    assert group_document.authority_review_required is False
    assert zone.thermostat_entity_ids == (THERMOSTAT,)
    assert zone.temperature_sources[0].entity_id == SENSOR
    _assert_json_compatible(entry.data)
    _assert_json_compatible(next(iter(entry.subentries.values())).data)
    json.dumps(dict(entry.data))


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_shared_multi_thermostat_graph_requires_explicit_relationship(
    hass: HomeAssistant,
) -> None:
    _set_entities(hass, (THERMOSTAT, SECOND_THERMOSTAT))
    result = await _submit_thermostats(
        hass,
        await _submit_user(hass),
        [THERMOSTAT, SECOND_THERMOSTAT],
    )
    assert result["step_id"] == "relationship"

    first_zone = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EQUIPMENT_RELATIONSHIP: EquipmentRelationship.SHARED_ZONED.value
        },
    )
    assert first_zone["step_id"] == "first_zone"
    confirm = await hass.config_entries.flow.async_configure(
        first_zone["flow_id"],
        user_input={
            CONF_ZONE_NAME: "Whole House",
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT, SECOND_THERMOSTAT],
            CONF_TEMPERATURE_SOURCES: [SENSOR],
        },
    )
    result = await hass.config_entries.flow.async_configure(
        confirm["flow_id"],
        user_input={},
    )
    entry = result["result"]
    group = decode_phase2_equipment_group_document(entry.data).equipment_group
    zone = decode_phase2_zone_config(next(iter(entry.subentries.values())).data).zone
    assert group.relationship is EquipmentRelationship.SHARED_ZONED
    assert group.shared_policy is not None
    assert group.shared_policy.zone_priority_order == (zone.zone_id,)
    assert [item.role for item in group.thermostats] == [
        ThermostatRole.PRIMARY,
        ThermostatRole.SECONDARY,
    ]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_first_zone_validation_and_schema_failure_leave_no_parent(
    hass: HomeAssistant,
) -> None:
    _set_entities(hass)
    first_zone = await _submit_thermostats(
        hass,
        await _submit_user(hass),
        [THERMOSTAT],
    )
    invalid = await hass.config_entries.flow.async_configure(
        first_zone["flow_id"],
        user_input={
            CONF_ZONE_NAME: "Dining",
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
            CONF_TEMPERATURE_SOURCES: ["sensor.missing"],
        },
    )
    assert _errors(invalid)[CONF_TEMPERATURE_SOURCES] == "missing_entity"
    assert hass.config_entries.async_entries(DOMAIN) == []

    confirm = await hass.config_entries.flow.async_configure(
        invalid["flow_id"],
        user_input={
            CONF_ZONE_NAME: "Dining",
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
            CONF_TEMPERATURE_SOURCES: [SENSOR],
        },
    )
    with patch(
        "custom_components.intelligent_climate.config_flow.decode_configuration_graph",
        side_effect=SchemaValidationError("graph", "invalid"),
    ):
        result = await hass.config_entries.flow.async_configure(
            confirm["flow_id"],
            user_input={},
        )
    assert result["type"] is FlowResultType.ABORT
    assert hass.config_entries.async_entries(DOMAIN) == []


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_flow_manager_rejects_inexact_fields(hass: HomeAssistant) -> None:
    form = await _submit_user(hass)
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            form["flow_id"],
            user_input={
                CONF_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
                "future": True,
            },
        )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_exposes_and_saves_every_phase_1_option(
    hass: HomeAssistant,
) -> None:
    entry = (await _create_entry(hass))["result"]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    schema = result["data_schema"]
    assert isinstance(schema, vol.Schema)
    assert {marker.schema for marker in schema.schema} == set(
        encode_options(DEFAULT_OPTIONS)
    )

    options = {
        "observation_enabled": False,
        "temperature_strategy": AggregationStrategy.PRIORITY.value,
        "humidity_strategy": AggregationStrategy.WEIGHTED_AVERAGE.value,
        "min_valid_temperature_sources": 2,
        "min_valid_humidity_sources": 2,
        "source_stale_after_seconds": 600,
        "startup_reconciliation_seconds": 90,
        "jump_limit_c_per_5_minutes": 4.5,
        "outlier_floor_c": 1.5,
        "indoor_temperature_min_c": 8.0,
        "indoor_temperature_max_c": 38.0,
        "history_max_records": 250,
        "history_max_age_days": 14,
        "log_level_detail": LogLevelDetail.VERBOSE.value,
    }
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=options,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        decode_phase2_options(result["data"]).observation.observation_enabled is False
    )
    assert result["data"]["observation"] == options


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_options_flow_rejects_invalid_cross_field_values(
    hass: HomeAssistant,
) -> None:
    entry = (await _create_entry(hass))["result"]
    result = await hass.config_entries.options.async_init(entry.entry_id)
    invalid = dict(encode_options(DEFAULT_OPTIONS))
    invalid["indoor_temperature_min_c"] = 35.0
    invalid["indoor_temperature_max_c"] = 10.0
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=invalid,
    )
    assert _errors(result)["base"] == "invalid_options"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_parent_reconfigure_preserves_group_and_zone_ids(
    hass: HomeAssistant,
) -> None:
    entry = (await _create_entry(hass))["result"]
    group_before = decode_phase2_equipment_group_document(entry.data).equipment_group
    subentry_before = next(iter(entry.subentries.values()))
    zone_before = decode_phase2_zone_config(subentry_before.data).zone
    hass.states.async_set(SECOND_THERMOSTAT, "cool")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EQUIPMENT_GROUP_NAME: "Renamed HVAC",
            CONF_EQUIPMENT_TYPE: EquipmentType.DUAL_FUEL.value,
            CONF_EQUIPMENT_RELATIONSHIP: EquipmentRelationship.INDEPENDENT.value,
            CONF_THERMOSTAT_ENTITY_IDS: [THERMOSTAT, SECOND_THERMOSTAT],
        },
    )
    assert result["step_id"] == "reconfigure_zone"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT, SECOND_THERMOSTAT]},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    group_after = decode_phase2_equipment_group_document(entry.data).equipment_group
    zone_after = decode_phase2_zone_config(subentry_before.data).zone
    assert group_after.equipment_group_id == group_before.equipment_group_id
    assert zone_after.zone_id == zone_before.zone_id
    assert entry.title == "Renamed HVAC"
    assert group_after.equipment_type is EquipmentType.DUAL_FUEL
    assert group_after.relationship is EquipmentRelationship.INDEPENDENT
    assert zone_after.thermostat_entity_ids == (THERMOSTAT, SECOND_THERMOSTAT)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_parent_reconfigure_rejects_duplicate_owner(
    hass: HomeAssistant,
) -> None:
    entry = (await _create_entry(hass))["result"]
    hass.states.async_set(SECOND_THERMOSTAT, "cool")
    other = MockConfigEntry(
        domain=DOMAIN,
        data=_parent_data(SECOND_THERMOSTAT),
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    other.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_EQUIPMENT_GROUP_NAME: "Existing",
            CONF_EQUIPMENT_TYPE: EquipmentType.BOILER.value,
            CONF_EQUIPMENT_RELATIONSHIP: EquipmentRelationship.INDEPENDENT.value,
            CONF_THERMOSTAT_ENTITY_IDS: [THERMOSTAT, SECOND_THERMOSTAT],
        },
    )
    assert _errors(result)[CONF_THERMOSTAT_ENTITY_IDS] == ("duplicate_thermostat_owner")


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_defensive_and_zero_zone_branches(
    hass: HomeAssistant,
) -> None:
    _set_entities(hass, (THERMOSTAT, SECOND_THERMOSTAT))
    malformed = MockConfigEntry(
        domain=DOMAIN,
        data={"equipment_group": {"name": "Broken"}},
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    malformed.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": malformed.entry_id,
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_existing_configuration"
    await hass.config_entries.async_remove(malformed.entry_id)

    entry = (await _create_entry(hass))["result"]
    flow = _direct_reconfigure_flow(hass, entry)
    result = await flow.async_step_reconfigure(
        {
            CONF_EQUIPMENT_GROUP_NAME: " ",
            CONF_EQUIPMENT_TYPE: 1,
            CONF_EQUIPMENT_RELATIONSHIP: 1,
            CONF_THERMOSTAT_ENTITY_IDS: ["climate.missing"],
            "future": True,
        }
    )
    assert {
        "invalid_input",
        "invalid_name",
        "invalid_equipment_type",
        "missing_entity",
        "invalid_relationship",
    } <= set(_errors(result).values())

    result = await flow.async_step_reconfigure(
        {
            CONF_EQUIPMENT_GROUP_NAME: "HVAC",
            CONF_EQUIPMENT_TYPE: EquipmentType.BOILER.value,
            CONF_EQUIPMENT_RELATIONSHIP: EquipmentRelationship.SINGLE_SYSTEM.value,
            CONF_THERMOSTAT_ENTITY_IDS: [THERMOSTAT, SECOND_THERMOSTAT],
        }
    )
    assert _errors(result)[CONF_EQUIPMENT_RELATIONSHIP] == "invalid_relationship"
    await hass.config_entries.async_remove(entry.entry_id)

    no_zone = MockConfigEntry(
        domain=DOMAIN,
        data=_parent_data(),
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    no_zone.add_to_hass(hass)
    no_zone_flow = _direct_reconfigure_flow(hass, no_zone)
    result = await no_zone_flow.async_step_reconfigure(
        {
            CONF_EQUIPMENT_GROUP_NAME: "HVAC",
            CONF_EQUIPMENT_TYPE: EquipmentType.BOILER.value,
            CONF_EQUIPMENT_RELATIONSHIP: EquipmentRelationship.SHARED_ZONED.value,
            CONF_THERMOSTAT_ENTITY_IDS: [THERMOSTAT, SECOND_THERMOSTAT],
        }
    )
    assert _errors(result)[CONF_EQUIPMENT_RELATIONSHIP] == "shared_requires_zone"
    result = await no_zone_flow.async_step_reconfigure(
        {
            CONF_EQUIPMENT_GROUP_NAME: "HVAC",
            CONF_EQUIPMENT_TYPE: EquipmentType.BOILER.value,
            CONF_EQUIPMENT_RELATIONSHIP: EquipmentRelationship.INDEPENDENT.value,
            CONF_THERMOSTAT_ENTITY_IDS: [THERMOSTAT, SECOND_THERMOSTAT],
        }
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_single_parent_reconfigure_finishes_without_membership_step(
    hass: HomeAssistant,
) -> None:
    entry = (await _create_entry(hass))["result"]
    flow = _direct_reconfigure_flow(hass, entry)

    result = await flow.async_step_reconfigure(
        {
            CONF_EQUIPMENT_GROUP_NAME: "Renamed",
            CONF_EQUIPMENT_TYPE: EquipmentType.BOILER.value,
            CONF_EQUIPMENT_RELATIONSHIP: EquipmentRelationship.SINGLE_SYSTEM.value,
            CONF_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
        }
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_multi_zone_membership_reconfigure_covers_errors_and_transaction(
    hass: HomeAssistant,
) -> None:
    entry = (await _create_entry(hass))["result"]
    _add_second_zone(hass, entry)
    hass.states.async_set(SECOND_THERMOSTAT, "cool")
    hass.states.async_set("climate.outside_group", "heat")
    flow = _direct_reconfigure_flow(hass, entry)
    result = await flow.async_step_reconfigure(
        {
            CONF_EQUIPMENT_GROUP_NAME: "HVAC",
            CONF_EQUIPMENT_TYPE: EquipmentType.BOILER.value,
            CONF_EQUIPMENT_RELATIONSHIP: EquipmentRelationship.INDEPENDENT.value,
            CONF_THERMOSTAT_ENTITY_IDS: [THERMOSTAT, SECOND_THERMOSTAT],
        }
    )
    assert result["step_id"] == "reconfigure_zone"

    result = await flow.async_step_reconfigure_zone(
        {
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
            "future": True,
        }
    )
    assert _errors(result)["base"] == "invalid_input"
    result = await flow.async_step_reconfigure_zone(
        {CONF_ZONE_THERMOSTAT_ENTITY_IDS: ["climate.missing"]}
    )
    assert _errors(result)[CONF_ZONE_THERMOSTAT_ENTITY_IDS] == "missing_entity"
    result = await flow.async_step_reconfigure_zone(
        {CONF_ZONE_THERMOSTAT_ENTITY_IDS: ["climate.outside_group"]}
    )
    assert _errors(result)[CONF_ZONE_THERMOSTAT_ENTITY_IDS] == (
        "thermostat_outside_group"
    )

    result = await flow.async_step_reconfigure_zone(
        {CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT]}
    )
    assert result["step_id"] == "reconfigure_zone"
    result = await flow.async_step_reconfigure_zone(
        {CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT]}
    )
    assert _errors(result)["base"] == "unassigned_thermostat"

    result = await flow.async_step_reconfigure_zone(
        {CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT]}
    )
    assert result["step_id"] == "reconfigure_zone"
    with patch(
        "custom_components.intelligent_climate.config_flow.decode_configuration_graph",
        side_effect=SchemaValidationError("graph", "invalid"),
    ):
        result = await flow.async_step_reconfigure_zone(
            {CONF_ZONE_THERMOSTAT_ENTITY_IDS: [SECOND_THERMOSTAT]}
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_input"


@pytest.mark.parametrize(
    ("step", "user_input", "expected"),
    [
        (
            "user",
            {
                CONF_EQUIPMENT_GROUP_NAME: " ",
                CONF_EQUIPMENT_TYPE: "unsupported",
            },
            {"invalid_name", "invalid_equipment_type"},
        ),
        (
            "thermostats",
            {CONF_THERMOSTAT_ENTITY_IDS: "bad"},
            {"invalid_entity_selection"},
        ),
        (
            "relationship",
            {CONF_EQUIPMENT_RELATIONSHIP: "bad"},
            {"invalid_relationship"},
        ),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_direct_steps_return_defensive_errors(
    hass: HomeAssistant,
    step: str,
    user_input: dict[str, object],
    expected: set[str],
) -> None:
    flow = IntelligentClimateConfigFlow()
    flow.hass = hass
    flow._pending_thermostats = (THERMOSTAT, SECOND_THERMOSTAT)
    result = await getattr(flow, f"async_step_{step}")(user_input)
    assert expected <= set(_errors(result).values())


def test_flow_surfaces_and_translations_are_complete() -> None:
    members = IntelligentClimateConfigFlow.__dict__
    assert {
        "async_step_user",
        "async_step_thermostats",
        "async_step_relationship",
        "async_step_first_zone",
        "async_step_confirm",
        "async_step_reconfigure",
        "async_get_options_flow",
    } <= set(members)
    translations = json.loads(
        (INTEGRATION_DIR / "translations" / "en.json").read_text()
    )
    assert set(translations["config"]["step"]) >= {
        "user",
        "thermostats",
        "relationship",
        "first_zone",
        "confirm",
        "reconfigure",
        "reconfigure_zone",
    }
    assert set(translations["options"]["step"]["init"]["data"]) == set(
        encode_options(DEFAULT_OPTIONS)
    )
    zone = translations["config_subentries"][SUBENTRY_TYPE_ZONE]
    assert set(zone["step"]) == {
        "user",
        "reconfigure",
        "source",
        "humidity_source",
    }
    assert translations["exceptions"]["observation_only"]["message"] == (
        "Intelligent Climate is observation-only and cannot change HVAC equipment."
    )
    assert not (INTEGRATION_DIR / "strings.json").exists()


def test_private_flow_value_validators_reject_every_invalid_numeric_type() -> None:
    with pytest.raises(ValueError):
        config_flow_module._equipment_type(1)
    with pytest.raises(ValueError):
        config_flow_module._relationship(1)
    for value in (True, "1", float("nan"), 0, 1.5):
        with pytest.raises(ValueError):
            config_flow_module._positive_integer(value)
    assert config_flow_module._positive_integer(2.0) == 2


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_direct_initial_steps_cover_all_defensive_branches(
    hass: HomeAssistant,
) -> None:
    _set_entities(hass, (THERMOSTAT, SECOND_THERMOSTAT))
    hass.states.async_set("climate.outside_group", "heat")
    flow = IntelligentClimateConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user(
        {
            CONF_EQUIPMENT_GROUP_NAME: "HVAC",
            CONF_EQUIPMENT_TYPE: EquipmentType.BOILER.value,
            "future": True,
        }
    )
    assert _errors(result)["base"] == "invalid_input"

    result = await flow.async_step_thermostats(
        {CONF_THERMOSTAT_ENTITY_IDS: [THERMOSTAT], "future": True}
    )
    assert _errors(result)["base"] == "invalid_input"

    flow._pending_thermostats = (THERMOSTAT, SECOND_THERMOSTAT)
    result = await flow.async_step_relationship(
        {
            CONF_EQUIPMENT_RELATIONSHIP: EquipmentRelationship.INDEPENDENT.value,
            "future": True,
        }
    )
    assert _errors(result)["base"] == "invalid_input"
    result = await flow.async_step_relationship(
        {CONF_EQUIPMENT_RELATIONSHIP: EquipmentRelationship.SINGLE_SYSTEM.value}
    )
    assert _errors(result)[CONF_EQUIPMENT_RELATIONSHIP] == "invalid_relationship"

    first_zone_cases: list[tuple[dict[str, Any], str, str]] = [
        (
            {
                CONF_ZONE_NAME: "Zone",
                CONF_ZONE_THERMOSTAT_ENTITY_IDS: [
                    THERMOSTAT,
                    SECOND_THERMOSTAT,
                ],
                CONF_TEMPERATURE_SOURCES: [SENSOR],
                "future": True,
            },
            "base",
            "invalid_input",
        ),
        (
            {
                CONF_ZONE_NAME: " ",
                CONF_ZONE_THERMOSTAT_ENTITY_IDS: [
                    THERMOSTAT,
                    SECOND_THERMOSTAT,
                ],
                CONF_TEMPERATURE_SOURCES: [SENSOR],
            },
            CONF_ZONE_NAME,
            "invalid_name",
        ),
        (
            {
                CONF_ZONE_NAME: "Zone",
                CONF_ZONE_THERMOSTAT_ENTITY_IDS: ["climate.missing"],
                CONF_TEMPERATURE_SOURCES: [SENSOR],
            },
            CONF_ZONE_THERMOSTAT_ENTITY_IDS,
            "missing_entity",
        ),
        (
            {
                CONF_ZONE_NAME: "Zone",
                CONF_ZONE_THERMOSTAT_ENTITY_IDS: ["climate.outside_group"],
                CONF_TEMPERATURE_SOURCES: [SENSOR],
            },
            CONF_ZONE_THERMOSTAT_ENTITY_IDS,
            "thermostat_outside_group",
        ),
        (
            {
                CONF_ZONE_NAME: "Zone",
                CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
                CONF_TEMPERATURE_SOURCES: [SENSOR],
            },
            CONF_ZONE_THERMOSTAT_ENTITY_IDS,
            "unassigned_thermostat",
        ),
    ]
    for user_input, key, error in first_zone_cases:
        result = await flow.async_step_first_zone(user_input)
        assert _errors(result)[key] == error

    flow._pending_name = "HVAC"
    flow._pending_zone_name = "Zone"
    flow._pending_relationship = EquipmentRelationship.INDEPENDENT
    result = await flow.async_step_confirm({"future": True})
    assert _errors(result)["base"] == "invalid_input"
