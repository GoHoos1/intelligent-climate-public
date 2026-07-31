"""Task 14 pure shared-equipment safety arbitration tests."""

from __future__ import annotations

from dataclasses import replace
from math import inf, nan
from typing import Any, cast
from uuid import UUID

import pytest

from custom_components.intelligent_climate.arbitration import (
    ArbitrationOutcome,
    ArbitrationReasonCode,
    SharedArbitrationDecision,
    SharedArbitrationInput,
    resolve_shared_equipment,
)
from custom_components.intelligent_climate.models import (
    DemandSuppression,
    EquipmentDirection,
    EquipmentGroupId,
    EquipmentRelationship,
    RelatedThermostatDisposition,
    RelatedThermostatObservation,
    SchemaValidationError,
    SharedEquipmentArbitrationPolicy,
    ZoneDemand,
    ZoneDemandDirection,
    ZoneId,
    validate_related_observations,
    validate_shared_arbitration_policy,
    validate_zone_demands,
)

ZONE_HIGH = ZoneId(UUID(int=1))
ZONE_LOW = ZoneId(UUID(int=2))
GROUP_ID = EquipmentGroupId(UUID(int=3))
AUTHORITY = "climate.shared_primary"
SECONDARY = "climate.shared_secondary"


def _policy(**changes: Any) -> SharedEquipmentArbitrationPolicy:
    value = SharedEquipmentArbitrationPolicy(
        equipment_group_id=GROUP_ID,
        relationship=EquipmentRelationship.SHARED_ZONED,
        configured_thermostat_entity_ids=(AUTHORITY, SECONDARY),
        command_authority_entity_ids=(AUTHORITY,),
        zone_priority_order=(ZONE_HIGH, ZONE_LOW),
        authority_reviewed=True,
    )
    return replace(value, **changes)


def _demand(
    zone_id: ZoneId,
    direction: ZoneDemandDirection,
    *,
    target: float | None = None,
    deviation: float = 1.0,
    suppression: DemandSuppression = DemandSuppression.NONE,
    emergency: bool = False,
) -> ZoneDemand:
    return ZoneDemand(
        zone_id=zone_id,
        direction=direction,
        deviation_c=deviation,
        requested_target_c=(
            target
            if target is not None
            else (
                21.0
                if direction is ZoneDemandDirection.HEAT
                else 24.0
                if direction is ZoneDemandDirection.COOL
                else None
            )
        ),
        suppression=suppression,
        emergency_protection=emergency,
    )


def _observations(
    *,
    authority: RelatedThermostatDisposition = RelatedThermostatDisposition.NEUTRAL,
    secondary: RelatedThermostatDisposition = RelatedThermostatDisposition.NEUTRAL,
    authority_certain: bool = True,
    secondary_certain: bool = True,
) -> tuple[RelatedThermostatObservation, ...]:
    return (
        RelatedThermostatObservation(AUTHORITY, authority, authority_certain),
        RelatedThermostatObservation(SECONDARY, secondary, secondary_certain),
    )


def _resolve(
    demands: tuple[ZoneDemand, ...],
    *,
    policy: SharedEquipmentArbitrationPolicy | None = None,
    equipment: EquipmentDirection = EquipmentDirection.IDLE,
    observations: tuple[RelatedThermostatObservation, ...] | None = None,
) -> SharedArbitrationDecision:
    return resolve_shared_equipment(
        SharedArbitrationInput(
            policy or _policy(),
            demands,
            equipment,
            _observations() if observations is None else observations,
        )
    )


def test_compatible_demand_uses_priority_not_largest_deviation() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.HEAT, target=20.5, deviation=0.5),
            _demand(ZONE_LOW, ZoneDemandDirection.HEAT, target=22.0, deviation=5.0),
        )
    )

    assert result.outcome is ArbitrationOutcome.SELECTED
    assert result.reason_code is ArbitrationReasonCode.HIGHEST_PRIORITY_COMPATIBLE
    assert result.selected_zone_id == ZONE_HIGH
    assert result.selected_direction is ZoneDemandDirection.HEAT
    assert result.selected_target_c == 20.5
    assert result.selected_deviation_c == 0.5
    assert result.selected_priority == 1
    assert not result.conflict_hold


@pytest.mark.parametrize(
    "suppression",
    [
        DemandSuppression.OVERRIDDEN,
        DemandSuppression.CONTACT_SUSPENDED,
        DemandSuppression.INVALID,
    ],
)
def test_suppressed_high_priority_zone_is_removed(
    suppression: DemandSuppression,
) -> None:
    result = _resolve(
        (
            _demand(
                ZONE_HIGH,
                ZoneDemandDirection.SUPPRESSED,
                suppression=suppression,
            ),
            _demand(ZONE_LOW, ZoneDemandDirection.COOL, target=23.0),
        )
    )

    assert result.selected_zone_id == ZONE_LOW
    assert result.selected_priority == 2


def test_satisfied_and_suppressed_demands_produce_no_selection() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.SATISFIED),
            _demand(
                ZONE_LOW,
                ZoneDemandDirection.SUPPRESSED,
                suppression=DemandSuppression.OVERRIDDEN,
            ),
        )
    )

    assert result.outcome is ArbitrationOutcome.NO_ELIGIBLE_DEMAND
    assert (
        result.reason_code is ArbitrationReasonCode.ALL_DEMAND_SATISFIED_OR_SUPPRESSED
    )
    assert result.selected_zone_id is None


def test_emergency_demand_precedes_higher_priority_comfort_demand() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.COOL),
            _demand(
                ZONE_LOW,
                ZoneDemandDirection.HEAT,
                target=10.0,
                emergency=True,
            ),
        )
    )

    assert result.outcome is ArbitrationOutcome.SELECTED
    assert result.reason_code is ArbitrationReasonCode.EMERGENCY_PROTECTION
    assert result.selected_zone_id == ZONE_LOW
    assert result.emergency_protection


def test_opposite_emergency_demands_fail_closed_without_priority_selection() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.HEAT, emergency=True),
            _demand(ZONE_LOW, ZoneDemandDirection.COOL, emergency=True),
        )
    )

    assert result.outcome is ArbitrationOutcome.CONFLICT_HOLD
    assert result.reason_code is ArbitrationReasonCode.EMERGENCY_DIRECTION_CONFLICT
    assert result.conflict_directions == (
        ZoneDemandDirection.HEAT,
        ZoneDemandDirection.COOL,
    )
    assert result.emergency_protection


def test_idle_opposite_demands_use_priority_with_neutral_state() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.COOL),
            _demand(ZONE_LOW, ZoneDemandDirection.HEAT),
        )
    )

    assert result.outcome is ArbitrationOutcome.SELECTED
    assert result.selected_zone_id == ZONE_HIGH
    assert result.selected_direction is ZoneDemandDirection.COOL


def test_active_direction_is_preserved_while_opposite_higher_priority_waits() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.COOL),
            _demand(ZONE_LOW, ZoneDemandDirection.HEAT),
        ),
        equipment=EquipmentDirection.HEAT,
        observations=_observations(
            authority=RelatedThermostatDisposition.HEAT,
            secondary=RelatedThermostatDisposition.NEUTRAL,
        ),
    )

    assert result.outcome is ArbitrationOutcome.SELECTED
    assert result.reason_code is ArbitrationReasonCode.ACTIVE_DIRECTION_PRESERVED
    assert result.selected_zone_id == ZONE_LOW
    assert result.selected_direction is ZoneDemandDirection.HEAT


def test_active_direction_with_opposing_related_state_holds() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.COOL),
            _demand(ZONE_LOW, ZoneDemandDirection.HEAT),
        ),
        equipment=EquipmentDirection.HEAT,
        observations=_observations(
            authority=RelatedThermostatDisposition.HEAT,
            secondary=RelatedThermostatDisposition.COOL,
        ),
    )

    assert result.outcome is ArbitrationOutcome.CONFLICT_HOLD
    assert result.reason_code is ArbitrationReasonCode.RELATED_STATE_OPPOSES_SELECTION


def test_unknown_active_direction_with_opposite_demands_holds() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.COOL),
            _demand(ZONE_LOW, ZoneDemandDirection.HEAT),
        ),
        equipment=EquipmentDirection.UNKNOWN,
    )

    assert result.outcome is ArbitrationOutcome.CONFLICT_HOLD
    assert result.reason_code is ArbitrationReasonCode.ACTIVE_DIRECTION_CONFLICT


def test_idle_opposite_demands_with_uncertain_related_state_hold() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.COOL),
            _demand(ZONE_LOW, ZoneDemandDirection.HEAT),
        ),
        observations=_observations(secondary=RelatedThermostatDisposition.UNCERTAIN),
    )

    assert result.outcome is ArbitrationOutcome.CONFLICT_HOLD
    assert result.reason_code is ArbitrationReasonCode.RELATED_STATE_UNCERTAIN


@pytest.mark.parametrize(
    ("equipment", "reason"),
    [
        (
            EquipmentDirection.COOL,
            ArbitrationReasonCode.ACTIVE_DIRECTION_CONFLICT,
        ),
        (
            EquipmentDirection.UNKNOWN,
            ArbitrationReasonCode.ACTIVE_DIRECTION_CONFLICT,
        ),
    ],
)
def test_single_opposite_or_unknown_active_direction_holds(
    equipment: EquipmentDirection,
    reason: ArbitrationReasonCode,
) -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        equipment=equipment,
    )

    assert result.outcome is ArbitrationOutcome.CONFLICT_HOLD
    assert result.reason_code is reason


@pytest.mark.parametrize(
    ("observations", "reason"),
    [
        (
            _observations(
                secondary=RelatedThermostatDisposition.COOL,
            ),
            ArbitrationReasonCode.RELATED_STATE_OPPOSES_SELECTION,
        ),
        (
            _observations(
                secondary=RelatedThermostatDisposition.UNCERTAIN,
            ),
            ArbitrationReasonCode.RELATED_STATE_UNCERTAIN,
        ),
        (
            _observations(
                secondary=RelatedThermostatDisposition.UNAVAILABLE,
            ),
            ArbitrationReasonCode.RELATED_STATE_UNCERTAIN,
        ),
        (
            _observations(secondary_certain=False),
            ArbitrationReasonCode.RELATED_STATE_UNCERTAIN,
        ),
        (
            (
                RelatedThermostatObservation(
                    AUTHORITY,
                    RelatedThermostatDisposition.NEUTRAL,
                    True,
                ),
            ),
            ArbitrationReasonCode.RELATED_STATE_UNCERTAIN,
        ),
    ],
)
def test_opposing_uncertain_or_missing_related_observation_holds(
    observations: tuple[RelatedThermostatObservation, ...],
    reason: ArbitrationReasonCode,
) -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        observations=observations,
    )

    assert result.outcome is ArbitrationOutcome.CONFLICT_HOLD
    assert result.reason_code is reason


def test_compatible_related_active_state_allows_selection() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.COOL),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        equipment=EquipmentDirection.COOL,
        observations=_observations(
            authority=RelatedThermostatDisposition.COOL,
            secondary=RelatedThermostatDisposition.COOL,
        ),
    )

    assert result.outcome is ArbitrationOutcome.SELECTED


@pytest.mark.parametrize(
    ("policy", "outcome", "reason"),
    [
        (
            _policy(authority_reviewed=False),
            ArbitrationOutcome.AUTHORITY_INVALID,
            ArbitrationReasonCode.AUTHORITY_NOT_REVIEWED,
        ),
        (
            _policy(command_authority_entity_ids=()),
            ArbitrationOutcome.AUTHORITY_INVALID,
            ArbitrationReasonCode.AUTHORITY_COUNT_INVALID,
        ),
        (
            _policy(command_authority_entity_ids=(AUTHORITY, SECONDARY)),
            ArbitrationOutcome.AUTHORITY_INVALID,
            ArbitrationReasonCode.AUTHORITY_COUNT_INVALID,
        ),
        (
            _policy(relationship=EquipmentRelationship.INDEPENDENT),
            ArbitrationOutcome.TOPOLOGY_UNSUPPORTED,
            ArbitrationReasonCode.MULTI_AUTHORITY_TOPOLOGY_UNSUPPORTED,
        ),
    ],
)
def test_authority_and_topology_fail_closed(
    policy: SharedEquipmentArbitrationPolicy,
    outcome: ArbitrationOutcome,
    reason: ArbitrationReasonCode,
) -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        policy=policy,
    )

    assert result.outcome is outcome
    assert result.reason_code is reason
    assert result.conflict_hold


@pytest.mark.parametrize(
    "policy",
    [
        _policy(equipment_group_id="not-an-id"),
        _policy(relationship="shared_zoned"),
        _policy(authority_reviewed=1),
        _policy(configured_thermostat_entity_ids=()),
        _policy(configured_thermostat_entity_ids=("sensor.bad",)),
        _policy(configured_thermostat_entity_ids=(AUTHORITY, AUTHORITY)),
        _policy(command_authority_entity_ids=["climate.bad"]),
        _policy(command_authority_entity_ids=("climate.foreign",)),
        _policy(zone_priority_order=()),
        _policy(zone_priority_order=(ZONE_HIGH, ZONE_HIGH)),
        _policy(zone_priority_order=(ZONE_HIGH, "not-a-zone")),
    ],
)
def test_malformed_policy_is_strictly_rejected(
    policy: SharedEquipmentArbitrationPolicy,
) -> None:
    with pytest.raises(SchemaValidationError):
        validate_shared_arbitration_policy(policy)


@pytest.mark.parametrize(
    "demands",
    [
        [_demand(ZONE_HIGH, ZoneDemandDirection.HEAT)],
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
            _demand(ZONE_HIGH, ZoneDemandDirection.COOL),
        ),
        (_demand(ZONE_HIGH, ZoneDemandDirection.HEAT),),
        (
            replace(
                _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
                zone_id=cast(Any, "bad"),
            ),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            replace(
                _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
                direction=cast(Any, "heat"),
            ),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            replace(
                _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
                suppression=cast(Any, "none"),
            ),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            replace(
                _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
                emergency_protection=cast(Any, 1),
            ),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.HEAT, deviation=-0.1),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.HEAT, deviation=nan),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.HEAT, target=inf),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            replace(
                _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
                suppression=DemandSuppression.INVALID,
            ),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            replace(
                _demand(ZONE_HIGH, ZoneDemandDirection.SATISFIED),
                suppression=DemandSuppression.INVALID,
            ),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.SUPPRESSED),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            replace(
                _demand(ZONE_HIGH, ZoneDemandDirection.SATISFIED),
                requested_target_c=20.0,
            ),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
        (
            replace(
                _demand(ZONE_HIGH, ZoneDemandDirection.SATISFIED),
                emergency_protection=True,
            ),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        ),
    ],
)
def test_malformed_or_incomplete_demand_sets_are_rejected(
    demands: object,
) -> None:
    with pytest.raises(SchemaValidationError):
        validate_zone_demands(_policy(), demands)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "observations",
    [
        [
            RelatedThermostatObservation(
                AUTHORITY,
                RelatedThermostatDisposition.NEUTRAL,
                True,
            )
        ],
        (
            RelatedThermostatObservation(
                AUTHORITY,
                RelatedThermostatDisposition.NEUTRAL,
                True,
            ),
            RelatedThermostatObservation(
                AUTHORITY,
                RelatedThermostatDisposition.NEUTRAL,
                True,
            ),
        ),
        (
            RelatedThermostatObservation(
                "climate.foreign",
                RelatedThermostatDisposition.NEUTRAL,
                True,
            ),
        ),
        (
            RelatedThermostatObservation(
                AUTHORITY,
                cast(Any, "neutral"),
                True,
            ),
        ),
        (
            RelatedThermostatObservation(
                AUTHORITY,
                RelatedThermostatDisposition.NEUTRAL,
                cast(Any, 1),
            ),
        ),
    ],
)
def test_malformed_related_observations_are_rejected(
    observations: object,
) -> None:
    with pytest.raises(SchemaValidationError):
        validate_related_observations(_policy(), observations)  # type: ignore[arg-type]


def test_invalid_equipment_direction_is_rejected() -> None:
    with pytest.raises(SchemaValidationError, match="equipment_direction"):
        resolve_shared_equipment(
            SharedArbitrationInput(
                _policy(),
                (
                    _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
                    _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
                ),
                "idle",  # type: ignore[arg-type]
                _observations(),
            )
        )


def test_decision_projection_contains_no_entity_or_user_identity() -> None:
    result = _resolve(
        (
            _demand(ZONE_HIGH, ZoneDemandDirection.HEAT),
            _demand(ZONE_LOW, ZoneDemandDirection.SATISFIED),
        )
    )
    projection = repr(result)

    assert AUTHORITY not in projection
    assert SECONDARY not in projection
    assert "context" not in projection
