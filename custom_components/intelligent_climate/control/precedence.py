"""Pure Phase 2 control precedence and manual-intent authority."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..models.control import ControlExecutionState, ControlReason
from ..models.modes import OperatingMode


class ObservationDirective(StrEnum):
    """Whether entry observation remains active across a control decision."""

    CONTINUE = "continue"
    STOP = "stop"


class ManualIntentSource(StrEnum):
    """Typed origin of a possible Manual Control request."""

    EXPLICIT_USER = "explicit_user"
    SENSOR = "sensor"
    SCHEDULE = "schedule"
    TIMER = "timer"
    OCCUPANCY = "occupancy"
    CONTACT = "contact"
    FAN_POLICY = "fan_policy"
    STARTUP = "startup"
    RELOAD = "reload"
    EXTERNAL_CHANGE = "external_change"
    WEATHER = "weather"
    LEARNING = "learning"


class ManualIntentResultCode(StrEnum):
    """Stable outcome code for the narrow Manual Control authority gate."""

    AUTHORIZED = "authorized"
    WRONG_MODE = "wrong_mode"
    SUPPRESSED_STATE = "suppressed_state"
    EXPLICIT_USER_REQUIRED = "explicit_user_required"
    AUTHENTICATED_USER_REQUIRED = "authenticated_user_required"
    FRESH_INTENT_REQUIRED = "fresh_intent_required"
    CURRENT_REVISION_REQUIRED = "current_revision_required"


@dataclass(frozen=True, slots=True)
class ControlPrecedenceInput:
    """Complete pure input for one control-precedence evaluation."""

    operating_mode: OperatingMode
    automation_enabled: bool
    loaded: bool = True
    initializing: bool = False
    unloading: bool = False
    configuration_valid: bool = True
    migration_valid: bool = True
    future_schema_supported: bool = True
    emergency_paused: bool = False
    reconciling: bool = False
    time_zone_acknowledgement_required: bool = False
    thermostat_available: bool = True
    capability_valid: bool = True
    command_awaiting_ack: bool = False
    command_uncertain: bool = False
    failure_lockout: bool = False
    control_authority_valid: bool = True
    required_autonomous_sensors_valid: bool = True
    schedule_available: bool = True
    emergency_protection_active: bool = False
    manual_override_active: bool = False
    window_suspended: bool = False
    shared_conflict_hold: bool = False
    occupancy_hold: bool = False
    shadow_qualified: bool = False
    active_control_armed: bool = False
    schedule_plan_pending: bool = False


@dataclass(frozen=True, slots=True)
class ControlPrecedenceDecision:
    """One reason-coded execution state selected by fixed precedence."""

    state: ControlExecutionState
    reason: ControlReason
    observation: ObservationDirective

    @property
    def observation_continues(self) -> bool:
        """Return whether observation remains active after this decision."""
        return self.observation is ObservationDirective.CONTINUE


@dataclass(frozen=True, slots=True)
class ManualIntentRequest:
    """Authority facts for one possible direct Manual Control request."""

    operating_mode: OperatingMode
    control_state: ControlExecutionState
    source: ManualIntentSource
    authenticated_user: bool
    fresh: bool
    observed_revision_matches: bool


@dataclass(frozen=True, slots=True)
class ManualIntentDecision:
    """Fail-closed authority result for a possible manual command."""

    authorized: bool
    code: ManualIntentResultCode


def resolve_control_precedence(
    value: ControlPrecedenceInput,
) -> ControlPrecedenceDecision:
    """Resolve one state using the approved highest-to-lowest precedence."""
    if not value.loaded:
        return _decision(ControlExecutionState.UNLOADED, ControlReason.UNLOAD)
    if value.unloading:
        return _decision(ControlExecutionState.UNLOADING, ControlReason.UNLOAD)
    if value.initializing:
        return _decision(ControlExecutionState.INITIALIZING, ControlReason.STARTUP)
    if not (
        value.configuration_valid
        and value.migration_valid
        and value.future_schema_supported
    ):
        return _decision(
            ControlExecutionState.SAFE_FALLBACK,
            ControlReason.CONFIGURATION_INVALID,
        )

    invalid_reason = _mode_configuration_failure(value)
    if invalid_reason is not None:
        return _decision(ControlExecutionState.SAFE_FALLBACK, invalid_reason)

    if value.emergency_paused:
        return _decision(
            ControlExecutionState.EMERGENCY_PAUSED,
            ControlReason.EMERGENCY_PAUSE,
        )
    if value.operating_mode is OperatingMode.DISABLED:
        return _decision(ControlExecutionState.DISABLED, ControlReason.DISABLED)
    if value.reconciling:
        return _decision(ControlExecutionState.RECONCILING, ControlReason.STARTUP)
    if value.time_zone_acknowledgement_required:
        return _decision(
            ControlExecutionState.RECONCILING,
            ControlReason.TIME_ZONE_REVIEW_REQUIRED,
        )
    if value.failure_lockout:
        return _decision(
            ControlExecutionState.EMERGENCY_PAUSED,
            ControlReason.FAILURE_LOCKOUT,
        )
    if value.command_uncertain:
        return _decision(
            ControlExecutionState.SAFE_FALLBACK,
            ControlReason.COMMAND_UNCERTAIN,
        )
    if value.command_awaiting_ack:
        return _decision(
            ControlExecutionState.COMMAND_AWAITING_ACK,
            ControlReason.COMMAND_AWAITING_ACK,
        )
    if not value.thermostat_available:
        return _decision(
            ControlExecutionState.DEGRADED,
            ControlReason.THERMOSTAT_UNAVAILABLE,
        )
    if not value.capability_valid:
        return _decision(
            ControlExecutionState.SAFE_FALLBACK,
            ControlReason.CAPABILITY_INVALID,
        )

    if value.operating_mode is OperatingMode.MANUAL_CONTROL:
        return _decision(
            ControlExecutionState.MANUAL_IDLE,
            ControlReason.MANUAL_CONTROL_SELECTED,
        )
    if not value.required_autonomous_sensors_valid:
        return _decision(
            ControlExecutionState.DEGRADED,
            ControlReason.REQUIRED_SENSOR_INVALID,
        )
    if value.operating_mode is OperatingMode.OBSERVE_ONLY:
        return _decision(
            ControlExecutionState.OBSERVING,
            ControlReason.OBSERVE_ONLY_SELECTED,
        )

    if value.emergency_protection_active:
        return _decision(
            ControlExecutionState.EMERGENCY_PROTECTION,
            ControlReason.EMERGENCY_PROTECTION,
        )
    if value.manual_override_active:
        return _decision(
            ControlExecutionState.MANUAL_OVERRIDE,
            ControlReason.MANUAL_OVERRIDE_ACTIVE,
        )
    if value.window_suspended:
        return _decision(
            ControlExecutionState.WINDOW_SUSPENDED,
            ControlReason.WINDOW_OPEN,
        )
    if value.shared_conflict_hold:
        return _decision(
            ControlExecutionState.SHARED_CONFLICT_HOLD,
            ControlReason.SHARED_EQUIPMENT_CONFLICT,
        )
    if value.occupancy_hold:
        return _decision(
            ControlExecutionState.OCCUPANCY_HOLD,
            ControlReason.OCCUPANCY_HOLD,
        )
    if not value.shadow_qualified:
        return _decision(
            ControlExecutionState.SHADOW_QUALIFYING,
            ControlReason.SHADOW_QUALIFYING,
        )
    if (
        value.operating_mode is OperatingMode.SCHEDULED_SHADOW
        or not value.active_control_armed
    ):
        return _decision(
            ControlExecutionState.SHADOW_READY,
            ControlReason.SHADOW_READY,
        )
    if value.schedule_plan_pending:
        return _decision(
            ControlExecutionState.SCHEDULED_PENDING,
            ControlReason.COMMAND_PLANNED,
        )
    return _decision(
        ControlExecutionState.SCHEDULED_IDLE,
        ControlReason.SCHEDULE_EVALUATION,
    )


def evaluate_manual_intent_authority(
    value: ManualIntentRequest,
) -> ManualIntentDecision:
    """Authorize only one fresh, authenticated, explicit Manual Control intent."""
    if value.operating_mode is not OperatingMode.MANUAL_CONTROL:
        return _manual_denial(ManualIntentResultCode.WRONG_MODE)
    if value.control_state is not ControlExecutionState.MANUAL_IDLE:
        return _manual_denial(ManualIntentResultCode.SUPPRESSED_STATE)
    if value.source is not ManualIntentSource.EXPLICIT_USER:
        return _manual_denial(ManualIntentResultCode.EXPLICIT_USER_REQUIRED)
    if not value.authenticated_user:
        return _manual_denial(ManualIntentResultCode.AUTHENTICATED_USER_REQUIRED)
    if not value.fresh:
        return _manual_denial(ManualIntentResultCode.FRESH_INTENT_REQUIRED)
    if not value.observed_revision_matches:
        return _manual_denial(ManualIntentResultCode.CURRENT_REVISION_REQUIRED)
    return ManualIntentDecision(
        authorized=True,
        code=ManualIntentResultCode.AUTHORIZED,
    )


def observation_directive_for_state(
    state: ControlExecutionState,
) -> ObservationDirective:
    """Keep observation active in every loaded and unloading control state."""
    if state is ControlExecutionState.UNLOADED:
        return ObservationDirective.STOP
    return ObservationDirective.CONTINUE


def _mode_configuration_failure(
    value: ControlPrecedenceInput,
) -> ControlReason | None:
    scheduled_mode = value.operating_mode in {
        OperatingMode.SCHEDULED_SHADOW,
        OperatingMode.SCHEDULED_CONTROL,
    }
    if scheduled_mode and not value.automation_enabled:
        return ControlReason.CONFIGURATION_INVALID
    if not scheduled_mode and value.active_control_armed:
        return ControlReason.CONFIGURATION_INVALID
    if scheduled_mode and not value.control_authority_valid:
        return ControlReason.COMMAND_AUTHORITY_INVALID
    if scheduled_mode and not value.schedule_available:
        return ControlReason.SCHEDULE_UNAVAILABLE
    return None


def _decision(
    state: ControlExecutionState,
    reason: ControlReason,
) -> ControlPrecedenceDecision:
    return ControlPrecedenceDecision(
        state=state,
        reason=reason,
        observation=observation_directive_for_state(state),
    )


def _manual_denial(code: ManualIntentResultCode) -> ManualIntentDecision:
    return ManualIntentDecision(authorized=False, code=code)
