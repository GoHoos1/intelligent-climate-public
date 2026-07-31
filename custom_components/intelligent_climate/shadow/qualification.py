"""Pure restart-safe Shadow qualification calculations."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from types import MappingProxyType

from ..models.identifiers import ZoneId
from ..models.phase2_schema import Phase2ShadowQualification
from ..models.schema import SchemaValidationError
from ..models.shadow import (
    MIN_SHADOW_DECISIONS,
    MIN_SHADOW_HOURS,
    MIN_SHADOW_TRANSITIONS_PER_ZONE,
    MIN_VALID_EVALUATION_RATIO,
    ShadowBlockingFault,
    ShadowReadinessEntitySnapshot,
    ShadowReadinessReason,
)


def empty_shadow_qualification(
    zone_ids: tuple[ZoneId, ...],
) -> Phase2ShadowQualification:
    """Create the canonical not-started qualification for all runtime zones."""
    zones = _zone_ids(zone_ids, "zone_ids")
    return Phase2ShadowQualification(
        started_at_utc=None,
        evaluated_decisions=0,
        valid_evaluations=0,
        material_transitions_by_zone=MappingProxyType(dict.fromkeys(zones, 0)),
        blocking_fault_codes=(),
    )


def reset_shadow_qualification(
    state: Phase2ShadowQualification,
    *,
    all_zone_ids: tuple[ZoneId, ...],
) -> Phase2ShadowQualification:
    """Reset continuity after mode, time-zone, ownership, or config change."""
    validate_shadow_qualification(state, all_zone_ids=all_zone_ids)
    return empty_shadow_qualification(all_zone_ids)


def record_shadow_evaluation(
    state: Phase2ShadowQualification,
    *,
    all_zone_ids: tuple[ZoneId, ...],
    evaluated_at_utc: datetime,
    valid: bool,
    material_transition_zone_id: ZoneId | None,
    active_faults: tuple[ShadowBlockingFault, ...],
) -> Phase2ShadowQualification:
    """Return the next qualification state using only caller-supplied facts."""
    validate_shadow_qualification(state, all_zone_ids=all_zone_ids)
    evaluated_at = _utc(evaluated_at_utc, "evaluated_at_utc")
    if type(valid) is not bool:
        raise SchemaValidationError("valid", "must be a boolean")
    faults = _faults(active_faults)
    if not valid and ShadowBlockingFault.SAFETY_EVALUATION not in faults:
        faults = tuple(sorted((*faults, ShadowBlockingFault.SAFETY_EVALUATION)))
    started_at = state.started_at_utc or evaluated_at
    if evaluated_at < started_at:
        raise SchemaValidationError(
            "evaluated_at_utc", "must not precede qualification start"
        )
    transitions = dict(state.material_transitions_by_zone)
    if material_transition_zone_id is not None:
        if material_transition_zone_id not in transitions:
            raise SchemaValidationError(
                "material_transition_zone_id", "must reference a runtime zone"
            )
        transitions[material_transition_zone_id] += 1
    result = Phase2ShadowQualification(
        started_at_utc=started_at,
        evaluated_decisions=state.evaluated_decisions + 1,
        valid_evaluations=state.valid_evaluations + int(valid),
        material_transitions_by_zone=MappingProxyType(transitions),
        blocking_fault_codes=tuple(fault.value for fault in faults),
    )
    validate_shadow_qualification(result, all_zone_ids=all_zone_ids)
    return result


def evaluate_shadow_readiness(
    state: Phase2ShadowQualification,
    *,
    all_zone_ids: tuple[ZoneId, ...],
    enabled_zone_ids: tuple[ZoneId, ...],
    now_utc: datetime,
) -> ShadowReadinessEntitySnapshot:
    """Calculate exact-boundary readiness and canonical entity values."""
    validate_shadow_qualification(state, all_zone_ids=all_zone_ids)
    now = _utc(now_utc, "now_utc")
    enabled = _zone_ids(enabled_zone_ids, "enabled_zone_ids")
    if not enabled or not set(enabled) <= set(all_zone_ids):
        raise SchemaValidationError(
            "enabled_zone_ids", "must be a nonempty subset of runtime zones"
        )
    started = state.started_at_utc
    if started is not None and started > now:
        raise SchemaValidationError("now_utc", "must not precede qualification start")
    elapsed_hours = 0.0 if started is None else (now - started).total_seconds() / 3600.0
    valid_ratio = (
        0.0
        if state.evaluated_decisions == 0
        else state.valid_evaluations / state.evaluated_decisions
    )
    minimum_transitions = min(
        state.material_transitions_by_zone[zone_id] for zone_id in enabled
    )
    faults = _stored_faults(state.blocking_fault_codes)
    reasons: list[ShadowReadinessReason] = []
    if started is None:
        reasons.append(ShadowReadinessReason.NOT_STARTED)
    if elapsed_hours < MIN_SHADOW_HOURS:
        reasons.append(ShadowReadinessReason.DURATION)
    if state.evaluated_decisions < MIN_SHADOW_DECISIONS:
        reasons.append(ShadowReadinessReason.DECISION_COUNT)
    if valid_ratio < MIN_VALID_EVALUATION_RATIO:
        reasons.append(ShadowReadinessReason.VALID_RATIO)
    if minimum_transitions < MIN_SHADOW_TRANSITIONS_PER_ZONE:
        reasons.append(ShadowReadinessReason.MATERIAL_TRANSITIONS)
    if faults:
        reasons.append(ShadowReadinessReason.BLOCKING_FAULT)
    progress = (
        min(elapsed_hours / MIN_SHADOW_HOURS, 1.0),
        min(state.evaluated_decisions / MIN_SHADOW_DECISIONS, 1.0),
        min(valid_ratio / MIN_VALID_EVALUATION_RATIO, 1.0),
        min(minimum_transitions / MIN_SHADOW_TRANSITIONS_PER_ZONE, 1.0),
        0.0 if faults else 1.0,
    )
    ready = not reasons
    qualification_percent = round(min(progress) * 100.0, 1)
    if not ready:
        qualification_percent = min(qualification_percent, 99.9)
    return ShadowReadinessEntitySnapshot(
        ready=ready,
        qualification_percent=qualification_percent,
        valid_evaluation_percent=round(valid_ratio * 100.0, 1),
        elapsed_hours=round(elapsed_hours, 3),
        evaluated_decisions=state.evaluated_decisions,
        valid_evaluations=state.valid_evaluations,
        minimum_material_transitions=minimum_transitions,
        blocking_reasons=tuple(reasons),
        blocking_faults=faults,
    )


def validate_shadow_qualification(
    state: Phase2ShadowQualification,
    *,
    all_zone_ids: tuple[ZoneId, ...],
) -> None:
    """Strictly validate the pre-authorized Runtime Store v2 slot."""
    if not isinstance(state, Phase2ShadowQualification):
        raise SchemaValidationError(
            "shadow_qualification", "must be a qualification record"
        )
    zones = _zone_ids(all_zone_ids, "all_zone_ids")
    if set(state.material_transitions_by_zone) != set(zones):
        raise SchemaValidationError(
            "material_transitions_by_zone", "must contain every runtime zone"
        )
    values: Iterable[object] = (
        state.evaluated_decisions,
        state.valid_evaluations,
        *state.material_transitions_by_zone.values(),
    )
    if any(type(value) is not int or value < 0 for value in values):
        raise SchemaValidationError(
            "shadow_qualification", "counts must be nonnegative"
        )
    if state.valid_evaluations > state.evaluated_decisions:
        raise SchemaValidationError(
            "valid_evaluations", "cannot exceed evaluated decisions"
        )
    if state.started_at_utc is not None:
        _utc(state.started_at_utc, "started_at_utc")
    faults = _stored_faults(state.blocking_fault_codes)
    if faults != tuple(sorted(set(faults))):
        raise SchemaValidationError(
            "blocking_fault_codes", "must be unique and canonically ordered"
        )


def _zone_ids(value: object, path: str) -> tuple[ZoneId, ...]:
    if not isinstance(value, tuple) or any(
        not isinstance(item, ZoneId) for item in value
    ):
        raise SchemaValidationError(path, "must be an immutable zone-ID sequence")
    if len(value) != len(set(value)):
        raise SchemaValidationError(path, "must not contain duplicates")
    return value


def _faults(value: object) -> tuple[ShadowBlockingFault, ...]:
    if not isinstance(value, tuple) or any(
        not isinstance(item, ShadowBlockingFault) for item in value
    ):
        raise SchemaValidationError("active_faults", "must contain supported faults")
    return tuple(sorted(set(value)))


def _stored_faults(value: object) -> tuple[ShadowBlockingFault, ...]:
    if not isinstance(value, tuple):
        raise SchemaValidationError(
            "blocking_fault_codes", "must be an immutable fault sequence"
        )
    try:
        return tuple(ShadowBlockingFault(code) for code in value)
    except (TypeError, ValueError) as err:
        raise SchemaValidationError(
            "blocking_fault_codes", "contains an unsupported fault"
        ) from err


def _utc(value: object, path: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None:
        raise SchemaValidationError(path, "must be timezone-aware")
    if value.utcoffset() != UTC.utcoffset(value):
        raise SchemaValidationError(path, "must use UTC")
    return value
