"""Immutable source-aggregation result models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from .identifiers import ObservationSourceId
from .observation import SourceObservation


class AggregationStatus(StrEnum):
    """Availability and quality of one calculated effective value."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class AggregationReason(StrEnum):
    """Stable reasons for degraded or unavailable aggregation."""

    SOURCE_EXCLUDED = "source_excluded"
    OUTLIER_EXCLUDED = "outlier_excluded"
    TWO_SOURCE_CONTRADICTION = "two_source_contradiction"
    BELOW_MINIMUM_VALID_SOURCES = "below_minimum_valid_sources"
    NO_ENABLED_SOURCES = "no_enabled_sources"
    NO_VALID_SOURCES = "no_valid_sources"
    PRIORITY_NOT_CONFIGURED = "priority_not_configured"
    PRIORITY_AMBIGUOUS = "priority_ambiguous"
    PRIORITY_FALLBACK = "priority_fallback"


@dataclass(frozen=True, slots=True)
class SourceAggregationResult:
    """One deterministic effective-value calculation and its source accounting."""

    effective_value: float | None
    spread: float | None
    valid_source_ids: tuple[ObservationSourceId, ...]
    contributing_source_ids: tuple[ObservationSourceId, ...]
    fallback_source_id: ObservationSourceId | None
    excluded_observations: tuple[SourceObservation[float], ...]
    status: AggregationStatus
    reasons: tuple[AggregationReason, ...]
    calculated_at: datetime
