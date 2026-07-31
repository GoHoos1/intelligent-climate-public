"""Typed Shadow history and readiness records for Phase 2 Task 18."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .command import (
    CommandAuthority,
    CommandCause,
    CommandControlledField,
    CommandKind,
    NormalizedCommandValues,
)
from .identifiers import CommandId, DecisionId, SafetyEvaluationId
from .safety import SafetyDisposition, SafetyReasonCode

MAX_SHADOW_HISTORY_RECORDS = 100
MAX_SHADOW_HISTORY_AGE_DAYS = 14
MIN_SHADOW_HOURS = 24
MIN_SHADOW_DECISIONS = 20
MIN_SHADOW_TRANSITIONS_PER_ZONE = 2
MIN_VALID_EVALUATION_RATIO = 0.95


class ShadowBlockingFault(StrEnum):
    """Stable current fault categories that block Shadow readiness."""

    CONFIGURATION = "configuration"
    TIME_ZONE = "time_zone"
    THERMOSTAT_UNAVAILABLE = "thermostat_unavailable"
    CAPABILITY = "capability"
    SENSOR = "sensor"
    CORRELATION = "correlation"
    COMMAND_FAILURE = "command_failure"
    SHARED_CONFLICT = "shared_conflict"
    PERSISTENCE = "persistence"
    SAFETY_EVALUATION = "safety_evaluation"


class ShadowHistoryOutcome(StrEnum):
    """Bounded result of one evaluated Shadow candidate."""

    WOULD_COMMAND = "would_command"
    SUPPRESSED = "suppressed"
    BLOCKED = "blocked"


class ShadowReadinessReason(StrEnum):
    """Stable unmet qualification requirement."""

    NOT_STARTED = "not_started"
    DURATION = "duration"
    DECISION_COUNT = "decision_count"
    VALID_RATIO = "valid_ratio"
    MATERIAL_TRANSITIONS = "material_transitions"
    BLOCKING_FAULT = "blocking_fault"


@dataclass(frozen=True, slots=True)
class ShadowWouldCommand:
    """Privacy-bounded exact projection of one validated command plan."""

    command_id: CommandId
    decision_id: DecisionId
    command_kind: CommandKind
    desired_fields: tuple[CommandControlledField, ...]
    desired: NormalizedCommandValues
    authority: CommandAuthority
    cause: CommandCause
    dedupe_fingerprint: str


@dataclass(frozen=True, slots=True)
class ShadowHistoryRecord:
    """One chronological Shadow evaluation with no target or user identity."""

    safety_evaluation_id: SafetyEvaluationId
    evaluated_at_utc: datetime
    outcome: ShadowHistoryOutcome
    safety_disposition: SafetyDisposition
    reason_code: SafetyReasonCode
    hard_checks_passed: bool
    would_command: ShadowWouldCommand | None


@dataclass(frozen=True, slots=True)
class ShadowReadinessEntitySnapshot:
    """Canonical values for the later readiness sensor and binary sensor."""

    ready: bool
    qualification_percent: float
    valid_evaluation_percent: float
    elapsed_hours: float
    evaluated_decisions: int
    valid_evaluations: int
    minimum_material_transitions: int
    blocking_reasons: tuple[ShadowReadinessReason, ...]
    blocking_faults: tuple[ShadowBlockingFault, ...]


@dataclass(frozen=True, slots=True)
class ShadowSinkSnapshot:
    """Complete inert result after one Shadow evaluation."""

    record: ShadowHistoryRecord
    readiness: ShadowReadinessEntitySnapshot
