"""Immutable thermostat capability discovery models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.components.climate.const import (
        ClimateEntityFeature,
        HVACMode,
    )


class ThermostatCapabilityDiscoveryStatus(StrEnum):
    """Quality of one public-state thermostat capability discovery."""

    COMPLETE = "complete"
    PARTIAL = "partial"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class ThermostatCapabilities:
    """Capabilities observed from one available thermostat's public state."""

    entity_id: str
    hvac_modes: frozenset[HVACMode]
    supported_features: ClimateEntityFeature
    target_temperature: bool
    target_temperature_range: bool
    fan_modes: tuple[str, ...]
    preset_modes: tuple[str, ...]
    current_temperature_available: bool
    current_humidity_available: bool
    auxiliary_heat_observable: bool
    stage_observable: bool
    discovered_at: datetime


@dataclass(frozen=True, slots=True)
class ThermostatCapabilityDiscovery:
    """Capability discovery result, including explicit unavailability."""

    status: ThermostatCapabilityDiscoveryStatus
    capabilities: ThermostatCapabilities | None
