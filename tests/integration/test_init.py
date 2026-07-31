"""Test persisted Task 5 setup validation with Home Assistant."""

from __future__ import annotations

import logging
from copy import deepcopy
from unittest.mock import AsyncMock, Mock, patch

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
from homeassistant.helpers import issue_registry as ir
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate import (
    _decode_runtime_configuration,
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
)
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
    PHASE2_CONFIG_MAJOR_VERSION,
    PHASE2_CONFIG_MINOR_VERSION,
    ControlState,
    EquipmentRelationship,
    OperatingMode,
    RuntimeConfigurationState,
    SourceQuality,
    decode_equipment_group_document,
    decode_phase2_equipment_group_document,
    decode_phase2_options,
    decode_phase2_zone_config,
)
from custom_components.intelligent_climate.repairs import IssueCode, issue_id

GROUP_ID = "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
ZONE_ID = "99246285-6f02-4e8a-94ed-bdfd4a5e62c4"
SOURCE_ID = "f15f73b1-ea59-4b28-819f-7b99acf065bf"
THERMOSTAT = "climate.main_floor"
SECOND_THERMOSTAT = "climate.upstairs"
SENSOR = "sensor.room_temperature"
SECOND_SENSOR = "sensor.upstairs_temperature"
SECOND_ZONE_ID = "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"
SECOND_SOURCE_ID = "ce30dafc-fadd-4cc4-b261-8a896d5a6d12"


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
    minor_version: int = CONFIG_ENTRY_MINOR_VERSION,
) -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=entry_id,
        data=_parent_data() if data is None else data,
        subentries_data=[] if zone_data is None else [_subentry(zone_data)],
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=minor_version,
        state=config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    )


def _set_valid_states(hass: HomeAssistant) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    hass.states.async_set(
        SENSOR,
        "20",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    )


def _shared_entry() -> MockConfigEntry:
    second_zone = _zone_data(
        thermostats=[SECOND_THERMOSTAT],
        sources=[_source(SECOND_SENSOR, source_id=SECOND_SOURCE_ID)],
    )
    second_zone["zone_id"] = SECOND_ZONE_ID
    second_zone["name"] = "Upstairs"
    parent = _parent_data()
    parent_group = parent["equipment_group"]
    assert isinstance(parent_group, dict)
    parent_group.update(
        {
            "relationship": EquipmentRelationship.SHARED_ZONED.value,
            "thermostats": [
                {"entity_id": THERMOSTAT, "role": "primary"},
                {"entity_id": SECOND_THERMOSTAT, "role": "secondary"},
            ],
            "shared_policy": {
                "zone_priority_order": [ZONE_ID, SECOND_ZONE_ID],
                "conflict_policy": "priority_order",
            },
        }
    )
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="shared-entry",
        data=parent,
        subentries_data=[
            _subentry(_zone_data()),
            config_entries.ConfigSubentryDataWithId(
                data=second_zone,
                subentry_id="zone-subentry-2",
                subentry_type=SUBENTRY_TYPE_ZONE,
                title="Upstairs",
                unique_id=SECOND_ZONE_ID,
            ),
        ],
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
        state=config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    )


async def _assert_invalid(hass: HomeAssistant, entry: ConfigEntry) -> None:
    with pytest.raises(
        ConfigEntryError,
        match="Invalid Intelligent Climate configuration",
    ):
        await async_setup_entry(hass, entry)
    assert entry.entry_id not in hass.data.get(DOMAIN, {})


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_config_entry_1_0_migration_is_atomic_and_canonical(
    hass: HomeAssistant,
) -> None:
    """A fully valid 1.0 hierarchy becomes safe canonical Phase 2."""
    _set_valid_states(hass)
    entry = _entry(zone_data=_zone_data(), minor_version=0)
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry)

    assert entry.version == PHASE2_CONFIG_MAJOR_VERSION
    assert entry.minor_version == PHASE2_CONFIG_MINOR_VERSION
    parent = decode_phase2_equipment_group_document(entry.data)
    options = decode_phase2_options(entry.options)
    zone = decode_phase2_zone_config(entry.subentries["zone-subentry-1"].data)
    assert str(parent.equipment_group.equipment_group_id) == GROUP_ID
    assert parent.automation_enabled is False
    assert parent.desired_operating_mode is OperatingMode.OBSERVE_ONLY
    assert options.observation.history_max_records == 500
    assert options.observation.history_max_age_days == 30
    assert str(zone.zone.zone_id) == ZONE_ID
    assert zone.contact_bindings == ()
    assert zone.occupancy_bindings == ()
    assert zone.fan_bindings == ()
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN,
            issue_id(entry.entry_id, IssueCode.MIGRATION_FAILED),
        )
        is None
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_failed_config_entry_migration_leaves_full_graph_unchanged(
    hass: HomeAssistant,
) -> None:
    """Invalid parent or zone data fails closed before any persisted update."""
    _set_valid_states(hass)
    invalid_parent = deepcopy(_parent_data())
    invalid_parent["equipment_group"]["future_field"] = True  # type: ignore[index]
    entry = _entry(
        data=invalid_parent,
        zone_data=_zone_data(),
        minor_version=0,
    )
    entry.add_to_hass(hass)
    before_data = deepcopy(dict(entry.data))
    before_options = deepcopy(dict(entry.options))
    before_zones = {
        key: deepcopy(dict(value.data)) for key, value in entry.subentries.items()
    }

    with patch.object(
        hass.config_entries,
        "async_update_entry",
        wraps=hass.config_entries.async_update_entry,
    ) as update:
        assert not await async_migrate_entry(hass, entry)

    update.assert_not_called()
    assert entry.minor_version == 0
    assert dict(entry.data) == before_data
    assert dict(entry.options) == before_options
    assert {
        key: dict(value.data) for key, value in entry.subentries.items()
    } == before_zones
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN,
            issue_id(entry.entry_id, IssueCode.MIGRATION_FAILED),
        )
        is not None
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_current_and_future_config_entry_migration_boundaries(
    hass: HomeAssistant,
) -> None:
    """Current entries are no-ops and future entries fail closed."""
    _set_valid_states(hass)
    current = _entry(entry_id="entry-current", zone_data=_zone_data())
    current.add_to_hass(hass)
    assert await async_migrate_entry(hass, current)
    current_data = deepcopy(dict(current.data))
    current_options = deepcopy(dict(current.options))
    assert await async_migrate_entry(hass, current)
    assert (current.version, current.minor_version) == (
        PHASE2_CONFIG_MAJOR_VERSION,
        PHASE2_CONFIG_MINOR_VERSION,
    )
    assert dict(current.data) == current_data
    assert dict(current.options) == current_options

    future = _entry(
        entry_id="entry-future",
        minor_version=CONFIG_ENTRY_MINOR_VERSION + 1,
    )
    future.add_to_hass(hass)
    assert not await async_migrate_entry(hass, future)
    assert future.minor_version == CONFIG_ENTRY_MINOR_VERSION + 1
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN,
            issue_id(future.entry_id, IssueCode.MIGRATION_FAILED),
        )
        is not None
    )


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
    assert hass.data[DOMAIN]["frontend_loaded_entries"] == {entry.entry_id: entry.title}
    assert await async_unload_entry(hass, entry)
    assert hass.data[DOMAIN]["frontend_loaded_entries"] == {}


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_shared_multi_zone_graph_loads_and_indexes_every_thermostat(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    hass.states.async_set(SECOND_THERMOSTAT, "cool")
    hass.states.async_set(
        SECOND_SENSOR,
        "22",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    )
    entry = _shared_entry()

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)

    configuration = entry.runtime_data.configuration
    assert configuration.state is RuntimeConfigurationState.CONFIGURED
    assert configuration.equipment_group.relationship is (
        EquipmentRelationship.SHARED_ZONED
    )
    assert len(configuration.equipment_group.thermostats) == 2
    assert len(configuration.zones) == 2
    assert set(entry.runtime_data.thermostat_dependency_index) == {
        THERMOSTAT,
        SECOND_THERMOSTAT,
    }
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_native_zone_removal_normalizes_parent_graph_before_reload(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    hass.states.async_set(SECOND_THERMOSTAT, "cool")
    entry = _shared_entry()
    entry.add_to_hass(hass)
    assert hass.config_entries.async_remove_subentry(entry, "zone-subentry-2")

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)

    group = decode_equipment_group_document(entry.data).equipment_group
    assert group.relationship is EquipmentRelationship.SINGLE_SYSTEM
    assert [item.entity_id for item in group.thermostats] == [THERMOSTAT]
    assert group.shared_policy is None
    assert len(entry.runtime_data.configuration.zones) == 1
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_valid_parent_without_zone_awaits_first_zone(
    hass: HomeAssistant,
) -> None:
    """A zone-less parent stays inert and raises the actionable required Repair."""
    _set_valid_states(hass)
    entry = _entry()

    configuration = _decode_runtime_configuration(hass, entry)

    assert configuration.state is RuntimeConfigurationState.AWAITING_FIRST_ZONE
    assert configuration.awaiting_first_zone is True
    assert configuration.transitional_empty_skeleton is False
    assert configuration.zones == ()

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN,
        issue_id(entry.entry_id, IssueCode.NO_ZONES_CONFIGURED),
    )
    assert issue is not None
    assert issue.data == {"issue_code": "no_zones_configured"}
    assert entry.runtime_data.configuration.state is (
        RuntimeConfigurationState.AWAITING_FIRST_ZONE
    )
    assert await async_unload_entry(hass, entry)

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)

    coordinator = entry.runtime_data
    assert coordinator.data.control_state is ControlState.INITIALIZING
    assert coordinator.data.reconciling is False
    assert coordinator.data.zones == ()
    assert coordinator._cancel_state_change_subscription is None
    assert coordinator._cancel_state_report_subscription is None
    assert coordinator._cancel_reconciliation is None
    assert coordinator._cancel_watchdog is None
    assert await async_unload_entry(hass, entry)


@pytest.mark.parametrize(
    "data",
    [
        {
            "equipment_group": {
                **_parent_data()["equipment_group"],  # type: ignore[dict-item]
                "relationship": "independent",
            }
        },
        {
            "equipment_group": {
                **_parent_data()["equipment_group"],  # type: ignore[dict-item]
                "thermostats": [
                    {"entity_id": THERMOSTAT, "role": "secondary"},
                ],
            }
        },
        {
            "equipment_group": {
                **_parent_data()["equipment_group"],  # type: ignore[dict-item]
                "shared_policy": {
                    "stage_entity_ids": [],
                    "fan_entity_ids": [],
                },
            }
        },
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_malformed_parent_without_zones_fails_closed(
    hass: HomeAssistant,
    data: dict[str, object],
) -> None:
    _set_valid_states(hass)
    await _assert_invalid(hass, _entry(data=data))


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_missing_parent_thermostat_state_starts_unavailable(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(
        SENSOR,
        "20",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    )
    entry = _entry(zone_data=_zone_data())

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ) as forward:
        assert await async_setup_entry(hass, entry)

    forward.assert_awaited_once_with(entry, PLATFORMS)
    thermostat = entry.runtime_data.data.thermostats[0].state
    assert thermostat.entity_id == THERMOSTAT
    assert thermostat.available is False
    assert await async_unload_entry(hass, entry)


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
async def test_missing_sensor_source_starts_unavailable(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    entry = _entry(zone_data=_zone_data())

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)

    zone = entry.runtime_data.data.zones[0]
    assert zone.temperature_observations[0].quality is SourceQuality.UNAVAILABLE
    assert zone.effective_temperature_c is None
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_missing_climate_source_starts_unavailable(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    climate_source = _source(
        "climate.dining_room",
        attribute="current_temperature",
    )
    entry = _entry(zone_data=_zone_data(sources=[climate_source]))

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)

    observation = entry.runtime_data.data.zones[0].temperature_observations[0]
    assert observation.quality is SourceQuality.UNAVAILABLE
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_missing_parent_and_source_start_with_both_subscriptions(
    hass: HomeAssistant,
) -> None:
    entry = _entry(zone_data=_zone_data())

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ) as forward:
        assert await async_setup_entry(hass, entry)

    coordinator = entry.runtime_data
    forward.assert_awaited_once_with(entry, PLATFORMS)
    assert coordinator.data.thermostats[0].state.available is False
    assert (
        coordinator.data.zones[0].temperature_observations[0].quality
        is SourceQuality.UNAVAILABLE
    )
    assert set(coordinator.source_dependency_index) == {SENSOR}
    assert set(coordinator.thermostat_dependency_index) == {THERMOSTAT}
    assert coordinator._cancel_state_change_subscription is not None
    assert coordinator._cancel_state_report_subscription is not None
    assert await async_unload_entry(hass, entry)


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
async def test_persisted_sensor_does_not_require_live_device_class(
    hass: HomeAssistant,
) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    hass.states.async_set(SENSOR, "50", {ATTR_DEVICE_CLASS: "humidity"})
    entry = _entry(zone_data=_zone_data())

    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)
    assert await async_unload_entry(hass, entry)


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


@pytest.mark.parametrize(
    ("parent_entity_id", "source_entity_id"),
    [
        ("climate.invalid entity", SENSOR),
        (THERMOSTAT, "sensor.invalid entity"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_persisted_entity_ids_fail_closed(
    hass: HomeAssistant,
    parent_entity_id: str,
    source_entity_id: str,
) -> None:
    data = _parent_data(parent_entity_id)
    zone = _zone_data(
        thermostats=[parent_entity_id],
        sources=[_source(source_entity_id)],
    )
    await _assert_invalid(hass, _entry(data=data, zone_data=zone))


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_persisted_zone_requires_temperature_source(
    hass: HomeAssistant,
) -> None:
    zone = _zone_data(sources=[])
    await _assert_invalid(hass, _entry(zone_data=zone))


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
async def test_malformed_data_leaves_no_runtime_residue(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="custom_components.intelligent_climate",
    )
    _set_valid_states(hass)
    malformed = deepcopy(_parent_data())
    malformed["equipment_group"]["future_field"] = True  # type: ignore[index]

    await _assert_invalid(hass, _entry(data=malformed, zone_data=_zone_data()))
    assert DOMAIN not in hass.data
    assert any(
        "Invalid persisted Intelligent Climate schema:" in record.getMessage()
        and "future_field" in record.getMessage()
        for record in caplog.records
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_persisted_entity_validation_error_logs_code_before_generic_error(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.ERROR,
        logger="custom_components.intelligent_climate",
    )
    data = _parent_data("sensor.not_a_thermostat")
    zone = _zone_data(thermostats=["sensor.not_a_thermostat"])

    await _assert_invalid(hass, _entry(data=data, zone_data=zone))

    messages = [record.getMessage() for record in caplog.records]
    assert any(
        "config_entry_id=entry-1" in message
        and "validation_code=wrong_domain" in message
        and "structural_context=config_entry_hierarchy" in message
        for message in messages
    )


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
    assert hass.data[DOMAIN]["frontend_loaded_entries"] == {
        second.entry_id: second.title
    }
    assert await async_unload_entry(hass, second)
    assert second_coordinator._shutdown is True
    assert hass.data[DOMAIN]["frontend_loaded_entries"] == {}


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
            match="Unable to set up the Intelligent Climate entity platforms",
        ) as raised,
    ):
        await async_setup_entry(hass, entry)

    assert raised.value.__cause__ is failure
    assert not hasattr(entry, "runtime_data")
    assert coordinator is not None
    assert coordinator._shutdown is True
    assert coordinator._cancel_state_change_subscription is None
    assert coordinator._cancel_state_report_subscription is None
    assert coordinator._cancel_debounce is None
    assert coordinator._cancel_reconciliation is None
    assert coordinator._cancel_watchdog is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_failed_platform_unload_keeps_live_coordinator(
    hass: HomeAssistant,
) -> None:
    _set_valid_states(hass)
    entry = _entry(zone_data=_zone_data())
    unregister_shutdown = Mock()
    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
        patch.object(
            HomeAssistant,
            "async_add_shutdown_job",
            autospec=True,
            return_value=unregister_shutdown,
        ) as add_shutdown_job,
    ):
        assert await async_setup_entry(hass, entry)
    add_shutdown_job.assert_called_once()
    assert add_shutdown_job.call_args.args[0] is hass
    assert (
        add_shutdown_job.call_args.args[1].target
        == entry.runtime_data._async_core_shutdown
    )
    entry.runtime_data.async_add_core_shutdown_job()
    add_shutdown_job.assert_called_once()
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
    unregister_shutdown.assert_not_called()

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        assert await async_unload_entry(hass, entry)
    unregister_shutdown.assert_called_once_with()
    coordinator.async_unregister_core_shutdown_job()
    unregister_shutdown.assert_called_once_with()
    assert coordinator._shutdown is True


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_home_assistant_core_stop_persists_clean_shutdown_marker(
    hass: HomeAssistant,
) -> None:
    """A real core stop awaits the entry-scoped verified final Store save."""
    _set_valid_states(hass)
    entry = _entry(zone_data=_zone_data())
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ):
        assert await async_setup_entry(hass, entry)
    runtime_store = entry.runtime_data.runtime_store
    assert runtime_store is not None

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        new_callable=AsyncMock,
    ) as service_call:
        await hass.async_stop(force=True)

    stored = runtime_store._store._data
    assert stored is not None
    assert stored["version"] == 1
    assert stored["minor_version"] == 2
    assert stored["data"]["last_clean_shutdown"] is True
    assert runtime_store.last_successful_save is not None
    assert runtime_store.dirty is False
    assert runtime_store.write_task is None
    assert entry.runtime_data._shutdown is True
    assert entry.runtime_data._cancel_reconciliation is None
    assert entry.runtime_data._cancel_watchdog is None
    await entry.runtime_data._async_core_shutdown()
    service_call.assert_not_awaited()
