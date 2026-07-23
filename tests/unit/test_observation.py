"""Test pure source observation and Task 7 normalization."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from math import inf, nan
from typing import Any

import pytest

pytest.importorskip("homeassistant", reason="CI installs Home Assistant 2026.7.3.")

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

from custom_components.intelligent_climate.models import (
    ExclusionReason,
    HumiditySource,
    ObservationSourceId,
    SourceObservation,
    SourceQuality,
    TemperatureSource,
)
from custom_components.intelligent_climate.observation import (
    observe_humidity_source,
    observe_temperature_source,
)

SOURCE_ID = ObservationSourceId.parse("f15f73b1-ea59-4b28-819f-7b99acf065bf")
ENTITY_ID = "sensor.room_temperature"
CLIMATE_ID = "climate.room"
OBSERVED_AT = datetime(2026, 7, 22, 15, 0, tzinfo=UTC)
LAST_UPDATED = datetime(2026, 7, 22, 14, 59, 30, tzinfo=UTC)


def _temperature_source(
    *,
    entity_id: str = ENTITY_ID,
    attribute: str | None = None,
    offset_c: float = 0.0,
    enabled: bool = True,
) -> TemperatureSource:
    return TemperatureSource(
        source_id=SOURCE_ID,
        entity_id=entity_id,
        attribute=attribute,
        offset_c=offset_c,
        weight=2.0,
        priority=3,
        enabled=enabled,
    )


def _humidity_source(
    *,
    entity_id: str = "sensor.room_humidity",
    attribute: str | None = None,
    offset_pct: float = 0.0,
    enabled: bool = True,
) -> HumiditySource:
    return HumiditySource(
        source_id=SOURCE_ID,
        entity_id=entity_id,
        attribute=attribute,
        offset_pct=offset_pct,
        weight=2.0,
        priority=3,
        enabled=enabled,
    )


def _state(
    entity_id: str,
    value: object,
    attributes: dict[str, Any] | None = None,
) -> State:
    return State(
        entity_id,
        str(value),
        attributes,
        last_changed=LAST_UPDATED,
        last_reported=LAST_UPDATED,
        last_updated=LAST_UPDATED,
    )


def _temperature_attribute_state(
    raw_value: object,
    *,
    extra: dict[str, Any] | None = None,
) -> State:
    attributes = {ATTR_CURRENT_TEMPERATURE: raw_value}
    if extra:
        attributes.update(extra)
    return _state(CLIMATE_ID, "heat", attributes)


def _assert_invariant(observation: SourceObservation[float]) -> None:
    if observation.quality is SourceQuality.VALID:
        assert observation.normalized_value is not None
        assert observation.exclusion_reason is None
    else:
        assert observation.normalized_value is None
        assert observation.exclusion_reason is not None
        assert observation.exclusion_reason.value == observation.quality.value


def test_observation_identity_metadata_and_raw_value_are_retained() -> None:
    """Test stable identity and raw/normalized metadata remain separate."""
    source = _temperature_source(
        entity_id=CLIMATE_ID,
        attribute=ATTR_CURRENT_TEMPERATURE,
    )
    state = _temperature_attribute_state(" 21.25 ")

    observation = observe_temperature_source(
        source,
        state,
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    assert observation.source_id is SOURCE_ID
    assert observation.raw_value == " 21.25 "
    assert observation.normalized_value == 21.25
    assert observation.observed_at is OBSERVED_AT
    assert observation.source_last_updated is LAST_UPDATED
    assert observation.quality is SourceQuality.VALID
    assert observation.exclusion_reason is None


def test_missing_state_has_no_source_timestamp() -> None:
    """Test absence is unavailable without a fabricated update time."""
    observation = observe_temperature_source(
        _temperature_source(),
        None,
        observed_at=OBSERVED_AT,
    )

    assert observation.raw_value is None
    assert observation.source_last_updated is None
    assert observation.quality is SourceQuality.UNAVAILABLE
    assert observation.exclusion_reason is ExclusionReason.UNAVAILABLE
    assert observation.restored is False


def test_observation_models_are_frozen_and_slotted() -> None:
    """Test Task 7 records are immutable slotted typed values."""
    observation = observe_temperature_source(
        _temperature_source(),
        _state(
            ENTITY_ID,
            "20",
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        ),
        observed_at=OBSERVED_AT,
    )

    assert not hasattr(observation, "__dict__")
    with pytest.raises(FrozenInstanceError):
        observation.raw_value = "changed"  # type: ignore[misc]


def test_observation_does_not_mutate_source_state_or_unit_context() -> None:
    """Test normalization leaves configuration, state, and unit context unchanged."""
    source = _temperature_source(
        entity_id=CLIMATE_ID,
        attribute=ATTR_CURRENT_TEMPERATURE,
        offset_c=1.0,
        enabled=False,
    )
    attributes = {
        ATTR_CURRENT_TEMPERATURE: "68",
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT,
        "vendor": {"nested": [1, 2]},
    }
    before = deepcopy(attributes)
    state = _state(CLIMATE_ID, "heat", attributes)
    unit_context = UnitOfTemperature.FAHRENHEIT

    observation = observe_temperature_source(
        source,
        state,
        observed_at=OBSERVED_AT,
        climate_temperature_unit=unit_context,
    )

    assert observation.normalized_value == 21.0
    assert attributes == before
    assert dict(state.attributes) == before
    assert source.enabled is False
    assert source.weight == 2.0
    assert source.priority == 3
    assert unit_context is UnitOfTemperature.FAHRENHEIT


def test_naive_observed_at_is_rejected() -> None:
    """Test the pure boundary never reads or assumes a clock."""
    with pytest.raises(ValueError, match="observed_at must be timezone-aware"):
        observe_temperature_source(
            _temperature_source(),
            None,
            observed_at=datetime(2026, 7, 22, 15, 0),
        )


def test_wrong_state_entity_is_rejected() -> None:
    """Test a caller cannot normalize data from the wrong entity."""
    with pytest.raises(
        ValueError,
        match=r"state\.entity_id must match source\.entity_id",
    ):
        observe_temperature_source(
            _temperature_source(),
            _state(
                "sensor.other",
                "20",
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
            ),
            observed_at=OBSERVED_AT,
        )


@pytest.mark.parametrize(
    ("state_value", "expected_quality", "expected_reason"),
    [
        (STATE_UNAVAILABLE, SourceQuality.UNAVAILABLE, ExclusionReason.UNAVAILABLE),
        (STATE_UNKNOWN, SourceQuality.UNKNOWN, ExclusionReason.UNKNOWN),
    ],
)
def test_sentinel_states_ignore_stale_configured_attributes(
    state_value: str,
    expected_quality: SourceQuality,
    expected_reason: ExclusionReason,
) -> None:
    """Test unavailable/unknown state wins over a stale configured attribute."""
    source = _temperature_source(
        entity_id=CLIMATE_ID,
        attribute=ATTR_CURRENT_TEMPERATURE,
    )
    state = _state(
        CLIMATE_ID,
        state_value,
        {ATTR_CURRENT_TEMPERATURE: 99},
    )

    observation = observe_temperature_source(
        source,
        state,
        observed_at=OBSERVED_AT,
    )

    assert observation.raw_value == state_value
    assert observation.normalized_value is None
    assert observation.source_last_updated is LAST_UPDATED
    assert observation.quality is expected_quality
    assert observation.exclusion_reason is expected_reason


@pytest.mark.parametrize("attributes", [{}, {ATTR_CURRENT_TEMPERATURE: None}])
def test_missing_or_none_configured_attribute_is_unknown(
    attributes: dict[str, object],
) -> None:
    """Test missing selected data is unknown rather than nonnumeric."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
        ),
        _state(CLIMATE_ID, "heat", attributes),
        observed_at=OBSERVED_AT,
    )

    assert observation.raw_value is None
    assert observation.quality is SourceQuality.UNKNOWN
    assert observation.exclusion_reason is ExclusionReason.UNKNOWN


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        (0, 0.0),
        (-12, -12.0),
        ("20.125", 20.125),
        ("  20.125\t", 20.125),
    ],
)
def test_numeric_values_parse_deterministically(
    raw_value: object,
    expected: float,
) -> None:
    """Test supported ordinary numeric representations."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
        ),
        _temperature_attribute_state(raw_value),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    assert observation.raw_value is raw_value
    assert observation.normalized_value == expected
    assert observation.quality is SourceQuality.VALID


@pytest.mark.parametrize(
    "raw_value",
    ["", "   ", "not-a-number", True, False, [20], {"value": 20}, 2 + 3j],
)
def test_unsupported_numeric_representations_are_non_numeric(
    raw_value: object,
) -> None:
    """Test booleans, containers, complex values, and text are rejected."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
        ),
        _temperature_attribute_state(raw_value),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    assert observation.raw_value is raw_value
    assert observation.quality is SourceQuality.NON_NUMERIC
    assert observation.exclusion_reason is ExclusionReason.NON_NUMERIC


@pytest.mark.parametrize(
    "raw_value",
    [nan, inf, -inf, "NaN", "inf", "-Infinity", "1e10000"],
)
def test_nonfinite_values_are_excluded(raw_value: object) -> None:
    """Test nonfinite parsed values are never normalized."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
        ),
        _temperature_attribute_state(raw_value),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    assert observation.quality is SourceQuality.NON_FINITE
    assert observation.exclusion_reason is ExclusionReason.NON_FINITE


def test_nonfinite_post_offset_value_is_excluded() -> None:
    """Test calibration cannot turn a valid value into infinity."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
            offset_c=1e308,
        ),
        _temperature_attribute_state(1e308),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    assert observation.quality is SourceQuality.NON_FINITE
    assert observation.exclusion_reason is ExclusionReason.NON_FINITE


@pytest.mark.parametrize(
    ("unit", "raw_value", "expected_c"),
    [
        (UnitOfTemperature.CELSIUS, 21.5, 21.5),
        (UnitOfTemperature.FAHRENHEIT, 68, 20.0),
        (UnitOfTemperature.KELVIN, 273.15, 0.0),
    ],
)
def test_state_temperature_supported_units_normalize_to_celsius(
    unit: UnitOfTemperature,
    raw_value: float,
    expected_c: float,
) -> None:
    """Test every officially supported 2026.7.3 temperature unit."""
    observation = observe_temperature_source(
        _temperature_source(),
        _state(ENTITY_ID, raw_value, {ATTR_UNIT_OF_MEASUREMENT: unit}),
        observed_at=OBSERVED_AT,
    )

    assert observation.normalized_value == pytest.approx(expected_c, abs=1e-12)
    assert observation.quality is SourceQuality.VALID


@pytest.mark.parametrize(
    ("unit", "raw_value", "expected_c"),
    [
        (UnitOfTemperature.CELSIUS, 22.5, 22.5),
        (UnitOfTemperature.FAHRENHEIT, 77, 25.0),
    ],
)
def test_climate_current_temperature_uses_explicit_configured_unit_context(
    unit: UnitOfTemperature,
    raw_value: float,
    expected_c: float,
) -> None:
    """Test realistic climate states use explicit configured unit context."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
        ),
        _temperature_attribute_state(raw_value),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=unit,
    )

    assert observation.normalized_value == pytest.approx(expected_c, abs=1e-12)
    assert observation.quality is SourceQuality.VALID


@pytest.mark.parametrize(
    "climate_temperature_unit",
    [None, 42, "degrees"],
)
def test_climate_rejects_missing_malformed_or_unsupported_explicit_unit(
    climate_temperature_unit: Any,
) -> None:
    """Test climate configured unit context is validated and required."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
        ),
        _temperature_attribute_state(20),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=climate_temperature_unit,
    )

    assert observation.normalized_value is None
    assert observation.quality is SourceQuality.UNIT_UNSUPPORTED
    assert observation.exclusion_reason is ExclusionReason.UNIT_UNSUPPORTED


def test_fake_climate_state_unit_is_not_used_without_explicit_context() -> None:
    """Test climate state metadata cannot substitute for configured unit context."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
        ),
        _temperature_attribute_state(
            20,
            extra={ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        ),
        observed_at=OBSERVED_AT,
    )

    assert observation.normalized_value is None
    assert observation.quality is SourceQuality.UNIT_UNSUPPORTED
    assert observation.exclusion_reason is ExclusionReason.UNIT_UNSUPPORTED


def test_explicit_climate_unit_overrides_conflicting_fake_state_unit() -> None:
    """Test explicit configured context is authoritative over climate metadata."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
        ),
        _temperature_attribute_state(
            68,
            extra={ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        ),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.FAHRENHEIT,
    )

    assert observation.normalized_value == pytest.approx(20.0, abs=1e-12)
    assert observation.quality is SourceQuality.VALID


def test_state_temperature_uses_its_own_unit_not_climate_context() -> None:
    """Test a normal sensor's public state unit remains authoritative."""
    observation = observe_temperature_source(
        _temperature_source(),
        _state(
            ENTITY_ID,
            68,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.FAHRENHEIT},
        ),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    assert observation.normalized_value == pytest.approx(20.0, abs=1e-12)
    assert observation.quality is SourceQuality.VALID


def test_state_temperature_does_not_use_climate_context_when_unit_missing() -> None:
    """Test explicit climate context cannot supply a missing sensor state unit."""
    observation = observe_temperature_source(
        _temperature_source(),
        _state(ENTITY_ID, 20),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    assert observation.normalized_value is None
    assert observation.quality is SourceQuality.UNIT_UNSUPPORTED
    assert observation.exclusion_reason is ExclusionReason.UNIT_UNSUPPORTED


def test_unsupported_temperature_attribute_binding_fails_closed() -> None:
    """Test Task 7 invents no unit semantics for future attribute bindings."""
    observation = observe_temperature_source(
        _temperature_source(entity_id=CLIMATE_ID, attribute="vendor_temperature"),
        _state(
            CLIMATE_ID,
            "heat",
            {
                "vendor_temperature": 20,
                ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
            },
        ),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    assert observation.normalized_value is None
    assert observation.quality is SourceQuality.UNIT_UNSUPPORTED
    assert observation.exclusion_reason is ExclusionReason.UNIT_UNSUPPORTED


@pytest.mark.parametrize("offset", [2.25, -3.5])
def test_temperature_calibration_applies_after_conversion(offset: float) -> None:
    """Test Celsius calibration follows Fahrenheit conversion."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
            offset_c=offset,
        ),
        _temperature_attribute_state(68),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.FAHRENHEIT,
    )

    assert observation.normalized_value == pytest.approx(20.0 + offset, abs=1e-12)


@pytest.mark.parametrize("raw_value", [20.123456789, -500.25, 500.25])
def test_temperature_is_not_rounded_or_plausibility_rejected(
    raw_value: float,
) -> None:
    """Test rounding and plausible indoor bounds remain outside Task 7."""
    observation = observe_temperature_source(
        _temperature_source(),
        _state(
            ENTITY_ID,
            raw_value,
            {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
        ),
        observed_at=OBSERVED_AT,
    )

    assert observation.normalized_value == raw_value
    assert observation.quality is SourceQuality.VALID


@pytest.mark.parametrize("raw_value", [0, 0.5, 45.125])
def test_state_humidity_percent_values_remain_percentage_points(
    raw_value: float,
) -> None:
    """Test percent values, including fractional-looking values, are not ratios."""
    source = _humidity_source()
    observation = observe_humidity_source(
        source,
        _state(
            source.entity_id,
            raw_value,
            {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE},
        ),
        observed_at=OBSERVED_AT,
    )

    assert observation.normalized_value == float(raw_value)
    assert observation.quality is SourceQuality.VALID


def test_climate_current_humidity_is_percentage_points_without_unit() -> None:
    """Test Home Assistant's public climate humidity contract."""
    source = _humidity_source(
        entity_id=CLIMATE_ID,
        attribute=ATTR_CURRENT_HUMIDITY,
    )
    observation = observe_humidity_source(
        source,
        _state(CLIMATE_ID, "cool", {ATTR_CURRENT_HUMIDITY: "50.25"}),
        observed_at=OBSERVED_AT,
    )

    assert observation.normalized_value == 50.25
    assert observation.quality is SourceQuality.VALID


@pytest.mark.parametrize("offset", [4.5, -7.25])
def test_humidity_calibration_is_unrounded(offset: float) -> None:
    """Test humidity calibration applies in percentage points without rounding."""
    source = _humidity_source(offset_pct=offset)
    observation = observe_humidity_source(
        source,
        _state(
            source.entity_id,
            "40.123456",
            {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE},
        ),
        observed_at=OBSERVED_AT,
    )

    assert observation.normalized_value == 40.123456 + offset


@pytest.mark.parametrize("raw_value", [-10, 150])
def test_humidity_is_not_clamped_or_plausibility_rejected(raw_value: float) -> None:
    """Test Task 8 retains ownership of humidity plausible-range checks."""
    source = _humidity_source()
    observation = observe_humidity_source(
        source,
        _state(
            source.entity_id,
            raw_value,
            {ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE},
        ),
        observed_at=OBSERVED_AT,
    )

    assert observation.normalized_value == raw_value
    assert observation.quality is SourceQuality.VALID


@pytest.mark.parametrize("unit", [None, "percent", "ratio", UnitOfTemperature.CELSIUS])
def test_state_humidity_rejects_missing_or_unsupported_units(unit: object) -> None:
    """Test only Home Assistant's exact public percent unit is supported."""
    source = _humidity_source()
    attributes = {} if unit is None else {ATTR_UNIT_OF_MEASUREMENT: unit}

    observation = observe_humidity_source(
        source,
        _state(source.entity_id, "50", attributes),
        observed_at=OBSERVED_AT,
    )

    assert observation.quality is SourceQuality.UNIT_UNSUPPORTED
    assert observation.exclusion_reason is ExclusionReason.UNIT_UNSUPPORTED


@pytest.mark.parametrize(
    ("state_value", "quality"),
    [
        ("heat", SourceQuality.VALID),
        (STATE_UNKNOWN, SourceQuality.UNKNOWN),
        (STATE_UNAVAILABLE, SourceQuality.UNAVAILABLE),
    ],
)
def test_supported_restored_marker_is_recorded_without_task_7_rejection(
    state_value: str,
    quality: SourceQuality,
) -> None:
    """Test restored is metadata until Task 8 health evaluation."""
    source = _temperature_source(
        entity_id=CLIMATE_ID,
        attribute=ATTR_CURRENT_TEMPERATURE,
    )
    state = _state(
        CLIMATE_ID,
        state_value,
        {
            ATTR_CURRENT_TEMPERATURE: 20,
            ATTR_RESTORED: True,
        },
    )

    observation = observe_temperature_source(
        source,
        state,
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    assert observation.restored is True
    assert observation.quality is quality
    if quality is SourceQuality.VALID:
        assert observation.normalized_value == 20.0


def test_restored_is_not_inferred_from_vendor_attributes() -> None:
    """Test only Home Assistant's supported marker is inspected."""
    observation = observe_temperature_source(
        _temperature_source(
            entity_id=CLIMATE_ID,
            attribute=ATTR_CURRENT_TEMPERATURE,
        ),
        _temperature_attribute_state(
            20,
            extra={"vendor_restored": True, "was_restored": True},
        ),
        observed_at=OBSERVED_AT,
        climate_temperature_unit=UnitOfTemperature.CELSIUS,
    )

    assert observation.quality is SourceQuality.VALID
    assert observation.restored is False


def test_every_task_7_quality_obeys_value_and_exclusion_invariants() -> None:
    """Test every quality Task 7 can produce has a consistent result shape."""
    source = _temperature_source(
        entity_id=CLIMATE_ID,
        attribute=ATTR_CURRENT_TEMPERATURE,
    )
    observations = [
        observe_temperature_source(
            source,
            _temperature_attribute_state(20),
            observed_at=OBSERVED_AT,
            climate_temperature_unit=UnitOfTemperature.CELSIUS,
        ),
        observe_temperature_source(source, None, observed_at=OBSERVED_AT),
        observe_temperature_source(
            source,
            _state(CLIMATE_ID, "heat", {}),
            observed_at=OBSERVED_AT,
        ),
        observe_temperature_source(
            source,
            _temperature_attribute_state(True),
            observed_at=OBSERVED_AT,
            climate_temperature_unit=UnitOfTemperature.CELSIUS,
        ),
        observe_temperature_source(
            source,
            _temperature_attribute_state(nan),
            observed_at=OBSERVED_AT,
            climate_temperature_unit=UnitOfTemperature.CELSIUS,
        ),
        observe_temperature_source(
            source,
            _temperature_attribute_state(20),
            observed_at=OBSERVED_AT,
        ),
    ]

    assert {item.quality for item in observations} == {
        SourceQuality.VALID,
        SourceQuality.UNAVAILABLE,
        SourceQuality.UNKNOWN,
        SourceQuality.NON_NUMERIC,
        SourceQuality.NON_FINITE,
        SourceQuality.UNIT_UNSUPPORTED,
    }
    for observation in observations:
        _assert_invariant(observation)


def test_task_7_never_produces_later_pipeline_qualities() -> None:
    """Test health, outlier, and aggregation quality codes remain dormant."""
    later_qualities = {
        SourceQuality.IMPLAUSIBLE,
        SourceQuality.STALE,
        SourceQuality.RESTORED_NOT_CONFIRMED,
        SourceQuality.JUMP_REJECTED,
        SourceQuality.OUTLIER,
        SourceQuality.CONTRADICTORY,
    }
    observations = [
        observe_temperature_source(
            _temperature_source(),
            _state(
                ENTITY_ID,
                value,
                {ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS},
            ),
            observed_at=OBSERVED_AT,
        )
        for value in (-1000, 0, 1000, "bad", "nan")
    ]

    assert later_qualities.isdisjoint(item.quality for item in observations)
