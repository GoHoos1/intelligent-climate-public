"""Deterministic shared-equipment safety arbitration."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..models.arbitration import (
    DemandSuppression,
    EquipmentDirection,
    RelatedThermostatDisposition,
    RelatedThermostatObservation,
    SharedEquipmentArbitrationPolicy,
    ZoneDemand,
    ZoneDemandDirection,
    validate_related_observations,
    validate_shared_arbitration_policy,
    validate_zone_demands,
)
from ..models.identifiers import ZoneId
from ..models.schema import EquipmentRelationship, SchemaValidationError


class ArbitrationOutcome(StrEnum):
    """Physically inert result of shared-equipment arbitration."""

    SELECTED = "selected"
    NO_ELIGIBLE_DEMAND = "no_eligible_demand"
    CONFLICT_HOLD = "conflict_hold"
    AUTHORITY_INVALID = "authority_invalid"
    TOPOLOGY_UNSUPPORTED = "topology_unsupported"


class ArbitrationReasonCode(StrEnum):
    """Privacy-safe explanation for one arbitration result."""

    HIGHEST_PRIORITY_COMPATIBLE = "highest_priority_compatible"
    EMERGENCY_PROTECTION = "emergency_protection"
    ACTIVE_DIRECTION_PRESERVED = "active_direction_preserved"
    ALL_DEMAND_SATISFIED_OR_SUPPRESSED = "all_demand_satisfied_or_suppressed"
    AUTHORITY_NOT_REVIEWED = "authority_not_reviewed"
    AUTHORITY_COUNT_INVALID = "authority_count_invalid"
    MULTI_AUTHORITY_TOPOLOGY_UNSUPPORTED = "multi_authority_topology_unsupported"
    OPPOSITE_DEMAND_CONFLICT = "opposite_demand_conflict"
    RELATED_STATE_OPPOSES_SELECTION = "related_state_opposes_selection"
    RELATED_STATE_UNCERTAIN = "related_state_uncertain"
    ACTIVE_DIRECTION_CONFLICT = "active_direction_conflict"
    EMERGENCY_DIRECTION_CONFLICT = "emergency_direction_conflict"


@dataclass(frozen=True, slots=True)
class SharedArbitrationInput:
    """All caller-supplied evidence for one pure arbitration."""

    policy: SharedEquipmentArbitrationPolicy
    demands: tuple[ZoneDemand, ...]
    equipment_direction: EquipmentDirection
    related_observations: tuple[RelatedThermostatObservation, ...]


@dataclass(frozen=True, slots=True)
class SharedArbitrationDecision:
    """A selection or hold; this is not a command plan."""

    outcome: ArbitrationOutcome
    reason_code: ArbitrationReasonCode
    selected_zone_id: ZoneId | None
    selected_direction: ZoneDemandDirection | None
    selected_target_c: float | None
    selected_deviation_c: float | None
    selected_priority: int | None
    emergency_protection: bool
    conflict_directions: tuple[ZoneDemandDirection, ...]
    considered_zone_ids: tuple[ZoneId, ...]

    @property
    def conflict_hold(self) -> bool:
        """Return whether this result must suppress later command planning."""
        return self.outcome in {
            ArbitrationOutcome.CONFLICT_HOLD,
            ArbitrationOutcome.AUTHORITY_INVALID,
            ArbitrationOutcome.TOPOLOGY_UNSUPPORTED,
        }


def resolve_shared_equipment(
    inputs: SharedArbitrationInput,
) -> SharedArbitrationDecision:
    """Apply authority, eligibility, priority, direction, and observation rules."""
    policy = inputs.policy
    validate_shared_arbitration_policy(policy)
    validate_zone_demands(policy, inputs.demands)
    validate_related_observations(policy, inputs.related_observations)
    if not isinstance(inputs.equipment_direction, EquipmentDirection):
        raise SchemaValidationError("equipment_direction", "is unsupported")

    if policy.relationship is not EquipmentRelationship.SHARED_ZONED:
        return _empty_decision(
            ArbitrationOutcome.TOPOLOGY_UNSUPPORTED,
            ArbitrationReasonCode.MULTI_AUTHORITY_TOPOLOGY_UNSUPPORTED,
            policy,
        )
    if not policy.authority_reviewed:
        return _empty_decision(
            ArbitrationOutcome.AUTHORITY_INVALID,
            ArbitrationReasonCode.AUTHORITY_NOT_REVIEWED,
            policy,
        )
    if len(policy.command_authority_entity_ids) != 1:
        return _empty_decision(
            ArbitrationOutcome.AUTHORITY_INVALID,
            ArbitrationReasonCode.AUTHORITY_COUNT_INVALID,
            policy,
        )

    eligible = tuple(
        demand
        for demand in inputs.demands
        if demand.direction in {ZoneDemandDirection.HEAT, ZoneDemandDirection.COOL}
        and demand.suppression is DemandSuppression.NONE
    )
    if not eligible:
        return _empty_decision(
            ArbitrationOutcome.NO_ELIGIBLE_DEMAND,
            ArbitrationReasonCode.ALL_DEMAND_SATISFIED_OR_SUPPRESSED,
            policy,
        )

    emergency = tuple(item for item in eligible if item.emergency_protection)
    candidates = emergency or eligible
    directions = _directions(candidates)
    if emergency and len(directions) > 1:
        return _conflict_decision(
            ArbitrationReasonCode.EMERGENCY_DIRECTION_CONFLICT,
            policy,
            directions,
            emergency=True,
        )

    if len(directions) > 1:
        active_direction = _active_demand_direction(inputs.equipment_direction)
        if active_direction is not None:
            same_direction = tuple(
                item for item in candidates if item.direction is active_direction
            )
            selected = _highest_priority(policy, same_direction)
            issue = _related_issue(
                selected.direction,
                policy,
                inputs.related_observations,
            )
            if issue is not None:
                return _conflict_decision(issue, policy, directions)
            return _selected_decision(
                selected,
                policy,
                ArbitrationReasonCode.ACTIVE_DIRECTION_PRESERVED,
            )
        if inputs.equipment_direction is not EquipmentDirection.IDLE:
            return _conflict_decision(
                ArbitrationReasonCode.ACTIVE_DIRECTION_CONFLICT,
                policy,
                directions,
            )
        selected = _highest_priority(policy, candidates)
        issue = _related_issue(selected.direction, policy, inputs.related_observations)
        if issue is not None:
            return _conflict_decision(issue, policy, directions)
        return _selected_decision(
            selected,
            policy,
            ArbitrationReasonCode.HIGHEST_PRIORITY_COMPATIBLE,
        )

    selected = _highest_priority(policy, candidates)
    active_direction = _active_demand_direction(inputs.equipment_direction)
    if inputs.equipment_direction is EquipmentDirection.UNKNOWN or (
        active_direction is not None and active_direction is not selected.direction
    ):
        return _conflict_decision(
            ArbitrationReasonCode.ACTIVE_DIRECTION_CONFLICT,
            policy,
            directions,
            emergency=selected.emergency_protection,
        )
    issue = _related_issue(selected.direction, policy, inputs.related_observations)
    if issue is not None:
        return _conflict_decision(
            issue,
            policy,
            directions,
            emergency=selected.emergency_protection,
        )
    return _selected_decision(
        selected,
        policy,
        (
            ArbitrationReasonCode.EMERGENCY_PROTECTION
            if selected.emergency_protection
            else ArbitrationReasonCode.HIGHEST_PRIORITY_COMPATIBLE
        ),
    )


def _related_issue(
    direction: ZoneDemandDirection,
    policy: SharedEquipmentArbitrationPolicy,
    observations: tuple[RelatedThermostatObservation, ...],
) -> ArbitrationReasonCode | None:
    by_entity = {item.entity_id: item for item in observations}
    for entity_id in policy.configured_thermostat_entity_ids:
        observation = by_entity.get(entity_id)
        if (
            observation is None
            or not observation.origin_certain
            or observation.disposition
            in {
                RelatedThermostatDisposition.UNCERTAIN,
                RelatedThermostatDisposition.UNAVAILABLE,
            }
        ):
            return ArbitrationReasonCode.RELATED_STATE_UNCERTAIN
        if (
            direction is ZoneDemandDirection.HEAT
            and observation.disposition is RelatedThermostatDisposition.COOL
        ) or (
            direction is ZoneDemandDirection.COOL
            and observation.disposition is RelatedThermostatDisposition.HEAT
        ):
            return ArbitrationReasonCode.RELATED_STATE_OPPOSES_SELECTION
    return None


def _highest_priority(
    policy: SharedEquipmentArbitrationPolicy,
    demands: tuple[ZoneDemand, ...],
) -> ZoneDemand:
    priority = {
        zone_id: index for index, zone_id in enumerate(policy.zone_priority_order)
    }
    return min(demands, key=lambda demand: priority[demand.zone_id])


def _directions(
    demands: tuple[ZoneDemand, ...],
) -> tuple[ZoneDemandDirection, ...]:
    present = {item.direction for item in demands}
    return tuple(
        item
        for item in (ZoneDemandDirection.HEAT, ZoneDemandDirection.COOL)
        if item in present
    )


def _active_demand_direction(
    value: EquipmentDirection,
) -> ZoneDemandDirection | None:
    if value is EquipmentDirection.HEAT:
        return ZoneDemandDirection.HEAT
    if value is EquipmentDirection.COOL:
        return ZoneDemandDirection.COOL
    return None


def _selected_decision(
    selected: ZoneDemand,
    policy: SharedEquipmentArbitrationPolicy,
    reason: ArbitrationReasonCode,
) -> SharedArbitrationDecision:
    priority = policy.zone_priority_order.index(selected.zone_id) + 1
    return SharedArbitrationDecision(
        outcome=ArbitrationOutcome.SELECTED,
        reason_code=reason,
        selected_zone_id=selected.zone_id,
        selected_direction=selected.direction,
        selected_target_c=selected.requested_target_c,
        selected_deviation_c=float(selected.deviation_c),
        selected_priority=priority,
        emergency_protection=selected.emergency_protection,
        conflict_directions=(),
        considered_zone_ids=policy.zone_priority_order,
    )


def _empty_decision(
    outcome: ArbitrationOutcome,
    reason: ArbitrationReasonCode,
    policy: SharedEquipmentArbitrationPolicy,
) -> SharedArbitrationDecision:
    return SharedArbitrationDecision(
        outcome=outcome,
        reason_code=reason,
        selected_zone_id=None,
        selected_direction=None,
        selected_target_c=None,
        selected_deviation_c=None,
        selected_priority=None,
        emergency_protection=False,
        conflict_directions=(),
        considered_zone_ids=policy.zone_priority_order,
    )


def _conflict_decision(
    reason: ArbitrationReasonCode,
    policy: SharedEquipmentArbitrationPolicy,
    directions: tuple[ZoneDemandDirection, ...],
    *,
    emergency: bool = False,
) -> SharedArbitrationDecision:
    return SharedArbitrationDecision(
        outcome=ArbitrationOutcome.CONFLICT_HOLD,
        reason_code=reason,
        selected_zone_id=None,
        selected_direction=None,
        selected_target_c=None,
        selected_deviation_c=None,
        selected_priority=None,
        emergency_protection=emergency,
        conflict_directions=directions,
        considered_zone_ids=policy.zone_priority_order,
    )
