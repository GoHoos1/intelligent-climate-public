"""Authoritative, revisioned persistence for validated weekly schedules."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import UnsupportedStorageVersionError
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .models import (
    SCHEDULE_SCHEMA_VERSION,
    ScheduleDocument,
    ScheduleValidationContext,
    SchemaMigrationError,
    SchemaValidationError,
    decode_schedule_document,
    encode_schedule_document,
    validate_schedule_document,
)

_LOGGER = logging.getLogger(__name__)

SCHEDULE_STORE_VERSION = 1
SCHEDULE_STORE_MINOR_VERSION = 0
_QUARANTINE_SUFFIX = ".quarantine"
_INVALID_STORE_REASON = "invalid_authoritative_schedule_store"

type NowFunction = Callable[[], datetime]


class ScheduleStoreLoadStatus(StrEnum):
    """Bounded result of loading the authoritative Schedule Store."""

    NOT_LOADED = "not_loaded"
    MISSING = "missing"
    LOADED = "loaded"
    QUARANTINED = "quarantined"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ScheduleStoreLoadResult:
    """Immutable Schedule Store load/recovery result."""

    status: ScheduleStoreLoadStatus
    document: ScheduleDocument | None
    read_only: bool
    quarantine_present: bool


class ScheduleStoreError(RuntimeError):
    """Base error for authoritative Schedule Store operations."""


class ScheduleStoreNotLoadedError(ScheduleStoreError):
    """Raised when a save is attempted before the Store is loaded."""


class ScheduleStoreReadOnlyError(ScheduleStoreError):
    """Raised when preserved data makes the Store unsafe to overwrite."""


class ScheduleRevisionConflictError(ScheduleStoreError):
    """Raised when a caller edits a revision that is no longer current."""

    def __init__(self, *, expected_revision: int, actual_revision: int) -> None:
        """Initialize a conflict without exposing persisted schedule contents."""
        self.expected_revision = expected_revision
        self.actual_revision = actual_revision
        super().__init__(
            "schedule revision conflict: "
            f"expected {expected_revision}, current revision is {actual_revision}"
        )


class ScheduleStoreWriteError(ScheduleStoreError):
    """Raised when an atomic write cannot be verified as durable."""


class _ScheduleDataStore(Store[dict[str, Any]]):
    """Home Assistant Store envelope for authoritative schedule schema v1."""

    def __init__(self, hass: HomeAssistant, key: str) -> None:
        super().__init__(
            hass,
            SCHEDULE_STORE_VERSION,
            key,
            atomic_writes=True,
            max_readable_version=SCHEDULE_STORE_VERSION,
            minor_version=SCHEDULE_STORE_MINOR_VERSION,
        )


class ScheduleStore:
    """Own one config entry's canonical schedule document and persistence."""

    __slots__ = (
        "_document",
        "_entry_id",
        "_hass",
        "_load_status",
        "_loaded",
        "_lock",
        "_now_fn",
        "_quarantine_present",
        "_quarantine_store",
        "_read_only",
        "_store",
        "_validation_context",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry_id: str,
        validation_context: ScheduleValidationContext,
        now_fn: NowFunction = utcnow,
    ) -> None:
        """Initialize an unwired authoritative Schedule Store."""
        if validation_context.entry_id != entry_id:
            raise ValueError("validation context entry_id must match entry_id")
        self._hass = hass
        self._entry_id = entry_id
        self._validation_context = validation_context
        self._now_fn = now_fn
        key = f"intelligent_climate.schedule.{entry_id}"
        self._store = _ScheduleDataStore(hass, key)
        self._quarantine_store: Store[dict[str, Any]] = Store(
            hass,
            SCHEDULE_STORE_VERSION,
            f"{key}{_QUARANTINE_SUFFIX}",
            atomic_writes=True,
        )
        self._lock = asyncio.Lock()
        self._loaded = False
        self._load_status = ScheduleStoreLoadStatus.NOT_LOADED
        self._read_only = False
        self._quarantine_present = False
        self._document: ScheduleDocument | None = None

    @property
    def key(self) -> str:
        """Return the exact Home Assistant Store key."""
        return self._store.key

    @property
    def version(self) -> int:
        """Return the Schedule Store envelope major version."""
        return SCHEDULE_STORE_VERSION

    @property
    def minor_version(self) -> int:
        """Return the Schedule Store envelope minor version."""
        return SCHEDULE_STORE_MINOR_VERSION

    @property
    def loaded(self) -> bool:
        """Return whether the bounded load/recovery attempt completed."""
        return self._loaded

    @property
    def load_status(self) -> ScheduleStoreLoadStatus:
        """Return the bounded load/recovery result."""
        return self._load_status

    @property
    def read_only(self) -> bool:
        """Return whether destructive schedule writes are suppressed."""
        return self._read_only

    @property
    def quarantine_present(self) -> bool:
        """Return whether invalid authoritative data remains quarantined."""
        return self._quarantine_present

    @property
    def document(self) -> ScheduleDocument | None:
        """Return the last successfully loaded or saved canonical document."""
        return self._document

    @property
    def revision(self) -> int:
        """Return the current optimistic revision, including empty revision zero."""
        return 0 if self._document is None else self._document.revision

    @property
    def validation_context(self) -> ScheduleValidationContext:
        """Return the immutable authoritative backend validation context."""
        return self._validation_context

    async def async_load(self) -> ScheduleStoreLoadResult:
        """Load one validated canonical schedule or recover fail closed."""
        async with self._lock:
            if self._loaded:
                return self._load_result()

            raw: object | None = None
            try:
                await self._async_load_quarantine_presence()
                raw = await self._store.async_load()
                if raw is None:
                    self._load_status = (
                        ScheduleStoreLoadStatus.QUARANTINED
                        if self._quarantine_present
                        else ScheduleStoreLoadStatus.MISSING
                    )
                elif _has_future_inner_schema(raw):
                    self._preserve_unsupported()
                else:
                    document = decode_schedule_document(
                        raw,
                        validation_context=self._validation_context,
                    )
                    if document.revision < 1:
                        raise SchemaValidationError(
                            "revision",
                            "persisted schedule revision must be positive",
                        )
                    self._document = document
                    self._load_status = ScheduleStoreLoadStatus.LOADED
            except asyncio.CancelledError:
                raise
            except UnsupportedStorageVersionError:
                self._preserve_unsupported()
            except (
                KeyError,
                SchemaMigrationError,
                SchemaValidationError,
                TypeError,
                ValueError,
            ):
                _LOGGER.warning(
                    "Schedule Store quarantined: "
                    "reason_code=invalid_authoritative_schedule_store"
                )
                if raw is None:
                    self._preserve_failed()
                else:
                    await self._async_quarantine(raw)
            except Exception:
                _LOGGER.warning(
                    "Schedule Store preserved: reason_code=schedule_store_load_failed"
                )
                self._preserve_failed()
            self._loaded = True
            return self._load_result()

    async def async_save(
        self,
        proposed: ScheduleDocument,
        *,
        expected_revision: int,
    ) -> ScheduleDocument:
        """Validate, compare-and-swap, persist, then publish one full document."""
        async with self._lock:
            if not self._loaded:
                raise ScheduleStoreNotLoadedError(
                    "Schedule Store must be loaded before saving"
                )
            if self._read_only:
                raise ScheduleStoreReadOnlyError(
                    "Schedule Store is preserved read-only"
                )
            if (
                isinstance(expected_revision, bool)
                or not isinstance(expected_revision, int)
                or expected_revision < 0
            ):
                raise ValueError("expected_revision must be a nonnegative integer")

            actual_revision = self.revision
            if expected_revision != actual_revision:
                raise ScheduleRevisionConflictError(
                    expected_revision=expected_revision,
                    actual_revision=actual_revision,
                )
            if proposed.revision != expected_revision:
                raise SchemaValidationError(
                    "revision",
                    "draft revision must match expected_revision",
                )
            validate_schedule_document(
                proposed,
                validation_context=self._validation_context,
            )
            if self._hass.state is CoreState.stopping:
                raise ScheduleStoreWriteError(
                    "Home Assistant is stopping; schedule was not saved"
                )

            canonical = replace(
                proposed,
                revision=actual_revision + 1,
                saved_at_utc=self._now(),
            )
            encoded = dict(
                encode_schedule_document(
                    canonical,
                    validation_context=self._validation_context,
                )
            )
            try:
                if not await _async_save_verified(self._store, encoded):
                    raise ScheduleStoreWriteError(
                        "schedule write could not be verified"
                    )
            except asyncio.CancelledError:
                raise
            except ScheduleStoreWriteError:
                raise
            except Exception as err:
                raise ScheduleStoreWriteError(
                    "schedule write could not be verified"
                ) from err

            self._document = canonical
            self._load_status = ScheduleStoreLoadStatus.LOADED
            await self._async_cleanup_quarantine()
            return canonical

    async def _async_load_quarantine_presence(self) -> None:
        """Inspect prior quarantine state without exposing its payload."""
        try:
            self._quarantine_present = (
                await self._quarantine_store.async_load() is not None
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._quarantine_present = True
            _LOGGER.warning(
                "Schedule Store quarantine preserved: "
                "reason_code=quarantine_load_failed"
            )

    async def _async_quarantine(self, raw: object) -> None:
        """Copy invalid data to one bounded quarantine before removing primary."""
        quarantine = {
            "quarantined_at": self._now().isoformat(),
            "reason_code": _INVALID_STORE_REASON,
            "data": raw,
        }
        try:
            if not await _async_save_verified(self._quarantine_store, quarantine):
                raise ScheduleStoreWriteError(
                    "schedule quarantine write could not be verified"
                )
            await self._store.async_remove()
        except asyncio.CancelledError:
            raise
        except Exception:
            self._preserve_failed()
            return
        self._quarantine_present = True
        self._load_status = ScheduleStoreLoadStatus.QUARANTINED

    async def _async_cleanup_quarantine(self) -> None:
        """Remove stale quarantine only after a verified canonical save."""
        if not self._quarantine_present:
            return
        try:
            await self._quarantine_store.async_remove()
        except asyncio.CancelledError:
            raise
        except Exception:
            _LOGGER.warning(
                "Schedule Store quarantine retained: "
                "reason_code=quarantine_cleanup_failed"
            )
        else:
            self._quarantine_present = False

    def _preserve_unsupported(self) -> None:
        """Preserve a future envelope or inner schema without downgrade."""
        self._document = None
        self._read_only = True
        self._load_status = ScheduleStoreLoadStatus.UNSUPPORTED
        _LOGGER.warning(
            "Schedule Store preserved: reason_code=unsupported_schedule_store_version"
        )

    def _preserve_failed(self) -> None:
        """Preserve unreadable or unverifiably quarantined data fail closed."""
        self._document = None
        self._read_only = True
        self._load_status = ScheduleStoreLoadStatus.FAILED

    def _load_result(self) -> ScheduleStoreLoadResult:
        return ScheduleStoreLoadResult(
            status=self._load_status,
            document=self._document,
            read_only=self._read_only,
            quarantine_present=self._quarantine_present,
        )

    def _now(self) -> datetime:
        result = self._now_fn()
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError(
                "Schedule Store now_fn must return a timezone-aware datetime"
            )
        return result.astimezone(UTC)


def _has_future_inner_schema(raw: object) -> bool:
    """Return whether a recognizable inner schema is newer than this release."""
    if not isinstance(raw, Mapping):
        return False
    version = raw.get("schedule_schema_version")
    return (
        not isinstance(version, bool)
        and isinstance(version, int)
        and version > SCHEDULE_SCHEMA_VERSION
    )


async def _async_save_verified(
    store: Store[dict[str, Any]],
    data: dict[str, Any],
) -> bool:
    """Persist one atomic payload and verify the exact canonical read-back."""
    await store.async_save(data)
    if store.hass.state is CoreState.stopping:
        return False
    return await store.async_load() == data
