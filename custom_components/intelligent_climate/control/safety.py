"""Deterministic central SafetyGate for Phase 2 Task 16."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from math import isclose

from ..arbitration.resolver import (
    ArbitrationOutcome,
    SharedArbitrationDecision,
)
from ..command.correlation import semantic_state_matches
from ..fan.policy import FanDirective, FanEvaluation
from ..fan.restore import FanRestoreDecision
from ..models.arbitration import ZoneDemandDirection
from ..models.command import (
    CommandAuthority,
    CommandCause,
    CommandControlledField,
    CommandKind,
    NormalizedStateEvidence,
    validate_state_evidence,
)
from ..models.control import ControlExecutionState
from ..models.fan import FanBindingKind, FanControlBinding
from ..models.modes import OperatingMode
from ..models.phase2_schema import Phase2CommandTiming, Phase2SafetyLimits
from ..models.safety import (
    FanSafetyOperation,
    SafetyAuthorityEvidence,
    SafetyCapabilitySnapshot,
    SafetyCommandCandidate,
    SafetyCorrelationState,
    SafetyDisposition,
    SafetyGateDecision,
    SafetyOwnership,
    SafetyReasonCode,
    SafetyTargetDirection,
    SafetyTimingEvidence,
    validate_safety_authority,
    validate_safety_candidate,
    validate_safety_capabilities,
    validate_safety_ownership,
    validate_safety_policy,
    validate_safety_timing,
)
from ..models.schema import EquipmentRelationship, SchemaValidationError


@dataclass(frozen=True, slots=True)
class SafetyFanEvidence:
    """Task 15 policy/restore proof for one fan command candidate."""

    operation: FanSafetyOperation
    binding: FanControlBinding
    evaluation: FanEvaluation
    restore: FanRestoreDecision | None = None


@dataclass(frozen=True, slots=True)
class SafetyGateInput:
    """Complete caller-supplied input for one pure safety evaluation."""

    candidate: SafetyCommandCandidate
    ownership: SafetyOwnership
    capabilities: SafetyCapabilitySnapshot
    authority: SafetyAuthorityEvidence
    timing_evidence: SafetyTimingEvidence
    safety_limits: Phase2SafetyLimits
    command_timing: Phase2CommandTiming
    current_state: NormalizedStateEvidence
    correlation_state: SafetyCorrelationState
    now_utc: datetime
    arbitration: SharedArbitrationDecision | None = None
    fan: SafetyFanEvidence | None = None


_EXPLANATIONS: dict[SafetyReasonCode, str] = {
    SafetyReasonCode.ALL_HARD_GATES_PASSED: "Every hard safety gate passed.",
    SafetyReasonCode.OBSERVE_ONLY: "Observe Only cannot execute a command.",
    SafetyReasonCode.SHADOW_ONLY: (
        "Shadow records the validated intent without execution."
    ),
    SafetyReasonCode.CONTROL_STATE_BLOCKED: (
        "The current control state suppresses commands."
    ),
    SafetyReasonCode.MANUAL_AUTHORITY_INVALID: (
        "Fresh explicit manual authority is absent."
    ),
    SafetyReasonCode.SCHEDULED_AUTHORITY_INVALID: (
        "Scheduled command authority is not currently armed."
    ),
    SafetyReasonCode.TARGET_NOT_OWNED: "The target is not owned by this entry.",
    SafetyReasonCode.COMMAND_AUTHORITY_INVALID: (
        "The configured command authority is not valid."
    ),
    SafetyReasonCode.ENTITY_DOMAIN_INVALID: (
        "The command kind does not match the target domain."
    ),
    SafetyReasonCode.CAPABILITY_UNAVAILABLE: (
        "Current target capabilities are unavailable."
    ),
    SafetyReasonCode.CAPABILITY_STALE: (
        "Target capabilities predate the command precondition."
    ),
    SafetyReasonCode.COMMAND_KIND_UNSUPPORTED: (
        "The target does not support this command kind."
    ),
    SafetyReasonCode.HVAC_MODE_UNSUPPORTED: (
        "The requested HVAC mode is not supported."
    ),
    SafetyReasonCode.FAN_MODE_UNSUPPORTED: ("The requested fan mode is not supported."),
    SafetyReasonCode.TARGET_OUTSIDE_ADVERTISED_LIMITS: (
        "The target exceeds advertised thermostat limits."
    ),
    SafetyReasonCode.TARGET_OUTSIDE_USER_LIMITS: (
        "The target exceeds configured absolute limits."
    ),
    SafetyReasonCode.RANGE_SEPARATION_INVALID: (
        "The heat and cool targets are too close."
    ),
    SafetyReasonCode.PRECONDITION_UNAVAILABLE: (
        "The current target state is unavailable."
    ),
    SafetyReasonCode.PRECONDITION_STALE: (
        "The current state no longer matches the request precondition."
    ),
    SafetyReasonCode.CORRELATION_AWAITING: (
        "A prior command is still awaiting acknowledgement."
    ),
    SafetyReasonCode.CORRELATION_UNCERTAIN: ("A prior command outcome is uncertain."),
    SafetyReasonCode.EXTERNAL_CHANGE: (
        "An external controlled-state change requires reconciliation."
    ),
    SafetyReasonCode.FAILURE_LOCKOUT: (
        "Command failure lockout requires administrator acknowledgement."
    ),
    SafetyReasonCode.NOT_BEFORE: "The request is not eligible yet.",
    SafetyReasonCode.EXPIRED: "The request expired before evaluation.",
    SafetyReasonCode.STARTUP_QUIET_PERIOD: (
        "The startup quiet period has not completed."
    ),
    SafetyReasonCode.FAILURE_COOLDOWN: "The failure cooldown has not completed.",
    SafetyReasonCode.MINIMUM_INTERVAL: (
        "The minimum command interval has not completed."
    ),
    SafetyReasonCode.MODE_REVERSAL_COOLDOWN: (
        "The HVAC mode-reversal cooldown has not completed."
    ),
    SafetyReasonCode.SEMANTIC_DEADBAND: (
        "The current controlled state already matches within deadband."
    ),
    SafetyReasonCode.ARBITRATION_REQUIRED: (
        "Shared equipment requires current arbitration evidence."
    ),
    SafetyReasonCode.ARBITRATION_BLOCKED: (
        "Shared-equipment arbitration is holding commands."
    ),
    SafetyReasonCode.ARBITRATION_MISMATCH: (
        "The request does not match the arbitrated zone and direction."
    ),
    SafetyReasonCode.FAN_EVIDENCE_REQUIRED: (
        "Fan-policy commands require current fan evidence."
    ),
    SafetyReasonCode.FAN_POLICY_BLOCKED: (
        "The fan policy does not authorize this action."
    ),
    SafetyReasonCode.FAN_POLICY_MISMATCH: (
        "The fan request does not match the configured binding and directive."
    ),
    SafetyReasonCode.FAN_RESTORE_BLOCKED: (
        "The thermostat fan mode is not safe to restore."
    ),
}

_CLIMATE_KINDS = frozenset(
    {
        CommandKind.SET_TARGET,
        CommandKind.SET_RANGE,
        CommandKind.SET_HVAC_MODE,
        CommandKind.SET_FAN_MODE,
    }
)
_FAN_KINDS = frozenset({CommandKind.FAN_ON, CommandKind.FAN_OFF})
_SCHEDULED_ACTIVE_STATES = frozenset(
    {
        ControlExecutionState.SCHEDULED_IDLE,
        ControlExecutionState.SCHEDULED_PENDING,
        ControlExecutionState.MANUAL_OVERRIDE,
        ControlExecutionState.EMERGENCY_PROTECTION,
    }
)
_SHADOW_STATES = frozenset(
    {
        ControlExecutionState.SHADOW_QUALIFYING,
        ControlExecutionState.SHADOW_READY,
    }
)


def evaluate_safety_gate(value: SafetyGateInput) -> SafetyGateDecision:
    """Apply every Task 16 hard check without dispatching or mutating state."""
    now = _validate_input(value)
    candidate = value.candidate

    result = _ownership_result(value)
    if result is not None:
        return result
    result = _capability_result(value)
    if result is not None:
        return result
    result = _precondition_result(value, now)
    if result is not None:
        return result
    result = _correlation_result(value)
    if result is not None:
        return result
    result = _limit_result(value)
    if result is not None:
        return result
    result = _arbitration_result(value)
    if result is not None:
        return result
    result = _fan_result(value)
    if result is not None:
        return result
    result = _timing_result(value, now)
    if result is not None:
        return result
    if _inside_semantic_deadband(value):
        return _decision(
            candidate,
            SafetyDisposition.SUPPRESSED,
            SafetyReasonCode.SEMANTIC_DEADBAND,
        )
    return _authority_result(value)


def _validate_input(value: SafetyGateInput) -> datetime:
    if not isinstance(value, SafetyGateInput):
        raise SchemaValidationError("safety_gate", "must be a safety-gate input")
    validate_safety_candidate(value.candidate)
    validate_safety_ownership(value.ownership)
    validate_safety_capabilities(value.capabilities)
    validate_safety_authority(value.authority)
    validate_safety_timing(value.timing_evidence)
    validate_safety_policy(value.safety_limits, value.command_timing)
    validate_state_evidence(value.current_state, path="current_state")
    if not isinstance(value.correlation_state, SafetyCorrelationState):
        raise SchemaValidationError("correlation_state", "is unsupported")
    now = _utc(value.now_utc, "now_utc")
    timestamps = (
        ("candidate.created_at_utc", value.candidate.created_at_utc),
        ("capabilities.observed_at_utc", value.capabilities.observed_at_utc),
        ("current_state.observed_at_utc", value.current_state.observed_at_utc),
        ("timing.runtime_started_at_utc", value.timing_evidence.runtime_started_at_utc),
        ("timing.last_command_at_utc", value.timing_evidence.last_command_at_utc),
        (
            "timing.last_mode_change_at_utc",
            value.timing_evidence.last_mode_change_at_utc,
        ),
        (
            "timing.last_terminal_failure_at_utc",
            value.timing_evidence.last_terminal_failure_at_utc,
        ),
    )
    for path, timestamp in timestamps:
        if timestamp is not None and timestamp > now:
            raise SchemaValidationError(path, "must not follow the evaluation clock")
    _validate_optional_evidence(value)
    return now


def _validate_optional_evidence(value: SafetyGateInput) -> None:
    shared_climate = (
        value.ownership.relationship is EquipmentRelationship.SHARED_ZONED
        and value.candidate.command_kind in _CLIMATE_KINDS
        and value.candidate.command_kind is not CommandKind.SET_FAN_MODE
    )
    if value.arbitration is not None and not isinstance(
        value.arbitration, SharedArbitrationDecision
    ):
        raise SchemaValidationError("arbitration", "must be an arbitration decision")
    if value.arbitration is not None and not shared_climate:
        raise SchemaValidationError(
            "arbitration", "is allowed only for shared thermostat control"
        )
    if value.fan is not None:
        if not isinstance(value.fan, SafetyFanEvidence):
            raise SchemaValidationError("fan", "must be fan safety evidence")
        _validate_fan_evidence(value.fan)
    if value.candidate.cause is not CommandCause.FAN_POLICY and value.fan is not None:
        raise SchemaValidationError("fan", "is allowed only for a fan-policy candidate")


def _validate_fan_evidence(value: SafetyFanEvidence) -> None:
    if not isinstance(value.operation, FanSafetyOperation):
        raise SchemaValidationError("fan.operation", "is unsupported")
    if not isinstance(value.binding, FanControlBinding):
        raise SchemaValidationError("fan.binding", "must be a fan binding")
    if not isinstance(value.evaluation, FanEvaluation):
        raise SchemaValidationError("fan.evaluation", "must be a fan evaluation")
    if value.restore is not None and not isinstance(value.restore, FanRestoreDecision):
        raise SchemaValidationError("fan.restore", "must be a fan restore decision")
    if value.operation is FanSafetyOperation.RESTORE and value.restore is None:
        raise SchemaValidationError("fan.restore", "is required for restore")
    if value.operation is not FanSafetyOperation.RESTORE and value.restore is not None:
        raise SchemaValidationError("fan.restore", "is allowed only for restore")


def _ownership_result(value: SafetyGateInput) -> SafetyGateDecision | None:
    candidate = value.candidate
    ownership = value.ownership
    if (
        candidate.entry_id != ownership.entry_id
        or candidate.equipment_group_id != ownership.equipment_group_id
        or candidate.zone_id not in ownership.zone_ids
        or candidate.target_entity_id not in ownership.owned_entity_ids
    ):
        return _blocked(candidate, SafetyReasonCode.TARGET_NOT_OWNED)
    if candidate.command_kind in _CLIMATE_KINDS:
        if (
            not ownership.authority_reviewed
            or candidate.target_entity_id not in ownership.command_authority_entity_ids
            or (
                ownership.relationship is EquipmentRelationship.SHARED_ZONED
                and len(ownership.command_authority_entity_ids) != 1
            )
        ):
            return _blocked(candidate, SafetyReasonCode.COMMAND_AUTHORITY_INVALID)
        if not candidate.target_entity_id.startswith("climate."):
            return _blocked(candidate, SafetyReasonCode.ENTITY_DOMAIN_INVALID)
    elif not candidate.target_entity_id.startswith("fan."):
        return _blocked(candidate, SafetyReasonCode.ENTITY_DOMAIN_INVALID)
    return None


def _capability_result(value: SafetyGateInput) -> SafetyGateDecision | None:
    candidate = value.candidate
    capabilities = value.capabilities
    if capabilities.entity_id != candidate.target_entity_id:
        return _blocked(candidate, SafetyReasonCode.TARGET_NOT_OWNED)
    if not capabilities.available:
        return _blocked(candidate, SafetyReasonCode.CAPABILITY_UNAVAILABLE)
    if capabilities.observed_at_utc < candidate.observed_precondition.observed_at_utc:
        return _blocked(candidate, SafetyReasonCode.CAPABILITY_STALE)
    if candidate.command_kind not in capabilities.supported_command_kinds:
        return _blocked(candidate, SafetyReasonCode.COMMAND_KIND_UNSUPPORTED)
    requested = candidate.requested_values
    if (
        CommandControlledField.HVAC_MODE in candidate.requested_fields
        and requested.hvac_mode not in capabilities.hvac_modes
    ):
        return _blocked(candidate, SafetyReasonCode.HVAC_MODE_UNSUPPORTED)
    if candidate.command_kind is CommandKind.SET_TARGET and (
        (
            candidate.target_direction is SafetyTargetDirection.HEAT
            and "heat" not in capabilities.hvac_modes
        )
        or (
            candidate.target_direction is SafetyTargetDirection.COOL
            and "cool" not in capabilities.hvac_modes
        )
    ):
        return _blocked(candidate, SafetyReasonCode.HVAC_MODE_UNSUPPORTED)
    if candidate.command_kind is CommandKind.SET_RANGE and not (
        {"heat_cool", "auto"} & set(capabilities.hvac_modes)
    ):
        return _blocked(candidate, SafetyReasonCode.HVAC_MODE_UNSUPPORTED)
    if (
        CommandControlledField.FAN_MODE in candidate.requested_fields
        and requested.fan_mode not in capabilities.fan_modes
    ):
        return _blocked(candidate, SafetyReasonCode.FAN_MODE_UNSUPPORTED)
    return None


def _precondition_result(
    value: SafetyGateInput,
    now: datetime,
) -> SafetyGateDecision | None:
    candidate = value.candidate
    current = value.current_state
    if not current.available:
        return _blocked(candidate, SafetyReasonCode.PRECONDITION_UNAVAILABLE)
    if (
        current.revision != candidate.requested_against_revision
        or current.observed_at_utc < candidate.observed_precondition.observed_at_utc
        or current.observed_at_utc > now
        or current.values != candidate.observed_precondition.values
    ):
        return _blocked(candidate, SafetyReasonCode.PRECONDITION_STALE)
    return None


def _correlation_result(value: SafetyGateInput) -> SafetyGateDecision | None:
    reason = {
        SafetyCorrelationState.CLEAR: None,
        SafetyCorrelationState.AWAITING_ACKNOWLEDGEMENT: (
            SafetyReasonCode.CORRELATION_AWAITING
        ),
        SafetyCorrelationState.UNCERTAIN: SafetyReasonCode.CORRELATION_UNCERTAIN,
        SafetyCorrelationState.EXTERNAL_CHANGE: SafetyReasonCode.EXTERNAL_CHANGE,
        SafetyCorrelationState.FAILURE_LOCKOUT: SafetyReasonCode.FAILURE_LOCKOUT,
    }[value.correlation_state]
    return None if reason is None else _blocked(value.candidate, reason)


def _limit_result(value: SafetyGateInput) -> SafetyGateDecision | None:
    candidate = value.candidate
    requested = candidate.requested_values
    capabilities = value.capabilities
    limits = value.safety_limits
    temperatures: tuple[float, ...] = ()
    if candidate.command_kind is CommandKind.SET_TARGET:
        assert requested.target_c is not None
        temperatures = (requested.target_c,)
    elif candidate.command_kind is CommandKind.SET_RANGE:
        assert requested.heat_target_c is not None
        assert requested.cool_target_c is not None
        temperatures = (requested.heat_target_c, requested.cool_target_c)
    if temperatures:
        minimum = capabilities.advertised_min_target_c
        maximum = capabilities.advertised_max_target_c
        if (
            minimum is None
            or maximum is None
            or any(item < minimum or item > maximum for item in temperatures)
        ):
            return _blocked(
                candidate,
                SafetyReasonCode.TARGET_OUTSIDE_ADVERTISED_LIMITS,
            )
    if candidate.command_kind is CommandKind.SET_TARGET:
        assert requested.target_c is not None
        bounds = (
            (
                limits.minimum_heating_target_c,
                limits.maximum_heating_target_c,
            )
            if candidate.target_direction is SafetyTargetDirection.HEAT
            else (
                limits.minimum_cooling_target_c,
                limits.maximum_cooling_target_c,
            )
        )
        if not bounds[0] <= requested.target_c <= bounds[1]:
            return _blocked(candidate, SafetyReasonCode.TARGET_OUTSIDE_USER_LIMITS)
    elif candidate.command_kind is CommandKind.SET_RANGE:
        assert requested.heat_target_c is not None
        assert requested.cool_target_c is not None
        if not (
            limits.minimum_heating_target_c
            <= requested.heat_target_c
            <= limits.maximum_heating_target_c
            and limits.minimum_cooling_target_c
            <= requested.cool_target_c
            <= limits.maximum_cooling_target_c
        ):
            return _blocked(candidate, SafetyReasonCode.TARGET_OUTSIDE_USER_LIMITS)
        separation = requested.cool_target_c - requested.heat_target_c
        if separation < limits.minimum_heat_cool_separation_c and not isclose(
            separation,
            limits.minimum_heat_cool_separation_c,
            rel_tol=0.0,
            abs_tol=1e-9,
        ):
            return _blocked(candidate, SafetyReasonCode.RANGE_SEPARATION_INVALID)
    return None


def _arbitration_result(value: SafetyGateInput) -> SafetyGateDecision | None:
    candidate = value.candidate
    shared_climate = (
        value.ownership.relationship is EquipmentRelationship.SHARED_ZONED
        and candidate.command_kind
        in {
            CommandKind.SET_TARGET,
            CommandKind.SET_RANGE,
            CommandKind.SET_HVAC_MODE,
        }
    )
    if not shared_climate:
        return None
    decision = value.arbitration
    if decision is None:
        return _blocked(candidate, SafetyReasonCode.ARBITRATION_REQUIRED)
    if decision.outcome is not ArbitrationOutcome.SELECTED:
        return _blocked(candidate, SafetyReasonCode.ARBITRATION_BLOCKED)
    expected_direction = _candidate_direction(candidate)
    if (
        decision.selected_zone_id != candidate.zone_id
        or expected_direction is None
        or decision.selected_direction is not expected_direction
        or (
            candidate.command_kind is CommandKind.SET_TARGET
            and decision.selected_target_c != candidate.requested_values.target_c
        )
    ):
        return _blocked(candidate, SafetyReasonCode.ARBITRATION_MISMATCH)
    return None


def _fan_result(value: SafetyGateInput) -> SafetyGateDecision | None:
    candidate = value.candidate
    if candidate.cause is not CommandCause.FAN_POLICY:
        return None
    evidence = value.fan
    if evidence is None:
        return _blocked(candidate, SafetyReasonCode.FAN_EVIDENCE_REQUIRED)
    if evidence.binding.entity_id != candidate.target_entity_id:
        return _blocked(candidate, SafetyReasonCode.FAN_POLICY_MISMATCH)
    if evidence.operation is FanSafetyOperation.RESTORE:
        if (
            candidate.command_kind is not CommandKind.SET_FAN_MODE
            or evidence.restore is None
            or not evidence.restore.eligible
            or evidence.restore.restore_mode != candidate.requested_values.fan_mode
        ):
            return _blocked(candidate, SafetyReasonCode.FAN_RESTORE_BLOCKED)
        return None
    if evidence.operation is FanSafetyOperation.START:
        valid = (
            evidence.evaluation.directive is FanDirective.START
            and evidence.evaluation.desired_running
            and not evidence.evaluation.lockout_active
            and (
                (
                    evidence.binding.kind is FanBindingKind.SEPARATE_FAN
                    and candidate.command_kind is CommandKind.FAN_ON
                )
                or (
                    evidence.binding.kind is FanBindingKind.THERMOSTAT_FAN_MODE
                    and candidate.command_kind is CommandKind.SET_FAN_MODE
                    and candidate.requested_values.fan_mode
                    == evidence.binding.circulation_mode
                )
            )
        )
    else:
        valid = (
            evidence.evaluation.directive is FanDirective.STOP
            and not evidence.evaluation.desired_running
            and evidence.binding.kind is FanBindingKind.SEPARATE_FAN
            and candidate.command_kind is CommandKind.FAN_OFF
        )
    if not valid:
        reason = (
            SafetyReasonCode.FAN_POLICY_BLOCKED
            if evidence.evaluation.lockout_active
            or evidence.evaluation.directive
            in {FanDirective.KEEP_RUNNING, FanDirective.KEEP_STOPPED}
            else SafetyReasonCode.FAN_POLICY_MISMATCH
        )
        return _blocked(candidate, reason)
    return None


def _timing_result(
    value: SafetyGateInput,
    now: datetime,
) -> SafetyGateDecision | None:
    candidate = value.candidate
    evidence = value.timing_evidence
    timing = value.command_timing
    if now < candidate.not_before_utc:
        return _suppressed(
            candidate,
            SafetyReasonCode.NOT_BEFORE,
            candidate.not_before_utc,
        )
    if now >= candidate.expires_at_utc:
        return _blocked(candidate, SafetyReasonCode.EXPIRED)
    startup_end = evidence.runtime_started_at_utc + timedelta(
        seconds=timing.startup_quiet_period_seconds
    )
    if now < startup_end:
        return _suppressed(
            candidate,
            SafetyReasonCode.STARTUP_QUIET_PERIOD,
            startup_end,
        )
    if evidence.last_terminal_failure_at_utc is not None:
        failure_end = evidence.last_terminal_failure_at_utc + timedelta(
            seconds=timing.failure_cooldown_seconds
        )
        if now < failure_end:
            return _suppressed(
                candidate,
                SafetyReasonCode.FAILURE_COOLDOWN,
                failure_end,
            )
    if evidence.last_command_at_utc is not None:
        interval_end = evidence.last_command_at_utc + timedelta(
            seconds=_minimum_interval_seconds(candidate, timing)
        )
        if now < interval_end:
            return _suppressed(
                candidate,
                SafetyReasonCode.MINIMUM_INTERVAL,
                interval_end,
            )
    if _is_mode_reversal(candidate):
        if evidence.last_mode_change_at_utc is None:
            return _blocked(candidate, SafetyReasonCode.MODE_REVERSAL_COOLDOWN)
        reversal_end = evidence.last_mode_change_at_utc + timedelta(
            seconds=timing.mode_reversal_cooldown_seconds
        )
        if now < reversal_end:
            return _suppressed(
                candidate,
                SafetyReasonCode.MODE_REVERSAL_COOLDOWN,
                reversal_end,
            )
    return None


def _authority_result(value: SafetyGateInput) -> SafetyGateDecision:
    candidate = value.candidate
    authority = value.authority
    if authority.operating_mode is OperatingMode.OBSERVE_ONLY:
        return _decision(
            candidate,
            SafetyDisposition.SUPPRESSED,
            SafetyReasonCode.OBSERVE_ONLY,
            hard_checks_passed=True,
        )
    if authority.operating_mode is OperatingMode.SCHEDULED_SHADOW:
        if authority.control_state not in _SHADOW_STATES:
            return _blocked(candidate, SafetyReasonCode.CONTROL_STATE_BLOCKED)
        return _decision(
            candidate,
            SafetyDisposition.SUPPRESSED,
            SafetyReasonCode.SHADOW_ONLY,
            hard_checks_passed=True,
        )
    if candidate.authority is CommandAuthority.MANUAL:
        if candidate.cause is CommandCause.MANUAL_USER:
            valid = (
                authority.operating_mode is OperatingMode.MANUAL_CONTROL
                and authority.control_state is ControlExecutionState.MANUAL_IDLE
                and authority.manual_intent_authorized
            )
        else:
            valid = (
                authority.operating_mode is OperatingMode.SCHEDULED_CONTROL
                and authority.control_state in _SCHEDULED_ACTIVE_STATES
                and authority.manual_intent_authorized
                and authority.shadow_qualified
                and authority.active_control_armed
            )
        if not valid:
            return _blocked(candidate, SafetyReasonCode.MANUAL_AUTHORITY_INVALID)
    else:
        valid = (
            authority.operating_mode is OperatingMode.SCHEDULED_CONTROL
            and authority.control_state in _SCHEDULED_ACTIVE_STATES
            and authority.shadow_qualified
            and authority.active_control_armed
        )
        if not valid:
            return _blocked(candidate, SafetyReasonCode.SCHEDULED_AUTHORITY_INVALID)
    return _decision(
        candidate,
        SafetyDisposition.ELIGIBLE,
        SafetyReasonCode.ALL_HARD_GATES_PASSED,
        hard_checks_passed=True,
    )


def _minimum_interval_seconds(
    candidate: SafetyCommandCandidate,
    timing: Phase2CommandTiming,
) -> int:
    if candidate.cause is CommandCause.MANUAL_USER:
        return timing.manual_control_minimum_interval_seconds
    if candidate.cause is CommandCause.UI_OVERRIDE:
        return timing.direct_override_minimum_interval_seconds
    return timing.automatic_minimum_interval_seconds


def _inside_semantic_deadband(value: SafetyGateInput) -> bool:
    candidate = value.candidate
    deadband = value.command_timing.target_deadband_c
    if candidate.requested_fields == frozenset({CommandControlledField.RANGE}):
        requested = candidate.requested_values
        observed = value.current_state.values
        assert requested.heat_target_c is not None
        assert requested.cool_target_c is not None
        assert observed.heat_target_c is not None
        assert observed.cool_target_c is not None
        return _within_deadband(
            requested.heat_target_c,
            observed.heat_target_c,
            deadband,
        ) or _within_deadband(
            requested.cool_target_c,
            observed.cool_target_c,
            deadband,
        )
    return semantic_state_matches(
        candidate.requested_fields,
        candidate.requested_values,
        value.current_state.values,
        temperature_deadband_c=deadband,
    )


def _within_deadband(requested: float, observed: float, deadband: float) -> bool:
    difference = abs(requested - observed)
    return difference <= deadband or isclose(
        difference,
        deadband,
        rel_tol=0.0,
        abs_tol=1e-9,
    )


def _is_mode_reversal(candidate: SafetyCommandCandidate) -> bool:
    if CommandControlledField.HVAC_MODE not in candidate.requested_fields:
        return False
    before = candidate.observed_precondition.values.hvac_mode
    after = candidate.requested_values.hvac_mode
    return (before, after) in {("heat", "cool"), ("cool", "heat")}


def _candidate_direction(
    candidate: SafetyCommandCandidate,
) -> ZoneDemandDirection | None:
    if candidate.command_kind is CommandKind.SET_TARGET:
        return (
            ZoneDemandDirection.HEAT
            if candidate.target_direction is SafetyTargetDirection.HEAT
            else ZoneDemandDirection.COOL
        )
    mode = candidate.requested_values.hvac_mode
    if mode == "heat":
        return ZoneDemandDirection.HEAT
    if mode == "cool":
        return ZoneDemandDirection.COOL
    return None


def _blocked(
    candidate: SafetyCommandCandidate,
    reason: SafetyReasonCode,
) -> SafetyGateDecision:
    return _decision(candidate, SafetyDisposition.BLOCKED, reason)


def _suppressed(
    candidate: SafetyCommandCandidate,
    reason: SafetyReasonCode,
    reevaluate_at_utc: datetime,
) -> SafetyGateDecision:
    return _decision(
        candidate,
        SafetyDisposition.SUPPRESSED,
        reason,
        reevaluate_at_utc=reevaluate_at_utc,
    )


def _decision(
    candidate: SafetyCommandCandidate,
    disposition: SafetyDisposition,
    reason: SafetyReasonCode,
    *,
    hard_checks_passed: bool = False,
    reevaluate_at_utc: datetime | None = None,
) -> SafetyGateDecision:
    return SafetyGateDecision(
        safety_evaluation_id=candidate.safety_evaluation_id,
        disposition=disposition,
        reason_code=reason,
        hard_checks_passed=hard_checks_passed,
        reevaluate_at_utc=reevaluate_at_utc,
        explanation=_EXPLANATIONS[reason],
    )


def _utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise SchemaValidationError(path, "must be timezone-aware")
    if value.utcoffset() != UTC.utcoffset(value):
        raise SchemaValidationError(path, "must use UTC")
    return value
