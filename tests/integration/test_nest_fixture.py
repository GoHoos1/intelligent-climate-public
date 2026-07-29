"""Verify the sanitized supplied Nest fixture through public HA contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.core import State

from custom_components.intelligent_climate.capability import (
    discover_thermostat_capabilities,
)
from custom_components.intelligent_climate.climate_state import (
    normalize_climate_state,
)
from custom_components.intelligent_climate.models import (
    ObservableBoolean,
    ThermostatCapabilityDiscoveryStatus,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "nest_cool_idle.json"
OBSERVED_AT = datetime(2026, 7, 29, 12, tzinfo=UTC)


def test_supplied_nest_cool_idle_fixture_is_normalized_conservatively() -> None:
    """Cool/idle Nest data exposes no invented stage or auxiliary status."""
    fixture = json.loads(FIXTURE.read_text())
    climate = fixture["climate_state"]
    expected = fixture["expected"]
    state = State(
        climate["entity_id"],
        climate["state"],
        climate["attributes"],
        last_changed=OBSERVED_AT,
        last_reported=OBSERVED_AT,
        last_updated=OBSERVED_AT,
    )

    normalized = normalize_climate_state(
        climate["entity_id"],
        state,
        observed_at=OBSERVED_AT,
        climate_temperature_unit=climate["temperature_unit"],
    )
    discovery = discover_thermostat_capabilities(
        climate["entity_id"],
        state,
        discovered_at=OBSERVED_AT,
    )

    assert normalized.hvac_mode is HVACMode(expected["hvac_mode"])
    assert normalized.hvac_action is HVACAction(expected["hvac_action"])
    assert normalized.current_temperature_c == pytest.approx(
        expected["current_temperature_c"]
    )
    assert normalized.current_humidity_pct == expected["current_humidity_pct"]
    assert normalized.target_temperature_c == expected["target_temperature_c"]
    assert normalized.auxiliary_heat_state is ObservableBoolean.NOT_OBSERVABLE
    assert discovery.status is ThermostatCapabilityDiscoveryStatus.COMPLETE
    capabilities = discovery.capabilities
    assert capabilities is not None
    assert capabilities.hvac_modes == {
        HVACMode.HEAT,
        HVACMode.COOL,
        HVACMode.HEAT_COOL,
        HVACMode.OFF,
    }
    assert capabilities.stage_observable is expected["stage_observable"]
    assert (
        capabilities.auxiliary_heat_observable is expected["auxiliary_heat_observable"]
    )
