"""Pure legal-transition enforcement for Phase 2 control execution."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from types import MappingProxyType
from typing import Final

from ..models.control import ControlExecutionState, ControlReason
from .precedence import (
    ControlPrecedenceDecision,
    ObservationDirective,
    observation_directive_for_state,
)

_SAFE_SUPPRESSION_STATES: Final = frozenset(
    {
        ControlExecutionState.DISABLED,
        ControlExecutionState.OBSERVING,
        ControlExecutionState.SAFE_FALLBACK,
        ControlExecutionState.EMERGENCY_PAUSED,
        ControlExecutionState.DEGRADED,
    }
)
_AUTOMATIC_STATES: Final = frozenset(
    {
        ControlExecutionState.SHADOW_QUALIFYING,
        ControlExecutionState.SHADOW_READY,
        ControlExecutionState.SCHEDULED_IDLE,
        ControlExecutionState.SCHEDULED_PENDING,
        ControlExecutionState.COMMAND_AWAITING_ACK,
        ControlExecutionState.MANUAL_OVERRIDE,
        ControlExecutionState.WINDOW_SUSPENDED,
        ControlExecutionState.OCCUPANCY_HOLD,
        ControlExecutionState.SHARED_CONFLICT_HOLD,
        ControlExecutionState.EMERGENCY_PROTECTION,
    }
)
_ACTIVE_RECOVERY_TARGETS: Final = frozenset(
    {
        ControlExecutionState.MANUAL_IDLE,
        *_AUTOMATIC_STATES,
    }
)
_SAFETY_EXITS: Final = frozenset(
    {
        ControlExecutionState.RECONCILING,
        ControlExecutionState.DISABLED,
        ControlExecutionState.OBSERVING,
        ControlExecutionState.SAFE_FALLBACK,
        ControlExecutionState.EMERGENCY_PAUSED,
        ControlExecutionState.DEGRADED,
        ControlExecutionState.UNLOADING,
    }
)
_MODE_SELECTIONS: Final = frozenset(
    {
        ControlExecutionState.OBSERVING,
        ControlExecutionState.MANUAL_IDLE,
        ControlExecutionState.SHADOW_QUALIFYING,
        ControlExecutionState.SHADOW_READY,
    }
)
_SCHEDULED_EFFECTS: Final = frozenset(
    {
        ControlExecutionState.SCHEDULED_IDLE,
        ControlExecutionState.SCHEDULED_PENDING,
        ControlExecutionState.MANUAL_OVERRIDE,
        ControlExecutionState.WINDOW_SUSPENDED,
        ControlExecutionState.OCCUPANCY_HOLD,
        ControlExecutionState.SHARED_CONFLICT_HOLD,
        ControlExecutionState.EMERGENCY_PROTECTION,
    }
)


def _with_self(
    state: ControlExecutionState,
    targets: frozenset[ControlExecutionState],
) -> frozenset[ControlExecutionState]:
    return targets | {state}


LEGAL_CONTROL_TRANSITIONS = MappingProxyType(
    {
        ControlExecutionState.UNLOADED: frozenset(
            {
                ControlExecutionState.UNLOADED,
                ControlExecutionState.INITIALIZING,
            }
        ),
        ControlExecutionState.INITIALIZING: _with_self(
            ControlExecutionState.INITIALIZING,
            frozenset(
                {
                    ControlExecutionState.RECONCILING,
                    ControlExecutionState.DISABLED,
                    ControlExecutionState.SAFE_FALLBACK,
                    ControlExecutionState.EMERGENCY_PAUSED,
                    ControlExecutionState.UNLOADING,
                }
            ),
        ),
        ControlExecutionState.RECONCILING: _with_self(
            ControlExecutionState.RECONCILING,
            _MODE_SELECTIONS
            | _SAFE_SUPPRESSION_STATES
            | {ControlExecutionState.UNLOADING},
        ),
        ControlExecutionState.DISABLED: _with_self(
            ControlExecutionState.DISABLED,
            _MODE_SELECTIONS | _SAFETY_EXITS,
        ),
        ControlExecutionState.OBSERVING: _with_self(
            ControlExecutionState.OBSERVING,
            _MODE_SELECTIONS | _SAFETY_EXITS,
        ),
        ControlExecutionState.MANUAL_IDLE: _with_self(
            ControlExecutionState.MANUAL_IDLE,
            _MODE_SELECTIONS
            | _SAFETY_EXITS
            | {ControlExecutionState.COMMAND_AWAITING_ACK},
        ),
        ControlExecutionState.SHADOW_QUALIFYING: _with_self(
            ControlExecutionState.SHADOW_QUALIFYING,
            _MODE_SELECTIONS | _SCHEDULED_EFFECTS | _SAFETY_EXITS,
        ),
        ControlExecutionState.SHADOW_READY: _with_self(
            ControlExecutionState.SHADOW_READY,
            _MODE_SELECTIONS | _SCHEDULED_EFFECTS | _SAFETY_EXITS,
        ),
        ControlExecutionState.SCHEDULED_IDLE: _with_self(
            ControlExecutionState.SCHEDULED_IDLE,
            _MODE_SELECTIONS
            | _SCHEDULED_EFFECTS
            | _SAFETY_EXITS
            | {ControlExecutionState.COMMAND_AWAITING_ACK},
        ),
        ControlExecutionState.SCHEDULED_PENDING: _with_self(
            ControlExecutionState.SCHEDULED_PENDING,
            _MODE_SELECTIONS
            | _SCHEDULED_EFFECTS
            | _SAFETY_EXITS
            | {ControlExecutionState.COMMAND_AWAITING_ACK},
        ),
        ControlExecutionState.COMMAND_AWAITING_ACK: _with_self(
            ControlExecutionState.COMMAND_AWAITING_ACK,
            _MODE_SELECTIONS | _SCHEDULED_EFFECTS | _SAFETY_EXITS,
        ),
        ControlExecutionState.MANUAL_OVERRIDE: _with_self(
            ControlExecutionState.MANUAL_OVERRIDE,
            _MODE_SELECTIONS | _SCHEDULED_EFFECTS | _SAFETY_EXITS,
        ),
        ControlExecutionState.WINDOW_SUSPENDED: _with_self(
            ControlExecutionState.WINDOW_SUSPENDED,
            _MODE_SELECTIONS | _SCHEDULED_EFFECTS | _SAFETY_EXITS,
        ),
        ControlExecutionState.OCCUPANCY_HOLD: _with_self(
            ControlExecutionState.OCCUPANCY_HOLD,
            _MODE_SELECTIONS | _SCHEDULED_EFFECTS | _SAFETY_EXITS,
        ),
        ControlExecutionState.SHARED_CONFLICT_HOLD: _with_self(
            ControlExecutionState.SHARED_CONFLICT_HOLD,
            _MODE_SELECTIONS | _SCHEDULED_EFFECTS | _SAFETY_EXITS,
        ),
        ControlExecutionState.EMERGENCY_PROTECTION: _with_self(
            ControlExecutionState.EMERGENCY_PROTECTION,
            _MODE_SELECTIONS | _SCHEDULED_EFFECTS | _SAFETY_EXITS,
        ),
        ControlExecutionState.SAFE_FALLBACK: _with_self(
            ControlExecutionState.SAFE_FALLBACK,
            _MODE_SELECTIONS | _ACTIVE_RECOVERY_TARGETS | _SAFETY_EXITS,
        ),
        ControlExecutionState.EMERGENCY_PAUSED: _with_self(
            ControlExecutionState.EMERGENCY_PAUSED,
            frozenset(
                {
                    ControlExecutionState.DISABLED,
                    ControlExecutionState.RECONCILING,
                    ControlExecutionState.SAFE_FALLBACK,
                    ControlExecutionState.UNLOADING,
                }
            ),
        ),
        ControlExecutionState.DEGRADED: _with_self(
            ControlExecutionState.DEGRADED,
            _MODE_SELECTIONS | _ACTIVE_RECOVERY_TARGETS | _SAFETY_EXITS,
        ),
        ControlExecutionState.UNLOADING: frozenset(
            {
                ControlExecutionState.UNLOADING,
                ControlExecutionState.UNLOADED,
            }
        ),
    }
)


@dataclass(frozen=True, slots=True)
class RecoveryEvidence:
    """Injected evidence required before degraded/fallback active recovery."""

    healthy_evaluations: int = 0
    elapsed_seconds: float = 0.0
    cooldown_complete: bool = False

    def __post_init__(self) -> None:
        """Reject impossible recovery evidence."""
        if (
            not isinstance(self.healthy_evaluations, int)
            or isinstance(self.healthy_evaluations, bool)
            or self.healthy_evaluations < 0
        ):
            raise ValueError("healthy_evaluations must be a nonnegative integer")
        if (
            not isinstance(self.elapsed_seconds, int | float)
            or isinstance(self.elapsed_seconds, bool)
            or not isfinite(self.elapsed_seconds)
            or self.elapsed_seconds < 0
        ):
            raise ValueError("elapsed_seconds must be a nonnegative finite number")
        if not isinstance(self.cooldown_complete, bool):
            raise ValueError("cooldown_complete must be a boolean")

    @property
    def permits_active_recovery(self) -> bool:
        """Return whether the two-evaluation/30-second/cooldown gate passed."""
        return (
            self.healthy_evaluations >= 2
            and self.elapsed_seconds >= 30
            and self.cooldown_complete
        )


@dataclass(frozen=True, slots=True)
class ControlTransition:
    """One immutable state transition outcome."""

    previous_state: ControlExecutionState
    state: ControlExecutionState
    reason: ControlReason
    observation: ObservationDirective
    changed: bool
    invariant_violation: bool

    @property
    def observation_continues(self) -> bool:
        """Return whether observation remains active after the transition."""
        return self.observation is ObservationDirective.CONTINUE


def transition_control_state(
    current: ControlExecutionState,
    decision: ControlPrecedenceDecision,
    *,
    recovery: RecoveryEvidence | None = None,
    emergency_resume_authorized: bool = False,
) -> ControlTransition:
    """Apply recovery, pause, and legal-transition gates to one decision."""
    if current is ControlExecutionState.EMERGENCY_PAUSED and decision.state not in {
        ControlExecutionState.EMERGENCY_PAUSED,
        ControlExecutionState.DISABLED,
        ControlExecutionState.SAFE_FALLBACK,
        ControlExecutionState.UNLOADING,
    }:
        if not emergency_resume_authorized:
            return _transition(
                current,
                ControlExecutionState.EMERGENCY_PAUSED,
                ControlReason.EMERGENCY_PAUSE,
            )
        return _transition(
            current,
            ControlExecutionState.RECONCILING,
            ControlReason.HEALTHY_RECOVERY,
        )

    if (
        current
        in {
            ControlExecutionState.SAFE_FALLBACK,
            ControlExecutionState.DEGRADED,
        }
        and decision.state in _ACTIVE_RECOVERY_TARGETS
    ):
        evidence = recovery or RecoveryEvidence()
        if not evidence.permits_active_recovery:
            return _transition(current, current, ControlReason.RECOVERY_PENDING)
        decision = ControlPrecedenceDecision(
            state=decision.state,
            reason=ControlReason.HEALTHY_RECOVERY,
            observation=decision.observation,
        )

    if decision.state not in LEGAL_CONTROL_TRANSITIONS[current]:
        return _transition(
            current,
            ControlExecutionState.SAFE_FALLBACK,
            ControlReason.ILLEGAL_TRANSITION,
            invariant_violation=True,
        )
    return _transition(current, decision.state, decision.reason)


def is_legal_control_transition(
    current: ControlExecutionState,
    target: ControlExecutionState,
) -> bool:
    """Return whether the static transition table permits a state pair."""
    return target in LEGAL_CONTROL_TRANSITIONS[current]


def _transition(
    previous: ControlExecutionState,
    state: ControlExecutionState,
    reason: ControlReason,
    *,
    invariant_violation: bool = False,
) -> ControlTransition:
    return ControlTransition(
        previous_state=previous,
        state=state,
        reason=reason,
        observation=observation_directive_for_state(state),
        changed=previous is not state,
        invariant_violation=invariant_violation,
    )
