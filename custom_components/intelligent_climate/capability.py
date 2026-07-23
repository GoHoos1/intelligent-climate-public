"""Pure thermostat capability discovery from public Home Assistant state."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODES,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODES,
)
from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import State

from .models.capability import (
    ThermostatCapabilities,
    ThermostatCapabilityDiscovery,
    ThermostatCapabilityDiscoveryStatus,
)

_MISSING = object()
_KNOWN_FEATURE_MASK = sum(int(feature) for feature in ClimateEntityFeature)


def discover_thermostat_capabilities(
    entity_id: str,
    state: State | None,
    *,
    discovered_at: datetime,
) -> ThermostatCapabilityDiscovery:
    """Discover one thermostat's capabilities without side effects."""
    if discovered_at.tzinfo is None or discovered_at.utcoffset() is None:
        raise ValueError("discovered_at must be timezone-aware")

    if state is None or state.state in {STATE_UNKNOWN, STATE_UNAVAILABLE}:
        return ThermostatCapabilityDiscovery(
            status=ThermostatCapabilityDiscoveryStatus.UNAVAILABLE,
            capabilities=None,
        )

    attributes = state.attributes
    partial = False

    hvac_modes, hvac_modes_valid = _normalize_hvac_modes(
        attributes.get(ATTR_HVAC_MODES, _MISSING)
    )
    if not hvac_modes_valid or not hvac_modes:
        partial = True

    supported_features, supported_features_valid = _normalize_supported_features(
        attributes.get(ATTR_SUPPORTED_FEATURES, _MISSING)
    )
    if not supported_features_valid:
        partial = True

    target_temperature = bool(
        supported_features & ClimateEntityFeature.TARGET_TEMPERATURE
    )
    target_temperature_range = bool(
        supported_features & ClimateEntityFeature.TARGET_TEMPERATURE_RANGE
    )
    if target_temperature and target_temperature_range:
        partial = True

    fan_modes, fan_modes_valid, fan_modes_present = _normalize_string_modes(
        attributes.get(ATTR_FAN_MODES, _MISSING)
    )
    fan_feature = bool(supported_features & ClimateEntityFeature.FAN_MODE)
    if not fan_modes_valid or fan_modes_present != fan_feature:
        partial = True
    if fan_feature and not fan_modes:
        partial = True

    preset_modes, preset_modes_valid, preset_modes_present = _normalize_string_modes(
        attributes.get(ATTR_PRESET_MODES, _MISSING)
    )
    preset_feature = bool(supported_features & ClimateEntityFeature.PRESET_MODE)
    if not preset_modes_valid or preset_modes_present != preset_feature:
        partial = True
    if preset_feature and not preset_modes:
        partial = True

    capabilities = ThermostatCapabilities(
        entity_id=entity_id,
        hvac_modes=hvac_modes,
        supported_features=supported_features,
        target_temperature=target_temperature,
        target_temperature_range=target_temperature_range,
        fan_modes=fan_modes,
        preset_modes=preset_modes,
        current_temperature_available=(
            ATTR_CURRENT_TEMPERATURE in attributes
            and attributes[ATTR_CURRENT_TEMPERATURE] is not None
        ),
        current_humidity_available=(
            ATTR_CURRENT_HUMIDITY in attributes
            and attributes[ATTR_CURRENT_HUMIDITY] is not None
        ),
        auxiliary_heat_observable=False,
        stage_observable=False,
        discovered_at=discovered_at,
    )
    return ThermostatCapabilityDiscovery(
        status=(
            ThermostatCapabilityDiscoveryStatus.PARTIAL
            if partial
            else ThermostatCapabilityDiscoveryStatus.COMPLETE
        ),
        capabilities=capabilities,
    )


def _normalize_hvac_modes(value: object) -> tuple[frozenset[HVACMode], bool]:
    """Normalize the public HVAC-mode list and report whether it was valid."""
    if not isinstance(value, list | tuple):
        return frozenset(), False

    modes: set[HVACMode] = set()
    valid = True
    for item in value:
        if not isinstance(item, str):
            valid = False
            continue
        try:
            mode = HVACMode(item)
        except ValueError:
            valid = False
            continue
        if mode in modes:
            valid = False
        modes.add(mode)
    return frozenset(modes), valid


def _normalize_supported_features(
    value: object,
) -> tuple[ClimateEntityFeature, bool]:
    """Normalize the public feature mask without dropping future bits."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return ClimateEntityFeature(0), False

    features = ClimateEntityFeature(value)
    has_unknown_bits = bool(value & ~_KNOWN_FEATURE_MASK)
    return features, not has_unknown_bits


def _normalize_string_modes(value: object) -> tuple[tuple[str, ...], bool, bool]:
    """Normalize a public fan/preset list while preserving published order."""
    if value is _MISSING:
        return (), True, False
    if not isinstance(value, list | tuple):
        return (), False, True

    modes: list[str] = []
    seen: set[str] = set()
    valid = True
    for item in value:
        if not isinstance(item, str) or not item:
            valid = False
            continue
        if item in seen:
            valid = False
            continue
        seen.add(item)
        modes.append(item)
    return tuple(modes), valid, True
