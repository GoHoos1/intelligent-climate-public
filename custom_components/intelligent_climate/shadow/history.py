"""Bounded, deterministic Shadow would-command history."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import isfinite
from typing import Any

from ..models.command import (
    CommandAuthority,
    CommandCause,
    CommandControlledField,
    CommandKind,
    NormalizedCommandValues,
)
from ..models.identifiers import CommandId, DecisionId, SafetyEvaluationId
from ..models.plan import (
    CommandPlan,
    validate_command_plan,
    validate_plan_safety_decision,
)
from ..models.safety import SafetyDisposition, SafetyGateDecision, SafetyReasonCode
from ..models.schema import SchemaValidationError
from ..models.shadow import (
    MAX_SHADOW_HISTORY_AGE_DAYS,
    MAX_SHADOW_HISTORY_RECORDS,
    ShadowHistoryOutcome,
    ShadowHistoryRecord,
    ShadowWouldCommand,
)

_COMMAND_FIELDS: dict[CommandKind, frozenset[frozenset[CommandControlledField]]] = {
    CommandKind.SET_TARGET: frozenset(
        {
            frozenset({CommandControlledField.TARGET}),
            frozenset(
                {CommandControlledField.TARGET, CommandControlledField.HVAC_MODE}
            ),
        }
    ),
    CommandKind.SET_RANGE: frozenset(
        {
            frozenset({CommandControlledField.RANGE}),
            frozenset({CommandControlledField.RANGE, CommandControlledField.HVAC_MODE}),
        }
    ),
    CommandKind.SET_HVAC_MODE: frozenset(
        {frozenset({CommandControlledField.HVAC_MODE})}
    ),
    CommandKind.SET_FAN_MODE: frozenset({frozenset({CommandControlledField.FAN_MODE})}),
    CommandKind.FAN_ON: frozenset({frozenset({CommandControlledField.FAN_STATE})}),
    CommandKind.FAN_OFF: frozenset({frozenset({CommandControlledField.FAN_STATE})}),
}


def shadow_history_record(
    *,
    plan: CommandPlan | None,
    safety_decision: SafetyGateDecision,
    evaluated_at_utc: datetime,
) -> ShadowHistoryRecord:
    """Project one decision without entity, user, context, or exception data."""
    evaluated_at = _utc(evaluated_at_utc, "evaluated_at_utc")
    validate_plan_safety_decision(safety_decision)
    would_command: ShadowWouldCommand | None = None
    if plan is not None:
        validate_command_plan(plan)
        if plan.safety_evaluation_id != safety_decision.safety_evaluation_id:
            raise SchemaValidationError(
                "safety_evaluation_id", "plan and safety result must match"
            )
        if evaluated_at < plan.created_at_utc:
            raise SchemaValidationError(
                "evaluated_at_utc", "must not precede plan creation"
            )
        would_command = ShadowWouldCommand(
            command_id=plan.command_id,
            decision_id=plan.decision_id,
            command_kind=plan.command_kind,
            desired_fields=tuple(
                sorted(plan.desired_fields, key=lambda item: item.value)
            ),
            desired=plan.desired,
            authority=plan.authority,
            cause=plan.cause,
            dedupe_fingerprint=plan.dedupe_fingerprint,
        )
    outcome = (
        ShadowHistoryOutcome.WOULD_COMMAND
        if would_command is not None
        else (
            ShadowHistoryOutcome.BLOCKED
            if safety_decision.disposition is SafetyDisposition.BLOCKED
            else ShadowHistoryOutcome.SUPPRESSED
        )
    )
    record = ShadowHistoryRecord(
        safety_evaluation_id=safety_decision.safety_evaluation_id,
        evaluated_at_utc=evaluated_at,
        outcome=outcome,
        safety_disposition=safety_decision.disposition,
        reason_code=safety_decision.reason_code,
        hard_checks_passed=safety_decision.hard_checks_passed,
        would_command=would_command,
    )
    validate_shadow_history_record(record)
    return record


def append_shadow_history(
    records: tuple[ShadowHistoryRecord, ...],
    record: ShadowHistoryRecord,
    *,
    now_utc: datetime,
) -> tuple[ShadowHistoryRecord, ...]:
    """Append, age-prune, count-bound, dedupe, and canonically order history."""
    now = _utc(now_utc, "now_utc")
    validate_shadow_history(records, enforce_bound=True)
    validate_shadow_history_record(record)
    if record.evaluated_at_utc > now:
        raise SchemaValidationError("record", "must not follow the caller clock")
    if any(
        item.safety_evaluation_id == record.safety_evaluation_id for item in records
    ):
        raise SchemaValidationError("record", "duplicates a safety evaluation")
    cutoff = now - timedelta(days=MAX_SHADOW_HISTORY_AGE_DAYS)
    retained = tuple(item for item in records if item.evaluated_at_utc >= cutoff)
    result = (*retained, record)[-MAX_SHADOW_HISTORY_RECORDS:]
    validate_shadow_history(result, enforce_bound=True)
    return result


def encode_shadow_history(
    records: tuple[ShadowHistoryRecord, ...],
) -> list[dict[str, Any]]:
    """Encode bounded history for an authorized Runtime Store v2 record slot."""
    validate_shadow_history(records, enforce_bound=True)
    return [_encode_record(record) for record in records]


def decode_shadow_history(value: object) -> tuple[ShadowHistoryRecord, ...]:
    """Strictly decode bounded Shadow history without arbitrary fields."""
    if not isinstance(value, (list, tuple)):
        raise SchemaValidationError("shadow_history", "must be an array")
    if len(value) > MAX_SHADOW_HISTORY_RECORDS:
        raise SchemaValidationError("shadow_history", "exceeds the 100-record bound")
    records = tuple(_decode_record(item) for item in value)
    validate_shadow_history(records, enforce_bound=True)
    return records


def validate_shadow_history(
    records: tuple[ShadowHistoryRecord, ...],
    *,
    enforce_bound: bool,
) -> None:
    """Validate immutable, unique, chronological history."""
    if not isinstance(records, tuple):
        raise SchemaValidationError("shadow_history", "must be immutable")
    if enforce_bound and len(records) > MAX_SHADOW_HISTORY_RECORDS:
        raise SchemaValidationError("shadow_history", "exceeds the 100-record bound")
    for record in records:
        validate_shadow_history_record(record)
    if len({record.safety_evaluation_id for record in records}) != len(records):
        raise SchemaValidationError("shadow_history", "contains duplicate evaluations")
    if records != tuple(
        sorted(
            records,
            key=lambda item: (item.evaluated_at_utc, str(item.safety_evaluation_id)),
        )
    ):
        raise SchemaValidationError("shadow_history", "must be chronological")


def validate_shadow_history_record(record: ShadowHistoryRecord) -> None:
    """Reject contradictory projection records."""
    if not isinstance(record, ShadowHistoryRecord):
        raise SchemaValidationError("shadow_history", "contains an invalid record")
    if not isinstance(record.safety_evaluation_id, SafetyEvaluationId):
        raise SchemaValidationError("safety_evaluation_id", "is invalid")
    _utc(record.evaluated_at_utc, "evaluated_at_utc")
    if not isinstance(record.outcome, ShadowHistoryOutcome):
        raise SchemaValidationError("outcome", "is unsupported")
    if not isinstance(record.safety_disposition, SafetyDisposition):
        raise SchemaValidationError("safety_disposition", "is unsupported")
    if not isinstance(record.reason_code, SafetyReasonCode):
        raise SchemaValidationError("reason_code", "is unsupported")
    if type(record.hard_checks_passed) is not bool:
        raise SchemaValidationError("hard_checks_passed", "must be a boolean")
    if record.outcome is ShadowHistoryOutcome.WOULD_COMMAND:
        if (
            record.would_command is None
            or not record.hard_checks_passed
            or record.safety_disposition is not SafetyDisposition.SUPPRESSED
            or record.reason_code is not SafetyReasonCode.SHADOW_ONLY
        ):
            raise SchemaValidationError("would_command", "requires passed hard checks")
        _validate_would_command(record.would_command)
    else:
        if record.would_command is not None or record.hard_checks_passed:
            raise SchemaValidationError(
                "would_command", "is allowed only for would-command"
            )
        expected = (
            SafetyDisposition.BLOCKED
            if record.outcome is ShadowHistoryOutcome.BLOCKED
            else SafetyDisposition.SUPPRESSED
        )
        if record.safety_disposition is not expected:
            raise SchemaValidationError("outcome", "contradicts safety disposition")


def _validate_would_command(value: ShadowWouldCommand) -> None:
    if not isinstance(value.command_id, CommandId) or not isinstance(
        value.decision_id, DecisionId
    ):
        raise SchemaValidationError("would_command", "contains invalid identities")
    if not isinstance(value.command_kind, CommandKind):
        raise SchemaValidationError("would_command.command_kind", "is unsupported")
    if (
        not isinstance(value.desired_fields, tuple)
        or not value.desired_fields
        or any(
            not isinstance(item, CommandControlledField)
            for item in value.desired_fields
        )
        or len(set(value.desired_fields)) != len(value.desired_fields)
    ):
        raise SchemaValidationError("would_command.desired_fields", "is invalid")
    if value.desired_fields != tuple(
        sorted(value.desired_fields, key=lambda item: item.value)
    ):
        raise SchemaValidationError(
            "would_command.desired_fields", "must be canonically ordered"
        )
    fields = frozenset(value.desired_fields)
    if fields not in _COMMAND_FIELDS[value.command_kind]:
        raise SchemaValidationError(
            "would_command.desired_fields", "does not match command kind"
        )
    if not isinstance(value.desired, NormalizedCommandValues):
        raise SchemaValidationError("would_command.desired", "is invalid")
    numeric = (
        value.desired.target_c,
        value.desired.heat_target_c,
        value.desired.cool_target_c,
    )
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
            "would_command.desired", "contains a nonfinite temperature"
        )
    heat = value.desired.heat_target_c
    cool = value.desired.cool_target_c
    if (heat is None) is not (cool is None) or (
        heat is not None and cool is not None and heat >= cool
    ):
        raise SchemaValidationError(
            "would_command.desired", "contains an invalid target range"
        )
    for field_name, text_value in (
        ("hvac_mode", value.desired.hvac_mode),
        ("fan_mode", value.desired.fan_mode),
        ("fan_state", value.desired.fan_state),
    ):
        if text_value is not None and (
            not isinstance(text_value, str) or not text_value or len(text_value) > 64
        ):
            raise SchemaValidationError(
                f"would_command.desired.{field_name}", "must be bounded text"
            )
    if value.desired.fan_state not in {None, "on", "off"}:
        raise SchemaValidationError(
            "would_command.desired.fan_state", "must be on or off"
        )
    desired_presence = {
        CommandControlledField.TARGET: value.desired.target_c is not None,
        CommandControlledField.RANGE: (
            value.desired.heat_target_c is not None
            and value.desired.cool_target_c is not None
        ),
        CommandControlledField.HVAC_MODE: value.desired.hvac_mode is not None,
        CommandControlledField.FAN_MODE: value.desired.fan_mode is not None,
        CommandControlledField.FAN_STATE: value.desired.fan_state is not None,
    }
    if {field for field, present in desired_presence.items() if present} != fields:
        raise SchemaValidationError(
            "would_command.desired", "does not match controlled fields"
        )
    if not isinstance(value.authority, CommandAuthority) or not isinstance(
        value.cause, CommandCause
    ):
        raise SchemaValidationError("would_command.authority", "is invalid")
    manual_causes = {CommandCause.MANUAL_USER, CommandCause.UI_OVERRIDE}
    if (value.authority is CommandAuthority.MANUAL) != (value.cause in manual_causes):
        raise SchemaValidationError(
            "would_command.cause", "contradicts command authority"
        )
    if (
        not isinstance(value.dedupe_fingerprint, str)
        or len(value.dedupe_fingerprint) != 64
        or any(
            character not in "0123456789abcdef"
            for character in value.dedupe_fingerprint
        )
    ):
        raise SchemaValidationError("would_command.dedupe_fingerprint", "is invalid")


def _encode_record(record: ShadowHistoryRecord) -> dict[str, Any]:
    would = record.would_command
    return {
        "safety_evaluation_id": str(record.safety_evaluation_id),
        "evaluated_at_utc": record.evaluated_at_utc.isoformat().replace("+00:00", "Z"),
        "outcome": record.outcome.value,
        "safety_disposition": record.safety_disposition.value,
        "reason_code": record.reason_code.value,
        "hard_checks_passed": record.hard_checks_passed,
        "would_command": (
            None
            if would is None
            else {
                "command_id": str(would.command_id),
                "decision_id": str(would.decision_id),
                "command_kind": would.command_kind.value,
                "desired_fields": [field.value for field in would.desired_fields],
                "desired": _encode_values(would.desired),
                "authority": would.authority.value,
                "cause": would.cause.value,
                "dedupe_fingerprint": would.dedupe_fingerprint,
            }
        ),
    }


def _decode_record(value: object) -> ShadowHistoryRecord:
    data = _mapping(value, "shadow_history")
    _exact_keys(
        data,
        {
            "safety_evaluation_id",
            "evaluated_at_utc",
            "outcome",
            "safety_disposition",
            "reason_code",
            "hard_checks_passed",
            "would_command",
        },
        "shadow_history",
    )
    hard = data["hard_checks_passed"]
    if type(hard) is not bool:
        raise SchemaValidationError("hard_checks_passed", "must be a boolean")
    raw_would = data["would_command"]
    try:
        record = ShadowHistoryRecord(
            safety_evaluation_id=SafetyEvaluationId.parse(
                _text(data["safety_evaluation_id"], "safety_evaluation_id")
            ),
            evaluated_at_utc=_datetime(data["evaluated_at_utc"], "evaluated_at_utc"),
            outcome=_enum(ShadowHistoryOutcome, data["outcome"], "outcome"),
            safety_disposition=_enum(
                SafetyDisposition,
                data["safety_disposition"],
                "safety_disposition",
            ),
            reason_code=_enum(SafetyReasonCode, data["reason_code"], "reason_code"),
            hard_checks_passed=hard,
            would_command=None if raw_would is None else _decode_would(raw_would),
        )
    except ValueError as err:
        raise SchemaValidationError(
            "shadow_history", "contains invalid identity"
        ) from err
    validate_shadow_history_record(record)
    return record


def _decode_would(value: object) -> ShadowWouldCommand:
    data = _mapping(value, "would_command")
    _exact_keys(
        data,
        {
            "command_id",
            "decision_id",
            "command_kind",
            "desired_fields",
            "desired",
            "authority",
            "cause",
            "dedupe_fingerprint",
        },
        "would_command",
    )
    raw_fields = data["desired_fields"]
    if not isinstance(raw_fields, (list, tuple)) or not raw_fields:
        raise SchemaValidationError("desired_fields", "must be a nonempty array")
    fields = tuple(
        _enum(CommandControlledField, item, "desired_fields") for item in raw_fields
    )
    try:
        return ShadowWouldCommand(
            command_id=CommandId.parse(_text(data["command_id"], "command_id")),
            decision_id=DecisionId.parse(_text(data["decision_id"], "decision_id")),
            command_kind=_enum(CommandKind, data["command_kind"], "command_kind"),
            desired_fields=fields,
            desired=_decode_values(data["desired"]),
            authority=_enum(CommandAuthority, data["authority"], "authority"),
            cause=_enum(CommandCause, data["cause"], "cause"),
            dedupe_fingerprint=_text(data["dedupe_fingerprint"], "dedupe_fingerprint"),
        )
    except ValueError as err:
        raise SchemaValidationError(
            "would_command", "contains invalid identity"
        ) from err


def _encode_values(value: NormalizedCommandValues) -> dict[str, object]:
    return {
        "target_c": value.target_c,
        "heat_target_c": value.heat_target_c,
        "cool_target_c": value.cool_target_c,
        "hvac_mode": value.hvac_mode,
        "fan_mode": value.fan_mode,
        "fan_state": value.fan_state,
    }


def _decode_values(value: object) -> NormalizedCommandValues:
    data = _mapping(value, "desired")
    keys = {
        "target_c",
        "heat_target_c",
        "cool_target_c",
        "hvac_mode",
        "fan_mode",
        "fan_state",
    }
    _exact_keys(data, keys, "desired")
    return NormalizedCommandValues(
        target_c=_optional_number(data["target_c"], "target_c"),
        heat_target_c=_optional_number(data["heat_target_c"], "heat_target_c"),
        cool_target_c=_optional_number(data["cool_target_c"], "cool_target_c"),
        hvac_mode=_optional_text(data["hvac_mode"], "hvac_mode"),
        fan_mode=_optional_text(data["fan_mode"], "fan_mode"),
        fan_state=_optional_text(data["fan_state"], "fan_state"),
    )


def _mapping(value: object, path: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(not isinstance(key, str) for key in value):
        raise SchemaValidationError(path, "must be an object")
    return value


def _exact_keys(data: Mapping[str, object], expected: set[str], path: str) -> None:
    if set(data) != expected:
        raise SchemaValidationError(path, "contains missing or unknown fields")


def _enum[T: StrEnum](kind: type[T], value: object, path: str) -> T:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    try:
        return kind(value)
    except ValueError as err:
        raise SchemaValidationError(path, "is unsupported") from err


def _text(value: object, path: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 255:
        raise SchemaValidationError(path, "must be bounded nonempty text")
    return value


def _optional_text(value: object, path: str) -> str | None:
    return None if value is None else _text(value, path)


def _optional_number(value: object, path: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise SchemaValidationError(path, "must be numeric")
    result = float(value)
    if result != result or result in {float("inf"), float("-inf")}:
        raise SchemaValidationError(path, "must be finite")
    return result


def _datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid ISO-8601 value") from err
    return _utc(parsed, path)


def _utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise SchemaValidationError(path, "must be timezone-aware")
    if value.utcoffset() != UTC.utcoffset(value):
        raise SchemaValidationError(path, "must use UTC")
    return value
