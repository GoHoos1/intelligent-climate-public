"""Test the pure Phase 2 control vocabulary introduced by backlog Task 2."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path
from uuid import UUID

import pytest

from custom_components.intelligent_climate.models import (
    CommandId,
    ContactBindingId,
    ControlExecutionState,
    ControlReason,
    ControlState,
    DecisionId,
    ExecutionContext,
    OccupancyModeId,
    OperatingMode,
    OverrideId,
    SafetyEvaluationId,
    SchedulePeriodId,
    ScheduleProfileId,
    parse_control_execution_state,
    parse_control_reason,
    parse_execution_context,
    parse_operating_mode,
)

ROOT = Path(__file__).parents[2]
INTEGRATION_DIR = ROOT / "custom_components" / "intelligent_climate"


def test_operating_modes_describe_user_intent_without_override_or_simulation() -> None:
    """Manual override is execution state and simulation is an isolated context."""
    assert [mode.value for mode in OperatingMode] == [
        "disabled",
        "observe_only",
        "manual_control",
        "scheduled_shadow",
        "scheduled_control",
    ]
    assert parse_operating_mode("manual_control") is OperatingMode.MANUAL_CONTROL
    assert parse_operating_mode("scheduled_shadow") is OperatingMode.SCHEDULED_SHADOW
    assert parse_operating_mode("scheduled_control") is OperatingMode.SCHEDULED_CONTROL
    with pytest.raises(ValueError):
        parse_operating_mode("manual_override")
    with pytest.raises(ValueError):
        parse_operating_mode("simulation")


def test_control_execution_states_match_the_approved_phase_2_design() -> None:
    """Execution states keep manual, override, shadow, and active states distinct."""
    assert [state.value for state in ControlExecutionState] == [
        "unloaded",
        "initializing",
        "reconciling",
        "disabled",
        "observing",
        "manual_idle",
        "shadow_qualifying",
        "shadow_ready",
        "scheduled_idle",
        "scheduled_pending",
        "command_awaiting_ack",
        "manual_override",
        "window_suspended",
        "occupancy_hold",
        "shared_conflict_hold",
        "emergency_protection",
        "safe_fallback",
        "emergency_paused",
        "degraded",
        "unloading",
    ]
    assert (
        parse_control_execution_state("manual_override")
        is ControlExecutionState.MANUAL_OVERRIDE
    )
    assert (
        parse_control_execution_state("scheduled_pending")
        is ControlExecutionState.SCHEDULED_PENDING
    )
    with pytest.raises(ValueError):
        parse_control_execution_state("predictive_control")


def test_phase_1_persisted_control_states_are_not_silently_extended() -> None:
    """Task 7, not Task 2, owns runtime Store v2 and its migration codec."""
    assert [state.value for state in ControlState] == [
        "unloaded",
        "initializing",
        "reconciling",
        "disabled",
        "observing",
        "degraded",
        "unloading",
    ]
    assert ControlState.__name__ != ControlExecutionState.__name__


def test_control_reasons_are_stable_privacy_safe_codes() -> None:
    """Reason vocabulary covers authority, suppression, recovery, and invariants."""
    assert (
        parse_control_reason("manual_user_intent") is ControlReason.MANUAL_USER_INTENT
    )
    assert (
        parse_control_reason("shared_equipment_conflict")
        is ControlReason.SHARED_EQUIPMENT_CONFLICT
    )
    assert (
        parse_control_reason("illegal_transition") is ControlReason.ILLEGAL_TRANSITION
    )
    assert all(reason.value == reason.value.lower() for reason in ControlReason)
    assert all(" " not in reason.value for reason in ControlReason)
    with pytest.raises(ValueError):
        parse_control_reason("because the living room thermostat changed")


def test_execution_context_separates_live_home_from_future_simulation() -> None:
    """Simulation is a context boundary, never a live operating mode."""
    assert tuple(ExecutionContext) == (
        ExecutionContext.LIVE,
        ExecutionContext.SIMULATION,
    )
    assert parse_execution_context("live") is ExecutionContext.LIVE
    assert parse_execution_context("simulation") is ExecutionContext.SIMULATION
    assert "simulation" not in {mode.value for mode in OperatingMode}
    with pytest.raises(ValueError):
        parse_execution_context("preview")


@pytest.mark.parametrize(
    "identifier_type",
    [
        ScheduleProfileId,
        SchedulePeriodId,
        OverrideId,
        DecisionId,
        CommandId,
        SafetyEvaluationId,
        ContactBindingId,
        OccupancyModeId,
    ],
)
def test_phase_2_identifiers_are_typed_immutable_canonical_uuids(
    identifier_type: type[
        ScheduleProfileId
        | SchedulePeriodId
        | OverrideId
        | DecisionId
        | CommandId
        | SafetyEvaluationId
        | ContactBindingId
        | OccupancyModeId
    ],
) -> None:
    """Every new domain identity has the same strict UUID boundary."""
    raw_id = "1d9288c0-8d54-478f-9d0e-264369992f0c"
    identifier = identifier_type.parse(raw_id)
    generated = identifier_type.new()

    assert identifier.value == UUID(raw_id)
    assert str(identifier) == raw_id
    assert "__dict__" not in identifier.__slots__
    assert UUID(str(generated)).version == 4
    with pytest.raises(FrozenInstanceError):
        identifier.value = UUID(int=0)  # type: ignore[misc]
    with pytest.raises(ValueError):
        identifier_type.parse("not-a-uuid")


def test_equal_uuid_values_do_not_erase_identifier_type() -> None:
    """A profile ID can never compare equal to a period or command ID."""
    raw_id = "1d9288c0-8d54-478f-9d0e-264369992f0c"
    profile_id: object = ScheduleProfileId.parse(raw_id)
    decision_id: object = DecisionId.parse(raw_id)

    assert profile_id != SchedulePeriodId.parse(raw_id)
    assert decision_id != CommandId.parse(raw_id)


def test_task_2_vocabulary_wiring_is_limited_to_approved_foundations() -> None:
    """Later tasks use only the vocabulary needed by their approved scope."""
    vocabulary_paths = {
        Path("models/__init__.py"),
        Path("models/control.py"),
        Path("models/identifiers.py"),
        Path("models/modes.py"),
    }
    task_3_schedule_path = Path("models/schedule.py")
    task_4_schedule_paths = {
        Path("schedule/evaluate.py"),
        Path("schedule/transitions.py"),
    }
    task_7_schema_path = Path("models/phase2_schema.py")
    task_8_persistence_paths = {
        Path("migration.py"),
        Path("storage.py"),
    }
    task_9_control_paths = {
        Path("control/precedence.py"),
        Path("control/state_machine.py"),
    }
    task_10_override_paths = {
        Path("models/override.py"),
        Path("override/expiration.py"),
        Path("override/state_machine.py"),
    }
    task_11_command_paths = {
        Path("models/command.py"),
        Path("command/correlation.py"),
    }
    task_12_contact_paths = {
        Path("models/contact.py"),
        Path("contact/state_machine.py"),
    }
    task_13_occupancy_paths = {
        Path("models/occupancy.py"),
        Path("occupancy/resolver.py"),
    }
    task_15_fan_paths = {
        Path("models/fan.py"),
        Path("fan/policy.py"),
    }
    task_16_safety_paths = {
        Path("models/safety.py"),
        Path("control/safety.py"),
    }
    task_17_plan_paths = {Path("models/plan.py")}
    task_18_shadow_paths = {
        Path("models/shadow.py"),
        Path("shadow/history.py"),
        Path("shadow/qualification.py"),
        Path("shadow/sink.py"),
    }
    task_19_runtime_paths = {
        Path("models/policy_runtime.py"),
        Path("runtime.py"),
    }
    task_20_manual_paths = {Path("manual_control.py")}
    task_2_names = (
        "ControlExecutionState",
        "ControlReason",
        "ExecutionContext",
        "ScheduleProfileId",
        "SchedulePeriodId",
        "OverrideId",
        "DecisionId",
        "CommandId",
        "CorrelationId",
        "SafetyEvaluationId",
        "ContactBindingId",
        "OccupancyModeId",
    )
    offenders = [
        f"{relative_path} uses {name}"
        for path in INTEGRATION_DIR.rglob("*.py")
        if (relative_path := path.relative_to(INTEGRATION_DIR)) not in vocabulary_paths
        for name in task_2_names
        if name in path.read_text(encoding="utf-8")
        and not (
            relative_path == task_3_schedule_path
            and name in {"ScheduleProfileId", "SchedulePeriodId"}
        )
        and not (
            relative_path in task_4_schedule_paths
            and name
            in {
                "ControlReason",
                "ScheduleProfileId",
                "SchedulePeriodId",
            }
        )
        and not (
            relative_path == task_7_schema_path and name == "ControlExecutionState"
        )
        and not (
            relative_path in task_8_persistence_paths
            and name == "ControlExecutionState"
        )
        and not (
            relative_path in task_9_control_paths
            and name in {"ControlExecutionState", "ControlReason"}
        )
        and not (
            relative_path in task_10_override_paths
            and name in {"OverrideId", "ScheduleProfileId"}
        )
        and not (
            relative_path in task_11_command_paths
            and name
            in {
                "CommandId",
                "CorrelationId",
                "DecisionId",
                "SafetyEvaluationId",
            }
        )
        and not (relative_path in task_12_contact_paths and name == "ContactBindingId")
        and not (
            relative_path in task_13_occupancy_paths
            and name in {"OccupancyModeId", "ScheduleProfileId"}
        )
        and not (relative_path in task_15_fan_paths and name == "OccupancyModeId")
        and not (
            relative_path in task_16_safety_paths
            and name in {"ControlExecutionState", "SafetyEvaluationId"}
        )
        and not (
            relative_path in task_17_plan_paths
            and name in {"CommandId", "DecisionId", "SafetyEvaluationId"}
        )
        and not (
            relative_path in task_18_shadow_paths
            and name in {"CommandId", "DecisionId", "SafetyEvaluationId"}
        )
        and not (
            relative_path in task_19_runtime_paths
            and name
            in {
                "CommandId",
                "ControlExecutionState",
                "ControlReason",
                "DecisionId",
                "SafetyEvaluationId",
                "SchedulePeriodId",
                "ScheduleProfileId",
            }
        )
        and not (
            relative_path in task_20_manual_paths and name == "ControlExecutionState"
        )
    ]

    assert offenders == []
    assert not (INTEGRATION_DIR / "control" / "command_adapter.py").exists()
