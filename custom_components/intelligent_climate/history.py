"""Bounded, entry-scoped material activity history."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import datetime, timedelta

from .models import ActivityRecord, ZoneId

type ActivityListener = Callable[[ActivityRecord], None]

_HARD_MAX_RECORDS = 500


class ActivityHistory:
    """Store validated activity oldest-to-newest with strict age/count bounds."""

    __slots__ = (
        "_listeners",
        "_max_age",
        "_max_records",
        "_record_ids",
        "_records",
    )

    def __init__(self, *, max_records: int, max_age_days: int) -> None:
        """Initialize configured bounds, including the hard 500-record cap."""
        if (
            not isinstance(max_records, int)
            or isinstance(max_records, bool)
            or max_records < 1
        ):
            raise ValueError("history max_records must be a positive integer")
        if (
            not isinstance(max_age_days, int)
            or isinstance(max_age_days, bool)
            or max_age_days < 1
        ):
            raise ValueError("history max_age_days must be a positive integer")
        self._max_records = min(max_records, _HARD_MAX_RECORDS)
        self._max_age = timedelta(days=max_age_days)
        self._records: tuple[ActivityRecord, ...] = ()
        self._record_ids: set[object] = set()
        self._listeners: list[ActivityListener] = []

    @property
    def records(self) -> tuple[ActivityRecord, ...]:
        """Return immutable history in oldest-to-newest order."""
        return self._records

    @property
    def latest(self) -> ActivityRecord | None:
        """Return the newest activity across the entry."""
        return None if not self._records else self._records[-1]

    def latest_for_zone(self, zone_id: ZoneId) -> ActivityRecord | None:
        """Return the newest activity scoped to one zone."""
        return next(
            (record for record in reversed(self._records) if record.zone_id == zone_id),
            None,
        )

    @property
    def max_records(self) -> int:
        """Return the effective configured count bound."""
        return self._max_records

    @property
    def max_age_days(self) -> int:
        """Return the configured integral age bound."""
        return self._max_age.days

    def restore(
        self,
        records: Iterable[ActivityRecord],
        *,
        now: datetime,
    ) -> None:
        """Sort, deduplicate, and prune validated loaded records silently."""
        _require_aware(now)
        ordered = sorted(
            records,
            key=lambda item: (
                item.timestamp,
                item.record_id.hex,
                item.activity_type.value,
                item.reason_code.value,
                item.explanation,
            ),
        )
        deduplicated: list[ActivityRecord] = []
        seen: set[object] = set()
        for record in ordered:
            if record.record_id in seen:
                continue
            seen.add(record.record_id)
            deduplicated.append(record)
        self._replace(self._bounded(tuple(deduplicated), now))

    def add(self, record: ActivityRecord, *, now: datetime | None = None) -> bool:
        """Accept and notify one new record, rejecting duplicate IDs."""
        reference = record.timestamp if now is None else now
        _require_aware(reference)
        if record.record_id in self._record_ids:
            return False
        bounded = self._bounded((*self._records, record), reference)
        if all(item.record_id != record.record_id for item in bounded):
            return False
        self._replace(bounded)
        for listener in tuple(self._listeners):
            listener(record)
        return True

    def prune(self, *, now: datetime) -> None:
        """Apply the configured bounds without publishing activity."""
        _require_aware(now)
        self._replace(self._bounded(self._records, now))

    def bounded_records(self, *, now: datetime) -> tuple[ActivityRecord, ...]:
        """Return a current pruned view without mutating history."""
        _require_aware(now)
        return self._bounded(self._records, now)

    def async_add_listener(self, listener: ActivityListener) -> Callable[[], None]:
        """Register a synchronous event-loop listener and return cleanup."""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            if listener in self._listeners:
                self._listeners.remove(listener)

        return unsubscribe

    @property
    def listener_count(self) -> int:
        """Return the owned listener count for lifecycle verification."""
        return len(self._listeners)

    def _bounded(
        self,
        records: tuple[ActivityRecord, ...],
        now: datetime,
    ) -> tuple[ActivityRecord, ...]:
        cutoff = now - self._max_age
        retained = tuple(record for record in records if record.timestamp >= cutoff)
        ordered = tuple(
            sorted(retained, key=lambda item: (item.timestamp, item.record_id.hex))
        )
        return ordered[-self._max_records :]

    def _replace(self, records: tuple[ActivityRecord, ...]) -> None:
        self._records = records
        self._record_ids = {record.record_id for record in records}


def _require_aware(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("history cutoff timestamp must be timezone-aware")
