"""Test native Home Assistant zone config-subentry flows."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import MappingProxyType
from typing import cast
from unittest.mock import PropertyMock, patch

import pytest

pytest.importorskip("homeassistant", reason="CI installs Home Assistant 2026.7.")
pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="CI installs the Home Assistant custom-component test harness.",
)

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.selector import EntitySelector, TextSelector
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate import zone_flow as zone_flow_module
from custom_components.intelligent_climate.const import (
    CONF_SOURCE_ENABLED,
    CONF_SOURCE_OFFSET_C,
    CONF_SOURCE_PRIORITY,
    CONF_SOURCE_WEIGHT,
    CONF_TEMPERATURE_SOURCES,
    CONF_ZONE_NAME,
    CONF_ZONE_THERMOSTAT_ENTITY_IDS,
    DOMAIN,
    SUBENTRY_TYPE_ZONE,
)
from custom_components.intelligent_climate.models import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
    EquipmentType,
    ObservationSourceId,
    RuntimeConfigurationState,
    SchemaValidationError,
    TemperatureSource,
    decode_zone_config,
)
from custom_components.intelligent_climate.validation import (
    EntityValidationCode,
    EntityValidationError,
    validate_live_temperature_selection,
    validate_persisted_temperature_sources,
)
from custom_components.intelligent_climate.zone_flow import ZoneSubentryFlowHandler

GROUP_ID = "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
ZONE_ID = "99246285-6f02-4e8a-94ed-bdfd4a5e62c4"
SOURCE_ID = "f15f73b1-ea59-4b28-819f-7b99acf065bf"
THERMOSTAT = "climate.main_floor"
SECOND_THERMOSTAT = "climate.upstairs"
SENSOR = "sensor.dining_room_temperature"
CLIMATE_SOURCE = "climate.dining_room"
SECOND_ZONE_ID = "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"


def _parent_data(
    *,
    thermostat: str | None = THERMOSTAT,
) -> dict[str, object]:
    thermostats = (
        [] if thermostat is None else [{"entity_id": thermostat, "role": "primary"}]
    )
    return {
        "equipment_group": {
            "equipment_group_id": GROUP_ID,
            "name": "Main Floor HVAC",
            "equipment_type": EquipmentType.AIR_SOURCE_HEAT_PUMP.value,
            "relationship": "single_system",
            "thermostats": thermostats,
            "shared_policy": None,
        }
    }


def _source(
    entity_id: str = SENSOR,
    *,
    source_id: str = SOURCE_ID,
    attribute: str | None = None,
    offset_c: float = 0.0,
    weight: float = 1.0,
    priority: int = 0,
    enabled: bool = True,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "entity_id": entity_id,
        "attribute": attribute,
        "offset_c": offset_c,
        "weight": weight,
        "priority": priority,
        "enabled": enabled,
    }


def _multi_parent_data(*, second_zone_configured: bool) -> dict[str, object]:
    priority = [ZONE_ID]
    if second_zone_configured:
        priority.append(SECOND_ZONE_ID)
    return {
        "equipment_group": {
            "equipment_group_id": GROUP_ID,
            "name": "Main Floor HVAC",
            "equipment_type": EquipmentType.AIR_SOURCE_HEAT_PUMP.value,
            "relationship": "shared_zoned",
            "thermostats": [
                {"entity_id": THERMOSTAT, "role": "primary"},
                {"entity_id": SECOND_THERMOSTAT, "role": "secondary"},
            ],
            "shared_policy": {
                "zone_priority_order": priority,
                "conflict_policy": "priority_order",
            },
        }
    }


def _zone_data(
    *,
    name: str = "Dining Room",
    zone_id: str = ZONE_ID,
    sources: list[dict[str, object]] | None = None,
    thermostats: list[str] | None = None,
) -> dict[str, object]:
    return {
        "data_version": 1,
        "zone_id": zone_id,
        "name": name,
        "thermostat_entity_ids": [THERMOSTAT] if thermostats is None else thermostats,
        "temperature_sources": [_source()] if sources is None else sources,
        "humidity_sources": [],
        "window_door_entity_ids": [],
        "occupancy_entity_ids": [],
        "stage_entity_ids": [],
        "fan_entity_ids": [],
    }


def _subentry_data(
    *,
    data: dict[str, object] | None = None,
    name: str = "Dining Room",
    subentry_id: str = "zone-subentry-1",
) -> config_entries.ConfigSubentryDataWithId:
    zone_data = _zone_data(name=name) if data is None else data
    return config_entries.ConfigSubentryDataWithId(
        data=zone_data,
        subentry_id=subentry_id,
        subentry_type=SUBENTRY_TYPE_ZONE,
        title=str(zone_data["name"]),
        unique_id=str(zone_data["zone_id"]),
    )


def _set_temperature_sensor(
    hass: HomeAssistant,
    entity_id: str = SENSOR,
    state: str = "20",
    *,
    device_class: object = SensorDeviceClass.TEMPERATURE,
) -> None:
    hass.states.async_set(
        entity_id,
        state,
        {ATTR_DEVICE_CLASS: device_class},
    )


def _make_parent(
    hass: HomeAssistant,
    *,
    data: dict[str, object] | None = None,
    subentries: list[config_entries.ConfigSubentryDataWithId] | None = None,
) -> ConfigEntry:
    hass.states.async_set(THERMOSTAT, "heat")
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_parent_data() if data is None else data,
        subentries_data=subentries,
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    entry.add_to_hass(hass)
    return cast(ConfigEntry, entry)


async def _start_add(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> config_entries.SubentryFlowResult:
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ZONE),
        context=config_entries.SubentryFlowContext(source=config_entries.SOURCE_USER),
    )


async def _submit_add(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    name: object = "Dining Room",
    sources: object = None,
    zone_thermostats: object = None,
    source_values: list[dict[str, object]] | None = None,
) -> config_entries.SubentryFlowResult:
    initial = await _start_add(hass, entry)
    if sources is None:
        sources = [SENSOR]
    if zone_thermostats is None:
        zone_thermostats = [THERMOSTAT]
    result = await hass.config_entries.subentries.async_configure(
        initial["flow_id"],
        user_input={
            CONF_ZONE_NAME: name,
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: zone_thermostats,
            CONF_TEMPERATURE_SOURCES: sources,
        },
    )
    return await _complete_source_forms(hass, result, source_values=source_values)


async def _start_reconfigure(
    hass: HomeAssistant,
    entry: ConfigEntry,
    subentry_id: str = "zone-subentry-1",
) -> config_entries.SubentryFlowResult:
    return await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ZONE),
        context=config_entries.SubentryFlowContext(
            source=config_entries.SOURCE_RECONFIGURE,
            subentry_id=subentry_id,
        ),
    )


async def _submit_reconfigure(
    hass: HomeAssistant,
    initial: config_entries.SubentryFlowResult,
    *,
    name: str = "Dining Room",
    sources: list[str] | None = None,
    zone_thermostats: list[str] | None = None,
    source_values: list[dict[str, object]] | None = None,
) -> config_entries.SubentryFlowResult:
    result = await hass.config_entries.subentries.async_configure(
        initial["flow_id"],
        user_input={
            CONF_ZONE_NAME: name,
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: (
                [THERMOSTAT] if zone_thermostats is None else zone_thermostats
            ),
            CONF_TEMPERATURE_SOURCES: [SENSOR] if sources is None else sources,
        },
    )
    return await _complete_source_forms(hass, result, source_values=source_values)


async def _complete_source_forms(
    hass: HomeAssistant,
    result: config_entries.SubentryFlowResult,
    *,
    source_values: list[dict[str, object]] | None = None,
) -> config_entries.SubentryFlowResult:
    index = 0
    while result["type"] is FlowResultType.FORM and result["step_id"] == "source":
        schema = result["data_schema"]
        assert isinstance(schema, vol.Schema)
        values = {
            marker.schema: marker.description["suggested_value"]
            for marker in schema.schema
        }
        if source_values is not None and index < len(source_values):
            values.update(source_values[index])
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"],
            user_input=values,
        )
        index += 1
    return result


def _errors(result: config_entries.SubentryFlowResult) -> dict[str, str]:
    assert result["type"] is FlowResultType.FORM
    errors: dict[str, str] | None = result["errors"]
    assert errors is not None
    return errors


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_form_has_name_and_multiple_filtered_entity_selector(
    hass: HomeAssistant,
) -> None:
    result = await _start_add(hass, _make_parent(hass))
    schema = result["data_schema"]

    assert result["step_id"] == "user"
    assert isinstance(schema, vol.Schema)
    selectors = {marker.schema: selector for marker, selector in schema.schema.items()}
    assert set(selectors) == {
        CONF_ZONE_NAME,
        CONF_ZONE_THERMOSTAT_ENTITY_IDS,
        CONF_TEMPERATURE_SOURCES,
    }
    assert isinstance(selectors[CONF_ZONE_NAME], TextSelector)
    entity_selector = selectors[CONF_TEMPERATURE_SOURCES]
    assert isinstance(entity_selector, EntitySelector)
    assert entity_selector.config["multiple"] is True
    assert entity_selector.config["filter"] == [
        {"domain": ["climate"]},
        {"domain": ["sensor"], "device_class": ["temperature"]},
    ]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_rejects_parent_without_thermostat(hass: HomeAssistant) -> None:
    entry = _make_parent(hass, data=_parent_data(thermostat=None))
    _set_temperature_sensor(hass)

    result = await _submit_add(hass, entry)

    assert _errors(result)["base"] == "invalid_parent_thermostat"
    assert entry.subentries == {}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_rejects_parent_thermostat_without_current_state(
    hass: HomeAssistant,
) -> None:
    entry = _make_parent(hass)
    hass.states.async_remove(THERMOSTAT)
    _set_temperature_sensor(hass)

    result = await _submit_add(hass, entry)

    assert _errors(result)["base"] == "invalid_parent_thermostat"
    assert entry.subentries == {}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_rejects_malformed_parent(hass: HomeAssistant) -> None:
    entry = _make_parent(hass, data={"equipment_group": {"name": "Broken"}})
    _set_temperature_sensor(hass)

    result = await _submit_add(hass, entry)

    assert _errors(result)["base"] == "invalid_existing_configuration"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_rejects_missing_temperature_source(hass: HomeAssistant) -> None:
    result = await _submit_add(hass, _make_parent(hass))

    assert _errors(result)[CONF_TEMPERATURE_SOURCES] == "missing_entity"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_rejects_unsupported_source_domain(hass: HomeAssistant) -> None:
    hass.states.async_set("binary_sensor.window", "off")
    result = await _submit_add(
        hass,
        _make_parent(hass),
        sources=["binary_sensor.window"],
    )

    assert _errors(result)[CONF_TEMPERATURE_SOURCES] == "wrong_domain"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_rejects_sensor_without_temperature_device_class(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass, device_class="humidity")
    result = await _submit_add(hass, _make_parent(hass))

    assert _errors(result)[CONF_TEMPERATURE_SOURCES] == "wrong_device_class"


@pytest.mark.parametrize(
    ("entity_id", "attributes"),
    [
        (SENSOR, {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE}),
        (CLIMATE_SOURCE, {}),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_accepts_unavailable_existing_sources(
    hass: HomeAssistant,
    entity_id: str,
    attributes: dict[str, object],
) -> None:
    hass.states.async_set(entity_id, "unavailable", attributes)

    with patch.object(hass.config_entries, "async_reload") as reload:
        result = await _submit_add(hass, _make_parent(hass), sources=[entity_id])
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    reload.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_requires_at_least_one_source(hass: HomeAssistant) -> None:
    result = await _submit_add(hass, _make_parent(hass), sources=[])

    assert _errors(result)[CONF_TEMPERATURE_SOURCES] == "no_temperature_sources"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_rejects_duplicate_binding_without_partial_subentry(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    entry = _make_parent(hass)

    result = await _submit_add(hass, entry, sources=[SENSOR, SENSOR])

    assert _errors(result)[CONF_TEMPERATURE_SOURCES] == ("duplicate_temperature_source")
    assert entry.subentries == {}


@pytest.mark.parametrize(
    ("entity_id", "expected_attribute"),
    [(SENSOR, None), (CLIMATE_SOURCE, "current_temperature")],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_maps_sources_with_exact_defaults(
    hass: HomeAssistant,
    entity_id: str,
    expected_attribute: str | None,
) -> None:
    if entity_id == SENSOR:
        _set_temperature_sensor(hass)
    else:
        hass.states.async_set(entity_id, "heat")

    result = await _submit_add(hass, _make_parent(hass), sources=[entity_id])
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    subentry = next(iter(entry.subentries.values()))
    zone = decode_zone_config(subentry.data)
    source = zone.temperature_sources[0]

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert zone.thermostat_entity_ids == (THERMOSTAT,)
    assert source.entity_id == entity_id
    assert source.attribute == expected_attribute
    assert source.offset_c == 0.0
    assert source.weight == 1.0
    assert source.priority == 0
    assert source.enabled is True
    assert source.source_id.value.version == 4


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_first_zone_commit_completes_one_reload_that_observes_zone(
    hass: HomeAssistant,
) -> None:
    """The real flow manager commits the first subentry before reload begins."""
    _set_temperature_sensor(hass)
    entry = _make_parent(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert (
        entry.runtime_data.configuration.state
        is RuntimeConfigurationState.AWAITING_FIRST_ZONE
    )

    with patch.object(
        hass.config_entries,
        "async_reload",
        wraps=hass.config_entries.async_reload,
    ) as reload:
        result = await _submit_add(hass, entry)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    reload.assert_awaited_once_with(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert len(entry.runtime_data.configuration.zones) == 1
    assert len(entry.subentries) == 1


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_later_zone_commit_completes_exactly_one_reload(
    hass: HomeAssistant,
) -> None:
    """Every additional committed zone refreshes the owning runtime once."""
    _set_temperature_sensor(hass)
    _set_temperature_sensor(hass, "sensor.living_room_temperature")
    entry = _make_parent(hass, subentries=[_subentry_data()])
    assert await hass.config_entries.async_setup(entry.entry_id)

    with patch.object(
        hass.config_entries,
        "async_reload",
        wraps=hass.config_entries.async_reload,
    ) as reload:
        result = await _submit_add(
            hass,
            entry,
            name="Living Room",
            sources=["sensor.living_room_temperature"],
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    reload.assert_awaited_once_with(entry.entry_id)
    assert len(entry.subentries) == 2
    assert len(entry.runtime_data.configuration.zones) == 2


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_and_canceled_zone_flows_schedule_no_reload(
    hass: HomeAssistant,
) -> None:
    """Forms and cancellation never trigger a parent reload."""
    entry = _make_parent(hass)
    with patch.object(hass.config_entries, "async_reload") as reload:
        invalid = await _submit_add(hass, entry)
        initial = await _start_add(hass, entry)
        hass.config_entries.subentries.async_abort(initial["flow_id"])
        await hass.async_block_till_done()

    assert invalid["type"] is FlowResultType.FORM
    reload.assert_not_called()
    assert entry.subentries == {}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_failed_subentry_commit_schedules_no_reload(
    hass: HomeAssistant,
) -> None:
    """A framework commit failure cannot race a reload of absent data."""
    _set_temperature_sensor(hass)
    entry = _make_parent(hass)

    with (
        patch.object(
            hass.config_entries,
            "async_add_subentry",
            side_effect=RuntimeError("commit failed"),
        ),
        patch.object(hass.config_entries, "async_reload") as reload,
        pytest.raises(RuntimeError, match="commit failed"),
    ):
        await _submit_add(hass, entry)
    await hass.async_block_till_done()

    reload.assert_not_called()
    assert entry.subentries == {}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_committed_zone_skips_reload_during_core_shutdown(
    hass: HomeAssistant,
) -> None:
    """A committed zone remains durable when core shutdown wins the reload race."""
    _set_temperature_sensor(hass)
    entry = _make_parent(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)

    with (
        patch.object(
            type(hass),
            "is_stopping",
            new_callable=PropertyMock,
            return_value=True,
        ),
        patch.object(hass.config_entries, "async_reload") as reload,
    ):
        result = await _submit_add(hass, entry)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    reload.assert_not_awaited()
    assert len(entry.subentries) == 1


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_accepts_multiple_compatible_sources(hass: HomeAssistant) -> None:
    _set_temperature_sensor(hass)
    hass.states.async_set(CLIMATE_SOURCE, "cool")

    result = await _submit_add(
        hass,
        _make_parent(hass),
        sources=[SENSOR, CLIMATE_SOURCE],
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    persisted = decode_zone_config(next(iter(entry.subentries.values())).data)
    assert [
        (item.entity_id, item.attribute) for item in persisted.temperature_sources
    ] == [
        (SENSOR, None),
        (CLIMATE_SOURCE, "current_temperature"),
    ]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_source_editor_persists_calibration_weight_priority_and_enable(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    result = await _submit_add(
        hass,
        _make_parent(hass),
        source_values=[
            {
                CONF_SOURCE_OFFSET_C: -1.5,
                CONF_SOURCE_WEIGHT: 2.25,
                CONF_SOURCE_PRIORITY: 3,
                CONF_SOURCE_ENABLED: False,
            }
        ],
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    zone = decode_zone_config(
        next(
            iter(hass.config_entries.async_entries(DOMAIN)[0].subentries.values())
        ).data
    )
    source = zone.temperature_sources[0]
    assert source.offset_c == -1.5
    assert source.weight == 2.25
    assert source.priority == 3
    assert source.enabled is False


@pytest.mark.parametrize(
    ("values", "error_key"),
    [
        (
            {
                CONF_SOURCE_OFFSET_C: float("nan"),
                CONF_SOURCE_WEIGHT: 1,
                CONF_SOURCE_PRIORITY: 0,
                CONF_SOURCE_ENABLED: True,
            },
            CONF_SOURCE_OFFSET_C,
        ),
        (
            {
                CONF_SOURCE_OFFSET_C: 0,
                CONF_SOURCE_WEIGHT: 0,
                CONF_SOURCE_PRIORITY: 0,
                CONF_SOURCE_ENABLED: True,
            },
            CONF_SOURCE_WEIGHT,
        ),
        (
            {
                CONF_SOURCE_OFFSET_C: 0,
                CONF_SOURCE_WEIGHT: 1,
                CONF_SOURCE_PRIORITY: 0.5,
                CONF_SOURCE_ENABLED: True,
            },
            CONF_SOURCE_PRIORITY,
        ),
        (
            {
                CONF_SOURCE_OFFSET_C: 0,
                CONF_SOURCE_WEIGHT: 1,
                CONF_SOURCE_PRIORITY: 0,
                CONF_SOURCE_ENABLED: "yes",
            },
            CONF_SOURCE_ENABLED,
        ),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_source_editor_rejects_invalid_metadata_without_commit(
    hass: HomeAssistant,
    values: dict[str, object],
    error_key: str,
) -> None:
    _set_temperature_sensor(hass)
    entry = _make_parent(hass)
    flow = ZoneSubentryFlowHandler()
    flow.hass = hass
    flow.handler = (entry.entry_id, SUBENTRY_TYPE_ZONE)
    flow.context = config_entries.SubentryFlowContext(source=config_entries.SOURCE_USER)
    result = await flow.async_step_user(
        {
            CONF_ZONE_NAME: "Dining Room",
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
            CONF_TEMPERATURE_SOURCES: [SENSOR],
        }
    )
    assert result["step_id"] == "source"

    result = await flow.async_step_source(values)

    assert _errors(result)[error_key].startswith("invalid_source_")
    assert entry.subentries == {}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_shared_zone_updates_priority_and_thermostat_membership(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    _set_temperature_sensor(hass, "sensor.upstairs_temperature")
    hass.states.async_set(SECOND_THERMOSTAT, "cool")
    entry = _make_parent(
        hass,
        data=_multi_parent_data(second_zone_configured=False),
        subentries=[_subentry_data()],
    )

    result = await _submit_add(
        hass,
        entry,
        name="Upstairs",
        sources=["sensor.upstairs_temperature"],
        zone_thermostats=[SECOND_THERMOSTAT],
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    zones = [decode_zone_config(item.data) for item in entry.subentries.values()]
    assert {zone.thermostat_entity_ids for zone in zones} == {
        (THERMOSTAT,),
        (SECOND_THERMOSTAT,),
    }
    group = entry.data["equipment_group"]
    assert isinstance(group, dict)
    policy = group["shared_policy"]
    assert isinstance(policy, dict)
    assert policy["zone_priority_order"] == [ZONE_ID, str(zones[1].zone_id)]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_zone_reconfigure_cannot_leave_parent_thermostat_unassigned(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    _set_temperature_sensor(hass, "sensor.upstairs_temperature")
    hass.states.async_set(SECOND_THERMOSTAT, "cool")
    second = _zone_data(
        name="Upstairs",
        zone_id=SECOND_ZONE_ID,
        thermostats=[SECOND_THERMOSTAT],
        sources=[
            _source(
                "sensor.upstairs_temperature",
                source_id="ce30dafc-fadd-4cc4-b261-8a896d5a6d12",
            )
        ],
    )
    entry = _make_parent(
        hass,
        data=_multi_parent_data(second_zone_configured=True),
        subentries=[
            _subentry_data(),
            _subentry_data(
                data=second,
                name="Upstairs",
                subentry_id="zone-subentry-2",
            ),
        ],
    )

    result = await _submit_reconfigure(
        hass,
        await _start_reconfigure(hass, entry),
        zone_thermostats=[SECOND_THERMOSTAT],
    )

    assert _errors(result)[CONF_ZONE_THERMOSTAT_ENTITY_IDS] == ("unassigned_thermostat")


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_suggests_current_name_and_sources(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    entry = _make_parent(hass, subentries=[_subentry_data()])

    result = await _start_reconfigure(hass, entry)
    schema = result["data_schema"]
    assert isinstance(schema, vol.Schema)
    suggested = {
        marker.schema: marker.description["suggested_value"] for marker in schema.schema
    }

    assert suggested == {
        CONF_ZONE_NAME: "Dining Room",
        CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
        CONF_TEMPERATURE_SOURCES: [SENSOR],
    }


def _metadata_zone_data() -> dict[str, object]:
    data = _zone_data(
        sources=[
            _source(offset_c=1.25, weight=2.5, priority=4, enabled=False),
            _source(
                CLIMATE_SOURCE,
                source_id="ce30dafc-fadd-4cc4-b261-8a896d5a6d12",
                attribute="current_temperature",
            ),
        ]
    )
    data["humidity_sources"] = [
        {
            "source_id": "3d59d933-a9f3-4dfd-bdf7-5288cd9f228a",
            "entity_id": "sensor.humidity",
            "attribute": None,
            "offset_pct": 0.0,
            "weight": 1.0,
            "priority": 0,
            "enabled": True,
        }
    ]
    data["window_door_entity_ids"] = ["binary_sensor.window"]
    data["occupancy_entity_ids"] = ["binary_sensor.occupied"]
    data["stage_entity_ids"] = ["sensor.stage"]
    data["fan_entity_ids"] = ["fan.air_handler"]
    return data


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_preserves_identity_metadata_and_unrelated_fields(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    hass.states.async_set(CLIMATE_SOURCE, "heat")
    data = _metadata_zone_data()
    entry = _make_parent(hass, subentries=[_subentry_data(data=data)])
    before = entry.subentries["zone-subentry-1"]
    initial = await _start_reconfigure(hass, entry)

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await _submit_reconfigure(
            hass,
            initial,
            name="Great Room",
            sources=[CLIMATE_SOURCE, SENSOR],
        )

    after = entry.subentries["zone-subentry-1"]
    zone = decode_zone_config(after.data)
    assert result["type"] is FlowResultType.ABORT
    reload.assert_called_once_with(entry.entry_id)
    assert (after.subentry_id, after.unique_id, after.data["zone_id"]) == (
        before.subentry_id,
        before.unique_id,
        before.data["zone_id"],
    )
    assert zone.temperature_sources[0].source_id == ObservationSourceId.parse(SOURCE_ID)
    assert zone.temperature_sources[0].offset_c == 1.25
    assert zone.temperature_sources[0].weight == 2.5
    assert zone.temperature_sources[0].priority == 4
    assert zone.temperature_sources[0].enabled is False
    for field in (
        "humidity_sources",
        "window_door_entity_ids",
        "occupancy_entity_ids",
        "stage_entity_ids",
        "fan_entity_ids",
    ):
        assert after.data[field] == data[field]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_adds_and_removes_sources_with_stable_retained_id(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    _set_temperature_sensor(hass, "sensor.second")
    hass.states.async_set(CLIMATE_SOURCE, "heat")
    data = _metadata_zone_data()
    entry = _make_parent(hass, subentries=[_subentry_data(data=data)])

    with patch.object(hass.config_entries, "async_schedule_reload"):
        result = await _submit_reconfigure(
            hass,
            await _start_reconfigure(hass, entry),
            sources=[SENSOR, "sensor.second"],
        )

    assert result["type"] is FlowResultType.ABORT
    sources = decode_zone_config(
        entry.subentries["zone-subentry-1"].data
    ).temperature_sources
    assert [source.entity_id for source in sources] == [SENSOR, "sensor.second"]
    assert str(sources[0].source_id) == SOURCE_ID
    assert sources[1].source_id != sources[0].source_id


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_duplicate_reconfigure_does_not_mutate(hass: HomeAssistant) -> None:
    _set_temperature_sensor(hass)
    entry = _make_parent(hass, subentries=[_subentry_data()])
    before = deepcopy(dict(entry.subentries["zone-subentry-1"].data))

    result = await _submit_reconfigure(
        hass,
        await _start_reconfigure(hass, entry),
        sources=[SENSOR, SENSOR],
    )

    assert _errors(result)[CONF_TEMPERATURE_SOURCES] == ("duplicate_temperature_source")
    assert dict(entry.subentries["zone-subentry-1"].data) == before


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_same_selection_and_reorder_do_not_reload(hass: HomeAssistant) -> None:
    _set_temperature_sensor(hass)
    hass.states.async_set(CLIMATE_SOURCE, "heat")
    data = _metadata_zone_data()
    entry = _make_parent(hass, subentries=[_subentry_data(data=data)])

    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
        result = await _submit_reconfigure(
            hass,
            await _start_reconfigure(hass, entry),
            sources=[CLIMATE_SOURCE, SENSOR],
        )

    assert result["type"] is FlowResultType.ABORT
    reload.assert_not_called()
    sources = decode_zone_config(
        entry.subentries["zone-subentry-1"].data
    ).temperature_sources
    assert [str(source.source_id) for source in sources] == [
        SOURCE_ID,
        "ce30dafc-fadd-4cc4-b261-8a896d5a6d12",
    ]


@pytest.mark.parametrize(
    ("method", "error"),
    [
        ("async_update_subentry", ValueError("framework update failed")),
        ("async_schedule_reload", RuntimeError("framework reload failed")),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_framework_errors_propagate(
    hass: HomeAssistant,
    method: str,
    error: Exception,
) -> None:
    _set_temperature_sensor(hass)
    entry = _make_parent(hass, subentries=[_subentry_data()])
    flow = ZoneSubentryFlowHandler()
    flow.hass = hass
    flow.handler = (entry.entry_id, SUBENTRY_TYPE_ZONE)
    flow.context = config_entries.SubentryFlowContext(
        source=config_entries.SOURCE_RECONFIGURE,
        subentry_id="zone-subentry-1",
    )

    result = await flow.async_step_reconfigure(
        {
            CONF_ZONE_NAME: "Great Room",
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
            CONF_TEMPERATURE_SOURCES: [SENSOR],
        }
    )
    assert result["step_id"] == "source"
    with (
        patch.object(hass.config_entries, method, side_effect=error),
        pytest.raises(type(error), match=str(error)),
    ):
        await flow.async_step_source(
            {
                CONF_SOURCE_OFFSET_C: 0.0,
                CONF_SOURCE_WEIGHT: 1.0,
                CONF_SOURCE_PRIORITY: 0,
                CONF_SOURCE_ENABLED: True,
            }
        )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_add_never_consumes_zone_or_source_ids(
    hass: HomeAssistant,
) -> None:
    entry = _make_parent(hass)
    with (
        patch(
            "custom_components.intelligent_climate.zone_flow.ZoneId.new"
        ) as zone_id_new,
        patch(
            "custom_components.intelligent_climate.zone_flow.ObservationSourceId.new"
        ) as source_id_new,
    ):
        result = await _submit_add(hass, entry)

    assert _errors(result)[CONF_TEMPERATURE_SOURCES] == "missing_entity"
    zone_id_new.assert_not_called()
    source_id_new.assert_not_called()
    assert entry.subentries == {}


@pytest.mark.parametrize(
    ("user_input", "error_key"),
    [
        ({}, "base"),
        (
            {
                CONF_ZONE_NAME: "Dining Room",
                CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
                CONF_TEMPERATURE_SOURCES: [SENSOR],
                "future": True,
            },
            "base",
        ),
        (
            {
                CONF_ZONE_NAME: "   ",
                CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
                CONF_TEMPERATURE_SOURCES: [SENSOR],
            },
            CONF_ZONE_NAME,
        ),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_direct_add_contains_defensive_input_errors(
    hass: HomeAssistant,
    user_input: dict[str, object],
    error_key: str,
) -> None:
    entry = _make_parent(hass)
    flow = ZoneSubentryFlowHandler()
    flow.hass = hass
    flow.handler = (entry.entry_id, SUBENTRY_TYPE_ZONE)
    flow.context = config_entries.SubentryFlowContext(source=config_entries.SOURCE_USER)

    result = await flow.async_step_user(user_input)

    assert error_key in _errors(result)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_duplicate_name_and_malformed_sibling_fail_closed(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    entry = _make_parent(hass, subentries=[_subentry_data()])

    duplicate = await _submit_add(hass, entry, name="DINING ROOM")
    assert _errors(duplicate)[CONF_ZONE_NAME] == "duplicate_name"

    malformed_data = _zone_data(name="Broken")
    malformed_data["zone_id"] = "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"
    malformed = config_entries.ConfigSubentryDataWithId(
        data=malformed_data,
        subentry_id="zone-subentry-2",
        subentry_type="future_type",
        title="Broken",
        unique_id=str(malformed_data["zone_id"]),
    )
    hass.states.async_set("climate.second", "heat")
    other = _make_parent(
        hass,
        data=_parent_data(thermostat="climate.second"),
        subentries=[malformed],
    )
    failed = await _submit_add(
        hass,
        other,
        name="Living Room",
        zone_thermostats=["climate.second"],
    )
    assert _errors(failed)["base"] == "invalid_zone_data"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_add_schema_failure_is_recoverable(hass: HomeAssistant) -> None:
    _set_temperature_sensor(hass)
    entry = _make_parent(hass)
    with patch(
        "custom_components.intelligent_climate.zone_flow.decode_zone_config",
        side_effect=SchemaValidationError("zone", "invalid"),
    ):
        result = await _submit_add(hass, entry)

    assert _errors(result)["base"] == "invalid_zone_data"
    assert entry.subentries == {}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_missing_or_malformed_target_aborts(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    entry = _make_parent(hass)
    missing = await _start_reconfigure(hass, entry, "missing")
    assert missing["reason"] == "invalid_zone_data"

    bad_data = _zone_data()
    malformed = config_entries.ConfigSubentryDataWithId(
        data=bad_data,
        subentry_id="zone-subentry-1",
        subentry_type=SUBENTRY_TYPE_ZONE,
        title="Wrong title",
        unique_id=ZONE_ID,
    )
    entry_with_bad_zone = _make_parent(hass, subentries=[malformed])
    invalid = await _start_reconfigure(hass, entry_with_bad_zone)
    assert invalid["reason"] == "invalid_zone_data"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_rejects_wrong_parent_membership(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    data = _zone_data()
    data["thermostat_entity_ids"] = ["climate.other"]
    entry = _make_parent(hass, subentries=[_subentry_data(data=data)])

    result = await _start_reconfigure(hass, entry)

    assert result["reason"] == "invalid_existing_configuration"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_rejects_missing_parent_thermostat_state(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    entry = _make_parent(hass, subentries=[_subentry_data()])
    hass.states.async_remove(THERMOSTAT)

    result = await _start_reconfigure(hass, entry)

    assert result["reason"] == "missing_entity"


@pytest.mark.parametrize(
    ("entity_id", "device_class", "expected"),
    [
        ("sensor.missing", None, "missing_entity"),
        ("binary_sensor.window", None, "wrong_domain"),
        ("sensor.humidity", SensorDeviceClass.HUMIDITY, "wrong_device_class"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_keeps_strict_live_source_validation(
    hass: HomeAssistant,
    entity_id: str,
    device_class: SensorDeviceClass | None,
    expected: str,
) -> None:
    _set_temperature_sensor(hass)
    if entity_id != "sensor.missing":
        hass.states.async_set(
            entity_id,
            "20",
            {} if device_class is None else {ATTR_DEVICE_CLASS: device_class},
        )
    entry = _make_parent(hass, subentries=[_subentry_data()])

    result = await _submit_reconfigure(
        hass,
        await _start_reconfigure(hass, entry),
        sources=[entity_id],
    )

    assert _errors(result)[CONF_TEMPERATURE_SOURCES] == expected


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reconfigure_contains_input_sibling_and_schema_errors(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    second_data = _zone_data(name="Living Room")
    second_data["zone_id"] = "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"
    entry = _make_parent(
        hass,
        subentries=[
            _subentry_data(),
            _subentry_data(
                data=second_data,
                name="Living Room",
                subentry_id="zone-subentry-2",
            ),
        ],
    )
    initial = await _start_reconfigure(hass, entry, "zone-subentry-2")

    blank = await _submit_reconfigure(hass, initial, name="   ")
    assert _errors(blank)[CONF_ZONE_NAME] == "invalid_name"
    duplicate = await _submit_reconfigure(hass, blank, name="DINING ROOM")
    assert _errors(duplicate)[CONF_ZONE_NAME] == "duplicate_name"
    missing_source = await _submit_reconfigure(
        hass,
        duplicate,
        name="Living Room",
        sources=["sensor.missing"],
    )
    assert _errors(missing_source)[CONF_TEMPERATURE_SOURCES] == "missing_entity"

    existing_zone = decode_zone_config(second_data)
    with patch(
        "custom_components.intelligent_climate.zone_flow.decode_zone_config",
        side_effect=[existing_zone, SchemaValidationError("zone", "invalid")],
    ):
        schema_error = await _submit_reconfigure(
            hass,
            missing_source,
            name="Family Room",
        )
    assert _errors(schema_error)["base"] == "invalid_zone_data"


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_validation_helpers_reject_nonlist_and_duplicate_persisted_sources(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    with pytest.raises(EntityValidationError, match="invalid_entity_selection"):
        validate_live_temperature_selection(hass, SENSOR)

    source = TemperatureSource(
        source_id=ObservationSourceId.parse(SOURCE_ID),
        entity_id=SENSOR,
        attribute=None,
        offset_c=0.0,
        weight=1.0,
        priority=0,
        enabled=True,
    )
    duplicate = TemperatureSource(
        source_id=ObservationSourceId.parse("ce30dafc-fadd-4cc4-b261-8a896d5a6d12"),
        entity_id=SENSOR,
        attribute=None,
        offset_c=0.0,
        weight=1.0,
        priority=0,
        enabled=True,
    )
    with pytest.raises(EntityValidationError, match="duplicate_temperature_source"):
        validate_persisted_temperature_sources((source, duplicate))


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_zone_flow_private_defensive_boundaries(hass: HomeAssistant) -> None:
    malformed_identity = config_entries.ConfigSubentry(
        data=MappingProxyType(_zone_data()),
        subentry_id="zone-subentry-bad",
        subentry_type=SUBENTRY_TYPE_ZONE,
        title="Dining Room",
        unique_id="7294e2ec-6f1f-4fbc-9f30-4a44d356cce8",
    )
    with pytest.raises(SchemaValidationError, match="config subentry unique ID"):
        zone_flow_module.decode_zone_subentry(malformed_identity)

    entry = _make_parent(hass)
    with (
        patch(
            "custom_components.intelligent_climate.zone_flow."
            "validate_live_thermostat_selections",
            return_value=(),
        ),
        pytest.raises(EntityValidationError, match="invalid_parent_thermostat"),
    ):
        zone_flow_module._parent_thermostats(hass, entry)

    hass.states.async_set("climate.outside_group", "heat")
    with pytest.raises(EntityValidationError, match="invalid_entity_selection"):
        zone_flow_module._zone_thermostats(
            hass,
            ["climate.outside_group"],
            parent_entity_ids=(THERMOSTAT,),
            entry_id=entry.entry_id,
        )

    errors: dict[str, str] = {}
    zone_flow_module._set_parent_error(
        errors,
        EntityValidationError(EntityValidationCode.INVALID_EXISTING_CONFIGURATION),
    )
    assert errors["base"] == "invalid_existing_configuration"

    for value in (True, "1"):
        with pytest.raises(ValueError):
            zone_flow_module._finite_number(value)
        with pytest.raises(ValueError):
            zone_flow_module._nonnegative_integer(value)

    flow = ZoneSubentryFlowHandler()
    flow.hass = hass
    flow.handler = ("missing-entry", SUBENTRY_TYPE_ZONE)
    flow.context = config_entries.SubentryFlowContext(source=config_entries.SOURCE_USER)
    result = await flow.async_step_user()
    assert _errors(result)["base"] == "invalid_zone_data"

    with patch.object(hass.config_entries, "async_reload") as reload:
        await zone_flow_module._async_reload_after_zone_commit(hass, entry, ZONE_ID)
    reload.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_zone_reconfigure_and_source_defensive_abort_paths(
    hass: HomeAssistant,
) -> None:
    _set_temperature_sensor(hass)
    entry = _make_parent(hass, subentries=[_subentry_data()])
    flow = ZoneSubentryFlowHandler()
    flow.hass = hass
    flow.handler = (entry.entry_id, SUBENTRY_TYPE_ZONE)
    flow.context = config_entries.SubentryFlowContext(
        source=config_entries.SOURCE_RECONFIGURE,
        subentry_id="zone-subentry-1",
    )

    result = await flow.async_step_reconfigure(
        {
            CONF_ZONE_NAME: "Dining Room",
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
            CONF_TEMPERATURE_SOURCES: [SENSOR],
            "future": True,
        }
    )
    assert _errors(result)["base"] == "invalid_input"
    result = await flow.async_step_reconfigure(
        {
            CONF_ZONE_NAME: "Dining Room",
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: ["climate.missing"],
            CONF_TEMPERATURE_SOURCES: [SENSOR],
        }
    )
    assert _errors(result)[CONF_ZONE_THERMOSTAT_ENTITY_IDS] == "missing_entity"

    result = await flow.async_step_reconfigure(
        {
            CONF_ZONE_NAME: "Dining Room",
            CONF_ZONE_THERMOSTAT_ENTITY_IDS: [THERMOSTAT],
            CONF_TEMPERATURE_SOURCES: [SENSOR],
        }
    )
    assert result["step_id"] == "source"
    result = await flow.async_step_source(
        {
            CONF_SOURCE_OFFSET_C: 0,
            CONF_SOURCE_WEIGHT: 1,
            CONF_SOURCE_PRIORITY: 0,
            CONF_SOURCE_ENABLED: True,
            "future": True,
        }
    )
    assert _errors(result)["base"] == "invalid_input"

    with patch(
        "custom_components.intelligent_climate.zone_flow.decode_zone_config",
        return_value=replace(flow._pending_zone, name="Different"),
    ):
        result = await flow.async_step_source(
            {
                CONF_SOURCE_OFFSET_C: 0,
                CONF_SOURCE_WEIGHT: 1,
                CONF_SOURCE_PRIORITY: 0,
                CONF_SOURCE_ENABLED: True,
            }
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_zone_data"

    flow._begin_source_configuration(
        "reconfigure",
        decode_zone_config(entry.subentries["zone-subentry-1"].data),
    )
    flow.context = config_entries.SubentryFlowContext(
        source=config_entries.SOURCE_RECONFIGURE,
        subentry_id="missing",
    )
    result = await flow.async_step_source(
        {
            CONF_SOURCE_OFFSET_C: 0,
            CONF_SOURCE_WEIGHT: 1,
            CONF_SOURCE_PRIORITY: 0,
            CONF_SOURCE_ENABLED: True,
        }
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_zone_data"
