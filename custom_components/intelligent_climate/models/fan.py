"""Pure fan policy and runtime-budget records for Phase 2 Task 15."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from typing import cast

from .identifiers import OccupancyModeId
from .schedule import Weekday
from .schema import SchemaValidationError

MAX_FAN_RUNTIME_INTERVALS = 100


class FanBindingKind(StrEnum):
    """Supported, explicitly mapped circulation control surfaces."""

    SEPARATE_FAN = "separate_fan"
    THERMOSTAT_FAN_MODE = "thermostat_fan_mode"


class FanStrategy(StrEnum):
    """Supported basic circulation request strategies."""

    SCHEDULE = "schedule"
    TEMPERATURE_SPREAD = "temperature_spread"
    EITHER = "either"


class FanHumidityUnavailablePolicy(StrEnum):
    """Handling when a configured humidity/dew-point gate lacks data."""

    LOCK_OUT = "lock_out"
    IGNORE_AND_DEGRADE = "ignore_and_degrade"


@dataclass(frozen=True, slots=True)
class FanControlBinding:
    """One reviewed fan entity or thermostat fan-mode mapping."""

    entity_id: str
    kind: FanBindingKind
    supported_modes: tuple[str, ...]
    circulation_mode: str | None
    native_mode: str | None
    enabled: bool = False
    reviewed: bool = False


@dataclass(frozen=True, slots=True)
class FanQuietPeriod:
    """A local-wall-time quiet interval; end may wrap through midnight."""

    weekdays: tuple[Weekday, ...]
    start_minute: int
    end_minute: int


@dataclass(frozen=True, slots=True)
class FanPolicy:
    """Complete pure Phase 2 basic circulation policy."""

    enabled: bool
    control_binding: FanControlBinding
    strategy: FanStrategy
    spread_start_c: float
    spread_stop_c: float
    occupied_only: bool
    allowed_occupancy_modes: tuple[OccupancyModeId, ...]
    allowed_hvac_modes: tuple[str, ...]
    quiet_periods: tuple[FanQuietPeriod, ...]
    minimum_on_seconds: int
    maximum_runtime_per_hour_seconds: int
    post_cooling_lockout_seconds: int
    max_humidity_pct: float | None
    max_dew_point_c: float | None
    humidity_unavailable_policy: FanHumidityUnavailablePolicy
    immediate_stop_on_humidity_lockout: bool = False


@dataclass(frozen=True, slots=True)
class FanRuntimeInterval:
    """One completed UTC fan-on interval used by the rolling-hour budget."""

    started_at_utc: datetime
    ended_at_utc: datetime


@dataclass(frozen=True, slots=True)
class FanRuntimeBudget:
    """Restart-safe bounded collection of completed fan-on intervals."""

    intervals: tuple[FanRuntimeInterval, ...]


def validate_fan_policy(policy: FanPolicy) -> None:
    """Strictly validate fan binding, gates, thresholds, and timing."""
    if not isinstance(policy.enabled, bool):
        raise SchemaValidationError("enabled", "must be a boolean")
    _validate_fan_binding(policy.control_binding)
    if not isinstance(policy.strategy, FanStrategy):
        raise SchemaValidationError("strategy", "is unsupported")
    _finite(policy.spread_start_c, "spread_start_c")
    _finite(policy.spread_stop_c, "spread_stop_c")
    if policy.spread_stop_c < 0 or policy.spread_start_c <= policy.spread_stop_c:
        raise SchemaValidationError(
            "spread_start_c", "must be greater than a nonnegative stop spread"
        )
    if not isinstance(policy.occupied_only, bool):
        raise SchemaValidationError("occupied_only", "must be a boolean")
    if not isinstance(policy.allowed_occupancy_modes, tuple):
        raise SchemaValidationError("allowed_occupancy_modes", "must be a tuple")
    if any(
        not isinstance(item, OccupancyModeId) for item in policy.allowed_occupancy_modes
    ):
        raise SchemaValidationError(
            "allowed_occupancy_modes", "must contain occupancy mode IDs"
        )
    if len(set(policy.allowed_occupancy_modes)) != len(policy.allowed_occupancy_modes):
        raise SchemaValidationError(
            "allowed_occupancy_modes", "must not contain duplicates"
        )
    if policy.occupied_only and not policy.allowed_occupancy_modes:
        raise SchemaValidationError(
            "allowed_occupancy_modes", "must not be empty when occupied_only"
        )
    _bounded_strings(policy.allowed_hvac_modes, "allowed_hvac_modes", allow_empty=False)
    if not isinstance(policy.quiet_periods, tuple):
        raise SchemaValidationError("quiet_periods", "must be a tuple")
    for index, period in enumerate(policy.quiet_periods):
        _validate_quiet_period(period, f"quiet_periods[{index}]")
    if len(set(policy.quiet_periods)) != len(policy.quiet_periods):
        raise SchemaValidationError("quiet_periods", "must not contain duplicates")
    for path, value, allow_zero in (
        ("minimum_on_seconds", policy.minimum_on_seconds, False),
        (
            "maximum_runtime_per_hour_seconds",
            policy.maximum_runtime_per_hour_seconds,
            False,
        ),
        (
            "post_cooling_lockout_seconds",
            policy.post_cooling_lockout_seconds,
            True,
        ),
    ):
        _whole_seconds(value, path, allow_zero=allow_zero)
    if policy.maximum_runtime_per_hour_seconds > 3600:
        raise SchemaValidationError(
            "maximum_runtime_per_hour_seconds", "must not exceed 3600"
        )
    if policy.minimum_on_seconds > policy.maximum_runtime_per_hour_seconds:
        raise SchemaValidationError(
            "minimum_on_seconds", "must not exceed the hourly runtime maximum"
        )
    if policy.max_humidity_pct is not None:
        _finite(policy.max_humidity_pct, "max_humidity_pct")
        if not 0 < policy.max_humidity_pct <= 100:
            raise SchemaValidationError(
                "max_humidity_pct", "must be greater than 0 and at most 100"
            )
    if policy.max_dew_point_c is not None:
        _finite(policy.max_dew_point_c, "max_dew_point_c")
        if not -100 <= policy.max_dew_point_c <= 100:
            raise SchemaValidationError(
                "max_dew_point_c", "must be between -100 and 100"
            )
    if not isinstance(policy.humidity_unavailable_policy, FanHumidityUnavailablePolicy):
        raise SchemaValidationError("humidity_unavailable_policy", "is unsupported")
    if not isinstance(policy.immediate_stop_on_humidity_lockout, bool):
        raise SchemaValidationError(
            "immediate_stop_on_humidity_lockout", "must be a boolean"
        )


def validate_fan_runtime_budget(budget: FanRuntimeBudget) -> None:
    """Reject malformed, overlapping, unsorted, or unbounded runtime evidence."""
    if not isinstance(budget, FanRuntimeBudget) or not isinstance(
        budget.intervals, tuple
    ):
        raise SchemaValidationError("fan_runtime_budget", "must be a budget record")
    if len(budget.intervals) > MAX_FAN_RUNTIME_INTERVALS:
        raise SchemaValidationError(
            "fan_runtime_budget",
            f"must contain at most {MAX_FAN_RUNTIME_INTERVALS} intervals",
        )
    previous_end: datetime | None = None
    for index, interval in enumerate(budget.intervals):
        path = f"fan_runtime_budget.intervals[{index}]"
        if not isinstance(interval, FanRuntimeInterval):
            raise SchemaValidationError(path, "must be a runtime interval")
        started = _aware_utc(interval.started_at_utc, f"{path}.started_at_utc")
        ended = _aware_utc(interval.ended_at_utc, f"{path}.ended_at_utc")
        if started >= ended:
            raise SchemaValidationError(path, "start must be before end")
        if (ended - started).total_seconds() > 86400:
            raise SchemaValidationError(path, "must not exceed 24 hours")
        if previous_end is not None and started < previous_end:
            raise SchemaValidationError(
                "fan_runtime_budget.intervals",
                "must be chronological and nonoverlapping",
            )
        previous_end = ended


def encode_fan_policy(policy: FanPolicy) -> dict[str, object]:
    """Encode a validated policy without activating persistence."""
    validate_fan_policy(policy)
    binding = policy.control_binding
    return {
        "enabled": policy.enabled,
        "control_binding": {
            "entity_id": binding.entity_id,
            "kind": binding.kind.value,
            "supported_modes": list(binding.supported_modes),
            "circulation_mode": binding.circulation_mode,
            "native_mode": binding.native_mode,
            "enabled": binding.enabled,
            "reviewed": binding.reviewed,
        },
        "strategy": policy.strategy.value,
        "spread_start_c": policy.spread_start_c,
        "spread_stop_c": policy.spread_stop_c,
        "occupied_only": policy.occupied_only,
        "allowed_occupancy_modes": [
            str(item) for item in policy.allowed_occupancy_modes
        ],
        "allowed_hvac_modes": list(policy.allowed_hvac_modes),
        "quiet_periods": [
            {
                "weekdays": [item.value for item in period.weekdays],
                "start_minute": period.start_minute,
                "end_minute": period.end_minute,
            }
            for period in policy.quiet_periods
        ],
        "minimum_on_seconds": policy.minimum_on_seconds,
        "maximum_runtime_per_hour_seconds": (policy.maximum_runtime_per_hour_seconds),
        "post_cooling_lockout_seconds": policy.post_cooling_lockout_seconds,
        "max_humidity_pct": policy.max_humidity_pct,
        "max_dew_point_c": policy.max_dew_point_c,
        "humidity_unavailable_policy": policy.humidity_unavailable_policy.value,
        "immediate_stop_on_humidity_lockout": (
            policy.immediate_stop_on_humidity_lockout
        ),
    }


def decode_fan_policy(value: object) -> FanPolicy:
    """Strictly decode one policy from JSON-compatible data."""
    data = _object(value, "fan_policy")
    _exact_fields(
        data,
        {
            "enabled",
            "control_binding",
            "strategy",
            "spread_start_c",
            "spread_stop_c",
            "occupied_only",
            "allowed_occupancy_modes",
            "allowed_hvac_modes",
            "quiet_periods",
            "minimum_on_seconds",
            "maximum_runtime_per_hour_seconds",
            "post_cooling_lockout_seconds",
            "max_humidity_pct",
            "max_dew_point_c",
            "humidity_unavailable_policy",
            "immediate_stop_on_humidity_lockout",
        },
        "fan_policy",
    )
    binding_data = _object(data["control_binding"], "control_binding")
    _exact_fields(
        binding_data,
        {
            "entity_id",
            "kind",
            "supported_modes",
            "circulation_mode",
            "native_mode",
            "enabled",
            "reviewed",
        },
        "control_binding",
    )
    try:
        policy = FanPolicy(
            enabled=_bool(data["enabled"], "enabled"),
            control_binding=FanControlBinding(
                entity_id=_string(binding_data["entity_id"], "entity_id"),
                kind=FanBindingKind(_string(binding_data["kind"], "kind")),
                supported_modes=tuple(
                    _string(item, "supported_modes")
                    for item in _list(
                        binding_data["supported_modes"], "supported_modes"
                    )
                ),
                circulation_mode=_optional_string(
                    binding_data["circulation_mode"], "circulation_mode"
                ),
                native_mode=_optional_string(
                    binding_data["native_mode"], "native_mode"
                ),
                enabled=_bool(binding_data["enabled"], "binding.enabled"),
                reviewed=_bool(binding_data["reviewed"], "binding.reviewed"),
            ),
            strategy=FanStrategy(_string(data["strategy"], "strategy")),
            spread_start_c=_number(data["spread_start_c"], "spread_start_c"),
            spread_stop_c=_number(data["spread_stop_c"], "spread_stop_c"),
            occupied_only=_bool(data["occupied_only"], "occupied_only"),
            allowed_occupancy_modes=tuple(
                OccupancyModeId.parse(_string(item, "allowed_occupancy_modes"))
                for item in _list(
                    data["allowed_occupancy_modes"], "allowed_occupancy_modes"
                )
            ),
            allowed_hvac_modes=tuple(
                _string(item, "allowed_hvac_modes")
                for item in _list(data["allowed_hvac_modes"], "allowed_hvac_modes")
            ),
            quiet_periods=tuple(
                _decode_quiet_period(item, index)
                for index, item in enumerate(
                    _list(data["quiet_periods"], "quiet_periods")
                )
            ),
            minimum_on_seconds=_int(data["minimum_on_seconds"], "minimum_on_seconds"),
            maximum_runtime_per_hour_seconds=_int(
                data["maximum_runtime_per_hour_seconds"],
                "maximum_runtime_per_hour_seconds",
            ),
            post_cooling_lockout_seconds=_int(
                data["post_cooling_lockout_seconds"],
                "post_cooling_lockout_seconds",
            ),
            max_humidity_pct=_optional_number(
                data["max_humidity_pct"], "max_humidity_pct"
            ),
            max_dew_point_c=_optional_number(
                data["max_dew_point_c"], "max_dew_point_c"
            ),
            humidity_unavailable_policy=FanHumidityUnavailablePolicy(
                _string(
                    data["humidity_unavailable_policy"],
                    "humidity_unavailable_policy",
                )
            ),
            immediate_stop_on_humidity_lockout=_bool(
                data["immediate_stop_on_humidity_lockout"],
                "immediate_stop_on_humidity_lockout",
            ),
        )
    except (TypeError, ValueError) as err:
        raise SchemaValidationError("fan_policy", "contains an invalid value") from err
    validate_fan_policy(policy)
    return policy


def encode_fan_runtime_budget(budget: FanRuntimeBudget) -> list[dict[str, str]]:
    """Encode bounded runtime evidence for the already-reserved Store slot."""
    validate_fan_runtime_budget(budget)
    return [
        {
            "started_at_utc": _aware_utc(
                item.started_at_utc, "started_at_utc"
            ).isoformat(),
            "ended_at_utc": _aware_utc(item.ended_at_utc, "ended_at_utc").isoformat(),
        }
        for item in budget.intervals
    ]


def decode_fan_runtime_budget(value: object) -> FanRuntimeBudget:
    """Strictly decode bounded completed runtime intervals."""
    items = _list(value, "fan_runtime_budget")
    intervals: list[FanRuntimeInterval] = []
    for index, item in enumerate(items):
        path = f"fan_runtime_budget[{index}]"
        data = _object(item, path)
        _exact_fields(data, {"started_at_utc", "ended_at_utc"}, path)
        intervals.append(
            FanRuntimeInterval(
                _datetime(data["started_at_utc"], f"{path}.started_at_utc"),
                _datetime(data["ended_at_utc"], f"{path}.ended_at_utc"),
            )
        )
    budget = FanRuntimeBudget(tuple(intervals))
    validate_fan_runtime_budget(budget)
    return budget


def _validate_fan_binding(binding: FanControlBinding) -> None:
    if not isinstance(binding, FanControlBinding):
        raise SchemaValidationError("control_binding", "must be a fan binding")
    if not isinstance(binding.kind, FanBindingKind):
        raise SchemaValidationError("control_binding.kind", "is unsupported")
    if not isinstance(binding.enabled, bool) or not isinstance(binding.reviewed, bool):
        raise SchemaValidationError(
            "control_binding", "enabled and reviewed must be booleans"
        )
    if binding.enabled and not binding.reviewed:
        raise SchemaValidationError(
            "control_binding.enabled", "cannot be true before review"
        )
    if binding.kind is FanBindingKind.SEPARATE_FAN:
        if not isinstance(binding.entity_id, str) or not binding.entity_id.startswith(
            "fan."
        ):
            raise SchemaValidationError(
                "control_binding.entity_id", "must be a fan entity ID"
            )
        if (
            binding.supported_modes
            or binding.circulation_mode is not None
            or binding.native_mode is not None
        ):
            raise SchemaValidationError(
                "control_binding",
                "separate fan binding must not define thermostat fan modes",
            )
        return
    if not isinstance(binding.entity_id, str) or not binding.entity_id.startswith(
        "climate."
    ):
        raise SchemaValidationError(
            "control_binding.entity_id", "must be a climate entity ID"
        )
    _bounded_strings(
        binding.supported_modes,
        "control_binding.supported_modes",
        allow_empty=False,
    )
    if (
        binding.circulation_mode is None
        or binding.native_mode is None
        or binding.circulation_mode == binding.native_mode
        or binding.circulation_mode not in binding.supported_modes
        or binding.native_mode not in binding.supported_modes
    ):
        raise SchemaValidationError(
            "control_binding",
            "requires distinct mapped circulation and native supported modes",
        )


def _validate_quiet_period(period: FanQuietPeriod, path: str) -> None:
    if not isinstance(period, FanQuietPeriod):
        raise SchemaValidationError(path, "must be a quiet period")
    if not period.weekdays or any(
        not isinstance(item, Weekday) for item in period.weekdays
    ):
        raise SchemaValidationError(f"{path}.weekdays", "must contain weekdays")
    if len(set(period.weekdays)) != len(period.weekdays):
        raise SchemaValidationError(f"{path}.weekdays", "must not contain duplicates")
    for name, value in (
        ("start_minute", period.start_minute),
        ("end_minute", period.end_minute),
    ):
        if (
            not isinstance(value, int)
            or isinstance(value, bool)
            or not 0 <= value < 1440
        ):
            raise SchemaValidationError(
                f"{path}.{name}", "must be a minute from 0 through 1439"
            )
    if period.start_minute == period.end_minute:
        raise SchemaValidationError(path, "start and end must differ")


def _decode_quiet_period(value: object, index: int) -> FanQuietPeriod:
    path = f"quiet_periods[{index}]"
    data = _object(value, path)
    _exact_fields(data, {"weekdays", "start_minute", "end_minute"}, path)
    try:
        return FanQuietPeriod(
            weekdays=tuple(
                Weekday(_string(item, f"{path}.weekdays"))
                for item in _list(data["weekdays"], f"{path}.weekdays")
            ),
            start_minute=_int(data["start_minute"], f"{path}.start_minute"),
            end_minute=_int(data["end_minute"], f"{path}.end_minute"),
        )
    except ValueError as err:
        raise SchemaValidationError(path, "contains an invalid value") from err


def _bounded_strings(values: tuple[str, ...], path: str, *, allow_empty: bool) -> None:
    if not isinstance(values, tuple):
        raise SchemaValidationError(path, "must be a tuple")
    if not allow_empty and not values:
        raise SchemaValidationError(path, "must not be empty")
    if any(not isinstance(item, str) or not item or len(item) > 64 for item in values):
        raise SchemaValidationError(path, "must contain bounded nonempty strings")
    if len(set(values)) != len(values):
        raise SchemaValidationError(path, "must not contain duplicates")


def _whole_seconds(value: object, path: str, *, allow_zero: bool) -> None:
    minimum = 0 if allow_zero else 1
    if (
        not isinstance(value, int)
        or isinstance(value, bool)
        or value < minimum
        or value > 86400
    ):
        raise SchemaValidationError(
            path,
            f"must be a whole number from {minimum} through 86400",
        )


def _finite(value: object, path: str) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not isfinite(value)
    ):
        raise SchemaValidationError(path, "must be finite")


def _aware_utc(value: object, path: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise SchemaValidationError(path, "must be an aware datetime")
    return value.astimezone(UTC)


def _datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be an ISO datetime string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as err:
        raise SchemaValidationError(path, "must be an ISO datetime string") from err
    return _aware_utc(parsed, path)


def _object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise SchemaValidationError(path, "must be an object")
    return value


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise SchemaValidationError(path, "must be a list")
    return value


def _exact_fields(value: dict[str, object], expected: set[str], path: str) -> None:
    if set(value) != expected:
        raise SchemaValidationError(path, "contains missing or unknown fields")


def _string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise SchemaValidationError(path, "must be a nonempty string")
    return value


def _optional_string(value: object, path: str) -> str | None:
    return None if value is None else _string(value, path)


def _bool(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(path, "must be a boolean")
    return value


def _int(value: object, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError(path, "must be a whole number")
    return value


def _number(value: object, path: str) -> float:
    _finite(value, path)
    return float(cast(int | float, value))


def _optional_number(value: object, path: str) -> float | None:
    return None if value is None else _number(value, path)
