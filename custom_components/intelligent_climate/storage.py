"""Debounced, bounded runtime Store persistence."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import UnsupportedStorageVersionError
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .activity import ActivityPublisher
from .history import ActivityHistory
from .models import (
    ActivityReason,
    ActivityRecord,
    ActivitySeverity,
    ActivityType,
    EntryObservationSnapshot,
    EntryRuntimeConfiguration,
    ObservationSourceId,
    RuntimeStoreDocument,
    RuntimeZoneState,
    SchemaMigrationError,
    SchemaValidationError,
    SourceBaseline,
    decode_runtime_store_document,
    encode_runtime_store_document,
)
from .repairs import MigrationFailureCategory, RepairsManager

if TYPE_CHECKING:
    from .coordinator import IntelligentClimateCoordinator

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
STORE_MINOR_VERSION = 2
STORE_DEBOUNCE_SECONDS = 30.0
STORE_MAX_DIRTY_SECONDS = 300.0
STORE_FINAL_SAVE_TIMEOUT_SECONDS = 5.0
_RETRY_DELAYS_SECONDS = (5.0, 15.0, 30.0, 60.0, 120.0)
_QUARANTINE_SUFFIX = ".quarantine"

type NowFunction = Callable[[], datetime]


class StoreLoadStatus(StrEnum):
    """Bounded runtime Store recovery result."""

    NOT_LOADED = "not_loaded"
    MISSING = "missing"
    LOADED = "loaded"
    MIGRATED = "migrated"
    QUARANTINED = "quarantined"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


class _UnsupportedStoreEnvelopeError(Exception):
    """Signal a future or unknown Store envelope without rewriting it."""


class _StoreWriteVerificationError(Exception):
    """Signal that a Store save did not produce the requested persisted data."""


class _RuntimeDataStore(Store[dict[str, Any]]):
    """Store-v1 envelope with a canonical minor-version migration."""

    __slots__ = ("migrated_from", "migration_payload")

    def __init__(self, hass: HomeAssistant, key: str) -> None:
        super().__init__(
            hass,
            STORE_VERSION,
            key,
            atomic_writes=True,
            max_readable_version=STORE_VERSION,
            minor_version=STORE_MINOR_VERSION,
        )
        self.migrated_from: tuple[int, int] | None = None
        self.migration_payload: object | None = None

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: object,
    ) -> dict[str, Any]:
        """Migrate Store 1.1 to canonical Store 1.2 without schema changes."""
        self.migration_payload = old_data
        if old_major_version != STORE_VERSION or old_minor_version != 1:
            raise _UnsupportedStoreEnvelopeError
        document = decode_runtime_store_document(old_data)
        self.migrated_from = (old_major_version, old_minor_version)
        return dict(encode_runtime_store_document(document))


class RuntimeStore:
    """Own one config entry's nonauthoritative Store lifecycle."""

    __slots__ = (
        "_activity",
        "_closing",
        "_consecutive_failures",
        "_coordinator",
        "_dirty",
        "_dirty_generation",
        "_dirty_since",
        "_entry_id",
        "_expected_group_id",
        "_expected_source_ids",
        "_expected_zone_ids",
        "_hass",
        "_history",
        "_last_successful_save",
        "_load_status",
        "_loaded",
        "_now_fn",
        "_previous_clean_shutdown",
        "_quarantine_present",
        "_quarantine_store",
        "_read_only",
        "_repairs",
        "_restored_source_baselines",
        "_save_handle",
        "_store",
        "_unsubscribe_history",
        "_write_task",
    )

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        entry_id: str,
        configuration: EntryRuntimeConfiguration,
        history: ActivityHistory,
        repairs: RepairsManager,
        now_fn: NowFunction = utcnow,
    ) -> None:
        """Initialize Store v1 with atomic writes and no active write task."""
        self._hass = hass
        self._entry_id = entry_id
        self._history = history
        self._repairs = repairs
        self._now_fn = now_fn
        key = f"intelligent_climate.{entry_id}"
        self._store = _RuntimeDataStore(hass, key)
        self._quarantine_store: Store[dict[str, Any]] = Store(
            hass,
            STORE_VERSION,
            f"{key}{_QUARANTINE_SUFFIX}",
            atomic_writes=True,
        )
        self._coordinator: IntelligentClimateCoordinator | None = None
        self._activity: ActivityPublisher | None = None
        self._loaded = False
        self._load_status = StoreLoadStatus.NOT_LOADED
        self._read_only = False
        self._quarantine_present = False
        self._previous_clean_shutdown: bool | None = None
        self._restored_source_baselines: dict[ObservationSourceId, SourceBaseline] = {}
        self._dirty = False
        self._dirty_generation = 0
        self._dirty_since: float | None = None
        self._save_handle: asyncio.TimerHandle | None = None
        self._write_task: asyncio.Task[None] | None = None
        self._consecutive_failures = 0
        self._last_successful_save: datetime | None = None
        self._closing = False
        self._unsubscribe_history = history.async_add_listener(self._activity_accepted)

        expected_group = configuration.equipment_group.equipment_group_id
        self._expected_group_id = expected_group
        self._expected_zone_ids = frozenset(
            zone.zone_id for zone in configuration.zones
        )
        self._expected_source_ids = frozenset(
            source.source_id
            for zone in configuration.zones
            for source in zone.temperature_sources
        ) | frozenset(
            source.source_id
            for zone in configuration.zones
            for source in zone.humidity_sources
        )

    @property
    def key(self) -> str:
        """Return the exact Home Assistant Store key."""
        return self._store.key

    @property
    def version(self) -> int:
        """Return the Home Assistant Store envelope version."""
        return self._store.version

    @property
    def minor_version(self) -> int:
        """Return the Home Assistant Store envelope minor version."""
        return self._store.minor_version

    @property
    def loaded(self) -> bool:
        """Return whether the one safe load attempt has completed."""
        return self._loaded

    @property
    def load_status(self) -> StoreLoadStatus:
        """Return the bounded result of the Store load/recovery attempt."""
        return self._load_status

    @property
    def read_only(self) -> bool:
        """Return whether unsafe overwrite is suppressed after load failure."""
        return self._read_only

    @property
    def quarantine_present(self) -> bool:
        """Return whether one bounded invalid-data quarantine is retained."""
        return self._quarantine_present

    @property
    def requires_repair(self) -> bool:
        """Return whether persisted-data recovery requires a Repairs issue."""
        return self._quarantine_present or self._load_status in {
            StoreLoadStatus.QUARANTINED,
            StoreLoadStatus.UNSUPPORTED,
            StoreLoadStatus.FAILED,
        }

    @property
    def migration_failure_category(self) -> MigrationFailureCategory | None:
        """Return the bounded Repairs category for persisted-data failure."""
        category = {
            StoreLoadStatus.QUARANTINED: MigrationFailureCategory.STORE_VALIDATION,
            StoreLoadStatus.UNSUPPORTED: MigrationFailureCategory.STORE_VERSION,
            StoreLoadStatus.FAILED: MigrationFailureCategory.STORE_LOAD,
        }.get(self._load_status)
        if category is not None:
            return category
        if self._quarantine_present:
            return MigrationFailureCategory.STORE_VALIDATION
        return None

    @property
    def previous_clean_shutdown(self) -> bool | None:
        """Return the validated prior shutdown marker, if one was loaded."""
        return self._previous_clean_shutdown

    @property
    def restored_source_baselines(
        self,
    ) -> dict[ObservationSourceId, SourceBaseline]:
        """Return validated comparison-only baselines defensively."""
        return dict(self._restored_source_baselines)

    @property
    def dirty(self) -> bool:
        """Return whether material runtime data still needs saving."""
        return self._dirty

    @property
    def consecutive_write_failures(self) -> int:
        """Return the current bounded write-failure count."""
        return self._consecutive_failures

    @property
    def last_successful_save(self) -> datetime | None:
        """Return the most recent successful save timestamp."""
        return self._last_successful_save

    @property
    def write_task(self) -> asyncio.Task[None] | None:
        """Return the single owned writer task for lifecycle verification."""
        return self._write_task

    def attach_runtime(
        self,
        coordinator: IntelligentClimateCoordinator,
        activity: ActivityPublisher,
    ) -> None:
        """Attach live snapshot providers after Store restoration."""
        self._coordinator = coordinator
        self._activity = activity

    async def async_load(self) -> None:
        """Restore validated history and comparison-only source baselines."""
        raw: object | None = None
        try:
            await self._async_load_quarantine_presence()
            raw = await self._store.async_load()
            if raw is None:
                self._load_status = (
                    StoreLoadStatus.QUARANTINED
                    if self._quarantine_present
                    else StoreLoadStatus.MISSING
                )
                return
            document = decode_runtime_store_document(raw)
            self._validate_document(document)
            self._history.restore(document.decisions, now=self._now())
            self._restored_source_baselines = dict(document.source_baselines)
            self._previous_clean_shutdown = document.last_clean_shutdown
            self._last_successful_save = document.saved_at
            self._load_status = (
                StoreLoadStatus.MIGRATED
                if self._store.migrated_from is not None
                else StoreLoadStatus.LOADED
            )
        except asyncio.CancelledError:
            raise
        except UnsupportedStorageVersionError, _UnsupportedStoreEnvelopeError:
            self._read_only = True
            self._load_status = StoreLoadStatus.UNSUPPORTED
            _LOGGER.warning(
                "Runtime Store preserved: reason_code=unsupported_store_version"
            )
            self._history.restore((), now=self._now())
        except (
            KeyError,
            SchemaMigrationError,
            SchemaValidationError,
            TypeError,
            ValueError,
        ):
            _LOGGER.warning(
                "Runtime Store quarantined: reason_code=invalid_nonauthoritative_store"
            )
            self._history.restore((), now=self._now())
            quarantine_payload = (
                self._store.migration_payload
                if self._store.migration_payload is not None
                else raw
            )
            if quarantine_payload is None:
                self._read_only = True
                self._load_status = StoreLoadStatus.FAILED
            else:
                await self._async_quarantine(quarantine_payload)
        except Exception:
            self._read_only = True
            self._load_status = StoreLoadStatus.FAILED
            _LOGGER.warning("Runtime Store preserved: reason_code=store_load_failed")
            self._history.restore((), now=self._now())
        finally:
            self._loaded = True

    async def _async_load_quarantine_presence(self) -> None:
        """Inspect a prior quarantine without preventing primary Store recovery."""
        try:
            self._quarantine_present = (
                await self._quarantine_store.async_load() is not None
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._quarantine_present = True
            _LOGGER.warning(
                "Runtime Store quarantine preserved: reason_code=quarantine_load_failed"
            )

    def _validate_document(self, document: RuntimeStoreDocument) -> None:
        if (
            document.entry_id != self._entry_id
            or document.equipment_group_id != self._expected_group_id
        ):
            raise SchemaValidationError(
                "runtime Store",
                "identity does not match the current configuration",
            )
        if not set(document.zones).issubset(self._expected_zone_ids):
            raise SchemaValidationError(
                "runtime Store zones",
                "contain an unknown zone identity",
            )
        if not set(document.source_baselines).issubset(self._expected_source_ids):
            raise SchemaValidationError(
                "runtime Store source_baselines",
                "contain an unknown source identity",
            )
        if any(
            baseline.last_accepted_at > document.saved_at
            for baseline in document.source_baselines.values()
        ):
            raise SchemaValidationError(
                "runtime Store source_baselines",
                "contain a baseline newer than the save",
            )
        if any(
            record.equipment_group_id != self._expected_group_id
            or (
                record.zone_id is not None
                and record.zone_id not in self._expected_zone_ids
            )
            for record in document.decisions
        ):
            raise SchemaValidationError(
                "runtime Store decisions",
                "contain an invalid identity",
            )

    async def _async_quarantine(self, raw: object) -> None:
        quarantine = {
            "quarantined_at": self._now().isoformat(),
            "reason_code": "invalid_nonauthoritative_store",
            "data": raw,
        }
        try:
            if (
                await _async_save_verified(self._quarantine_store, quarantine)
                is not True
            ):
                raise _StoreWriteVerificationError
            await self._store.async_remove()
        except asyncio.CancelledError:
            raise
        except Exception:
            self._read_only = True
            self._load_status = StoreLoadStatus.FAILED
            return
        self._quarantine_present = True
        self._load_status = StoreLoadStatus.QUARANTINED

    def _activity_accepted(self, _record: ActivityRecord) -> None:
        self._mark_dirty()

    def _mark_dirty(self) -> None:
        if self._read_only:
            return
        if self._closing:
            self._dirty = True
            self._dirty_generation += 1
            return
        loop_time = self._hass.loop.time()
        self._dirty = True
        self._dirty_generation += 1
        if self._dirty_since is None:
            self._dirty_since = loop_time
        deadline = min(
            loop_time + STORE_DEBOUNCE_SECONDS,
            self._dirty_since + STORE_MAX_DIRTY_SECONDS,
        )
        self._schedule_at(deadline)

    def _schedule_at(self, deadline: float) -> None:
        if self._closing:
            return
        if self._save_handle is not None:
            self._save_handle.cancel()
        self._save_handle = self._hass.loop.call_at(
            deadline,
            self._start_write_task,
        )

    def _start_write_task(self) -> None:
        if self._save_handle is not None:
            self._save_handle.cancel()
        self._save_handle = None
        if self._closing or not self._dirty:
            return
        if self._write_task is not None and not self._write_task.done():
            return
        self._write_task = self._hass.async_create_task(
            self._async_write(),
            "Intelligent Climate runtime Store write",
        )

    async def _async_write(self) -> None:
        try:
            await self._async_attempt_save(last_clean_shutdown=False)
        finally:
            self._write_task = None
            if self._dirty and not self._closing and self._save_handle is None:
                self._schedule_at(self._hass.loop.time() + STORE_DEBOUNCE_SECONDS)

    async def _async_attempt_save(self, *, last_clean_shutdown: bool) -> bool:
        if self._read_only:
            return False
        coordinator = self._coordinator
        if coordinator is None:
            return False
        saved_at = self._now()
        self._history.prune(now=saved_at)
        generation = self._dirty_generation
        document = self._document(
            coordinator,
            saved_at=saved_at,
            last_clean_shutdown=last_clean_shutdown,
        )
        encoded_document = dict(encode_runtime_store_document(document))
        try:
            verification = await _async_save_verified(
                self._store,
                encoded_document,
            )
            if verification is False:
                raise _StoreWriteVerificationError
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_write_failure()
            return False

        if generation == self._dirty_generation:
            self._dirty = False
            self._dirty_since = None
        if verification is None:
            return True
        self._last_successful_save = saved_at
        if self._quarantine_present:
            try:
                await self._quarantine_store.async_remove()
            except Exception:
                _LOGGER.warning(
                    "Runtime Store quarantine retained: "
                    "reason_code=quarantine_cleanup_failed"
                )
            else:
                self._quarantine_present = False
                self._repairs.async_clear_migration_failure()
        self._load_status = StoreLoadStatus.LOADED
        if self._consecutive_failures:
            self._consecutive_failures = 0
            self._repairs.async_notify_store_write_failures(0)
            if self._activity is not None:
                self._activity.record(
                    activity_type=ActivityType.STORE_WRITE_RECOVERED,
                    reason_code=ActivityReason.STORE_WRITE_RECOVERED,
                    severity=ActivitySeverity.INFO,
                    explanation="Runtime activity persistence recovered.",
                )
        return True

    def _record_write_failure(self) -> None:
        self._consecutive_failures += 1
        self._repairs.async_notify_store_write_failures(self._consecutive_failures)
        if self._consecutive_failures == 1 and self._activity is not None:
            self._activity.record(
                activity_type=ActivityType.STORE_WRITE_FAILED,
                reason_code=ActivityReason.STORE_WRITE_FAILED,
                severity=ActivitySeverity.WARNING,
                explanation="Runtime activity could not be persisted.",
            )
        if not self._closing:
            index = min(
                self._consecutive_failures - 1,
                len(_RETRY_DELAYS_SECONDS) - 1,
            )
            self._schedule_at(self._hass.loop.time() + _RETRY_DELAYS_SECONDS[index])

    def _document(
        self,
        coordinator: IntelligentClimateCoordinator,
        *,
        saved_at: datetime,
        last_clean_shutdown: bool,
    ) -> RuntimeStoreDocument:
        snapshot: EntryObservationSnapshot = coordinator.data
        zones = {
            observation.zone_id: RuntimeZoneState(
                last_runtime_state=snapshot.control_state,
                last_live_observation_at=(
                    observation.calculated_at
                    if observation.effective_temperature_c is not None
                    else None
                ),
                last_effective_temperature_c=observation.effective_temperature_c,
                last_effective_humidity_pct=observation.effective_humidity_pct,
                last_decision_id=(
                    None
                    if (latest := self._history.latest_for_zone(observation.zone_id))
                    is None
                    else str(latest.record_id)
                ),
            )
            for observation in snapshot.zones
        }
        baselines: dict[ObservationSourceId, SourceBaseline] = (
            coordinator.source_baselines
        )
        return RuntimeStoreDocument(
            entry_id=self._entry_id,
            equipment_group_id=snapshot.equipment_group_id,
            saved_at=saved_at,
            last_clean_shutdown=last_clean_shutdown,
            zones=zones,
            source_baselines=baselines,
            decisions=self._history.records,
            command_journal=(),
        )

    async def async_final_save(self) -> None:
        """Attempt a clean save within five seconds without blocking unload."""
        self._closing = True
        if self._save_handle is not None:
            self._save_handle.cancel()
            self._save_handle = None
        if self._read_only:
            return
        try:
            async with asyncio.timeout(STORE_FINAL_SAVE_TIMEOUT_SECONDS):
                if self._write_task is not None:
                    await self._write_task
                    self._write_task = None
                self._dirty = True
                self._dirty_generation += 1
                await self._async_attempt_save(last_clean_shutdown=True)
                if self._dirty:
                    await self._async_attempt_save(last_clean_shutdown=True)
        except TimeoutError:
            self._record_write_failure()
            task = self._write_task
            if task is not None and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            self._write_task = None
        except Exception:
            self._record_write_failure()

    async def async_shutdown(self) -> None:
        """Cancel every Store timer/task/listener without another save."""
        self._closing = True
        if self._save_handle is not None:
            self._save_handle.cancel()
            self._save_handle = None
        task = self._write_task
        if task is not None and not task.done():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._write_task = None
        self._unsubscribe_history()

    def _now(self) -> datetime:
        result = self._now_fn()
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError("Store now_fn must return a timezone-aware datetime")
        return result


async def _async_save_verified(
    store: Store[dict[str, Any]],
    data: dict[str, Any],
) -> bool | None:
    """Persist and verify, or report a Home Assistant final-write deferral."""
    await store.async_save(data)
    if store.hass.state is CoreState.stopping:
        return None
    return await store.async_load() == data
