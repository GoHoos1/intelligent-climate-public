"""Task 16 central SafetyGate tests."""

from __future__ import annotations

from copy import copy
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from math import inf, nan
from typing import Any, cast
from uuid import UUID

import pytest

from custom_components.intelligent_climate.arbitration.resolver import (
    ArbitrationOutcome,
    ArbitrationReasonCode,
    SharedArbitrationDecision,
)
from custom_components.intelligent_climate.control.safety import (
    SafetyFanEvidence,
    SafetyGateInput,
    evaluate_safety_gate,
)
from custom_components.intelligent_climate.fan.policy import (
    FanDirective,
    FanEvaluation,
    FanReasonCode,
)
from custom_components.intelligent_climate.fan.restore import (
    FanRestoreDecision,
    FanRestoreReasonCode,
)
from custom_components.intelligent_climate.models.arbitration import (
    ZoneDemandDirection,
)
from custom_components.intelligent_climate.models.command import (
    CommandAuthority,
    CommandCause,
    CommandControlledField,
    CommandKind,
    NormalizedCommandValues,
    NormalizedStateEvidence,
)
from custom_components.intelligent_climate.models.control import ControlExecutionState
from custom_components.intelligent_climate.models.fan import (
    FanBindingKind,
    FanControlBinding,
)
from custom_components.intelligent_climate.models.identifiers import (
    EquipmentGroupId,
    SafetyEvaluationId,
    ZoneId,
)
from custom_components.intelligent_climate.models.modes import OperatingMode
from custom_components.intelligent_climate.models.phase2_schema import (
    DEFAULT_PHASE2_COMMAND_TIMING,
    DEFAULT_PHASE2_SAFETY_LIMITS,
    Phase2CommandTiming,
    Phase2SafetyLimits,
)
from custom_components.intelligent_climate.models.safety import (
    FanSafetyOperation,
    SafetyAuthorityEvidence,
    SafetyCapabilitySnapshot,
    SafetyCommandCandidate,
    SafetyCorrelationState,
    SafetyDisposition,
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
from custom_components.intelligent_climate.models.schema import (
    EquipmentRelationship,
    SchemaValidationError,
)

NOW = datetime(2026, 7, 30, 18, tzinfo=UTC)
EVALUATION_ID = SafetyEvaluationId(UUID("00000000-0000-4000-8000-000000000071"))
GROUP_ID = EquipmentGroupId(UUID("00000000-0000-4000-8000-000000000072"))
ZONE_ID = ZoneId(UUID("00000000-0000-4000-8000-000000000073"))
OTHER_ZONE_ID = ZoneId(UUID("00000000-0000-4000-8000-000000000074"))
CLIMATE = "climate.living_room"
SECONDARY = "climate.secondary"
FAN = "fan.circulation"


def _state(
    *,
    values: NormalizedCommandValues | None = None,
    revision: int = 7,
    observed_at: datetime = NOW - timedelta(seconds=2),
    available: bool = True,
) -> NormalizedStateEvidence:
    return NormalizedStateEvidence(
        revision=revision,
        observed_at_utc=observed_at,
        available=available,
        values=values or NormalizedCommandValues(target_c=20.0, hvac_mode="heat"),
    )


def _candidate(**changes: Any) -> SafetyCommandCandidate:
    values: dict[str, Any] = {
        "safety_evaluation_id": EVALUATION_ID,
        "entry_id": "entry-1",
        "equipment_group_id": GROUP_ID,
        "zone_id": ZONE_ID,
        "target_entity_id": CLIMATE,
        "command_kind": CommandKind.SET_TARGET,
        "requested_fields": frozenset({CommandControlledField.TARGET}),
        "requested_values": NormalizedCommandValues(target_c=21.0),
        "target_direction": SafetyTargetDirection.HEAT,
        "authority": CommandAuthority.MANUAL,
        "cause": CommandCause.MANUAL_USER,
        "observed_precondition": _state(),
        "requested_against_revision": 7,
        "created_at_utc": NOW - timedelta(seconds=1),
        "not_before_utc": NOW - timedelta(seconds=1),
        "expires_at_utc": NOW + timedelta(minutes=5),
    }
    values.update(changes)
    return SafetyCommandCandidate(**values)


def _ownership(**changes: Any) -> SafetyOwnership:
    values: dict[str, Any] = {
        "entry_id": "entry-1",
        "equipment_group_id": GROUP_ID,
        "zone_ids": (ZONE_ID,),
        "relationship": EquipmentRelationship.INDEPENDENT,
        "owned_entity_ids": (CLIMATE, FAN),
        "command_authority_entity_ids": (CLIMATE,),
        "authority_reviewed": True,
    }
    values.update(changes)
    return SafetyOwnership(**values)


def _capabilities(**changes: Any) -> SafetyCapabilitySnapshot:
    values: dict[str, Any] = {
        "entity_id": CLIMATE,
        "available": True,
        "supported_command_kinds": frozenset(
            {
                CommandKind.SET_TARGET,
                CommandKind.SET_RANGE,
                CommandKind.SET_HVAC_MODE,
                CommandKind.SET_FAN_MODE,
            }
        ),
        "hvac_modes": ("off", "heat", "cool", "heat_cool"),
        "fan_modes": ("auto", "circulate"),
        "advertised_min_target_c": 5.0,
        "advertised_max_target_c": 40.0,
        "observed_at_utc": NOW - timedelta(seconds=2),
    }
    values.update(changes)
    return SafetyCapabilitySnapshot(**values)


def _authority(**changes: Any) -> SafetyAuthorityEvidence:
    values: dict[str, Any] = {
        "operating_mode": OperatingMode.MANUAL_CONTROL,
        "control_state": ControlExecutionState.MANUAL_IDLE,
        "manual_intent_authorized": True,
        "shadow_qualified": False,
        "active_control_armed": False,
    }
    values.update(changes)
    return SafetyAuthorityEvidence(**values)


def _timing(**changes: Any) -> SafetyTimingEvidence:
    values: dict[str, Any] = {
        "runtime_started_at_utc": NOW - timedelta(minutes=10),
        "last_command_at_utc": None,
        "last_mode_change_at_utc": None,
        "last_terminal_failure_at_utc": None,
    }
    values.update(changes)
    return SafetyTimingEvidence(**values)


def _input(
    *,
    candidate: SafetyCommandCandidate | None = None,
    ownership: SafetyOwnership | None = None,
    capabilities: SafetyCapabilitySnapshot | None = None,
    authority: SafetyAuthorityEvidence | None = None,
    timing: SafetyTimingEvidence | None = None,
    limits: Phase2SafetyLimits = DEFAULT_PHASE2_SAFETY_LIMITS,
    command_timing: Phase2CommandTiming = DEFAULT_PHASE2_COMMAND_TIMING,
    current_state: NormalizedStateEvidence | None = None,
    correlation: SafetyCorrelationState = SafetyCorrelationState.CLEAR,
    now: datetime = NOW,
    arbitration: SharedArbitrationDecision | None = None,
    fan: SafetyFanEvidence | None = None,
) -> SafetyGateInput:
    request = candidate or _candidate()
    return SafetyGateInput(
        candidate=request,
        ownership=ownership or _ownership(),
        capabilities=capabilities or _capabilities(),
        authority=authority or _authority(),
        timing_evidence=timing or _timing(),
        safety_limits=limits,
        command_timing=command_timing,
        current_state=current_state or request.observed_precondition,
        correlation_state=correlation,
        now_utc=now,
        arbitration=arbitration,
        fan=fan,
    )


def _invalid_copy[T](value: T, **changes: Any) -> T:
    """Bypass frozen-record construction to exercise public validators."""
    result = copy(value)
    for name, replacement in changes.items():
        object.__setattr__(result, name, replacement)
    return result


def _scheduled_authority(
    *,
    shadow: bool = False,
    state: ControlExecutionState | None = None,
    qualified: bool = True,
    armed: bool = True,
) -> SafetyAuthorityEvidence:
    return _authority(
        operating_mode=(
            OperatingMode.SCHEDULED_SHADOW
            if shadow
            else OperatingMode.SCHEDULED_CONTROL
        ),
        control_state=state
        or (
            ControlExecutionState.SHADOW_READY
            if shadow
            else ControlExecutionState.SCHEDULED_PENDING
        ),
        manual_intent_authorized=False,
        shadow_qualified=qualified,
        active_control_armed=not shadow and qualified and armed,
    )


def _assert_reason(
    value: SafetyGateInput,
    reason: SafetyReasonCode,
    disposition: SafetyDisposition,
) -> None:
    result = evaluate_safety_gate(value)
    assert result.reason_code is reason
    assert result.disposition is disposition
    assert not result.eligible
    assert result.safety_evaluation_id == EVALUATION_ID


@pytest.mark.parametrize(
    ("candidate", "capabilities", "timing"),
    [
        (_candidate(), _capabilities(), _timing()),
        (
            _candidate(
                command_kind=CommandKind.SET_RANGE,
                requested_fields=frozenset({CommandControlledField.RANGE}),
                requested_values=NormalizedCommandValues(
                    heat_target_c=19.0,
                    cool_target_c=24.0,
                ),
                target_direction=None,
                observed_precondition=_state(
                    values=NormalizedCommandValues(
                        heat_target_c=18.0,
                        cool_target_c=25.0,
                    )
                ),
            ),
            _capabilities(),
            _timing(),
        ),
        (
            _candidate(
                command_kind=CommandKind.SET_HVAC_MODE,
                requested_fields=frozenset({CommandControlledField.HVAC_MODE}),
                requested_values=NormalizedCommandValues(hvac_mode="cool"),
                target_direction=None,
                observed_precondition=_state(
                    values=NormalizedCommandValues(hvac_mode="heat")
                ),
            ),
            _capabilities(),
            _timing(
                runtime_started_at_utc=NOW - timedelta(minutes=30),
                last_mode_change_at_utc=NOW - timedelta(minutes=20),
            ),
        ),
        (
            _candidate(
                command_kind=CommandKind.SET_FAN_MODE,
                requested_fields=frozenset({CommandControlledField.FAN_MODE}),
                requested_values=NormalizedCommandValues(fan_mode="circulate"),
                target_direction=None,
                observed_precondition=_state(
                    values=NormalizedCommandValues(fan_mode="auto")
                ),
            ),
            _capabilities(),
            _timing(),
        ),
        (
            _candidate(
                target_entity_id=FAN,
                command_kind=CommandKind.FAN_ON,
                requested_fields=frozenset({CommandControlledField.FAN_STATE}),
                requested_values=NormalizedCommandValues(fan_state="on"),
                target_direction=None,
                observed_precondition=_state(
                    values=NormalizedCommandValues(fan_state="off")
                ),
            ),
            _capabilities(
                entity_id=FAN,
                supported_command_kinds=frozenset(
                    {CommandKind.FAN_ON, CommandKind.FAN_OFF}
                ),
                hvac_modes=(),
                fan_modes=(),
                advertised_min_target_c=None,
                advertised_max_target_c=None,
            ),
            _timing(),
        ),
        (
            _candidate(
                target_entity_id=FAN,
                command_kind=CommandKind.FAN_OFF,
                requested_fields=frozenset({CommandControlledField.FAN_STATE}),
                requested_values=NormalizedCommandValues(fan_state="off"),
                target_direction=None,
                observed_precondition=_state(
                    values=NormalizedCommandValues(fan_state="on")
                ),
            ),
            _capabilities(
                entity_id=FAN,
                supported_command_kinds=frozenset(
                    {CommandKind.FAN_ON, CommandKind.FAN_OFF}
                ),
                hvac_modes=(),
                fan_modes=(),
                advertised_min_target_c=None,
                advertised_max_target_c=None,
            ),
            _timing(),
        ),
    ],
)
def test_every_supported_command_kind_can_pass_all_hard_gates(
    candidate: SafetyCommandCandidate,
    capabilities: SafetyCapabilitySnapshot,
    timing: SafetyTimingEvidence,
) -> None:
    result = evaluate_safety_gate(
        _input(candidate=candidate, capabilities=capabilities, timing=timing)
    )

    assert result.disposition is SafetyDisposition.ELIGIBLE
    assert result.reason_code is SafetyReasonCode.ALL_HARD_GATES_PASSED
    assert result.hard_checks_passed
    assert result.eligible
    assert result.reevaluate_at_utc is None
    assert CLIMATE not in repr(result)
    assert FAN not in repr(result)


@pytest.mark.parametrize(
    ("target", "direction", "reason"),
    [
        (7.19, SafetyTargetDirection.HEAT, SafetyReasonCode.TARGET_OUTSIDE_USER_LIMITS),
        (
            26.71,
            SafetyTargetDirection.HEAT,
            SafetyReasonCode.TARGET_OUTSIDE_USER_LIMITS,
        ),
        (
            15.59,
            SafetyTargetDirection.COOL,
            SafetyReasonCode.TARGET_OUTSIDE_USER_LIMITS,
        ),
        (
            35.01,
            SafetyTargetDirection.COOL,
            SafetyReasonCode.TARGET_OUTSIDE_USER_LIMITS,
        ),
        (
            4.99,
            SafetyTargetDirection.HEAT,
            SafetyReasonCode.TARGET_OUTSIDE_ADVERTISED_LIMITS,
        ),
        (
            40.01,
            SafetyTargetDirection.COOL,
            SafetyReasonCode.TARGET_OUTSIDE_ADVERTISED_LIMITS,
        ),
    ],
)
def test_single_target_absolute_and_advertised_limits_fail_closed(
    target: float,
    direction: SafetyTargetDirection,
    reason: SafetyReasonCode,
) -> None:
    request = _candidate(
        requested_values=NormalizedCommandValues(target_c=target),
        target_direction=direction,
    )
    _assert_reason(_input(candidate=request), reason, SafetyDisposition.BLOCKED)


@pytest.mark.parametrize(
    ("target", "direction"),
    [
        (7.2, SafetyTargetDirection.HEAT),
        (26.7, SafetyTargetDirection.HEAT),
        (15.6, SafetyTargetDirection.COOL),
        (35.0, SafetyTargetDirection.COOL),
    ],
)
def test_exact_user_limit_boundaries_are_eligible(
    target: float,
    direction: SafetyTargetDirection,
) -> None:
    request = _candidate(
        requested_values=NormalizedCommandValues(target_c=target),
        target_direction=direction,
    )
    assert evaluate_safety_gate(_input(candidate=request)).eligible


@pytest.mark.parametrize(
    ("heat", "cool", "reason"),
    [
        (7.19, 24.0, SafetyReasonCode.TARGET_OUTSIDE_USER_LIMITS),
        (19.0, 35.01, SafetyReasonCode.TARGET_OUTSIDE_USER_LIMITS),
        (20.0, 21.69, SafetyReasonCode.RANGE_SEPARATION_INVALID),
        (4.99, 24.0, SafetyReasonCode.TARGET_OUTSIDE_ADVERTISED_LIMITS),
    ],
)
def test_range_limits_and_separation(
    heat: float,
    cool: float,
    reason: SafetyReasonCode,
) -> None:
    request = _candidate(
        command_kind=CommandKind.SET_RANGE,
        requested_fields=frozenset({CommandControlledField.RANGE}),
        requested_values=NormalizedCommandValues(
            heat_target_c=heat,
            cool_target_c=cool,
        ),
        target_direction=None,
        observed_precondition=_state(
            values=NormalizedCommandValues(heat_target_c=18.0, cool_target_c=25.0)
        ),
    )
    _assert_reason(_input(candidate=request), reason, SafetyDisposition.BLOCKED)


def test_exact_range_separation_boundary_is_eligible() -> None:
    request = _candidate(
        command_kind=CommandKind.SET_RANGE,
        requested_fields=frozenset({CommandControlledField.RANGE}),
        requested_values=NormalizedCommandValues(
            heat_target_c=20.0,
            cool_target_c=21.7,
        ),
        target_direction=None,
        observed_precondition=_state(
            values=NormalizedCommandValues(heat_target_c=18.0, cool_target_c=25.0)
        ),
    )
    assert evaluate_safety_gate(_input(candidate=request)).eligible


@pytest.mark.parametrize(
    ("capability_changes", "reason"),
    [
        ({"available": False}, SafetyReasonCode.CAPABILITY_UNAVAILABLE),
        (
            {"supported_command_kinds": frozenset({CommandKind.SET_RANGE})},
            SafetyReasonCode.COMMAND_KIND_UNSUPPORTED,
        ),
        ({"hvac_modes": ("off", "cool")}, SafetyReasonCode.HVAC_MODE_UNSUPPORTED),
    ],
)
def test_missing_or_unsupported_capability_blocks(
    capability_changes: dict[str, Any],
    reason: SafetyReasonCode,
) -> None:
    _assert_reason(
        _input(capabilities=_capabilities(**capability_changes)),
        reason,
        SafetyDisposition.BLOCKED,
    )


def test_unsupported_explicit_hvac_and_fan_modes_block() -> None:
    hvac = _candidate(
        command_kind=CommandKind.SET_HVAC_MODE,
        requested_fields=frozenset({CommandControlledField.HVAC_MODE}),
        requested_values=NormalizedCommandValues(hvac_mode="dry"),
        target_direction=None,
        observed_precondition=_state(values=NormalizedCommandValues(hvac_mode="off")),
    )
    _assert_reason(
        _input(candidate=hvac),
        SafetyReasonCode.HVAC_MODE_UNSUPPORTED,
        SafetyDisposition.BLOCKED,
    )
    fan = _candidate(
        command_kind=CommandKind.SET_FAN_MODE,
        requested_fields=frozenset({CommandControlledField.FAN_MODE}),
        requested_values=NormalizedCommandValues(fan_mode="turbo"),
        target_direction=None,
        observed_precondition=_state(values=NormalizedCommandValues(fan_mode="auto")),
    )
    _assert_reason(
        _input(candidate=fan),
        SafetyReasonCode.FAN_MODE_UNSUPPORTED,
        SafetyDisposition.BLOCKED,
    )


@pytest.mark.parametrize(
    ("ownership", "reason"),
    [
        (_ownership(entry_id="other"), SafetyReasonCode.TARGET_NOT_OWNED),
        (
            _ownership(equipment_group_id=EquipmentGroupId(UUID(int=99))),
            SafetyReasonCode.TARGET_NOT_OWNED,
        ),
        (_ownership(zone_ids=(OTHER_ZONE_ID,)), SafetyReasonCode.TARGET_NOT_OWNED),
        (
            _ownership(
                owned_entity_ids=(FAN,),
                command_authority_entity_ids=(),
            ),
            SafetyReasonCode.TARGET_NOT_OWNED,
        ),
        (
            _ownership(authority_reviewed=False),
            SafetyReasonCode.COMMAND_AUTHORITY_INVALID,
        ),
        (
            _ownership(
                owned_entity_ids=(CLIMATE, SECONDARY),
                command_authority_entity_ids=(SECONDARY,),
            ),
            SafetyReasonCode.COMMAND_AUTHORITY_INVALID,
        ),
    ],
)
def test_identity_ownership_and_authority_are_hard_gates(
    ownership: SafetyOwnership,
    reason: SafetyReasonCode,
) -> None:
    _assert_reason(_input(ownership=ownership), reason, SafetyDisposition.BLOCKED)


def test_capability_identity_and_entity_domain_mismatch_block() -> None:
    _assert_reason(
        _input(capabilities=_capabilities(entity_id=SECONDARY)),
        SafetyReasonCode.TARGET_NOT_OWNED,
        SafetyDisposition.BLOCKED,
    )
    fan_target = _candidate(
        target_entity_id=FAN,
        command_kind=CommandKind.SET_TARGET,
    )
    _assert_reason(
        _input(
            candidate=fan_target,
            ownership=_ownership(command_authority_entity_ids=(FAN,)),
            capabilities=_fan_capabilities(),
        ),
        SafetyReasonCode.ENTITY_DOMAIN_INVALID,
        SafetyDisposition.BLOCKED,
    )


def test_capability_evidence_must_cover_the_command_precondition() -> None:
    stale = _capabilities(observed_at_utc=NOW - timedelta(seconds=3))
    _assert_reason(
        _input(capabilities=stale),
        SafetyReasonCode.CAPABILITY_STALE,
        SafetyDisposition.BLOCKED,
    )


@pytest.mark.parametrize(
    ("current", "reason"),
    [
        (_state(available=False), SafetyReasonCode.PRECONDITION_UNAVAILABLE),
        (_state(revision=8), SafetyReasonCode.PRECONDITION_STALE),
        (
            _state(values=NormalizedCommandValues(target_c=19.0, hvac_mode="heat")),
            SafetyReasonCode.PRECONDITION_STALE,
        ),
        (
            _state(observed_at=NOW - timedelta(seconds=3)),
            SafetyReasonCode.PRECONDITION_STALE,
        ),
    ],
)
def test_current_state_must_be_available_and_match_precondition(
    current: NormalizedStateEvidence,
    reason: SafetyReasonCode,
) -> None:
    _assert_reason(
        _input(current_state=current),
        reason,
        SafetyDisposition.BLOCKED,
    )


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        (
            SafetyCorrelationState.AWAITING_ACKNOWLEDGEMENT,
            SafetyReasonCode.CORRELATION_AWAITING,
        ),
        (SafetyCorrelationState.UNCERTAIN, SafetyReasonCode.CORRELATION_UNCERTAIN),
        (SafetyCorrelationState.EXTERNAL_CHANGE, SafetyReasonCode.EXTERNAL_CHANGE),
        (SafetyCorrelationState.FAILURE_LOCKOUT, SafetyReasonCode.FAILURE_LOCKOUT),
    ],
)
def test_every_nonclear_correlation_state_blocks(
    state: SafetyCorrelationState,
    reason: SafetyReasonCode,
) -> None:
    _assert_reason(
        _input(correlation=state),
        reason,
        SafetyDisposition.BLOCKED,
    )


@pytest.mark.parametrize(
    ("cause", "elapsed", "interval", "reason"),
    [
        (CommandCause.MANUAL_USER, 1.999, 2, SafetyReasonCode.MINIMUM_INTERVAL),
        (CommandCause.UI_OVERRIDE, 59.999, 60, SafetyReasonCode.MINIMUM_INTERVAL),
        (CommandCause.SCHEDULE, 299.999, 300, SafetyReasonCode.MINIMUM_INTERVAL),
    ],
)
def test_each_authority_uses_its_documented_minimum_interval(
    cause: CommandCause,
    elapsed: float,
    interval: int,
    reason: SafetyReasonCode,
) -> None:
    authority = (
        CommandAuthority.MANUAL
        if cause in {CommandCause.MANUAL_USER, CommandCause.UI_OVERRIDE}
        else CommandAuthority.SCHEDULED
    )
    request = _candidate(authority=authority, cause=cause)
    auth = _authority() if cause is CommandCause.MANUAL_USER else _scheduled_authority()
    result = evaluate_safety_gate(
        _input(
            candidate=request,
            authority=replace(
                auth,
                manual_intent_authorized=(cause is CommandCause.UI_OVERRIDE),
            ),
            timing=_timing(last_command_at_utc=NOW - timedelta(seconds=elapsed)),
        )
    )

    assert result.reason_code is reason
    assert result.reevaluate_at_utc == NOW + timedelta(seconds=interval - elapsed)


@pytest.mark.parametrize(
    ("cause", "interval"),
    [
        (CommandCause.MANUAL_USER, 2),
        (CommandCause.UI_OVERRIDE, 60),
        (CommandCause.SCHEDULE, 300),
    ],
)
def test_exact_minimum_interval_boundaries_pass(
    cause: CommandCause,
    interval: int,
) -> None:
    authority = (
        CommandAuthority.MANUAL
        if cause in {CommandCause.MANUAL_USER, CommandCause.UI_OVERRIDE}
        else CommandAuthority.SCHEDULED
    )
    request = _candidate(authority=authority, cause=cause)
    auth = (
        _authority()
        if cause is CommandCause.MANUAL_USER
        else replace(
            _scheduled_authority(),
            manual_intent_authorized=(cause is CommandCause.UI_OVERRIDE),
        )
    )
    result = evaluate_safety_gate(
        _input(
            candidate=request,
            authority=auth,
            timing=_timing(last_command_at_utc=NOW - timedelta(seconds=interval)),
        )
    )
    assert result.eligible


def test_not_before_expiration_startup_and_failure_cooldown_boundaries() -> None:
    future = _candidate(not_before_utc=NOW + timedelta(seconds=5))
    result = evaluate_safety_gate(_input(candidate=future))
    assert result.reason_code is SafetyReasonCode.NOT_BEFORE
    assert result.reevaluate_at_utc == NOW + timedelta(seconds=5)

    expired = _candidate(expires_at_utc=NOW)
    _assert_reason(
        _input(candidate=expired),
        SafetyReasonCode.EXPIRED,
        SafetyDisposition.BLOCKED,
    )

    startup = _timing(runtime_started_at_utc=NOW - timedelta(seconds=119))
    result = evaluate_safety_gate(_input(timing=startup))
    assert result.reason_code is SafetyReasonCode.STARTUP_QUIET_PERIOD
    assert result.reevaluate_at_utc == NOW + timedelta(seconds=1)
    assert evaluate_safety_gate(
        _input(timing=_timing(runtime_started_at_utc=NOW - timedelta(seconds=120)))
    ).eligible

    failure = _timing(
        runtime_started_at_utc=NOW - timedelta(minutes=20),
        last_terminal_failure_at_utc=NOW - timedelta(seconds=899),
    )
    result = evaluate_safety_gate(_input(timing=failure))
    assert result.reason_code is SafetyReasonCode.FAILURE_COOLDOWN
    assert result.reevaluate_at_utc == NOW + timedelta(seconds=1)
    assert evaluate_safety_gate(
        _input(
            timing=_timing(
                runtime_started_at_utc=NOW - timedelta(minutes=20),
                last_terminal_failure_at_utc=NOW - timedelta(seconds=900),
            )
        )
    ).eligible


def test_mode_reversal_requires_known_completed_cooldown() -> None:
    request = _candidate(
        command_kind=CommandKind.SET_HVAC_MODE,
        requested_fields=frozenset({CommandControlledField.HVAC_MODE}),
        requested_values=NormalizedCommandValues(hvac_mode="cool"),
        target_direction=None,
        observed_precondition=_state(values=NormalizedCommandValues(hvac_mode="heat")),
    )
    _assert_reason(
        _input(candidate=request),
        SafetyReasonCode.MODE_REVERSAL_COOLDOWN,
        SafetyDisposition.BLOCKED,
    )
    result = evaluate_safety_gate(
        _input(
            candidate=request,
            timing=_timing(
                runtime_started_at_utc=NOW - timedelta(minutes=20),
                last_mode_change_at_utc=NOW - timedelta(seconds=899),
            ),
        )
    )
    assert result.reason_code is SafetyReasonCode.MODE_REVERSAL_COOLDOWN
    assert result.reevaluate_at_utc == NOW + timedelta(seconds=1)
    assert evaluate_safety_gate(
        _input(
            candidate=request,
            timing=_timing(
                runtime_started_at_utc=NOW - timedelta(minutes=20),
                last_mode_change_at_utc=NOW - timedelta(seconds=900),
            ),
        )
    ).eligible


@pytest.mark.parametrize(
    ("requested", "suppressed"),
    [(20.3, True), (20.300001, False)],
)
def test_exact_semantic_deadband_boundary(
    requested: float,
    suppressed: bool,
) -> None:
    request = _candidate(requested_values=NormalizedCommandValues(target_c=requested))
    result = evaluate_safety_gate(_input(candidate=request))
    assert (result.reason_code is SafetyReasonCode.SEMANTIC_DEADBAND) is suppressed


@pytest.mark.parametrize(
    ("heat_target", "cool_target", "suppressed"),
    [
        (18.3, 24.0, True),
        (19.0, 24.7, True),
        (18.300001, 24.699999, False),
    ],
)
def test_range_requires_both_endpoints_outside_deadband(
    heat_target: float,
    cool_target: float,
    suppressed: bool,
) -> None:
    request = _candidate(
        command_kind=CommandKind.SET_RANGE,
        requested_fields=frozenset({CommandControlledField.RANGE}),
        requested_values=NormalizedCommandValues(
            heat_target_c=heat_target,
            cool_target_c=cool_target,
        ),
        target_direction=None,
        observed_precondition=_state(
            values=NormalizedCommandValues(
                heat_target_c=18.0,
                cool_target_c=25.0,
            )
        ),
    )
    result = evaluate_safety_gate(_input(candidate=request))
    assert (result.reason_code is SafetyReasonCode.SEMANTIC_DEADBAND) is suppressed


def test_range_and_exact_mode_dedupe_use_semantic_controlled_fields() -> None:
    range_request = _candidate(
        command_kind=CommandKind.SET_RANGE,
        requested_fields=frozenset({CommandControlledField.RANGE}),
        requested_values=NormalizedCommandValues(
            heat_target_c=18.3,
            cool_target_c=24.7,
        ),
        target_direction=None,
        observed_precondition=_state(
            values=NormalizedCommandValues(heat_target_c=18.0, cool_target_c=25.0)
        ),
    )
    _assert_reason(
        _input(candidate=range_request),
        SafetyReasonCode.SEMANTIC_DEADBAND,
        SafetyDisposition.SUPPRESSED,
    )
    mode_request = _candidate(
        command_kind=CommandKind.SET_HVAC_MODE,
        requested_fields=frozenset({CommandControlledField.HVAC_MODE}),
        requested_values=NormalizedCommandValues(hvac_mode="heat"),
        target_direction=None,
        observed_precondition=_state(values=NormalizedCommandValues(hvac_mode="heat")),
    )
    _assert_reason(
        _input(candidate=mode_request),
        SafetyReasonCode.SEMANTIC_DEADBAND,
        SafetyDisposition.SUPPRESSED,
    )


def test_observe_and_shadow_are_fully_validated_zero_command_results() -> None:
    observe = evaluate_safety_gate(
        _input(
            authority=_authority(
                operating_mode=OperatingMode.OBSERVE_ONLY,
                control_state=ControlExecutionState.OBSERVING,
                manual_intent_authorized=False,
            )
        )
    )
    assert observe.reason_code is SafetyReasonCode.OBSERVE_ONLY
    assert observe.hard_checks_passed
    assert not observe.eligible

    scheduled = _candidate(
        authority=CommandAuthority.SCHEDULED,
        cause=CommandCause.SCHEDULE,
    )
    shadow = evaluate_safety_gate(
        _input(
            candidate=scheduled,
            authority=_scheduled_authority(shadow=True),
        )
    )
    assert shadow.reason_code is SafetyReasonCode.SHADOW_ONLY
    assert shadow.hard_checks_passed
    assert not shadow.eligible


@pytest.mark.parametrize(
    ("candidate", "authority", "reason"),
    [
        (
            _candidate(),
            _authority(manual_intent_authorized=False),
            SafetyReasonCode.MANUAL_AUTHORITY_INVALID,
        ),
        (
            _candidate(),
            _authority(control_state=ControlExecutionState.SAFE_FALLBACK),
            SafetyReasonCode.MANUAL_AUTHORITY_INVALID,
        ),
        (
            _candidate(
                authority=CommandAuthority.SCHEDULED,
                cause=CommandCause.SCHEDULE,
            ),
            _scheduled_authority(qualified=False),
            SafetyReasonCode.SCHEDULED_AUTHORITY_INVALID,
        ),
        (
            _candidate(
                authority=CommandAuthority.SCHEDULED,
                cause=CommandCause.SCHEDULE,
            ),
            _scheduled_authority(armed=False),
            SafetyReasonCode.SCHEDULED_AUTHORITY_INVALID,
        ),
        (
            _candidate(
                authority=CommandAuthority.SCHEDULED,
                cause=CommandCause.SCHEDULE,
            ),
            _scheduled_authority(state=ControlExecutionState.WINDOW_SUSPENDED),
            SafetyReasonCode.SCHEDULED_AUTHORITY_INVALID,
        ),
    ],
)
def test_manual_and_scheduled_authority_fail_closed(
    candidate: SafetyCommandCandidate,
    authority: SafetyAuthorityEvidence,
    reason: SafetyReasonCode,
) -> None:
    _assert_reason(
        _input(candidate=candidate, authority=authority),
        reason,
        SafetyDisposition.BLOCKED,
    )


def test_ui_override_needs_fresh_manual_intent_in_scheduled_control() -> None:
    request = _candidate(cause=CommandCause.UI_OVERRIDE)
    denied = _scheduled_authority()
    _assert_reason(
        _input(candidate=request, authority=denied),
        SafetyReasonCode.MANUAL_AUTHORITY_INVALID,
        SafetyDisposition.BLOCKED,
    )
    allowed = replace(denied, manual_intent_authorized=True)
    assert evaluate_safety_gate(_input(candidate=request, authority=allowed)).eligible


def _arbitration(
    *,
    outcome: ArbitrationOutcome = ArbitrationOutcome.SELECTED,
    zone_id: ZoneId | None = ZONE_ID,
    direction: ZoneDemandDirection | None = ZoneDemandDirection.HEAT,
    target: float | None = 21.0,
) -> SharedArbitrationDecision:
    return SharedArbitrationDecision(
        outcome=outcome,
        reason_code=(
            ArbitrationReasonCode.HIGHEST_PRIORITY_COMPATIBLE
            if outcome is ArbitrationOutcome.SELECTED
            else ArbitrationReasonCode.RELATED_STATE_UNCERTAIN
        ),
        selected_zone_id=zone_id,
        selected_direction=direction,
        selected_target_c=target,
        selected_deviation_c=1.0 if zone_id is not None else None,
        selected_priority=1 if zone_id is not None else None,
        emergency_protection=False,
        conflict_directions=(),
        considered_zone_ids=(ZONE_ID, OTHER_ZONE_ID),
    )


def _shared_input(
    *,
    arbitration: SharedArbitrationDecision | None,
) -> SafetyGateInput:
    request = _candidate(
        authority=CommandAuthority.SCHEDULED,
        cause=CommandCause.SCHEDULE,
    )
    return _input(
        candidate=request,
        ownership=_ownership(
            relationship=EquipmentRelationship.SHARED_ZONED,
            zone_ids=(ZONE_ID, OTHER_ZONE_ID),
            owned_entity_ids=(CLIMATE, SECONDARY),
            command_authority_entity_ids=(CLIMATE,),
        ),
        authority=_scheduled_authority(),
        arbitration=arbitration,
    )


@pytest.mark.parametrize(
    ("arbitration", "reason"),
    [
        (None, SafetyReasonCode.ARBITRATION_REQUIRED),
        (
            _arbitration(outcome=ArbitrationOutcome.CONFLICT_HOLD, zone_id=None),
            SafetyReasonCode.ARBITRATION_BLOCKED,
        ),
        (
            _arbitration(zone_id=OTHER_ZONE_ID),
            SafetyReasonCode.ARBITRATION_MISMATCH,
        ),
        (
            _arbitration(direction=ZoneDemandDirection.COOL),
            SafetyReasonCode.ARBITRATION_MISMATCH,
        ),
        (_arbitration(target=22.0), SafetyReasonCode.ARBITRATION_MISMATCH),
    ],
)
def test_shared_equipment_requires_exact_selected_arbitration(
    arbitration: SharedArbitrationDecision | None,
    reason: SafetyReasonCode,
) -> None:
    _assert_reason(
        _shared_input(arbitration=arbitration),
        reason,
        SafetyDisposition.BLOCKED,
    )


def test_exact_shared_arbitration_passes() -> None:
    assert evaluate_safety_gate(_shared_input(arbitration=_arbitration())).eligible


def _fan_binding(
    *,
    kind: FanBindingKind = FanBindingKind.SEPARATE_FAN,
) -> FanControlBinding:
    return FanControlBinding(
        entity_id=FAN if kind is FanBindingKind.SEPARATE_FAN else CLIMATE,
        kind=kind,
        supported_modes=() if kind is FanBindingKind.SEPARATE_FAN else ("auto", "on"),
        circulation_mode=None if kind is FanBindingKind.SEPARATE_FAN else "on",
        native_mode=None if kind is FanBindingKind.SEPARATE_FAN else "auto",
        enabled=True,
        reviewed=True,
    )


def _fan_evaluation(
    directive: FanDirective,
    *,
    lockout: bool = False,
) -> FanEvaluation:
    return FanEvaluation(
        directive=directive,
        reason_code=(
            FanReasonCode.SPREAD_START
            if directive is FanDirective.START
            else FanReasonCode.SPREAD_SATISFIED
        ),
        desired_running=directive in {FanDirective.START, FanDirective.KEEP_RUNNING},
        lockout_active=lockout,
        degraded=False,
        calculated_dew_point_c=10.0,
        runtime_seconds_last_hour=0,
        runtime_remaining_seconds=1200,
        next_evaluation_at_utc=None,
    )


def _fan_candidate(
    kind: CommandKind,
    *,
    target: str = FAN,
    fan_mode: str | None = None,
) -> SafetyCommandCandidate:
    field = (
        CommandControlledField.FAN_MODE
        if kind is CommandKind.SET_FAN_MODE
        else CommandControlledField.FAN_STATE
    )
    desired = (
        NormalizedCommandValues(fan_mode=fan_mode)
        if kind is CommandKind.SET_FAN_MODE
        else NormalizedCommandValues(
            fan_state="on" if kind is CommandKind.FAN_ON else "off"
        )
    )
    current = (
        NormalizedCommandValues(fan_mode="on")
        if kind is CommandKind.SET_FAN_MODE
        else NormalizedCommandValues(
            fan_state="off" if kind is CommandKind.FAN_ON else "on"
        )
    )
    return _candidate(
        target_entity_id=target,
        command_kind=kind,
        requested_fields=frozenset({field}),
        requested_values=desired,
        target_direction=None,
        authority=CommandAuthority.SCHEDULED,
        cause=CommandCause.FAN_POLICY,
        observed_precondition=_state(values=current),
    )


def _fan_capabilities(
    *,
    thermostat: bool = False,
) -> SafetyCapabilitySnapshot:
    return _capabilities(
        entity_id=CLIMATE if thermostat else FAN,
        supported_command_kinds=(
            frozenset({CommandKind.SET_FAN_MODE})
            if thermostat
            else frozenset({CommandKind.FAN_ON, CommandKind.FAN_OFF})
        ),
        hvac_modes=("off", "heat", "cool") if thermostat else (),
        fan_modes=("auto", "on") if thermostat else (),
        advertised_min_target_c=None,
        advertised_max_target_c=None,
    )


def test_fan_start_stop_and_correlated_restore_require_exact_task_15_evidence() -> None:
    start = _fan_candidate(CommandKind.FAN_ON)
    start_evidence = SafetyFanEvidence(
        FanSafetyOperation.START,
        _fan_binding(),
        _fan_evaluation(FanDirective.START),
    )
    assert evaluate_safety_gate(
        _input(
            candidate=start,
            capabilities=_fan_capabilities(),
            authority=_scheduled_authority(),
            fan=start_evidence,
        )
    ).eligible

    stop = _fan_candidate(CommandKind.FAN_OFF)
    stop_evidence = SafetyFanEvidence(
        FanSafetyOperation.STOP,
        _fan_binding(),
        _fan_evaluation(FanDirective.STOP),
    )
    assert evaluate_safety_gate(
        _input(
            candidate=stop,
            capabilities=_fan_capabilities(),
            authority=_scheduled_authority(),
            fan=stop_evidence,
        )
    ).eligible

    restore = _fan_candidate(
        CommandKind.SET_FAN_MODE,
        target=CLIMATE,
        fan_mode="auto",
    )
    restore_evidence = SafetyFanEvidence(
        FanSafetyOperation.RESTORE,
        _fan_binding(kind=FanBindingKind.THERMOSTAT_FAN_MODE),
        _fan_evaluation(FanDirective.STOP),
        FanRestoreDecision(
            True,
            FanRestoreReasonCode.ELIGIBLE,
            "auto",
        ),
    )
    assert evaluate_safety_gate(
        _input(
            candidate=restore,
            capabilities=_fan_capabilities(thermostat=True),
            authority=_scheduled_authority(),
            fan=restore_evidence,
        )
    ).eligible


@pytest.mark.parametrize(
    ("fan", "reason"),
    [
        (None, SafetyReasonCode.FAN_EVIDENCE_REQUIRED),
        (
            SafetyFanEvidence(
                FanSafetyOperation.START,
                _fan_binding(),
                _fan_evaluation(FanDirective.KEEP_STOPPED, lockout=True),
            ),
            SafetyReasonCode.FAN_POLICY_BLOCKED,
        ),
        (
            SafetyFanEvidence(
                FanSafetyOperation.STOP,
                _fan_binding(),
                _fan_evaluation(FanDirective.START),
            ),
            SafetyReasonCode.FAN_POLICY_MISMATCH,
        ),
    ],
)
def test_fan_policy_missing_blocked_or_mismatched_evidence_fails_closed(
    fan: SafetyFanEvidence | None,
    reason: SafetyReasonCode,
) -> None:
    request = _fan_candidate(CommandKind.FAN_ON)
    _assert_reason(
        _input(
            candidate=request,
            capabilities=_fan_capabilities(),
            authority=_scheduled_authority(),
            fan=fan,
        ),
        reason,
        SafetyDisposition.BLOCKED,
    )


def test_fan_binding_and_restore_mismatch_fail_closed() -> None:
    request = _fan_candidate(CommandKind.FAN_ON)
    mismatched = SafetyFanEvidence(
        FanSafetyOperation.START,
        replace(_fan_binding(), entity_id="fan.other"),
        _fan_evaluation(FanDirective.START),
    )
    _assert_reason(
        _input(
            candidate=request,
            capabilities=_fan_capabilities(),
            authority=_scheduled_authority(),
            fan=mismatched,
        ),
        SafetyReasonCode.FAN_POLICY_MISMATCH,
        SafetyDisposition.BLOCKED,
    )
    restore = _fan_candidate(
        CommandKind.SET_FAN_MODE,
        target=CLIMATE,
        fan_mode="auto",
    )
    denied = SafetyFanEvidence(
        FanSafetyOperation.RESTORE,
        _fan_binding(kind=FanBindingKind.THERMOSTAT_FAN_MODE),
        _fan_evaluation(FanDirective.STOP),
        FanRestoreDecision(
            False,
            FanRestoreReasonCode.EXTERNAL_CHANGE,
            None,
        ),
    )
    _assert_reason(
        _input(
            candidate=restore,
            capabilities=_fan_capabilities(thermostat=True),
            authority=_scheduled_authority(),
            fan=denied,
        ),
        SafetyReasonCode.FAN_RESTORE_BLOCKED,
        SafetyDisposition.BLOCKED,
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"safety_evaluation_id": "bad"},
        {"entry_id": ""},
        {"equipment_group_id": "bad"},
        {"zone_id": "bad"},
        {"target_entity_id": "sensor.bad"},
        {"command_kind": "set_target"},
        {"requested_fields": {CommandControlledField.TARGET}},
        {"requested_fields": frozenset({CommandControlledField.RANGE})},
        {"requested_values": object()},
        {"requested_values": NormalizedCommandValues(target_c=nan)},
        {"requested_values": NormalizedCommandValues(target_c=inf)},
        {
            "requested_values": NormalizedCommandValues(
                target_c=21.0,
                fan_mode="auto",
            )
        },
        {"target_direction": None},
        {"target_direction": "heat"},
        {"authority": "manual"},
        {"cause": "manual_user"},
        {"requested_against_revision": True},
        {"requested_against_revision": 6},
        {"created_at_utc": NOW.replace(tzinfo=None)},
        {"not_before_utc": NOW - timedelta(seconds=2)},
        {"expires_at_utc": NOW - timedelta(seconds=1)},
    ],
)
def test_candidate_rejects_malformed_or_contradictory_fields(
    changes: dict[str, Any],
) -> None:
    values = {
        "safety_evaluation_id": EVALUATION_ID,
        "entry_id": "entry-1",
        "equipment_group_id": GROUP_ID,
        "zone_id": ZONE_ID,
        "target_entity_id": CLIMATE,
        "command_kind": CommandKind.SET_TARGET,
        "requested_fields": frozenset({CommandControlledField.TARGET}),
        "requested_values": NormalizedCommandValues(target_c=21.0),
        "target_direction": SafetyTargetDirection.HEAT,
        "authority": CommandAuthority.MANUAL,
        "cause": CommandCause.MANUAL_USER,
        "observed_precondition": _state(),
        "requested_against_revision": 7,
        "created_at_utc": NOW - timedelta(seconds=1),
        "not_before_utc": NOW - timedelta(seconds=1),
        "expires_at_utc": NOW + timedelta(minutes=5),
    }
    values.update(changes)
    with pytest.raises(SchemaValidationError):
        cast(Any, SafetyCommandCandidate)(**values)


def test_candidate_range_fan_and_authority_shape_validation() -> None:
    with pytest.raises(SchemaValidationError, match="range heat target"):
        _candidate(
            command_kind=CommandKind.SET_RANGE,
            requested_fields=frozenset({CommandControlledField.RANGE}),
            requested_values=NormalizedCommandValues(
                heat_target_c=24.0,
                cool_target_c=20.0,
            ),
            target_direction=None,
            observed_precondition=_state(
                values=NormalizedCommandValues(
                    heat_target_c=18.0,
                    cool_target_c=25.0,
                )
            ),
        )
    for kind, state in (
        (CommandKind.FAN_ON, "off"),
        (CommandKind.FAN_OFF, "on"),
    ):
        with pytest.raises(SchemaValidationError, match="must be"):
            _candidate(
                target_entity_id=FAN,
                command_kind=kind,
                requested_fields=frozenset({CommandControlledField.FAN_STATE}),
                requested_values=NormalizedCommandValues(fan_state=state),
                target_direction=None,
                observed_precondition=_state(
                    values=NormalizedCommandValues(fan_state="off")
                ),
            )
    with pytest.raises(SchemaValidationError, match="manual authority"):
        _candidate(cause=CommandCause.SCHEDULE)
    with pytest.raises(SchemaValidationError, match="requires manual"):
        _candidate(authority=CommandAuthority.SCHEDULED)


def test_candidate_requires_complete_precondition_and_timestamp_order() -> None:
    with pytest.raises(SchemaValidationError, match="must be true"):
        _candidate(observed_precondition=_state(available=False))
    with pytest.raises(SchemaValidationError, match="every controlled field"):
        _candidate(
            observed_precondition=_state(
                values=NormalizedCommandValues(hvac_mode="heat")
            )
        )
    with pytest.raises(SchemaValidationError, match="must not follow"):
        _candidate(
            observed_precondition=_state(observed_at=NOW),
            created_at_utc=NOW - timedelta(seconds=1),
        )


@pytest.mark.parametrize(
    "ownership",
    [
        _invalid_copy(_ownership(), entry_id=""),
        _invalid_copy(_ownership(), equipment_group_id="bad"),
        _invalid_copy(_ownership(), zone_ids=()),
        _invalid_copy(_ownership(), zone_ids=(ZONE_ID, ZONE_ID)),
        _invalid_copy(_ownership(), relationship="independent"),
        _invalid_copy(_ownership(), owned_entity_ids=()),
        _invalid_copy(_ownership(), owned_entity_ids=(CLIMATE, CLIMATE)),
        _invalid_copy(
            _ownership(),
            command_authority_entity_ids=("climate.foreign",),
        ),
        _invalid_copy(_ownership(), authority_reviewed=1),
    ],
)
def test_ownership_validation_rejects_malformed_graph(
    ownership: SafetyOwnership,
) -> None:
    with pytest.raises(SchemaValidationError):
        validate_safety_ownership(ownership)


@pytest.mark.parametrize(
    "capabilities",
    [
        _invalid_copy(_capabilities(), entity_id="sensor.bad"),
        _invalid_copy(_capabilities(), available=1),
        _invalid_copy(_capabilities(), supported_command_kinds=set()),
        _invalid_copy(
            _capabilities(),
            supported_command_kinds=frozenset({"set_target"}),
        ),
        _invalid_copy(
            _capabilities(),
            supported_command_kinds=frozenset({CommandKind.FAN_ON}),
        ),
        _invalid_copy(_capabilities(), hvac_modes=["heat"]),
        _invalid_copy(_capabilities(), hvac_modes=("heat", "heat")),
        _invalid_copy(_capabilities(), advertised_min_target_c=nan),
        _invalid_copy(_capabilities(), advertised_min_target_c=40.0),
        _invalid_copy(_capabilities(), advertised_max_target_c=None),
        _invalid_copy(
            _fan_capabilities(),
            advertised_min_target_c=5.0,
            advertised_max_target_c=40.0,
        ),
    ],
)
def test_capability_validation_rejects_malformed_or_contradictory_snapshots(
    capabilities: SafetyCapabilitySnapshot,
) -> None:
    with pytest.raises(SchemaValidationError):
        validate_safety_capabilities(capabilities)


def test_authority_timing_and_policy_validation_are_strict() -> None:
    for authority in (
        _invalid_copy(_authority(), operating_mode="manual_control"),
        _invalid_copy(_authority(), control_state="manual_idle"),
        _invalid_copy(_authority(), manual_intent_authorized=1),
        _invalid_copy(_authority(), shadow_qualified=1),
        _invalid_copy(_authority(), active_control_armed=1),
        _invalid_copy(
            _authority(
                operating_mode=OperatingMode.OBSERVE_ONLY,
                control_state=ControlExecutionState.OBSERVING,
                manual_intent_authorized=False,
            ),
            active_control_armed=True,
        ),
        _invalid_copy(
            _authority(
                operating_mode=OperatingMode.SCHEDULED_SHADOW,
                control_state=ControlExecutionState.SHADOW_READY,
                manual_intent_authorized=False,
            ),
            manual_intent_authorized=True,
        ),
    ):
        with pytest.raises(SchemaValidationError):
            validate_safety_authority(authority)

    for timing in (
        _invalid_copy(
            _timing(),
            runtime_started_at_utc=NOW.replace(tzinfo=None),
        ),
        _invalid_copy(
            _timing(),
            last_command_at_utc=NOW - timedelta(minutes=11),
        ),
    ):
        with pytest.raises(SchemaValidationError):
            validate_safety_timing(timing)

    with pytest.raises(SchemaValidationError):
        validate_safety_policy(cast(Any, object()), DEFAULT_PHASE2_COMMAND_TIMING)
    with pytest.raises(SchemaValidationError):
        validate_safety_policy(DEFAULT_PHASE2_SAFETY_LIMITS, cast(Any, object()))
    with pytest.raises(SchemaValidationError):
        validate_safety_policy(
            replace(DEFAULT_PHASE2_SAFETY_LIMITS, minimum_heating_target_c=nan),
            DEFAULT_PHASE2_COMMAND_TIMING,
        )
    with pytest.raises(SchemaValidationError):
        validate_safety_policy(
            DEFAULT_PHASE2_SAFETY_LIMITS,
            replace(DEFAULT_PHASE2_COMMAND_TIMING, target_deadband_c=0),
        )


@pytest.mark.parametrize(
    ("changes", "path"),
    [
        ({"now_utc": NOW.replace(tzinfo=None)}, "now_utc"),
        ({"now_utc": NOW.astimezone(timezone(timedelta(hours=-4)))}, "now_utc"),
        (
            {"now_utc": NOW - timedelta(seconds=2)},
            "candidate.created_at_utc",
        ),
        (
            {
                "current_state": _state(
                    observed_at=NOW + timedelta(seconds=1),
                )
            },
            "current_state.observed_at_utc",
        ),
        ({"correlation_state": "clear"}, "correlation_state"),
    ],
)
def test_gate_rejects_malformed_clock_and_evaluation_inputs(
    changes: dict[str, Any],
    path: str,
) -> None:
    value = _input()
    with pytest.raises(SchemaValidationError, match=path):
        evaluate_safety_gate(replace(value, **changes))


def test_gate_rejects_evidence_in_wrong_scope_or_shape() -> None:
    with pytest.raises(SchemaValidationError, match="arbitration"):
        evaluate_safety_gate(_input(arbitration=_arbitration()))
    with pytest.raises(SchemaValidationError, match="fan"):
        evaluate_safety_gate(
            _input(
                fan=SafetyFanEvidence(
                    FanSafetyOperation.START,
                    _fan_binding(),
                    _fan_evaluation(FanDirective.START),
                )
            )
        )
    fan_request = _fan_candidate(CommandKind.FAN_ON)
    malformed = SafetyFanEvidence(
        FanSafetyOperation.RESTORE,
        _fan_binding(),
        _fan_evaluation(FanDirective.STOP),
        None,
    )
    with pytest.raises(SchemaValidationError, match=r"fan\.restore"):
        evaluate_safety_gate(
            _input(
                candidate=fan_request,
                capabilities=_fan_capabilities(),
                authority=_scheduled_authority(),
                fan=malformed,
            )
        )


def test_public_validators_accept_canonical_records() -> None:
    validate_safety_candidate(_candidate())
    validate_safety_ownership(_ownership())
    validate_safety_capabilities(_capabilities())
    validate_safety_authority(_authority())
    validate_safety_timing(_timing())
    validate_safety_policy(
        DEFAULT_PHASE2_SAFETY_LIMITS,
        DEFAULT_PHASE2_COMMAND_TIMING,
    )


def test_gate_rejects_wrong_top_level_and_optional_evidence_types() -> None:
    with pytest.raises(SchemaValidationError, match="safety_gate"):
        evaluate_safety_gate(cast(Any, object()))
    with pytest.raises(SchemaValidationError, match="arbitration"):
        evaluate_safety_gate(replace(_input(), arbitration=cast(Any, object())))
    with pytest.raises(SchemaValidationError, match="fan"):
        evaluate_safety_gate(replace(_input(), fan=cast(Any, object())))


@pytest.mark.parametrize(
    ("changes", "path"),
    [
        ({"operation": "start"}, "fan.operation"),
        ({"binding": object()}, "fan.binding"),
        ({"evaluation": object()}, "fan.evaluation"),
        ({"restore": object()}, "fan.restore"),
    ],
)
def test_gate_rejects_malformed_fan_evidence(
    changes: dict[str, Any],
    path: str,
) -> None:
    evidence = SafetyFanEvidence(
        operation=FanSafetyOperation.START,
        binding=_fan_binding(),
        evaluation=_fan_evaluation(FanDirective.START),
    )
    malformed = _invalid_copy(evidence, **changes)
    with pytest.raises(SchemaValidationError, match=path):
        evaluate_safety_gate(
            _input(
                candidate=_fan_candidate(CommandKind.FAN_ON),
                capabilities=_fan_capabilities(),
                authority=_scheduled_authority(),
                fan=malformed,
            )
        )


def test_nonrestore_fan_evidence_rejects_restore_record() -> None:
    restore = FanRestoreDecision(
        eligible=True,
        reason_code=FanRestoreReasonCode.ELIGIBLE,
        restore_mode="auto",
    )
    evidence = SafetyFanEvidence(
        FanSafetyOperation.START,
        _fan_binding(),
        _fan_evaluation(FanDirective.START),
        restore,
    )
    with pytest.raises(SchemaValidationError, match=r"fan\.restore"):
        evaluate_safety_gate(
            _input(
                candidate=_fan_candidate(CommandKind.FAN_ON),
                capabilities=_fan_capabilities(),
                authority=_scheduled_authority(),
                fan=evidence,
            )
        )


def test_separate_fan_kind_requires_fan_entity_domain() -> None:
    request = _candidate(
        command_kind=CommandKind.FAN_ON,
        requested_fields=frozenset({CommandControlledField.FAN_STATE}),
        requested_values=NormalizedCommandValues(fan_state="on"),
        target_direction=None,
        observed_precondition=_state(values=NormalizedCommandValues(fan_state="off")),
    )
    _assert_reason(
        _input(candidate=request),
        SafetyReasonCode.ENTITY_DOMAIN_INVALID,
        SafetyDisposition.BLOCKED,
    )


def test_range_requires_heat_cool_capability() -> None:
    request = _candidate(
        command_kind=CommandKind.SET_RANGE,
        requested_fields=frozenset({CommandControlledField.RANGE}),
        requested_values=NormalizedCommandValues(
            heat_target_c=19.0,
            cool_target_c=24.0,
        ),
        target_direction=None,
        observed_precondition=_state(
            values=NormalizedCommandValues(
                heat_target_c=18.0,
                cool_target_c=25.0,
            )
        ),
    )
    capabilities = _capabilities(hvac_modes=("off", "heat", "cool"))
    _assert_reason(
        _input(candidate=request, capabilities=capabilities),
        SafetyReasonCode.HVAC_MODE_UNSUPPORTED,
        SafetyDisposition.BLOCKED,
    )


def test_shadow_control_state_must_be_a_shadow_state() -> None:
    request = _candidate(
        authority=CommandAuthority.SCHEDULED,
        cause=CommandCause.SCHEDULE,
    )
    authority = _scheduled_authority(
        shadow=True,
        state=ControlExecutionState.SCHEDULED_PENDING,
    )
    _assert_reason(
        _input(candidate=request, authority=authority),
        SafetyReasonCode.CONTROL_STATE_BLOCKED,
        SafetyDisposition.BLOCKED,
    )


@pytest.mark.parametrize(
    ("kind", "values", "precondition", "direction"),
    [
        (
            CommandKind.SET_RANGE,
            NormalizedCommandValues(
                heat_target_c=19.0,
                cool_target_c=24.0,
            ),
            NormalizedCommandValues(
                heat_target_c=18.0,
                cool_target_c=25.0,
            ),
            None,
        ),
        (
            CommandKind.SET_HVAC_MODE,
            NormalizedCommandValues(hvac_mode="heat"),
            NormalizedCommandValues(hvac_mode="off"),
            ZoneDemandDirection.HEAT,
        ),
        (
            CommandKind.SET_HVAC_MODE,
            NormalizedCommandValues(hvac_mode="cool"),
            NormalizedCommandValues(hvac_mode="off"),
            ZoneDemandDirection.COOL,
        ),
        (
            CommandKind.SET_HVAC_MODE,
            NormalizedCommandValues(hvac_mode="off"),
            NormalizedCommandValues(hvac_mode="heat"),
            None,
        ),
    ],
)
def test_shared_candidate_direction_is_complete_and_fail_closed(
    kind: CommandKind,
    values: NormalizedCommandValues,
    precondition: NormalizedCommandValues,
    direction: ZoneDemandDirection | None,
) -> None:
    field = (
        CommandControlledField.RANGE
        if kind is CommandKind.SET_RANGE
        else CommandControlledField.HVAC_MODE
    )
    request = _candidate(
        command_kind=kind,
        requested_fields=frozenset({field}),
        requested_values=values,
        target_direction=None,
        authority=CommandAuthority.SCHEDULED,
        cause=CommandCause.SCHEDULE,
        observed_precondition=_state(values=precondition),
    )
    ownership = _ownership(
        relationship=EquipmentRelationship.SHARED_ZONED,
        zone_ids=(ZONE_ID, OTHER_ZONE_ID),
        owned_entity_ids=(CLIMATE, SECONDARY),
    )
    arbitration = _arbitration(
        direction=direction or ZoneDemandDirection.HEAT,
        target=None,
    )
    result = evaluate_safety_gate(
        _input(
            candidate=request,
            ownership=ownership,
            authority=_scheduled_authority(),
            arbitration=arbitration,
            timing=(
                _timing(
                    runtime_started_at_utc=NOW - timedelta(minutes=20),
                    last_mode_change_at_utc=NOW - timedelta(minutes=15),
                )
                if precondition.hvac_mode in {"heat", "cool"}
                and values.hvac_mode in {"heat", "cool"}
                and precondition.hvac_mode != values.hvac_mode
                else _timing()
            ),
        )
    )
    if direction is None:
        assert result.reason_code is SafetyReasonCode.ARBITRATION_MISMATCH
    else:
        assert result.eligible


def test_remaining_validation_branches_fail_closed() -> None:
    invalid_ownership = (
        _invalid_copy(_ownership(), zone_ids=(cast(Any, "bad"),)),
        _invalid_copy(_ownership(), owned_entity_ids=["climate.bad"]),
        _invalid_copy(_ownership(), owned_entity_ids=("climatebad",)),
    )
    for value in invalid_ownership:
        with pytest.raises(SchemaValidationError):
            validate_safety_ownership(value)

    fan_with_climate_command = _invalid_copy(
        _fan_capabilities(),
        supported_command_kinds=frozenset({CommandKind.SET_HVAC_MODE}),
    )
    with pytest.raises(SchemaValidationError):
        validate_safety_capabilities(fan_with_climate_command)

    invalid_limits = (
        replace(
            DEFAULT_PHASE2_SAFETY_LIMITS,
            emergency_protection_enabled=cast(Any, 1),
        ),
        replace(
            DEFAULT_PHASE2_SAFETY_LIMITS,
            minimum_heating_target_c=26.7,
        ),
        replace(
            DEFAULT_PHASE2_SAFETY_LIMITS,
            minimum_cooling_target_c=35.0,
        ),
        replace(
            DEFAULT_PHASE2_SAFETY_LIMITS,
            minimum_heat_cool_separation_c=0.0,
        ),
        replace(
            DEFAULT_PHASE2_SAFETY_LIMITS,
            emergency_low_target_c=33.0,
        ),
    )
    for limits in invalid_limits:
        with pytest.raises(SchemaValidationError):
            validate_safety_policy(limits, DEFAULT_PHASE2_COMMAND_TIMING)

    invalid_timings = (
        replace(
            DEFAULT_PHASE2_COMMAND_TIMING,
            automatic_minimum_interval_seconds=0,
        ),
        replace(DEFAULT_PHASE2_COMMAND_TIMING, target_deadband_c=nan),
        replace(
            DEFAULT_PHASE2_COMMAND_TIMING,
            startup_quiet_period_seconds=119,
        ),
    )
    for timing in invalid_timings:
        with pytest.raises(SchemaValidationError):
            validate_safety_policy(DEFAULT_PHASE2_SAFETY_LIMITS, timing)

    with pytest.raises(SchemaValidationError, match="target_direction"):
        _candidate(
            command_kind=CommandKind.SET_HVAC_MODE,
            requested_fields=frozenset({CommandControlledField.HVAC_MODE}),
            requested_values=NormalizedCommandValues(hvac_mode="heat"),
            target_direction=SafetyTargetDirection.HEAT,
            observed_precondition=_state(
                values=NormalizedCommandValues(hvac_mode="off")
            ),
        )
    with pytest.raises(SchemaValidationError, match="must use UTC"):
        _candidate(created_at_utc=NOW.astimezone(timezone(timedelta(hours=-4))))
