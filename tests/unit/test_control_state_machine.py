"""Test Task 9's pure legal-transition and recovery state machine."""

from __future__ import annotations

from itertools import product

import pytest

from custom_components.intelligent_climate.control.precedence import (
    ControlPrecedenceDecision,
    ObservationDirective,
)
from custom_components.intelligent_climate.control.state_machine import (
    LEGAL_CONTROL_TRANSITIONS,
    RecoveryEvidence,
    is_legal_control_transition,
    transition_control_state,
)
from custom_components.intelligent_climate.models import (
    ControlExecutionState,
    ControlReason,
)


def _decision(
    state: ControlExecutionState,
    reason: ControlReason = ControlReason.SCHEDULE_EVALUATION,
) -> ControlPrecedenceDecision:
    return ControlPrecedenceDecision(
        state=state,
        reason=reason,
        observation=(
            ObservationDirective.STOP
            if state is ControlExecutionState.UNLOADED
            else ObservationDirective.CONTINUE
        ),
    )


def test_transition_table_is_total_immutable_and_reflexive() -> None:
    """Every typed state has a table row and may remain stable."""
    assert set(LEGAL_CONTROL_TRANSITIONS) == set(ControlExecutionState)
    assert all(
        state in LEGAL_CONTROL_TRANSITIONS[state] for state in ControlExecutionState
    )
    with pytest.raises(TypeError):
        LEGAL_CONTROL_TRANSITIONS[ControlExecutionState.UNLOADED] = frozenset()  # type: ignore[index]


@pytest.mark.parametrize(
    ("current", "target"),
    product(ControlExecutionState, repeat=2),
)
def test_every_state_pair_matches_the_authoritative_transition_table(
    current: ControlExecutionState,
    target: ControlExecutionState,
) -> None:
    """The public legality helper is exactly the immutable transition table."""
    assert is_legal_control_transition(current, target) is (
        target in LEGAL_CONTROL_TRANSITIONS[current]
    )


def test_ordinary_legal_transition_preserves_reason_and_observation() -> None:
    """A legal precedence result becomes one transparent transition."""
    transition = transition_control_state(
        ControlExecutionState.OBSERVING,
        _decision(
            ControlExecutionState.MANUAL_IDLE,
            ControlReason.MANUAL_CONTROL_SELECTED,
        ),
    )

    assert transition.previous_state is ControlExecutionState.OBSERVING
    assert transition.state is ControlExecutionState.MANUAL_IDLE
    assert transition.reason is ControlReason.MANUAL_CONTROL_SELECTED
    assert transition.changed
    assert not transition.invariant_violation
    assert transition.observation_continues


def test_stable_transition_reports_no_change() -> None:
    """Repeated equivalent evaluations remain explicit without false churn."""
    transition = transition_control_state(
        ControlExecutionState.OBSERVING,
        _decision(
            ControlExecutionState.OBSERVING,
            ControlReason.OBSERVE_ONLY_SELECTED,
        ),
    )

    assert transition.state is ControlExecutionState.OBSERVING
    assert not transition.changed
    assert not transition.invariant_violation


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (ControlExecutionState.UNLOADED, ControlExecutionState.MANUAL_IDLE),
        (ControlExecutionState.OBSERVING, ControlExecutionState.UNLOADED),
        (ControlExecutionState.SCHEDULED_IDLE, ControlExecutionState.INITIALIZING),
        (ControlExecutionState.UNLOADING, ControlExecutionState.OBSERVING),
    ],
)
def test_illegal_transition_fails_closed_and_records_invariant_violation(
    current: ControlExecutionState,
    target: ControlExecutionState,
) -> None:
    """Illegal lifecycle jumps never inherit the requested authority."""
    transition = transition_control_state(current, _decision(target))

    assert transition.previous_state is current
    assert transition.state is ControlExecutionState.SAFE_FALLBACK
    assert transition.reason is ControlReason.ILLEGAL_TRANSITION
    assert transition.invariant_violation
    assert transition.observation_continues


@pytest.mark.parametrize(
    ("evidence", "permitted"),
    [
        (RecoveryEvidence(1, 30, True), False),
        (RecoveryEvidence(2, 29.9, True), False),
        (RecoveryEvidence(2, 30, False), False),
        (RecoveryEvidence(2, 30, True), True),
        (RecoveryEvidence(3, 90, True), True),
    ],
)
def test_recovery_evidence_enforces_every_required_threshold(
    evidence: RecoveryEvidence,
    permitted: bool,
) -> None:
    """Two evaluations, 30 seconds, and cooldown completion are all mandatory."""
    assert evidence.permits_active_recovery is permitted


@pytest.mark.parametrize(
    "current",
    [ControlExecutionState.SAFE_FALLBACK, ControlExecutionState.DEGRADED],
)
def test_active_recovery_waits_then_uses_a_stable_recovery_reason(
    current: ControlExecutionState,
) -> None:
    """Fallback/degraded state cannot jump active on one healthy evaluation."""
    target = _decision(
        ControlExecutionState.SCHEDULED_IDLE,
        ControlReason.SCHEDULE_EVALUATION,
    )

    held = transition_control_state(
        current,
        target,
        recovery=RecoveryEvidence(1, 30, True),
    )
    released = transition_control_state(
        current,
        target,
        recovery=RecoveryEvidence(2, 30, True),
    )

    assert held.state is current
    assert held.reason is ControlReason.RECOVERY_PENDING
    assert not held.changed
    assert released.state is ControlExecutionState.SCHEDULED_IDLE
    assert released.reason is ControlReason.HEALTHY_RECOVERY
    assert released.changed


def test_missing_recovery_evidence_fails_closed() -> None:
    """Callers cannot omit health evidence and accidentally regain authority."""
    transition = transition_control_state(
        ControlExecutionState.SAFE_FALLBACK,
        _decision(ControlExecutionState.MANUAL_IDLE),
    )

    assert transition.state is ControlExecutionState.SAFE_FALLBACK
    assert transition.reason is ControlReason.RECOVERY_PENDING


@pytest.mark.parametrize(
    "target",
    [
        ControlExecutionState.OBSERVING,
        ControlExecutionState.DISABLED,
        ControlExecutionState.RECONCILING,
        ControlExecutionState.UNLOADING,
    ],
)
def test_recovery_evidence_is_not_required_for_nonactive_safe_targets(
    target: ControlExecutionState,
) -> None:
    """A user may remain suppressed or unload without waiting for active recovery."""
    transition = transition_control_state(
        ControlExecutionState.DEGRADED,
        _decision(target, ControlReason.DISABLED),
    )

    assert transition.state is target
    assert transition.reason is ControlReason.DISABLED


def test_emergency_pause_requires_explicit_resume_and_reconciliation() -> None:
    """Resume never jumps directly from pause into an active-capable state."""
    target = _decision(
        ControlExecutionState.MANUAL_IDLE,
        ControlReason.MANUAL_CONTROL_SELECTED,
    )

    held = transition_control_state(ControlExecutionState.EMERGENCY_PAUSED, target)
    resumed = transition_control_state(
        ControlExecutionState.EMERGENCY_PAUSED,
        target,
        emergency_resume_authorized=True,
    )

    assert held.state is ControlExecutionState.EMERGENCY_PAUSED
    assert held.reason is ControlReason.EMERGENCY_PAUSE
    assert resumed.state is ControlExecutionState.RECONCILING
    assert resumed.reason is ControlReason.HEALTHY_RECOVERY


@pytest.mark.parametrize(
    "target",
    [
        ControlExecutionState.EMERGENCY_PAUSED,
        ControlExecutionState.DISABLED,
        ControlExecutionState.SAFE_FALLBACK,
        ControlExecutionState.UNLOADING,
    ],
)
def test_emergency_pause_allows_only_safe_direct_exits(
    target: ControlExecutionState,
) -> None:
    """Remaining paused, disabling, failing closed, and unloading need no resume."""
    transition = transition_control_state(
        ControlExecutionState.EMERGENCY_PAUSED,
        _decision(target, ControlReason.EMERGENCY_PAUSE),
    )

    assert transition.state is target
    assert not transition.invariant_violation


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("healthy_evaluations", -1, "healthy_evaluations"),
        ("healthy_evaluations", True, "healthy_evaluations"),
        ("healthy_evaluations", 1.5, "healthy_evaluations"),
        ("elapsed_seconds", -0.1, "elapsed_seconds"),
        ("elapsed_seconds", True, "elapsed_seconds"),
        ("elapsed_seconds", float("nan"), "elapsed_seconds"),
        ("elapsed_seconds", float("inf"), "elapsed_seconds"),
        ("cooldown_complete", 1, "cooldown_complete"),
    ],
)
def test_recovery_evidence_rejects_impossible_values(
    field: str,
    value: object,
    match: str,
) -> None:
    """Malformed counters, time, and cooldown evidence cannot satisfy recovery."""
    changes = {
        "healthy_evaluations": 0,
        "elapsed_seconds": 0.0,
        "cooldown_complete": False,
        field: value,
    }
    with pytest.raises(ValueError, match=match):
        RecoveryEvidence(**changes)  # type: ignore[arg-type]


def test_unloading_finishes_with_observation_stopping_only_when_unloaded() -> None:
    """Observation persists through teardown and stops at the terminal state."""
    transition = transition_control_state(
        ControlExecutionState.UNLOADING,
        _decision(ControlExecutionState.UNLOADED, ControlReason.UNLOAD),
    )

    assert transition.state is ControlExecutionState.UNLOADED
    assert transition.changed
    assert transition.observation is ObservationDirective.STOP
    assert not transition.observation_continues
