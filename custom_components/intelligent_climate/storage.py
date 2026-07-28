"""Debounced, bounded runtime Store persistence."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from contextlib import suppress
from datetime import datetime
from typing import TYPE_CHECKING, Any

from homeassistant.core import HomeAssistant
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
from .repairs import RepairsManager

if TYPE_CHECKING:
    from .coordinator import IntelligentClimateCoordinator

_LOGGER = logging.getLogger(__name__)

STORE_VERSION = 1
STORE_DEBOUNCE_SECONDS = 30.0
STORE_MAX_DIRTY_SECONDS = 300.0
STORE_FINAL_SAVE_TIMEOUT_SECONDS = 5.0
_RETRY_DELAYS_SECONDS = (5.0, 15.0, 30.0, 60.0, 120.0)

type NowFunction = Callable[[], datetime]


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
        "_expected_zone_ids",
        "_hass",
        "_history",
        "_last_successful_save",
        "_loaded",
        "_now_fn",
        "_repairs",
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
        self._store: Store[dict[str, Any]] = Store(
            hass,
            STORE_VERSION,
            f"intelligent_climate.{entry_id}",
            atomic_writes=True,
        )
        self._coordinator: IntelligentClimateCoordinator | None = None
        self._activity: ActivityPublisher | None = None
        self._loaded = False
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

    @property
    def key(self) -> str:
        """Return the exact Home Assistant Store key."""
        return self._store.key

    @property
    def version(self) -> int:
        """Return the Home Assistant Store envelope version."""
        return self._store.version

    @property
    def loaded(self) -> bool:
        """Return whether the one safe load attempt has completed."""
        return self._loaded

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
        """Restore only valid bounded history; never hydrate live observations."""
        try:
            raw = await self._store.async_load()
            if raw is None:
                return
            document = decode_runtime_store_document(raw)
            if (
                document.entry_id != self._entry_id
                or document.equipment_group_id != self._expected_group_id
                or any(
                    record.equipment_group_id != self._expected_group_id
                    or (
                        record.zone_id is not None
                        and record.zone_id not in self._expected_zone_ids
                    )
                    for record in document.decisions
                )
            ):
                raise SchemaValidationError(
                    "runtime Store",
                    "identity does not match the current configuration",
                )
            self._history.restore(document.decisions, now=self._now())
        except asyncio.CancelledError:
            raise
        except (
            KeyError,
            SchemaMigrationError,
            SchemaValidationError,
            TypeError,
            ValueError,
        ):
            _LOGGER.warning(
                "Runtime Store ignored: reason_code=invalid_nonauthoritative_store"
            )
            self._history.restore((), now=self._now())
        except Exception:
            _LOGGER.warning("Runtime Store ignored: reason_code=store_load_failed")
            self._history.restore((), now=self._now())
        finally:
            self._loaded = True

    def _activity_accepted(self, _record: ActivityRecord) -> None:
        self._mark_dirty()

    def _mark_dirty(self) -> None:
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
        try:
            await self._store.async_save(dict(encode_runtime_store_document(document)))
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_write_failure()
            return False

        if generation == self._dirty_generation:
            self._dirty = False
            self._dirty_since = None
        self._last_successful_save = saved_at
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
