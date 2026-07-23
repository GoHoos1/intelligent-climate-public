"""Pure normalization of public generic Home Assistant climate state."""

from __future__ import annotations

import math
from datetime import datetime

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
from homeassistant.core import State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_conversion import TemperatureConverter

from .models.runtime import NormalizedClimateState, ObservableBoolean


def normalize_climate_state(
    entity_id: str,
    state: State | None,
    *,
    observed_at: datetime,
    climate_temperature_unit: str,
) -> NormalizedClimateState:
    """Normalize one supplied public climate state without side effects."""
    _require_aware(observed_at)
    if state is not None and state.entity_id != entity_id:
        raise ValueError("state.entity_id must match entity_id")

    if state is None:
        return _unavailable(entity_id)
    if state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
        return _unavailable(
            entity_id,
            context_id=state.context.id,
            last_changed=state.last_changed,
            last_updated=state.last_updated,
        )

    attributes = state.attributes
    return NormalizedClimateState(
        entity_id=entity_id,
        available=True,
        hvac_mode=_hvac_mode_or_none(state.state),
        hvac_action=_hvac_action_or_none(attributes.get(ATTR_HVAC_ACTION)),
        current_temperature_c=_temperature_or_none(
            attributes.get(ATTR_CURRENT_TEMPERATURE),
            climate_temperature_unit,
        ),
        target_temperature_c=_temperature_or_none(
            attributes.get(ATTR_TEMPERATURE),
            climate_temperature_unit,
        ),
        target_low_c=_temperature_or_none(
            attributes.get(ATTR_TARGET_TEMP_LOW),
            climate_temperature_unit,
        ),
        target_high_c=_temperature_or_none(
            attributes.get(ATTR_TARGET_TEMP_HIGH),
            climate_temperature_unit,
        ),
        current_humidity_pct=_finite_or_none(attributes.get(ATTR_CURRENT_HUMIDITY)),
        fan_mode=_nonempty_string_or_none(attributes.get(ATTR_FAN_MODE)),
        preset_mode=_nonempty_string_or_none(attributes.get(ATTR_PRESET_MODE)),
        auxiliary_heat_state=ObservableBoolean.NOT_OBSERVABLE,
        context_id=state.context.id,
        last_changed=state.last_changed,
        last_updated=state.last_updated,
    )


def _unavailable(
    entity_id: str,
    *,
    context_id: str | None = None,
    last_changed: datetime | None = None,
    last_updated: datetime | None = None,
) -> NormalizedClimateState:
    return NormalizedClimateState(
        entity_id=entity_id,
        available=False,
        hvac_mode=None,
        hvac_action=None,
        current_temperature_c=None,
        target_temperature_c=None,
        target_low_c=None,
        target_high_c=None,
        current_humidity_pct=None,
        fan_mode=None,
        preset_mode=None,
        auxiliary_heat_state=ObservableBoolean.NOT_OBSERVABLE,
        context_id=context_id,
        last_changed=last_changed,
        last_updated=last_updated,
    )


def _hvac_mode_or_none(value: object) -> HVACMode | None:
    if not isinstance(value, str):
        return None
    try:
        return HVACMode(value)
    except ValueError:
        return None


def _hvac_action_or_none(value: object) -> HVACAction | None:
    if not isinstance(value, str):
        return None
    try:
        return HVACAction(value)
    except ValueError:
        return None


def _temperature_or_none(value: object, unit: str) -> float | None:
    numeric = _finite_or_none(value)
    if numeric is None or unit not in TemperatureConverter.VALID_UNITS:
        return None
    try:
        converted = TemperatureConverter.convert(
            numeric,
            unit,
            UnitOfTemperature.CELSIUS,
        )
    except HomeAssistantError:
        return None
    return converted if math.isfinite(converted) else None


def _finite_or_none(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        try:
            numeric = float(value)
        except OverflowError:
            return None
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            numeric = float(stripped)
        except ValueError:
            return None
    else:
        return None
    return numeric if math.isfinite(numeric) else None


def _nonempty_string_or_none(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
