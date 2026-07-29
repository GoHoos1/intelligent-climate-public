"""Event-driven, entry-scoped observation coordinator."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from functools import partial

from homeassistant.core import (
    CALLBACK_TYPE,
    Event,
    EventStateChangedData,
    EventStateReportedData,
    HassJob,
    HomeAssistant,
    callback,
)
from homeassistant.helpers.event import (
    async_call_later,
    async_track_point_in_utc_time,
    async_track_state_change_event,
    async_track_state_report_event,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util.dt import utcnow

from .activity import ActivityPublisher
from .aggregation import (
    aggregate_humidity_sources,
    aggregate_temperature_sources,
)
from .capability import discover_thermostat_capabilities
from .climate_state import normalize_climate_state
from .const import DOMAIN, STATE_CHANGE_DEBOUNCE_SECONDS
from .control import ObserveOnlyCommandSink
from .health import evaluate_humidity_health, evaluate_temperature_health
from .history import ActivityHistory
from .models import (
    ActivityReason,
    ActivitySeverity,
    ActivityType,
    AggregationReason,
    AggregationStatus,
    ControlState,
    EntryObservationSnapshot,
    EntryRuntimeConfiguration,
    NormalizedClimateState,
    ObservationSourceId,
    PendingJumpCandidate,
    RuntimeConfigurationState,
    SourceAggregationResult,
    SourceBaseline,
    SourceHealthEvaluation,
    SourceObservation,
    SourceQuality,
    ThermostatRuntimeSnapshot,
    ZoneConfig,
    ZoneId,
    ZoneObservation,
)
from .observation import observe_humidity_source, observe_temperature_source
from .repairs import RepairsManager
from .storage import RuntimeStore
from .type_aliases import IntelligentClimateConfigEntry

_LOGGER = logging.getLogger(__name__)
_STALE_BOUNDARY_INCREMENT = timedelta(microseconds=1)
_RECOVERY_CONFIRMATION_INTERVAL = timedelta(seconds=30)
_WARNING_COOLDOWN = timedelta(minutes=15)

type NowFunction = Callable[[], datetime]


class IntelligentClimateCoordinator(DataUpdateCoordinator[EntryObservationSnapshot]):
    """Coordinate live observation without polling or physical control."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: IntelligentClimateConfigEntry,
        configuration: EntryRuntimeConfiguration,
        *,
        now_fn: NowFunction = utcnow,
        issue_manager: RepairsManager | None = None,
        history: ActivityHistory | None = None,
        activity: ActivityPublisher | None = None,
        runtime_store: RuntimeStore | None = None,
        restored_source_baselines: Mapping[ObservationSourceId, SourceBaseline]
        | None = None,
    ) -> None:
        """Initialize deterministic indexes and private orchestration state."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=None,
        )
        self.entry = entry
        self.configuration = configuration
        self._now_fn = now_fn
        self.issue_manager = issue_manager or RepairsManager(hass, entry.entry_id)
        self.history = history or ActivityHistory(
            max_records=configuration.options.history_max_records,
            max_age_days=configuration.options.history_max_age_days,
        )
        self.activity = activity or ActivityPublisher(
            hass,
            entry_id=entry.entry_id,
            equipment_group_id=configuration.equipment_group.equipment_group_id,
            history=self.history,
            now_fn=now_fn,
        )
        self.issue_manager.set_activity_reporter(self.activity)
        self.runtime_store = runtime_store
        self.command_sink = ObserveOnlyCommandSink(self.issue_manager)

        self._zones_by_id = {zone.zone_id: zone for zone in configuration.zones}
        self._source_to_zones: dict[str, tuple[ZoneId, ...]]
        self._thermostat_to_zones: dict[str, tuple[ZoneId, ...]]
        self._source_id_to_zones: dict[ObservationSourceId, tuple[ZoneId, ...]]
        (
            self._source_to_zones,
            self._thermostat_to_zones,
            self._source_id_to_zones,
        ) = self._build_dependency_indexes()

        self._source_baselines: dict[ObservationSourceId, SourceBaseline] = dict(
            restored_source_baselines or {}
        )
        self._pending_temperature_jumps: dict[
            ObservationSourceId, PendingJumpCandidate
        ] = {}
        self._source_observations: dict[
            ObservationSourceId, SourceObservation[float]
        ] = {}
        self._thermostat_snapshots: dict[str, ThermostatRuntimeSnapshot] = {}

        self._pending_zone_ids: set[ZoneId] = set()
        self._pending_thermostat_entity_ids: set[str] = set()
        self._cancel_debounce: CALLBACK_TYPE | None = None
        self._cancel_reconciliation: CALLBACK_TYPE | None = None
        self._cancel_watchdog: CALLBACK_TYPE | None = None
        self._cancel_state_change_subscription: CALLBACK_TYPE | None = None
        self._cancel_state_report_subscription: CALLBACK_TYPE | None = None
        self._cancel_core_shutdown_job: CALLBACK_TYPE | None = None
        self._debounce_generation = 0
        self._reconciliation_generation = 0
        self._watchdog_generation = 0
        self._revision = 0
        self._reconciling = False
        self._recovery_candidate_at: datetime | None = None
        self._warning_last_logged: dict[str, datetime] = {}
        self._shutdown = False

    @property
    def source_dependency_index(self) -> dict[str, tuple[ZoneId, ...]]:
        """Return a defensive copy of the deterministic source index."""
        return dict(self._source_to_zones)

    @property
    def thermostat_dependency_index(self) -> dict[str, tuple[ZoneId, ...]]:
        """Return a defensive copy of the deterministic thermostat index."""
        return dict(self._thermostat_to_zones)

    @property
    def source_baselines(self) -> dict[ObservationSourceId, SourceBaseline]:
        """Return a defensive copy for schema-complete nonauthoritative saves."""
        return dict(self._source_baselines)

    async def async_start(self) -> None:
        """Subscribe, publish the initial snapshot, then schedule deadlines."""
        if self._shutdown:
            raise RuntimeError("coordinator has shut down")
        if self._runtime_is_active:
            self._register_state_subscriptions()
        _LOGGER.info(
            "Intelligent Climate setup started: config_entry_id=%s "
            "reason_code=setup_started",
            self.entry.entry_id,
        )
        self.activity.record(
            activity_type=ActivityType.LIFECYCLE,
            reason_code=ActivityReason.SETUP_STARTED,
            severity=ActivitySeverity.INFO,
            explanation="Intelligent Climate observation setup started.",
        )
        await self.async_config_entry_first_refresh()
        if self._runtime_is_active:
            self._schedule_reconciliation()
            self._schedule_watchdog(self.data.calculated_at)

    def async_record_setup_complete(self) -> None:
        """Record successful platform setup after activity entities subscribe."""
        _LOGGER.info(
            "Intelligent Climate setup completed: config_entry_id=%s "
            "reason_code=setup_completed",
            self.entry.entry_id,
        )
        self.activity.record(
            activity_type=ActivityType.LIFECYCLE,
            reason_code=ActivityReason.SETUP_COMPLETED,
            severity=ActivitySeverity.INFO,
            explanation="Intelligent Climate observation setup completed.",
        )

    def async_add_core_shutdown_job(self) -> None:
        """Register one awaited, entry-scoped Home Assistant shutdown job."""
        if self._cancel_core_shutdown_job is not None:
            return
        self._cancel_core_shutdown_job = self.hass.async_add_shutdown_job(
            HassJob(
                self._async_core_shutdown,
                "Intelligent Climate core shutdown",
            )
        )

    def async_unregister_core_shutdown_job(self) -> None:
        """Remove the entry-scoped shutdown job idempotently."""
        if self._cancel_core_shutdown_job is None:
            return
        cancel = self._cancel_core_shutdown_job
        self._cancel_core_shutdown_job = None
        cancel()

    async def _async_core_shutdown(self) -> None:
        """Persist a clean marker and release runtime callbacks on core stop."""
        if self._shutdown:
            return
        try:
            if self.runtime_store is not None:
                await self.runtime_store.async_final_save()
        finally:
            await self._async_shutdown(remove_core_shutdown_job=False)

    def async_record_store_migrated(self) -> None:
        """Record one successful runtime Store envelope migration."""
        self.activity.record(
            activity_type=ActivityType.LIFECYCLE,
            reason_code=ActivityReason.STORE_MIGRATED,
            severity=ActivitySeverity.INFO,
            explanation="Runtime persistence migration completed.",
        )

    def async_record_unclean_shutdown(self) -> None:
        """Record that live reconciliation follows an unclean prior shutdown."""
        self._log_warning_once(
            "unclean_shutdown_detected",
            self._now(),
            "Unclean shutdown detected: config_entry_id=%s "
            "reason_code=unclean_shutdown_detected",
            self.entry.entry_id,
        )
        self.activity.record(
            activity_type=ActivityType.LIFECYCLE,
            reason_code=ActivityReason.UNCLEAN_SHUTDOWN_DETECTED,
            severity=ActivitySeverity.WARNING,
            explanation=(
                "An unclean previous shutdown was detected; "
                "live reconciliation is required."
            ),
        )

    def async_record_unload(self) -> None:
        """Record the final clean-unload activity before Store flush."""
        _LOGGER.info(
            "Intelligent Climate unload started: config_entry_id=%s reason_code=unload",
            self.entry.entry_id,
        )
        self.activity.record(
            activity_type=ActivityType.LIFECYCLE,
            reason_code=ActivityReason.UNLOAD,
            severity=ActivitySeverity.INFO,
            explanation="Intelligent Climate observation unloaded cleanly.",
        )

    def _log_warning_once(
        self,
        reason_code: str,
        timestamp: datetime,
        message: str,
        *args: object,
    ) -> None:
        """Log one warning per stable reason during the cooldown."""
        previous = self._warning_last_logged.get(reason_code)
        if previous is not None and timestamp - previous < _WARNING_COOLDOWN:
            return
        self._warning_last_logged[reason_code] = timestamp
        _LOGGER.warning(message, *args)

    def async_record_unsupported_control_attempt(self, zone_id: ZoneId) -> None:
        """Record one payload-free virtual-climate setter rejection."""
        self.activity.record(
            activity_type=ActivityType.UNSUPPORTED_CONTROL_ATTEMPT,
            reason_code=ActivityReason.UNSUPPORTED_CONTROL_ATTEMPT,
            severity=ActivitySeverity.WARNING,
            explanation="A virtual climate control attempt was safely rejected.",
            zone_id=zone_id,
        )

    @property
    def _runtime_is_active(self) -> bool:
        return (
            self.configuration.options.observation_enabled
            and self.configuration.state is RuntimeConfigurationState.CONFIGURED
        )

    async def _async_update_data(self) -> EntryObservationSnapshot:
        """Build the first snapshot through the supported first-refresh path."""
        calculated_at = self._now()
        if self.configuration.transitional_empty_skeleton:
            return self._new_snapshot(
                thermostats=(),
                zones=(),
                reconciling=False,
                calculated_at=calculated_at,
            )
        if self.configuration.awaiting_first_zone:
            return self._new_snapshot(
                thermostats=(),
                zones=(),
                reconciling=False,
                calculated_at=calculated_at,
            )
        if not self.configuration.options.observation_enabled:
            thermostats = self._unavailable_thermostats(calculated_at)
            self._thermostat_snapshots = {item.entity_id: item for item in thermostats}
            zones = tuple(
                self._disabled_zone(zone, calculated_at)
                for zone in self.configuration.zones
            )
            return self._new_snapshot(
                thermostats=thermostats,
                zones=zones,
                reconciling=False,
                calculated_at=calculated_at,
            )

        self._reconciling = True
        thermostats = self._refresh_thermostats(
            self._configured_thermostat_entity_ids,
            calculated_at,
        )
        zones = tuple(
            self._evaluate_zone(zone, calculated_at)
            for zone in self.configuration.zones
        )
        snapshot = self._new_snapshot(
            thermostats=thermostats,
            zones=zones,
            reconciling=True,
            calculated_at=calculated_at,
        )
        self._record_snapshot_activity(previous=None, current=snapshot)
        return snapshot

    @property
    def _configured_thermostat_entity_ids(self) -> tuple[str, ...]:
        return tuple(
            binding.entity_id
            for binding in self.configuration.equipment_group.thermostats
        )

    def _build_dependency_indexes(
        self,
    ) -> tuple[
        dict[str, tuple[ZoneId, ...]],
        dict[str, tuple[ZoneId, ...]],
        dict[ObservationSourceId, tuple[ZoneId, ...]],
    ]:
        source_entities: dict[str, list[ZoneId]] = {}
        thermostat_entities: dict[str, list[ZoneId]] = {}
        source_ids: dict[ObservationSourceId, list[ZoneId]] = {}
        for zone in self.configuration.zones:
            for temperature_source in zone.temperature_sources:
                if not temperature_source.enabled:
                    continue
                _append_unique(
                    source_entities,
                    temperature_source.entity_id,
                    zone.zone_id,
                )
                _append_unique(
                    source_ids,
                    temperature_source.source_id,
                    zone.zone_id,
                )
            for humidity_source in zone.humidity_sources:
                if not humidity_source.enabled:
                    continue
                _append_unique(
                    source_entities,
                    humidity_source.entity_id,
                    zone.zone_id,
                )
                _append_unique(
                    source_ids,
                    humidity_source.source_id,
                    zone.zone_id,
                )
            for entity_id in zone.thermostat_entity_ids:
                _append_unique(thermostat_entities, entity_id, zone.zone_id)
        return (
            {key: tuple(value) for key, value in source_entities.items()},
            {key: tuple(value) for key, value in thermostat_entities.items()},
            {key: tuple(value) for key, value in source_ids.items()},
        )

    def _register_state_subscriptions(self) -> None:
        entity_ids = list(self._source_to_zones)
        entity_ids.extend(
            entity_id
            for entity_id in self._configured_thermostat_entity_ids
            if entity_id not in self._source_to_zones
        )
        if entity_ids:
            self._cancel_state_change_subscription = async_track_state_change_event(
                self.hass,
                entity_ids,
                self._async_state_changed,
            )
            self._cancel_state_report_subscription = async_track_state_report_event(
                self.hass,
                entity_ids,
                self._async_state_reported,
            )

    @callback
    def _async_state_changed(
        self,
        event: Event[EventStateChangedData],
    ) -> None:
        """Collect affected dependencies and replace the short debounce."""
        self._collect_entity_event(event.data["entity_id"])

    @callback
    def _async_state_reported(
        self,
        event: Event[EventStateReportedData],
    ) -> None:
        """Collect an unchanged state report through the shared debounce path."""
        self._collect_entity_event(event.data["entity_id"])

    def _collect_entity_event(self, entity_id: str) -> None:
        """Collect one state change or unchanged report for targeted evaluation."""
        if self._shutdown:
            return
        self._pending_zone_ids.update(self._source_to_zones.get(entity_id, ()))
        thermostat_zones = self._thermostat_to_zones.get(entity_id)
        if thermostat_zones is not None:
            self._pending_zone_ids.update(thermostat_zones)
            self._pending_thermostat_entity_ids.add(entity_id)
        if not self._pending_zone_ids and not self._pending_thermostat_entity_ids:
            return

        self._debounce_generation += 1
        generation = self._debounce_generation
        _cancel(self._cancel_debounce)
        self._cancel_debounce = async_call_later(
            self.hass,
            STATE_CHANGE_DEBOUNCE_SECONDS,
            partial(self._async_debounce_elapsed, generation=generation),
        )

    async def _async_debounce_elapsed(
        self,
        fire_time: datetime,
        *,
        generation: int,
    ) -> None:
        """Publish one targeted update for the complete coalesced burst."""
        if self._shutdown or generation != self._debounce_generation:
            return
        _cancel(self._cancel_debounce)
        self._cancel_debounce = None
        zone_ids = set(self._pending_zone_ids)
        thermostat_ids = set(self._pending_thermostat_entity_ids)
        self._pending_zone_ids.clear()
        self._pending_thermostat_entity_ids.clear()
        if not zone_ids and not thermostat_ids:
            return
        self._refresh_thermostats(thermostat_ids, fire_time)
        self._publish_targeted(zone_ids, fire_time)

    def _refresh_thermostats(
        self,
        entity_ids: set[str] | tuple[str, ...],
        calculated_at: datetime,
    ) -> tuple[ThermostatRuntimeSnapshot, ...]:
        requested = set(entity_ids)
        unit = self.hass.config.units.temperature_unit
        for entity_id in self._configured_thermostat_entity_ids:
            if entity_id not in requested:
                continue
            state = self.hass.states.get(entity_id)
            self._thermostat_snapshots[entity_id] = ThermostatRuntimeSnapshot(
                entity_id=entity_id,
                state=normalize_climate_state(
                    entity_id,
                    state,
                    observed_at=calculated_at,
                    climate_temperature_unit=unit,
                ),
                capability_discovery=discover_thermostat_capabilities(
                    entity_id,
                    state,
                    discovered_at=calculated_at,
                ),
            )
        return tuple(
            self._thermostat_snapshots[entity_id]
            for entity_id in self._configured_thermostat_entity_ids
        )

    def _unavailable_thermostats(
        self,
        calculated_at: datetime,
    ) -> tuple[ThermostatRuntimeSnapshot, ...]:
        unit = self.hass.config.units.temperature_unit
        return tuple(
            ThermostatRuntimeSnapshot(
                entity_id=entity_id,
                state=normalize_climate_state(
                    entity_id,
                    None,
                    observed_at=calculated_at,
                    climate_temperature_unit=unit,
                ),
                capability_discovery=discover_thermostat_capabilities(
                    entity_id,
                    None,
                    discovered_at=calculated_at,
                ),
            )
            for entity_id in self._configured_thermostat_entity_ids
        )

    def _evaluate_zone(
        self,
        zone: ZoneConfig,
        calculated_at: datetime,
    ) -> ZoneObservation:
        options = self.configuration.options
        climate_unit = self.hass.config.units.temperature_unit
        temperature_observations: list[SourceObservation[float]] = []
        for temperature_source in zone.temperature_sources:
            if not temperature_source.enabled:
                continue
            normalized = observe_temperature_source(
                temperature_source,
                self.hass.states.get(temperature_source.entity_id),
                observed_at=calculated_at,
                climate_temperature_unit=climate_unit,
            )
            health = evaluate_temperature_health(
                normalized,
                baseline=self._source_baselines.get(temperature_source.source_id),
                pending_jump=self._pending_temperature_jumps.get(
                    temperature_source.source_id
                ),
                stale_after_seconds=options.source_stale_after_seconds,
                plausible_min_c=options.indoor_temperature_min_c,
                plausible_max_c=options.indoor_temperature_max_c,
                jump_limit_c_per_5_minutes=options.jump_limit_c_per_5_minutes,
            )
            self._update_health_state(temperature_source.source_id, health)
            temperature_observations.append(health.observation)

        humidity_observations: list[SourceObservation[float]] = []
        for humidity_source in zone.humidity_sources:
            if not humidity_source.enabled:
                continue
            normalized = observe_humidity_source(
                humidity_source,
                self.hass.states.get(humidity_source.entity_id),
                observed_at=calculated_at,
            )
            health = evaluate_humidity_health(
                normalized,
                stale_after_seconds=options.source_stale_after_seconds,
                baseline=self._source_baselines.get(humidity_source.source_id),
            )
            self._update_health_state(humidity_source.source_id, health)
            humidity_observations.append(health.observation)

        temperature_aggregation = aggregate_temperature_sources(
            zone.temperature_sources,
            tuple(temperature_observations),
            strategy=options.temperature_strategy,
            min_valid_sources=options.min_valid_temperature_sources,
            outlier_floor_c=options.outlier_floor_c,
            calculated_at=calculated_at,
        )
        humidity_aggregation = (
            aggregate_humidity_sources(
                zone.humidity_sources,
                tuple(humidity_observations),
                strategy=options.humidity_strategy,
                min_valid_sources=options.min_valid_humidity_sources,
                calculated_at=calculated_at,
            )
            if zone.humidity_sources
            else None
        )
        self._log_source_exclusions(
            zone,
            (
                *temperature_aggregation.excluded_observations,
                *(
                    ()
                    if humidity_aggregation is None
                    else humidity_aggregation.excluded_observations
                ),
            ),
        )
        thermostat_states = tuple(
            self._thermostat_snapshots[entity_id].state
            for entity_id in zone.thermostat_entity_ids
        )
        return ZoneObservation(
            zone_id=zone.zone_id,
            temperature_observations=tuple(temperature_observations),
            humidity_observations=tuple(humidity_observations),
            temperature_aggregation=temperature_aggregation,
            humidity_aggregation=humidity_aggregation,
            thermostat_states=thermostat_states,
            sensor_data_degraded=(
                temperature_aggregation.status is not AggregationStatus.HEALTHY
                or (
                    humidity_aggregation is not None
                    and humidity_aggregation.status is not AggregationStatus.HEALTHY
                )
            ),
            thermostat_data_degraded=(
                any(not state.available for state in thermostat_states)
                or _thermostat_states_conflict(thermostat_states)
            ),
            calculated_at=calculated_at,
        )

    def _log_source_exclusions(
        self,
        zone: ZoneConfig,
        exclusions: tuple[SourceObservation[float], ...],
    ) -> None:
        """Log only bounded identifiers and quality metadata for exclusions."""
        source_entities_by_id = {
            source.source_id: source.entity_id for source in zone.temperature_sources
        }
        source_entities_by_id.update(
            {source.source_id: source.entity_id for source in zone.humidity_sources}
        )
        for observation in exclusions:
            reason = observation.exclusion_reason
            _LOGGER.debug(
                (
                    "Configured source excluded: config_entry_id=%s zone_id=%s "
                    "source_id=%s source_entity_id=%s source_quality=%s "
                    "exclusion_reason=%s source_last_reported=%s "
                    "observation_time=%s"
                ),
                self.entry.entry_id,
                zone.zone_id,
                observation.source_id,
                source_entities_by_id[observation.source_id],
                observation.quality.value,
                None if reason is None else reason.value,
                observation.source_last_reported,
                observation.observed_at,
            )

    def _update_health_state(
        self,
        source_id: ObservationSourceId,
        health: SourceHealthEvaluation,
    ) -> None:
        if health.next_baseline is not None:
            self._source_baselines[source_id] = health.next_baseline
        else:
            self._source_baselines.pop(source_id, None)
        if health.pending_jump is not None:
            self._pending_temperature_jumps[source_id] = health.pending_jump
        else:
            self._pending_temperature_jumps.pop(source_id, None)
        self._source_observations[source_id] = health.observation

    def _disabled_zone(
        self,
        zone: ZoneConfig,
        calculated_at: datetime,
    ) -> ZoneObservation:
        temperature = _empty_aggregation(calculated_at)
        humidity = _empty_aggregation(calculated_at) if zone.humidity_sources else None
        return ZoneObservation(
            zone_id=zone.zone_id,
            temperature_observations=(),
            humidity_observations=(),
            temperature_aggregation=temperature,
            humidity_aggregation=humidity,
            thermostat_states=tuple(
                self._thermostat_snapshots[entity_id].state
                for entity_id in zone.thermostat_entity_ids
            ),
            sensor_data_degraded=False,
            thermostat_data_degraded=False,
            calculated_at=calculated_at,
        )

    def _publish_targeted(
        self,
        affected_zone_ids: set[ZoneId],
        calculated_at: datetime,
    ) -> None:
        if self._shutdown or not affected_zone_ids:
            return
        zones = tuple(
            (
                self._evaluate_zone(self._zones_by_id[item.zone_id], calculated_at)
                if item.zone_id in affected_zone_ids
                else item
            )
            for item in self.data.zones
        )
        snapshot = self._new_snapshot(
            thermostats=tuple(
                self._thermostat_snapshots[entity_id]
                for entity_id in self._configured_thermostat_entity_ids
            ),
            zones=zones,
            reconciling=self._reconciling,
            calculated_at=calculated_at,
        )
        self._record_snapshot_activity(previous=self.data, current=snapshot)
        self.async_set_updated_data(snapshot)
        if not self._reconciling:
            self.issue_manager.async_sync_entity_conditions(self.configuration)
        self._schedule_watchdog(calculated_at)

    def _new_snapshot(
        self,
        *,
        thermostats: tuple[ThermostatRuntimeSnapshot, ...],
        zones: tuple[ZoneObservation, ...],
        reconciling: bool,
        calculated_at: datetime,
    ) -> EntryObservationSnapshot:
        self._revision += 1
        if self.configuration.awaiting_first_zone:
            control_state = ControlState.INITIALIZING
        elif reconciling:
            control_state = ControlState.RECONCILING
        elif not self.configuration.options.observation_enabled:
            control_state = ControlState.DISABLED
        elif any(
            zone.sensor_data_degraded or zone.thermostat_data_degraded for zone in zones
        ):
            self._recovery_candidate_at = None
            control_state = ControlState.DEGRADED
        else:
            previous = getattr(self, "data", None)
            if previous is not None and previous.control_state is ControlState.DEGRADED:
                if self._recovery_candidate_at is None:
                    self._recovery_candidate_at = calculated_at
                    control_state = ControlState.DEGRADED
                elif (
                    calculated_at - self._recovery_candidate_at
                    < _RECOVERY_CONFIRMATION_INTERVAL
                ):
                    control_state = ControlState.DEGRADED
                else:
                    self._recovery_candidate_at = None
                    control_state = ControlState.OBSERVING
            else:
                self._recovery_candidate_at = None
                control_state = ControlState.OBSERVING
        return EntryObservationSnapshot(
            entry_id=self.entry.entry_id,
            equipment_group_id=self.configuration.equipment_group.equipment_group_id,
            control_state=control_state,
            reconciling=reconciling,
            revision=self._revision,
            thermostats=thermostats,
            zones=zones,
            calculated_at=calculated_at,
        )

    def _schedule_reconciliation(self) -> None:
        self._reconciliation_generation += 1
        generation = self._reconciliation_generation
        _cancel(self._cancel_reconciliation)
        self._cancel_reconciliation = async_call_later(
            self.hass,
            self.configuration.options.startup_reconciliation_seconds,
            partial(self._async_reconciliation_complete, generation=generation),
        )

    async def _async_reconciliation_complete(
        self,
        fire_time: datetime,
        *,
        generation: int,
    ) -> None:
        if self._shutdown or generation != self._reconciliation_generation:
            return
        _cancel(self._cancel_reconciliation)
        self._cancel_reconciliation = None
        self._reconciling = False
        self._refresh_thermostats(
            self._configured_thermostat_entity_ids,
            fire_time,
        )
        zones = tuple(
            self._evaluate_zone(zone, fire_time) for zone in self.configuration.zones
        )
        snapshot = self._new_snapshot(
            thermostats=tuple(
                self._thermostat_snapshots[entity_id]
                for entity_id in self._configured_thermostat_entity_ids
            ),
            zones=zones,
            reconciling=False,
            calculated_at=fire_time,
        )
        self._record_snapshot_activity(previous=self.data, current=snapshot)
        self.async_set_updated_data(snapshot)
        _LOGGER.info(
            "Startup reconciliation completed: config_entry_id=%s "
            "control_state=%s reason_code=reconciliation_completed",
            self.entry.entry_id,
            snapshot.control_state.value,
        )
        self.activity.record(
            activity_type=ActivityType.LIFECYCLE,
            reason_code=ActivityReason.RECONCILIATION_COMPLETED,
            severity=(
                ActivitySeverity.WARNING
                if snapshot.control_state is ControlState.DEGRADED
                else ActivitySeverity.INFO
            ),
            explanation="Startup observation reconciliation completed.",
            timestamp=fire_time,
        )
        self.issue_manager.async_sync_entity_conditions(self.configuration)
        self._schedule_watchdog(fire_time)

    def _schedule_watchdog(self, reference_time: datetime) -> None:
        self._watchdog_generation += 1
        generation = self._watchdog_generation
        _cancel(self._cancel_watchdog)
        self._cancel_watchdog = None
        deadlines = tuple(
            self._stale_deadline(observation)
            for observation in self._source_observations.values()
            if observation.quality is SourceQuality.VALID
            and observation.source_last_reported is not None
        )
        future_deadlines = tuple(
            deadline for deadline in deadlines if deadline > reference_time
        )
        if not future_deadlines or self._shutdown:
            return
        self._cancel_watchdog = async_track_point_in_utc_time(
            self.hass,
            partial(self._async_watchdog_elapsed, generation=generation),
            min(future_deadlines),
        )

    def _stale_deadline(self, observation: SourceObservation[float]) -> datetime:
        source_last_reported = observation.source_last_reported
        if source_last_reported is None:
            raise ValueError("accepted source observation requires last_reported")
        return (
            source_last_reported
            + timedelta(seconds=self.configuration.options.source_stale_after_seconds)
            + _STALE_BOUNDARY_INCREMENT
        )

    async def _async_watchdog_elapsed(
        self,
        fire_time: datetime,
        *,
        generation: int,
    ) -> None:
        if self._shutdown or generation != self._watchdog_generation:
            return
        _cancel(self._cancel_watchdog)
        self._cancel_watchdog = None
        due_source_ids = {
            source_id
            for source_id, observation in self._source_observations.items()
            if observation.quality is SourceQuality.VALID
            and observation.source_last_reported is not None
            and self._stale_deadline(observation) <= fire_time
        }
        affected_zone_ids = {
            zone_id
            for source_id in due_source_ids
            for zone_id in self._source_id_to_zones.get(source_id, ())
        }
        if not affected_zone_ids:
            self._schedule_watchdog(fire_time)
            return
        self._publish_targeted(affected_zone_ids, fire_time)

    def _record_snapshot_activity(
        self,
        *,
        previous: EntryObservationSnapshot | None,
        current: EntryObservationSnapshot,
    ) -> None:
        """Produce only semantic activity, ignoring revisions and timestamps."""
        if previous is not None and previous.control_state is not current.control_state:
            if current.control_state is ControlState.DEGRADED:
                self._log_warning_once(
                    "control_state_degraded",
                    current.calculated_at,
                    "Observation runtime degraded: config_entry_id=%s "
                    "reason_code=control_state_degraded",
                    self.entry.entry_id,
                )
            else:
                _LOGGER.info(
                    "Observation runtime transition: config_entry_id=%s "
                    "previous_state=%s new_state=%s "
                    "reason_code=control_state_changed",
                    self.entry.entry_id,
                    previous.control_state.value,
                    current.control_state.value,
                )
            self.activity.record(
                activity_type=ActivityType.RUNTIME_STATE_CHANGED,
                reason_code=ActivityReason.CONTROL_STATE_CHANGED,
                severity=(
                    ActivitySeverity.WARNING
                    if current.control_state is ControlState.DEGRADED
                    else ActivitySeverity.INFO
                ),
                explanation="The observation runtime state changed.",
                detail={
                    "previous_state": previous.control_state.value,
                    "new_state": current.control_state.value,
                },
                timestamp=current.calculated_at,
            )

        previous_zones = (
            {} if previous is None else {zone.zone_id: zone for zone in previous.zones}
        )
        for current_zone in current.zones:
            previous_zone = previous_zones.get(current_zone.zone_id)
            self._record_source_activity(previous_zone, current_zone)

        previous_thermostats = (
            {}
            if previous is None
            else {item.entity_id: item for item in previous.thermostats}
        )
        for thermostat in current.thermostats:
            prior = previous_thermostats.get(thermostat.entity_id)
            zone_ids = self._thermostat_to_zones.get(thermostat.entity_id, ())
            if prior is None:
                if thermostat.capability_discovery.status.value == "unavailable":
                    for zone_id in zone_ids:
                        self.activity.record(
                            activity_type=(
                                ActivityType.THERMOSTAT_CAPABILITIES_CHANGED
                            ),
                            reason_code=(
                                ActivityReason.THERMOSTAT_CAPABILITIES_CHANGED
                            ),
                            severity=ActivitySeverity.WARNING,
                            explanation="Thermostat capabilities are unavailable.",
                            zone_id=zone_id,
                            timestamp=current.calculated_at,
                        )
                continue
            if _capability_semantics(prior) != _capability_semantics(thermostat):
                for zone_id in zone_ids:
                    self.activity.record(
                        activity_type=ActivityType.THERMOSTAT_CAPABILITIES_CHANGED,
                        reason_code=ActivityReason.THERMOSTAT_CAPABILITIES_CHANGED,
                        severity=(
                            ActivitySeverity.INFO
                            if thermostat.capability_discovery.capabilities is not None
                            else ActivitySeverity.WARNING
                        ),
                        explanation="Observed thermostat capabilities changed.",
                        zone_id=zone_id,
                        timestamp=current.calculated_at,
                    )
            if prior.state.hvac_mode != thermostat.state.hvac_mode:
                for zone_id in zone_ids:
                    self.activity.record(
                        activity_type=ActivityType.THERMOSTAT_OBSERVATION_CHANGED,
                        reason_code=ActivityReason.THERMOSTAT_MODE_CHANGED,
                        severity=(
                            ActivitySeverity.INFO
                            if thermostat.state.hvac_mode is not None
                            else ActivitySeverity.WARNING
                        ),
                        explanation="The observed thermostat mode changed.",
                        zone_id=zone_id,
                        timestamp=current.calculated_at,
                    )
            if _target_semantics(prior) != _target_semantics(thermostat):
                for zone_id in zone_ids:
                    self.activity.record(
                        activity_type=ActivityType.THERMOSTAT_OBSERVATION_CHANGED,
                        reason_code=ActivityReason.THERMOSTAT_TARGET_CHANGED,
                        severity=(
                            ActivitySeverity.INFO
                            if any(
                                value is not None
                                for value in _target_semantics(thermostat)
                            )
                            else ActivitySeverity.WARNING
                        ),
                        explanation="The observed thermostat target changed.",
                        zone_id=zone_id,
                        timestamp=current.calculated_at,
                    )

    def _record_source_activity(
        self,
        previous: ZoneObservation | None,
        current: ZoneObservation,
    ) -> None:
        previous_sources = {} if previous is None else _final_source_states(previous)
        for source_id, observation in _final_source_states(current).items():
            prior = previous_sources.get(source_id)
            current_semantics = (observation.quality, observation.exclusion_reason)
            if prior is None:
                if observation.quality is SourceQuality.VALID:
                    continue
                reason = ActivityReason.SOURCE_EXCLUDED
                explanation = "A configured observation source was excluded."
            else:
                prior_semantics = (prior.quality, prior.exclusion_reason)
                if prior_semantics == current_semantics:
                    continue
                if (
                    prior.quality is SourceQuality.VALID
                    and observation.quality is not SourceQuality.VALID
                ):
                    reason = ActivityReason.SOURCE_EXCLUDED
                    explanation = "A configured observation source was excluded."
                elif (
                    prior.quality is not SourceQuality.VALID
                    and observation.quality is SourceQuality.VALID
                ):
                    reason = ActivityReason.SOURCE_RECOVERED
                    explanation = "A configured observation source recovered."
                else:
                    reason = ActivityReason.SOURCE_EXCLUSION_CHANGED
                    explanation = "An observation source exclusion reason changed."
            if reason is ActivityReason.SOURCE_RECOVERED:
                _LOGGER.info(
                    "Observation source recovered: config_entry_id=%s "
                    "zone_id=%s source_id=%s reason_code=source_recovered",
                    self.entry.entry_id,
                    current.zone_id,
                    source_id,
                )
            elif observation.quality is not SourceQuality.VALID:
                self._log_warning_once(
                    f"source_excluded:{source_id}",
                    current.calculated_at,
                    "Observation source excluded: config_entry_id=%s "
                    "zone_id=%s source_id=%s reason_code=%s",
                    self.entry.entry_id,
                    current.zone_id,
                    source_id,
                    (
                        "source_excluded"
                        if observation.exclusion_reason is None
                        else observation.exclusion_reason.value
                    ),
                )
            self.activity.record(
                activity_type=ActivityType.SOURCE_QUALITY_CHANGED,
                reason_code=reason,
                severity=(
                    ActivitySeverity.INFO
                    if observation.quality is SourceQuality.VALID
                    else ActivitySeverity.WARNING
                ),
                explanation=explanation,
                zone_id=current.zone_id,
                detail={
                    "source_id": str(source_id),
                    "previous_quality": (
                        None if prior is None else prior.quality.value
                    ),
                    "new_quality": observation.quality.value,
                    "previous_exclusion_reason": (
                        None
                        if prior is None or prior.exclusion_reason is None
                        else prior.exclusion_reason.value
                    ),
                    "new_exclusion_reason": (
                        None
                        if observation.exclusion_reason is None
                        else observation.exclusion_reason.value
                    ),
                },
                timestamp=current.calculated_at,
            )

    def _now(self) -> datetime:
        result = self._now_fn()
        if result.tzinfo is None or result.utcoffset() is None:
            raise ValueError("now_fn must return a timezone-aware datetime")
        return result

    async def async_shutdown(self) -> None:
        """Idempotently cancel every owned subscription and timer."""
        await self._async_shutdown(remove_core_shutdown_job=True)

    async def _async_shutdown(self, *, remove_core_shutdown_job: bool) -> None:
        """Cancel owned resources, optionally removing the core-shutdown job."""
        if self._shutdown:
            if remove_core_shutdown_job:
                self.async_unregister_core_shutdown_job()
            return
        if remove_core_shutdown_job:
            self.async_unregister_core_shutdown_job()
        self._shutdown = True
        self._debounce_generation += 1
        self._reconciliation_generation += 1
        self._watchdog_generation += 1
        _cancel(self._cancel_state_change_subscription)
        _cancel(self._cancel_state_report_subscription)
        _cancel(self._cancel_debounce)
        _cancel(self._cancel_reconciliation)
        _cancel(self._cancel_watchdog)
        self._cancel_state_change_subscription = None
        self._cancel_state_report_subscription = None
        self._cancel_debounce = None
        self._cancel_reconciliation = None
        self._cancel_watchdog = None
        self._pending_zone_ids.clear()
        self._pending_thermostat_entity_ids.clear()
        if self.runtime_store is not None:
            await self.runtime_store.async_shutdown()
        self.activity.close()
        await super().async_shutdown()


def _append_unique[KeyT](
    index: dict[KeyT, list[ZoneId]],
    key: KeyT,
    zone_id: ZoneId,
) -> None:
    zones = index.setdefault(key, [])
    if zone_id not in zones:
        zones.append(zone_id)


def _empty_aggregation(calculated_at: datetime) -> SourceAggregationResult:
    return SourceAggregationResult(
        effective_value=None,
        spread=None,
        valid_source_ids=(),
        contributing_source_ids=(),
        fallback_source_id=None,
        excluded_observations=(),
        status=AggregationStatus.UNAVAILABLE,
        reasons=(AggregationReason.NO_VALID_SOURCES,),
        calculated_at=calculated_at,
    )


def _cancel(cancel: CALLBACK_TYPE | None) -> None:
    if cancel is not None:
        cancel()


def _final_source_states(
    zone: ZoneObservation,
) -> dict[ObservationSourceId, SourceObservation[float]]:
    result = {
        observation.source_id: observation
        for observation in (
            *zone.temperature_observations,
            *zone.humidity_observations,
        )
    }
    result.update(
        {
            observation.source_id: observation
            for observation in zone.temperature_aggregation.excluded_observations
        }
    )
    if zone.humidity_aggregation is not None:
        result.update(
            {
                observation.source_id: observation
                for observation in zone.humidity_aggregation.excluded_observations
            }
        )
    return result


def _target_semantics(
    thermostat: ThermostatRuntimeSnapshot,
) -> tuple[float | None, float | None, float | None]:
    state = thermostat.state
    return (
        state.target_temperature_c,
        state.target_low_c,
        state.target_high_c,
    )


def _capability_semantics(thermostat: ThermostatRuntimeSnapshot) -> tuple[object, ...]:
    discovery = thermostat.capability_discovery
    capabilities = discovery.capabilities
    if capabilities is None:
        return (discovery.status,)
    return (
        discovery.status,
        tuple(sorted(mode.value for mode in capabilities.hvac_modes)),
        int(capabilities.supported_features),
        capabilities.target_temperature,
        capabilities.target_temperature_range,
        capabilities.fan_modes,
        capabilities.preset_modes,
        capabilities.current_temperature_available,
        capabilities.current_humidity_available,
        capabilities.auxiliary_heat_observable,
        capabilities.stage_observable,
    )


def _thermostat_states_conflict(
    states: tuple[NormalizedClimateState, ...],
) -> bool:
    """Return whether multiple available thermostats disagree materially."""
    available = tuple(state for state in states if state.available)
    if len(available) < 2:
        return False

    def _different(values: tuple[object, ...]) -> bool:
        return len(set(values)) > 1

    return any(
        (
            _different(tuple(state.hvac_mode for state in available)),
            _different(tuple(state.hvac_action for state in available)),
            _different(
                tuple(
                    (
                        state.target_temperature_c,
                        state.target_low_c,
                        state.target_high_c,
                    )
                    for state in available
                )
            ),
        )
    )
