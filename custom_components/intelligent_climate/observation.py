"""Pure source extraction and Task 7 value normalization."""

from __future__ import annotations

import math
from datetime import datetime

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
)
from homeassistant.const import (
    ATTR_RESTORED,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.unit_conversion import TemperatureConverter

from .models import HumiditySource, ObservationSourceId, TemperatureSource
from .models.observation import (
    ExclusionReason,
    SourceObservation,
    SourceQuality,
)


def observe_temperature_source(
    source: TemperatureSource,
    state: State | None,
    *,
    observed_at: datetime,
    climate_temperature_unit: str | None = None,
) -> SourceObservation[float]:
    """Normalize one supplied public temperature state to Celsius.

    State-based sensors publish their unit on the state. Home Assistant climate
    current-temperature values are already serialized into the configured
    temperature unit, which a future caller must supply explicitly.

    The boundary deliberately ignores ``source.enabled``. A future orchestration
    layer decides which configured sources to invoke.
    """
    prepared = _prepare_source(
        source.source_id,
        source.entity_id,
        source.attribute,
        state,
        observed_at,
    )
    if isinstance(prepared, SourceObservation):
        return prepared
    raw_value, source_last_reported, restored = prepared
    assert state is not None

    parsed = _parse_numeric(raw_value)
    if isinstance(parsed, SourceQuality):
        return _excluded(
            source.source_id,
            raw_value,
            observed_at,
            source_last_reported,
            parsed,
            restored,
        )

    if source.attribute is None:
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
    elif source.attribute == ATTR_CURRENT_TEMPERATURE:
        unit = climate_temperature_unit
    else:
        unit = None
    if not isinstance(unit, str) or unit not in TemperatureConverter.VALID_UNITS:
        return _excluded(
            source.source_id,
            raw_value,
            observed_at,
            source_last_reported,
            SourceQuality.UNIT_UNSUPPORTED,
            restored,
        )

    try:
        normalized = TemperatureConverter.convert(
            parsed,
            unit,
            UnitOfTemperature.CELSIUS,
        )
    except HomeAssistantError:
        return _excluded(
            source.source_id,
            raw_value,
            observed_at,
            source_last_reported,
            SourceQuality.UNIT_UNSUPPORTED,
            restored,
        )

    normalized += source.offset_c
    if not math.isfinite(normalized):
        return _excluded(
            source.source_id,
            raw_value,
            observed_at,
            source_last_reported,
            SourceQuality.NON_FINITE,
            restored,
        )
    return _valid(
        source.source_id,
        raw_value,
        normalized,
        observed_at,
        source_last_reported,
        restored,
    )


def observe_humidity_source(
    source: HumiditySource,
    state: State | None,
    *,
    observed_at: datetime,
) -> SourceObservation[float]:
    """Normalize one supplied public humidity state to percentage points.

    State-based sensors must publish the public percent unit. The generic
    climate ``current_humidity`` attribute is already expressed in percentage
    points by Home Assistant's public climate contract.
    """
    prepared = _prepare_source(
        source.source_id,
        source.entity_id,
        source.attribute,
        state,
        observed_at,
    )
    if isinstance(prepared, SourceObservation):
        return prepared
    raw_value, source_last_reported, restored = prepared
    assert state is not None

    parsed = _parse_numeric(raw_value)
    if isinstance(parsed, SourceQuality):
        return _excluded(
            source.source_id,
            raw_value,
            observed_at,
            source_last_reported,
            parsed,
            restored,
        )

    if source.attribute is None:
        unit = state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        unit_supported = unit == PERCENTAGE
    else:
        unit_supported = source.attribute == ATTR_CURRENT_HUMIDITY
    if not unit_supported:
        return _excluded(
            source.source_id,
            raw_value,
            observed_at,
            source_last_reported,
            SourceQuality.UNIT_UNSUPPORTED,
            restored,
        )

    normalized = parsed + source.offset_pct
    if not math.isfinite(normalized):
        return _excluded(
            source.source_id,
            raw_value,
            observed_at,
            source_last_reported,
            SourceQuality.NON_FINITE,
            restored,
        )
    return _valid(
        source.source_id,
        raw_value,
        normalized,
        observed_at,
        source_last_reported,
        restored,
    )


def _prepare_source(
    source_id: ObservationSourceId,
    entity_id: str,
    attribute: str | None,
    state: State | None,
    observed_at: datetime,
) -> SourceObservation[float] | tuple[object, datetime, bool]:
    """Validate invocation invariants and select the configured raw value."""
    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise ValueError("observed_at must be timezone-aware")
    if state is None:
        return _excluded(
            source_id,
            None,
            observed_at,
            None,
            SourceQuality.UNAVAILABLE,
            False,
        )
    if state.entity_id != entity_id:
        raise ValueError("state.entity_id must match source.entity_id")

    restored = state.attributes.get(ATTR_RESTORED) is True
    if state.state == STATE_UNAVAILABLE:
        return _excluded(
            source_id,
            STATE_UNAVAILABLE,
            observed_at,
            state.last_reported,
            SourceQuality.UNAVAILABLE,
            restored,
        )
    if state.state == STATE_UNKNOWN:
        return _excluded(
            source_id,
            STATE_UNKNOWN,
            observed_at,
            state.last_reported,
            SourceQuality.UNKNOWN,
            restored,
        )

    raw_value: object = (
        state.state if attribute is None else state.attributes.get(attribute)
    )
    if raw_value is None:
        return _excluded(
            source_id,
            None,
            observed_at,
            state.last_reported,
            SourceQuality.UNKNOWN,
            restored,
        )
    return raw_value, state.last_reported, restored


def _parse_numeric(value: object) -> float | SourceQuality:
    """Parse integers, floats, and stripped Python float-literal strings.

    Boolean values are deliberately not numeric. Strings use Python's strict
    ``float`` parser after ordinary surrounding whitespace is removed; empty
    strings and any other object type are rejected.
    """
    if isinstance(value, bool):
        return SourceQuality.NON_NUMERIC
    if isinstance(value, int | float):
        try:
            parsed = float(value)
        except OverflowError:
            return SourceQuality.NON_FINITE
    elif isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return SourceQuality.NON_NUMERIC
        try:
            parsed = float(stripped)
        except ValueError:
            return SourceQuality.NON_NUMERIC
    else:
        return SourceQuality.NON_NUMERIC
    if not math.isfinite(parsed):
        return SourceQuality.NON_FINITE
    return parsed


def _valid(
    source_id: ObservationSourceId,
    raw_value: object,
    normalized_value: float,
    observed_at: datetime,
    source_last_reported: datetime,
    restored: bool,
) -> SourceObservation[float]:
    return SourceObservation(
        source_id=source_id,
        raw_value=raw_value,
        normalized_value=normalized_value,
        observed_at=observed_at,
        source_last_reported=source_last_reported,
        quality=SourceQuality.VALID,
        exclusion_reason=None,
        restored=restored,
    )


def _excluded(
    source_id: ObservationSourceId,
    raw_value: object,
    observed_at: datetime,
    source_last_reported: datetime | None,
    quality: SourceQuality,
    restored: bool,
) -> SourceObservation[float]:
    if quality is SourceQuality.VALID:
        raise ValueError("excluded observation quality must be nonvalid")
    return SourceObservation(
        source_id=source_id,
        raw_value=raw_value,
        normalized_value=None,
        observed_at=observed_at,
        source_last_reported=source_last_reported,
        quality=quality,
        exclusion_reason=ExclusionReason(quality.value),
        restored=restored,
    )
