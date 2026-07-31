"""Task 15 pure fan, dew-point, runtime-budget, and restore tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from math import inf, nan
from typing import Any, cast
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from custom_components.intelligent_climate.fan import (
    FanDirective,
    FanEvaluationInput,
    FanReasonCode,
    FanRestoreEvidence,
    FanRestoreReasonCode,
    calculate_dew_point_c,
    calculate_fan_runtime_budget,
    evaluate_fan_policy,
    evaluate_fan_restore,
)
from custom_components.intelligent_climate.models import (
    MAX_FAN_RUNTIME_INTERVALS,
    FanBindingKind,
    FanControlBinding,
    FanHumidityUnavailablePolicy,
    FanPolicy,
    FanQuietPeriod,
    FanRuntimeBudget,
    FanRuntimeInterval,
    FanStrategy,
    OccupancyModeId,
    SchemaValidationError,
    Weekday,
    decode_fan_policy,
    decode_fan_runtime_budget,
    encode_fan_policy,
    encode_fan_runtime_budget,
    validate_fan_policy,
    validate_fan_runtime_budget,
)

NOW = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)
NY = ZoneInfo("America/New_York")
HOME = OccupancyModeId(UUID(int=1))
AWAY = OccupancyModeId(UUID(int=2))


def _separate_binding(**changes: Any) -> FanControlBinding:
    value = FanControlBinding(
        entity_id="fan.circulation",
        kind=FanBindingKind.SEPARATE_FAN,
        supported_modes=(),
        circulation_mode=None,
        native_mode=None,
        enabled=True,
        reviewed=True,
    )
    return replace(value, **changes)


def _thermostat_binding(**changes: Any) -> FanControlBinding:
    value = FanControlBinding(
        entity_id="climate.dining",
        kind=FanBindingKind.THERMOSTAT_FAN_MODE,
        supported_modes=("auto", "on"),
        circulation_mode="on",
        native_mode="auto",
        enabled=True,
        reviewed=True,
    )
    return replace(value, **changes)


def _policy(**changes: Any) -> FanPolicy:
    value = FanPolicy(
        enabled=True,
        control_binding=_separate_binding(),
        strategy=FanStrategy.TEMPERATURE_SPREAD,
        spread_start_c=1.1,
        spread_stop_c=0.6,
        occupied_only=True,
        allowed_occupancy_modes=(HOME,),
        allowed_hvac_modes=("heat", "cool"),
        quiet_periods=(),
        minimum_on_seconds=600,
        maximum_runtime_per_hour_seconds=1200,
        post_cooling_lockout_seconds=900,
        max_humidity_pct=60.0,
        max_dew_point_c=15.6,
        humidity_unavailable_policy=FanHumidityUnavailablePolicy.LOCK_OUT,
        immediate_stop_on_humidity_lockout=False,
    )
    return replace(value, **changes)


def _inputs(**changes: Any) -> FanEvaluationInput:
    value = FanEvaluationInput(
        at_utc=NOW,
        at_local=NOW.astimezone(NY),
        is_running=False,
        running_since_utc=None,
        temperature_spread_c=1.2,
        schedule_requested=False,
        occupancy_mode_id=HOME,
        hvac_mode="heat",
        effective_temperature_c=22.0,
        effective_humidity_pct=50.0,
        last_cooling_ended_at_utc=None,
        runtime_budget=FanRuntimeBudget(()),
    )
    return replace(value, **changes)


def _running_inputs(age_seconds: int = 700, **changes: Any) -> FanEvaluationInput:
    return _inputs(
        is_running=True,
        running_since_utc=NOW - timedelta(seconds=age_seconds),
        **changes,
    )


def test_separate_and_thermostat_policy_round_trip_without_activation() -> None:
    separate = _policy()
    thermostat = _policy(control_binding=_thermostat_binding())

    assert decode_fan_policy(encode_fan_policy(separate)) == separate
    assert decode_fan_policy(encode_fan_policy(thermostat)) == thermostat


def test_runtime_budget_round_trip_is_restart_safe_and_utc_canonical() -> None:
    budget = FanRuntimeBudget(
        (
            FanRuntimeInterval(
                NOW - timedelta(minutes=50),
                NOW - timedelta(minutes=40),
            ),
            FanRuntimeInterval(
                NOW - timedelta(minutes=20),
                NOW - timedelta(minutes=10),
            ),
        )
    )

    encoded = encode_fan_runtime_budget(budget)

    assert decode_fan_runtime_budget(encoded) == budget
    assert all(item["started_at_utc"].endswith("+00:00") for item in encoded)


@pytest.mark.parametrize(
    ("temperature", "humidity", "expected"),
    [
        (22.0, 50.0, 11.095),
        (22, 100, 22.0),
        (None, 50.0, None),
        (22.0, None, None),
        (nan, 50.0, None),
        (22.0, inf, None),
        (22.0, 0.0, None),
        (22.0, 101.0, None),
        (-100.0, 50.0, None),
        (100.0, 50.0, None),
        (True, 50.0, None),
        (22.0, False, None),
    ],
)
def test_dew_point_is_calculated_or_truthfully_unavailable(
    temperature: object,
    humidity: object,
    expected: float | None,
) -> None:
    result = calculate_dew_point_c(
        cast(Any, temperature),
        cast(Any, humidity),
    )

    assert result == expected


def test_schedule_strategy_starts_only_when_requested() -> None:
    policy = _policy(strategy=FanStrategy.SCHEDULE)

    stopped = evaluate_fan_policy(policy, inputs=_inputs(schedule_requested=False))
    started = evaluate_fan_policy(policy, inputs=_inputs(schedule_requested=True))

    assert stopped.directive is FanDirective.KEEP_STOPPED
    assert stopped.reason_code is FanReasonCode.SCHEDULE_NOT_REQUESTED
    assert started.directive is FanDirective.START
    assert started.reason_code is FanReasonCode.SCHEDULE_REQUESTED


@pytest.mark.parametrize(
    ("spread", "directive", "reason"),
    [
        (1.09, FanDirective.KEEP_STOPPED, FanReasonCode.SPREAD_BELOW_START),
        (1.1, FanDirective.START, FanReasonCode.SPREAD_START),
        (2.0, FanDirective.START, FanReasonCode.SPREAD_START),
    ],
)
def test_spread_start_boundary_is_inclusive(
    spread: float,
    directive: FanDirective,
    reason: FanReasonCode,
) -> None:
    result = evaluate_fan_policy(
        _policy(),
        inputs=_inputs(temperature_spread_c=spread),
    )

    assert result.directive is directive
    assert result.reason_code is reason


@pytest.mark.parametrize(
    ("inputs", "directive"),
    [
        (_inputs(temperature_spread_c=None), FanDirective.KEEP_STOPPED),
        (
            _running_inputs(temperature_spread_c=None),
            FanDirective.STOP,
        ),
    ],
)
def test_unavailable_spread_fails_closed_and_degrades(
    inputs: FanEvaluationInput,
    directive: FanDirective,
) -> None:
    result = evaluate_fan_policy(_policy(), inputs=inputs)

    assert result.directive is directive
    assert result.reason_code is FanReasonCode.SPREAD_UNAVAILABLE
    assert result.degraded


@pytest.mark.parametrize(
    ("spread", "directive", "reason"),
    [
        (0.6, FanDirective.STOP, FanReasonCode.SPREAD_SATISFIED),
        (0.61, FanDirective.KEEP_RUNNING, FanReasonCode.SPREAD_HYSTERESIS),
        (1.1, FanDirective.KEEP_RUNNING, FanReasonCode.SPREAD_HYSTERESIS),
    ],
)
def test_spread_stop_boundary_and_hysteresis(
    spread: float,
    directive: FanDirective,
    reason: FanReasonCode,
) -> None:
    result = evaluate_fan_policy(
        _policy(),
        inputs=_running_inputs(temperature_spread_c=spread),
    )

    assert result.directive is directive
    assert result.reason_code is reason


@pytest.mark.parametrize(
    ("schedule", "spread", "running", "reason"),
    [
        (True, 0.0, False, FanReasonCode.EITHER_REQUESTED),
        (False, 1.1, False, FanReasonCode.EITHER_REQUESTED),
        (False, 0.0, False, FanReasonCode.SPREAD_BELOW_START),
        (False, 0.6, True, FanReasonCode.SPREAD_SATISFIED),
    ],
)
def test_either_strategy_combines_schedule_and_spread(
    schedule: bool,
    spread: float,
    running: bool,
    reason: FanReasonCode,
) -> None:
    inputs = (
        _running_inputs(schedule_requested=schedule, temperature_spread_c=spread)
        if running
        else _inputs(schedule_requested=schedule, temperature_spread_c=spread)
    )
    result = evaluate_fan_policy(
        _policy(strategy=FanStrategy.EITHER),
        inputs=inputs,
    )

    assert result.reason_code is reason


def test_either_strategy_can_use_schedule_when_spread_is_unavailable() -> None:
    result = evaluate_fan_policy(
        _policy(strategy=FanStrategy.EITHER),
        inputs=_inputs(
            schedule_requested=True,
            temperature_spread_c=None,
        ),
    )

    assert result.directive is FanDirective.START
    assert result.reason_code is FanReasonCode.EITHER_REQUESTED
    assert result.degraded


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"occupancy_mode_id": AWAY}, FanReasonCode.OCCUPANCY_BLOCKED),
        ({"occupancy_mode_id": None}, FanReasonCode.OCCUPANCY_BLOCKED),
        ({"hvac_mode": "off"}, FanReasonCode.HVAC_MODE_BLOCKED),
        ({"hvac_mode": None}, FanReasonCode.HVAC_MODE_BLOCKED),
    ],
)
def test_occupancy_and_hvac_gates_block_start(
    changes: dict[str, object],
    reason: FanReasonCode,
) -> None:
    result = evaluate_fan_policy(_policy(), inputs=_inputs(**changes))

    assert result.directive is FanDirective.KEEP_STOPPED
    assert result.reason_code is reason
    assert result.lockout_active


def test_occupancy_gate_can_be_disabled_without_losing_mode_allowlist() -> None:
    result = evaluate_fan_policy(
        _policy(occupied_only=False),
        inputs=_inputs(occupancy_mode_id=None),
    )

    assert result.directive is FanDirective.START


@pytest.mark.parametrize(
    ("local", "period", "blocked"),
    [
        (
            datetime(2026, 7, 30, 22, 0, tzinfo=NY),
            FanQuietPeriod((Weekday.THURSDAY,), 21 * 60, 23 * 60),
            True,
        ),
        (
            datetime(2026, 7, 30, 23, 0, tzinfo=NY),
            FanQuietPeriod((Weekday.THURSDAY,), 21 * 60, 23 * 60),
            False,
        ),
        (
            datetime(2026, 7, 31, 1, 0, tzinfo=NY),
            FanQuietPeriod((Weekday.THURSDAY,), 22 * 60, 6 * 60),
            True,
        ),
        (
            datetime(2026, 7, 31, 7, 0, tzinfo=NY),
            FanQuietPeriod((Weekday.THURSDAY,), 22 * 60, 6 * 60),
            False,
        ),
    ],
)
def test_quiet_periods_support_exact_and_midnight_wrapping(
    local: datetime,
    period: FanQuietPeriod,
    blocked: bool,
) -> None:
    at_utc = local.astimezone(UTC)
    result = evaluate_fan_policy(
        _policy(quiet_periods=(period,)),
        inputs=_inputs(at_utc=at_utc, at_local=local),
    )

    assert (result.reason_code is FanReasonCode.QUIET_PERIOD) is blocked


def test_completed_and_current_runtime_use_strict_rolling_hour_overlap() -> None:
    budget = FanRuntimeBudget(
        (
            FanRuntimeInterval(
                NOW - timedelta(minutes=70),
                NOW - timedelta(minutes=50),
            ),
            FanRuntimeInterval(
                NOW - timedelta(minutes=40),
                NOW - timedelta(minutes=30),
            ),
        )
    )
    result = calculate_fan_runtime_budget(
        budget,
        at_utc=NOW,
        maximum_runtime_per_hour_seconds=1800,
        running_since_utc=NOW - timedelta(minutes=5),
    )

    assert result.runtime_seconds_last_hour == 1500
    assert result.remaining_seconds == 300
    assert not result.exhausted
    assert result.next_release_at_utc is None


def test_runtime_interval_entirely_before_window_contributes_zero() -> None:
    result = calculate_fan_runtime_budget(
        FanRuntimeBudget(
            (
                FanRuntimeInterval(
                    NOW - timedelta(minutes=90),
                    NOW - timedelta(minutes=70),
                ),
            )
        ),
        at_utc=NOW,
        maximum_runtime_per_hour_seconds=1200,
    )

    assert result.runtime_seconds_last_hour == 0
    assert result.remaining_seconds == 1200


def test_exhausted_budget_blocks_start_and_reports_release() -> None:
    interval = FanRuntimeInterval(
        NOW - timedelta(minutes=50),
        NOW - timedelta(minutes=30),
    )
    result = evaluate_fan_policy(
        _policy(),
        inputs=_inputs(runtime_budget=FanRuntimeBudget((interval,))),
    )

    assert result.directive is FanDirective.KEEP_STOPPED
    assert result.reason_code is FanReasonCode.RUNTIME_BUDGET_EXHAUSTED
    assert result.runtime_seconds_last_hour == 1200
    assert result.runtime_remaining_seconds == 0
    assert result.next_evaluation_at_utc == NOW + timedelta(minutes=10)


def test_interval_crossing_window_start_releases_budget_after_one_second() -> None:
    state = calculate_fan_runtime_budget(
        FanRuntimeBudget(
            (
                FanRuntimeInterval(
                    NOW - timedelta(minutes=70),
                    NOW - timedelta(minutes=50),
                ),
            )
        ),
        at_utc=NOW,
        maximum_runtime_per_hour_seconds=600,
    )

    assert state.exhausted
    assert state.next_release_at_utc == NOW + timedelta(seconds=1)


def test_running_fan_stops_immediately_at_hourly_budget_even_before_minimum() -> None:
    interval = FanRuntimeInterval(
        NOW - timedelta(minutes=30),
        NOW - timedelta(minutes=11),
    )
    result = evaluate_fan_policy(
        _policy(),
        inputs=_running_inputs(
            age_seconds=60,
            runtime_budget=FanRuntimeBudget((interval,)),
        ),
    )

    assert result.directive is FanDirective.STOP
    assert result.reason_code is FanReasonCode.RUNTIME_BUDGET_EXHAUSTED


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"effective_humidity_pct": 60.1}, FanReasonCode.HUMIDITY_HIGH),
        (
            {"effective_temperature_c": 25.0, "effective_humidity_pct": 60.0},
            FanReasonCode.DEW_POINT_HIGH,
        ),
        ({"effective_humidity_pct": None}, FanReasonCode.HUMIDITY_UNAVAILABLE),
        ({"effective_humidity_pct": 0.0}, FanReasonCode.HUMIDITY_UNAVAILABLE),
        (
            {"effective_temperature_c": None},
            FanReasonCode.HUMIDITY_UNAVAILABLE,
        ),
    ],
)
def test_humidity_dew_point_and_unavailable_lockouts(
    changes: dict[str, object],
    reason: FanReasonCode,
) -> None:
    result = evaluate_fan_policy(_policy(), inputs=_inputs(**changes))

    assert result.directive is FanDirective.KEEP_STOPPED
    assert result.reason_code is reason
    assert result.lockout_active


def test_humidity_only_policy_does_not_require_temperature_for_dew_point() -> None:
    result = evaluate_fan_policy(
        _policy(max_dew_point_c=None),
        inputs=_inputs(effective_temperature_c=None),
    )

    assert result.directive is FanDirective.START
    assert not result.degraded
    assert result.calculated_dew_point_c is None


def test_unavailable_humidity_can_ignore_and_degrade_without_lockout() -> None:
    result = evaluate_fan_policy(
        _policy(
            humidity_unavailable_policy=(
                FanHumidityUnavailablePolicy.IGNORE_AND_DEGRADE
            )
        ),
        inputs=_inputs(effective_humidity_pct=None),
    )

    assert result.directive is FanDirective.START
    assert result.degraded
    assert not result.lockout_active


def test_no_humidity_thresholds_need_no_humidity_data() -> None:
    result = evaluate_fan_policy(
        _policy(max_humidity_pct=None, max_dew_point_c=None),
        inputs=_inputs(
            effective_temperature_c=None,
            effective_humidity_pct=None,
        ),
    )

    assert result.directive is FanDirective.START
    assert not result.degraded


def test_elevated_humidity_after_cooling_uses_specific_lockout_deadline() -> None:
    result = evaluate_fan_policy(
        _policy(),
        inputs=_inputs(
            effective_humidity_pct=70.0,
            last_cooling_ended_at_utc=NOW - timedelta(minutes=5),
        ),
    )

    assert result.reason_code is FanReasonCode.POST_COOLING_LOCKOUT
    assert result.next_evaluation_at_utc == NOW + timedelta(minutes=10)


def test_expired_post_cooling_period_falls_back_to_humidity_reason() -> None:
    result = evaluate_fan_policy(
        _policy(),
        inputs=_inputs(
            effective_humidity_pct=70.0,
            last_cooling_ended_at_utc=NOW - timedelta(minutes=15),
        ),
    )

    assert result.reason_code is FanReasonCode.HUMIDITY_HIGH


def test_zero_post_cooling_policy_has_no_post_cooling_reason() -> None:
    result = evaluate_fan_policy(
        _policy(post_cooling_lockout_seconds=0),
        inputs=_inputs(
            effective_humidity_pct=70.0,
            last_cooling_ended_at_utc=NOW,
        ),
    )

    assert result.reason_code is FanReasonCode.HUMIDITY_HIGH


def test_minimum_on_delays_ordinary_and_humidity_stop() -> None:
    spread = evaluate_fan_policy(
        _policy(),
        inputs=_running_inputs(age_seconds=300, temperature_spread_c=0.0),
    )
    humidity = evaluate_fan_policy(
        _policy(),
        inputs=_running_inputs(age_seconds=300, effective_humidity_pct=70.0),
    )

    assert spread.directive is FanDirective.KEEP_RUNNING
    assert spread.reason_code is FanReasonCode.MINIMUM_ON_ACTIVE
    assert spread.next_evaluation_at_utc == NOW + timedelta(minutes=5)
    assert humidity.directive is FanDirective.KEEP_RUNNING
    assert humidity.reason_code is FanReasonCode.MINIMUM_ON_ACTIVE


def test_immediate_humidity_stop_bypasses_minimum_on() -> None:
    result = evaluate_fan_policy(
        _policy(immediate_stop_on_humidity_lockout=True),
        inputs=_running_inputs(age_seconds=60, effective_humidity_pct=70.0),
    )

    assert result.directive is FanDirective.STOP
    assert result.reason_code is FanReasonCode.HUMIDITY_HIGH


def test_running_fan_reports_budget_exhaustion_deadline() -> None:
    result = evaluate_fan_policy(
        _policy(maximum_runtime_per_hour_seconds=1800),
        inputs=_running_inputs(age_seconds=700),
    )

    assert result.directive is FanDirective.KEEP_RUNNING
    assert result.next_evaluation_at_utc == NOW + timedelta(seconds=1100)


@pytest.mark.parametrize(
    ("policy", "running", "directive", "reason"),
    [
        (
            _policy(enabled=False),
            False,
            FanDirective.KEEP_STOPPED,
            FanReasonCode.POLICY_DISABLED,
        ),
        (
            _policy(enabled=False),
            True,
            FanDirective.STOP,
            FanReasonCode.POLICY_DISABLED,
        ),
        (
            _policy(
                enabled=False,
                control_binding=_separate_binding(enabled=False),
            ),
            False,
            FanDirective.KEEP_STOPPED,
            FanReasonCode.POLICY_DISABLED,
        ),
        (
            _policy(
                enabled=False,
                control_binding=_separate_binding(enabled=False),
            ),
            True,
            FanDirective.STOP,
            FanReasonCode.POLICY_DISABLED,
        ),
    ],
)
def test_disabled_policy_stops_or_stays_stopped(
    policy: FanPolicy,
    running: bool,
    directive: FanDirective,
    reason: FanReasonCode,
) -> None:
    inputs = _running_inputs() if running else _inputs()
    result = evaluate_fan_policy(policy, inputs=inputs)

    assert result.directive is directive
    assert result.reason_code is reason


def test_disabled_binding_is_reason_coded() -> None:
    result = evaluate_fan_policy(
        _policy(control_binding=_separate_binding(enabled=False)),
        inputs=_inputs(),
    )

    assert result.directive is FanDirective.KEEP_STOPPED
    assert result.reason_code is FanReasonCode.BINDING_DISABLED


@pytest.mark.parametrize(
    ("evidence", "reason", "eligible"),
    [
        (
            FanRestoreEvidence(_policy(), None, None, True, False),
            FanRestoreReasonCode.NOT_THERMOSTAT_FAN_MODE,
            False,
        ),
        (
            FanRestoreEvidence(
                _policy(control_binding=_thermostat_binding()),
                None,
                "on",
                True,
                False,
            ),
            FanRestoreReasonCode.NO_PRIOR_MODE,
            False,
        ),
        (
            FanRestoreEvidence(
                _policy(control_binding=_thermostat_binding()),
                "auto",
                "on",
                True,
                True,
            ),
            FanRestoreReasonCode.EXTERNAL_CHANGE,
            False,
        ),
        (
            FanRestoreEvidence(
                _policy(control_binding=_thermostat_binding()),
                "auto",
                "on",
                False,
                False,
            ),
            FanRestoreReasonCode.CORRELATION_MISMATCH,
            False,
        ),
        (
            FanRestoreEvidence(
                _policy(control_binding=_thermostat_binding()),
                "auto",
                "auto",
                True,
                False,
            ),
            FanRestoreReasonCode.CURRENT_MODE_MISMATCH,
            False,
        ),
        (
            FanRestoreEvidence(
                _policy(control_binding=_thermostat_binding()),
                "auto",
                "on",
                True,
                False,
            ),
            FanRestoreReasonCode.ELIGIBLE,
            True,
        ),
    ],
)
def test_restore_requires_exact_current_mode_and_correlation(
    evidence: FanRestoreEvidence,
    reason: FanRestoreReasonCode,
    eligible: bool,
) -> None:
    result = evaluate_fan_restore(evidence)

    assert result.reason_code is reason
    assert result.eligible is eligible
    assert result.restore_mode == ("auto" if eligible else None)


@pytest.mark.parametrize(
    "evidence",
    [
        FanRestoreEvidence(
            _policy(control_binding=_thermostat_binding()),
            cast(Any, 1),
            "on",
            True,
            False,
        ),
        FanRestoreEvidence(
            _policy(control_binding=_thermostat_binding()),
            "auto",
            cast(Any, ""),
            True,
            False,
        ),
        FanRestoreEvidence(
            _policy(control_binding=_thermostat_binding()),
            "unsupported",
            "on",
            True,
            False,
        ),
        FanRestoreEvidence(
            _policy(control_binding=_thermostat_binding()),
            "auto",
            "unsupported",
            True,
            False,
        ),
        FanRestoreEvidence(
            _policy(control_binding=_thermostat_binding()),
            "on",
            "on",
            True,
            False,
        ),
        FanRestoreEvidence(
            _policy(control_binding=_thermostat_binding()),
            "auto",
            "on",
            cast(Any, 1),
            False,
        ),
        FanRestoreEvidence(
            _policy(control_binding=_thermostat_binding()),
            "auto",
            "on",
            True,
            cast(Any, 1),
        ),
    ],
)
def test_restore_rejects_malformed_or_unsupported_evidence(
    evidence: FanRestoreEvidence,
) -> None:
    with pytest.raises(SchemaValidationError):
        evaluate_fan_restore(evidence)


@pytest.mark.parametrize(
    "policy",
    [
        replace(_policy(), enabled=cast(Any, 1)),
        replace(_policy(), strategy=cast(Any, "either")),
        replace(_policy(), spread_start_c=nan),
        replace(_policy(), spread_stop_c=-0.1),
        replace(_policy(), spread_start_c=0.5),
        replace(_policy(), occupied_only=cast(Any, 1)),
        replace(_policy(), allowed_occupancy_modes=cast(Any, [HOME])),
        replace(_policy(), allowed_occupancy_modes=(HOME, HOME)),
        replace(_policy(), allowed_occupancy_modes=(cast(Any, "home"),)),
        replace(_policy(), occupied_only=True, allowed_occupancy_modes=()),
        replace(_policy(), allowed_hvac_modes=()),
        replace(_policy(), allowed_hvac_modes=cast(Any, ["heat"])),
        replace(_policy(), allowed_hvac_modes=("heat", "heat")),
        replace(_policy(), allowed_hvac_modes=(cast(Any, 1),)),
        replace(_policy(), quiet_periods=cast(Any, [])),
        replace(
            _policy(),
            quiet_periods=(
                FanQuietPeriod((Weekday.THURSDAY,), 100, 200),
                FanQuietPeriod((Weekday.THURSDAY,), 100, 200),
            ),
        ),
        replace(_policy(), minimum_on_seconds=0),
        replace(_policy(), maximum_runtime_per_hour_seconds=3601),
        replace(_policy(), minimum_on_seconds=1300),
        replace(_policy(), post_cooling_lockout_seconds=-1),
        replace(_policy(), max_humidity_pct=0),
        replace(_policy(), max_humidity_pct=101),
        replace(_policy(), max_dew_point_c=inf),
        replace(_policy(), max_dew_point_c=-101),
        replace(
            _policy(),
            humidity_unavailable_policy=cast(Any, "lock_out"),
        ),
        replace(
            _policy(),
            immediate_stop_on_humidity_lockout=cast(Any, 1),
        ),
    ],
)
def test_policy_validation_rejects_malformed_or_unsafe_values(
    policy: FanPolicy,
) -> None:
    with pytest.raises(SchemaValidationError):
        validate_fan_policy(policy)


@pytest.mark.parametrize(
    "binding",
    [
        cast(Any, "fan.bad"),
        replace(_separate_binding(), kind=cast(Any, "separate_fan")),
        replace(_separate_binding(), enabled=cast(Any, 1)),
        replace(_separate_binding(), enabled=True, reviewed=False),
        replace(_separate_binding(), entity_id="climate.bad"),
        replace(_separate_binding(), supported_modes=("on",)),
        replace(_thermostat_binding(), entity_id="fan.bad"),
        replace(_thermostat_binding(), supported_modes=()),
        replace(_thermostat_binding(), supported_modes=("auto", "auto")),
        replace(_thermostat_binding(), circulation_mode=None),
        replace(_thermostat_binding(), native_mode="on"),
        replace(_thermostat_binding(), circulation_mode="circulate"),
    ],
)
def test_binding_validation_requires_explicit_reviewed_supported_mapping(
    binding: FanControlBinding,
) -> None:
    with pytest.raises(SchemaValidationError):
        validate_fan_policy(
            _policy(
                enabled=False,
                control_binding=binding,
            )
        )


@pytest.mark.parametrize(
    "period",
    [
        cast(Any, "quiet"),
        FanQuietPeriod((), 100, 200),
        FanQuietPeriod((cast(Any, "thursday"),), 100, 200),
        FanQuietPeriod((Weekday.THURSDAY, Weekday.THURSDAY), 100, 200),
        FanQuietPeriod((Weekday.THURSDAY,), -1, 200),
        FanQuietPeriod((Weekday.THURSDAY,), 100, 1440),
        FanQuietPeriod((Weekday.THURSDAY,), 100, 100),
    ],
)
def test_quiet_period_validation_is_strict(period: FanQuietPeriod) -> None:
    with pytest.raises(SchemaValidationError):
        validate_fan_policy(_policy(quiet_periods=(period,)))


@pytest.mark.parametrize(
    "budget",
    [
        cast(Any, []),
        FanRuntimeBudget(cast(Any, [])),
        FanRuntimeBudget(
            tuple(
                FanRuntimeInterval(
                    NOW - timedelta(seconds=index + 2),
                    NOW - timedelta(seconds=index + 1),
                )
                for index in range(MAX_FAN_RUNTIME_INTERVALS + 1)
            )
        ),
        FanRuntimeBudget((cast(Any, "interval"),)),
        FanRuntimeBudget((FanRuntimeInterval(NOW, NOW),)),
        FanRuntimeBudget((FanRuntimeInterval(NOW, NOW - timedelta(seconds=1)),)),
        FanRuntimeBudget((FanRuntimeInterval(NOW - timedelta(days=2), NOW),)),
        FanRuntimeBudget(
            (
                FanRuntimeInterval(
                    NOW - timedelta(minutes=20),
                    NOW - timedelta(minutes=10),
                ),
                FanRuntimeInterval(
                    NOW - timedelta(minutes=15),
                    NOW - timedelta(minutes=5),
                ),
            )
        ),
        FanRuntimeBudget(
            (
                FanRuntimeInterval(
                    cast(Any, datetime(2026, 1, 1)),
                    NOW,
                ),
            )
        ),
    ],
)
def test_runtime_budget_validation_rejects_bad_history(
    budget: FanRuntimeBudget,
) -> None:
    with pytest.raises(SchemaValidationError):
        validate_fan_runtime_budget(budget)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        ({"at_utc": datetime(2026, 1, 1)}, "at_utc"),
        ({"at_local": datetime(2026, 1, 1)}, "at_local"),
        (
            {"at_local": (NOW + timedelta(seconds=1)).astimezone(NY)},
            "at_local",
        ),
        ({"is_running": cast(Any, 1)}, "fan_input"),
        ({"schedule_requested": cast(Any, 1)}, "fan_input"),
        ({"is_running": True}, "running_since_utc"),
        ({"running_since_utc": NOW}, "running_since_utc"),
        (
            {
                "is_running": True,
                "running_since_utc": NOW + timedelta(seconds=1),
            },
            "future",
        ),
        ({"temperature_spread_c": -1.0}, "temperature_spread_c"),
        ({"temperature_spread_c": nan}, "temperature_spread_c"),
        ({"effective_temperature_c": inf}, "effective_temperature_c"),
        ({"effective_humidity_pct": cast(Any, True)}, "effective_humidity_pct"),
        ({"occupancy_mode_id": cast(Any, "home")}, "occupancy_mode_id"),
        ({"hvac_mode": ""}, "hvac_mode"),
        (
            {"last_cooling_ended_at_utc": NOW + timedelta(seconds=1)},
            "future",
        ),
    ],
)
def test_evaluation_input_rejects_malformed_or_future_evidence(
    changes: dict[str, object],
    match: str,
) -> None:
    with pytest.raises(SchemaValidationError, match=match):
        evaluate_fan_policy(_policy(), inputs=_inputs(**changes))


def test_runtime_calculator_rejects_invalid_limits_future_and_overlap() -> None:
    with pytest.raises(SchemaValidationError, match="aware"):
        calculate_fan_runtime_budget(
            FanRuntimeBudget(()),
            at_utc=datetime(2026, 1, 1),
            maximum_runtime_per_hour_seconds=1200,
        )
    with pytest.raises(SchemaValidationError):
        calculate_fan_runtime_budget(
            FanRuntimeBudget(()),
            at_utc=NOW,
            maximum_runtime_per_hour_seconds=cast(Any, True),
        )
    with pytest.raises(SchemaValidationError, match="future"):
        calculate_fan_runtime_budget(
            FanRuntimeBudget(()),
            at_utc=NOW,
            maximum_runtime_per_hour_seconds=1200,
            running_since_utc=NOW + timedelta(seconds=1),
        )
    with pytest.raises(SchemaValidationError, match="future interval"):
        calculate_fan_runtime_budget(
            FanRuntimeBudget(
                (
                    FanRuntimeInterval(
                        NOW,
                        NOW + timedelta(seconds=1),
                    ),
                )
            ),
            at_utc=NOW,
            maximum_runtime_per_hour_seconds=1200,
        )
    with pytest.raises(SchemaValidationError, match="overlap"):
        calculate_fan_runtime_budget(
            FanRuntimeBudget(
                (
                    FanRuntimeInterval(
                        NOW - timedelta(minutes=10),
                        NOW - timedelta(minutes=5),
                    ),
                )
            ),
            at_utc=NOW,
            maximum_runtime_per_hour_seconds=1200,
            running_since_utc=NOW - timedelta(minutes=6),
        )


def test_policy_decoder_rejects_unknown_missing_and_wrong_container_fields() -> None:
    encoded = encode_fan_policy(_policy())
    encoded["unexpected"] = True
    with pytest.raises(SchemaValidationError, match="unknown"):
        decode_fan_policy(encoded)

    encoded = encode_fan_policy(_policy())
    del encoded["strategy"]
    with pytest.raises(SchemaValidationError, match="missing"):
        decode_fan_policy(encoded)

    with pytest.raises(SchemaValidationError, match="object"):
        decode_fan_policy([])

    encoded = encode_fan_policy(_policy())
    encoded["control_binding"] = []
    with pytest.raises(SchemaValidationError, match="object"):
        decode_fan_policy(encoded)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("enabled", 1),
        ("strategy", "unsupported"),
        ("spread_start_c", True),
        ("allowed_occupancy_modes", {}),
        ("allowed_occupancy_modes", ["not-a-uuid"]),
        ("allowed_hvac_modes", {}),
        ("allowed_hvac_modes", [""]),
        ("quiet_periods", {}),
        ("minimum_on_seconds", True),
        ("max_humidity_pct", "60"),
        ("humidity_unavailable_policy", "unsupported"),
    ],
)
def test_policy_decoder_rejects_malformed_json_fields(
    path: str,
    value: object,
) -> None:
    encoded = encode_fan_policy(_policy())
    encoded[path] = value

    with pytest.raises(SchemaValidationError):
        decode_fan_policy(encoded)


def test_policy_decoder_rejects_bad_binding_and_quiet_period_shapes() -> None:
    encoded = encode_fan_policy(_policy())
    binding = cast(dict[str, object], encoded["control_binding"])
    binding["unexpected"] = True
    with pytest.raises(SchemaValidationError):
        decode_fan_policy(encoded)

    encoded = encode_fan_policy(_policy())
    quiet = {
        "weekdays": ["unsupported"],
        "start_minute": 1,
        "end_minute": 2,
    }
    encoded["quiet_periods"] = [quiet]
    with pytest.raises(SchemaValidationError):
        decode_fan_policy(encoded)

    encoded = encode_fan_policy(_policy())
    encoded["quiet_periods"] = [{"weekdays": []}]
    with pytest.raises(SchemaValidationError):
        decode_fan_policy(encoded)


def test_runtime_decoder_rejects_wrong_shape_fields_and_datetime() -> None:
    with pytest.raises(SchemaValidationError):
        decode_fan_runtime_budget({})
    with pytest.raises(SchemaValidationError):
        decode_fan_runtime_budget([[]])
    with pytest.raises(SchemaValidationError):
        decode_fan_runtime_budget(
            [{"started_at_utc": NOW.isoformat(), "unexpected": "x"}]
        )
    with pytest.raises(SchemaValidationError):
        decode_fan_runtime_budget(
            [{"started_at_utc": "bad", "ended_at_utc": NOW.isoformat()}]
        )
    with pytest.raises(SchemaValidationError):
        decode_fan_runtime_budget(
            [{"started_at_utc": 1, "ended_at_utc": NOW.isoformat()}]
        )
    with pytest.raises(SchemaValidationError):
        decode_fan_runtime_budget(
            [
                {
                    "started_at_utc": datetime(2026, 1, 1).isoformat(),
                    "ended_at_utc": NOW.isoformat(),
                }
            ]
        )


def test_fan_decisions_are_fan_only_and_privacy_bounded() -> None:
    result = evaluate_fan_policy(_policy(), inputs=_inputs())
    projection = repr(result)

    assert "target" not in projection
    assert "hvac_mode" not in projection
    assert "entity_id" not in projection
    assert "context" not in projection
