"""Typed, restart-safe command-journal records for Phase 2 Task 11."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import isfinite
from typing import Any

from .identifiers import (
    CommandId,
    CorrelationId,
    DecisionId,
    EquipmentGroupId,
    SafetyEvaluationId,
    ZoneId,
)
from .schema import SchemaValidationError

MAX_COMMAND_TEXT_LENGTH = 255
MAX_ACKNOWLEDGEMENT_WINDOW_SECONDS = 5 * 60
MAX_JOURNAL_RECORDS = 100
MAX_JOURNAL_AGE_DAYS = 14


class CommandKind(StrEnum):
    """Allowlisted semantic command kinds; this is not an adapter allowlist."""

    SET_TARGET = "set_target"
    SET_RANGE = "set_range"
    SET_HVAC_MODE = "set_hvac_mode"
    SET_FAN_MODE = "set_fan_mode"
    FAN_ON = "fan_on"
    FAN_OFF = "fan_off"


class CommandControlledField(StrEnum):
    """Normalized state fields that a journal record may control."""

    TARGET = "target"
    RANGE = "range"
    HVAC_MODE = "hvac_mode"
    FAN_MODE = "fan_mode"
    FAN_STATE = "fan_state"


class CommandAuthority(StrEnum):
    """Source authority under which a command intent was created."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"


class CommandCause(StrEnum):
    """Bounded reason for one requested command."""

    MANUAL_USER = "manual_user"
    SCHEDULE = "schedule"
    UI_OVERRIDE = "ui_override"
    OVERRIDE_END = "override_end"
    PROTECTION = "protection"
    FAN_POLICY = "fan_policy"


class CommandJournalStatus(StrEnum):
    """Restart-safe lifecycle state for one journal record."""

    PENDING = "pending"
    DISPATCHED = "dispatched"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    UNCERTAIN = "uncertain"
    SUPPRESSED = "suppressed"


class CommandReasonCode(StrEnum):
    """Privacy-safe lifecycle reason without arbitrary exception text."""

    REQUEST_ACCEPTED = "request_accepted"
    DISPATCH_RECORDED = "dispatch_recorded"
    SEMANTIC_ACKNOWLEDGEMENT = "semantic_acknowledgement"
    REJECTED_BEFORE_DISPATCH = "rejected_before_dispatch"
    ACKNOWLEDGEMENT_DEADLINE_EXPIRED = "acknowledgement_deadline_expired"
    ACTION_FAILED = "action_failed"
    DISPATCH_OUTCOME_UNKNOWN = "dispatch_outcome_unknown"
    CONFLICTING_RESULT = "conflicting_result"
    EXTERNAL_CHANGE = "external_change"
    CORRELATION_AMBIGUOUS = "correlation_ambiguous"


class ObservationOrigin(StrEnum):
    """Privacy-bounded origin category supplied with an observation."""

    INTELLIGENT_CLIMATE = "intelligent_climate"
    HOME_ASSISTANT_USER = "home_assistant_user"
    HOME_ASSISTANT_AUTOMATION = "home_assistant_automation"
    PHYSICAL_DEVICE = "physical_device"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class NormalizedCommandValues:
    """Allowlisted normalized values used by journal and correlation code."""

    target_c: float | None = None
    heat_target_c: float | None = None
    cool_target_c: float | None = None
    hvac_mode: str | None = None
    fan_mode: str | None = None
    fan_state: str | None = None


@dataclass(frozen=True, slots=True)
class NormalizedStateEvidence:
    """Bounded semantic state and revision evidence at one observed instant."""

    revision: int
    observed_at_utc: datetime
    available: bool
    values: NormalizedCommandValues

    def __post_init__(self) -> None:
        """Reject invalid evidence at direct-construction boundaries."""
        validate_state_evidence(self, path="state")


@dataclass(frozen=True, slots=True)
class CommandJournalRecord:
    """Complete typed journal record; no adapter or dispatch behavior."""

    command_id: CommandId
    correlation_id: CorrelationId
    decision_id: DecisionId
    safety_evaluation_id: SafetyEvaluationId
    entry_id: str
    equipment_group_id: EquipmentGroupId
    zone_id: ZoneId
    target_entity_id: str
    command_kind: CommandKind
    requested_fields: frozenset[CommandControlledField]
    requested_values: NormalizedCommandValues
    temperature_tolerance_c: float
    observed_precondition: NormalizedStateEvidence
    requested_against_revision: int
    authority: CommandAuthority
    cause: CommandCause
    user_context_id: str | None
    created_at_utc: datetime
    not_before_utc: datetime
    acknowledgement_deadline_utc: datetime
    status: CommandJournalStatus
    reason_code: CommandReasonCode
    dispatched_at_utc: datetime | None = None
    action_context_id: str | None = None
    service_completed_at_utc: datetime | None = None
    acknowledged_at_utc: datetime | None = None
    failed_at_utc: datetime | None = None
    suppressed_at_utc: datetime | None = None
    observed_result: NormalizedStateEvidence | None = None

    def __post_init__(self) -> None:
        """Reject contradictory journal records at construction time."""
        validate_command_journal_record(self)


@dataclass(frozen=True, slots=True)
class CommandJournalProjection:
    """Privacy-bounded projection omitting entity, user, and context identity."""

    command_kind: CommandKind
    requested_fields: tuple[CommandControlledField, ...]
    authority: CommandAuthority
    cause: CommandCause
    status: CommandJournalStatus
    created_at_utc: datetime
    acknowledgement_deadline_utc: datetime
    terminal_at_utc: datetime | None
    reason_code: CommandReasonCode
    explanation: str


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

_EXPLANATIONS: dict[CommandReasonCode, str] = {
    CommandReasonCode.REQUEST_ACCEPTED: "The request is awaiting dispatch.",
    CommandReasonCode.DISPATCH_RECORDED: "Dispatch is awaiting a matching state.",
    CommandReasonCode.SEMANTIC_ACKNOWLEDGEMENT: (
        "The resulting controlled state matched the request."
    ),
    CommandReasonCode.REJECTED_BEFORE_DISPATCH: (
        "The request was suppressed before dispatch."
    ),
    CommandReasonCode.ACKNOWLEDGEMENT_DEADLINE_EXPIRED: (
        "No matching state arrived before the acknowledgement deadline."
    ),
    CommandReasonCode.ACTION_FAILED: "The command attempt failed.",
    CommandReasonCode.DISPATCH_OUTCOME_UNKNOWN: (
        "The command outcome is uncertain and control remains suspended."
    ),
    CommandReasonCode.CONFLICTING_RESULT: (
        "A conflicting controlled state was observed."
    ),
    CommandReasonCode.EXTERNAL_CHANGE: (
        "The controlled state appears to have changed externally."
    ),
    CommandReasonCode.CORRELATION_AMBIGUOUS: (
        "The controlled-state origin could not be proven safely."
    ),
}


def validate_command_journal_record(record: CommandJournalRecord) -> None:
    """Validate identity, authority, values, revisions, timestamps, and state."""
    _nonempty_text(record.entry_id, "entry_id")
    _entity_id(record.target_entity_id, "target_entity_id")
    if not isinstance(record.command_kind, CommandKind):
        raise SchemaValidationError("command_kind", "is unsupported")
    if not isinstance(record.authority, CommandAuthority):
        raise SchemaValidationError("authority", "is unsupported")
    if not isinstance(record.cause, CommandCause):
        raise SchemaValidationError("cause", "is unsupported")
    if not isinstance(record.status, CommandJournalStatus):
        raise SchemaValidationError("status", "is unsupported")
    if not isinstance(record.reason_code, CommandReasonCode):
        raise SchemaValidationError("reason_code", "is unsupported")
    _validate_requested_values(
        record.command_kind,
        record.requested_fields,
        record.requested_values,
        path="requested_values",
    )
    validate_state_evidence(record.observed_precondition, path="observed_precondition")
    _validate_temperature_tolerance(record.temperature_tolerance_c)
    _require_controlled_fields(
        record.requested_fields,
        record.observed_precondition.values,
        path="observed_precondition.values",
    )
    revision = _positive_integer(
        record.requested_against_revision,
        "requested_against_revision",
    )
    if revision != record.observed_precondition.revision:
        raise SchemaValidationError(
            "requested_against_revision",
            "must match the pre-command observed revision",
        )
    _validate_authority(record)
    _validate_timeline(record)
    _validate_lifecycle(record)


def validate_state_evidence(
    evidence: NormalizedStateEvidence,
    *,
    path: str,
) -> None:
    """Validate one normalized state snapshot without requiring every field."""
    _positive_integer(evidence.revision, f"{path}.revision")
    _utc_datetime(evidence.observed_at_utc, f"{path}.observed_at_utc")
    if type(evidence.available) is not bool:
        raise SchemaValidationError(f"{path}.available", "must be a boolean")
    _validate_normalized_values(evidence.values, path=f"{path}.values")


def command_journal_projection(
    record: CommandJournalRecord,
) -> CommandJournalProjection:
    """Return a fixed privacy-safe journal explanation."""
    validate_command_journal_record(record)
    terminal = (
        record.acknowledged_at_utc or record.failed_at_utc or record.suppressed_at_utc
    )
    return CommandJournalProjection(
        command_kind=record.command_kind,
        requested_fields=tuple(sorted(record.requested_fields, key=str)),
        authority=record.authority,
        cause=record.cause,
        status=record.status,
        created_at_utc=record.created_at_utc,
        acknowledgement_deadline_utc=record.acknowledgement_deadline_utc,
        terminal_at_utc=terminal,
        reason_code=record.reason_code,
        explanation=_EXPLANATIONS[record.reason_code],
    )


def encode_command_journal_record(record: CommandJournalRecord) -> dict[str, Any]:
    """Encode a validated record into deterministic Runtime Store v2 JSON."""
    validate_command_journal_record(record)
    return {
        "command_id": str(record.command_id),
        "correlation_id": str(record.correlation_id),
        "decision_id": str(record.decision_id),
        "safety_evaluation_id": str(record.safety_evaluation_id),
        "entry_id": record.entry_id,
        "equipment_group_id": str(record.equipment_group_id),
        "zone_id": str(record.zone_id),
        "target_entity_id": record.target_entity_id,
        "command_kind": record.command_kind.value,
        "requested_fields": sorted(item.value for item in record.requested_fields),
        "requested_values": _encode_values(record.requested_values),
        "temperature_tolerance_c": record.temperature_tolerance_c,
        "observed_precondition": _encode_state(record.observed_precondition),
        "requested_against_revision": record.requested_against_revision,
        "authority": record.authority.value,
        "cause": record.cause.value,
        "user_context_id": record.user_context_id,
        "created_at_utc": _encode_datetime(record.created_at_utc),
        "not_before_utc": _encode_datetime(record.not_before_utc),
        "acknowledgement_deadline_utc": _encode_datetime(
            record.acknowledgement_deadline_utc
        ),
        "status": record.status.value,
        "reason_code": record.reason_code.value,
        "dispatched_at_utc": _encode_optional_datetime(record.dispatched_at_utc),
        "action_context_id": record.action_context_id,
        "service_completed_at_utc": _encode_optional_datetime(
            record.service_completed_at_utc
        ),
        "acknowledged_at_utc": _encode_optional_datetime(record.acknowledged_at_utc),
        "failed_at_utc": _encode_optional_datetime(record.failed_at_utc),
        "suppressed_at_utc": _encode_optional_datetime(record.suppressed_at_utc),
        "observed_result": (
            None
            if record.observed_result is None
            else _encode_state(record.observed_result)
        ),
    }


def encode_command_journal(
    records: tuple[CommandJournalRecord, ...],
) -> list[dict[str, Any]]:
    """Encode a bounded, canonically ordered Runtime Store v2 journal."""
    validated = _validate_journal_collection(records)
    return [encode_command_journal_record(record) for record in validated]


def decode_command_journal(value: object) -> tuple[CommandJournalRecord, ...]:
    """Decode and strictly validate one bounded journal collection."""
    if not isinstance(value, (list, tuple)):
        raise SchemaValidationError("command_journal", "must be an array")
    records = tuple(decode_command_journal_record(item) for item in value)
    return _validate_journal_collection(records)


def prune_command_journal(
    records: tuple[CommandJournalRecord, ...],
    *,
    now_utc: datetime,
) -> tuple[CommandJournalRecord, ...]:
    """Return the authorized 100-entry/14-day journal using an injected clock."""
    now = _utc_datetime(now_utc, "now_utc")
    ordered = _validate_journal_collection(records, enforce_limit=False)
    cutoff = now - timedelta(days=MAX_JOURNAL_AGE_DAYS)
    if any(record.created_at_utc > now for record in ordered):
        raise SchemaValidationError(
            "command_journal",
            "contains a record created after the caller-supplied clock",
        )
    retained = tuple(record for record in ordered if record.created_at_utc >= cutoff)
    return retained[-MAX_JOURNAL_RECORDS:]


def decode_command_journal_record(value: object) -> CommandJournalRecord:
    """Decode and strictly validate one journal record."""
    data = _mapping(value, "command_journal")
    _exact_keys(
        data,
        {
            "command_id",
            "correlation_id",
            "decision_id",
            "safety_evaluation_id",
            "entry_id",
            "equipment_group_id",
            "zone_id",
            "target_entity_id",
            "command_kind",
            "requested_fields",
            "requested_values",
            "temperature_tolerance_c",
            "observed_precondition",
            "requested_against_revision",
            "authority",
            "cause",
            "user_context_id",
            "created_at_utc",
            "not_before_utc",
            "acknowledgement_deadline_utc",
            "status",
            "reason_code",
            "dispatched_at_utc",
            "action_context_id",
            "service_completed_at_utc",
            "acknowledged_at_utc",
            "failed_at_utc",
            "suppressed_at_utc",
            "observed_result",
        },
        "command_journal",
    )
    result = data["observed_result"]
    try:
        return CommandJournalRecord(
            command_id=CommandId.parse(_text(data["command_id"], "command_id")),
            correlation_id=CorrelationId.parse(
                _text(data["correlation_id"], "correlation_id")
            ),
            decision_id=DecisionId.parse(_text(data["decision_id"], "decision_id")),
            safety_evaluation_id=SafetyEvaluationId.parse(
                _text(data["safety_evaluation_id"], "safety_evaluation_id")
            ),
            entry_id=_text(data["entry_id"], "entry_id"),
            equipment_group_id=EquipmentGroupId.parse(
                _text(data["equipment_group_id"], "equipment_group_id")
            ),
            zone_id=ZoneId.parse(_text(data["zone_id"], "zone_id")),
            target_entity_id=_text(data["target_entity_id"], "target_entity_id"),
            command_kind=_enum(CommandKind, data["command_kind"], "command_kind"),
            requested_fields=_decode_fields(data["requested_fields"]),
            requested_values=_decode_values(
                data["requested_values"], "requested_values"
            ),
            temperature_tolerance_c=_number(
                data["temperature_tolerance_c"],
                "temperature_tolerance_c",
            ),
            observed_precondition=_decode_state(
                data["observed_precondition"], "observed_precondition"
            ),
            requested_against_revision=_positive_integer(
                data["requested_against_revision"],
                "requested_against_revision",
            ),
            authority=_enum(CommandAuthority, data["authority"], "authority"),
            cause=_enum(CommandCause, data["cause"], "cause"),
            user_context_id=_optional_text(data["user_context_id"], "user_context_id"),
            created_at_utc=_decode_datetime(data["created_at_utc"], "created_at_utc"),
            not_before_utc=_decode_datetime(data["not_before_utc"], "not_before_utc"),
            acknowledgement_deadline_utc=_decode_datetime(
                data["acknowledgement_deadline_utc"],
                "acknowledgement_deadline_utc",
            ),
            status=_enum(CommandJournalStatus, data["status"], "status"),
            reason_code=_enum(CommandReasonCode, data["reason_code"], "reason_code"),
            dispatched_at_utc=_decode_optional_datetime(
                data["dispatched_at_utc"], "dispatched_at_utc"
            ),
            action_context_id=_optional_text(
                data["action_context_id"], "action_context_id"
            ),
            service_completed_at_utc=_decode_optional_datetime(
                data["service_completed_at_utc"],
                "service_completed_at_utc",
            ),
            acknowledged_at_utc=_decode_optional_datetime(
                data["acknowledged_at_utc"], "acknowledged_at_utc"
            ),
            failed_at_utc=_decode_optional_datetime(
                data["failed_at_utc"], "failed_at_utc"
            ),
            suppressed_at_utc=_decode_optional_datetime(
                data["suppressed_at_utc"], "suppressed_at_utc"
            ),
            observed_result=(
                None if result is None else _decode_state(result, "observed_result")
            ),
        )
    except (TypeError, ValueError) as err:
        raise SchemaValidationError("command_journal", "contains invalid data") from err


def _validate_authority(record: CommandJournalRecord) -> None:
    manual_causes = frozenset({CommandCause.MANUAL_USER, CommandCause.UI_OVERRIDE})
    if record.authority is CommandAuthority.MANUAL:
        if record.cause not in manual_causes:
            raise SchemaValidationError(
                "cause",
                "is not authorized for manual command authority",
            )
        _nonempty_text(record.user_context_id, "user_context_id")
        return
    if record.cause in manual_causes:
        raise SchemaValidationError(
            "cause",
            "requires manual command authority",
        )
    if record.user_context_id is not None:
        raise SchemaValidationError(
            "user_context_id",
            "must not be stored for scheduled authority",
        )


def _validate_timeline(record: CommandJournalRecord) -> None:
    created = _utc_datetime(record.created_at_utc, "created_at_utc")
    not_before = _utc_datetime(record.not_before_utc, "not_before_utc")
    deadline = _utc_datetime(
        record.acknowledgement_deadline_utc,
        "acknowledgement_deadline_utc",
    )
    if record.observed_precondition.observed_at_utc > created:
        raise SchemaValidationError(
            "observed_precondition.observed_at_utc",
            "must not be later than command creation",
        )
    if not_before < created:
        raise SchemaValidationError(
            "not_before_utc",
            "must not precede command creation",
        )
    if deadline <= not_before:
        raise SchemaValidationError(
            "acknowledgement_deadline_utc",
            "must be later than not_before_utc",
        )
    if (deadline - not_before).total_seconds() > MAX_ACKNOWLEDGEMENT_WINDOW_SECONDS:
        raise SchemaValidationError(
            "acknowledgement_deadline_utc",
            "exceeds the bounded acknowledgement window",
        )
    timeline = (
        ("dispatched_at_utc", record.dispatched_at_utc),
        ("service_completed_at_utc", record.service_completed_at_utc),
        ("acknowledged_at_utc", record.acknowledged_at_utc),
        ("failed_at_utc", record.failed_at_utc),
        ("suppressed_at_utc", record.suppressed_at_utc),
    )
    for path, value in timeline:
        if value is not None and _utc_datetime(value, path) < created:
            raise SchemaValidationError(path, "must not precede command creation")
    if record.dispatched_at_utc is not None and record.dispatched_at_utc < not_before:
        raise SchemaValidationError(
            "dispatched_at_utc",
            "must not precede not_before_utc",
        )
    if record.service_completed_at_utc is not None and (
        record.dispatched_at_utc is None
        or record.service_completed_at_utc < record.dispatched_at_utc
    ):
        raise SchemaValidationError(
            "service_completed_at_utc",
            "requires and must follow dispatch",
        )
    if record.acknowledged_at_utc is not None and (
        record.dispatched_at_utc is None
        or record.acknowledged_at_utc < record.dispatched_at_utc
        or record.acknowledged_at_utc > deadline
    ):
        raise SchemaValidationError(
            "acknowledged_at_utc",
            "requires dispatch and must fall within the acknowledgement window",
        )
    if (
        record.observed_result is not None
        and record.observed_result.observed_at_utc < created
    ):
        raise SchemaValidationError(
            "observed_result.observed_at_utc",
            "must not precede command creation",
        )
    if (
        record.observed_result is not None
        and record.observed_result.revision <= record.observed_precondition.revision
    ):
        raise SchemaValidationError(
            "observed_result.revision",
            "must be newer than the pre-command observed revision",
        )


def _validate_lifecycle(record: CommandJournalRecord) -> None:
    present = {
        "dispatch": record.dispatched_at_utc is not None,
        "action_context": record.action_context_id is not None,
        "service_completed": record.service_completed_at_utc is not None,
        "acknowledged": record.acknowledged_at_utc is not None,
        "failed": record.failed_at_utc is not None,
        "suppressed": record.suppressed_at_utc is not None,
        "result": record.observed_result is not None,
    }
    allowed: dict[CommandJournalStatus, frozenset[str]] = {
        CommandJournalStatus.PENDING: frozenset(),
        CommandJournalStatus.DISPATCHED: frozenset(
            {"dispatch", "action_context", "service_completed"}
        ),
        CommandJournalStatus.ACKNOWLEDGED: frozenset(
            {
                "dispatch",
                "action_context",
                "service_completed",
                "acknowledged",
                "result",
            }
        ),
        CommandJournalStatus.FAILED: frozenset(
            {"dispatch", "action_context", "service_completed", "failed"}
        ),
        CommandJournalStatus.UNCERTAIN: frozenset(
            {"dispatch", "action_context", "service_completed", "failed"}
        ),
        CommandJournalStatus.SUPPRESSED: frozenset({"suppressed"}),
    }
    actual = frozenset(name for name, is_present in present.items() if is_present)
    required: dict[CommandJournalStatus, frozenset[str]] = {
        CommandJournalStatus.PENDING: frozenset(),
        CommandJournalStatus.DISPATCHED: frozenset({"dispatch"}),
        CommandJournalStatus.ACKNOWLEDGED: frozenset(
            {"dispatch", "acknowledged", "result"}
        ),
        CommandJournalStatus.FAILED: frozenset({"failed"}),
        CommandJournalStatus.UNCERTAIN: frozenset({"failed"}),
        CommandJournalStatus.SUPPRESSED: frozenset({"suppressed"}),
    }
    if not required[record.status].issubset(actual) or not actual.issubset(
        allowed[record.status]
    ):
        raise SchemaValidationError(
            "status",
            "contradicts the recorded lifecycle timestamps or result",
        )
    valid_reasons: dict[CommandJournalStatus, frozenset[CommandReasonCode]] = {
        CommandJournalStatus.PENDING: frozenset({CommandReasonCode.REQUEST_ACCEPTED}),
        CommandJournalStatus.DISPATCHED: frozenset(
            {CommandReasonCode.DISPATCH_RECORDED}
        ),
        CommandJournalStatus.ACKNOWLEDGED: frozenset(
            {CommandReasonCode.SEMANTIC_ACKNOWLEDGEMENT}
        ),
        CommandJournalStatus.FAILED: frozenset(
            {
                CommandReasonCode.ACKNOWLEDGEMENT_DEADLINE_EXPIRED,
                CommandReasonCode.ACTION_FAILED,
                CommandReasonCode.CONFLICTING_RESULT,
            }
        ),
        CommandJournalStatus.UNCERTAIN: frozenset(
            {
                CommandReasonCode.DISPATCH_OUTCOME_UNKNOWN,
                CommandReasonCode.CORRELATION_AMBIGUOUS,
                CommandReasonCode.EXTERNAL_CHANGE,
            }
        ),
        CommandJournalStatus.SUPPRESSED: frozenset(
            {CommandReasonCode.REJECTED_BEFORE_DISPATCH}
        ),
    }
    if record.reason_code not in valid_reasons[record.status]:
        raise SchemaValidationError(
            "reason_code",
            "is not valid for the journal lifecycle state",
        )
    if record.action_context_id is not None:
        _nonempty_text(record.action_context_id, "action_context_id")
    if record.status is CommandJournalStatus.ACKNOWLEDGED:
        assert record.observed_result is not None
        if not _semantic_values_match(
            record.requested_fields,
            record.requested_values,
            record.observed_result.values,
            temperature_tolerance_c=record.temperature_tolerance_c,
        ):
            raise SchemaValidationError(
                "observed_result.values",
                "does not semantically acknowledge the requested controlled fields",
            )


def _validate_requested_values(
    kind: CommandKind,
    fields: frozenset[CommandControlledField],
    values: NormalizedCommandValues,
    *,
    path: str,
) -> None:
    if not isinstance(fields, frozenset) or fields not in _COMMAND_FIELDS[kind]:
        raise SchemaValidationError(
            "requested_fields",
            "does not match the command kind",
        )
    _validate_normalized_values(values, path=path)
    required = {
        CommandControlledField.TARGET: values.target_c,
        CommandControlledField.RANGE: (
            values.heat_target_c if values.cool_target_c is not None else None
        ),
        CommandControlledField.HVAC_MODE: values.hvac_mode,
        CommandControlledField.FAN_MODE: values.fan_mode,
        CommandControlledField.FAN_STATE: values.fan_state,
    }
    if any(required[field] is None for field in fields):
        raise SchemaValidationError(path, "is missing a requested controlled value")
    present_fields = frozenset(
        field for field, value in required.items() if value is not None
    )
    if present_fields != fields:
        raise SchemaValidationError(
            path,
            "contains a value outside the requested controlled fields",
        )
    if kind is CommandKind.FAN_ON and values.fan_state != "on":
        raise SchemaValidationError(f"{path}.fan_state", "must be 'on'")
    if kind is CommandKind.FAN_OFF and values.fan_state != "off":
        raise SchemaValidationError(f"{path}.fan_state", "must be 'off'")


def _validate_normalized_values(
    values: NormalizedCommandValues,
    *,
    path: str,
) -> None:
    if not isinstance(values, NormalizedCommandValues):
        raise SchemaValidationError(path, "must be normalized controlled values")
    for name, value in (
        ("target_c", values.target_c),
        ("heat_target_c", values.heat_target_c),
        ("cool_target_c", values.cool_target_c),
    ):
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not isfinite(value)
        ):
            raise SchemaValidationError(f"{path}.{name}", "must be finite")
    if (values.heat_target_c is None) is not (values.cool_target_c is None):
        raise SchemaValidationError(path, "range endpoints must appear together")
    if (
        values.heat_target_c is not None
        and values.cool_target_c is not None
        and values.heat_target_c >= values.cool_target_c
    ):
        raise SchemaValidationError(path, "heat target must be below cool target")
    for name, text_value in (
        ("hvac_mode", values.hvac_mode),
        ("fan_mode", values.fan_mode),
        ("fan_state", values.fan_state),
    ):
        if text_value is not None:
            _nonempty_text(text_value, f"{path}.{name}")
    if values.fan_state not in {None, "on", "off"}:
        raise SchemaValidationError(
            f"{path}.fan_state",
            "must be 'on' or 'off'",
        )


def _require_controlled_fields(
    fields: frozenset[CommandControlledField],
    values: NormalizedCommandValues,
    *,
    path: str,
) -> None:
    present = {
        CommandControlledField.TARGET: values.target_c is not None,
        CommandControlledField.RANGE: (
            values.heat_target_c is not None and values.cool_target_c is not None
        ),
        CommandControlledField.HVAC_MODE: values.hvac_mode is not None,
        CommandControlledField.FAN_MODE: values.fan_mode is not None,
        CommandControlledField.FAN_STATE: values.fan_state is not None,
    }
    if any(not present[field] for field in fields):
        raise SchemaValidationError(
            path,
            "is missing pre-command evidence for a controlled field",
        )


def _semantic_values_match(
    fields: frozenset[CommandControlledField],
    requested: NormalizedCommandValues,
    observed: NormalizedCommandValues,
    *,
    temperature_tolerance_c: float,
) -> bool:
    comparisons = {
        CommandControlledField.TARGET: _temperature_matches(
            requested.target_c,
            observed.target_c,
            temperature_tolerance_c,
        ),
        CommandControlledField.RANGE: (
            _temperature_matches(
                requested.heat_target_c,
                observed.heat_target_c,
                temperature_tolerance_c,
            )
            and _temperature_matches(
                requested.cool_target_c,
                observed.cool_target_c,
                temperature_tolerance_c,
            )
        ),
        CommandControlledField.HVAC_MODE: (
            requested.hvac_mode is not None
            and requested.hvac_mode == observed.hvac_mode
        ),
        CommandControlledField.FAN_MODE: (
            requested.fan_mode is not None and requested.fan_mode == observed.fan_mode
        ),
        CommandControlledField.FAN_STATE: (
            requested.fan_state is not None
            and requested.fan_state == observed.fan_state
        ),
    }
    return all(comparisons[field] for field in fields)


def _temperature_matches(
    requested: float | None,
    observed: float | None,
    tolerance: float,
) -> bool:
    return (
        requested is not None
        and observed is not None
        and abs(requested - observed) <= tolerance
    )


def _validate_temperature_tolerance(value: object) -> float:
    tolerance = _number(value, "temperature_tolerance_c")
    if tolerance < 0 or tolerance > 5:
        raise SchemaValidationError(
            "temperature_tolerance_c",
            "must be between 0 and 5",
        )
    return tolerance


def _encode_values(value: NormalizedCommandValues) -> dict[str, Any]:
    return {
        "target_c": value.target_c,
        "heat_target_c": value.heat_target_c,
        "cool_target_c": value.cool_target_c,
        "hvac_mode": value.hvac_mode,
        "fan_mode": value.fan_mode,
        "fan_state": value.fan_state,
    }


def _decode_values(value: object, path: str) -> NormalizedCommandValues:
    data = _mapping(value, path)
    _exact_keys(
        data,
        {
            "target_c",
            "heat_target_c",
            "cool_target_c",
            "hvac_mode",
            "fan_mode",
            "fan_state",
        },
        path,
    )
    result = NormalizedCommandValues(
        target_c=_optional_number(data["target_c"], f"{path}.target_c"),
        heat_target_c=_optional_number(data["heat_target_c"], f"{path}.heat_target_c"),
        cool_target_c=_optional_number(data["cool_target_c"], f"{path}.cool_target_c"),
        hvac_mode=_optional_text(data["hvac_mode"], f"{path}.hvac_mode"),
        fan_mode=_optional_text(data["fan_mode"], f"{path}.fan_mode"),
        fan_state=_optional_text(data["fan_state"], f"{path}.fan_state"),
    )
    _validate_normalized_values(result, path=path)
    return result


def _encode_state(value: NormalizedStateEvidence) -> dict[str, Any]:
    return {
        "revision": value.revision,
        "observed_at_utc": _encode_datetime(value.observed_at_utc),
        "available": value.available,
        "values": _encode_values(value.values),
    }


def _decode_state(value: object, path: str) -> NormalizedStateEvidence:
    data = _mapping(value, path)
    _exact_keys(data, {"revision", "observed_at_utc", "available", "values"}, path)
    available = data["available"]
    if type(available) is not bool:
        raise SchemaValidationError(f"{path}.available", "must be a boolean")
    return NormalizedStateEvidence(
        revision=_positive_integer(data["revision"], f"{path}.revision"),
        observed_at_utc=_decode_datetime(
            data["observed_at_utc"], f"{path}.observed_at_utc"
        ),
        available=available,
        values=_decode_values(data["values"], f"{path}.values"),
    )


def _decode_fields(value: object) -> frozenset[CommandControlledField]:
    if not isinstance(value, (list, tuple)) or not value:
        raise SchemaValidationError(
            "requested_fields",
            "must be a nonempty array",
        )
    fields = tuple(
        _enum(CommandControlledField, item, "requested_fields") for item in value
    )
    if len(fields) != len(set(fields)):
        raise SchemaValidationError("requested_fields", "contains duplicates")
    return frozenset(fields)


def _validate_journal_collection(
    records: tuple[CommandJournalRecord, ...],
    *,
    enforce_limit: bool = True,
) -> tuple[CommandJournalRecord, ...]:
    if not isinstance(records, tuple):
        raise SchemaValidationError(
            "command_journal",
            "must be an immutable sequence",
        )
    if enforce_limit and len(records) > MAX_JOURNAL_RECORDS:
        raise SchemaValidationError(
            "command_journal",
            "exceeds the 100-record persistence bound",
        )
    for record in records:
        validate_command_journal_record(record)
    if len({record.command_id for record in records}) != len(records):
        raise SchemaValidationError(
            "command_journal",
            "contains duplicate command identities",
        )
    if len({record.correlation_id for record in records}) != len(records):
        raise SchemaValidationError(
            "command_journal",
            "contains duplicate correlation identities",
        )
    ordered = tuple(
        sorted(
            records,
            key=lambda record: (record.created_at_utc, str(record.command_id)),
        )
    )
    if records != ordered:
        raise SchemaValidationError(
            "command_journal",
            "must use canonical chronological ordering",
        )
    return records


def _mapping(value: object, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaValidationError(path, "must be an object")
    if any(not isinstance(key, str) for key in value):
        raise SchemaValidationError(path, "contains a non-string key")
    return value


def _exact_keys(data: Mapping[str, Any], expected: set[str], path: str) -> None:
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
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    return _nonempty_text(value, path)


def _optional_text(value: object, path: str) -> str | None:
    if value is None:
        return None
    return _text(value, path)


def _nonempty_text(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_COMMAND_TEXT_LENGTH
    ):
        raise SchemaValidationError(
            path,
            "must be nonempty and no more than 255 characters",
        )
    return value


def _entity_id(value: object, path: str) -> str:
    entity_id = _nonempty_text(value, path)
    domain, separator, object_id = entity_id.partition(".")
    if separator != "." or domain not in {"climate", "fan"} or not object_id:
        raise SchemaValidationError(path, "must be a climate or fan entity ID")
    return entity_id


def _positive_integer(value: object, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SchemaValidationError(path, "must be a positive integer")
    return value


def _optional_number(value: object, path: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
    ):
        raise SchemaValidationError(path, "must be finite")
    return float(value)


def _number(value: object, path: str) -> float:
    parsed = _optional_number(value, path)
    if parsed is None:
        raise SchemaValidationError(path, "is required")
    return parsed


def _utc_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise SchemaValidationError(path, "must be timezone-aware")
    if value.utcoffset() != UTC.utcoffset(value):
        raise SchemaValidationError(path, "must use UTC")
    return value


def _encode_datetime(value: datetime) -> str:
    return _utc_datetime(value, "datetime").isoformat().replace("+00:00", "Z")


def _encode_optional_datetime(value: datetime | None) -> str | None:
    return None if value is None else _encode_datetime(value)


def _decode_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid ISO-8601 value") from err
    return _utc_datetime(parsed, path)


def _decode_optional_datetime(value: object, path: str) -> datetime | None:
    return None if value is None else _decode_datetime(value, path)
