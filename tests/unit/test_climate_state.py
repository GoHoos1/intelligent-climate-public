"""Test pure generic climate-state normalization."""

from __future__ import annotations

from datetime import UTC, datetime
from math import inf, nan

import pytest
from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODE,
    ATTR_HVAC_ACTION,
    ATTR_PRESET_MODE,
    ATTR_TARGET_TEMP_HIGH,
    ATTR_TARGET_TEMP_LOW,
)
from homeassistant.components.climate.const import HVACAction, HVACMode
from homeassistant.const import (
    ATTR_TEMPERATURE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import Context, State

from custom_components.intelligent_climate.climate_state import (
    normalize_climate_state,
)
from custom_components.intelligent_climate.models import (
    NormalizedClimateState,
    ObservableBoolean,
)

ENTITY_ID = "climate.main"
OBSERVED_AT = datetime(2026, 7, 23, 12, tzinfo=UTC)
LAST_CHANGED = datetime(2026, 7, 23, 11, tzinfo=UTC)
LAST_UPDATED = datetime(2026, 7, 23, 11, 30, tzinfo=UTC)


def _state(
    state: str = HVACMode.HEAT,
    attributes: dict[str, object] | None = None,
) -> State:
    return State(
        ENTITY_ID,
        state,
        attributes or {},
        last_changed=LAST_CHANGED,
        last_updated=LAST_UPDATED,
        context=Context(id="01K0TESTCONTEXT000000000000"),
    )


def _normalize(
    state: State | None,
    unit: str = UnitOfTemperature.CELSIUS,
) -> NormalizedClimateState:
    return normalize_climate_state(
        ENTITY_ID,
        state,
        observed_at=OBSERVED_AT,
        climate_temperature_unit=unit,
    )


def test_missing_state_is_fully_unavailable_without_timestamps() -> None:
    result = _normalize(None)

    assert result.available is False
    assert result.entity_id == ENTITY_ID
    assert result.hvac_mode is None
    assert result.current_temperature_c is None
    assert result.context_id is None
    assert result.last_changed is None
    assert result.last_updated is None
    assert result.auxiliary_heat_state is ObservableBoolean.NOT_OBSERVABLE


@pytest.mark.parametrize("sentinel", [STATE_UNKNOWN, STATE_UNAVAILABLE])
def test_sentinel_state_preserves_metadata_but_ignores_attributes(
    sentinel: str,
) -> None:
    state = _state(
        sentinel,
        {
            ATTR_CURRENT_TEMPERATURE: 99,
            ATTR_HVAC_ACTION: HVACAction.HEATING,
            ATTR_CURRENT_HUMIDITY: 50,
        },
    )

    result = _normalize(state)

    assert result.available is False
    assert result.current_temperature_c is None
    assert result.hvac_action is None
    assert result.current_humidity_pct is None
    assert result.context_id == state.context.id
    assert result.last_changed is LAST_CHANGED
    assert result.last_updated is LAST_UPDATED


def test_complete_available_state_normalizes_only_public_attributes() -> None:
    attributes: dict[str, object] = {
        ATTR_CURRENT_TEMPERATURE: 68,
        ATTR_TEMPERATURE: 70,
        ATTR_TARGET_TEMP_LOW: 65,
        ATTR_TARGET_TEMP_HIGH: 75,
        ATTR_CURRENT_HUMIDITY: "47.5",
        ATTR_HVAC_ACTION: HVACAction.HEATING,
        ATTR_FAN_MODE: " auto ",
        ATTR_PRESET_MODE: "eco",
        "vendor_aux_heat": True,
        "vendor_stage": 2,
    }
    original = dict(attributes)
    state = _state(HVACMode.HEAT_COOL, attributes)

    result = _normalize(state, UnitOfTemperature.FAHRENHEIT)

    assert result.available is True
    assert result.hvac_mode is HVACMode.HEAT_COOL
    assert result.hvac_action is HVACAction.HEATING
    assert result.current_temperature_c == pytest.approx(20)
    assert result.target_temperature_c == pytest.approx(21.111111)
    assert result.target_low_c == pytest.approx(18.333333)
    assert result.target_high_c == pytest.approx(23.888889)
    assert result.current_humidity_pct == 47.5
    assert result.fan_mode == "auto"
    assert result.preset_mode == "eco"
    assert result.auxiliary_heat_state is ObservableBoolean.NOT_OBSERVABLE
    assert result.context_id == state.context.id
    assert dict(state.attributes) == original


@pytest.mark.parametrize("mode", ["future_mode", "", "HEAT"])
def test_malformed_hvac_mode_does_not_make_state_unavailable(mode: str) -> None:
    result = _normalize(_state(mode))

    assert result.available is True
    assert result.hvac_mode is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (HVACAction.COOLING, HVACAction.COOLING),
        ("future_action", None),
        (1, None),
        (None, None),
    ],
)
def test_hvac_action_parsing_is_independent(
    value: object,
    expected: HVACAction | None,
) -> None:
    result = _normalize(_state(attributes={ATTR_HVAC_ACTION: value}))

    assert result.hvac_action is expected
    assert result.available is True


@pytest.mark.parametrize(
    "value",
    [None, True, "", "not-a-number", nan, inf, -inf, object()],
)
def test_malformed_individual_numeric_values_become_none(value: object) -> None:
    result = _normalize(
        _state(
            attributes={
                ATTR_CURRENT_TEMPERATURE: value,
                ATTR_TEMPERATURE: value,
                ATTR_TARGET_TEMP_LOW: value,
                ATTR_TARGET_TEMP_HIGH: value,
                ATTR_CURRENT_HUMIDITY: value,
            }
        )
    )

    assert result.available is True
    assert result.current_temperature_c is None
    assert result.target_temperature_c is None
    assert result.target_low_c is None
    assert result.target_high_c is None
    assert result.current_humidity_pct is None


def test_celsius_values_remain_celsius_and_invalid_unit_fails_temperatures() -> None:
    state = _state(attributes={ATTR_CURRENT_TEMPERATURE: 20.25})

    assert _normalize(state).current_temperature_c == 20.25
    assert _normalize(state, "future_unit").current_temperature_c is None


@pytest.mark.parametrize("value", [None, "", "   ", 3, False])
def test_fan_and_preset_require_nonempty_strings(value: object) -> None:
    result = _normalize(
        _state(attributes={ATTR_FAN_MODE: value, ATTR_PRESET_MODE: value})
    )

    assert result.fan_mode is None
    assert result.preset_mode is None


def test_wrong_entity_and_naive_clock_are_rejected() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        normalize_climate_state(
            ENTITY_ID,
            None,
            observed_at=datetime(2026, 7, 23),
            climate_temperature_unit=UnitOfTemperature.CELSIUS,
        )
    with pytest.raises(ValueError, match="must match"):
        _normalize(State("climate.other", HVACMode.OFF))
