"""Test the pure Task 9 control-precedence and manual-authority policies."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from itertools import combinations
from typing import Any

import pytest

from custom_components.intelligent_climate.control.precedence import (
    ControlPrecedenceInput,
    ManualIntentRequest,
    ManualIntentResultCode,
    ManualIntentSource,
    ObservationDirective,
    evaluate_manual_intent_authority,
    observation_directive_for_state,
    resolve_control_precedence,
)
from custom_components.intelligent_climate.models import (
    ControlExecutionState,
    ControlReason,
    OperatingMode,
)


def _scheduled_input(**changes: Any) -> ControlPrecedenceInput:
    value = ControlPrecedenceInput(
        operating_mode=OperatingMode.SCHEDULED_CONTROL,
        automation_enabled=True,
        shadow_qualified=True,
        active_control_armed=True,
    )
    return replace(value, **changes)


@pytest.mark.parametrize(
    ("changes", "state", "reason", "observation"),
    [
        (
            {"loaded": False},
            ControlExecutionState.UNLOADED,
            ControlReason.UNLOAD,
            ObservationDirective.STOP,
        ),
        (
            {"unloading": True},
            ControlExecutionState.UNLOADING,
            ControlReason.UNLOAD,
            ObservationDirective.CONTINUE,
        ),
        (
            {"initializing": True},
            ControlExecutionState.INITIALIZING,
            ControlReason.STARTUP,
            ObservationDirective.CONTINUE,
        ),
    ],
)
def test_lifecycle_precedence_is_deterministic_and_observation_safe(
    changes: dict[str, Any],
    state: ControlExecutionState,
    reason: ControlReason,
    observation: ObservationDirective,
) -> None:
    """Lifecycle decisions precede loaded control policy without hidden effects."""
    decision = resolve_control_precedence(_scheduled_input(**changes))

    assert decision.state is state
    assert decision.reason is reason
    assert decision.observation is observation
    assert decision.observation_continues is (
        observation is ObservationDirective.CONTINUE
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"configuration_valid": False},
        {"migration_valid": False},
        {"future_schema_supported": False},
    ],
)
def test_invalid_authoritative_state_always_fails_closed(
    changes: dict[str, Any],
) -> None:
    """Invalid, partial, or future authoritative data cannot select control."""
    decision = resolve_control_precedence(
        _scheduled_input(
            emergency_paused=True,
            failure_lockout=True,
            **changes,
        )
    )

    assert decision.state is ControlExecutionState.SAFE_FALLBACK
    assert decision.reason is ControlReason.CONFIGURATION_INVALID
    assert decision.observation_continues


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"automation_enabled": False}, ControlReason.CONFIGURATION_INVALID),
        (
            {
                "operating_mode": OperatingMode.MANUAL_CONTROL,
                "automation_enabled": False,
                "active_control_armed": True,
            },
            ControlReason.CONFIGURATION_INVALID,
        ),
        (
            {"control_authority_valid": False},
            ControlReason.COMMAND_AUTHORITY_INVALID,
        ),
        ({"schedule_available": False}, ControlReason.SCHEDULE_UNAVAILABLE),
    ],
)
def test_invalid_mode_authority_combinations_fail_before_runtime_policy(
    changes: dict[str, Any],
    reason: ControlReason,
) -> None:
    """Mode/config contradictions never become a weaker runtime warning."""
    decision = resolve_control_precedence(_scheduled_input(**changes))

    assert decision.state is ControlExecutionState.SAFE_FALLBACK
    assert decision.reason is reason


_PRECEDENCE_CASES = (
    (
        {"configuration_valid": False},
        ControlExecutionState.SAFE_FALLBACK,
        ControlReason.CONFIGURATION_INVALID,
    ),
    (
        {"emergency_paused": True},
        ControlExecutionState.EMERGENCY_PAUSED,
        ControlReason.EMERGENCY_PAUSE,
    ),
    (
        {"reconciling": True},
        ControlExecutionState.RECONCILING,
        ControlReason.STARTUP,
    ),
    (
        {"time_zone_acknowledgement_required": True},
        ControlExecutionState.RECONCILING,
        ControlReason.TIME_ZONE_REVIEW_REQUIRED,
    ),
    (
        {"failure_lockout": True},
        ControlExecutionState.EMERGENCY_PAUSED,
        ControlReason.FAILURE_LOCKOUT,
    ),
    (
        {"command_uncertain": True},
        ControlExecutionState.SAFE_FALLBACK,
        ControlReason.COMMAND_UNCERTAIN,
    ),
    (
        {"command_awaiting_ack": True},
        ControlExecutionState.COMMAND_AWAITING_ACK,
        ControlReason.COMMAND_AWAITING_ACK,
    ),
    (
        {"thermostat_available": False},
        ControlExecutionState.DEGRADED,
        ControlReason.THERMOSTAT_UNAVAILABLE,
    ),
    (
        {"capability_valid": False},
        ControlExecutionState.SAFE_FALLBACK,
        ControlReason.CAPABILITY_INVALID,
    ),
    (
        {"required_autonomous_sensors_valid": False},
        ControlExecutionState.DEGRADED,
        ControlReason.REQUIRED_SENSOR_INVALID,
    ),
    (
        {"emergency_protection_active": True},
        ControlExecutionState.EMERGENCY_PROTECTION,
        ControlReason.EMERGENCY_PROTECTION,
    ),
    (
        {"manual_override_active": True},
        ControlExecutionState.MANUAL_OVERRIDE,
        ControlReason.MANUAL_OVERRIDE_ACTIVE,
    ),
    (
        {"window_suspended": True},
        ControlExecutionState.WINDOW_SUSPENDED,
        ControlReason.WINDOW_OPEN,
    ),
    (
        {"shared_conflict_hold": True},
        ControlExecutionState.SHARED_CONFLICT_HOLD,
        ControlReason.SHARED_EQUIPMENT_CONFLICT,
    ),
    (
        {"occupancy_hold": True},
        ControlExecutionState.OCCUPANCY_HOLD,
        ControlReason.OCCUPANCY_HOLD,
    ),
    (
        {"shadow_qualified": False},
        ControlExecutionState.SHADOW_QUALIFYING,
        ControlReason.SHADOW_QUALIFYING,
    ),
    (
        {"active_control_armed": False},
        ControlExecutionState.SHADOW_READY,
        ControlReason.SHADOW_READY,
    ),
    (
        {"schedule_plan_pending": True},
        ControlExecutionState.SCHEDULED_PENDING,
        ControlReason.COMMAND_PLANNED,
    ),
)


@pytest.mark.parametrize(
    ("higher_index", "lower_index"),
    combinations(range(len(_PRECEDENCE_CASES)), 2),
)
def test_every_precedence_pair_selects_the_higher_condition(
    higher_index: int,
    lower_index: int,
) -> None:
    """Every pair in the fixed table resolves to the earlier safety condition."""
    higher_changes, expected_state, expected_reason = _PRECEDENCE_CASES[higher_index]
    lower_changes, _, _ = _PRECEDENCE_CASES[lower_index]
    combined = {**lower_changes, **higher_changes}

    decision = resolve_control_precedence(_scheduled_input(**combined))

    assert decision.state is expected_state
    assert decision.reason is expected_reason


def test_normal_scheduled_and_shadow_modes_never_skip_qualification_or_arming() -> None:
    """Qualification and explicit arming remain separate authority gates."""
    active = resolve_control_precedence(_scheduled_input())
    shadow_ready = resolve_control_precedence(
        _scheduled_input(
            operating_mode=OperatingMode.SCHEDULED_SHADOW,
            active_control_armed=False,
        )
    )
    shadow_qualifying = resolve_control_precedence(
        _scheduled_input(
            operating_mode=OperatingMode.SCHEDULED_SHADOW,
            active_control_armed=False,
            shadow_qualified=False,
        )
    )
    scheduled_pending = resolve_control_precedence(
        _scheduled_input(schedule_plan_pending=True)
    )

    assert active.state is ControlExecutionState.SCHEDULED_IDLE
    assert active.reason is ControlReason.SCHEDULE_EVALUATION
    assert shadow_ready.state is ControlExecutionState.SHADOW_READY
    assert shadow_qualifying.state is ControlExecutionState.SHADOW_QUALIFYING
    assert scheduled_pending.state is ControlExecutionState.SCHEDULED_PENDING
    assert scheduled_pending.reason is ControlReason.COMMAND_PLANNED


def test_disabled_manual_and_observe_intents_disable_autonomous_policy() -> None:
    """User-selected nonautomatic modes win over every lower autonomous overlay."""
    overlays = {
        "required_autonomous_sensors_valid": False,
        "emergency_protection_active": True,
        "manual_override_active": True,
        "window_suspended": True,
        "shared_conflict_hold": True,
        "occupancy_hold": True,
    }
    disabled = resolve_control_precedence(
        _scheduled_input(
            operating_mode=OperatingMode.DISABLED,
            automation_enabled=False,
            active_control_armed=False,
            **overlays,
        )
    )
    manual = resolve_control_precedence(
        _scheduled_input(
            operating_mode=OperatingMode.MANUAL_CONTROL,
            automation_enabled=False,
            active_control_armed=False,
            **overlays,
        )
    )
    observe = resolve_control_precedence(
        _scheduled_input(
            operating_mode=OperatingMode.OBSERVE_ONLY,
            automation_enabled=False,
            active_control_armed=False,
            required_autonomous_sensors_valid=True,
            emergency_protection_active=True,
            manual_override_active=True,
            window_suspended=True,
            shared_conflict_hold=True,
            occupancy_hold=True,
        )
    )

    assert disabled.state is ControlExecutionState.DISABLED
    assert manual.state is ControlExecutionState.MANUAL_IDLE
    assert manual.reason is ControlReason.MANUAL_CONTROL_SELECTED
    assert observe.state is ControlExecutionState.OBSERVING
    assert observe.reason is ControlReason.OBSERVE_ONLY_SELECTED
    assert all(
        decision.observation_continues for decision in (disabled, manual, observe)
    )


def test_observe_only_still_reports_required_sensor_degradation() -> None:
    """Permanent observation stays active while its data quality remains honest."""
    decision = resolve_control_precedence(
        _scheduled_input(
            operating_mode=OperatingMode.OBSERVE_ONLY,
            automation_enabled=False,
            active_control_armed=False,
            required_autonomous_sensors_valid=False,
        )
    )

    assert decision.state is ControlExecutionState.DEGRADED
    assert decision.reason is ControlReason.REQUIRED_SENSOR_INVALID
    assert decision.observation_continues


@pytest.mark.parametrize(
    ("changes", "code"),
    [
        (
            {"operating_mode": OperatingMode.OBSERVE_ONLY},
            ManualIntentResultCode.WRONG_MODE,
        ),
        (
            {"control_state": ControlExecutionState.COMMAND_AWAITING_ACK},
            ManualIntentResultCode.SUPPRESSED_STATE,
        ),
        (
            {"source": ManualIntentSource.SENSOR},
            ManualIntentResultCode.EXPLICIT_USER_REQUIRED,
        ),
        (
            {"authenticated_user": False},
            ManualIntentResultCode.AUTHENTICATED_USER_REQUIRED,
        ),
        ({"fresh": False}, ManualIntentResultCode.FRESH_INTENT_REQUIRED),
        (
            {"observed_revision_matches": False},
            ManualIntentResultCode.CURRENT_REVISION_REQUIRED,
        ),
    ],
)
def test_manual_intent_gate_fails_closed_in_stable_order(
    changes: dict[str, Any],
    code: ManualIntentResultCode,
) -> None:
    """Each missing authority fact rejects without falling through."""
    request = ManualIntentRequest(
        operating_mode=OperatingMode.MANUAL_CONTROL,
        control_state=ControlExecutionState.MANUAL_IDLE,
        source=ManualIntentSource.EXPLICIT_USER,
        authenticated_user=True,
        fresh=True,
        observed_revision_matches=True,
    )

    decision = evaluate_manual_intent_authority(replace(request, **changes))

    assert decision.authorized is False
    assert decision.code is code


@pytest.mark.parametrize(
    "source",
    [
        source
        for source in ManualIntentSource
        if source is not ManualIntentSource.EXPLICIT_USER
    ],
)
def test_every_autonomous_or_lifecycle_source_lacks_manual_authority(
    source: ManualIntentSource,
) -> None:
    """No sensor, schedule, timer, restart, or policy event can impersonate a user."""
    decision = evaluate_manual_intent_authority(
        ManualIntentRequest(
            operating_mode=OperatingMode.MANUAL_CONTROL,
            control_state=ControlExecutionState.MANUAL_IDLE,
            source=source,
            authenticated_user=True,
            fresh=True,
            observed_revision_matches=True,
        )
    )

    assert decision == (
        type(decision)(
            authorized=False,
            code=ManualIntentResultCode.EXPLICIT_USER_REQUIRED,
        )
    )


def test_fresh_current_user_intent_is_authorized_but_not_executed() -> None:
    """Task 9 grants authority only; it creates no command plan or physical call."""
    decision = evaluate_manual_intent_authority(
        ManualIntentRequest(
            operating_mode=OperatingMode.MANUAL_CONTROL,
            control_state=ControlExecutionState.MANUAL_IDLE,
            source=ManualIntentSource.EXPLICIT_USER,
            authenticated_user=True,
            fresh=True,
            observed_revision_matches=True,
        )
    )

    assert decision.authorized
    assert decision.code is ManualIntentResultCode.AUTHORIZED


def test_observation_directive_stops_only_after_entry_is_unloaded() -> None:
    """Control suppression never disables observation for a loaded entry."""
    assert {
        state
        for state in ControlExecutionState
        if observation_directive_for_state(state) is ObservationDirective.STOP
    } == {ControlExecutionState.UNLOADED}


def test_precedence_models_are_immutable() -> None:
    """Authority inputs and outputs cannot be mutated between policy stages."""
    value = _scheduled_input()
    decision = resolve_control_precedence(value)

    with pytest.raises(FrozenInstanceError):
        value.loaded = False  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        decision.reason = ControlReason.DISABLED  # type: ignore[misc]
