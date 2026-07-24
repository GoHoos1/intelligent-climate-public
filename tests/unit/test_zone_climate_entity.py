"""Test the read-only coordinator-backed zone climate entity."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from typing import cast
from unittest.mock import patch

import pytest
from homeassistant import config_entries
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    ClimateEntityStateAttribute,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate.climate import (
    IntelligentClimateZoneClimateEntity,
)
from custom_components.intelligent_climate.const import DOMAIN, NAME
from custom_components.intelligent_climate.coordinator import (
    IntelligentClimateCoordinator,
)
from custom_components.intelligent_climate.models import (
    DEFAULT_OPTIONS,
    AggregationReason,
    AggregationStatus,
    ControlState,
    EntryObservationSnapshot,
    EntryRuntimeConfiguration,
    EquipmentGroupConfig,
    EquipmentGroupId,
    EquipmentRelationship,
    EquipmentType,
    HumiditySource,
    NormalizedClimateState,
    ObservableBoolean,
    ObservationSourceId,
    RuntimeConfigurationState,
    SourceAggregationResult,
    TemperatureSource,
    ThermostatBinding,
    ThermostatRole,
    ZoneConfig,
    ZoneId,
    ZoneObservation,
)
from custom_components.intelligent_climate.type_aliases import (
    IntelligentClimateConfigEntry,
)

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)
GROUP_ID = EquipmentGroupId.parse("b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3")
ZONE_ID = ZoneId.parse("99246285-6f02-4e8a-94ed-bdfd4a5e62c4")
SOURCE_ID = ObservationSourceId.parse("f15f73b1-ea59-4b28-819f-7b99acf065bf")
HUMIDITY_SOURCE_ID = ObservationSourceId.parse("ce30dafc-fadd-4cc4-b261-8a896d5a6d12")


def _climate_state(
    entity_id: str = "climate.main",
    *,
    available: bool = True,
    mode: HVACMode | None = HVACMode.HEAT,
    action: HVACAction | None = HVACAction.IDLE,
    target: float | None = None,
    low: float | None = None,
    high: float | None = None,
) -> NormalizedClimateState:
    return NormalizedClimateState(
        entity_id=entity_id,
        available=available,
        hvac_mode=mode,
        hvac_action=action,
        current_temperature_c=20.0 if available else None,
        target_temperature_c=target,
        target_low_c=low,
        target_high_c=high,
        current_humidity_pct=None,
        fan_mode=None,
        preset_mode=None,
        auxiliary_heat_state=ObservableBoolean.NOT_OBSERVABLE,
        context_id=None,
        last_changed=NOW,
        last_updated=NOW,
    )


def _aggregation(
    value: float | None,
    *,
    status: AggregationStatus = AggregationStatus.HEALTHY,
) -> SourceAggregationResult:
    return SourceAggregationResult(
        effective_value=value,
        spread=0.0 if value is not None else None,
        valid_source_ids=(SOURCE_ID,) if value is not None else (),
        contributing_source_ids=(SOURCE_ID,) if value is not None else (),
        fallback_source_id=None,
        excluded_observations=(),
        status=status,
        reasons=(
            ()
            if status is AggregationStatus.HEALTHY
            else (AggregationReason.BELOW_MINIMUM_VALID_SOURCES,)
        ),
        calculated_at=NOW,
    )


def _zone(
    thermostat_ids: tuple[str, ...],
    *,
    humidity_configured: bool,
    name: str = "Dining Room",
) -> ZoneConfig:
    return ZoneConfig(
        zone_id=ZONE_ID,
        name=name,
        thermostat_entity_ids=thermostat_ids,
        temperature_sources=(
            TemperatureSource(
                SOURCE_ID,
                "sensor.temperature",
                None,
                0.0,
                1.0,
                0,
                True,
            ),
        ),
        humidity_sources=(
            (
                HumiditySource(
                    HUMIDITY_SOURCE_ID,
                    "sensor.humidity",
                    None,
                    0.0,
                    1.0,
                    0,
                    True,
                ),
            )
            if humidity_configured
            else ()
        ),
        window_door_entity_ids=(),
        occupancy_entity_ids=(),
        stage_entity_ids=(),
        fan_entity_ids=(),
    )


def _make_entity(
    hass: HomeAssistant,
    thermostat_states: tuple[NormalizedClimateState, ...] = (_climate_state(),),
    *,
    temperature: float | None = 20.4,
    humidity: float | None = None,
    humidity_configured: bool = False,
    reconciling: bool = False,
    observation_enabled: bool = True,
    aggregation_status: AggregationStatus = AggregationStatus.HEALTHY,
) -> tuple[IntelligentClimateZoneClimateEntity, IntelligentClimateCoordinator]:
    thermostat_ids = tuple(state.entity_id for state in thermostat_states)
    zone = _zone(thermostat_ids, humidity_configured=humidity_configured)
    group = EquipmentGroupConfig(
        GROUP_ID,
        "Main Floor HVAC",
        EquipmentType.CONVENTIONAL,
        EquipmentRelationship.SINGLE_SYSTEM,
        tuple(
            ThermostatBinding(
                entity_id,
                (ThermostatRole.PRIMARY if index == 0 else ThermostatRole.SECONDARY),
            )
            for index, entity_id in enumerate(thermostat_ids)
        ),
        None,
    )
    configuration = EntryRuntimeConfiguration(
        group,
        (zone,),
        replace(DEFAULT_OPTIONS, observation_enabled=observation_enabled),
        RuntimeConfigurationState.CONFIGURED,
    )
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry-1",
        data={},
        version=1,
        minor_version=0,
        state=config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    )
    coordinator = IntelligentClimateCoordinator(
        hass,
        cast(IntelligentClimateConfigEntry, mock_entry),
        configuration,
        now_fn=lambda: NOW,
    )
    humidity_aggregation = (
        replace(_aggregation(humidity), valid_source_ids=(HUMIDITY_SOURCE_ID,))
        if humidity_configured
        else None
    )
    observation = ZoneObservation(
        ZONE_ID,
        (),
        (),
        _aggregation(temperature, status=aggregation_status),
        humidity_aggregation,
        thermostat_states,
        aggregation_status is not AggregationStatus.HEALTHY,
        any(not state.available for state in thermostat_states),
        NOW,
    )
    coordinator.async_set_updated_data(
        EntryObservationSnapshot(
            "entry-1",
            GROUP_ID,
            ControlState.RECONCILING if reconciling else ControlState.OBSERVING,
            reconciling,
            1,
            (),
            (observation,),
            NOW,
        )
    )
    entity = IntelligentClimateZoneClimateEntity(coordinator, zone)
    entity.hass = hass
    return entity, coordinator


def _current_temperature(
    entity: IntelligentClimateZoneClimateEntity,
) -> float | None:
    return entity.current_temperature


def _hvac_mode(entity: IntelligentClimateZoneClimateEntity) -> HVACMode | None:
    return entity.hvac_mode


def test_stable_identity_primary_name_device_and_empty_feature_mask(
    hass: HomeAssistant,
) -> None:
    entity, _ = _make_entity(hass)

    assert isinstance(entity, CoordinatorEntity)
    assert entity.should_poll is False
    assert entity.unique_id == f"{ZONE_ID}:zone"
    assert entity.name is None
    assert entity.has_entity_name is True
    assert entity.temperature_unit == UnitOfTemperature.CELSIUS
    assert entity.precision == 0.1
    assert entity.supported_features == ClimateEntityFeature(0)
    assert entity.device_info == {
        "identifiers": {(DOMAIN, str(ZONE_ID))},
        "manufacturer": NAME,
        "model": "Climate zone",
        "name": "Dining Room",
        "via_device": (DOMAIN, str(GROUP_ID)),
    }


@pytest.mark.parametrize(
    (
        "reconciling",
        "enabled",
        "temperature",
        "states",
        "status",
        "expected",
    ),
    [
        (False, True, 20.0, (_climate_state(),), AggregationStatus.HEALTHY, True),
        (True, True, 20.0, (_climate_state(),), AggregationStatus.HEALTHY, False),
        (False, False, None, (_climate_state(),), AggregationStatus.UNAVAILABLE, False),
        (False, True, None, (_climate_state(),), AggregationStatus.UNAVAILABLE, False),
        (
            False,
            True,
            20.0,
            (_climate_state(available=False),),
            AggregationStatus.HEALTHY,
            False,
        ),
        (
            False,
            True,
            20.0,
            (
                _climate_state("climate.one", available=False),
                _climate_state("climate.two"),
            ),
            AggregationStatus.HEALTHY,
            True,
        ),
        (False, True, 20.0, (_climate_state(),), AggregationStatus.DEGRADED, True),
    ],
)
def test_strict_availability_rules(
    hass: HomeAssistant,
    reconciling: bool,
    enabled: bool,
    temperature: float | None,
    states: tuple[NormalizedClimateState, ...],
    status: AggregationStatus,
    expected: bool,
) -> None:
    entity, _ = _make_entity(
        hass,
        states,
        temperature=temperature,
        reconciling=reconciling,
        observation_enabled=enabled,
        aggregation_status=status,
    )

    assert entity.available is expected


def test_missing_zone_and_failed_coordinator_are_unavailable_without_stale_value(
    hass: HomeAssistant,
) -> None:
    entity, coordinator = _make_entity(hass, temperature=20.5)
    assert entity.current_temperature == 20.5
    coordinator.async_set_updated_data(replace(coordinator.data, revision=2, zones=()))

    assert entity.available is False
    assert _current_temperature(entity) is None
    coordinator.last_update_success = False
    assert entity.available is False


@pytest.mark.parametrize(
    ("configured", "humidity", "expected"),
    [(True, 47.5, 47.5), (True, None, None), (False, 47.5, None)],
)
def test_humidity_requires_configuration_and_current_value(
    hass: HomeAssistant,
    configured: bool,
    humidity: float | None,
    expected: float | None,
) -> None:
    entity, _ = _make_entity(
        hass,
        humidity=humidity,
        humidity_configured=configured,
    )

    assert entity.current_humidity == expected


@pytest.mark.parametrize(
    ("states", "expected_mode", "expected_modes", "expected_action"),
    [
        ((_climate_state(),), HVACMode.HEAT, [HVACMode.HEAT], HVACAction.IDLE),
        (
            (
                _climate_state("climate.one", mode=HVACMode.COOL),
                _climate_state("climate.two", mode=HVACMode.COOL),
            ),
            HVACMode.COOL,
            [HVACMode.COOL],
            HVACAction.IDLE,
        ),
        (
            (
                _climate_state("climate.one", mode=HVACMode.HEAT),
                _climate_state("climate.two", mode=HVACMode.COOL),
            ),
            None,
            [],
            HVACAction.IDLE,
        ),
        (
            (
                _climate_state("climate.one", mode=None),
                _climate_state("climate.two"),
            ),
            None,
            [],
            HVACAction.IDLE,
        ),
        (
            (
                _climate_state(
                    "climate.one",
                    available=False,
                    mode=HVACMode.COOL,
                    action=HVACAction.COOLING,
                ),
                _climate_state("climate.two", action=HVACAction.HEATING),
            ),
            HVACMode.HEAT,
            [HVACMode.HEAT],
            HVACAction.HEATING,
        ),
        (
            (
                _climate_state("climate.one", action=HVACAction.HEATING),
                _climate_state("climate.two", action=HVACAction.COOLING),
            ),
            HVACMode.HEAT,
            [HVACMode.HEAT],
            None,
        ),
        (
            (
                _climate_state("climate.one", action=None),
                _climate_state("climate.two", action=HVACAction.HEATING),
            ),
            HVACMode.HEAT,
            [HVACMode.HEAT],
            None,
        ),
    ],
)
def test_mode_and_action_consensus(
    hass: HomeAssistant,
    states: tuple[NormalizedClimateState, ...],
    expected_mode: HVACMode | None,
    expected_modes: list[HVACMode],
    expected_action: HVACAction | None,
) -> None:
    entity, _ = _make_entity(hass, states)

    assert entity.hvac_mode is expected_mode
    assert entity.hvac_modes == expected_modes
    assert entity.hvac_action is expected_action


def test_mode_does_not_reuse_previous_consensus(hass: HomeAssistant) -> None:
    entity, coordinator = _make_entity(hass)
    assert entity.hvac_mode is HVACMode.HEAT
    prior = coordinator.data.zones[0]
    conflicting = replace(
        prior,
        thermostat_states=(
            _climate_state("climate.one", mode=HVACMode.HEAT),
            _climate_state("climate.two", mode=HVACMode.COOL),
        ),
    )
    coordinator.async_set_updated_data(
        replace(coordinator.data, revision=2, zones=(conflicting,))
    )

    assert _hvac_mode(entity) is None
    assert entity.hvac_modes == []


@pytest.mark.parametrize(
    ("states", "expected"),
    [
        ((_climate_state(target=21.0),), (21.0, None, None)),
        (
            (
                _climate_state("climate.one", target=21.0),
                _climate_state("climate.two", target=21.1),
            ),
            (21.0, None, None),
        ),
        (
            (
                _climate_state("climate.one", target=21.0),
                _climate_state("climate.two", target=21.1001),
            ),
            (None, None, None),
        ),
        ((_climate_state(target=None),), (None, None, None)),
        ((_climate_state(available=False, target=21.0),), (None, None, None)),
        ((_climate_state(low=18.0, high=24.0),), (None, 18.0, 24.0)),
        (
            (
                _climate_state("climate.one", low=18.0, high=24.0),
                _climate_state("climate.two", low=18.1, high=24.1),
            ),
            (None, 18.0, 24.0),
        ),
        (
            (
                _climate_state("climate.one", low=18.0, high=24.0),
                _climate_state("climate.two", low=18.1001, high=24.0),
            ),
            (None, None, None),
        ),
        (
            (
                _climate_state("climate.one", low=18.0, high=24.0),
                _climate_state("climate.two", low=18.0, high=24.1001),
            ),
            (None, None, None),
        ),
        ((_climate_state(low=18.0, high=None),), (None, None, None)),
        ((_climate_state(low=24.0, high=18.0),), (None, None, None)),
        (
            (
                _climate_state("climate.one", target=21.0),
                _climate_state("climate.two", low=18.0, high=24.0),
            ),
            (None, None, None),
        ),
        (
            (_climate_state(target=21.0, low=18.0, high=24.0),),
            (None, None, None),
        ),
    ],
)
def test_target_consensus_is_current_deterministic_and_exclusive(
    hass: HomeAssistant,
    states: tuple[NormalizedClimateState, ...],
    expected: tuple[float | None, float | None, float | None],
) -> None:
    entity, _ = _make_entity(hass, states)

    assert (
        entity.target_temperature,
        entity.target_temperature_low,
        entity.target_temperature_high,
    ) == expected


def test_target_serialization_uses_standard_names_and_display_units(
    hass: HomeAssistant,
) -> None:
    entity, _ = _make_entity(hass, (_climate_state(target=20.0),))

    assert entity.extra_state_attributes == {
        ClimateEntityStateAttribute.TEMPERATURE: 20.0
    }
    hass.config.units = US_CUSTOMARY_SYSTEM
    assert entity.extra_state_attributes == {
        ClimateEntityStateAttribute.TEMPERATURE: 68.0
    }

    range_entity, _ = _make_entity(
        hass,
        (_climate_state(low=18.0, high=24.0),),
    )
    assert range_entity.extra_state_attributes == {
        ClimateEntityStateAttribute.TARGET_TEMP_LOW: 64.4,
        ClimateEntityStateAttribute.TARGET_TEMP_HIGH: 75.2,
    }
    assert range_entity.target_temperature is None
    assert range_entity.supported_features == ClimateEntityFeature(0)


@pytest.mark.parametrize(
    ("method_name", "args", "kwargs"),
    [
        ("async_set_hvac_mode", (HVACMode.HEAT,), {}),
        ("async_set_temperature", (), {"temperature": 21.0}),
        ("async_set_humidity", (45,), {}),
        ("async_set_fan_mode", ("auto",), {}),
        ("async_set_preset_mode", ("eco",), {}),
        ("async_set_swing_mode", ("on",), {}),
        ("async_set_swing_horizontal_mode", ("on",), {}),
        ("async_turn_on", (), {}),
        ("async_turn_off", (), {}),
        ("async_toggle", (), {}),
    ],
)
async def test_every_async_setter_immediately_raises_translated_error(
    hass: HomeAssistant,
    method_name: str,
    args: tuple[object, ...],
    kwargs: dict[str, object],
) -> None:
    entity, coordinator = _make_entity(hass)
    snapshot = coordinator.data

    with (
        patch.object(hass, "async_add_executor_job") as executor_job,
        pytest.raises(ServiceValidationError) as raised,
    ):
        await getattr(entity, method_name)(*args, **kwargs)

    assert raised.value.translation_domain == DOMAIN
    assert raised.value.translation_key == "observation_only"
    assert coordinator.data is snapshot
    executor_job.assert_not_called()


def test_common_consensus_rejects_empty_or_missing_values(
    hass: HomeAssistant,
) -> None:
    entity, _ = _make_entity(
        hass,
        (_climate_state(available=False, mode=None, action=None),),
    )

    assert entity.hvac_mode is None
    assert entity.hvac_action is None


def test_target_helpers_fail_closed_for_nonfinite_values(
    hass: HomeAssistant,
) -> None:
    entity, _ = _make_entity(hass, (_climate_state(target=float("nan")),))

    assert entity.target_temperature is None
    assert entity.extra_state_attributes is None


def test_entity_update_path_is_coordinator_listener_only(
    hass: HomeAssistant,
) -> None:
    entity, _ = _make_entity(hass)

    with patch.object(entity, "async_write_ha_state") as write_state:
        entity._handle_coordinator_update()

    write_state.assert_called_once_with()
    assert not hasattr(entity, "update")
