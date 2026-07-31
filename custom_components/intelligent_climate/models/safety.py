"""Pure central safety-gate records for Phase 2 Task 16."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite

from .command import (
    CommandAuthority,
    CommandCause,
    CommandControlledField,
    CommandKind,
    NormalizedCommandValues,
    NormalizedStateEvidence,
    validate_state_evidence,
)
from .control import ControlExecutionState
from .identifiers import EquipmentGroupId, SafetyEvaluationId, ZoneId
from .modes import OperatingMode
from .phase2_schema import Phase2CommandTiming, Phase2SafetyLimits
from .schema import EquipmentRelationship, SchemaValidationError


class SafetyDisposition(StrEnum):
    """Physically inert outcome of one complete safety evaluation."""

    ELIGIBLE = "eligible"
    SUPPRESSED = "suppressed"
    BLOCKED = "blocked"


class SafetyReasonCode(StrEnum):
    """Stable privacy-safe reason for one safety result."""

    ALL_HARD_GATES_PASSED = "all_hard_gates_passed"
    OBSERVE_ONLY = "observe_only"
    SHADOW_ONLY = "shadow_only"
    CONTROL_STATE_BLOCKED = "control_state_blocked"
    MANUAL_AUTHORITY_INVALID = "manual_authority_invalid"
    SCHEDULED_AUTHORITY_INVALID = "scheduled_authority_invalid"
    TARGET_NOT_OWNED = "target_not_owned"
    COMMAND_AUTHORITY_INVALID = "command_authority_invalid"
    ENTITY_DOMAIN_INVALID = "entity_domain_invalid"
    CAPABILITY_UNAVAILABLE = "capability_unavailable"
    CAPABILITY_STALE = "capability_stale"
    COMMAND_KIND_UNSUPPORTED = "command_kind_unsupported"
    HVAC_MODE_UNSUPPORTED = "hvac_mode_unsupported"
    FAN_MODE_UNSUPPORTED = "fan_mode_unsupported"
    TARGET_OUTSIDE_ADVERTISED_LIMITS = "target_outside_advertised_limits"
    TARGET_OUTSIDE_USER_LIMITS = "target_outside_user_limits"
    RANGE_SEPARATION_INVALID = "range_separation_invalid"
    PRECONDITION_UNAVAILABLE = "precondition_unavailable"
    PRECONDITION_STALE = "precondition_stale"
    CORRELATION_AWAITING = "correlation_awaiting"
    CORRELATION_UNCERTAIN = "correlation_uncertain"
    EXTERNAL_CHANGE = "external_change"
    FAILURE_LOCKOUT = "failure_lockout"
    NOT_BEFORE = "not_before"
    EXPIRED = "expired"
    STARTUP_QUIET_PERIOD = "startup_quiet_period"
    FAILURE_COOLDOWN = "failure_cooldown"
    MINIMUM_INTERVAL = "minimum_interval"
    MODE_REVERSAL_COOLDOWN = "mode_reversal_cooldown"
    SEMANTIC_DEADBAND = "semantic_deadband"
    ARBITRATION_REQUIRED = "arbitration_required"
    ARBITRATION_BLOCKED = "arbitration_blocked"
    ARBITRATION_MISMATCH = "arbitration_mismatch"
    FAN_EVIDENCE_REQUIRED = "fan_evidence_required"
    FAN_POLICY_BLOCKED = "fan_policy_blocked"
    FAN_POLICY_MISMATCH = "fan_policy_mismatch"
    FAN_RESTORE_BLOCKED = "fan_restore_blocked"


class SafetyTargetDirection(StrEnum):
    """Limit family for one single-target request."""

    HEAT = "heat"
    COOL = "cool"


class SafetyCorrelationState(StrEnum):
    """Current correlation/failure state for one command authority."""

    CLEAR = "clear"
    AWAITING_ACKNOWLEDGEMENT = "awaiting_acknowledgement"
    UNCERTAIN = "uncertain"
    EXTERNAL_CHANGE = "external_change"
    FAILURE_LOCKOUT = "failure_lockout"


class FanSafetyOperation(StrEnum):
    """Task 15 evidence expected for one fan request."""

    START = "start"
    STOP = "stop"
    RESTORE = "restore"


@dataclass(frozen=True, slots=True)
class SafetyCommandCandidate:
    """Typed pre-plan request evaluated without constructing an executable plan."""

    safety_evaluation_id: SafetyEvaluationId
    entry_id: str
    equipment_group_id: EquipmentGroupId
    zone_id: ZoneId
    target_entity_id: str
    command_kind: CommandKind
    requested_fields: frozenset[CommandControlledField]
    requested_values: NormalizedCommandValues
    target_direction: SafetyTargetDirection | None
    authority: CommandAuthority
    cause: CommandCause
    observed_precondition: NormalizedStateEvidence
    requested_against_revision: int
    created_at_utc: datetime
    not_before_utc: datetime
    expires_at_utc: datetime

    def __post_init__(self) -> None:
        """Reject malformed candidates at the pure input boundary."""
        validate_safety_candidate(self)


@dataclass(frozen=True, slots=True)
class SafetyOwnership:
    """Explicit entry/group/zone ownership and reviewed command authority."""

    entry_id: str
    equipment_group_id: EquipmentGroupId
    zone_ids: tuple[ZoneId, ...]
    relationship: EquipmentRelationship
    owned_entity_ids: tuple[str, ...]
    command_authority_entity_ids: tuple[str, ...]
    authority_reviewed: bool

    def __post_init__(self) -> None:
        """Reject incomplete or contradictory ownership."""
        validate_safety_ownership(self)


@dataclass(frozen=True, slots=True)
class SafetyCapabilitySnapshot:
    """Caller-supplied current capability facts for the target entity."""

    entity_id: str
    available: bool
    supported_command_kinds: frozenset[CommandKind]
    hvac_modes: tuple[str, ...]
    fan_modes: tuple[str, ...]
    advertised_min_target_c: float | None
    advertised_max_target_c: float | None
    observed_at_utc: datetime

    def __post_init__(self) -> None:
        """Reject fabricated, malformed, or contradictory capabilities."""
        validate_safety_capabilities(self)


@dataclass(frozen=True, slots=True)
class SafetyAuthorityEvidence:
    """Current operating and execution authority supplied by Task 9."""

    operating_mode: OperatingMode
    control_state: ControlExecutionState
    manual_intent_authorized: bool
    shadow_qualified: bool
    active_control_armed: bool

    def __post_init__(self) -> None:
        """Reject malformed authority flags."""
        validate_safety_authority(self)


@dataclass(frozen=True, slots=True)
class SafetyTimingEvidence:
    """Caller-supplied timestamps for interval and cooldown decisions."""

    runtime_started_at_utc: datetime
    last_command_at_utc: datetime | None = None
    last_mode_change_at_utc: datetime | None = None
    last_terminal_failure_at_utc: datetime | None = None

    def __post_init__(self) -> None:
        """Reject naive or contradictory timestamp types."""
        validate_safety_timing(self)


@dataclass(frozen=True, slots=True)
class SafetyGateDecision:
    """Privacy-bounded result; it is not a command or dispatch token."""

    safety_evaluation_id: SafetyEvaluationId
    disposition: SafetyDisposition
    reason_code: SafetyReasonCode
    hard_checks_passed: bool
    reevaluate_at_utc: datetime | None
    explanation: str

    @property
    def eligible(self) -> bool:
        """Return whether a later suppressed/active sink may consume the result."""
        return self.disposition is SafetyDisposition.ELIGIBLE


_COMMAND_FIELDS: dict[CommandKind, frozenset[frozenset[CommandControlledField]]] = {
    CommandKind.SET_TARGET: frozenset(
        {
            frozenset({CommandControlledField.TARGET}),
            frozenset(
                {
                    CommandControlledField.TARGET,
                    CommandControlledField.HVAC_MODE,
                }
            ),
        }
    ),
    CommandKind.SET_RANGE: frozenset(
        {
            frozenset({CommandControlledField.RANGE}),
            frozenset(
                {
                    CommandControlledField.RANGE,
                    CommandControlledField.HVAC_MODE,
                }
            ),
        }
    ),
    CommandKind.SET_HVAC_MODE: frozenset(
        {frozenset({CommandControlledField.HVAC_MODE})}
    ),
    CommandKind.SET_FAN_MODE: frozenset({frozenset({CommandControlledField.FAN_MODE})}),
    CommandKind.FAN_ON: frozenset({frozenset({CommandControlledField.FAN_STATE})}),
    CommandKind.FAN_OFF: frozenset({frozenset({CommandControlledField.FAN_STATE})}),
}


def validate_safety_candidate(candidate: SafetyCommandCandidate) -> None:
    """Validate identity, request shape, values, revision, and timestamps."""
    if not isinstance(candidate.safety_evaluation_id, SafetyEvaluationId):
        raise SchemaValidationError(
            "safety_evaluation_id", "must be a safety evaluation ID"
        )
    _text(candidate.entry_id, "entry_id")
    if not isinstance(candidate.equipment_group_id, EquipmentGroupId):
        raise SchemaValidationError(
            "equipment_group_id", "must be an equipment group ID"
        )
    if not isinstance(candidate.zone_id, ZoneId):
        raise SchemaValidationError("zone_id", "must be a zone ID")
    _entity_id(candidate.target_entity_id, "target_entity_id")
    if not isinstance(candidate.command_kind, CommandKind):
        raise SchemaValidationError("command_kind", "is unsupported")
    if not isinstance(candidate.requested_fields, frozenset):
        raise SchemaValidationError("requested_fields", "must be an immutable set")
    if candidate.requested_fields not in _COMMAND_FIELDS[candidate.command_kind]:
        raise SchemaValidationError(
            "requested_fields", "does not match the command kind"
        )
    if not isinstance(candidate.requested_values, NormalizedCommandValues):
        raise SchemaValidationError(
            "requested_values", "must be normalized command values"
        )
    _validate_requested_values(candidate)
    if not isinstance(candidate.authority, CommandAuthority):
        raise SchemaValidationError("authority", "is unsupported")
    if not isinstance(candidate.cause, CommandCause):
        raise SchemaValidationError("cause", "is unsupported")
    _validate_authority_cause(candidate.authority, candidate.cause)
    validate_state_evidence(
        candidate.observed_precondition,
        path="observed_precondition",
    )
    if not candidate.observed_precondition.available:
        raise SchemaValidationError(
            "observed_precondition.available",
            "must be true when a candidate is created",
        )
    _require_precondition_fields(candidate)
    revision = _positive_integer(
        candidate.requested_against_revision,
        "requested_against_revision",
    )
    if revision != candidate.observed_precondition.revision:
        raise SchemaValidationError(
            "requested_against_revision",
            "must match the observed precondition revision",
        )
    created = _utc(candidate.created_at_utc, "created_at_utc")
    not_before = _utc(candidate.not_before_utc, "not_before_utc")
    expires = _utc(candidate.expires_at_utc, "expires_at_utc")
    if candidate.observed_precondition.observed_at_utc > created:
        raise SchemaValidationError(
            "observed_precondition.observed_at_utc",
            "must not follow candidate creation",
        )
    if not_before < created:
        raise SchemaValidationError("not_before_utc", "must not precede creation")
    if expires <= created or expires < not_before:
        raise SchemaValidationError(
            "expires_at_utc", "must follow creation and not-before time"
        )


def validate_safety_ownership(value: SafetyOwnership) -> None:
    """Validate one complete, explicit ownership graph."""
    _text(value.entry_id, "ownership.entry_id")
    if not isinstance(value.equipment_group_id, EquipmentGroupId):
        raise SchemaValidationError(
            "ownership.equipment_group_id", "must be an equipment group ID"
        )
    if not isinstance(value.zone_ids, tuple) or not value.zone_ids:
        raise SchemaValidationError("ownership.zone_ids", "must be a nonempty tuple")
    if any(not isinstance(item, ZoneId) for item in value.zone_ids):
        raise SchemaValidationError("ownership.zone_ids", "must contain zone IDs")
    if len(set(value.zone_ids)) != len(value.zone_ids):
        raise SchemaValidationError("ownership.zone_ids", "contains duplicates")
    if not isinstance(value.relationship, EquipmentRelationship):
        raise SchemaValidationError("ownership.relationship", "is unsupported")
    _entity_ids(value.owned_entity_ids, "ownership.owned_entity_ids", allow_empty=False)
    _entity_ids(
        value.command_authority_entity_ids,
        "ownership.command_authority_entity_ids",
        allow_empty=True,
    )
    if not set(value.command_authority_entity_ids) <= set(value.owned_entity_ids):
        raise SchemaValidationError(
            "ownership.command_authority_entity_ids",
            "must reference owned entities",
        )
    if not isinstance(value.authority_reviewed, bool):
        raise SchemaValidationError("ownership.authority_reviewed", "must be a boolean")


def validate_safety_capabilities(value: SafetyCapabilitySnapshot) -> None:
    """Validate one normalized target capability snapshot."""
    domain = _entity_id(value.entity_id, "capabilities.entity_id")
    if type(value.available) is not bool:
        raise SchemaValidationError("capabilities.available", "must be a boolean")
    if not isinstance(value.supported_command_kinds, frozenset):
        raise SchemaValidationError(
            "capabilities.supported_command_kinds",
            "must be an immutable set",
        )
    if any(not isinstance(item, CommandKind) for item in value.supported_command_kinds):
        raise SchemaValidationError(
            "capabilities.supported_command_kinds",
            "contains an unsupported command kind",
        )
    if domain == "climate" and any(
        item in {CommandKind.FAN_ON, CommandKind.FAN_OFF}
        for item in value.supported_command_kinds
    ):
        raise SchemaValidationError(
            "capabilities.supported_command_kinds",
            "contains a separate-fan command for a climate entity",
        )
    if domain == "fan" and any(
        item not in {CommandKind.FAN_ON, CommandKind.FAN_OFF}
        for item in value.supported_command_kinds
    ):
        raise SchemaValidationError(
            "capabilities.supported_command_kinds",
            "contains a climate command for a fan entity",
        )
    _bounded_modes(value.hvac_modes, "capabilities.hvac_modes")
    _bounded_modes(value.fan_modes, "capabilities.fan_modes")
    minimum = _optional_finite(
        value.advertised_min_target_c,
        "capabilities.advertised_min_target_c",
    )
    maximum = _optional_finite(
        value.advertised_max_target_c,
        "capabilities.advertised_max_target_c",
    )
    supports_temperature = bool(
        value.supported_command_kinds & {CommandKind.SET_TARGET, CommandKind.SET_RANGE}
    )
    if supports_temperature and (minimum is None or maximum is None):
        raise SchemaValidationError(
            "capabilities.advertised_min_target_c",
            "temperature support requires advertised limits",
        )
    if not supports_temperature and (minimum is not None or maximum is not None):
        raise SchemaValidationError(
            "capabilities.advertised_min_target_c",
            "advertised limits require temperature support",
        )
    if minimum is not None and maximum is not None and minimum >= maximum:
        raise SchemaValidationError(
            "capabilities.advertised_min_target_c",
            "must be below the advertised maximum",
        )
    _utc(value.observed_at_utc, "capabilities.observed_at_utc")


def validate_safety_authority(value: SafetyAuthorityEvidence) -> None:
    """Validate typed operating/control authority evidence."""
    if not isinstance(value.operating_mode, OperatingMode):
        raise SchemaValidationError("authority.operating_mode", "is unsupported")
    if not isinstance(value.control_state, ControlExecutionState):
        raise SchemaValidationError("authority.control_state", "is unsupported")
    for path, flag in (
        ("manual_intent_authorized", value.manual_intent_authorized),
        ("shadow_qualified", value.shadow_qualified),
        ("active_control_armed", value.active_control_armed),
    ):
        if type(flag) is not bool:
            raise SchemaValidationError(f"authority.{path}", "must be a boolean")
    if value.active_control_armed and (
        value.operating_mode is not OperatingMode.SCHEDULED_CONTROL
        or not value.shadow_qualified
    ):
        raise SchemaValidationError(
            "authority.active_control_armed",
            "requires qualified Scheduled Control",
        )
    if value.manual_intent_authorized and value.operating_mode not in {
        OperatingMode.MANUAL_CONTROL,
        OperatingMode.SCHEDULED_CONTROL,
    }:
        raise SchemaValidationError(
            "authority.manual_intent_authorized",
            "is allowed only for a manual-capable control mode",
        )


def validate_safety_timing(value: SafetyTimingEvidence) -> None:
    """Validate all timing evidence without reading a clock."""
    started = _utc(value.runtime_started_at_utc, "timing.runtime_started_at_utc")
    for path, timestamp in (
        ("last_command_at_utc", value.last_command_at_utc),
        ("last_mode_change_at_utc", value.last_mode_change_at_utc),
        ("last_terminal_failure_at_utc", value.last_terminal_failure_at_utc),
    ):
        if timestamp is not None and _utc(timestamp, f"timing.{path}") < started:
            raise SchemaValidationError(
                f"timing.{path}", "must not precede runtime start"
            )


def validate_safety_policy(
    limits: Phase2SafetyLimits,
    timing: Phase2CommandTiming,
) -> None:
    """Validate caller-supplied Phase 2 hard-limit and timing policy."""
    if not isinstance(limits, Phase2SafetyLimits):
        raise SchemaValidationError("limits", "must be Phase 2 safety limits")
    finite_limits = (
        limits.minimum_heating_target_c,
        limits.maximum_heating_target_c,
        limits.minimum_cooling_target_c,
        limits.maximum_cooling_target_c,
        limits.minimum_heat_cool_separation_c,
        limits.emergency_low_threshold_c,
        limits.emergency_low_target_c,
        limits.emergency_high_threshold_c,
        limits.emergency_high_target_c,
    )
    if any(
        isinstance(item, bool)
        or not isinstance(item, int | float)
        or not isfinite(item)
        for item in finite_limits
    ):
        raise SchemaValidationError("limits", "must contain finite numbers")
    if type(limits.emergency_protection_enabled) is not bool:
        raise SchemaValidationError(
            "limits.emergency_protection_enabled", "must be a boolean"
        )
    if limits.minimum_heating_target_c >= limits.maximum_heating_target_c:
        raise SchemaValidationError("limits", "heating minimum must be below maximum")
    if limits.minimum_cooling_target_c >= limits.maximum_cooling_target_c:
        raise SchemaValidationError("limits", "cooling minimum must be below maximum")
    if limits.minimum_heat_cool_separation_c <= 0:
        raise SchemaValidationError(
            "limits.minimum_heat_cool_separation_c", "must be positive"
        )
    if not (
        limits.emergency_low_threshold_c
        < limits.emergency_low_target_c
        < limits.emergency_high_target_c
        < limits.emergency_high_threshold_c
    ):
        raise SchemaValidationError("limits", "emergency targets are contradictory")
    if not isinstance(timing, Phase2CommandTiming):
        raise SchemaValidationError("timing", "must be Phase 2 command timing")
    integer_values = (
        timing.automatic_minimum_interval_seconds,
        timing.direct_override_minimum_interval_seconds,
        timing.manual_control_minimum_interval_seconds,
        timing.mode_reversal_cooldown_seconds,
        timing.acknowledgement_window_seconds,
        timing.retry_delay_seconds,
        timing.failure_cooldown_seconds,
        timing.repeated_failure_count,
        timing.repeated_failure_window_seconds,
        timing.startup_quiet_period_seconds,
    )
    if any(
        isinstance(item, bool) or not isinstance(item, int) or item <= 0
        for item in integer_values
    ):
        raise SchemaValidationError("timing", "must contain positive whole seconds")
    if (
        isinstance(timing.target_deadband_c, bool)
        or not isinstance(timing.target_deadband_c, int | float)
        or not isfinite(timing.target_deadband_c)
        or timing.target_deadband_c <= 0
    ):
        raise SchemaValidationError(
            "timing.target_deadband_c", "must be a positive finite number"
        )
    if timing.startup_quiet_period_seconds < 120:
        raise SchemaValidationError(
            "timing.startup_quiet_period_seconds", "must be at least 120 seconds"
        )


def _validate_requested_values(candidate: SafetyCommandCandidate) -> None:
    values = candidate.requested_values
    numeric = (values.target_c, values.heat_target_c, values.cool_target_c)
    if any(
        item is not None
        and (
            isinstance(item, bool)
            or not isinstance(item, int | float)
            or not isfinite(item)
        )
        for item in numeric
    ):
        raise SchemaValidationError(
            "requested_values", "contains a nonfinite temperature"
        )
    for path, value in (
        ("hvac_mode", values.hvac_mode),
        ("fan_mode", values.fan_mode),
        ("fan_state", values.fan_state),
    ):
        if value is not None:
            _text(value, f"requested_values.{path}", maximum=64)
    expected_non_null = {
        CommandControlledField.TARGET: ("target_c",),
        CommandControlledField.RANGE: ("heat_target_c", "cool_target_c"),
        CommandControlledField.HVAC_MODE: ("hvac_mode",),
        CommandControlledField.FAN_MODE: ("fan_mode",),
        CommandControlledField.FAN_STATE: ("fan_state",),
    }
    all_names = {
        "target_c",
        "heat_target_c",
        "cool_target_c",
        "hvac_mode",
        "fan_mode",
        "fan_state",
    }
    required = {
        name
        for field in candidate.requested_fields
        for name in expected_non_null[field]
    }
    present = {name for name in all_names if getattr(values, name) is not None}
    if present != required:
        raise SchemaValidationError(
            "requested_values", "must exactly match the controlled fields"
        )
    if candidate.command_kind is CommandKind.SET_TARGET:
        if not isinstance(candidate.target_direction, SafetyTargetDirection):
            raise SchemaValidationError(
                "target_direction", "is required for a single target"
            )
    elif candidate.target_direction is not None:
        raise SchemaValidationError(
            "target_direction", "must be null except for a single target"
        )
    if candidate.command_kind is CommandKind.SET_RANGE:
        heat = values.heat_target_c
        cool = values.cool_target_c
        if heat is None or cool is None or heat >= cool:
            raise SchemaValidationError(
                "requested_values", "range heat target must be below cool target"
            )
    if candidate.command_kind is CommandKind.FAN_ON and values.fan_state != "on":
        raise SchemaValidationError("requested_values.fan_state", "must be on")
    if candidate.command_kind is CommandKind.FAN_OFF and values.fan_state != "off":
        raise SchemaValidationError("requested_values.fan_state", "must be off")


def _validate_authority_cause(
    authority: CommandAuthority,
    cause: CommandCause,
) -> None:
    manual = {CommandCause.MANUAL_USER, CommandCause.UI_OVERRIDE}
    if authority is CommandAuthority.MANUAL and cause not in manual:
        raise SchemaValidationError("cause", "is invalid for manual authority")
    if authority is CommandAuthority.SCHEDULED and cause in manual:
        raise SchemaValidationError("cause", "requires manual authority")


def _require_precondition_fields(candidate: SafetyCommandCandidate) -> None:
    values = candidate.observed_precondition.values
    required = {
        CommandControlledField.TARGET: ("target_c",),
        CommandControlledField.RANGE: ("heat_target_c", "cool_target_c"),
        CommandControlledField.HVAC_MODE: ("hvac_mode",),
        CommandControlledField.FAN_MODE: ("fan_mode",),
        CommandControlledField.FAN_STATE: ("fan_state",),
    }
    missing = [
        name
        for field in candidate.requested_fields
        for name in required[field]
        if getattr(values, name) is None
    ]
    if missing:
        raise SchemaValidationError(
            "observed_precondition.values",
            "must contain every controlled field",
        )


def _positive_integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise SchemaValidationError(path, "must be a positive integer")
    return value


def _utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise SchemaValidationError(path, "must be timezone-aware")
    if value.utcoffset() != UTC.utcoffset(value):
        raise SchemaValidationError(path, "must use UTC")
    return value


def _optional_finite(value: object, path: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, int | float)
        or not isfinite(value)
    ):
        raise SchemaValidationError(path, "must be a finite number or null")
    return float(value)


def _text(value: object, path: str, *, maximum: int = 255) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise SchemaValidationError(path, "must be bounded nonempty text")
    return value


def _entity_id(value: object, path: str) -> str:
    text = _text(value, path)
    if text.count(".") != 1:
        raise SchemaValidationError(path, "must be an entity ID")
    domain, object_id = text.split(".", 1)
    if domain not in {"climate", "fan"} or not object_id:
        raise SchemaValidationError(path, "must be a climate or fan entity ID")
    return domain


def _entity_ids(values: object, path: str, *, allow_empty: bool) -> None:
    if not isinstance(values, tuple):
        raise SchemaValidationError(path, "must be a tuple")
    if not allow_empty and not values:
        raise SchemaValidationError(path, "must not be empty")
    for item in values:
        _entity_id(item, path)
    if len(set(values)) != len(values):
        raise SchemaValidationError(path, "contains duplicates")


def _bounded_modes(values: object, path: str) -> None:
    if not isinstance(values, tuple):
        raise SchemaValidationError(path, "must be a tuple")
    for item in values:
        _text(item, path, maximum=64)
    if len(set(values)) != len(values):
        raise SchemaValidationError(path, "contains duplicates")
