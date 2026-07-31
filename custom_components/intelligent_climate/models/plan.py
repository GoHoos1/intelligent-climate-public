"""Strict typed command plans for Phase 2 Task 17."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256

from .command import (
    CommandAuthority,
    CommandCause,
    CommandControlledField,
    CommandKind,
    NormalizedCommandValues,
    NormalizedStateEvidence,
)
from .identifiers import (
    CommandId,
    DecisionId,
    EquipmentGroupId,
    SafetyEvaluationId,
    ZoneId,
)
from .safety import (
    SafetyCommandCandidate,
    SafetyDisposition,
    SafetyGateDecision,
    SafetyReasonCode,
    SafetyTargetDirection,
    validate_safety_candidate,
)
from .schema import SchemaValidationError

DEDUPE_FINGERPRINT_LENGTH = 64


class CommandSinkDisposition(StrEnum):
    """Physically inert result produced by a suppressed command sink."""

    SUPPRESSED_OBSERVE_ONLY = "suppressed_observe_only"
    SUPPRESSED_SHADOW = "suppressed_shadow"


@dataclass(frozen=True, slots=True)
class CommandPlan:
    """Complete typed plan with no adapter, action name, or service payload."""

    command_id: CommandId
    decision_id: DecisionId
    entry_id: str
    equipment_group_id: EquipmentGroupId
    zone_id: ZoneId
    target_entity_id: str
    command_kind: CommandKind
    desired_fields: frozenset[CommandControlledField]
    desired: NormalizedCommandValues
    target_direction: SafetyTargetDirection | None
    observed_precondition: NormalizedStateEvidence
    requested_against_revision: int
    cause: CommandCause
    authority: CommandAuthority
    user_context_id: str | None
    created_at_utc: datetime
    not_before_utc: datetime
    expires_at_utc: datetime
    safety_evaluation_id: SafetyEvaluationId
    dedupe_fingerprint: str

    def __post_init__(self) -> None:
        """Reject malformed, unbounded, or contradictory plans."""
        validate_command_plan(self)


@dataclass(frozen=True, slots=True)
class CommandSinkResult:
    """Bounded result from a suppressed sink; never dispatch authority."""

    disposition: CommandSinkDisposition
    command_id: CommandId
    decision_id: DecisionId
    safety_evaluation_id: SafetyEvaluationId
    reason_code: SafetyReasonCode
    recorded_at_utc: datetime


def build_command_plan(
    candidate: SafetyCommandCandidate,
    safety_decision: SafetyGateDecision,
    *,
    command_id: CommandId,
    decision_id: DecisionId,
    user_context_id: str | None,
) -> CommandPlan:
    """Create a plan only after the complete Task 16 gate passed."""
    _require_candidate(candidate)
    _validate_safety_link(candidate, safety_decision)
    fingerprint = command_dedupe_fingerprint(candidate)
    return CommandPlan(
        command_id=command_id,
        decision_id=decision_id,
        entry_id=candidate.entry_id,
        equipment_group_id=candidate.equipment_group_id,
        zone_id=candidate.zone_id,
        target_entity_id=candidate.target_entity_id,
        command_kind=candidate.command_kind,
        desired_fields=candidate.requested_fields,
        desired=candidate.requested_values,
        target_direction=candidate.target_direction,
        observed_precondition=candidate.observed_precondition,
        requested_against_revision=candidate.requested_against_revision,
        cause=candidate.cause,
        authority=candidate.authority,
        user_context_id=user_context_id,
        created_at_utc=candidate.created_at_utc,
        not_before_utc=candidate.not_before_utc,
        expires_at_utc=candidate.expires_at_utc,
        safety_evaluation_id=candidate.safety_evaluation_id,
        dedupe_fingerprint=fingerprint,
    )


def validate_command_plan(plan: CommandPlan) -> None:
    """Validate a plan by reconstructing its lossless safety candidate."""
    if not isinstance(plan, CommandPlan):
        raise SchemaValidationError("command_plan", "must be a command plan")
    if not isinstance(plan.command_id, CommandId):
        raise SchemaValidationError("command_id", "must be a command ID")
    if not isinstance(plan.decision_id, DecisionId):
        raise SchemaValidationError("decision_id", "must be a decision ID")
    candidate = SafetyCommandCandidate(
        safety_evaluation_id=plan.safety_evaluation_id,
        entry_id=plan.entry_id,
        equipment_group_id=plan.equipment_group_id,
        zone_id=plan.zone_id,
        target_entity_id=plan.target_entity_id,
        command_kind=plan.command_kind,
        requested_fields=plan.desired_fields,
        requested_values=plan.desired,
        target_direction=plan.target_direction,
        authority=plan.authority,
        cause=plan.cause,
        observed_precondition=plan.observed_precondition,
        requested_against_revision=plan.requested_against_revision,
        created_at_utc=plan.created_at_utc,
        not_before_utc=plan.not_before_utc,
        expires_at_utc=plan.expires_at_utc,
    )
    _validate_user_context(plan.authority, plan.user_context_id)
    expected = command_dedupe_fingerprint(candidate)
    if plan.dedupe_fingerprint != expected:
        raise SchemaValidationError(
            "dedupe_fingerprint",
            "must match the canonical command semantics",
        )


def validate_plan_safety_decision(decision: SafetyGateDecision) -> None:
    """Validate a hand-constructed Task 16 result at a plan/sink boundary."""
    if not isinstance(decision, SafetyGateDecision):
        raise SchemaValidationError("safety_decision", "must be a safety decision")
    if not isinstance(decision.safety_evaluation_id, SafetyEvaluationId):
        raise SchemaValidationError("safety_evaluation_id", "is invalid")
    if not isinstance(decision.disposition, SafetyDisposition):
        raise SchemaValidationError("safety_disposition", "is unsupported")
    if not isinstance(decision.reason_code, SafetyReasonCode):
        raise SchemaValidationError("safety_reason", "is unsupported")
    if type(decision.hard_checks_passed) is not bool:
        raise SchemaValidationError("hard_checks_passed", "must be a boolean")
    if (
        not isinstance(decision.explanation, str)
        or not decision.explanation
        or len(decision.explanation) > 255
    ):
        raise SchemaValidationError("explanation", "must be bounded nonempty text")
    if decision.reevaluate_at_utc is not None:
        value = decision.reevaluate_at_utc
        if value.tzinfo is None or value.utcoffset() != UTC.utcoffset(value):
            raise SchemaValidationError("reevaluate_at_utc", "must use UTC")
    passed_reasons = {
        SafetyReasonCode.ALL_HARD_GATES_PASSED,
        SafetyReasonCode.OBSERVE_ONLY,
        SafetyReasonCode.SHADOW_ONLY,
    }
    if decision.hard_checks_passed != (decision.reason_code in passed_reasons):
        raise SchemaValidationError(
            "hard_checks_passed", "contradicts the safety reason"
        )
    expected_disposition = {
        SafetyReasonCode.ALL_HARD_GATES_PASSED: SafetyDisposition.ELIGIBLE,
        SafetyReasonCode.OBSERVE_ONLY: SafetyDisposition.SUPPRESSED,
        SafetyReasonCode.SHADOW_ONLY: SafetyDisposition.SUPPRESSED,
    }.get(decision.reason_code)
    if (
        expected_disposition is not None
        and decision.disposition is not expected_disposition
    ):
        raise SchemaValidationError(
            "safety_disposition", "contradicts the safety reason"
        )


def command_dedupe_fingerprint(candidate: SafetyCommandCandidate) -> str:
    """Return a stable SHA-256 fingerprint without volatile plan identities."""
    _require_candidate(candidate)
    values = candidate.requested_values
    payload = {
        "entry_id": candidate.entry_id,
        "equipment_group_id": str(candidate.equipment_group_id),
        "zone_id": str(candidate.zone_id),
        "target_entity_id": candidate.target_entity_id,
        "command_kind": candidate.command_kind.value,
        "desired_fields": sorted(field.value for field in candidate.requested_fields),
        "desired": {
            "target_c": values.target_c,
            "heat_target_c": values.heat_target_c,
            "cool_target_c": values.cool_target_c,
            "hvac_mode": values.hvac_mode,
            "fan_mode": values.fan_mode,
            "fan_state": values.fan_state,
        },
        "target_direction": (
            None
            if candidate.target_direction is None
            else candidate.target_direction.value
        ),
        "requested_against_revision": candidate.requested_against_revision,
        "cause": candidate.cause.value,
        "authority": candidate.authority.value,
    }
    encoded = json.dumps(
        payload,
        allow_nan=False,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("ascii")
    return sha256(encoded).hexdigest()


def _validate_safety_link(
    candidate: SafetyCommandCandidate,
    decision: SafetyGateDecision,
) -> None:
    validate_plan_safety_decision(decision)
    if decision.safety_evaluation_id != candidate.safety_evaluation_id:
        raise SchemaValidationError(
            "safety_evaluation_id",
            "must match the completed safety evaluation",
        )


def _require_candidate(value: object) -> SafetyCommandCandidate:
    if not isinstance(value, SafetyCommandCandidate):
        raise SchemaValidationError(
            "command_candidate", "must be a safety command candidate"
        )
    validate_safety_candidate(value)
    return value


def _validate_user_context(
    authority: CommandAuthority,
    user_context_id: str | None,
) -> None:
    if authority is CommandAuthority.MANUAL:
        # SafetyCommandCandidate reconstruction already proves the enum pairing.
        _bounded_text(user_context_id, "user_context_id")
        return
    if user_context_id is not None:
        raise SchemaValidationError(
            "user_context_id",
            "must not be retained for scheduled authority",
        )


def _bounded_text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 255:
        raise SchemaValidationError(path, "must be nonempty and at most 255 characters")
    return value
