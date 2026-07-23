"""Test immutable Task 10 runtime models."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime

import pytest
from homeassistant.components.climate.const import HVACMode

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
    NormalizedClimateState,
    ObservableBoolean,
    SourceAggregationResult,
    ThermostatBinding,
    ThermostatRole,
    ZoneId,
    ZoneObservation,
)

NOW = datetime(2026, 7, 23, 12, tzinfo=UTC)
GROUP_ID = EquipmentGroupId.parse("b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3")
ZONE_ID = ZoneId.parse("99246285-6f02-4e8a-94ed-bdfd4a5e62c4")


def _aggregation(
    value: float | None = 20.0,
    *,
    status: AggregationStatus = AggregationStatus.HEALTHY,
) -> SourceAggregationResult:
    return SourceAggregationResult(
        effective_value=value,
        spread=0.5 if value is not None else None,
        valid_source_ids=(),
        contributing_source_ids=(),
        fallback_source_id=None,
        excluded_observations=(),
        status=status,
        reasons=(
            ()
            if status is AggregationStatus.HEALTHY
            else (AggregationReason.NO_VALID_SOURCES,)
        ),
        calculated_at=NOW,
    )


def _climate(entity_id: str) -> NormalizedClimateState:
    return NormalizedClimateState(
        entity_id=entity_id,
        available=True,
        hvac_mode=HVACMode.HEAT,
        hvac_action=None,
        current_temperature_c=20.0,
        target_temperature_c=None,
        target_low_c=None,
        target_high_c=None,
        current_humidity_pct=None,
        fan_mode=None,
        preset_mode=None,
        auxiliary_heat_state=ObservableBoolean.NOT_OBSERVABLE,
        context_id=None,
        last_changed=NOW,
        last_updated=NOW,
    )


def test_runtime_configuration_and_snapshot_models_are_frozen_and_slotted() -> None:
    group = EquipmentGroupConfig(
        equipment_group_id=GROUP_ID,
        name="Main",
        equipment_type=EquipmentType.CONVENTIONAL,
        relationship=EquipmentRelationship.SINGLE_SYSTEM,
        thermostats=(ThermostatBinding("climate.main", ThermostatRole.PRIMARY),),
        shared_policy=None,
    )
    runtime = EntryRuntimeConfiguration(group, (), DEFAULT_OPTIONS, False)

    assert "__dict__" not in runtime.__slots__
    with pytest.raises(FrozenInstanceError):
        runtime.transitional_empty_skeleton = True  # type: ignore[misc]


def test_zone_convenience_properties_derive_from_aggregations() -> None:
    temperature = _aggregation(20.5)
    humidity = replace(_aggregation(47.25), spread=3.0)
    zone = ZoneObservation(
        zone_id=ZONE_ID,
        temperature_observations=(),
        humidity_observations=(),
        temperature_aggregation=temperature,
        humidity_aggregation=humidity,
        thermostat_states=(_climate("climate.main"),),
        sensor_data_degraded=False,
        thermostat_data_degraded=False,
        calculated_at=NOW,
    )

    assert zone.effective_temperature_c == 20.5
    assert zone.effective_humidity_pct == 47.25
    assert zone.temperature_spread_c == 0.5
    assert zone.valid_temperature_source_ids == ()
    assert zone.valid_humidity_source_ids == ()
    assert zone.excluded_sources == ()
    assert "__dict__" not in zone.__slots__
    with pytest.raises(FrozenInstanceError):
        zone.sensor_data_degraded = True  # type: ignore[misc]


def test_optional_humidity_is_absent_without_fabricated_degradation() -> None:
    zone = ZoneObservation(
        zone_id=ZONE_ID,
        temperature_observations=(),
        humidity_observations=(),
        temperature_aggregation=_aggregation(),
        humidity_aggregation=None,
        thermostat_states=(),
        sensor_data_degraded=False,
        thermostat_data_degraded=False,
        calculated_at=NOW,
    )

    assert zone.effective_humidity_pct is None
    assert zone.valid_humidity_source_ids == ()
    assert zone.sensor_data_degraded is False


def test_entry_snapshot_preserves_configured_tuple_order_and_revision() -> None:
    first = ZoneObservation(
        ZONE_ID,
        (),
        (),
        _aggregation(),
        None,
        (),
        False,
        False,
        NOW,
    )
    second = replace(
        first,
        zone_id=ZoneId.parse("7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"),
    )
    snapshot = EntryObservationSnapshot(
        entry_id="entry-1",
        equipment_group_id=GROUP_ID,
        control_state=ControlState.RECONCILING,
        reconciling=True,
        revision=1,
        thermostats=(),
        zones=(first, second),
        calculated_at=NOW,
    )
    next_snapshot = replace(snapshot, revision=2, zones=(replace(first), second))

    assert snapshot.revision == 1
    assert tuple(zone.zone_id for zone in snapshot.zones) == (
        first.zone_id,
        second.zone_id,
    )
    assert next_snapshot.revision == 2
    assert snapshot.zones[0] is first
    assert next_snapshot.zones[1] is second


def test_runtime_models_reject_mismatched_or_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timestamp must match"):
        ZoneObservation(
            ZONE_ID,
            (),
            (),
            replace(_aggregation(), calculated_at=datetime(2026, 7, 23, tzinfo=UTC)),
            None,
            (),
            False,
            False,
            NOW,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        EntryObservationSnapshot(
            "entry",
            GROUP_ID,
            ControlState.OBSERVING,
            False,
            1,
            (),
            (),
            datetime(2026, 7, 23),
        )
    with pytest.raises(ValueError, match="positive"):
        EntryObservationSnapshot(
            "entry",
            GROUP_ID,
            ControlState.OBSERVING,
            False,
            0,
            (),
            (),
            NOW,
        )
