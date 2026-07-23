"""Immutable runtime configuration and observation snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from homeassistant.components.climate.const import HVACAction, HVACMode

from .aggregation import SourceAggregationResult
from .capability import ThermostatCapabilityDiscovery
from .identifiers import EquipmentGroupId, ObservationSourceId, ZoneId
from .observation import SourceObservation
from .schema import (
    ControlState,
    EquipmentGroupConfig,
    IntegrationOptions,
    ZoneConfig,
)


class ObservableBoolean(StrEnum):
    """A boolean observation that can explicitly be unavailable."""

    TRUE = "true"
    FALSE = "false"
    NOT_OBSERVABLE = "not_observable"


@dataclass(frozen=True, slots=True)
class EntryRuntimeConfiguration:
    """One fully decoded config-entry hierarchy used by runtime code."""

    equipment_group: EquipmentGroupConfig
    zones: tuple[ZoneConfig, ...]
    options: IntegrationOptions
    transitional_empty_skeleton: bool


@dataclass(frozen=True, slots=True)
class NormalizedClimateState:
    """Public generic climate state normalized for observation."""

    entity_id: str
    available: bool
    hvac_mode: HVACMode | None
    hvac_action: HVACAction | None
    current_temperature_c: float | None
    target_temperature_c: float | None
    target_low_c: float | None
    target_high_c: float | None
    current_humidity_pct: float | None
    fan_mode: str | None
    preset_mode: str | None
    auxiliary_heat_state: ObservableBoolean
    context_id: str | None
    last_changed: datetime | None
    last_updated: datetime | None


@dataclass(frozen=True, slots=True)
class ThermostatRuntimeSnapshot:
    """One thermostat's public state and capability-discovery result."""

    entity_id: str
    state: NormalizedClimateState
    capability_discovery: ThermostatCapabilityDiscovery

    def __post_init__(self) -> None:
        """Require wrapper and normalized-state identity to agree."""
        if self.entity_id != self.state.entity_id:
            raise ValueError("thermostat snapshot entity IDs must match")


@dataclass(frozen=True, slots=True)
class ZoneObservation:
    """One complete immutable observation of a configured zone."""

    zone_id: ZoneId
    temperature_observations: tuple[SourceObservation[float], ...]
    humidity_observations: tuple[SourceObservation[float], ...]
    temperature_aggregation: SourceAggregationResult
    humidity_aggregation: SourceAggregationResult | None
    thermostat_states: tuple[NormalizedClimateState, ...]
    sensor_data_degraded: bool
    thermostat_data_degraded: bool
    calculated_at: datetime

    def __post_init__(self) -> None:
        """Reject ambiguous snapshot timestamps."""
        _require_aware(self.calculated_at, "calculated_at")
        if self.temperature_aggregation.calculated_at != self.calculated_at:
            raise ValueError("temperature aggregation timestamp must match zone")
        if (
            self.humidity_aggregation is not None
            and self.humidity_aggregation.calculated_at != self.calculated_at
        ):
            raise ValueError("humidity aggregation timestamp must match zone")

    @property
    def effective_temperature_c(self) -> float | None:
        """Return the current effective Celsius temperature."""
        return self.temperature_aggregation.effective_value

    @property
    def effective_humidity_pct(self) -> float | None:
        """Return the current effective humidity percentage."""
        if self.humidity_aggregation is None:
            return None
        return self.humidity_aggregation.effective_value

    @property
    def temperature_spread_c(self) -> float | None:
        """Return the spread among currently valid temperature sources."""
        return self.temperature_aggregation.spread

    @property
    def valid_temperature_source_ids(self) -> tuple[ObservationSourceId, ...]:
        """Return valid temperature sources in configured order."""
        return self.temperature_aggregation.valid_source_ids

    @property
    def valid_humidity_source_ids(self) -> tuple[ObservationSourceId, ...]:
        """Return valid humidity sources in configured order."""
        if self.humidity_aggregation is None:
            return ()
        return self.humidity_aggregation.valid_source_ids

    @property
    def excluded_sources(self) -> tuple[SourceObservation[float], ...]:
        """Return temperature then humidity exclusions in configured order."""
        humidity_exclusions = (
            ()
            if self.humidity_aggregation is None
            else self.humidity_aggregation.excluded_observations
        )
        return (
            *self.temperature_aggregation.excluded_observations,
            *humidity_exclusions,
        )


@dataclass(frozen=True, slots=True)
class EntryObservationSnapshot:
    """The single immutable observation published for a config entry."""

    entry_id: str
    equipment_group_id: EquipmentGroupId
    control_state: ControlState
    reconciling: bool
    revision: int
    thermostats: tuple[ThermostatRuntimeSnapshot, ...]
    zones: tuple[ZoneObservation, ...]
    calculated_at: datetime

    def __post_init__(self) -> None:
        """Validate public revision and timestamp invariants."""
        if self.revision < 1:
            raise ValueError("revision must be positive")
        _require_aware(self.calculated_at, "calculated_at")


def _require_aware(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
