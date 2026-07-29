"""Test the event-driven observe-only coordinator with Home Assistant."""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from homeassistant import config_entries
from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_MODES,
)
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_RESTORED,
    ATTR_SUPPORTED_FEATURES,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate.const import DOMAIN
from custom_components.intelligent_climate.coordinator import (
    IntelligentClimateCoordinator,
)
from custom_components.intelligent_climate.models import (
    DEFAULT_OPTIONS,
    AggregationStatus,
    AggregationStrategy,
    ControlState,
    EntryRuntimeConfiguration,
    EquipmentGroupConfig,
    EquipmentGroupId,
    EquipmentRelationship,
    EquipmentType,
    ExclusionReason,
    HumiditySource,
    ObservationSourceId,
    RuntimeConfigurationState,
    SourceQuality,
    TemperatureSource,
    ThermostatBinding,
    ThermostatCapabilityDiscoveryStatus,
    ThermostatRole,
    ZoneConfig,
    ZoneId,
    encode_equipment_group_document,
    encode_zone_config,
)
from custom_components.intelligent_climate.models.schema import EquipmentGroupDocument

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)
THERMOSTAT = "climate.main"
SHARED_SENSOR = "sensor.shared"
OTHER_SENSOR = "sensor.other"
HUMIDITY_SENSOR = "sensor.humidity"
THIRD_SENSOR = "sensor.third"
GROUP_ID = EquipmentGroupId.parse("b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3")
ZONE_IDS = (
    ZoneId.parse("99246285-6f02-4e8a-94ed-bdfd4a5e62c4"),
    ZoneId.parse("7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"),
    ZoneId.parse("7d5e2ab2-b2ef-4989-876b-f92d541f17d7"),
)
SOURCE_IDS = (
    ObservationSourceId.parse("f15f73b1-ea59-4b28-819f-7b99acf065bf"),
    ObservationSourceId.parse("ce30dafc-fadd-4cc4-b261-8a896d5a6d12"),
    ObservationSourceId.parse("4d61f93e-a98a-4ce1-bd4a-58b571bdd115"),
)


def _source(
    index: int,
    entity_id: str,
    *,
    enabled: bool = True,
    offset_c: float = 0,
) -> TemperatureSource:
    return TemperatureSource(
        source_id=SOURCE_IDS[index],
        entity_id=entity_id,
        attribute=None,
        offset_c=offset_c,
        weight=1,
        priority=0,
        enabled=enabled,
    )


def _configuration(
    *,
    zone_count: int = 2,
    observation_enabled: bool = True,
    restored: bool = False,
    empty: bool = False,
) -> EntryRuntimeConfiguration:
    del restored
    group = EquipmentGroupConfig(
        equipment_group_id=GROUP_ID,
        name="Main",
        equipment_type=EquipmentType.CONVENTIONAL,
        relationship=EquipmentRelationship.SINGLE_SYSTEM,
        thermostats=(
            () if empty else (ThermostatBinding(THERMOSTAT, ThermostatRole.PRIMARY),)
        ),
        shared_policy=None,
    )
    zones: tuple[ZoneConfig, ...]
    if empty:
        zones = ()
    else:
        zones = tuple(
            ZoneConfig(
                zone_id=ZONE_IDS[index],
                name=f"Zone {index}",
                thermostat_entity_ids=(THERMOSTAT,),
                temperature_sources=(
                    _source(
                        index,
                        SHARED_SENSOR if index < 2 else OTHER_SENSOR,
                        offset_c=float(index),
                    ),
                ),
                humidity_sources=(),
                window_door_entity_ids=(),
                occupancy_entity_ids=(),
                stage_entity_ids=(),
                fan_entity_ids=(),
            )
            for index in range(zone_count)
        )
    return EntryRuntimeConfiguration(
        equipment_group=group,
        zones=zones,
        options=replace(
            DEFAULT_OPTIONS,
            observation_enabled=observation_enabled,
            source_stale_after_seconds=10,
            startup_reconciliation_seconds=60,
        ),
        state=(
            RuntimeConfigurationState.TRANSITIONAL_EMPTY_SKELETON
            if empty
            else RuntimeConfigurationState.CONFIGURED
        ),
    )


def _entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry-1",
        data={},
        version=1,
        minor_version=0,
        state=config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    )


def _set_states(
    hass: HomeAssistant,
    *,
    thermostat_mode: HVACMode = HVACMode.HEAT,
    shared_value: float = 20,
    other_value: float = 22,
    timestamp: datetime = NOW,
    restored: bool = False,
) -> None:
    hass.states.async_set(
        THERMOSTAT,
        thermostat_mode,
        {
            ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL],
            ATTR_SUPPORTED_FEATURES: int(ClimateEntityFeature.TARGET_TEMPERATURE),
            ATTR_CURRENT_TEMPERATURE: shared_value,
        },
        timestamp=timestamp.timestamp(),
    )
    sensor_attributes: dict[str, object] = {
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
    }
    if restored:
        sensor_attributes[ATTR_RESTORED] = True
    hass.states.async_set(
        SHARED_SENSOR,
        str(shared_value),
        sensor_attributes,
        timestamp=timestamp.timestamp(),
    )
    hass.states.async_set(
        OTHER_SENSOR,
        str(other_value),
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
        timestamp=timestamp.timestamp(),
    )


async def _start(
    hass: HomeAssistant,
    configuration: EntryRuntimeConfiguration | None = None,
) -> IntelligentClimateCoordinator:
    coordinator = IntelligentClimateCoordinator(
        hass,
        _entry(),
        configuration or _configuration(),
        now_fn=lambda: NOW,
    )
    await coordinator.async_start()
    return coordinator


async def test_initial_refresh_builds_ordered_capabilities_zones_and_indexes(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    coordinator = await _start(hass)

    snapshot = coordinator.data
    assert snapshot.revision == 1
    assert snapshot.reconciling is True
    assert snapshot.control_state is ControlState.RECONCILING
    assert snapshot.thermostats[0].entity_id == THERMOSTAT
    assert (
        snapshot.thermostats[0].capability_discovery.status
        is ThermostatCapabilityDiscoveryStatus.COMPLETE
    )
    assert tuple(zone.zone_id for zone in snapshot.zones) == ZONE_IDS[:2]
    assert tuple(zone.effective_temperature_c for zone in snapshot.zones) == (
        20,
        21,
    )
    assert coordinator.source_dependency_index[SHARED_SENSOR] == ZONE_IDS[:2]
    assert coordinator.thermostat_dependency_index[THERMOSTAT] == ZONE_IDS[:2]
    assert coordinator._cancel_state_change_subscription is not None
    assert coordinator._cancel_state_report_subscription is not None
    assert coordinator._cancel_reconciliation is not None
    assert coordinator._cancel_watchdog is not None
    await coordinator.async_shutdown()


async def test_subscription_uses_one_unique_union_and_unrelated_changes_do_nothing(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    event_helpers = __import__("homeassistant.helpers.event", fromlist=["unused"])
    with (
        patch(
            "custom_components.intelligent_climate.coordinator."
            "async_track_state_change_event",
            wraps=event_helpers.async_track_state_change_event,
        ) as track_changes,
        patch(
            "custom_components.intelligent_climate.coordinator."
            "async_track_state_report_event",
            wraps=event_helpers.async_track_state_report_event,
        ) as track_reports,
    ):
        coordinator = await _start(hass, _configuration(zone_count=3))

    assert track_changes.call_count == 1
    assert track_reports.call_count == 1
    expected_entities = (
        SHARED_SENSOR,
        OTHER_SENSOR,
        THERMOSTAT,
    )
    assert tuple(track_changes.call_args.args[1]) == expected_entities
    assert tuple(track_reports.call_args.args[1]) == expected_entities
    revision = coordinator.data.revision
    hass.states.async_set("sensor.unrelated", "99")
    await hass.async_block_till_done()
    assert coordinator.data.revision == revision
    assert coordinator._pending_zone_ids == set()
    await coordinator.async_shutdown()


async def test_source_burst_unions_zones_notifies_once_and_preserves_unaffected(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    coordinator = await _start(hass, _configuration(zone_count=3))
    listener = Mock()
    remove_listener = coordinator.async_add_listener(listener)
    original_zones = coordinator.data.zones

    _set_states(hass, shared_value=20.1, timestamp=NOW + timedelta(seconds=1))
    _set_states(hass, shared_value=20.2, timestamp=NOW + timedelta(seconds=2))
    await hass.async_block_till_done()
    generation = coordinator._debounce_generation
    assert coordinator._pending_zone_ids == set(ZONE_IDS)

    await coordinator._async_debounce_elapsed(
        NOW + timedelta(seconds=2),
        generation=generation,
    )

    assert coordinator.data.revision == 2
    assert listener.call_count == 1
    assert coordinator.data.zones[0] is not original_zones[0]
    assert coordinator.data.zones[1] is not original_zones[1]
    assert coordinator.data.zones[2] is not original_zones[2]
    assert coordinator.data.zones[2].calculated_at == NOW + timedelta(seconds=2)
    remove_listener()
    await coordinator.async_shutdown()


async def test_one_source_change_only_replaces_its_zone_and_old_debounce_is_noop(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    coordinator = await _start(hass, _configuration(zone_count=3))
    original = coordinator.data.zones

    hass.states.async_set(
        OTHER_SENSOR,
        "22.1",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
        timestamp=(NOW + timedelta(seconds=1)).timestamp(),
    )
    await hass.async_block_till_done()
    current_generation = coordinator._debounce_generation
    await coordinator._async_debounce_elapsed(
        NOW + timedelta(seconds=1),
        generation=current_generation - 1,
    )
    assert coordinator.data.revision == 1

    await coordinator._async_debounce_elapsed(
        NOW + timedelta(seconds=1),
        generation=current_generation,
    )
    assert coordinator.data.zones[0] is original[0]
    assert coordinator.data.zones[1] is original[1]
    assert coordinator.data.zones[2] is not original[2]
    assert coordinator.data.zones[0].calculated_at is NOW
    await coordinator.async_shutdown()


async def test_thermostat_change_refreshes_capability_and_source_dependencies_once(
    hass: HomeAssistant,
) -> None:
    configuration = _configuration(zone_count=1)
    zone = configuration.zones[0]
    configuration = replace(
        configuration,
        zones=(
            replace(
                zone,
                temperature_sources=(
                    replace(
                        zone.temperature_sources[0],
                        entity_id=THERMOSTAT,
                        attribute=ATTR_CURRENT_TEMPERATURE,
                    ),
                ),
            ),
        ),
    )
    _set_states(hass)
    coordinator = await _start(hass, configuration)
    original_discovery = coordinator.data.thermostats[0].capability_discovery

    hass.states.async_set(
        THERMOSTAT,
        HVACMode.COOL,
        {
            ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.COOL],
            ATTR_SUPPORTED_FEATURES: 0,
            ATTR_CURRENT_TEMPERATURE: 21,
        },
        timestamp=(NOW + timedelta(minutes=5)).timestamp(),
    )
    await hass.async_block_till_done()
    assert coordinator._pending_zone_ids == {ZONE_IDS[0]}
    assert coordinator._pending_thermostat_entity_ids == {THERMOSTAT}

    await coordinator._async_debounce_elapsed(
        NOW + timedelta(minutes=5),
        generation=coordinator._debounce_generation,
    )

    assert coordinator.data.revision == 2
    assert coordinator.data.thermostats[0].state.hvac_mode is HVACMode.COOL
    assert (
        coordinator.data.thermostats[0].capability_discovery is not original_discovery
    )
    await coordinator.async_shutdown()


async def test_sensor_uses_recent_report_when_last_update_is_hours_old(
    hass: HomeAssistant,
) -> None:
    """An unchanged but recently reported sensor remains fresh."""
    old = NOW - timedelta(hours=4)
    _set_states(hass, timestamp=old)
    _set_states(hass, timestamp=NOW)
    state = hass.states.get(SHARED_SENSOR)
    assert state is not None
    assert state.last_updated == old
    assert state.last_reported == NOW

    coordinator = await _start(hass, _configuration(zone_count=1))

    observation = coordinator.data.zones[0].temperature_observations[0]
    assert observation.source_last_reported == NOW
    assert observation.quality is SourceQuality.VALID
    assert coordinator.data.zones[0].effective_temperature_c == 20
    assert coordinator._stale_deadline(observation) == (
        NOW + timedelta(seconds=10, microseconds=1)
    )
    await coordinator.async_shutdown()


async def test_climate_source_uses_recent_report_when_last_update_is_hours_old(
    hass: HomeAssistant,
) -> None:
    """A climate current-temperature report uses its report timestamp."""
    configuration = _configuration(zone_count=1)
    zone = configuration.zones[0]
    configuration = replace(
        configuration,
        zones=(
            replace(
                zone,
                temperature_sources=(
                    replace(
                        zone.temperature_sources[0],
                        entity_id=THERMOSTAT,
                        attribute=ATTR_CURRENT_TEMPERATURE,
                    ),
                ),
            ),
        ),
    )
    old = NOW - timedelta(hours=4)
    _set_states(hass, timestamp=old)
    _set_states(hass, timestamp=NOW)
    state = hass.states.get(THERMOSTAT)
    assert state is not None
    assert state.last_updated == old
    assert state.last_reported == NOW

    coordinator = await _start(hass, configuration)

    observation = coordinator.data.zones[0].temperature_observations[0]
    assert observation.source_last_reported == NOW
    assert observation.quality is SourceQuality.VALID
    await coordinator.async_shutdown()


async def test_same_value_report_recovers_stale_source_without_state_change(
    hass: HomeAssistant,
) -> None:
    """The state-report listener refreshes freshness through the debounce path."""
    stale_at = NOW - timedelta(seconds=11)
    _set_states(hass, timestamp=stale_at)
    coordinator = await _start(hass, _configuration(zone_count=1))
    assert coordinator.data.zones[0].temperature_observations[0].quality is (
        SourceQuality.STALE
    )
    generation = coordinator._debounce_generation

    hass.states.async_set(
        SHARED_SENSOR,
        "20",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
        timestamp=NOW.timestamp(),
    )
    await hass.async_block_till_done()

    current = hass.states.get(SHARED_SENSOR)
    assert current is not None
    assert current.last_updated == stale_at
    assert current.last_reported == NOW
    assert coordinator._debounce_generation == generation + 1
    assert coordinator._pending_zone_ids == {ZONE_IDS[0]}
    await coordinator._async_debounce_elapsed(
        NOW,
        generation=coordinator._debounce_generation,
    )
    recovered = coordinator.data.zones[0].temperature_observations[0]
    assert recovered.quality is SourceQuality.VALID
    assert recovered.source_last_reported == NOW
    assert coordinator.data.zones[0].effective_temperature_c == 20
    await coordinator.async_shutdown()


async def test_watchdog_respects_exact_boundary_then_excludes_stale_source(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    coordinator = await _start(hass, _configuration(zone_count=1))
    original = coordinator.data.zones[0]

    await coordinator._async_watchdog_elapsed(
        NOW + timedelta(seconds=10),
        generation=coordinator._watchdog_generation,
    )
    assert coordinator.data.revision == 1
    assert coordinator.data.zones[0] is original

    await coordinator._async_watchdog_elapsed(
        NOW + timedelta(seconds=10, microseconds=1),
        generation=coordinator._watchdog_generation,
    )

    assert coordinator.data.revision == 2
    assert coordinator.data.zones[0].temperature_observations[0].quality is (
        SourceQuality.STALE
    )
    assert coordinator.data.zones[0].effective_temperature_c is None
    assert coordinator.data.zones[0].temperature_aggregation.status is (
        AggregationStatus.UNAVAILABLE
    )
    assert coordinator._cancel_watchdog is None
    await coordinator.async_shutdown()


async def test_watchdog_reschedules_next_deadline_and_state_update_replaces_it(
    hass: HomeAssistant,
) -> None:
    configuration = _configuration(zone_count=1)
    zone = configuration.zones[0]
    configuration = replace(
        configuration,
        zones=(
            replace(
                zone,
                temperature_sources=(
                    _source(0, SHARED_SENSOR),
                    _source(1, OTHER_SENSOR),
                ),
            ),
        ),
    )
    _set_states(hass, shared_value=20, other_value=21)
    hass.states.async_set(
        OTHER_SENSOR,
        "21",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
        force_update=True,
        timestamp=(NOW + timedelta(seconds=5)).timestamp(),
    )
    coordinator = await _start(hass, configuration)
    initial_watchdog = coordinator._cancel_watchdog

    await coordinator._async_watchdog_elapsed(
        NOW + timedelta(seconds=10, microseconds=1),
        generation=coordinator._watchdog_generation,
    )
    assert coordinator.data.revision == 2
    assert coordinator.data.zones[0].temperature_observations[0].quality is (
        SourceQuality.STALE
    )
    assert coordinator.data.zones[0].temperature_observations[1].quality is (
        SourceQuality.VALID
    )
    assert coordinator._cancel_watchdog is not None
    assert coordinator._cancel_watchdog is not initial_watchdog

    old_generation = coordinator._watchdog_generation
    hass.states.async_set(
        OTHER_SENSOR,
        "21",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
        force_update=True,
        timestamp=(NOW + timedelta(seconds=12)).timestamp(),
    )
    await hass.async_block_till_done()
    await coordinator._async_debounce_elapsed(
        NOW + timedelta(seconds=12),
        generation=coordinator._debounce_generation,
    )
    assert coordinator._watchdog_generation > old_generation
    revision = coordinator.data.revision
    await coordinator._async_watchdog_elapsed(
        NOW + timedelta(seconds=15, microseconds=1),
        generation=old_generation,
    )
    assert coordinator.data.revision == revision

    await coordinator._async_watchdog_elapsed(
        NOW + timedelta(seconds=22, microseconds=1),
        generation=coordinator._watchdog_generation,
    )
    assert coordinator.data.revision == revision + 1
    assert all(
        observation.quality is SourceQuality.STALE
        for observation in coordinator.data.zones[0].temperature_observations
    )
    await coordinator.async_shutdown()


async def test_reconciliation_completion_reevaluates_and_restored_stays_excluded(
    hass: HomeAssistant,
) -> None:
    _set_states(hass, restored=True)
    coordinator = await _start(hass, _configuration(zone_count=1))
    listener = Mock()
    coordinator.async_add_listener(listener)

    assert coordinator.data.zones[0].temperature_observations[0].quality is (
        SourceQuality.RESTORED_NOT_CONFIRMED
    )
    generation = coordinator._reconciliation_generation
    await coordinator._async_reconciliation_complete(
        NOW + timedelta(seconds=60),
        generation=generation,
    )

    assert coordinator.data.revision == 2
    assert coordinator.data.reconciling is False
    assert coordinator.data.control_state is ControlState.DEGRADED
    assert coordinator.data.zones[0].temperature_observations[0].quality is (
        SourceQuality.RESTORED_NOT_CONFIRMED
    )
    assert listener.call_count == 1
    await coordinator.async_shutdown()


@pytest.mark.parametrize(("disabled", "empty"), [(True, False), (False, True)])
async def test_disabled_and_empty_runtime_register_no_callbacks(
    hass: HomeAssistant,
    disabled: bool,
    empty: bool,
) -> None:
    _set_states(hass)
    coordinator = await _start(
        hass,
        _configuration(observation_enabled=not disabled, empty=empty),
    )

    assert coordinator.data.reconciling is False
    assert coordinator.data.control_state is (
        ControlState.DISABLED if disabled else ControlState.OBSERVING
    )
    assert coordinator._cancel_state_change_subscription is None
    assert coordinator._cancel_state_report_subscription is None
    assert coordinator._cancel_reconciliation is None
    assert coordinator._cancel_watchdog is None
    if disabled:
        assert len(coordinator.data.zones) == 2
        assert coordinator.data.zones[0].temperature_observations == ()
        assert coordinator.data.zones[0].sensor_data_degraded is False
    else:
        assert coordinator.data.zones == ()
    await coordinator.async_shutdown()


async def test_disabled_source_is_not_indexed_read_or_scheduled(
    hass: HomeAssistant,
) -> None:
    configuration = _configuration(zone_count=1)
    zone = configuration.zones[0]
    configuration = replace(
        configuration,
        zones=(
            replace(
                zone,
                temperature_sources=(
                    replace(zone.temperature_sources[0], enabled=False),
                ),
            ),
        ),
    )
    _set_states(hass)

    coordinator = await _start(hass, configuration)

    assert SHARED_SENSOR not in coordinator.source_dependency_index
    assert coordinator.data.zones[0].temperature_observations == ()
    assert coordinator.data.zones[0].effective_temperature_c is None
    assert coordinator._cancel_watchdog is None
    await coordinator.async_shutdown()


async def test_missing_thermostat_is_snapshot_degradation_not_refresh_failure(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    hass.states.async_remove(THERMOSTAT)
    coordinator = await _start(hass, _configuration(zone_count=1))

    initial_snapshot = coordinator.data
    assert initial_snapshot.thermostats[0].state.available is False
    assert initial_snapshot.zones[0].thermostat_data_degraded is True
    assert initial_snapshot.control_state is ControlState.RECONCILING
    await coordinator._async_reconciliation_complete(
        NOW + timedelta(seconds=60),
        generation=coordinator._reconciliation_generation,
    )
    completed_snapshot = coordinator.data
    assert completed_snapshot.control_state is ControlState.DEGRADED
    await coordinator.async_shutdown()


async def test_shutdown_is_idempotent_and_late_callbacks_cannot_publish(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    coordinator = await _start(hass, _configuration(zone_count=1))
    listener = Mock()
    coordinator.async_add_listener(listener)
    debounce_generation = coordinator._debounce_generation
    watchdog_generation = coordinator._watchdog_generation
    reconciliation_generation = coordinator._reconciliation_generation

    await coordinator._async_core_shutdown()
    await coordinator.async_shutdown()
    _set_states(hass, shared_value=21, timestamp=NOW + timedelta(seconds=1))
    _set_states(hass, shared_value=21, timestamp=NOW + timedelta(seconds=2))
    await hass.async_block_till_done()
    await coordinator._async_debounce_elapsed(
        NOW,
        generation=debounce_generation,
    )
    await coordinator._async_watchdog_elapsed(
        NOW + timedelta(hours=1),
        generation=watchdog_generation,
    )
    await coordinator._async_reconciliation_complete(
        NOW + timedelta(minutes=1),
        generation=reconciliation_generation,
    )

    assert coordinator.data.revision == 1
    assert listener.call_count == 0
    assert coordinator._cancel_state_change_subscription is None
    assert coordinator._cancel_state_report_subscription is None
    assert coordinator._cancel_debounce is None
    assert coordinator._cancel_reconciliation is None
    assert coordinator._cancel_watchdog is None


async def test_humidity_pipeline_uses_calibration_and_optional_aggregation(
    hass: HomeAssistant,
) -> None:
    configuration = _configuration(zone_count=1)
    zone = configuration.zones[0]
    humidity_source = HumiditySource(
        source_id=SOURCE_IDS[1],
        entity_id=HUMIDITY_SENSOR,
        attribute=None,
        offset_pct=2.5,
        weight=1,
        priority=0,
        enabled=True,
    )
    configuration = replace(
        configuration,
        zones=(replace(zone, humidity_sources=(humidity_source,)),),
    )
    _set_states(hass)
    hass.states.async_set(
        HUMIDITY_SENSOR,
        "45",
        {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE},
        timestamp=NOW.timestamp(),
    )

    coordinator = await _start(hass, configuration)

    zone_snapshot = coordinator.data.zones[0]
    assert zone_snapshot.humidity_observations[0].normalized_value == 47.5
    assert zone_snapshot.effective_humidity_pct == 47.5
    assert zone_snapshot.humidity_aggregation is not None
    assert zone_snapshot.humidity_aggregation.status is AggregationStatus.HEALTHY
    assert coordinator.source_dependency_index[HUMIDITY_SENSOR] == (ZONE_IDS[0],)
    await coordinator.async_shutdown()


async def test_humidity_freshness_uses_last_reported(
    hass: HomeAssistant,
) -> None:
    configuration = _configuration(zone_count=1)
    zone = configuration.zones[0]
    humidity_source = HumiditySource(
        source_id=SOURCE_IDS[1],
        entity_id=HUMIDITY_SENSOR,
        attribute=None,
        offset_pct=0,
        weight=1,
        priority=0,
        enabled=True,
    )
    configuration = replace(
        configuration,
        zones=(replace(zone, humidity_sources=(humidity_source,)),),
    )
    _set_states(hass)
    old = NOW - timedelta(hours=4)
    attributes = {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE}
    hass.states.async_set(
        HUMIDITY_SENSOR,
        "45",
        attributes,
        timestamp=old.timestamp(),
    )
    hass.states.async_set(
        HUMIDITY_SENSOR,
        "45",
        attributes,
        timestamp=NOW.timestamp(),
    )

    coordinator = await _start(hass, configuration)

    observation = coordinator.data.zones[0].humidity_observations[0]
    current = hass.states.get(HUMIDITY_SENSOR)
    assert current is not None
    assert current.last_updated == old
    assert observation.source_last_reported == NOW
    assert observation.quality is SourceQuality.VALID
    await coordinator.async_shutdown()


async def test_temperature_jump_requires_second_live_update_to_confirm(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    coordinator = await _start(hass, _configuration(zone_count=1))

    hass.states.async_set(
        SHARED_SENSOR,
        "30",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
        timestamp=(NOW + timedelta(minutes=5)).timestamp(),
    )
    await hass.async_block_till_done()
    await coordinator._async_debounce_elapsed(
        NOW + timedelta(minutes=5),
        generation=coordinator._debounce_generation,
    )
    candidate_snapshot = coordinator.data
    assert candidate_snapshot.zones[0].temperature_observations[0].quality is (
        SourceQuality.JUMP_REJECTED
    )
    assert candidate_snapshot.zones[0].effective_temperature_c is None

    hass.states.async_set(
        SHARED_SENSOR,
        "30.1",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
        timestamp=(NOW + timedelta(minutes=5, seconds=30)).timestamp(),
    )
    await hass.async_block_till_done()
    await coordinator._async_debounce_elapsed(
        NOW + timedelta(minutes=5, seconds=30),
        generation=coordinator._debounce_generation,
    )

    confirmed_snapshot = coordinator.data
    assert confirmed_snapshot.revision == 3
    assert confirmed_snapshot.zones[0].temperature_observations[0].quality is (
        SourceQuality.VALID
    )
    assert confirmed_snapshot.zones[0].effective_temperature_c == 30.1
    await coordinator.async_shutdown()


@pytest.mark.parametrize(
    "strategy",
    list(AggregationStrategy),
)
async def test_coordinator_invokes_every_configured_temperature_strategy(
    hass: HomeAssistant,
    strategy: AggregationStrategy,
) -> None:
    configuration = _configuration(zone_count=1)
    zone = configuration.zones[0]
    configuration = replace(
        configuration,
        options=replace(configuration.options, temperature_strategy=strategy),
        zones=(
            replace(
                zone,
                temperature_sources=(replace(zone.temperature_sources[0], priority=1),),
            ),
        ),
    )
    _set_states(hass)

    coordinator = await _start(hass, configuration)

    assert coordinator.data.zones[0].effective_temperature_c == 20
    await coordinator.async_shutdown()


async def test_new_unavailable_result_never_reuses_prior_aggregate(
    hass: HomeAssistant,
) -> None:
    _set_states(hass)
    coordinator = await _start(hass, _configuration(zone_count=1))
    available_snapshot = coordinator.data
    assert available_snapshot.zones[0].effective_temperature_c == 20

    hass.states.async_set(
        SHARED_SENSOR,
        "unavailable",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
        timestamp=(NOW + timedelta(seconds=1)).timestamp(),
    )
    await hass.async_block_till_done()
    await coordinator._async_debounce_elapsed(
        NOW + timedelta(seconds=1),
        generation=coordinator._debounce_generation,
    )

    unavailable_snapshot = coordinator.data
    assert unavailable_snapshot.zones[0].effective_temperature_c is None
    assert unavailable_snapshot.zones[0].temperature_aggregation.status is (
        AggregationStatus.UNAVAILABLE
    )
    await coordinator.async_shutdown()


async def test_fahrenheit_sensor_is_normalized_with_calibration(
    hass: HomeAssistant,
) -> None:
    configuration = _configuration(zone_count=1)
    zone = configuration.zones[0]
    configuration = replace(
        configuration,
        zones=(
            replace(
                zone,
                temperature_sources=(
                    replace(zone.temperature_sources[0], offset_c=1.5),
                ),
            ),
        ),
    )
    _set_states(hass)
    hass.states.async_set(
        SHARED_SENSOR,
        "68",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        },
        timestamp=NOW.timestamp(),
    )

    coordinator = await _start(hass, configuration)

    assert coordinator.data.zones[0].temperature_observations[0].normalized_value == (
        21.5
    )
    assert coordinator.data.zones[0].effective_temperature_c == 21.5
    await coordinator.async_shutdown()


async def test_implausible_temperature_is_excluded_before_aggregation(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="custom_components.intelligent_climate.coordinator",
    )
    _set_states(hass, shared_value=100)
    coordinator = await _start(hass, _configuration(zone_count=1))

    observation = coordinator.data.zones[0].temperature_observations[0]
    assert observation.quality is SourceQuality.IMPLAUSIBLE
    assert observation.exclusion_reason is ExclusionReason.IMPLAUSIBLE
    assert coordinator.data.zones[0].effective_temperature_c is None
    message = next(
        record.getMessage()
        for record in caplog.records
        if record.getMessage().startswith("Configured source excluded:")
    )
    assert f"config_entry_id={coordinator.entry.entry_id}" in message
    assert f"zone_id={ZONE_IDS[0]}" in message
    assert f"source_id={SOURCE_IDS[0]}" in message
    assert f"source_entity_id={SHARED_SENSOR}" in message
    assert "source_quality=implausible" in message
    assert "exclusion_reason=implausible" in message
    assert f"source_last_reported={NOW.isoformat(' ')}" in message
    assert f"observation_time={NOW.isoformat(' ')}" in message
    assert "attributes" not in message
    await coordinator.async_shutdown()


async def test_mad_outlier_and_two_source_contradiction_run_in_coordinator(
    hass: HomeAssistant,
) -> None:
    base = _configuration(zone_count=1)
    zone = base.zones[0]
    three_sources = (
        _source(0, SHARED_SENSOR),
        _source(1, OTHER_SENSOR),
        _source(2, THIRD_SENSOR),
    )
    outlier_config = replace(
        base,
        zones=(replace(zone, temperature_sources=three_sources),),
        options=replace(base.options, min_valid_temperature_sources=2),
    )
    _set_states(hass, shared_value=20, other_value=20)
    hass.states.async_set(
        THIRD_SENSOR,
        "30",
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
            ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        },
        timestamp=NOW.timestamp(),
    )
    outlier = await _start(hass, outlier_config)

    assert outlier.data.zones[0].effective_temperature_c == 20
    assert outlier.data.zones[0].temperature_aggregation.status is (
        AggregationStatus.DEGRADED
    )
    assert outlier.data.zones[0].excluded_sources[0].quality is SourceQuality.OUTLIER
    await outlier.async_shutdown()

    contradiction_config = replace(
        base,
        zones=(replace(zone, temperature_sources=three_sources[:2]),),
    )
    _set_states(hass, shared_value=20, other_value=30)
    contradiction = await _start(hass, contradiction_config)

    assert contradiction.data.zones[0].effective_temperature_c is None
    assert {item.quality for item in contradiction.data.zones[0].excluded_sources} == {
        SourceQuality.CONTRADICTORY
    }
    await contradiction.async_shutdown()


async def test_minimum_count_is_enforced_by_coordinator_pipeline(
    hass: HomeAssistant,
) -> None:
    configuration = _configuration(zone_count=1)
    configuration = replace(
        configuration,
        options=replace(
            configuration.options,
            min_valid_temperature_sources=2,
        ),
    )
    _set_states(hass)

    coordinator = await _start(hass, configuration)

    assert coordinator.data.zones[0].effective_temperature_c is None
    assert coordinator.data.zones[0].temperature_aggregation.status is (
        AggregationStatus.UNAVAILABLE
    )
    await coordinator.async_shutdown()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_real_config_entry_reload_replaces_runtime_without_services(
    hass: HomeAssistant,
) -> None:
    _set_states(hass, timestamp=utcnow())
    configuration = _configuration(zone_count=1)
    group_data = dict(
        encode_equipment_group_document(
            EquipmentGroupDocument(configuration.equipment_group)
        )
    )
    zone = configuration.zones[0]
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="real-entry",
        data=group_data,
        subentries_data=[
            ConfigSubentryDataWithId(
                data=dict(encode_zone_config(zone)),
                subentry_id="zone-subentry-1",
                subentry_type="zone",
                title=zone.name,
                unique_id=str(zone.zone_id),
            )
        ],
        version=1,
        minor_version=0,
    )
    entry.add_to_hass(hass)

    with patch.object(type(hass.services), "async_call") as service_call:
        assert await hass.config_entries.async_setup(entry.entry_id)
        first = entry.runtime_data
        assert await hass.config_entries.async_reload(entry.entry_id)
        second = entry.runtime_data
        assert first is not second
        assert first._shutdown is True
        assert second.data.revision == 1
        assert second._source_baselines
        assert first._source_baselines is not second._source_baselines
        assert DOMAIN not in hass.services.async_services()
        assert service_call.call_count == 0
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert service_call.call_count == 0

    assert not hasattr(entry, "runtime_data")
