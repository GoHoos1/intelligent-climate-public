"""Test public-state-only thermostat capability discovery."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from typing import Any

import pytest

pytest.importorskip("homeassistant")

from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_FAN_MODES,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
    ATTR_PRESET_MODES,
)
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import (
    ATTR_SUPPORTED_FEATURES,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import State

from custom_components.intelligent_climate.capability import (
    discover_thermostat_capabilities,
)
from custom_components.intelligent_climate.models import (
    ThermostatCapabilityDiscovery,
    ThermostatCapabilityDiscoveryStatus,
)

ENTITY_ID = "climate.generic_thermostat"
DISCOVERED_AT = datetime(2026, 7, 22, 14, 30, tzinfo=UTC)


def _attributes(
    *,
    features: int | ClimateEntityFeature = ClimateEntityFeature.TARGET_TEMPERATURE,
) -> dict[str, Any]:
    return {
        ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL],
        ATTR_SUPPORTED_FEATURES: features,
    }


def _state(
    attributes: dict[str, Any],
    *,
    state: str = HVACMode.HEAT,
) -> State:
    return State(
        ENTITY_ID,
        state,
        attributes,
        last_changed=DISCOVERED_AT,
        last_reported=DISCOVERED_AT,
        last_updated=DISCOVERED_AT,
    )


def _discover(attributes: dict[str, Any]) -> ThermostatCapabilityDiscovery:
    return discover_thermostat_capabilities(
        ENTITY_ID,
        _state(attributes),
        discovered_at=DISCOVERED_AT,
    )


def test_complete_generic_climate_capabilities_are_normalized_and_immutable() -> None:
    """Test a complete public climate fixture produces immutable capabilities."""
    features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.PRESET_MODE
    )
    attributes = _attributes(features=features)
    attributes.update(
        {
            ATTR_FAN_MODES: ["auto", "low", "high"],
            ATTR_PRESET_MODES: ["none", "eco"],
            ATTR_CURRENT_TEMPERATURE: 0,
            ATTR_CURRENT_HUMIDITY: 50,
        }
    )

    discovery = _discover(attributes)

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.COMPLETE
    capabilities = discovery.capabilities
    assert capabilities is not None
    assert capabilities.entity_id == ENTITY_ID
    assert capabilities.hvac_modes == frozenset(
        {HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL}
    )
    assert capabilities.supported_features == features
    assert capabilities.target_temperature is True
    assert capabilities.target_temperature_range is False
    assert capabilities.fan_modes == ("auto", "low", "high")
    assert capabilities.preset_modes == ("none", "eco")
    assert capabilities.current_temperature_available is True
    assert capabilities.current_humidity_available is True
    assert capabilities.auxiliary_heat_observable is False
    assert capabilities.stage_observable is False
    assert capabilities.discovered_at is DISCOVERED_AT
    with pytest.raises(FrozenInstanceError):
        discovery.status = ThermostatCapabilityDiscoveryStatus.PARTIAL  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        capabilities.entity_id = "climate.changed"  # type: ignore[misc]
    with pytest.raises(AttributeError):
        capabilities.hvac_modes.add(HVACMode.AUTO)  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("features", "target", "target_range", "status"),
    [
        (
            ClimateEntityFeature.TARGET_TEMPERATURE,
            True,
            False,
            ThermostatCapabilityDiscoveryStatus.COMPLETE,
        ),
        (
            ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
            False,
            True,
            ThermostatCapabilityDiscoveryStatus.COMPLETE,
        ),
        (
            ClimateEntityFeature(0),
            False,
            False,
            ThermostatCapabilityDiscoveryStatus.COMPLETE,
        ),
        (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.TARGET_TEMPERATURE_RANGE,
            True,
            True,
            ThermostatCapabilityDiscoveryStatus.PARTIAL,
        ),
    ],
)
def test_target_semantics_remain_independent(
    features: ClimateEntityFeature,
    target: bool,
    target_range: bool,
    status: ThermostatCapabilityDiscoveryStatus,
) -> None:
    """Test target flags are retained independently without conflict resolution."""
    discovery = _discover(_attributes(features=features))

    assert discovery.status is status
    assert discovery.capabilities is not None
    assert discovery.capabilities.target_temperature is target
    assert discovery.capabilities.target_temperature_range is target_range


@pytest.mark.parametrize("state", [None, STATE_UNKNOWN, STATE_UNAVAILABLE])
def test_missing_unknown_and_unavailable_states_are_explicitly_unavailable(
    state: str | None,
) -> None:
    """Test unavailable discovery never fabricates capability values."""
    attributes = _attributes()
    attributes.update(
        {
            "hvac_stage": 2,
            "aux_heat": True,
            ATTR_FAN_MODES: ["vendor_fan"],
        }
    )
    state_object = None if state is None else _state(attributes, state=state)

    discovery = discover_thermostat_capabilities(
        ENTITY_ID,
        state_object,
        discovered_at=DISCOVERED_AT,
    )

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.UNAVAILABLE
    assert discovery.capabilities is None


@pytest.mark.parametrize(
    ("value", "expected_modes"),
    [
        (None, frozenset()),
        ("heat", frozenset()),
        ([HVACMode.HEAT, "vendor_mode"], frozenset({HVACMode.HEAT})),
        (
            [HVACMode.HEAT, HVACMode.HEAT, HVACMode.OFF],
            frozenset({HVACMode.HEAT, HVACMode.OFF}),
        ),
        ([HVACMode.HEAT, 7], frozenset({HVACMode.HEAT})),
        ([], frozenset()),
    ],
)
def test_missing_or_malformed_hvac_modes_are_partial(
    value: object,
    expected_modes: frozenset[HVACMode],
) -> None:
    """Test malformed modes are omitted rather than crashing or being invented."""
    attributes = _attributes()
    if value is None:
        attributes.pop(ATTR_HVAC_MODES)
    else:
        attributes[ATTR_HVAC_MODES] = value

    discovery = _discover(attributes)

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.PARTIAL
    assert discovery.capabilities is not None
    assert discovery.capabilities.hvac_modes == expected_modes


def test_hvac_modes_accept_strings_and_enum_members() -> None:
    """Test supported HVAC modes normalize to genuine enum members."""
    attributes = _attributes()
    attributes[ATTR_HVAC_MODES] = ["off", HVACMode.HEAT_COOL]

    discovery = _discover(attributes)

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.COMPLETE
    assert discovery.capabilities is not None
    assert discovery.capabilities.hvac_modes == frozenset(
        {HVACMode.OFF, HVACMode.HEAT_COOL}
    )


@pytest.mark.parametrize("value", [None, "1", True, -1, 1.0])
def test_missing_or_malformed_supported_features_are_partial(value: object) -> None:
    """Test malformed feature values normalize conservatively to zero."""
    attributes = _attributes()
    if value is None:
        attributes.pop(ATTR_SUPPORTED_FEATURES)
    else:
        attributes[ATTR_SUPPORTED_FEATURES] = value

    discovery = _discover(attributes)

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.PARTIAL
    assert discovery.capabilities is not None
    assert discovery.capabilities.supported_features == ClimateEntityFeature(0)
    assert discovery.capabilities.target_temperature is False
    assert discovery.capabilities.target_temperature_range is False


def test_zero_supported_features_is_valid_and_complete() -> None:
    """Test an explicit zero mask does not imply missing capability data."""
    discovery = _discover(_attributes(features=0))

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.COMPLETE
    assert discovery.capabilities is not None
    assert discovery.capabilities.supported_features == ClimateEntityFeature(0)


def test_unknown_future_feature_bits_are_preserved_but_partial() -> None:
    """Test future bits neither crash discovery nor grant unrelated features."""
    future_bit = 1 << 20
    raw_features = future_bit | int(ClimateEntityFeature.TARGET_TEMPERATURE)

    discovery = _discover(_attributes(features=raw_features))

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.PARTIAL
    assert discovery.capabilities is not None
    assert int(discovery.capabilities.supported_features) == raw_features
    assert discovery.capabilities.target_temperature is True
    assert discovery.capabilities.target_temperature_range is False


@pytest.mark.parametrize(
    ("attribute", "feature"),
    [
        (ATTR_FAN_MODES, ClimateEntityFeature.FAN_MODE),
        (ATTR_PRESET_MODES, ClimateEntityFeature.PRESET_MODE),
    ],
)
def test_missing_advertised_fan_or_preset_modes_are_partial(
    attribute: str,
    feature: ClimateEntityFeature,
) -> None:
    """Test a feature flag requires its corresponding public mode list."""
    discovery = _discover(_attributes(features=feature))

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.PARTIAL
    assert discovery.capabilities is not None
    assert getattr(discovery.capabilities, attribute) == ()


@pytest.mark.parametrize(
    ("attribute", "feature", "value", "expected"),
    [
        (ATTR_FAN_MODES, ClimateEntityFeature.FAN_MODE, "auto", ()),
        (ATTR_FAN_MODES, ClimateEntityFeature.FAN_MODE, [], ()),
        (ATTR_FAN_MODES, ClimateEntityFeature.FAN_MODE, ["auto", 2], ("auto",)),
        (
            ATTR_FAN_MODES,
            ClimateEntityFeature.FAN_MODE,
            ["auto", "auto", "low"],
            ("auto", "low"),
        ),
        (ATTR_PRESET_MODES, ClimateEntityFeature.PRESET_MODE, {"eco"}, ()),
        (ATTR_PRESET_MODES, ClimateEntityFeature.PRESET_MODE, [], ()),
        (
            ATTR_PRESET_MODES,
            ClimateEntityFeature.PRESET_MODE,
            ["eco", None],
            ("eco",),
        ),
        (
            ATTR_PRESET_MODES,
            ClimateEntityFeature.PRESET_MODE,
            ["eco", "eco", "away"],
            ("eco", "away"),
        ),
    ],
)
def test_malformed_and_duplicate_fan_or_preset_modes_are_partial(
    attribute: str,
    feature: ClimateEntityFeature,
    value: object,
    expected: tuple[str, ...],
) -> None:
    """Test mode lists omit malformed values and deduplicate in source order."""
    attributes = _attributes(features=feature)
    attributes[attribute] = value

    discovery = _discover(attributes)

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.PARTIAL
    assert discovery.capabilities is not None
    assert getattr(discovery.capabilities, attribute) == expected


@pytest.mark.parametrize(
    ("attribute", "expected"),
    [(ATTR_FAN_MODES, ("auto", "low")), (ATTR_PRESET_MODES, ("eco", "away"))],
)
def test_observed_mode_lists_without_feature_flags_are_retained_as_partial(
    attribute: str,
    expected: tuple[str, ...],
) -> None:
    """Test public lists and authoritative feature flags remain independent."""
    attributes = _attributes(features=0)
    attributes[attribute] = list(expected)

    discovery = _discover(attributes)

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.PARTIAL
    assert discovery.capabilities is not None
    assert getattr(discovery.capabilities, attribute) == expected


@pytest.mark.parametrize("attribute", [ATTR_FAN_MODES, ATTR_PRESET_MODES])
def test_absent_optional_fan_and_preset_lists_do_not_make_discovery_partial(
    attribute: str,
) -> None:
    """Test absence is valid when the corresponding feature is not advertised."""
    attributes = _attributes(features=0)
    attributes.pop(attribute, None)

    discovery = _discover(attributes)

    assert discovery.status is ThermostatCapabilityDiscoveryStatus.COMPLETE


@pytest.mark.parametrize(
    ("attribute", "value", "expected"),
    [
        (ATTR_CURRENT_TEMPERATURE, 0, True),
        (ATTR_CURRENT_TEMPERATURE, object(), True),
        (ATTR_CURRENT_TEMPERATURE, None, False),
        (ATTR_CURRENT_HUMIDITY, 0, True),
        (ATTR_CURRENT_HUMIDITY, object(), True),
        (ATTR_CURRENT_HUMIDITY, None, False),
    ],
)
def test_current_value_availability_uses_presence_and_non_none_only(
    attribute: str,
    value: object,
    expected: bool,
) -> None:
    """Test Task 6 does not parse, normalize, or range-check current values."""
    attributes = _attributes()
    attributes[attribute] = value

    discovery = _discover(attributes)

    assert discovery.capabilities is not None
    actual = (
        discovery.capabilities.current_temperature_available
        if attribute == ATTR_CURRENT_TEMPERATURE
        else discovery.capabilities.current_humidity_available
    )
    assert actual is expected


def test_absent_current_values_are_not_available() -> None:
    """Test absent public current-value attributes are not fabricated."""
    discovery = _discover(_attributes())

    assert discovery.capabilities is not None
    assert discovery.capabilities.current_temperature_available is False
    assert discovery.capabilities.current_humidity_available is False


def test_vendor_fields_mode_action_and_equipment_do_not_imply_stage_or_aux() -> None:
    """Test plausible private fields never create generic observability."""
    attributes = _attributes()
    attributes.update(
        {
            "hvac_stage": 2,
            "equipment_stage": "second",
            "aux_heat": True,
            "auxiliary_heat": "on",
            "emergency_heat": True,
            "status": {"stage": 2},
            "traits": {"aux": True},
            "equipment_type": "heat_pump",
            ATTR_HVAC_ACTION: HVACAction.HEATING,
        }
    )

    discovery = _discover(attributes)

    assert discovery.capabilities is not None
    assert discovery.capabilities.stage_observable is False
    assert discovery.capabilities.auxiliary_heat_observable is False


def test_discovery_does_not_mutate_input_attributes() -> None:
    """Test public state data remains unchanged after normalization."""
    attributes = _attributes(
        features=ClimateEntityFeature.FAN_MODE | ClimateEntityFeature.PRESET_MODE
    )
    attributes[ATTR_FAN_MODES] = ["auto", "auto", 1]
    attributes[ATTR_PRESET_MODES] = ["eco", None]
    before = deepcopy(attributes)

    _discover(attributes)

    assert attributes == before


def test_discovery_requires_an_injected_timezone_aware_timestamp() -> None:
    """Test discovery never accepts a naive timestamp as an implicit clock."""
    with pytest.raises(ValueError, match="timezone-aware"):
        discover_thermostat_capabilities(
            ENTITY_ID,
            _state(_attributes()),
            discovered_at=datetime(2026, 7, 22, 14, 30),
        )
