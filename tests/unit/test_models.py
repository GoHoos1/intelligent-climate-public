"""Test minimal domain models."""

from __future__ import annotations

from uuid import UUID

import pytest

from custom_components.intelligent_climate.const import (
    CONFIG_SCHEMA_VERSION,
    DOMAIN,
)
from custom_components.intelligent_climate.models import (
    EquipmentGroupId,
    OperatingMode,
    ZoneId,
    parse_operating_mode,
)


def test_domain_and_schema_constants_define_foundation_contract() -> None:
    """Test constants that external configuration will depend on."""
    assert DOMAIN == "intelligent_climate"
    assert CONFIG_SCHEMA_VERSION == 1


def test_equipment_group_id_round_trips_as_uuid() -> None:
    """Test stable equipment-group identifiers validate UUID strings."""
    raw_id = "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
    equipment_group_id = EquipmentGroupId.parse(raw_id)

    assert equipment_group_id.value == UUID(raw_id)
    assert str(equipment_group_id) == raw_id


def test_zone_id_round_trips_as_uuid() -> None:
    """Test stable zone identifiers validate UUID strings."""
    raw_id = "99246285-6f02-4e8a-94ed-bdfd4a5e62c4"
    zone_id = ZoneId.parse(raw_id)

    assert zone_id.value == UUID(raw_id)
    assert str(zone_id) == raw_id


def test_new_identifiers_are_unique() -> None:
    """Test generated identifiers are stable typed UUID wrappers."""
    assert EquipmentGroupId.new() != EquipmentGroupId.new()
    assert ZoneId.new() != ZoneId.new()


def test_new_zone_identifiers_are_canonical_uuid4_strings() -> None:
    """Test zone creation uses canonical lowercase UUIDv4 identity."""
    zone_id = ZoneId.new()
    encoded = str(zone_id)

    assert encoded == encoded.lower()
    assert encoded == str(UUID(encoded))
    assert UUID(encoded).version == 4


@pytest.mark.parametrize(
    ("raw_value", "expected"),
    [
        ("disabled", OperatingMode.DISABLED),
        ("observe_only", OperatingMode.OBSERVE_ONLY),
    ],
)
def test_operating_mode_validation_accepts_foundation_modes(
    raw_value: str,
    expected: OperatingMode,
) -> None:
    """Test operating-mode validation accepts only implemented modes."""
    assert parse_operating_mode(raw_value) is expected


def test_operating_mode_validation_rejects_future_modes() -> None:
    """Test unimplemented future modes are not silently accepted."""
    with pytest.raises(ValueError):
        parse_operating_mode("predictive_control")
