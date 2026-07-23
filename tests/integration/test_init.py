"""Test persisted Task 5 setup validation with Home Assistant."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant", reason="CI installs Home Assistant 2026.7.")
pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="CI installs the Home Assistant custom-component test harness.",
)

from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigSubentryDataWithId
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate import async_setup_entry, async_unload_entry
from custom_components.intelligent_climate.const import (
    DOMAIN,
    PLATFORMS,
    SUBENTRY_TYPE_ZONE,
)
from custom_components.intelligent_climate.coordinator import (
    IntelligentClimateCoordinator,
)
from custom_components.intelligent_climate.models import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
)

GROUP_ID = "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
ZONE_ID = "99246285-6f02-4e8a-94ed-bdfd4a5e62c4"
SOURCE_ID = "f15f73b1-ea59-4b28-819f-7b99acf065bf"
THERMOSTAT = "climate.main_floor"
SENSOR = "sensor.room_temperature"


def _parent_data(thermostat: str | None = THERMOSTAT) -> dict[str, object]:
    return {
        "equipment_group": {
            "equipment_group_id": GROUP_ID,
            "name": "Main Floor HVAC",
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


def _source(
    entity_id: str = SENSOR,
    *,
    attribute: str | None = None,
    source_id: str = SOURCE_ID,
) -> dict[str, object]:
    return {
        "source_id": source_id,
        "entity_id": entity_id,
        "attribute": attribute,
        "offset_c": 0.0,
        "weight": 1.0,
        "priority": 0,
        "enabled": True,
    }


def _zone_data(
    *,
    thermostats: list[str] | None = None,
    sources: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "data_version": 1,
        "zone_id": ZONE_ID,
        "name": "Dining Room",
        "thermostat_entity_ids": [THERMOSTAT] if thermostats is None else thermostats,
        "temperature_sources": [_source()] if sources is None else sources,
        "humidity_sources": [],
        "window_door_entity_ids": [],
        "occupancy_entity_ids": [],
        "stage_entity_ids": [],
        "fan_entity_ids": [],
    }


def _subentry(data: dict[str, object]) -> ConfigSubentryDataWithId:
    return config_entries.ConfigSubentryDataWithId(
        data=data,
        subentry_id="zone-subentry-1",
        subentry_type=SUBENTRY_TYPE_ZONE,
        title=str(data["name"]),
        unique_id=str(data["zone_id"]),
    )


def _entry(
    *,
    data: dict[str, object] | None = None,
    zone_data: dict[str, object] | None = None,
    entry_id: str = "entry-1",
) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=entry_id,
        data=_parent_data() if data is None else data,
        subentries_data=[] if zone_data is None else [_subentry(zone_data)],
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
        state=config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    )


def _set_valid_states(hass: HomeAssistant) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    hass.states.async_set(
        SENSOR,
        "20",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    )


async def _assert_invalid(hass: HomeAssistant, entry: ConfigEntry) -> None:
    with pytest.raises(
        ConfigEntryError,
        match="Invalid Intelligent Climate configuration",
    ):
        await async_setup_entry(hass, entry)
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_valid_selected_parent_and_zone_graph(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    entry = _entry(zone_data=_zone_data())

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ) as forward:
        assert await async_setup_entry(hass, entry)
    forward.assert_awaited_once_with(entry, PLATFORMS)
    assert entry.runtime_data.data.entry_id == entry.entry_id
    assert DOMAIN not in hass.data
    assert await async_unload_entry(hass, entry)
    assert DOMAIN not in hass.data


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_missing_parent_thermostat_state_fails_closed(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(
        SENSOR,
        "20",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    )
    await _assert_invalid(hass, _entry(zone_data=_zone_data()))


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_wrong_parent_thermostat_domain_fails_closed(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    hass.states.async_set("sensor.thermostat", "20")
    data = _parent_data("sensor.thermostat")
    zone = _zone_data(thermostats=["sensor.thermostat"])
    await _assert_invalid(hass, _entry(data=data, zone_data=zone))


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_duplicate_parent_thermostat_ownership_fails_closed(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    existing = _entry(entry_id="entry-existing")
    existing.add_to_hass(hass)

    await _assert_invalid(
        hass,
        _entry(entry_id="entry-current", zone_data=_zone_data()),
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_missing_zone_source_fails_closed(hass: HomeAssistant) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    await _assert_invalid(hass, _entry(zone_data=_zone_data()))


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_wrong_zone_source_domain_fails_closed(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    hass.states.async_set("binary_sensor.window", "off")
    await _assert_invalid(
        hass,
        _entry(
            zone_data=_zone_data(
                sources=[_source("binary_sensor.window")],
            )
        ),
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_wrong_sensor_device_class_fails_closed(hass: HomeAssistant) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    hass.states.async_set(SENSOR, "50", {ATTR_DEVICE_CLASS: "humidity"})
    await _assert_invalid(hass, _entry(zone_data=_zone_data()))


@pytest.mark.parametrize(
    "source",
    [
        _source("climate.room", attribute=None),
        _source(SENSOR, attribute="current_temperature"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_domain_attribute_pair_fails_closed(
    hass: HomeAssistant,
    source: dict[str, object],
) -> None:
    _set_valid_states(hass)
    hass.states.async_set("climate.room", "heat")
    await _assert_invalid(
        hass,
        _entry(zone_data=_zone_data(sources=[source])),
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_duplicate_source_binding_fails_closed(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    duplicate = _source(source_id="ce30dafc-fadd-4cc4-b261-8a896d5a6d12")
    await _assert_invalid(
        hass,
        _entry(zone_data=_zone_data(sources=[_source(), duplicate])),
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unavailable_configured_entities_are_accepted(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(THERMOSTAT, "unavailable")
    hass.states.async_set(
        SENSOR,
        "unavailable",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    )
    entry = _entry(zone_data=_zone_data())

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_complete_task_4_skeleton_is_accepted(hass: HomeAssistant) -> None:
    skeleton_zone = _zone_data(thermostats=[], sources=[])
    entry = _entry(data=_parent_data(None), zone_data=skeleton_zone)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)
    assert await async_unload_entry(hass, entry)


@pytest.mark.parametrize(
    ("parent", "zone"),
    [
        (_parent_data(None), _zone_data()),
        (_parent_data(), _zone_data(thermostats=[], sources=[])),
        (
            _parent_data(None),
            {
                **_zone_data(thermostats=[], sources=[]),
                "window_door_entity_ids": ["binary_sensor.window"],
            },
        ),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_partially_bound_legacy_documents_fail_closed(
    hass: HomeAssistant,
    parent: dict[str, object],
    zone: dict[str, object],
) -> None:
    _set_valid_states(hass)
    await _assert_invalid(hass, _entry(data=parent, zone_data=zone))


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_malformed_data_leaves_no_runtime_residue(hass: HomeAssistant) -> None:
    _set_valid_states(hass)
    malformed = deepcopy(_parent_data())
    malformed["equipment_group"]["future_field"] = True  # type: ignore[index]

    await _assert_invalid(hass, _entry(data=malformed, zone_data=_zone_data()))
    assert DOMAIN not in hass.data


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unload_without_runtime_is_idempotent(hass: HomeAssistant) -> None:
    entry = _entry(data=_parent_data(None))
    assert await async_unload_entry(hass, entry)
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_subentry_type_identity_and_title_fail_closed(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    valid = _subentry(_zone_data())
    cases = [
        config_entries.ConfigSubentryDataWithId(
            **{**valid, "subentry_type": "future_type"}
        ),
        config_entries.ConfigSubentryDataWithId(
            **{**valid, "unique_id": "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"}
        ),
        config_entries.ConfigSubentryDataWithId(**{**valid, "title": "Wrong title"}),
    ]
    for index, subentry in enumerate(cases):
        entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id=f"entry-invalid-{index}",
            data=_parent_data(),
            subentries_data=[subentry],
            version=CONFIG_ENTRY_MAJOR_VERSION,
            minor_version=CONFIG_ENTRY_MINOR_VERSION,
        )
        await _assert_invalid(hass, entry)


@pytest.mark.parametrize("duplicate_kind", ["zone_id", "name"])
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_duplicate_zone_identity_or_name_fails_closed(
    hass: HomeAssistant,
    duplicate_kind: str,
) -> None:
    _set_valid_states(hass)
    second = _zone_data()
    if duplicate_kind == "zone_id":
        second["name"] = "Living Room"
    else:
        second["zone_id"] = "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"
        second["name"] = "DINING ROOM"
    second_subentry = config_entries.ConfigSubentryDataWithId(
        data=second,
        subentry_id="zone-subentry-2",
        subentry_type=SUBENTRY_TYPE_ZONE,
        title=str(second["name"]),
        unique_id=str(second["zone_id"]),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_parent_data(),
        subentries_data=[_subentry(_zone_data()), second_subentry],
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )

    await _assert_invalid(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_duplicate_source_id_across_zone_source_types_fails_closed(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    hass.states.async_set(
        "sensor.second",
        "21",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    )
    second = _zone_data(
        sources=[
            _source(
                "sensor.second",
                source_id="ce30dafc-fadd-4cc4-b261-8a896d5a6d12",
            )
        ]
    )
    second["zone_id"] = "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"
    second["name"] = "Living Room"
    second["humidity_sources"] = [
        {
            "source_id": SOURCE_ID,
            "entity_id": "sensor.humidity",
            "attribute": None,
            "offset_pct": 0.0,
            "weight": 1.0,
            "priority": 0,
            "enabled": True,
        }
    ]
    second_subentry = config_entries.ConfigSubentryDataWithId(
        data=second,
        subentry_id="zone-subentry-2",
        subentry_type=SUBENTRY_TYPE_ZONE,
        title="Living Room",
        unique_id=str(second["zone_id"]),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=_parent_data(),
        subentries_data=[_subentry(_zone_data()), second_subentry],
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )

    await _assert_invalid(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unload_one_of_two_runtime_entries_preserves_other(
    hass: HomeAssistant,
) -> None:
    first = _entry(data=_parent_data(None), entry_id="entry-1")
    second = _entry(data=_parent_data(None), entry_id="entry-2")
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, first)
        assert await async_setup_entry(hass, second)
    first_coordinator = first.runtime_data
    second_coordinator = second.runtime_data
    assert first_coordinator is not second_coordinator

    assert await async_unload_entry(hass, first)
    assert first_coordinator._shutdown is True
    assert DOMAIN not in hass.data
    assert await async_unload_entry(hass, second)
    assert second_coordinator._shutdown is True
    assert DOMAIN not in hass.data


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_platform_forward_failure_shuts_down_new_coordinator_and_chains(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_valid_states(hass)
    entry = _entry(zone_data=_zone_data())
    failure = RuntimeError("platform import failed")
    coordinator: IntelligentClimateCoordinator | None = None
    original_start = IntelligentClimateCoordinator.async_start

    async def capture_coordinator(
        instance: IntelligentClimateCoordinator,
    ) -> None:
        nonlocal coordinator
        coordinator = instance
        await original_start(instance)

    monkeypatch.setattr(
        IntelligentClimateCoordinator,
        "async_start",
        capture_coordinator,
    )

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
            side_effect=failure,
        ),
        pytest.raises(
            ConfigEntryError,
            match="Unable to set up the Intelligent Climate climate platform",
        ) as raised,
    ):
        await async_setup_entry(hass, entry)

    assert raised.value.__cause__ is failure
    assert not hasattr(entry, "runtime_data")
    assert coordinator is not None
    assert coordinator._shutdown is True
    assert coordinator._cancel_subscription is None
    assert coordinator._cancel_debounce is None
    assert coordinator._cancel_reconciliation is None
    assert coordinator._cancel_watchdog is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_failed_platform_unload_keeps_live_coordinator(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    entry = _entry(zone_data=_zone_data())
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)
    coordinator = entry.runtime_data

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ) as unload:
        assert await async_unload_entry(hass, entry) is False

    unload.assert_awaited_once_with(entry, PLATFORMS)
    assert coordinator._shutdown is False
    assert entry.runtime_data is coordinator

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        assert await async_unload_entry(hass, entry)
    assert coordinator._shutdown is True
