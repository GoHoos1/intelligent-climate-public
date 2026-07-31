"""Typed, restart-safe manual-override records for Phase 2 Task 10."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any

from .identifiers import EquipmentGroupId, OverrideId, ZoneId
from .schedule import LocalTime
from .schema import SchemaValidationError

MIN_OVERRIDE_DURATION_SECONDS = 15 * 60
MAX_OVERRIDE_DURATION_SECONDS = 7 * 24 * 60 * 60
MAX_OVERRIDE_TEXT_LENGTH = 255


class ControlledField(StrEnum):
    """Allowlisted thermostat fields that one override may own."""

    TARGET = "target"
    RANGE = "range"
    HVAC_MODE = "hvac_mode"
    PRESET = "preset"
    FAN_MODE = "fan_mode"
    HOLD = "hold"


class OverrideSource(StrEnum):
    """Privacy-bounded category describing where an override originated."""

    INTELLIGENT_CLIMATE_UI = "intelligent_climate_ui"
    PHYSICAL_OR_EXTERNAL = "physical_or_external"
    HOME_ASSISTANT_USER = "home_assistant_user"
    HOME_ASSISTANT_AUTOMATION = "home_assistant_automation"
    UNKNOWN = "unknown"


class OverrideExpirationKind(StrEnum):
    """Supported Phase 2 override-expiration policies."""

    NEXT_MATERIAL_SCHEDULE_TRANSITION = "next_material_schedule_transition"
    DURATION = "duration"
    NEXT_OCCUPANCY_TRANSITION = "next_occupancy_transition"
    SPECIFIED_LOCAL_TIME = "specified_local_time"
    MANUAL_CANCELLATION = "manual_cancellation"
    NEXT_DAY_SCHEDULE_START = "next_day_schedule_start"


class OverrideState(StrEnum):
    """Restart-safe lifecycle state for one override."""

    ACTIVE = "active"
    EXPIRING = "expiring"
    ENDED = "ended"


class OverrideEndReason(StrEnum):
    """Stable terminal reason with no user or entity identifiers."""

    EXPIRED = "expired"
    MANUALLY_CANCELLED = "manually_cancelled"
    REPLACED = "replaced"
    RECONCILED = "reconciled"
    SAFETY_INVALIDATED = "safety_invalidated"


class OverrideReasonCode(StrEnum):
    """Stable explanation code for override projections and transitions."""

    ACTIVE = "override_active"
    EXTENDED = "override_extended"
    MANUALLY_CANCELLED = "override_manually_cancelled"
    EXPIRATION_DUE = "override_expiration_due"
    ENDED = "override_ended"


@dataclass(frozen=True, slots=True)
class ControlledValues:
    """Normalized allowlisted values owned by an override or command."""

    target_c: float | None = None
    heat_target_c: float | None = None
    cool_target_c: float | None = None
    hvac_mode: str | None = None
    preset: str | None = None
    fan_mode: str | None = None
    hold: bool | None = None


@dataclass(frozen=True, slots=True)
class OverrideExpirationPolicy:
    """One tagged override-expiration policy."""

    kind: OverrideExpirationKind
    duration_seconds: int | None = None
    local_time: LocalTime | None = None

    def __post_init__(self) -> None:
        """Reject contradictory or incomplete policy parameters."""
        validate_expiration_policy(self)


@dataclass(frozen=True, slots=True)
class ManualOverride:
    """Complete typed manual override suitable for Runtime Store v2 records."""

    override_id: OverrideId
    entry_id: str
    equipment_group_id: EquipmentGroupId
    zone_id: ZoneId
    controlled_fields: frozenset[ControlledField]
    source: OverrideSource
    source_context_id: str | None
    requested_values: ControlledValues
    started_at_utc: datetime
    last_updated_at_utc: datetime
    expiration_policy: OverrideExpirationPolicy
    expires_at_utc: datetime | None
    anchor_transition_key: str | None
    state: OverrideState
    ended_at_utc: datetime | None = None
    end_reason: OverrideEndReason | None = None


@dataclass(frozen=True, slots=True)
class OverrideValidationContext:
    """Caller-supplied identity and controlled-field ownership."""

    entry_id: str
    equipment_group_id: EquipmentGroupId
    controlled_fields_by_zone: Mapping[ZoneId, frozenset[ControlledField]]

    def __post_init__(self) -> None:
        """Freeze the caller-owned mapping."""
        object.__setattr__(
            self,
            "controlled_fields_by_zone",
            MappingProxyType(dict(self.controlled_fields_by_zone)),
        )


@dataclass(frozen=True, slots=True)
class OverrideProjection:
    """Privacy-safe explanation that omits raw context and stable identities."""

    state: OverrideState
    source: OverrideSource
    controlled_fields: tuple[ControlledField, ...]
    started_at_utc: datetime
    expires_at_utc: datetime | None
    reason_code: OverrideReasonCode
    explanation: str


def validate_expiration_policy(policy: OverrideExpirationPolicy) -> None:
    """Validate the tagged expiration policy without reading a clock."""
    if not isinstance(policy.kind, OverrideExpirationKind):
        raise SchemaValidationError(
            "expiration_policy.kind",
            "must be a supported override expiration policy",
        )
    if policy.kind is OverrideExpirationKind.DURATION:
        duration = _integer(
            policy.duration_seconds,
            "expiration_policy.duration_seconds",
        )
        if not (
            MIN_OVERRIDE_DURATION_SECONDS <= duration <= MAX_OVERRIDE_DURATION_SECONDS
        ):
            raise SchemaValidationError(
                "expiration_policy.duration_seconds",
                "must be between 900 and 604800 seconds",
            )
        if policy.local_time is not None:
            raise SchemaValidationError(
                "expiration_policy.local_time",
                "is not valid for a duration policy",
            )
        return
    if policy.kind is OverrideExpirationKind.SPECIFIED_LOCAL_TIME:
        if not isinstance(policy.local_time, LocalTime):
            raise SchemaValidationError(
                "expiration_policy.local_time",
                "is required for a specified-local-time policy",
            )
        if policy.duration_seconds is not None:
            raise SchemaValidationError(
                "expiration_policy.duration_seconds",
                "is not valid for a specified-local-time policy",
            )
        return
    if policy.duration_seconds is not None or policy.local_time is not None:
        raise SchemaValidationError(
            "expiration_policy",
            "contains parameters not authorized for this policy",
        )


def validate_controlled_values(
    fields: frozenset[ControlledField],
    values: ControlledValues,
    *,
    path: str = "requested_values",
) -> None:
    """Reject missing, contradictory, nonfinite, or unsupported values."""
    if not isinstance(fields, frozenset) or not fields:
        raise SchemaValidationError(
            "controlled_fields",
            "must be a nonempty immutable set",
        )
    if any(not isinstance(item, ControlledField) for item in fields):
        raise SchemaValidationError(
            "controlled_fields",
            "contains an unsupported controlled field",
        )
    if ControlledField.TARGET in fields and ControlledField.RANGE in fields:
        raise SchemaValidationError(
            "controlled_fields",
            "target and range cannot be controlled together",
        )

    _validate_optional_finite(values.target_c, f"{path}.target_c")
    _validate_optional_finite(values.heat_target_c, f"{path}.heat_target_c")
    _validate_optional_finite(values.cool_target_c, f"{path}.cool_target_c")
    if ControlledField.TARGET in fields:
        if values.target_c is None:
            raise SchemaValidationError(f"{path}.target_c", "is required")
    elif values.target_c is not None:
        raise SchemaValidationError(
            f"{path}.target_c",
            "is present without target ownership",
        )

    if ControlledField.RANGE in fields:
        if values.heat_target_c is None or values.cool_target_c is None:
            raise SchemaValidationError(
                path,
                "heat_target_c and cool_target_c are required for range ownership",
            )
        if values.heat_target_c >= values.cool_target_c:
            raise SchemaValidationError(
                path,
                "heat_target_c must be less than cool_target_c",
            )
    elif values.heat_target_c is not None or values.cool_target_c is not None:
        raise SchemaValidationError(
            path,
            "range endpoints are present without range ownership",
        )

    string_fields = (
        (ControlledField.HVAC_MODE, values.hvac_mode, "hvac_mode"),
        (ControlledField.PRESET, values.preset, "preset"),
        (ControlledField.FAN_MODE, values.fan_mode, "fan_mode"),
    )
    for field, value, name in string_fields:
        if field in fields:
            _plain_string(value, f"{path}.{name}")
        elif value is not None:
            raise SchemaValidationError(
                f"{path}.{name}",
                f"is present without {field.value} ownership",
            )
    if ControlledField.HOLD in fields:
        if not isinstance(values.hold, bool):
            raise SchemaValidationError(f"{path}.hold", "must be a boolean")
    elif values.hold is not None:
        raise SchemaValidationError(
            f"{path}.hold",
            "is present without hold ownership",
        )


def validate_manual_override(
    value: ManualOverride,
    *,
    validation_context: OverrideValidationContext,
) -> None:
    """Validate identity, ownership, value, timestamp, and lifecycle contracts."""
    _plain_string(value.entry_id, "entry_id")
    _plain_string(validation_context.entry_id, "validation_context.entry_id")
    if value.entry_id != validation_context.entry_id:
        raise SchemaValidationError("entry_id", "does not match the loaded entry")
    if value.equipment_group_id != validation_context.equipment_group_id:
        raise SchemaValidationError(
            "equipment_group_id",
            "does not match the loaded equipment group",
        )
    owned_fields = validation_context.controlled_fields_by_zone.get(value.zone_id)
    if owned_fields is None:
        raise SchemaValidationError("zone_id", "is not owned by the loaded entry")
    if not value.controlled_fields <= owned_fields:
        raise SchemaValidationError(
            "controlled_fields",
            "contains a field not owned by this zone",
        )
    if not isinstance(value.source, OverrideSource):
        raise SchemaValidationError("source", "must be a supported source category")
    if value.source_context_id is not None:
        _plain_string(value.source_context_id, "source_context_id")
    validate_controlled_values(value.controlled_fields, value.requested_values)
    _utc_datetime(value.started_at_utc, "started_at_utc")
    _utc_datetime(value.last_updated_at_utc, "last_updated_at_utc")
    if value.last_updated_at_utc < value.started_at_utc:
        raise SchemaValidationError(
            "last_updated_at_utc",
            "must not precede started_at_utc",
        )
    validate_expiration_policy(value.expiration_policy)
    if value.expires_at_utc is not None:
        _utc_datetime(value.expires_at_utc, "expires_at_utc")
        if value.expires_at_utc < value.last_updated_at_utc:
            raise SchemaValidationError(
                "expires_at_utc",
                "must not precede last_updated_at_utc",
            )
    if (
        value.expiration_policy.kind is OverrideExpirationKind.DURATION
        and value.expires_at_utc is None
    ):
        raise SchemaValidationError(
            "expires_at_utc",
            "is required for a duration policy",
        )
    if value.expiration_policy.kind is OverrideExpirationKind.MANUAL_CANCELLATION and (
        value.expires_at_utc is not None or value.anchor_transition_key is not None
    ):
        raise SchemaValidationError(
            "expires_at_utc",
            "manual-cancellation policy cannot have an automatic deadline",
        )
    if value.anchor_transition_key is not None:
        _plain_string(value.anchor_transition_key, "anchor_transition_key")
    if not isinstance(value.state, OverrideState):
        raise SchemaValidationError("state", "must be a supported override state")
    if value.state is OverrideState.ENDED:
        if value.ended_at_utc is None or value.end_reason is None:
            raise SchemaValidationError(
                "state",
                "ended overrides require ended_at_utc and end_reason",
            )
        _utc_datetime(value.ended_at_utc, "ended_at_utc")
        if value.ended_at_utc < value.last_updated_at_utc:
            raise SchemaValidationError(
                "ended_at_utc",
                "must not precede last_updated_at_utc",
            )
    elif value.ended_at_utc is not None or value.end_reason is not None:
        raise SchemaValidationError(
            "state",
            "non-ended overrides cannot contain terminal fields",
        )


def encode_manual_override(
    value: ManualOverride,
    *,
    validation_context: OverrideValidationContext,
) -> dict[str, object]:
    """Validate and deterministically encode one runtime-v2 override record."""
    validate_manual_override(value, validation_context=validation_context)
    return {
        "override_id": str(value.override_id),
        "entry_id": value.entry_id,
        "equipment_group_id": str(value.equipment_group_id),
        "zone_id": str(value.zone_id),
        "controlled_fields": [
            field.value for field in sorted(value.controlled_fields, key=str)
        ],
        "source": value.source.value,
        "source_context_id": value.source_context_id,
        "requested_values": _encode_controlled_values(value.requested_values),
        "started_at_utc": value.started_at_utc.isoformat(),
        "last_updated_at_utc": value.last_updated_at_utc.isoformat(),
        "expiration_policy": _encode_expiration_policy(value.expiration_policy),
        "expires_at_utc": (
            value.expires_at_utc.isoformat()
            if value.expires_at_utc is not None
            else None
        ),
        "anchor_transition_key": value.anchor_transition_key,
        "state": value.state.value,
        "ended_at_utc": (
            value.ended_at_utc.isoformat() if value.ended_at_utc is not None else None
        ),
        "end_reason": value.end_reason.value if value.end_reason is not None else None,
    }


def decode_manual_override(
    raw: object,
    *,
    validation_context: OverrideValidationContext,
) -> ManualOverride:
    """Strictly decode one restart-safe runtime-v2 override record."""
    root = _object(raw, "")
    expected = {
        "override_id",
        "entry_id",
        "equipment_group_id",
        "zone_id",
        "controlled_fields",
        "source",
        "source_context_id",
        "requested_values",
        "started_at_utc",
        "last_updated_at_utc",
        "expiration_policy",
        "expires_at_utc",
        "anchor_transition_key",
        "state",
        "ended_at_utc",
        "end_reason",
    }
    _reject_unknown(root, expected, "")
    fields = frozenset(
        _enum(ControlledField, item, f"controlled_fields[{index}]")
        for index, item in enumerate(
            _list(root.get("controlled_fields"), "controlled_fields")
        )
    )
    value = ManualOverride(
        override_id=_override_id(root.get("override_id"), "override_id"),
        entry_id=_plain_string(root.get("entry_id"), "entry_id"),
        equipment_group_id=_equipment_group_id(
            root.get("equipment_group_id"),
            "equipment_group_id",
        ),
        zone_id=_zone_id(root.get("zone_id"), "zone_id"),
        controlled_fields=fields,
        source=_enum(OverrideSource, root.get("source"), "source"),
        source_context_id=_optional_string(
            root.get("source_context_id"),
            "source_context_id",
        ),
        requested_values=_decode_controlled_values(
            root.get("requested_values"),
            "requested_values",
        ),
        started_at_utc=_utc_datetime(root.get("started_at_utc"), "started_at_utc"),
        last_updated_at_utc=_utc_datetime(
            root.get("last_updated_at_utc"),
            "last_updated_at_utc",
        ),
        expiration_policy=_decode_expiration_policy(
            root.get("expiration_policy"),
        ),
        expires_at_utc=_optional_utc_datetime(
            root.get("expires_at_utc"),
            "expires_at_utc",
        ),
        anchor_transition_key=_optional_string(
            root.get("anchor_transition_key"),
            "anchor_transition_key",
        ),
        state=_enum(OverrideState, root.get("state"), "state"),
        ended_at_utc=_optional_utc_datetime(
            root.get("ended_at_utc"),
            "ended_at_utc",
        ),
        end_reason=_optional_enum(
            OverrideEndReason,
            root.get("end_reason"),
            "end_reason",
        ),
    )
    validate_manual_override(value, validation_context=validation_context)
    return value


def project_manual_override(value: ManualOverride) -> OverrideProjection:
    """Return a fixed, privacy-safe explanation without raw identifiers."""
    if value.state is OverrideState.ENDED:
        reason = (
            OverrideReasonCode.MANUALLY_CANCELLED
            if value.end_reason is OverrideEndReason.MANUALLY_CANCELLED
            else OverrideReasonCode.ENDED
        )
    elif value.state is OverrideState.EXPIRING:
        reason = OverrideReasonCode.EXPIRATION_DUE
    else:
        reason = OverrideReasonCode.ACTIVE
    explanations = {
        OverrideReasonCode.ACTIVE: "A manual override is active.",
        OverrideReasonCode.EXTENDED: "The manual override was extended.",
        OverrideReasonCode.MANUALLY_CANCELLED: "The manual override was cancelled.",
        OverrideReasonCode.EXPIRATION_DUE: "The manual override is due to expire.",
        OverrideReasonCode.ENDED: "The manual override has ended.",
    }
    return OverrideProjection(
        state=value.state,
        source=value.source,
        controlled_fields=tuple(sorted(value.controlled_fields, key=str)),
        started_at_utc=value.started_at_utc,
        expires_at_utc=value.expires_at_utc,
        reason_code=reason,
        explanation=explanations[reason],
    )


def _encode_controlled_values(value: ControlledValues) -> dict[str, object]:
    return {
        "target_c": value.target_c,
        "heat_target_c": value.heat_target_c,
        "cool_target_c": value.cool_target_c,
        "hvac_mode": value.hvac_mode,
        "preset": value.preset,
        "fan_mode": value.fan_mode,
        "hold": value.hold,
    }


def _decode_controlled_values(raw: object, path: str) -> ControlledValues:
    root = _object(raw, path)
    expected = set(_encode_controlled_values(ControlledValues()))
    _reject_unknown(root, expected, path)
    return ControlledValues(
        target_c=_optional_finite(root.get("target_c"), f"{path}.target_c"),
        heat_target_c=_optional_finite(
            root.get("heat_target_c"),
            f"{path}.heat_target_c",
        ),
        cool_target_c=_optional_finite(
            root.get("cool_target_c"),
            f"{path}.cool_target_c",
        ),
        hvac_mode=_optional_string(root.get("hvac_mode"), f"{path}.hvac_mode"),
        preset=_optional_string(root.get("preset"), f"{path}.preset"),
        fan_mode=_optional_string(root.get("fan_mode"), f"{path}.fan_mode"),
        hold=_optional_bool(root.get("hold"), f"{path}.hold"),
    )


def _encode_expiration_policy(value: OverrideExpirationPolicy) -> dict[str, object]:
    return {
        "kind": value.kind.value,
        "duration_seconds": value.duration_seconds,
        "local_time": str(value.local_time) if value.local_time is not None else None,
    }


def _decode_expiration_policy(raw: object) -> OverrideExpirationPolicy:
    path = "expiration_policy"
    root = _object(raw, path)
    _reject_unknown(root, {"kind", "duration_seconds", "local_time"}, path)
    local_time_value = root.get("local_time")
    try:
        local_time = (
            LocalTime.parse(local_time_value)
            if isinstance(local_time_value, str)
            else None
        )
    except ValueError as err:
        raise SchemaValidationError(f"{path}.local_time", str(err)) from err
    if local_time_value is not None and not isinstance(local_time_value, str):
        raise SchemaValidationError(f"{path}.local_time", "must be a string or null")
    return OverrideExpirationPolicy(
        kind=_enum(
            OverrideExpirationKind,
            root.get("kind"),
            f"{path}.kind",
        ),
        duration_seconds=_optional_integer(
            root.get("duration_seconds"),
            f"{path}.duration_seconds",
        ),
        local_time=local_time,
    )


def _object(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaValidationError(path, "must be an object")
    if any(not isinstance(key, str) for key in value):
        raise SchemaValidationError(path, "object keys must be strings")
    return dict(value)


def _list(value: object, path: str) -> tuple[object, ...]:
    if not isinstance(value, list | tuple):
        raise SchemaValidationError(path, "must be a list")
    return tuple(value)


def _reject_unknown(
    root: Mapping[str, object],
    expected: set[str],
    path: str,
) -> None:
    unknown = set(root) - expected
    if unknown:
        name = min(unknown)
        raise SchemaValidationError(f"{path}.{name}".strip("."), "unknown field")
    missing = expected - set(root)
    if missing:
        name = min(missing)
        raise SchemaValidationError(f"{path}.{name}".strip("."), "missing field")


def _enum[T: StrEnum](enum_type: type[T], value: object, path: str) -> T:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    try:
        return enum_type(value)
    except ValueError as err:
        raise SchemaValidationError(path, "contains an unsupported value") from err


def _optional_enum[T: StrEnum](
    enum_type: type[T],
    value: object,
    path: str,
) -> T | None:
    return None if value is None else _enum(enum_type, value, path)


def _plain_string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_OVERRIDE_TEXT_LENGTH:
        raise SchemaValidationError(
            path,
            "must be a nonempty string of at most "
            f"{MAX_OVERRIDE_TEXT_LENGTH} characters",
        )
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise SchemaValidationError(path, "must not contain control characters")
    return value


def _optional_string(value: object, path: str) -> str | None:
    return None if value is None else _plain_string(value, path)


def _integer(value: object, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError(path, "must be an integer")
    return value


def _optional_integer(value: object, path: str) -> int | None:
    return None if value is None else _integer(value, path)


def _validate_optional_finite(value: float | None, path: str) -> None:
    if value is not None and (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise SchemaValidationError(path, "must be a finite number or null")


def _optional_finite(value: object, path: str) -> float | None:
    if value is None:
        return None
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise SchemaValidationError(path, "must be a finite number or null")
    return float(value)


def _optional_bool(value: object, path: str) -> bool | None:
    if value is not None and not isinstance(value, bool):
        raise SchemaValidationError(path, "must be a boolean or null")
    return value


def _utc_datetime(value: object, path: str) -> datetime:
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError as err:
            raise SchemaValidationError(path, "must be an ISO datetime") from err
    elif isinstance(value, datetime):
        parsed = value
    else:
        raise SchemaValidationError(path, "must be a datetime")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise SchemaValidationError(path, "must be timezone-aware")
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise SchemaValidationError(path, "must be expressed in UTC")
    return parsed


def _optional_utc_datetime(value: object, path: str) -> datetime | None:
    return None if value is None else _utc_datetime(value, path)


def _override_id(value: object, path: str) -> OverrideId:
    try:
        return OverrideId.parse(_plain_string(value, path))
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err


def _equipment_group_id(value: object, path: str) -> EquipmentGroupId:
    try:
        return EquipmentGroupId.parse(_plain_string(value, path))
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err


def _zone_id(value: object, path: str) -> ZoneId:
    try:
        return ZoneId.parse(_plain_string(value, path))
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err
