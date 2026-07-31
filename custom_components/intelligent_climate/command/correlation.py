"""Deterministic command/state correlation with no adapter or runtime wiring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import StrEnum
from math import isclose, isfinite

from ..models.command import (
    CommandControlledField,
    CommandJournalRecord,
    CommandJournalStatus,
    NormalizedCommandValues,
    NormalizedStateEvidence,
    ObservationOrigin,
    validate_command_journal_record,
    validate_state_evidence,
)
from ..models.identifiers import CommandId, CorrelationId
from ..models.schema import SchemaValidationError

DEFAULT_TEMPERATURE_DEADBAND_C = 0.25
DEFAULT_LATE_CORRELATION_SECONDS = 120
MAX_LATE_CORRELATION_SECONDS = 5 * 60
MAX_CONTEXT_LENGTH = 255


class CorrelationClassification(StrEnum):
    """Fail-closed classification for one observed state change."""

    ACKNOWLEDGED = "acknowledged"
    INTELLIGENT_CLIMATE_CHANGE = "intelligent_climate_change"
    EXTERNAL_CHANGE = "external_change"
    AMBIGUOUS_ORIGIN = "ambiguous_origin"
    CONFLICTING_RESULT = "conflicting_result"
    UNRELATED_OBSERVATION = "unrelated_observation"
    STALE_OBSERVATION = "stale_observation"
    REORDERED_OBSERVATION = "reordered_observation"
    DUPLICATE_OBSERVATION = "duplicate_observation"


class CorrelationReasonCode(StrEnum):
    """Privacy-safe reason for a correlation classification."""

    SEMANTIC_PENDING_MATCH = "semantic_pending_match"
    COMMAND_ID_AND_STATE_MATCH = "command_id_and_state_match"
    CONTEXT_AND_STATE_MATCH = "context_and_state_match"
    STATE_ONLY_MATCH = "state_only_match"
    LATE_ACKNOWLEDGED_MATCH = "late_acknowledged_match"
    EXPLICIT_EXTERNAL_ORIGIN = "explicit_external_origin"
    IDENTIFIER_MISMATCH = "identifier_mismatch"
    MISSING_OR_AMBIGUOUS_ORIGIN = "missing_or_ambiguous_origin"
    CONTROLLED_STATE_CONFLICT = "controlled_state_conflict"
    TELEMETRY_ONLY = "telemetry_only"
    WRONG_TARGET = "wrong_target"
    BEFORE_COMMAND = "before_command"
    REVISION_BEFORE_COMMAND = "revision_before_command"
    REVISION_REORDERED = "revision_reordered"
    REVISION_DUPLICATE = "revision_duplicate"


@dataclass(frozen=True, slots=True)
class ObservedStateChange:
    """Caller-supplied normalized observation and bounded origin evidence."""

    entry_id: str
    target_entity_id: str
    state: NormalizedStateEvidence
    changed_fields: frozenset[CommandControlledField]
    origin: ObservationOrigin
    context_id: str | None = None
    parent_context_id: str | None = None
    reported_command_id: CommandId | None = None
    reported_correlation_id: CorrelationId | None = None


@dataclass(frozen=True, slots=True)
class CorrelationPolicy:
    """Pure caller-supplied tolerances and external-origin policy."""

    late_correlation_seconds: int = DEFAULT_LATE_CORRELATION_SECONDS
    all_external_changes_are_overrides: bool = True


@dataclass(frozen=True, slots=True)
class CorrelationInput:
    """Complete deterministic input for one correlation evaluation."""

    observation: ObservedStateChange
    journal: tuple[CommandJournalRecord, ...]
    policy: CorrelationPolicy
    last_processed_revision: int | None = None
    last_processed_state: NormalizedStateEvidence | None = None
    external_change_after_last_ack: bool = False


@dataclass(frozen=True, slots=True)
class CorrelationResult:
    """Privacy-safe classification with optional matched stable identity."""

    classification: CorrelationClassification
    reason_code: CorrelationReasonCode
    matched_command_id: CommandId | None
    matched_correlation_id: CorrelationId | None
    should_acknowledge: bool
    should_suspend_control: bool
    explanation: str


_EXPLANATIONS: dict[CorrelationReasonCode, str] = {
    CorrelationReasonCode.SEMANTIC_PENDING_MATCH: (
        "The controlled state matches a pending command."
    ),
    CorrelationReasonCode.COMMAND_ID_AND_STATE_MATCH: (
        "Command identity and controlled state both match."
    ),
    CorrelationReasonCode.CONTEXT_AND_STATE_MATCH: (
        "Action context and controlled state both match."
    ),
    CorrelationReasonCode.STATE_ONLY_MATCH: (
        "The controlled state matches within the acknowledgement window."
    ),
    CorrelationReasonCode.LATE_ACKNOWLEDGED_MATCH: (
        "The state matches a recent acknowledged command."
    ),
    CorrelationReasonCode.EXPLICIT_EXTERNAL_ORIGIN: (
        "The controlled change has an explicit external origin."
    ),
    CorrelationReasonCode.IDENTIFIER_MISMATCH: (
        "The observation identifies a different command."
    ),
    CorrelationReasonCode.MISSING_OR_AMBIGUOUS_ORIGIN: (
        "The controlled-state origin cannot be proven safely."
    ),
    CorrelationReasonCode.CONTROLLED_STATE_CONFLICT: (
        "The observed controlled state conflicts with the request."
    ),
    CorrelationReasonCode.TELEMETRY_ONLY: (
        "The update does not change a controlled field."
    ),
    CorrelationReasonCode.WRONG_TARGET: (
        "The update is unrelated to the candidate command target."
    ),
    CorrelationReasonCode.BEFORE_COMMAND: (
        "The observation predates the candidate command."
    ),
    CorrelationReasonCode.REVISION_BEFORE_COMMAND: (
        "The observation revision predates the command precondition."
    ),
    CorrelationReasonCode.REVISION_REORDERED: (
        "The observation arrived after a newer revision."
    ),
    CorrelationReasonCode.REVISION_DUPLICATE: (
        "The observation repeats the last processed revision and state."
    ),
}

_EXPLICIT_EXTERNAL = frozenset(
    {
        ObservationOrigin.HOME_ASSISTANT_USER,
        ObservationOrigin.HOME_ASSISTANT_AUTOMATION,
        ObservationOrigin.PHYSICAL_DEVICE,
    }
)


def correlate_state_change(value: CorrelationInput) -> CorrelationResult:
    """Classify one observation using identity, context, state, order, and time."""
    _validate_input(value)
    observation = value.observation

    sequence_result = _sequence_classification(value)
    if sequence_result is not None:
        return sequence_result

    candidates = tuple(
        record
        for record in value.journal
        if record.entry_id == observation.entry_id
        and record.target_entity_id == observation.target_entity_id
    )
    if not candidates:
        return _without_candidate(value, wrong_target=bool(value.journal))

    latest = max(candidates, key=lambda item: item.created_at_utc)
    if observation.state.revision < latest.observed_precondition.revision:
        return _result(
            CorrelationClassification.STALE_OBSERVATION,
            CorrelationReasonCode.REVISION_BEFORE_COMMAND,
        )
    if observation.state.observed_at_utc < latest.created_at_utc:
        return _result(
            CorrelationClassification.STALE_OBSERVATION,
            CorrelationReasonCode.BEFORE_COMMAND,
        )

    identity_match = _identity_match(observation, latest)
    if identity_match is False:
        return _external_or_ambiguous(
            value.policy,
            CorrelationReasonCode.IDENTIFIER_MISMATCH,
        )

    controlled_changed = bool(
        observation.changed_fields.intersection(latest.requested_fields)
    )
    if not controlled_changed:
        return _result(
            CorrelationClassification.UNRELATED_OBSERVATION,
            CorrelationReasonCode.TELEMETRY_ONLY,
        )

    if observation.origin in _EXPLICIT_EXTERNAL and not _context_matches(
        observation, latest
    ):
        return _result(
            CorrelationClassification.EXTERNAL_CHANGE,
            CorrelationReasonCode.EXPLICIT_EXTERNAL_ORIGIN,
            suspend=True,
        )

    semantic_match = semantic_state_matches(
        latest.requested_fields,
        latest.requested_values,
        observation.state.values,
        temperature_deadband_c=latest.temperature_tolerance_c,
    )
    if latest.status in {
        CommandJournalStatus.PENDING,
        CommandJournalStatus.DISPATCHED,
    }:
        return _pending_result(value, latest, identity_match, semantic_match)

    if latest.status is CommandJournalStatus.ACKNOWLEDGED:
        return _acknowledged_result(value, latest, semantic_match)

    if semantic_match:
        return _external_or_ambiguous(
            value.policy,
            CorrelationReasonCode.MISSING_OR_AMBIGUOUS_ORIGIN,
        )
    return _result(
        CorrelationClassification.CONFLICTING_RESULT,
        CorrelationReasonCode.CONTROLLED_STATE_CONFLICT,
        matched=latest,
        suspend=True,
    )


def semantic_state_matches(
    fields: frozenset[CommandControlledField],
    requested: NormalizedCommandValues,
    observed: NormalizedCommandValues,
    *,
    temperature_deadband_c: float,
) -> bool:
    """Return whether every controlled semantic field matches."""
    _validate_deadband(temperature_deadband_c)
    if not isinstance(fields, frozenset) or not fields:
        raise SchemaValidationError("fields", "must be a nonempty immutable set")
    if any(not isinstance(field, CommandControlledField) for field in fields):
        raise SchemaValidationError("fields", "contains an unsupported field")
    comparisons = {
        CommandControlledField.TARGET: _temperature_matches(
            requested.target_c,
            observed.target_c,
            temperature_deadband_c,
        ),
        CommandControlledField.RANGE: (
            _temperature_matches(
                requested.heat_target_c,
                observed.heat_target_c,
                temperature_deadband_c,
            )
            and _temperature_matches(
                requested.cool_target_c,
                observed.cool_target_c,
                temperature_deadband_c,
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


def _pending_result(
    value: CorrelationInput,
    record: CommandJournalRecord,
    identity_match: bool | None,
    semantic_match: bool,
) -> CorrelationResult:
    observation = value.observation
    if observation.state.observed_at_utc > record.acknowledgement_deadline_utc:
        if semantic_match:
            return _external_or_ambiguous(
                value.policy,
                CorrelationReasonCode.MISSING_OR_AMBIGUOUS_ORIGIN,
            )
        return _result(
            CorrelationClassification.CONFLICTING_RESULT,
            CorrelationReasonCode.CONTROLLED_STATE_CONFLICT,
            matched=record,
            suspend=True,
        )
    if not semantic_match:
        return _result(
            CorrelationClassification.CONFLICTING_RESULT,
            CorrelationReasonCode.CONTROLLED_STATE_CONFLICT,
            matched=record,
            suspend=True,
        )
    if identity_match:
        reason = CorrelationReasonCode.COMMAND_ID_AND_STATE_MATCH
    elif _context_matches(observation, record):
        reason = CorrelationReasonCode.CONTEXT_AND_STATE_MATCH
    elif observation.origin is ObservationOrigin.INTELLIGENT_CLIMATE:
        reason = CorrelationReasonCode.SEMANTIC_PENDING_MATCH
    else:
        reason = CorrelationReasonCode.STATE_ONLY_MATCH
    return _result(
        CorrelationClassification.ACKNOWLEDGED,
        reason,
        matched=record,
        acknowledge=True,
    )


def _acknowledged_result(
    value: CorrelationInput,
    record: CommandJournalRecord,
    semantic_match: bool,
) -> CorrelationResult:
    if (
        semantic_match
        and not value.external_change_after_last_ack
        and record.acknowledged_at_utc is not None
        and value.observation.state.observed_at_utc
        <= record.acknowledged_at_utc
        + timedelta(seconds=value.policy.late_correlation_seconds)
    ):
        return _result(
            CorrelationClassification.INTELLIGENT_CLIMATE_CHANGE,
            CorrelationReasonCode.LATE_ACKNOWLEDGED_MATCH,
            matched=record,
        )
    if not semantic_match:
        return _result(
            CorrelationClassification.EXTERNAL_CHANGE,
            CorrelationReasonCode.CONTROLLED_STATE_CONFLICT,
            matched=record,
            suspend=True,
        )
    return _external_or_ambiguous(
        value.policy,
        CorrelationReasonCode.MISSING_OR_AMBIGUOUS_ORIGIN,
    )


def _without_candidate(
    value: CorrelationInput,
    *,
    wrong_target: bool,
) -> CorrelationResult:
    if not value.observation.changed_fields:
        return _result(
            CorrelationClassification.UNRELATED_OBSERVATION,
            CorrelationReasonCode.TELEMETRY_ONLY,
        )
    if wrong_target:
        return _result(
            CorrelationClassification.UNRELATED_OBSERVATION,
            CorrelationReasonCode.WRONG_TARGET,
        )
    if value.observation.origin in _EXPLICIT_EXTERNAL:
        return _result(
            CorrelationClassification.EXTERNAL_CHANGE,
            CorrelationReasonCode.EXPLICIT_EXTERNAL_ORIGIN,
            suspend=True,
        )
    return _external_or_ambiguous(
        value.policy,
        CorrelationReasonCode.MISSING_OR_AMBIGUOUS_ORIGIN,
    )


def _sequence_classification(value: CorrelationInput) -> CorrelationResult | None:
    last_revision = value.last_processed_revision
    if last_revision is None:
        return None
    current = value.observation.state.revision
    if current < last_revision:
        return _result(
            CorrelationClassification.REORDERED_OBSERVATION,
            CorrelationReasonCode.REVISION_REORDERED,
        )
    if current > last_revision:
        return None
    if (
        value.last_processed_state is not None
        and value.observation.state.values == value.last_processed_state.values
        and value.observation.state.available == value.last_processed_state.available
    ):
        return _result(
            CorrelationClassification.DUPLICATE_OBSERVATION,
            CorrelationReasonCode.REVISION_DUPLICATE,
        )
    raise SchemaValidationError(
        "observation.state.revision",
        "same revision contradicts the last processed state",
    )


def _identity_match(
    observation: ObservedStateChange,
    record: CommandJournalRecord,
) -> bool | None:
    matches: list[bool] = []
    if observation.reported_command_id is not None:
        matches.append(observation.reported_command_id == record.command_id)
    if observation.reported_correlation_id is not None:
        matches.append(observation.reported_correlation_id == record.correlation_id)
    if not matches:
        return None
    return all(matches)


def _context_matches(
    observation: ObservedStateChange,
    record: CommandJournalRecord,
) -> bool:
    if record.action_context_id is None:
        return False
    return record.action_context_id in {
        observation.context_id,
        observation.parent_context_id,
    }


def _external_or_ambiguous(
    policy: CorrelationPolicy,
    reason: CorrelationReasonCode,
) -> CorrelationResult:
    if policy.all_external_changes_are_overrides:
        return _result(
            CorrelationClassification.EXTERNAL_CHANGE,
            reason,
            suspend=True,
        )
    return _result(
        CorrelationClassification.AMBIGUOUS_ORIGIN,
        reason,
        suspend=True,
    )


def _result(
    classification: CorrelationClassification,
    reason: CorrelationReasonCode,
    *,
    matched: CommandJournalRecord | None = None,
    acknowledge: bool = False,
    suspend: bool = False,
) -> CorrelationResult:
    return CorrelationResult(
        classification=classification,
        reason_code=reason,
        matched_command_id=None if matched is None else matched.command_id,
        matched_correlation_id=None if matched is None else matched.correlation_id,
        should_acknowledge=acknowledge,
        should_suspend_control=suspend,
        explanation=_EXPLANATIONS[reason],
    )


def _validate_input(value: CorrelationInput) -> None:
    observation = value.observation
    if not isinstance(observation, ObservedStateChange):
        raise SchemaValidationError("observation", "must be normalized")
    _bounded_text(observation.entry_id, "observation.entry_id")
    _entity_id(observation.target_entity_id, "observation.target_entity_id")
    validate_state_evidence(observation.state, path="observation.state")
    if not isinstance(observation.changed_fields, frozenset):
        raise SchemaValidationError(
            "observation.changed_fields",
            "must be an immutable set",
        )
    if any(
        not isinstance(field, CommandControlledField)
        for field in observation.changed_fields
    ):
        raise SchemaValidationError(
            "observation.changed_fields",
            "contains an unsupported field",
        )
    if not isinstance(observation.origin, ObservationOrigin):
        raise SchemaValidationError("observation.origin", "is unsupported")
    _optional_context(observation.context_id, "observation.context_id")
    _optional_context(
        observation.parent_context_id,
        "observation.parent_context_id",
    )
    if type(value.policy.all_external_changes_are_overrides) is not bool:
        raise SchemaValidationError(
            "policy.all_external_changes_are_overrides",
            "must be a boolean",
        )
    if (
        isinstance(value.policy.late_correlation_seconds, bool)
        or not isinstance(value.policy.late_correlation_seconds, int)
        or not 0
        <= value.policy.late_correlation_seconds
        <= MAX_LATE_CORRELATION_SECONDS
    ):
        raise SchemaValidationError(
            "policy.late_correlation_seconds",
            "must be between 0 and 300",
        )
    if not isinstance(value.journal, tuple):
        raise SchemaValidationError("journal", "must be an immutable sequence")
    for record in value.journal:
        validate_command_journal_record(record)
    if len({record.command_id for record in value.journal}) != len(value.journal):
        raise SchemaValidationError("journal", "contains duplicate command identities")
    if len({record.correlation_id for record in value.journal}) != len(value.journal):
        raise SchemaValidationError(
            "journal",
            "contains duplicate correlation identities",
        )
    if value.last_processed_revision is not None:
        if (
            isinstance(value.last_processed_revision, bool)
            or not isinstance(value.last_processed_revision, int)
            or value.last_processed_revision < 1
        ):
            raise SchemaValidationError(
                "last_processed_revision",
                "must be a positive integer",
            )
        if value.last_processed_state is None:
            raise SchemaValidationError(
                "last_processed_state",
                "is required with last_processed_revision",
            )
        validate_state_evidence(
            value.last_processed_state,
            path="last_processed_state",
        )
        if value.last_processed_state.revision != value.last_processed_revision:
            raise SchemaValidationError(
                "last_processed_state.revision",
                "must match last_processed_revision",
            )
    elif value.last_processed_state is not None:
        raise SchemaValidationError(
            "last_processed_state",
            "requires last_processed_revision",
        )
    if type(value.external_change_after_last_ack) is not bool:
        raise SchemaValidationError(
            "external_change_after_last_ack",
            "must be a boolean",
        )


def _temperature_matches(
    requested: float | None,
    observed: float | None,
    deadband: float,
) -> bool:
    return (
        requested is not None
        and observed is not None
        and isfinite(requested)
        and isfinite(observed)
        and (
            abs(requested - observed) <= deadband
            or isclose(
                abs(requested - observed),
                deadband,
                rel_tol=0.0,
                abs_tol=1e-9,
            )
        )
    )


def _validate_deadband(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not isfinite(value)
        or value < 0
        or value > 5
    ):
        raise SchemaValidationError(
            "temperature_deadband_c",
            "must be finite and between 0 and 5",
        )
    return float(value)


def _optional_context(value: object, path: str) -> None:
    if value is not None:
        _bounded_text(value, path)


def _bounded_text(value: object, path: str) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
        or len(value) > MAX_CONTEXT_LENGTH
    ):
        raise SchemaValidationError(
            path,
            "must be nonempty and no more than 255 characters",
        )
    return value


def _entity_id(value: object, path: str) -> str:
    entity_id = _bounded_text(value, path)
    domain, separator, object_id = entity_id.partition(".")
    if separator != "." or domain not in {"climate", "fan"} or not object_id:
        raise SchemaValidationError(path, "must be a climate or fan entity ID")
    return entity_id
