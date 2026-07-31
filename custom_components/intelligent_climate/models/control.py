"""Pure Phase 2 control vocabulary with no runtime wiring."""

from __future__ import annotations

from enum import StrEnum


class ControlExecutionState(StrEnum):
    """Current Phase 2 execution state, distinct from user operating intent."""

    UNLOADED = "unloaded"
    INITIALIZING = "initializing"
    RECONCILING = "reconciling"
    DISABLED = "disabled"
    OBSERVING = "observing"
    MANUAL_IDLE = "manual_idle"
    SHADOW_QUALIFYING = "shadow_qualifying"
    SHADOW_READY = "shadow_ready"
    SCHEDULED_IDLE = "scheduled_idle"
    SCHEDULED_PENDING = "scheduled_pending"
    COMMAND_AWAITING_ACK = "command_awaiting_ack"
    MANUAL_OVERRIDE = "manual_override"
    WINDOW_SUSPENDED = "window_suspended"
    OCCUPANCY_HOLD = "occupancy_hold"
    SHARED_CONFLICT_HOLD = "shared_conflict_hold"
    EMERGENCY_PROTECTION = "emergency_protection"
    SAFE_FALLBACK = "safe_fallback"
    EMERGENCY_PAUSED = "emergency_paused"
    DEGRADED = "degraded"
    UNLOADING = "unloading"


class ControlReason(StrEnum):
    """Stable, privacy-safe reason codes for control-state explanations."""

    STARTUP = "startup"
    CONFIGURATION_INVALID = "configuration_invalid"
    DISABLED = "disabled"
    OBSERVE_ONLY_SELECTED = "observe_only_selected"
    MANUAL_CONTROL_SELECTED = "manual_control_selected"
    MANUAL_USER_INTENT = "manual_user_intent"
    SHADOW_STARTED = "shadow_started"
    SHADOW_QUALIFYING = "shadow_qualifying"
    SHADOW_READY = "shadow_ready"
    SCHEDULED_CONTROL_ARMED = "scheduled_control_armed"
    SCHEDULE_EVALUATION = "schedule_evaluation"
    COMMAND_PLANNED = "command_planned"
    COMMAND_AWAITING_ACK = "command_awaiting_ack"
    MANUAL_OVERRIDE_ACTIVE = "manual_override_active"
    WINDOW_OPEN = "window_open"
    OCCUPANCY_HOLD = "occupancy_hold"
    SHARED_EQUIPMENT_CONFLICT = "shared_equipment_conflict"
    EMERGENCY_PROTECTION = "emergency_protection"
    EMERGENCY_PAUSE = "emergency_pause"
    THERMOSTAT_UNAVAILABLE = "thermostat_unavailable"
    CAPABILITY_INVALID = "capability_invalid"
    REQUIRED_SENSOR_INVALID = "required_sensor_invalid"
    COMMAND_UNCERTAIN = "command_uncertain"
    FAILURE_LOCKOUT = "failure_lockout"
    TIME_ZONE_REVIEW_REQUIRED = "time_zone_review_required"
    COMMAND_AUTHORITY_INVALID = "command_authority_invalid"
    SCHEDULE_UNAVAILABLE = "schedule_unavailable"
    SAFE_FALLBACK = "safe_fallback"
    RECOVERY_PENDING = "recovery_pending"
    HEALTHY_RECOVERY = "healthy_recovery"
    ILLEGAL_TRANSITION = "illegal_transition"
    UNLOAD = "unload"


class ExecutionContext(StrEnum):
    """Isolation boundary for real-home and future simulation execution."""

    LIVE = "live"
    SIMULATION = "simulation"


def parse_control_execution_state(value: str) -> ControlExecutionState:
    """Parse and validate a Phase 2 control execution state."""
    return ControlExecutionState(value)


def parse_control_reason(value: str) -> ControlReason:
    """Parse and validate a stable control reason code."""
    return ControlReason(value)


def parse_execution_context(value: str) -> ExecutionContext:
    """Parse and validate an execution-context value."""
    return ExecutionContext(value)
