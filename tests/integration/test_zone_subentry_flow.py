"""Test native Home Assistant zone config-subentry flows."""

from __future__ import annotations

from copy import deepcopy
from typing import cast
from unittest.mock import patch

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

from custom_components.intelligent_climate.const import (
    CONF_TEMPERATURE_SOURCES,
    CONF_ZONE_NAME,
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
    EntityValidationError,
    validate_persisted_temperature_sources,
    validate_temperature_selection,
)
from custom_components.intelligent_climate.zone_flow import ZoneSubentryFlowHandler

GROUP_ID = "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
ZONE_ID = "99246285-6f02-4e8a-94ed-bdfd4a5e62c4"
SOURCE_ID = "f15f73b1-ea59-4b28-819f-7b99acf065bf"
THERMOSTAT = "climate.main_floor"
SENSOR = "sensor.dining_room_temperature"
CLIMATE_SOURCE = "climate.dining_room"


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


def _zone_data(
    *,
    name: str = "Dining Room",
    zone_id: str = ZONE_ID,
    sources: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "data_version": 1,
        "zone_id": zone_id,
        "name": name,
        "thermostat_entity_ids": [THERMOSTAT],
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
) -> config_entries.SubentryFlowResult:
    initial = await _start_add(hass, entry)
    if sources is None:
        sources = [SENSOR]
    return await hass.config_entries.subentries.async_configure(
        initial["flow_id"],
        user_input={CONF_ZONE_NAME: name, CONF_TEMPERATURE_SOURCES: sources},
    )


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
) -> config_entries.SubentryFlowResult:
    return await hass.config_entries.subentries.async_configure(
        initial["flow_id"],
        user_input={
            CONF_ZONE_NAME: name,
            CONF_TEMPERATURE_SOURCES: [SENSOR] if sources is None else sources,
        },
    )


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
    assert set(selectors) == {CONF_ZONE_NAME, CONF_TEMPERATURE_SOURCES}
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

    result = await _submit_add(hass, _make_parent(hass), sources=[entity_id])

    assert result["type"] is FlowResultType.CREATE_ENTRY


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
async def test_first_zone_commit_schedules_one_reload_that_observes_zone(
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
        "async_schedule_reload",
        wraps=hass.config_entries.async_schedule_reload,
    ) as reload:
        result = await _submit_add(hass, entry)
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    reload.assert_called_once_with(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.LOADED
    assert len(entry.runtime_data.configuration.zones) == 1
    assert len(entry.subentries) == 1


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_later_zone_commit_schedules_exactly_one_reload(
    hass: HomeAssistant,
) -> None:
    """Every additional committed zone refreshes the owning runtime once."""
    _set_temperature_sensor(hass)
    _set_temperature_sensor(hass, "sensor.living_room_temperature")
    entry = _make_parent(hass, subentries=[_subentry_data()])
    assert await hass.config_entries.async_setup(entry.entry_id)

    with patch.object(
        hass.config_entries,
        "async_schedule_reload",
        wraps=hass.config_entries.async_schedule_reload,
    ) as reload:
        result = await _submit_add(
            hass,
            entry,
            name="Living Room",
            sources=["sensor.living_room_temperature"],
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    reload.assert_called_once_with(entry.entry_id)
    assert len(entry.subentries) == 2
    assert len(entry.runtime_data.configuration.zones) == 2


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_and_canceled_zone_flows_schedule_no_reload(
    hass: HomeAssistant,
) -> None:
    """Forms and cancellation never trigger a parent reload."""
    entry = _make_parent(hass)
    with patch.object(hass.config_entries, "async_schedule_reload") as reload:
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
        patch.object(hass.config_entries, "async_schedule_reload") as reload,
        pytest.raises(RuntimeError, match="commit failed"),
    ):
        await _submit_add(hass, entry)
    await hass.async_block_till_done()

    reload.assert_not_called()
    assert entry.subentries == {}


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

    with (
        patch.object(hass.config_entries, method, side_effect=error),
        pytest.raises(type(error), match=str(error)),
    ):
        await flow.async_step_reconfigure(
            {CONF_ZONE_NAME: "Great Room", CONF_TEMPERATURE_SOURCES: [SENSOR]}
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
                CONF_TEMPERATURE_SOURCES: [SENSOR],
                "future": True,
            },
            "base",
        ),
        (
            {CONF_ZONE_NAME: "   ", CONF_TEMPERATURE_SOURCES: [SENSOR]},
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
    failed = await _submit_add(hass, other, name="Living Room")
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
        validate_temperature_selection(hass, SENSOR)

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
        validate_persisted_temperature_sources(hass, (source, duplicate))
