"""Strict backend DTOs for the versioned Phase 2 frontend API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite

from .identifiers import ZoneId

FRONTEND_API_VERSION = 1


class TimelineValueKind(StrEnum):
    """Truthful provenance attached to every timeline series."""

    MEASURED = "measured"
    CONFIGURED = "configured"
    CALCULATED = "calculated"
    FORECAST = "forecast"
    PREDICTED = "predicted"
    PLANNED = "planned"


class TimelineSeriesKind(StrEnum):
    """Allowlisted factual Phase 2 series."""

    EFFECTIVE_TEMPERATURE = "effective_temperature"
    EFFECTIVE_HUMIDITY = "effective_humidity"
    OUTDOOR_TEMPERATURE = "outdoor_temperature"
    SCHEDULED_TARGET = "scheduled_target"
    SCHEDULED_HEAT_TARGET = "scheduled_heat_target"
    SCHEDULED_COOL_TARGET = "scheduled_cool_target"
    EFFECTIVE_TARGET = "effective_target"
    EFFECTIVE_HEAT_TARGET = "effective_heat_target"
    EFFECTIVE_COOL_TARGET = "effective_cool_target"
    HVAC_ACTION = "hvac_action"
    FAN_ACTION = "fan_action"
    CONTACT_STATE = "contact_state"
    CONTROL_CONTEXT = "control_context"


@dataclass(frozen=True, slots=True)
class TimelineSample:
    """One UTC sample; unavailable values are omitted, never represented as zero."""

    timestamp_utc: datetime
    value: float | str

    def __post_init__(self) -> None:
        _utc(self.timestamp_utc, "sample timestamp")
        if isinstance(self.value, bool) or not isinstance(
            self.value, float | int | str
        ):
            raise ValueError("timeline sample value must be finite numeric or text")
        if isinstance(self.value, float | int) and not isfinite(self.value):
            raise ValueError("timeline sample numeric value must be finite")
        if isinstance(self.value, str) and not self.value:
            raise ValueError("timeline sample text must not be empty")


@dataclass(frozen=True, slots=True)
class TimelineMissingInterval:
    """One explicit gap rather than an invented zero-valued span."""

    start_utc: datetime
    end_utc: datetime

    def __post_init__(self) -> None:
        _utc(self.start_utc, "missing interval start")
        _utc(self.end_utc, "missing interval end")
        if self.end_utc <= self.start_utc:
            raise ValueError("missing interval must have positive duration")


@dataclass(frozen=True, slots=True)
class TimelineSeries:
    """Canonical provenance-labeled series returned by the backend."""

    kind: TimelineSeriesKind
    value_kind: TimelineValueKind
    unit: str | None
    source_quality: str
    coverage_start_utc: datetime | None
    coverage_end_utc: datetime | None
    missing_intervals: tuple[TimelineMissingInterval, ...]
    samples: tuple[TimelineSample, ...]

    def __post_init__(self) -> None:
        if self.value_kind in {
            TimelineValueKind.PREDICTED,
            TimelineValueKind.PLANNED,
        }:
            raise ValueError("Phase 2 cannot expose predicted or planned series")
        if not self.source_quality:
            raise ValueError("source_quality must not be empty")
        if not self.samples:
            raise ValueError("empty timeline series must be omitted")
        if self.coverage_start_utc is None or self.coverage_end_utc is None:
            raise ValueError("nonempty series requires explicit coverage")
        if self.coverage_start_utc > self.coverage_end_utc:
            raise ValueError("timeline coverage is reversed")


@dataclass(frozen=True, slots=True)
class TimelineAnnotation:
    """Typed timeline annotation linked to one material activity record."""

    annotation_id: str
    timestamp_utc: datetime
    reason_code: str
    activity_record_id: str


@dataclass(frozen=True, slots=True)
class TodayTimeline:
    """Canonical local-day DTO with actual 23/24/25-hour boundaries."""

    api_version: int
    entry_id: str
    zone_id: ZoneId
    time_zone: str
    local_date: str
    day_start_utc: datetime
    day_end_utc: datetime
    generated_at_utc: datetime
    series: tuple[TimelineSeries, ...]
    annotations: tuple[TimelineAnnotation, ...]
    indoor_prediction_available: bool = False
    capability_statement: str = "No indoor prediction in Safe Scheduled Control"

    def __post_init__(self) -> None:
        if self.api_version != FRONTEND_API_VERSION:
            raise ValueError("unsupported frontend API version")
        if self.day_end_utc <= self.day_start_utc:
            raise ValueError("local day boundaries are reversed")
        duration = (self.day_end_utc - self.day_start_utc).total_seconds() / 3600
        if duration not in {23.0, 24.0, 25.0}:
            raise ValueError("local day must be 23, 24, or 25 hours")
        if self.indoor_prediction_available:
            raise ValueError("Phase 2 has no indoor prediction")


@dataclass(frozen=True, slots=True)
class CurrentNarrativeFacts:
    """Validated facts permitted in the deterministic current explanation."""

    api_version: int
    entry_id: str
    zone_id: ZoneId
    control_state: str
    reason_code: str
    temperature_c: float | None
    hvac_action: str | None
    scheduled_target_c: float | None
    effective_target_c: float | None
    next_transition_utc: datetime | None
    source_degraded: bool
    context_forecast_available: bool
    included_categories: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.api_version != FRONTEND_API_VERSION:
            raise ValueError("unsupported narrative API version")
        if any(
            value is not None and not isfinite(value)
            for value in (
                self.temperature_c,
                self.scheduled_target_c,
                self.effective_target_c,
            )
        ):
            raise ValueError("narrative temperatures must be finite")
        if len(set(self.included_categories)) != len(self.included_categories):
            raise ValueError("narrative categories must be unique")


def _utc(value: datetime, field: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
