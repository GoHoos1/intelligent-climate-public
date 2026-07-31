"""Pure local-wall-time resolution for weekly schedule boundaries."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..models.schedule import LocalTime

_MAX_GAP_SEARCH = timedelta(days=3)
_ONE_MINUTE = timedelta(minutes=1)


def normalize_aware_instant(value: datetime) -> datetime:
    """Return an aware instant in UTC and reject naive datetimes."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("evaluation instant must be timezone-aware")
    return value.astimezone(UTC)


def resolve_local_boundary(
    local_date: date,
    local_time: LocalTime,
    *,
    time_zone: str,
) -> datetime:
    """Resolve one local boundary using the approved gap/fold policy.

    Ambiguous times use their first occurrence. Nonexistent times advance to
    the first valid local minute after the gap.
    """
    try:
        zone = ZoneInfo(time_zone)
    except (ValueError, ZoneInfoNotFoundError) as err:
        raise ValueError("schedule time zone is invalid") from err

    nominal = datetime(
        local_date.year,
        local_date.month,
        local_date.day,
        local_time.hour,
        local_time.minute,
    )
    resolved = _first_valid_occurrence(nominal, zone)
    if resolved is not None:
        return resolved.astimezone(UTC)

    limit = nominal + _MAX_GAP_SEARCH
    candidate = nominal + _ONE_MINUTE
    while candidate <= limit:
        resolved = _first_valid_occurrence(candidate, zone)
        if resolved is not None:
            return resolved.astimezone(UTC)
        candidate += _ONE_MINUTE
    raise ValueError("local schedule boundary cannot be resolved")


def _first_valid_occurrence(
    nominal: datetime,
    zone: ZoneInfo,
) -> datetime | None:
    """Return fold zero when a local minute round-trips, otherwise none."""
    candidate = nominal.replace(tzinfo=zone, fold=0)
    round_trip = candidate.astimezone(UTC).astimezone(zone)
    if round_trip.replace(tzinfo=None) == nominal and round_trip.fold == 0:
        return candidate
    return None
