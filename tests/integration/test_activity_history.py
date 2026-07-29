"""Test genuine Home Assistant activity, entity, bus, and persistence wiring."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODES,
)
from homeassistant.components.climate import DATA_COMPONENT as CLIMATE_COMPONENT
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.event import DATA_COMPONENT as EVENT_COMPONENT
from homeassistant.components.sensor import DATA_COMPONENT as SENSOR_COMPONENT
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigSubentryDataWithId
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate import async_unload_entry
from custom_components.intelligent_climate.const import (
    DOMAIN,
    EVENT_ACTIVITY,
    SUBENTRY_TYPE_ZONE,
)
from custom_components.intelligent_climate.control import ObservationIntent
from custom_components.intelligent_climate.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.intelligent_climate.event import (
    _zone_subentries_by_id as event_zone_subentries,
)
from custom_components.intelligent_climate.event import (
    async_setup_entry as async_setup_event_entry,
)
from custom_components.intelligent_climate.models import (
    DEFAULT_OPTIONS,
    ActivityReason,
    ActivityType,
    ControlState,
    EquipmentGroupId,
    ObservationSourceId,
    RuntimeStoreDocument,
    RuntimeZoneState,
    SourceBaseline,
    SourceQuality,
    ZoneId,
    encode_options,
    encode_runtime_store_document,
)
from custom_components.intelligent_climate.repairs import (
    IssueCode,
    MigrationFailureCategory,
    RepairsManager,
    issue_id,
)
from custom_components.intelligent_climate.sensor import (
    _zone_subentries_by_id as sensor_zone_subentries,
)
from custom_components.intelligent_climate.sensor import (
    async_setup_entry as async_setup_sensor_entry,
)
from custom_components.intelligent_climate.storage import StoreLoadStatus

GROUP_ID = "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
ZONE_ID = "99246285-6f02-4e8a-94ed-bdfd4a5e62c4"
SOURCE_ID = "f15f73b1-ea59-4b28-819f-7b99acf065bf"
THERMOSTAT = "climate.physical_activity"
SENSOR = "sensor.activity_temperature"
ENTRY_ID = "activity-entry-1"


def _entry(
    *,
    entry_id: str = ENTRY_ID,
    group_id: str = GROUP_ID,
    zone_id: str = ZONE_ID,
    thermostat: str = THERMOSTAT,
    sensor: str = SENSOR,
) -> MockConfigEntry:
    zone = {
        "data_version": 1,
        "zone_id": zone_id,
        "name": "Activity zone",
        "thermostat_entity_ids": [thermostat],
        "temperature_sources": [
            {
                "source_id": SOURCE_ID,
                "entity_id": sensor,
                "attribute": None,
                "offset_c": 0.0,
                "weight": 1.0,
                "priority": 0,
                "enabled": True,
            }
        ],
        "humidity_sources": [],
        "window_door_entity_ids": [],
        "occupancy_entity_ids": [],
        "stage_entity_ids": [],
        "fan_entity_ids": [],
    }
    subentry = ConfigSubentryDataWithId(
        data=zone,
        subentry_id=f"{entry_id}-zone-subentry",
        subentry_type=SUBENTRY_TYPE_ZONE,
        title="Activity zone",
        unique_id=zone_id,
    )
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=entry_id,
        title="Activity equipment",
        unique_id=group_id,
        data={
            "equipment_group": {
                "equipment_group_id": group_id,
                "name": "Activity equipment",
                "equipment_type": "conventional",
                "relationship": "single_system",
                "thermostats": [
                    {"entity_id": thermostat, "role": "primary"},
                ],
                "shared_policy": None,
            }
        },
        options=dict(
            encode_options(replace(DEFAULT_OPTIONS, startup_reconciliation_seconds=60))
        ),
        subentries_data=[subentry],
        version=1,
        minor_version=0,
    )


def _set_states(
    hass: HomeAssistant,
    *,
    thermostat: str = THERMOSTAT,
    sensor: str = SENSOR,
    mode: HVACMode = HVACMode.HEAT,
    target: float = 21.0,
    supported_features: ClimateEntityFeature = (
        ClimateEntityFeature.TARGET_TEMPERATURE
    ),
    sensor_state: str = "20.0",
) -> None:
    hass.states.async_set(
        thermostat,
        mode,
        {
            ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL],
            ATTR_SUPPORTED_FEATURES: int(supported_features),
            ATTR_CURRENT_TEMPERATURE: 20.0,
            ATTR_TEMPERATURE: target,
        },
    )
    hass.states.async_set(
        sensor,
        sensor_state,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> ConfigEntry:
    if hass.config_entries.async_get_entry(entry.entry_id) is None:
        entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    if coordinator.data.reconciling:
        await coordinator._async_reconciliation_complete(
            coordinator.data.calculated_at + timedelta(seconds=61),
            generation=coordinator._reconciliation_generation,
        )
        await hass.async_block_till_done()
    return cast(ConfigEntry, entry)


async def _flush(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.async_block_till_done()
    coordinator = entry.runtime_data
    await coordinator._async_debounce_elapsed(
        coordinator.data.calculated_at + timedelta(seconds=1),
        generation=coordinator._debounce_generation,
    )
    await hass.async_block_till_done()


def _store_document(
    *,
    entry_id: str = ENTRY_ID,
    persisted_temperature: float = 40.0,
    baseline_temperature: float = 10.0,
    clean_shutdown: bool = False,
) -> dict[str, Any]:
    """Return one valid Store-v1 payload with intentionally stale live values."""
    saved_at = utcnow()
    return dict(
        encode_runtime_store_document(
            RuntimeStoreDocument(
                entry_id=entry_id,
                equipment_group_id=EquipmentGroupId.parse(GROUP_ID),
                saved_at=saved_at,
                last_clean_shutdown=clean_shutdown,
                zones={
                    ZoneId.parse(ZONE_ID): RuntimeZoneState(
                        last_runtime_state=ControlState.OBSERVING,
                        last_live_observation_at=saved_at,
                        last_effective_temperature_c=persisted_temperature,
                        last_effective_humidity_pct=None,
                        last_decision_id=None,
                    )
                },
                source_baselines={
                    ObservationSourceId.parse(SOURCE_ID): SourceBaseline(
                        baseline_temperature,
                        saved_at,
                    )
                },
                decisions=(),
                command_journal=(),
            )
        )
    )


def _entity_id(hass: HomeAssistant, platform: Platform, unique_id: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(platform, DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_exact_inventory_devices_subentries_bus_and_startup_activity(
    hass: HomeAssistant,
) -> None:
    """The exact Task 14 surfaces and lifecycle activity use supported HA APIs."""
    _set_states(hass)
    bus_events: list[dict[str, object]] = []
    unsubscribe = hass.bus.async_listen(
        EVENT_ACTIVITY,
        lambda event: bus_events.append(dict(event.data)),
    )
    entry = await _setup(hass, _entry())

    registry_entries = er.async_entries_for_config_entry(
        er.async_get(hass),
        entry.entry_id,
    )
    group_unique_ids = {
        f"{GROUP_ID}:activity",
        f"{GROUP_ID}:configuration_degraded",
        f"{GROUP_ID}:equipment_relationship",
        f"{GROUP_ID}:thermostat_capability_status",
    }
    zone_unique_ids = {
        f"{ZONE_ID}:{key}"
        for key in {
            "activity",
            "effective_temperature",
            "latest_activity",
            "observation_enabled",
            "operating_mode",
            "reconciling",
            "sensor_data_degraded",
            "thermostat_data_degraded",
            "valid_temperature_sources",
            "zone",
        }
    }
    assert {item.unique_id for item in registry_entries} == (
        group_unique_ids | zone_unique_ids
    )
    assert {item.unique_id: item.config_subentry_id for item in registry_entries} == {
        **dict.fromkeys(group_unique_ids),
        **dict.fromkeys(zone_unique_ids, f"{ENTRY_ID}-zone-subentry"),
    }

    group_device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, GROUP_ID)})
    zone_device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, ZONE_ID)})
    assert group_device is not None
    assert zone_device is not None
    assert zone_device.via_device_id == group_device.id
    zone_entities = [
        item for item in registry_entries if item.unique_id.startswith(ZONE_ID)
    ]
    assert {item.device_id for item in zone_entities} == {zone_device.id}

    await hass.async_block_till_done()
    assert {payload["reason_code"] for payload in bus_events} >= {
        ActivityReason.SETUP_STARTED.value,
        ActivityReason.SETUP_COMPLETED.value,
        ActivityReason.RECONCILIATION_COMPLETED.value,
        ActivityReason.CONTROL_STATE_CHANGED.value,
    }
    assert all(
        set(payload)
        == {
            "entry_id",
            "equipment_group_id",
            "zone_id",
            "activity_type",
            "reason_code",
            "severity",
            "timestamp",
            "explanation",
        }
        for payload in bus_events
    )
    assert all(payload["entry_id"] == ENTRY_ID for payload in bus_events)

    group_event_id = _entity_id(
        hass,
        Platform.EVENT,
        f"{GROUP_ID}:activity",
    )
    group_event = hass.data[EVENT_COMPONENT].get_entity(group_event_id)
    assert group_event is not None
    assert group_event.entity_category is EntityCategory.DIAGNOSTIC
    assert group_event.should_poll is False
    assert group_event.event_types == [
        "lifecycle",
        "runtime_state_changed",
        "repair_issue_created",
        "repair_issue_resolved",
        "unsupported_control_attempt",
        "store_write_failed",
        "store_write_recovered",
    ]
    group_state = hass.states.get(group_event_id)
    assert group_state is not None
    assert group_state.attributes["event_type"] == "lifecycle"
    assert group_state.attributes["reason_code"] == "reconciliation_completed"
    assert group_state.attributes["equipment_group_id"] == GROUP_ID
    assert group_state.attributes["zone_id"] is None

    coordinator = entry.runtime_data
    runtime_store = coordinator.runtime_store
    assert runtime_store is not None
    unsubscribe()
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert coordinator.history.listener_count == 0
    assert runtime_store.write_task is None
    assert runtime_store._save_handle is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_activity_platforms_reject_invalid_zone_subentry_associations(
    hass: HomeAssistant,
) -> None:
    """Both new platforms fail closed on missing or malformed zone subentries."""
    non_zone = SimpleNamespace(subentry_type="other", unique_id=None)
    missing_id = SimpleNamespace(subentry_type=SUBENTRY_TYPE_ZONE, unique_id=None)
    for mapper in (event_zone_subentries, sensor_zone_subentries):
        assert mapper(cast(Any, SimpleNamespace(subentries={"other": non_zone}))) == {}
        with pytest.raises(ConfigEntryError, match="missing its stable ID"):
            mapper(cast(Any, SimpleNamespace(subentries={"zone": missing_id})))

    _set_states(hass)
    entry = await _setup(hass, _entry())
    missing_zone_entry = SimpleNamespace(
        runtime_data=entry.runtime_data,
        subentries={},
    )
    for setup_platform in (async_setup_event_entry, async_setup_sensor_entry):
        with pytest.raises(ConfigEntryError, match="exactly one config subentry"):
            await setup_platform(
                hass,
                cast(Any, missing_zone_entry),
                cast(Any, Mock()),
            )

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_source_transitions_event_latest_sensor_and_semantic_noops(
    hass: HomeAssistant,
) -> None:
    """Source materiality updates both entities; equivalent reports stay silent."""
    _set_states(hass)
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    zone_id = ZoneId.parse(ZONE_ID)

    hass.states.async_set(
        SENSOR,
        STATE_UNAVAILABLE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await _flush(hass, entry)
    assert coordinator.history.latest_for_zone(zone_id).reason_code is (
        ActivityReason.SOURCE_EXCLUDED
    )

    hass.states.async_set(
        SENSOR,
        STATE_UNKNOWN,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await _flush(hass, entry)
    assert coordinator.history.latest_for_zone(zone_id).reason_code is (
        ActivityReason.SOURCE_EXCLUSION_CHANGED
    )

    _set_states(hass, sensor_state="20.0")
    await _flush(hass, entry)
    latest = coordinator.history.latest_for_zone(zone_id)
    assert latest is not None
    assert latest.reason_code is ActivityReason.SOURCE_RECOVERED

    zone_event_id = _entity_id(hass, Platform.EVENT, f"{ZONE_ID}:activity")
    zone_event = hass.data[EVENT_COMPONENT].get_entity(zone_event_id)
    assert zone_event is not None
    assert zone_event.entity_category is EntityCategory.DIAGNOSTIC
    assert zone_event.should_poll is False
    assert zone_event.event_types == [
        "source_quality_changed",
        "thermostat_observation_changed",
        "thermostat_capabilities_changed",
        "unsupported_control_attempt",
    ]
    event_state = hass.states.get(zone_event_id)
    assert event_state is not None
    assert event_state.attributes["reason_code"] == "source_recovered"
    event_attributes = zone_event.state_attributes
    assert event_attributes is not None
    assert set(event_attributes) == {
        "event_type",
        "reason_code",
        "severity",
        "timestamp",
        "explanation",
        "record_id",
        "equipment_group_id",
        "zone_id",
    }

    latest_id = _entity_id(
        hass,
        Platform.SENSOR,
        f"{ZONE_ID}:latest_activity",
    )
    latest_sensor = hass.data[SENSOR_COMPONENT].get_entity(latest_id)
    assert latest_sensor is not None
    assert latest_sensor.entity_category is EntityCategory.DIAGNOSTIC
    assert latest_sensor.should_poll is False
    assert latest_sensor.native_value == latest.explanation
    latest_attributes = latest_sensor.extra_state_attributes
    assert latest_attributes is not None
    assert set(latest_attributes) == {
        "activity_type",
        "reason_code",
        "severity",
        "timestamp",
        "record_id",
    }

    await coordinator.runtime_store._async_attempt_save(last_clean_shutdown=False)
    assert coordinator.runtime_store.dirty is False
    history_count = len(coordinator.history.records)
    with patch.object(
        coordinator.runtime_store._store,
        "async_save",
        new_callable=AsyncMock,
    ) as save:
        _set_states(hass, sensor_state="20.0")
        await _flush(hass, entry)
        coordinator._publish_targeted(
            {zone_id},
            coordinator.data.calculated_at + timedelta(seconds=1),
        )
        await hass.async_block_till_done()

    assert len(coordinator.history.records) == history_count
    assert coordinator.runtime_store.dirty is False
    save.assert_not_awaited()
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_thermostat_mode_target_and_capability_semantics_ignore_time(
    hass: HomeAssistant,
) -> None:
    """Material public observations record once; discovered_at-only changes do not."""
    _set_states(hass)
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    before_ids = {record.record_id for record in coordinator.history.records}

    _set_states(
        hass,
        mode=HVACMode.COOL,
        target=22.0,
        supported_features=(
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
    )
    await _flush(hass, entry)

    new_records = [
        record
        for record in coordinator.history.records
        if record.record_id not in before_ids
    ]
    assert {record.reason_code for record in new_records} >= {
        ActivityReason.THERMOSTAT_MODE_CHANGED,
        ActivityReason.THERMOSTAT_TARGET_CHANGED,
        ActivityReason.THERMOSTAT_CAPABILITIES_CHANGED,
    }
    count = len(coordinator.history.records)

    _set_states(
        hass,
        mode=HVACMode.COOL,
        target=22.0,
        supported_features=(
            ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.FAN_MODE
        ),
    )
    await _flush(hass, entry)

    assert len(coordinator.history.records) == count
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_setter_and_command_boundary_activity_are_payload_free(
    hass: HomeAssistant,
) -> None:
    """Setter and invariant rejection record once without submitted values."""
    _set_states(hass)
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    climate_id = _entity_id(hass, Platform.CLIMATE, f"{ZONE_ID}:zone")
    climate_entity = hass.data[CLIMATE_COMPONENT].get_entity(climate_id)
    assert climate_entity is not None

    before_ids = {record.record_id for record in coordinator.history.records}
    with pytest.raises(ServiceValidationError):
        await climate_entity.async_set_temperature(
            temperature=12345.678,
            private_payload="do-not-store",
        )
    setter_records = [
        record
        for record in coordinator.history.records
        if record.record_id not in before_ids
    ]
    assert len(setter_records) == 1
    setter_record = setter_records[0]
    assert setter_record.activity_type is ActivityType.UNSUPPORTED_CONTROL_ATTEMPT
    assert setter_record.reason_code is ActivityReason.UNSUPPORTED_CONTROL_ATTEMPT

    await coordinator.command_sink.async_record_intent(
        ObservationIntent(
            source="climate.private_real_thermostat",
            description="set 99 with private payload",
        )
    )
    serialized = json.dumps(
        [
            {
                "explanation": record.explanation,
                "detail": dict(record.detail),
                "reason": record.reason_code.value,
            }
            for record in coordinator.history.records
        ]
    )
    assert "12345" not in serialized
    assert "do-not-store" not in serialized
    assert "climate.private_real_thermostat" not in serialized
    assert "set 99" not in serialized
    assert ActivityReason.COMMAND_BOUNDARY_VIOLATION.value in serialized

    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_activity_persists_without_hydrating_temperature_or_replaying_bus(
    hass: HomeAssistant,
) -> None:
    """Unload/reload restores history only and publishes no persisted temperature."""
    _set_states(hass)
    mock_entry = _entry()
    entry = await _setup(hass, mock_entry)
    coordinator = entry.runtime_data

    hass.states.async_set(
        SENSOR,
        STATE_UNAVAILABLE,
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
    )
    await _flush(hass, entry)
    persisted_record = coordinator.history.records[-1]
    persisted_timestamp = persisted_record.timestamp.isoformat()

    assert await hass.config_entries.async_unload(entry.entry_id)
    hass.states.async_remove(SENSOR)
    bus_events: list[dict[str, object]] = []
    unsubscribe = hass.bus.async_listen(
        EVENT_ACTIVITY,
        lambda event: bus_events.append(dict(event.data)),
    )
    reloaded = await _setup(hass, mock_entry)

    assert any(
        record.record_id == persisted_record.record_id
        for record in reloaded.runtime_data.history.records
    )
    assert all(payload["timestamp"] != persisted_timestamp for payload in bus_events)
    climate_state = hass.states.get(
        _entity_id(hass, Platform.CLIMATE, f"{ZONE_ID}:zone")
    )
    assert climate_state is not None
    assert climate_state.state == STATE_UNAVAILABLE
    assert ATTR_CURRENT_TEMPERATURE not in climate_state.attributes

    unsubscribe()
    assert await hass.config_entries.async_unload(reloaded.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_failed_platform_unload_preserves_runtime_and_no_unload_activity(
    hass: HomeAssistant,
) -> None:
    """A platform refusal leaves the coordinator, listeners, and Store usable."""
    _set_states(hass)
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    before = len(coordinator.history.records)

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(entry.entry_id)

    assert entry.runtime_data is coordinator
    assert coordinator._shutdown is False
    assert len(coordinator.history.records) == before
    assert all(
        record.reason_code is not ActivityReason.UNLOAD
        for record in coordinator.history.records
    )
    assert coordinator._cancel_state_change_subscription is not None
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_repairs_activity_and_multiple_entry_isolation(
    hass: HomeAssistant,
) -> None:
    """Issue transitions and all history/entity/Store scopes remain entry-local."""
    second_group = "379faccc-2bbb-456d-a8b9-00610f83ab9f"
    second_zone = "c2a791b0-778f-4a67-86b6-2835ed263a45"
    second_thermostat = "climate.second_physical_activity"
    second_sensor = "sensor.second_activity_temperature"
    _set_states(hass)
    _set_states(
        hass,
        thermostat=second_thermostat,
        sensor=second_sensor,
    )
    first = await _setup(hass, _entry())
    second = await _setup(
        hass,
        _entry(
            entry_id="activity-entry-2",
            group_id=second_group,
            zone_id=second_zone,
            thermostat=second_thermostat,
            sensor=second_sensor,
        ),
    )
    first_count = len(first.runtime_data.history.records)
    second_count = len(second.runtime_data.history.records)

    hass.states.async_remove(SENSOR)
    await _flush(hass, first)

    assert len(first.runtime_data.history.records) > first_count
    assert len(second.runtime_data.history.records) == second_count
    assert {record.activity_type for record in first.runtime_data.history.records} >= {
        ActivityType.SOURCE_QUALITY_CHANGED,
        ActivityType.REPAIR_ISSUE_CREATED,
    }
    created_count = sum(
        record.activity_type is ActivityType.REPAIR_ISSUE_CREATED
        for record in first.runtime_data.history.records
    )
    first.runtime_data.issue_manager.async_sync_entity_conditions(
        first.runtime_data.configuration
    )
    assert (
        sum(
            record.activity_type is ActivityType.REPAIR_ISSUE_CREATED
            for record in first.runtime_data.history.records
        )
        == created_count
    )
    assert all(
        record.equipment_group_id
        == first.runtime_data.configuration.equipment_group.equipment_group_id
        for record in first.runtime_data.history.records
    )
    assert all(
        record.equipment_group_id
        == second.runtime_data.configuration.equipment_group.equipment_group_id
        for record in second.runtime_data.history.records
    )
    assert first.runtime_data.runtime_store.key != second.runtime_data.runtime_store.key

    _set_states(hass)
    await _flush(hass, first)
    assert ActivityType.REPAIR_ISSUE_RESOLVED in {
        record.activity_type for record in first.runtime_data.history.records
    }
    resolved_count = sum(
        record.activity_type is ActivityType.REPAIR_ISSUE_RESOLVED
        for record in first.runtime_data.history.records
    )
    first.runtime_data.issue_manager.async_sync_entity_conditions(
        first.runtime_data.configuration
    )
    assert (
        sum(
            record.activity_type is ActivityType.REPAIR_ISSUE_RESOLVED
            for record in first.runtime_data.history.records
        )
        == resolved_count
    )
    assert _entity_id(
        hass,
        Platform.EVENT,
        f"{GROUP_ID}:activity",
    ) != _entity_id(
        hass,
        Platform.EVENT,
        f"{second_group}:activity",
    )

    assert await hass.config_entries.async_unload(first.entry_id)
    assert await hass.config_entries.async_unload(second.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_store_1_1_migration_restores_baseline_for_reconciliation_only(
    hass: HomeAssistant,
) -> None:
    """Startup migrates 0.0.5 data but never publishes its saved temperature."""
    _set_states(hass, sensor_state="20.0")
    legacy_store: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"intelligent_climate.{ENTRY_ID}",
        atomic_writes=True,
        minor_version=1,
    )
    await legacy_store.async_save(_store_document())
    events: list[dict[str, object]] = []
    unsubscribe = hass.bus.async_listen(
        EVENT_ACTIVITY,
        lambda event: events.append(dict(event.data)),
    )

    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        new_callable=AsyncMock,
    ) as service_call:
        entry = await _setup(hass, _entry())

    coordinator = entry.runtime_data
    runtime_store = coordinator.runtime_store
    assert runtime_store.load_status is StoreLoadStatus.MIGRATED
    assert runtime_store.minor_version == 2
    assert runtime_store.previous_clean_shutdown is False
    assert (
        runtime_store.restored_source_baselines[
            ObservationSourceId.parse(SOURCE_ID)
        ].last_accepted_value
        == 10.0
    )
    observation = coordinator.data.zones[0].temperature_observations[0]
    assert observation.quality is SourceQuality.JUMP_REJECTED
    assert coordinator.data.zones[0].effective_temperature_c is None
    climate_state = hass.states.get(
        _entity_id(hass, Platform.CLIMATE, f"{ZONE_ID}:zone")
    )
    assert climate_state is not None
    assert climate_state.state == STATE_UNAVAILABLE
    assert ATTR_CURRENT_TEMPERATURE not in climate_state.attributes
    assert all(
        state.attributes.get(ATTR_CURRENT_TEMPERATURE) != 40.0
        for state in hass.states.async_all()
    )
    assert (
        sum(
            payload["reason_code"] == ActivityReason.STORE_MIGRATED.value
            for payload in events
        )
        == 1
    )
    assert (
        sum(
            payload["reason_code"] == ActivityReason.UNCLEAN_SHUTDOWN_DETECTED.value
            for payload in events
        )
        == 1
    )
    service_call.assert_not_awaited()

    unsubscribe()
    assert await hass.config_entries.async_unload(entry.entry_id)
    current_store: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"intelligent_climate.{ENTRY_ID}",
        atomic_writes=True,
        minor_version=2,
    )
    saved = await current_store.async_load()
    assert saved is not None
    assert saved["schema_version"] == 1
    assert saved["last_clean_shutdown"] is True
    assert saved["command_journal"] == []


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_store_is_quarantined_then_repaired_by_clean_save(
    hass: HomeAssistant,
) -> None:
    """Semantic corruption cannot block setup and clears only after replacement."""
    _set_states(hass)
    primary: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"intelligent_climate.{ENTRY_ID}",
        atomic_writes=True,
        minor_version=2,
    )
    await primary.async_save(_store_document(entry_id="wrong-entry"))

    entry = await _setup(hass, _entry())
    runtime_store = entry.runtime_data.runtime_store
    registry = ir.async_get(hass)
    migration_issue = issue_id(entry.entry_id, IssueCode.MIGRATION_FAILED)
    assert runtime_store.load_status is StoreLoadStatus.QUARANTINED
    assert runtime_store.quarantine_present is True
    assert registry.async_get_issue(DOMAIN, migration_issue) is not None
    assert entry.runtime_data.data.zones[0].effective_temperature_c == 20.0
    diagnostics = await async_get_config_entry_diagnostics(hass, entry)
    assert diagnostics["runtime"]["store"]["load_status"] == "quarantined"
    assert diagnostics["runtime"]["store"]["quarantine_present"] is True
    assert "wrong-entry" not in json.dumps(diagnostics)

    assert await runtime_store._async_attempt_save(last_clean_shutdown=False)

    assert cast(Any, runtime_store).load_status is StoreLoadStatus.LOADED
    assert cast(Any, runtime_store).quarantine_present is False
    assert registry.async_get_issue(DOMAIN, migration_issue) is None
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_existing_quarantine_repair_survives_setup_until_verified_cleanup(
    hass: HomeAssistant,
) -> None:
    """A valid primary cannot clear a leftover quarantine issue during setup."""
    _set_states(hass)
    primary: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"intelligent_climate.{ENTRY_ID}",
        atomic_writes=True,
        minor_version=2,
    )
    await primary.async_save(
        _store_document(
            baseline_temperature=20.0,
            clean_shutdown=True,
        )
    )
    quarantine: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"intelligent_climate.{ENTRY_ID}.quarantine",
        atomic_writes=True,
    )
    await quarantine.async_save(
        {
            "quarantined_at": utcnow().isoformat(),
            "reason_code": "invalid_nonauthoritative_store",
            "data": {"invalid": True},
        }
    )
    RepairsManager(hass, ENTRY_ID).async_report_migration_failure(
        MigrationFailureCategory.STORE_VALIDATION
    )

    entry = await _setup(hass, _entry())
    runtime_store = entry.runtime_data.runtime_store
    registry = ir.async_get(hass)
    migration_issue = issue_id(entry.entry_id, IssueCode.MIGRATION_FAILED)

    assert runtime_store.load_status is StoreLoadStatus.LOADED
    assert runtime_store.quarantine_present is True
    assert registry.async_get_issue(DOMAIN, migration_issue) is not None

    assert await runtime_store._async_attempt_save(last_clean_shutdown=False)

    assert not cast(Any, runtime_store).quarantine_present
    assert cast(Any, registry).async_get_issue(DOMAIN, migration_issue) is None
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_future_store_minor_is_preserved_read_only_across_unload(
    hass: HomeAssistant,
) -> None:
    """Unknown future persistence starts safely without destructive downgrade."""
    _set_states(hass)
    future_payload = _store_document()
    future_store: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"intelligent_climate.{ENTRY_ID}",
        atomic_writes=True,
        minor_version=99,
    )
    await future_store.async_save(future_payload)

    entry = await _setup(hass, _entry())
    runtime_store = entry.runtime_data.runtime_store
    assert runtime_store.load_status is StoreLoadStatus.UNSUPPORTED
    assert runtime_store.read_only is True
    assert runtime_store.dirty is False
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN,
            issue_id(entry.entry_id, IssueCode.MIGRATION_FAILED),
        )
        is not None
    )
    assert entry.runtime_data.data.zones[0].effective_temperature_c == 20.0

    assert await hass.config_entries.async_unload(entry.entry_id)
    reloaded_future = await future_store.async_load()
    assert reloaded_future == future_payload
