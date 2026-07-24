"""Test the genuine Home Assistant read-only climate platform lifecycle."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from typing import cast
from unittest.mock import patch

import pytest
from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
)
from homeassistant.components.climate import (
    DOMAIN as CLIMATE_DOMAIN,
)
from homeassistant.components.climate.const import (
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigSubentryDataWithId
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util.dt import utcnow
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.intelligent_climate.climate import (
    IntelligentClimateZoneClimateEntity,
)
from custom_components.intelligent_climate.const import (
    DOMAIN,
    PLATFORMS,
    SUBENTRY_TYPE_ZONE,
)
from custom_components.intelligent_climate.models import (
    DEFAULT_OPTIONS,
    encode_options,
)

GROUP_ID = "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
ZONE_IDS = (
    "99246285-6f02-4e8a-94ed-bdfd4a5e62c4",
    "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8",
)
SOURCE_IDS = (
    "f15f73b1-ea59-4b28-819f-7b99acf065bf",
    "ce30dafc-fadd-4cc4-b261-8a896d5a6d12",
)
HUMIDITY_SOURCE_ID = "4d61f93e-a98a-4ce1-bd4a-58b571bdd115"
THERMOSTAT = "climate.physical"
SENSORS = ("sensor.dining_room_temperature", "sensor.living_room_temperature")
HUMIDITY_SENSOR = "sensor.dining_room_humidity"


def _parent_data(
    *,
    name: str = "Main Floor HVAC",
    thermostat: str | None = THERMOSTAT,
) -> dict[str, object]:
    return {
        "equipment_group": {
            "equipment_group_id": GROUP_ID,
            "name": name,
            "equipment_type": "air_source_heat_pump",
            "relationship": "single_system",
            "thermostats": (
                []
                if thermostat is None
                else [{"entity_id": thermostat, "role": "primary"}]
            ),
            "shared_policy": None,
        }
    }


def _temperature_source(
    index: int,
    *,
    entity_id: str | None = None,
) -> dict[str, object]:
    return {
        "source_id": SOURCE_IDS[index],
        "entity_id": entity_id or SENSORS[index],
        "attribute": None,
        "offset_c": 0.0,
        "weight": 1.0,
        "priority": 0,
        "enabled": True,
    }


def _zone_data(
    index: int,
    *,
    name: str | None = None,
    humidity: bool = False,
    empty: bool = False,
) -> dict[str, object]:
    return {
        "data_version": 1,
        "zone_id": ZONE_IDS[index],
        "name": name or ("Dining Room" if index == 0 else "Living Room"),
        "thermostat_entity_ids": [] if empty else [THERMOSTAT],
        "temperature_sources": [] if empty else [_temperature_source(index)],
        "humidity_sources": (
            [
                {
                    "source_id": HUMIDITY_SOURCE_ID,
                    "entity_id": HUMIDITY_SENSOR,
                    "attribute": None,
                    "offset_pct": 0.0,
                    "weight": 1.0,
                    "priority": 0,
                    "enabled": True,
                }
            ]
            if humidity and not empty
            else []
        ),
        "window_door_entity_ids": [],
        "occupancy_entity_ids": [],
        "stage_entity_ids": [],
        "fan_entity_ids": [],
    }


def _subentry(
    index: int,
    *,
    data: dict[str, object] | None = None,
) -> ConfigSubentryDataWithId:
    zone = _zone_data(index) if data is None else data
    return ConfigSubentryDataWithId(
        data=zone,
        subentry_id=f"zone-subentry-{index + 1}",
        subentry_type=SUBENTRY_TYPE_ZONE,
        title=str(zone["name"]),
        unique_id=str(zone["zone_id"]),
    )


def _entry(
    *,
    zones: list[ConfigSubentryDataWithId] | None = None,
    data: dict[str, object] | None = None,
    observation_enabled: bool = True,
    entry_id: str = "entry-1",
) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=entry_id,
        title="Main Floor HVAC",
        unique_id=GROUP_ID,
        data=_parent_data() if data is None else data,
        options=dict(
            encode_options(
                replace(
                    DEFAULT_OPTIONS,
                    observation_enabled=observation_enabled,
                    startup_reconciliation_seconds=60,
                )
            )
        ),
        subentries_data=[_subentry(0)] if zones is None else zones,
        version=1,
        minor_version=0,
    )


def _set_states(
    hass: HomeAssistant,
    *,
    display_unit: UnitOfTemperature = UnitOfTemperature.CELSIUS,
    mode: HVACMode = HVACMode.HEAT,
    action: HVACAction | None = HVACAction.HEATING,
    target: float | None = 21.0,
    low: float | None = None,
    high: float | None = None,
    sensor_values: tuple[float, ...] = (20.4, 22.0),
    humidity: float = 47.5,
) -> None:
    attributes: dict[str, object] = {
        ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL],
        ATTR_SUPPORTED_FEATURES: int(ClimateEntityFeature.TARGET_TEMPERATURE),
        ATTR_CURRENT_TEMPERATURE: sensor_values[0],
        ATTR_CURRENT_HUMIDITY: humidity,
    }
    if action is not None:
        attributes[ATTR_HVAC_ACTION] = action
    if target is not None:
        attributes[ATTR_TEMPERATURE] = target
    if low is not None:
        attributes[ATTR_TARGET_TEMP_LOW] = low
    if high is not None:
        attributes[ATTR_TARGET_TEMP_HIGH] = high
    now = utcnow()
    hass.states.async_set(
        THERMOSTAT,
        mode,
        attributes,
        timestamp=now.timestamp(),
    )
    for entity_id, value in zip(SENSORS, sensor_values, strict=False):
        hass.states.async_set(
            entity_id,
            str(value),
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                ATTR_UNIT_OF_MEASUREMENT: display_unit,
            },
            timestamp=now.timestamp(),
        )
    hass.states.async_set(
        HUMIDITY_SENSOR,
        str(humidity),
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
            ATTR_UNIT_OF_MEASUREMENT: "%",
        },
        timestamp=now.timestamp(),
    )


async def _setup_entry(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    *,
    finish_reconciliation: bool = True,
) -> ConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    if finish_reconciliation and entry.runtime_data.data.reconciling:
        async_fire_time_changed(
            hass,
            entry.runtime_data.data.calculated_at + timedelta(seconds=61),
        )
        await hass.async_block_till_done()
    return cast(ConfigEntry, entry)


def _entity_id(hass: HomeAssistant, zone_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        Platform.CLIMATE,
        DOMAIN,
        f"{zone_id}:zone",
    )
    assert entity_id is not None
    return entity_id


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_inventory_order_identity_subentries_and_virtual_devices(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    zones = [_subentry(0), _subentry(1)]
    entry = await _setup_entry(hass, _entry(zones=zones))
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)

    registry_entries = [
        item
        for item in er.async_entries_for_config_entry(
            entity_registry,
            entry.entry_id,
        )
        if item.domain == Platform.CLIMATE
    ]
    assert [item.unique_id for item in registry_entries] == [
        f"{ZONE_IDS[0]}:zone",
        f"{ZONE_IDS[1]}:zone",
    ]
    assert [item.config_subentry_id for item in registry_entries] == [
        zones[0]["subentry_id"],
        zones[1]["subentry_id"],
    ]
    assert all(item.supported_features == 0 for item in registry_entries)
    assert all(hass.states.get(item.entity_id) is not None for item in registry_entries)

    group_device = device_registry.async_get_device(identifiers={(DOMAIN, GROUP_ID)})
    assert group_device is not None
    assert group_device.name == "Main Floor HVAC"
    assert group_device.config_entries_subentries[entry.entry_id] == {None}
    zone_devices = [
        device_registry.async_get_device(identifiers={(DOMAIN, zone_id)})
        for zone_id in ZONE_IDS
    ]
    assert all(device is not None for device in zone_devices)
    assert [device.name for device in zone_devices if device is not None] == [
        "Dining Room",
        "Living Room",
    ]
    assert all(
        device is not None and device.via_device_id == group_device.id
        for device in zone_devices
    )
    assert [
        device.config_entries_subentries[entry.entry_id]
        for device in zone_devices
        if device is not None
    ] == [{zones[0]["subentry_id"]}, {zones[1]["subentry_id"]}]

    integration_devices = [
        device
        for device in device_registry.devices.values()
        if any(identifier[0] == DOMAIN for identifier in device.identifiers)
    ]
    assert len(integration_devices) == 3
    assert {platform.value for platform in PLATFORMS} == {CLIMATE_DOMAIN}
    assert not any(
        state.domain in {"sensor", "binary_sensor", "switch", "event"}
        and state.entity_id.startswith(f"{state.domain}.intelligent_climate")
        for state in hass.states.async_all()
    )
    assert DOMAIN not in hass.services.async_services()

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_empty_skeleton_creates_no_zone_entity_and_disabled_keeps_one(
    hass: HomeAssistant,
) -> None:
    empty_zone = _zone_data(0, empty=True)
    empty = _entry(
        data=_parent_data(thermostat=None),
        zones=[_subentry(0, data=empty_zone)],
        entry_id="empty-entry",
    )
    empty_entry = await _setup_entry(hass, empty)
    assert (
        er.async_entries_for_config_entry(
            er.async_get(hass),
            empty_entry.entry_id,
        )
        == []
    )
    assert await hass.config_entries.async_unload(empty_entry.entry_id)

    _set_states(hass)
    disabled_entry = await _setup_entry(
        hass,
        _entry(observation_enabled=False, entry_id="disabled-entry"),
    )
    disabled_state = hass.states.get(_entity_id(hass, ZONE_IDS[0]))
    assert disabled_state is not None
    assert disabled_state.state == "unavailable"
    assert ATTR_CURRENT_TEMPERATURE not in disabled_state.attributes
    assert await hass.config_entries.async_unload(disabled_entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_awaiting_first_zone_creates_only_equipment_group_device(
    hass: HomeAssistant,
) -> None:
    """Platform setup stays successful without orphan zone registry entries."""
    _set_states(hass)
    entry = await _setup_entry(
        hass,
        _entry(zones=[], entry_id="awaiting-first-zone"),
        finish_reconciliation=False,
    )

    assert er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id) == []
    group_device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, GROUP_ID)})
    assert group_device is not None
    assert group_device.config_entries_subentries[entry.entry_id] == {None}
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("fahrenheit", "source_value", "target", "expected"),
    [
        (False, 20.4, 21.0, (20.4, 21.0)),
        (True, 68.72, 69.8, (68.7, 69.8)),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_actual_state_serialization_in_celsius_and_fahrenheit(
    hass: HomeAssistant,
    fahrenheit: bool,
    source_value: float,
    target: float,
    expected: tuple[float, float],
) -> None:
    unit = UnitOfTemperature.FAHRENHEIT if fahrenheit else UnitOfTemperature.CELSIUS
    if fahrenheit:
        hass.config.units = US_CUSTOMARY_SYSTEM
    _set_states(
        hass,
        display_unit=unit,
        sensor_values=(source_value,),
        target=target,
    )
    zone = _zone_data(0, humidity=True)
    entry = await _setup_entry(hass, _entry(zones=[_subentry(0, data=zone)]))

    state = hass.states.get(_entity_id(hass, ZONE_IDS[0]))
    assert state is not None
    assert state.state == HVACMode.HEAT
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == expected[0]
    assert state.attributes[ATTR_TEMPERATURE] == expected[1]
    assert state.attributes[ATTR_CURRENT_HUMIDITY] == 47.5
    assert state.attributes[ATTR_HVAC_ACTION] == HVACAction.HEATING
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    assert ATTR_TARGET_TEMP_LOW not in state.attributes
    assert ATTR_TARGET_TEMP_HIGH not in state.attributes

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_target_range_serializes_without_writable_feature(
    hass: HomeAssistant,
) -> None:
    _set_states(hass, target=None, low=18.0, high=24.0)
    entry = await _setup_entry(hass, _entry())

    state = hass.states.get(_entity_id(hass, ZONE_IDS[0]))
    assert state is not None
    assert state.attributes[ATTR_TARGET_TEMP_LOW] == 18.0
    assert state.attributes[ATTR_TARGET_TEMP_HIGH] == 24.0
    assert ATTR_TEMPERATURE not in state.attributes
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 0
    registry_entry = er.async_get(hass).async_get(state.entity_id)
    assert registry_entry is not None
    assert registry_entry.supported_features == 0

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_one_coordinator_publication_updates_state_once(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    entry = await _setup_entry(hass, _entry())
    entity_id = _entity_id(hass, ZONE_IDS[0])
    events: list[Event[EventStateChangedData]] = []
    cancel = async_track_state_change_event(
        hass,
        [entity_id],
        events.append,
    )

    update_time = entry.runtime_data.data.calculated_at + timedelta(minutes=1)
    hass.states.async_set(
        SENSORS[0],
        "20.5",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
        timestamp=update_time.timestamp(),
    )
    async_fire_time_changed(hass, update_time + timedelta(seconds=1))
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes[ATTR_CURRENT_TEMPERATURE] == 20.5
    assert len(events) == 1
    cancel()
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_physical_device_is_not_claimed_and_no_source_device_is_created(
    hass: HomeAssistant,
) -> None:
    foreign = MockConfigEntry(
        domain="test",
        entry_id="physical-entry",
        data={},
    )
    foreign.add_to_hass(hass)
    device_registry = dr.async_get(hass)
    physical = device_registry.async_get_or_create(
        config_entry_id=foreign.entry_id,
        identifiers={("test", "physical-thermostat")},
        name="Physical thermostat",
    )
    original_identifiers = physical.identifiers
    _set_states(hass)
    entry = await _setup_entry(hass, _entry())

    physical_after = device_registry.async_get(physical.id)
    assert physical_after is not None
    assert physical_after.identifiers == original_identifiers
    assert physical_after.config_entries == {foreign.entry_id}
    assert device_registry.async_get_device(identifiers={(DOMAIN, SENSORS[0])}) is None

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_reload_recreates_entity_object_with_same_registry_identity(
    hass: HomeAssistant,
) -> None:
    from homeassistant.components.climate import DATA_COMPONENT

    _set_states(hass)
    entry = await _setup_entry(hass, _entry())
    entity_id = _entity_id(hass, ZONE_IDS[0])
    first_coordinator = entry.runtime_data
    first_entity = hass.data[DATA_COMPONENT].get_entity(entity_id)
    assert isinstance(first_entity, IntelligentClimateZoneClimateEntity)

    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    second_coordinator = entry.runtime_data
    second_entity = hass.data[DATA_COMPONENT].get_entity(entity_id)

    assert first_coordinator is not second_coordinator
    assert first_coordinator._shutdown is True
    assert isinstance(second_entity, IntelligentClimateZoneClimateEntity)
    assert first_entity is not second_entity
    assert _entity_id(hass, ZONE_IDS[0]) == entity_id

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.data[DATA_COMPONENT].get_entity(entity_id) is None
    assert second_coordinator._shutdown is True


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_zone_rename_updates_device_name_without_unique_id_change(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    entry = await _setup_entry(hass, _entry())
    entity_id = _entity_id(hass, ZONE_IDS[0])
    subentry = entry.subentries["zone-subentry-1"]
    renamed = _zone_data(0, name="Dining and Kitchen")
    hass.states.async_set(
        "sensor.renamed_source",
        "20.4",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    renamed["temperature_sources"] = [
        _temperature_source(0, entity_id="sensor.renamed_source")
    ]
    assert hass.config_entries.async_update_subentry(
        entry,
        subentry,
        data=renamed,
        title="Dining and Kitchen",
    )
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert _entity_id(hass, ZONE_IDS[0]) == entity_id
    zone_device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, ZONE_IDS[0])}
    )
    assert zone_device is not None
    assert zone_device.name == "Dining and Kitchen"
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_observed_mode_service_reaches_translated_rejecting_setter(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    entry = await _setup_entry(hass, _entry())
    entity_id = _entity_id(hass, ZONE_IDS[0])
    physical_before = hass.states.get(THERMOSTAT)

    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {"entity_id": entity_id, "hvac_mode": HVACMode.HEAT},
            blocking=True,
        )

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "observation_only"
    assert hass.states.get(THERMOSTAT) == physical_before

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {"entity_id": entity_id, ATTR_TEMPERATURE: 25.0},
            blocking=True,
        )
    for service in (SERVICE_TURN_ON, SERVICE_TURN_OFF):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                CLIMATE_DOMAIN,
                service,
                {"entity_id": entity_id},
                blocking=True,
            )
    assert hass.states.get(THERMOSTAT) == physical_before
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_platform_setup_has_runtime_and_coordinator_started_first(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    entry = _entry()
    entry.add_to_hass(hass)
    observed: list[tuple[bool, bool]] = []
    original = hass.config_entries.async_forward_entry_setups

    async def _forward(
        forwarded_entry: ConfigEntry,
        platforms: tuple[Platform, ...],
    ) -> None:
        observed.append(
            (
                hasattr(forwarded_entry, "runtime_data"),
                forwarded_entry.runtime_data.data.revision == 1,
            )
        )
        assert platforms == (Platform.CLIMATE,)
        await original(forwarded_entry, platforms)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        side_effect=_forward,
    ) as forward:
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert observed == [(True, True)]
    forward.assert_called_once()
    assert await hass.config_entries.async_unload(entry.entry_id)
