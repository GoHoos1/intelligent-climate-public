"""Canonical factual Today timeline projection for Phase 2."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, time, timedelta
from itertools import pairwise
from zoneinfo import ZoneInfo

from .models.frontend import (
    FRONTEND_API_VERSION,
    TimelineAnnotation,
    TimelineMissingInterval,
    TimelineSample,
    TimelineSeries,
    TimelineSeriesKind,
    TimelineValueKind,
    TodayTimeline,
)
from .models.identifiers import ZoneId
from .models.presentation import PresentationTraceDocument, PresentationTracePoint
from .models.schedule import TargetKind

_MISSING_AFTER = timedelta(minutes=10)

type PointValue = Callable[[PresentationTracePoint], float | str | None]


def build_today_timeline(
    document: PresentationTraceDocument,
    *,
    zone_id: ZoneId,
    time_zone: str,
    local_date: date,
    generated_at_utc: datetime,
) -> TodayTimeline:
    """Build one local calendar day without interpolation or causal inference."""
    zone = ZoneInfo(time_zone)
    start_local = datetime.combine(local_date, time.min, tzinfo=zone)
    end_local = datetime.combine(local_date + timedelta(days=1), time.min, tzinfo=zone)
    start = start_local.astimezone(UTC)
    end = end_local.astimezone(UTC)
    points = tuple(
        item
        for item in document.samples_by_zone.get(zone_id, ())
        if start <= item.timestamp_utc < end
    )
    definitions: tuple[
        tuple[TimelineSeriesKind, TimelineValueKind, str | None, PointValue], ...
    ] = (
        (
            TimelineSeriesKind.EFFECTIVE_TEMPERATURE,
            TimelineValueKind.MEASURED,
            "°C",
            lambda item: item.effective_temperature_c,
        ),
        (
            TimelineSeriesKind.EFFECTIVE_HUMIDITY,
            TimelineValueKind.MEASURED,
            "%",
            lambda item: item.effective_humidity_pct,
        ),
        (
            TimelineSeriesKind.OUTDOOR_TEMPERATURE,
            TimelineValueKind.MEASURED,
            "°C",
            lambda item: item.outdoor_temperature_c,
        ),
        (
            TimelineSeriesKind.SCHEDULED_TARGET,
            TimelineValueKind.CONFIGURED,
            "°C",
            lambda item: _target_value(item, scheduled=True, endpoint="single"),
        ),
        (
            TimelineSeriesKind.SCHEDULED_HEAT_TARGET,
            TimelineValueKind.CONFIGURED,
            "°C",
            lambda item: _target_value(item, scheduled=True, endpoint="heat"),
        ),
        (
            TimelineSeriesKind.SCHEDULED_COOL_TARGET,
            TimelineValueKind.CONFIGURED,
            "°C",
            lambda item: _target_value(item, scheduled=True, endpoint="cool"),
        ),
        (
            TimelineSeriesKind.EFFECTIVE_TARGET,
            TimelineValueKind.CALCULATED,
            "°C",
            lambda item: _target_value(item, scheduled=False, endpoint="single"),
        ),
        (
            TimelineSeriesKind.EFFECTIVE_HEAT_TARGET,
            TimelineValueKind.CALCULATED,
            "°C",
            lambda item: _target_value(item, scheduled=False, endpoint="heat"),
        ),
        (
            TimelineSeriesKind.EFFECTIVE_COOL_TARGET,
            TimelineValueKind.CALCULATED,
            "°C",
            lambda item: _target_value(item, scheduled=False, endpoint="cool"),
        ),
        (
            TimelineSeriesKind.HVAC_ACTION,
            TimelineValueKind.MEASURED,
            None,
            lambda item: item.hvac_action.value,
        ),
        (
            TimelineSeriesKind.FAN_ACTION,
            TimelineValueKind.MEASURED,
            None,
            lambda item: item.fan_action.value,
        ),
        (
            TimelineSeriesKind.CONTACT_STATE,
            TimelineValueKind.MEASURED,
            None,
            lambda item: item.contact_state.value,
        ),
        (
            TimelineSeriesKind.CONTROL_CONTEXT,
            TimelineValueKind.CALCULATED,
            None,
            lambda item: item.control_context.value,
        ),
    )
    series = tuple(
        result
        for kind, value_kind, unit, extractor in definitions
        if (
            result := _build_series(
                points,
                kind=kind,
                value_kind=value_kind,
                unit=unit,
                extractor=extractor,
            )
        )
        is not None
    )
    annotations = tuple(
        TimelineAnnotation(
            annotation_id=str(item.annotation_id),
            timestamp_utc=item.timestamp_utc,
            reason_code=item.kind.value,
            activity_record_id=str(item.activity_record_id),
        )
        for item in document.annotations
        if item.zone_id == zone_id and start <= item.timestamp_utc < end
    )
    return TodayTimeline(
        api_version=FRONTEND_API_VERSION,
        entry_id=document.entry_id,
        zone_id=zone_id,
        time_zone=time_zone,
        local_date=local_date.isoformat(),
        day_start_utc=start,
        day_end_utc=end,
        generated_at_utc=_utc(generated_at_utc),
        series=series,
        annotations=annotations,
    )


def timeline_to_json(value: TodayTimeline) -> dict[str, object]:
    """Encode the typed DTO without exposing Python objects to the frontend."""
    return {
        "api_version": value.api_version,
        "entry_id": value.entry_id,
        "zone_id": str(value.zone_id),
        "time_zone": value.time_zone,
        "local_date": value.local_date,
        "day_start_utc": value.day_start_utc.isoformat(),
        "day_end_utc": value.day_end_utc.isoformat(),
        "generated_at_utc": value.generated_at_utc.isoformat(),
        "indoor_prediction_available": value.indoor_prediction_available,
        "capability_statement": value.capability_statement,
        "series": [
            {
                "kind": item.kind.value,
                "value_kind": item.value_kind.value,
                "unit": item.unit,
                "source_quality": item.source_quality,
                "coverage_start_utc": _coverage_timestamp(item, start=True),
                "coverage_end_utc": _coverage_timestamp(item, start=False),
                "missing_intervals": [
                    {
                        "start_utc": interval.start_utc.isoformat(),
                        "end_utc": interval.end_utc.isoformat(),
                    }
                    for interval in item.missing_intervals
                ],
                "samples": [
                    {
                        "timestamp_utc": sample.timestamp_utc.isoformat(),
                        "value": sample.value,
                    }
                    for sample in item.samples
                ],
            }
            for item in value.series
        ],
        "annotations": [
            {
                "annotation_id": item.annotation_id,
                "timestamp_utc": item.timestamp_utc.isoformat(),
                "reason_code": item.reason_code,
                "activity_record_id": item.activity_record_id,
            }
            for item in value.annotations
        ],
    }


def _build_series(
    points: tuple[PresentationTracePoint, ...],
    *,
    kind: TimelineSeriesKind,
    value_kind: TimelineValueKind,
    unit: str | None,
    extractor: PointValue,
) -> TimelineSeries | None:
    samples = tuple(
        TimelineSample(item.timestamp_utc, value)
        for item in points
        if (value := extractor(item)) is not None
    )
    if not samples:
        return None
    missing = tuple(
        TimelineMissingInterval(previous.timestamp_utc, current.timestamp_utc)
        for previous, current in pairwise(samples)
        if current.timestamp_utc - previous.timestamp_utc > _MISSING_AFTER
    )
    return TimelineSeries(
        kind=kind,
        value_kind=value_kind,
        unit=unit,
        source_quality="available",
        coverage_start_utc=samples[0].timestamp_utc,
        coverage_end_utc=samples[-1].timestamp_utc,
        missing_intervals=missing,
        samples=samples,
    )


def _target_value(
    point: PresentationTracePoint,
    *,
    scheduled: bool,
    endpoint: str,
) -> float | None:
    target = point.scheduled_target if scheduled else point.effective_target
    if target is None:
        return None
    if endpoint == "single":
        return target.target_c if target.kind is TargetKind.SINGLE else None
    if target.kind is not TargetKind.RANGE:
        return None
    return target.heat_target_c if endpoint == "heat" else target.cool_target_c


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timeline generated_at must be timezone-aware")
    return value.astimezone(UTC)


def _coverage_timestamp(value: TimelineSeries, *, start: bool) -> str:
    """Encode coverage after the DTO has enforced non-null boundaries."""
    timestamp = value.coverage_start_utc if start else value.coverage_end_utc
    if timestamp is None:  # pragma: no cover - guarded by TimelineSeries
        raise ValueError("timeline series coverage is missing")
    return timestamp.isoformat()
