"""Immutable source-observation models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .identifiers import ObservationSourceId


class SourceQuality(StrEnum):
    """Approved Phase 1 source-quality codes."""

    VALID = "valid"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    NON_NUMERIC = "non_numeric"
    NON_FINITE = "non_finite"
    UNIT_UNSUPPORTED = "unit_unsupported"
    IMPLAUSIBLE = "implausible"
    STALE = "stale"
    RESTORED_NOT_CONFIRMED = "restored_not_confirmed"
    JUMP_REJECTED = "jump_rejected"
    OUTLIER = "outlier"
    CONTRADICTORY = "contradictory"


class ExclusionReason(StrEnum):
    """Stable reasons why a source value was excluded."""

    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"
    NON_NUMERIC = "non_numeric"
    NON_FINITE = "non_finite"
    UNIT_UNSUPPORTED = "unit_unsupported"
    IMPLAUSIBLE = "implausible"
    STALE = "stale"
    RESTORED_NOT_CONFIRMED = "restored_not_confirmed"
    JUMP_REJECTED = "jump_rejected"
    OUTLIER = "outlier"
    CONTRADICTORY = "contradictory"


@dataclass(frozen=True, slots=True)
class SourceObservation[T]:
    """One raw source value and its Task 7 normalization result."""

    source_id: ObservationSourceId
    raw_value: object
    normalized_value: T | None
    observed_at: datetime
    source_last_updated: datetime | None
    quality: SourceQuality
    exclusion_reason: ExclusionReason | None
    restored: bool
