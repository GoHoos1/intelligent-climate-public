"""Deterministic basic fan eligibility and hysteresis engine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import isfinite

from ..models.fan import (
    FanHumidityUnavailablePolicy,
    FanPolicy,
    FanQuietPeriod,
    FanRuntimeBudget,
    FanStrategy,
    validate_fan_policy,
    validate_fan_runtime_budget,
)
from ..models.identifiers import OccupancyModeId
from ..models.schedule import WEEKDAYS
from ..models.schema import SchemaValidationError
from .dew_point import calculate_dew_point_c
from .runtime_budget import FanRuntimeBudgetState, calculate_fan_runtime_budget


class FanDirective(StrEnum):
    """Physically inert directive for a later command-planning task."""

    START = "start"
    KEEP_RUNNING = "keep_running"
    STOP = "stop"
    KEEP_STOPPED = "keep_stopped"


class FanReasonCode(StrEnum):
    """Privacy-safe explanation for a fan policy result."""

    POLICY_DISABLED = "policy_disabled"
    BINDING_DISABLED = "binding_disabled"
    SCHEDULE_REQUESTED = "schedule_requested"
    SPREAD_START = "spread_start"
    SPREAD_HYSTERESIS = "spread_hysteresis"
    EITHER_REQUESTED = "either_requested"
    SCHEDULE_NOT_REQUESTED = "schedule_not_requested"
    SPREAD_UNAVAILABLE = "spread_unavailable"
    SPREAD_BELOW_START = "spread_below_start"
    SPREAD_SATISFIED = "spread_satisfied"
    OCCUPANCY_BLOCKED = "occupancy_blocked"
    HVAC_MODE_BLOCKED = "hvac_mode_blocked"
    QUIET_PERIOD = "quiet_period"
    RUNTIME_BUDGET_EXHAUSTED = "runtime_budget_exhausted"
    HUMIDITY_HIGH = "humidity_high"
    DEW_POINT_HIGH = "dew_point_high"
    HUMIDITY_UNAVAILABLE = "humidity_unavailable"
    POST_COOLING_LOCKOUT = "post_cooling_lockout"
    MINIMUM_ON_ACTIVE = "minimum_on_active"


@dataclass(frozen=True, slots=True)
class FanEvaluationInput:
    """Complete caller-supplied facts for one fan evaluation."""

    at_utc: datetime
    at_local: datetime
    is_running: bool
    running_since_utc: datetime | None
    temperature_spread_c: float | None
    schedule_requested: bool
    occupancy_mode_id: OccupancyModeId | None
    hvac_mode: str | None
    effective_temperature_c: float | None
    effective_humidity_pct: float | None
    last_cooling_ended_at_utc: datetime | None
    runtime_budget: FanRuntimeBudget


@dataclass(frozen=True, slots=True)
class FanEvaluation:
    """One inert fan-only policy result."""

    directive: FanDirective
    reason_code: FanReasonCode
    desired_running: bool
    lockout_active: bool
    degraded: bool
    calculated_dew_point_c: float | None
    runtime_seconds_last_hour: int
    runtime_remaining_seconds: int
    next_evaluation_at_utc: datetime | None


def evaluate_fan_policy(
    policy: FanPolicy, *, inputs: FanEvaluationInput
) -> FanEvaluation:
    """Apply request hysteresis and every documented fan-only gate."""
    validate_fan_policy(policy)
    at, local = _validate_inputs(policy, inputs)
    budget = calculate_fan_runtime_budget(
        inputs.runtime_budget,
        at_utc=at,
        maximum_runtime_per_hour_seconds=(policy.maximum_runtime_per_hour_seconds),
        running_since_utc=inputs.running_since_utc,
    )
    dew_point = calculate_dew_point_c(
        inputs.effective_temperature_c,
        inputs.effective_humidity_pct,
    )
    if not policy.enabled:
        return _stopped_or_stop(
            inputs,
            FanReasonCode.POLICY_DISABLED,
            budget,
            dew_point,
        )
    if not policy.control_binding.enabled:
        return _stopped_or_stop(
            inputs,
            FanReasonCode.BINDING_DISABLED,
            budget,
            dew_point,
        )

    request_reason = _request_reason(policy, inputs)
    block = _first_block(policy, inputs, at, local, budget, dew_point)
    degraded = (
        _humidity_required(policy)
        and not _humidity_available(policy, inputs, dew_point)
        and policy.humidity_unavailable_policy
        is FanHumidityUnavailablePolicy.IGNORE_AND_DEGRADE
    ) or (
        policy.strategy in {FanStrategy.TEMPERATURE_SPREAD, FanStrategy.EITHER}
        and inputs.temperature_spread_c is None
    )
    if inputs.is_running:
        return _running_result(
            policy,
            inputs,
            at,
            budget,
            dew_point,
            request_reason,
            block,
            degraded,
        )
    if request_reason in {
        FanReasonCode.SCHEDULE_NOT_REQUESTED,
        FanReasonCode.SPREAD_UNAVAILABLE,
        FanReasonCode.SPREAD_BELOW_START,
        FanReasonCode.SPREAD_SATISFIED,
    }:
        return _evaluation(
            FanDirective.KEEP_STOPPED,
            request_reason,
            False,
            False,
            degraded,
            dew_point,
            budget,
            None,
        )
    if block is not None:
        reason, next_at = block
        return _evaluation(
            FanDirective.KEEP_STOPPED,
            reason,
            False,
            True,
            degraded,
            dew_point,
            budget,
            next_at,
        )
    next_at = (
        at + timedelta(seconds=budget.remaining_seconds)
        if budget.remaining_seconds > 0
        else None
    )
    return _evaluation(
        FanDirective.START,
        request_reason,
        True,
        False,
        degraded,
        dew_point,
        budget,
        next_at,
    )


def _running_result(
    policy: FanPolicy,
    inputs: FanEvaluationInput,
    at: datetime,
    budget: FanRuntimeBudgetState,
    dew_point: float | None,
    request_reason: FanReasonCode,
    block: tuple[FanReasonCode, datetime | None] | None,
    degraded: bool,
) -> FanEvaluation:
    running_since = _utc(inputs.running_since_utc, "running_since_utc")
    minimum_end = running_since + timedelta(seconds=policy.minimum_on_seconds)
    stop_reason = (
        block[0]
        if block is not None
        else request_reason
        if request_reason
        in {
            FanReasonCode.SCHEDULE_NOT_REQUESTED,
            FanReasonCode.SPREAD_UNAVAILABLE,
            FanReasonCode.SPREAD_SATISFIED,
            FanReasonCode.SPREAD_BELOW_START,
        }
        else None
    )
    humidity_stop = stop_reason in {
        FanReasonCode.HUMIDITY_HIGH,
        FanReasonCode.DEW_POINT_HIGH,
        FanReasonCode.HUMIDITY_UNAVAILABLE,
        FanReasonCode.POST_COOLING_LOCKOUT,
    }
    hard_stop = stop_reason is FanReasonCode.RUNTIME_BUDGET_EXHAUSTED or (
        humidity_stop and policy.immediate_stop_on_humidity_lockout
    )
    if stop_reason is not None and at < minimum_end and not hard_stop:
        return _evaluation(
            FanDirective.KEEP_RUNNING,
            FanReasonCode.MINIMUM_ON_ACTIVE,
            True,
            True,
            degraded,
            dew_point,
            budget,
            minimum_end,
        )
    if stop_reason is not None:
        return _evaluation(
            FanDirective.STOP,
            stop_reason,
            False,
            True,
            degraded,
            dew_point,
            budget,
            None,
        )
    next_at = (
        at + timedelta(seconds=budget.remaining_seconds)
        if budget.remaining_seconds > 0
        else None
    )
    return _evaluation(
        FanDirective.KEEP_RUNNING,
        request_reason,
        True,
        False,
        degraded,
        dew_point,
        budget,
        next_at,
    )


def _request_reason(policy: FanPolicy, inputs: FanEvaluationInput) -> FanReasonCode:
    spread = inputs.temperature_spread_c
    if policy.strategy is FanStrategy.SCHEDULE:
        return (
            FanReasonCode.SCHEDULE_REQUESTED
            if inputs.schedule_requested
            else FanReasonCode.SCHEDULE_NOT_REQUESTED
        )
    if spread is None and not (
        policy.strategy is FanStrategy.EITHER and inputs.schedule_requested
    ):
        return FanReasonCode.SPREAD_UNAVAILABLE
    spread_requested = spread is not None and (
        spread > policy.spread_stop_c
        if inputs.is_running
        else spread >= policy.spread_start_c
    )
    if policy.strategy is FanStrategy.TEMPERATURE_SPREAD:
        if spread_requested:
            return (
                FanReasonCode.SPREAD_HYSTERESIS
                if inputs.is_running
                else FanReasonCode.SPREAD_START
            )
        return (
            FanReasonCode.SPREAD_SATISFIED
            if inputs.is_running
            else FanReasonCode.SPREAD_BELOW_START
        )
    if inputs.schedule_requested or spread_requested:
        return FanReasonCode.EITHER_REQUESTED
    return (
        FanReasonCode.SPREAD_SATISFIED
        if inputs.is_running
        else FanReasonCode.SPREAD_BELOW_START
    )


def _first_block(
    policy: FanPolicy,
    inputs: FanEvaluationInput,
    at: datetime,
    local: datetime,
    budget: FanRuntimeBudgetState,
    dew_point: float | None,
) -> tuple[FanReasonCode, datetime | None] | None:
    if policy.occupied_only and (
        inputs.occupancy_mode_id is None
        or inputs.occupancy_mode_id not in policy.allowed_occupancy_modes
    ):
        return FanReasonCode.OCCUPANCY_BLOCKED, None
    if inputs.hvac_mode is None or inputs.hvac_mode not in policy.allowed_hvac_modes:
        return FanReasonCode.HVAC_MODE_BLOCKED, None
    if any(_in_quiet_period(local, period) for period in policy.quiet_periods):
        return FanReasonCode.QUIET_PERIOD, None
    if budget.exhausted:
        return FanReasonCode.RUNTIME_BUDGET_EXHAUSTED, budget.next_release_at_utc

    humidity_reason = _humidity_reason(policy, inputs, dew_point)
    if humidity_reason is not None:
        post_cooling_end = _post_cooling_end(policy, inputs, at)
        if post_cooling_end is not None:
            return FanReasonCode.POST_COOLING_LOCKOUT, post_cooling_end
        return humidity_reason, None
    return None


def _humidity_reason(
    policy: FanPolicy,
    inputs: FanEvaluationInput,
    dew_point: float | None,
) -> FanReasonCode | None:
    if not _humidity_required(policy):
        return None
    if (
        inputs.effective_humidity_pct is None
        or not _valid_humidity(inputs.effective_humidity_pct)
        or (policy.max_dew_point_c is not None and dew_point is None)
    ):
        if policy.humidity_unavailable_policy is FanHumidityUnavailablePolicy.LOCK_OUT:
            return FanReasonCode.HUMIDITY_UNAVAILABLE
        return None
    if (
        policy.max_humidity_pct is not None
        and inputs.effective_humidity_pct > policy.max_humidity_pct
    ):
        return FanReasonCode.HUMIDITY_HIGH
    if (
        policy.max_dew_point_c is not None
        and dew_point is not None
        and dew_point > policy.max_dew_point_c
    ):
        return FanReasonCode.DEW_POINT_HIGH
    return None


def _post_cooling_end(
    policy: FanPolicy,
    inputs: FanEvaluationInput,
    at: datetime,
) -> datetime | None:
    if (
        inputs.last_cooling_ended_at_utc is None
        or policy.post_cooling_lockout_seconds == 0
    ):
        return None
    ended = _utc(inputs.last_cooling_ended_at_utc, "last_cooling_ended_at_utc")
    lockout_end = ended + timedelta(seconds=policy.post_cooling_lockout_seconds)
    return lockout_end if at < lockout_end else None


def _in_quiet_period(local: datetime, period: FanQuietPeriod) -> bool:
    weekday_index = local.weekday()
    weekday = WEEKDAYS[weekday_index]
    previous_weekday = WEEKDAYS[(weekday_index - 1) % len(WEEKDAYS)]
    minute = local.hour * 60 + local.minute
    if period.start_minute < period.end_minute:
        return (
            weekday in period.weekdays
            and period.start_minute <= minute < period.end_minute
        )
    return (weekday in period.weekdays and minute >= period.start_minute) or (
        previous_weekday in period.weekdays and minute < period.end_minute
    )


def _validate_inputs(
    policy: FanPolicy, inputs: FanEvaluationInput
) -> tuple[datetime, datetime]:
    at = _utc(inputs.at_utc, "at_utc")
    local = _aware(inputs.at_local, "at_local")
    if local.astimezone(UTC) != at:
        raise SchemaValidationError("at_local", "must represent the at_utc instant")
    if not isinstance(inputs.is_running, bool) or not isinstance(
        inputs.schedule_requested, bool
    ):
        raise SchemaValidationError(
            "fan_input", "running and schedule flags must be booleans"
        )
    if inputs.is_running != (inputs.running_since_utc is not None):
        raise SchemaValidationError(
            "running_since_utc", "must be present exactly while fan is running"
        )
    if inputs.running_since_utc is not None:
        running_since = _utc(inputs.running_since_utc, "running_since_utc")
        if running_since > at:
            raise SchemaValidationError(
                "running_since_utc", "must not be in the future"
            )
    for path, value in (
        ("temperature_spread_c", inputs.temperature_spread_c),
        ("effective_temperature_c", inputs.effective_temperature_c),
        ("effective_humidity_pct", inputs.effective_humidity_pct),
    ):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, int | float)
            or not isfinite(value)
        ):
            raise SchemaValidationError(path, "must be finite or null")
    if inputs.temperature_spread_c is not None and inputs.temperature_spread_c < 0:
        raise SchemaValidationError("temperature_spread_c", "must be nonnegative")
    if inputs.occupancy_mode_id is not None and not isinstance(
        inputs.occupancy_mode_id, OccupancyModeId
    ):
        raise SchemaValidationError(
            "occupancy_mode_id", "must be an occupancy mode ID or null"
        )
    if inputs.hvac_mode is not None and (
        not isinstance(inputs.hvac_mode, str)
        or not inputs.hvac_mode
        or len(inputs.hvac_mode) > 64
    ):
        raise SchemaValidationError("hvac_mode", "must be a bounded mode or null")
    if inputs.last_cooling_ended_at_utc is not None:
        ended = _utc(
            inputs.last_cooling_ended_at_utc,
            "last_cooling_ended_at_utc",
        )
        if ended > at:
            raise SchemaValidationError(
                "last_cooling_ended_at_utc", "must not be in the future"
            )
    validate_fan_runtime_budget(inputs.runtime_budget)
    return at, local


def _humidity_required(policy: FanPolicy) -> bool:
    return policy.max_humidity_pct is not None or policy.max_dew_point_c is not None


def _humidity_available(
    policy: FanPolicy,
    inputs: FanEvaluationInput,
    dew_point: float | None,
) -> bool:
    return (
        inputs.effective_humidity_pct is not None
        and _valid_humidity(inputs.effective_humidity_pct)
        and (policy.max_dew_point_c is None or dew_point is not None)
    )


def _valid_humidity(value: float) -> bool:
    return isfinite(value) and 0 < value <= 100


def _stopped_or_stop(
    inputs: FanEvaluationInput,
    reason: FanReasonCode,
    budget: FanRuntimeBudgetState,
    dew_point: float | None,
) -> FanEvaluation:
    return _evaluation(
        FanDirective.STOP if inputs.is_running else FanDirective.KEEP_STOPPED,
        reason,
        False,
        False,
        False,
        dew_point,
        budget,
        None,
    )


def _evaluation(
    directive: FanDirective,
    reason: FanReasonCode,
    desired_running: bool,
    lockout: bool,
    degraded: bool,
    dew_point: float | None,
    budget: FanRuntimeBudgetState,
    next_at: datetime | None,
) -> FanEvaluation:
    return FanEvaluation(
        directive=directive,
        reason_code=reason,
        desired_running=desired_running,
        lockout_active=lockout,
        degraded=degraded,
        calculated_dew_point_c=dew_point,
        runtime_seconds_last_hour=budget.runtime_seconds_last_hour,
        runtime_remaining_seconds=budget.remaining_seconds,
        next_evaluation_at_utc=next_at,
    )


def _utc(value: object, path: str) -> datetime:
    return _aware(value, path).astimezone(UTC)


def _aware(value: object, path: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise SchemaValidationError(path, "must be an aware datetime")
    return value
