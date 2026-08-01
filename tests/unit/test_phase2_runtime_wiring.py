"""Task 19 live suppressed-policy and presentation-trace tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from types import MappingProxyType, SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.core import HomeAssistant

from custom_components.intelligent_climate.models import (
    DEFAULT_OPTIONS,
    DEFAULT_PHASE2_COMMAND_TIMING,
    DEFAULT_PHASE2_SAFETY_LIMITS,
    AggregationStatus,
    ControlExecutionState,
    ControlReason,
    ControlState,
    EntryObservationSnapshot,
    EquipmentGroupConfig,
    EquipmentGroupId,
    EquipmentRelationship,
    EquipmentType,
    LocalTime,
    NormalizedClimateState,
    ObservableBoolean,
    OperatingMode,
    Phase2ControlIntent,
    Phase2EquipmentGroupDocument,
    Phase2IntegrationOptions,
    Phase2RuntimeStoreDocument,
    Phase2RuntimeZoneState,
    Phase2ZoneConfig,
    PresentationContactState,
    PresentationControlContext,
    PresentationFanAction,
    PresentationHvacAction,
    ScheduleDocument,
    ScheduleOccupancyLabel,
    SchedulePeriod,
    SchedulePeriodId,
    ScheduleProfileId,
    ScheduleValidationContext,
    ScheduleZoneConstraints,
    SourceAggregationResult,
    TargetKind,
    TargetSpec,
    ThermostatBinding,
    ThermostatCapabilities,
    ThermostatCapabilityDiscovery,
    ThermostatCapabilityDiscoveryStatus,
    ThermostatRole,
    ThermostatRuntimeSnapshot,
    Weekday,
    WeeklyScheduleProfile,
    ZoneConfig,
    ZoneId,
    ZoneObservation,
    ZoneScheduleSet,
)
from custom_components.intelligent_climate.models.phase2_schema import (
    Phase2ShadowQualification,
)
from custom_components.intelligent_climate.models.policy_runtime import (
    Phase2PolicySnapshot,
    ZonePolicySnapshot,
)
from custom_components.intelligent_climate.presentation_trace import (
    PresentationTraceRuntime,
    _fan_only_action,
    _hvac_action,
)
from custom_components.intelligent_climate.runtime import Phase2CoordinatorRuntime
from custom_components.intelligent_climate.schedule_storage import ScheduleStore

NOW = datetime(2026, 7, 27, 16, tzinfo=UTC)
ENTRY_ID = "entry-1"
THERMOSTAT = "climate.main"
GROUP_ID = EquipmentGroupId.parse("b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3")
ZONE_ID = ZoneId.parse("99246285-6f02-4e8a-94ed-bdfd4a5e62c4")
PROFILE_ID = ScheduleProfileId.parse("80b2289f-8d5a-48b2-9a34-d6efad8c99c7")
PERIOD_ID = SchedulePeriodId.parse("553c9de9-e4f8-485f-8231-3741bec69b7f")


def _zone_config() -> ZoneConfig:
    return ZoneConfig(
        zone_id=ZONE_ID,
        name="Dining Room",
        thermostat_entity_ids=(THERMOSTAT,),
        temperature_sources=(),
        humidity_sources=(),
        window_door_entity_ids=(),
        occupancy_entity_ids=(),
        stage_entity_ids=(),
        fan_entity_ids=(),
    )


def _aggregation(value: float | None) -> SourceAggregationResult:
    return SourceAggregationResult(
        effective_value=value,
        spread=None,
        valid_source_ids=(),
        contributing_source_ids=(),
        fallback_source_id=None,
        excluded_observations=(),
        status=(
            AggregationStatus.HEALTHY
            if value is not None
            else AggregationStatus.UNAVAILABLE
        ),
        reasons=(),
        calculated_at=NOW,
    )


def _thermostat(
    *,
    available: bool = True,
    hvac_action: HVACAction | None = HVACAction.HEATING,
    fan_mode: str | None = None,
) -> ThermostatRuntimeSnapshot:
    state = NormalizedClimateState(
        entity_id=THERMOSTAT,
        available=available,
        hvac_mode=HVACMode.HEAT,
        hvac_action=hvac_action,
        current_temperature_c=19.0,
        target_temperature_c=19.0,
        target_low_c=None,
        target_high_c=None,
        current_humidity_pct=None,
        fan_mode=fan_mode,
        preset_mode=None,
        auxiliary_heat_state=ObservableBoolean.NOT_OBSERVABLE,
        context_id=None,
        last_changed=NOW,
        last_updated=NOW,
    )
    capabilities = ThermostatCapabilities(
        entity_id=THERMOSTAT,
        hvac_modes=frozenset({HVACMode.HEAT}),
        supported_features=ClimateEntityFeature.TARGET_TEMPERATURE,
        target_temperature=True,
        target_temperature_range=False,
        fan_modes=(),
        preset_modes=(),
        current_temperature_available=True,
        current_humidity_available=False,
        auxiliary_heat_observable=False,
        stage_observable=False,
        discovered_at=NOW,
    )
    return ThermostatRuntimeSnapshot(
        entity_id=THERMOSTAT,
        state=state,
        capability_discovery=ThermostatCapabilityDiscovery(
            status=ThermostatCapabilityDiscoveryStatus.COMPLETE,
            capabilities=capabilities,
        ),
    )


def _observation(
    *,
    revision: int = 1,
    temperature: float = 19.0,
    thermostat_available: bool = True,
    hvac_action: HVACAction | None = HVACAction.HEATING,
    fan_mode: str | None = None,
) -> EntryObservationSnapshot:
    thermostat = _thermostat(
        available=thermostat_available,
        hvac_action=hvac_action,
        fan_mode=fan_mode,
    )
    return EntryObservationSnapshot(
        entry_id=ENTRY_ID,
        equipment_group_id=GROUP_ID,
        control_state=ControlState.OBSERVING,
        reconciling=False,
        revision=revision,
        thermostats=(thermostat,),
        zones=(
            ZoneObservation(
                zone_id=ZONE_ID,
                temperature_observations=(),
                humidity_observations=(),
                temperature_aggregation=_aggregation(temperature),
                humidity_aggregation=None,
                thermostat_states=(thermostat.state,),
                sensor_data_degraded=False,
                thermostat_data_degraded=False,
                calculated_at=NOW,
            ),
        ),
        calculated_at=NOW,
    )


def _context() -> ScheduleValidationContext:
    return ScheduleValidationContext(
        entry_id=ENTRY_ID,
        equipment_group_id=GROUP_ID,
        time_zone="America/New_York",
        zone_constraints={
            ZONE_ID: ScheduleZoneConstraints(
                zone_id=ZONE_ID,
                supports_single_target=True,
                supports_target_range=False,
                single_target_min_c=7.2,
                single_target_max_c=26.7,
                heat_target_min_c=7.2,
                heat_target_max_c=26.7,
                cool_target_min_c=15.6,
                cool_target_max_c=35.0,
                minimum_heat_cool_separation_c=1.7,
            )
        },
    )


def test_presentation_uses_hvac_action_and_fan_mode_as_distinct_facts() -> None:
    """Cooling drives the blower but does not imply fan-only circulation."""
    cooling = _thermostat(
        hvac_action=HVACAction.COOLING,
        fan_mode="off",
    ).state
    assert _hvac_action(cooling) is PresentationHvacAction.COOLING
    assert _fan_only_action(cooling) is PresentationFanAction.OFF

    circulating = _thermostat(
        hvac_action=HVACAction.IDLE,
        fan_mode="on",
    ).state
    assert _hvac_action(circulating) is PresentationHvacAction.IDLE
    assert _fan_only_action(circulating) is PresentationFanAction.ON


def test_presentation_distinguishes_unavailable_and_not_reported() -> None:
    unavailable = _thermostat(available=False, hvac_action=None).state
    assert _hvac_action(unavailable) is PresentationHvacAction.UNAVAILABLE
    assert _fan_only_action(unavailable) is PresentationFanAction.UNAVAILABLE

    not_reported = _thermostat(hvac_action=None, fan_mode=None).state
    assert _hvac_action(not_reported) is PresentationHvacAction.NOT_REPORTED
    assert _fan_only_action(not_reported) is PresentationFanAction.NOT_REPORTED


def _schedule() -> ScheduleDocument:
    period = SchedulePeriod(
        period_id=PERIOD_ID,
        local_start=LocalTime(0, 0),
        label="Home",
        occupancy_label=ScheduleOccupancyLabel.HOME,
        target=TargetSpec(TargetKind.SINGLE, 21.0, None, None),
        tolerance_c=0.3,
    )
    profile = WeeklyScheduleProfile(
        profile_id=PROFILE_ID,
        name="Home",
        enabled=True,
        days=MappingProxyType(dict.fromkeys(Weekday, (period,))),
    )
    return ScheduleDocument(
        schedule_schema_version=1,
        entry_id=ENTRY_ID,
        equipment_group_id=GROUP_ID,
        time_zone="America/New_York",
        revision=1,
        zones=MappingProxyType(
            {
                ZONE_ID: ZoneScheduleSet(
                    zone_id=ZONE_ID,
                    enabled=True,
                    selected_profile_id=PROFILE_ID,
                    profiles=(profile,),
                )
            }
        ),
        saved_at_utc=NOW - timedelta(hours=1),
    )


def _migration(mode: OperatingMode = OperatingMode.SCHEDULED_SHADOW) -> Any:
    group = EquipmentGroupConfig(
        equipment_group_id=GROUP_ID,
        name="Main",
        equipment_type=EquipmentType.AIR_SOURCE_HEAT_PUMP,
        relationship=EquipmentRelationship.SINGLE_SYSTEM,
        thermostats=(ThermostatBinding(THERMOSTAT, ThermostatRole.PRIMARY),),
        shared_policy=None,
    )
    qualification = Phase2ShadowQualification(
        started_at_utc=None,
        evaluated_decisions=0,
        valid_evaluations=0,
        material_transitions_by_zone=MappingProxyType({ZONE_ID: 0}),
        blocking_fault_codes=(),
    )
    return SimpleNamespace(
        config=Phase2EquipmentGroupDocument(
            equipment_group=group,
            automation_enabled=mode is OperatingMode.SCHEDULED_SHADOW,
            desired_operating_mode=mode,
            command_authority_entity_ids=(THERMOSTAT,),
            authority_review_required=False,
            acknowledged_time_zone="America/New_York",
        ),
        options=Phase2IntegrationOptions(
            observation=DEFAULT_OPTIONS,
            safety_limits=DEFAULT_PHASE2_SAFETY_LIMITS,
            command_timing=replace(
                DEFAULT_PHASE2_COMMAND_TIMING,
                startup_quiet_period_seconds=120,
            ),
        ),
        zones=(
            Phase2ZoneConfig(
                zone=_zone_config(),
                contact_bindings=(),
                occupancy_bindings=(),
                fan_bindings=(),
            ),
        ),
        runtime=Phase2RuntimeStoreDocument(
            entry_id=ENTRY_ID,
            equipment_group_id=GROUP_ID,
            saved_at=NOW - timedelta(minutes=5),
            last_clean_shutdown=True,
            zones=MappingProxyType(
                {
                    ZONE_ID: Phase2RuntimeZoneState(
                        control_state=ControlExecutionState.RECONCILING,
                        last_live_observation_at=None,
                        comparison_temperature_c=None,
                        comparison_humidity_pct=None,
                        last_decision_id=None,
                    )
                }
            ),
            source_baselines=MappingProxyType({}),
            decisions=(),
            command_journal=(),
            overrides=(),
            transition_ledger=(),
            occupancy_timers=(),
            contact_timers=(),
            fan_runtime_budget=(),
            shadow_qualification=qualification,
            failure_counters=(),
            control_intent=Phase2ControlIntent(
                automation_enabled=mode is OperatingMode.SCHEDULED_SHADOW,
                desired_operating_mode=mode,
                active_control_armed=False,
                time_zone_acknowledgement_required=False,
            ),
        ),
    )


class _ScheduleStore:
    def __init__(self, document: ScheduleDocument | None) -> None:
        self.document = document
        self.validation_context = _context()


class _Trace:
    def __init__(self) -> None:
        self.calls: list[tuple[EntryObservationSnapshot, Phase2PolicySnapshot]] = []

    def record_snapshot(
        self,
        observation: EntryObservationSnapshot,
        policy: Phase2PolicySnapshot,
    ) -> bool:
        self.calls.append((observation, policy))
        return True

    async def async_shutdown(self) -> None:
        return None


async def test_scheduled_shadow_runs_complete_safety_path_without_service_call(
    hass: HomeAssistant,
) -> None:
    trace = _Trace()
    runtime = Phase2CoordinatorRuntime(
        migration=_migration(),
        schedule_store=cast(ScheduleStore, _ScheduleStore(_schedule())),
        presentation_trace=cast(PresentationTraceRuntime, trace),
        started_at_utc=NOW - timedelta(seconds=121),
    )

    with patch.object(type(hass.services), "async_call") as service_call:
        snapshot = await runtime.async_process_snapshot(_observation())

    assert snapshot.control_state is ControlExecutionState.SHADOW_QUALIFYING
    assert snapshot.zones[0].would_command
    assert snapshot.zones[0].safety_decision is not None
    assert snapshot.zones[0].safety_decision.reason_code.value == "shadow_only"
    assert runtime.qualification.evaluated_decisions == 1
    assert runtime.qualification.valid_evaluations == 1
    assert len(runtime.shadow_sink.history) == 1
    assert trace.calls[-1][1] is snapshot
    service_call.assert_not_called()


async def test_missing_schedule_records_blocked_shadow_evidence_without_command(
    hass: HomeAssistant,
) -> None:
    runtime = Phase2CoordinatorRuntime(
        migration=_migration(),
        schedule_store=cast(ScheduleStore, _ScheduleStore(None)),
        presentation_trace=cast(PresentationTraceRuntime, _Trace()),
        started_at_utc=NOW - timedelta(seconds=121),
    )
    with patch.object(type(hass.services), "async_call") as service_call:
        snapshot = await runtime.async_process_snapshot(_observation())

    assert snapshot.control_state is ControlExecutionState.SAFE_FALLBACK
    assert not snapshot.zones[0].would_command
    assert runtime.qualification.evaluated_decisions == 1
    assert runtime.qualification.valid_evaluations == 0
    service_call.assert_not_called()


async def test_presentation_trace_buckets_material_changes_and_flushes(
    hass: HomeAssistant,
) -> None:
    trace = PresentationTraceRuntime(
        hass,
        entry_id=ENTRY_ID,
        equipment_group_id=GROUP_ID,
        zone_ids=(ZONE_ID,),
        now_fn=lambda: NOW,
    )
    policy = Phase2PolicySnapshot(
        entry_id=ENTRY_ID,
        observation_revision=1,
        evaluated_at_utc=NOW,
        control_state=ControlExecutionState.OBSERVING,
        reason_code=ControlReason.OBSERVE_ONLY_SELECTED,
        zones=(
            ZonePolicySnapshot(
                zone_id=ZONE_ID,
                control_state=ControlExecutionState.OBSERVING,
                reason_code=ControlReason.OBSERVE_ONLY_SELECTED,
                scheduled_target=None,
                effective_target=None,
                profile_id=None,
                period_id=None,
                next_transition_utc=None,
                safety_decision=None,
                would_command=False,
            ),
        ),
        shadow_readiness=None,
        next_evaluation_at_utc=None,
    )
    load = AsyncMock(return_value=None)
    save = AsyncMock()
    with (
        patch.object(trace._store, "async_load", load),
        patch.object(trace._store, "async_save", save),
    ):
        await trace.async_load()
        assert trace.record_snapshot(_observation(), policy)
        assert not trace.record_snapshot(_observation(), policy)
        assert len(trace.document.samples_by_zone[ZONE_ID]) == 1
        await trace.async_shutdown()
    save.assert_awaited_once()


async def test_presentation_trace_records_aggregate_contact_and_control_context(
    hass: HomeAssistant,
) -> None:
    """The trace stores no contact IDs, only the zone-level factual state."""
    hass.states.async_set("binary_sensor.dining_window", "on")
    trace = PresentationTraceRuntime(
        hass,
        entry_id=ENTRY_ID,
        equipment_group_id=GROUP_ID,
        zone_ids=(ZONE_ID,),
        contact_entity_ids_by_zone={
            ZONE_ID: ("binary_sensor.dining_window",),
        },
        now_fn=lambda: NOW,
    )
    policy = Phase2PolicySnapshot(
        entry_id=ENTRY_ID,
        observation_revision=1,
        evaluated_at_utc=NOW,
        control_state=ControlExecutionState.WINDOW_SUSPENDED,
        reason_code=ControlReason.WINDOW_OPEN,
        zones=(
            ZonePolicySnapshot(
                zone_id=ZONE_ID,
                control_state=ControlExecutionState.WINDOW_SUSPENDED,
                reason_code=ControlReason.WINDOW_OPEN,
                scheduled_target=None,
                effective_target=None,
                profile_id=None,
                period_id=None,
                next_transition_utc=None,
                safety_decision=None,
                would_command=False,
            ),
        ),
        shadow_readiness=None,
        next_evaluation_at_utc=None,
    )
    with (
        patch.object(trace._store, "async_load", AsyncMock(return_value=None)),
        patch.object(trace._store, "async_save", AsyncMock()),
    ):
        await trace.async_load()
        assert trace.record_snapshot(_observation(), policy)
        point = trace.document.samples_by_zone[ZONE_ID][-1]
        assert point.contact_state is PresentationContactState.OPEN
        assert point.control_context is PresentationControlContext.WINDOW_SUSPENDED
        encoded = str(trace.document)
        assert "binary_sensor.dining_window" not in encoded
        await trace.async_shutdown()


async def test_presentation_trace_defers_material_change_until_time_advances(
    hass: HomeAssistant,
) -> None:
    """Reload/replay never appends a new point at a non-newer timestamp."""
    trace = PresentationTraceRuntime(
        hass,
        entry_id=ENTRY_ID,
        equipment_group_id=GROUP_ID,
        zone_ids=(ZONE_ID,),
        now_fn=lambda: NOW,
    )
    policy = Phase2PolicySnapshot(
        entry_id=ENTRY_ID,
        observation_revision=1,
        evaluated_at_utc=NOW,
        control_state=ControlExecutionState.OBSERVING,
        reason_code=ControlReason.OBSERVE_ONLY_SELECTED,
        zones=(
            ZonePolicySnapshot(
                zone_id=ZONE_ID,
                control_state=ControlExecutionState.OBSERVING,
                reason_code=ControlReason.OBSERVE_ONLY_SELECTED,
                scheduled_target=None,
                effective_target=None,
                profile_id=None,
                period_id=None,
                next_transition_utc=None,
                safety_decision=None,
                would_command=False,
            ),
        ),
        shadow_readiness=None,
        next_evaluation_at_utc=None,
    )
    suspended = replace(
        policy,
        control_state=ControlExecutionState.WINDOW_SUSPENDED,
        reason_code=ControlReason.WINDOW_OPEN,
        zones=(
            replace(
                policy.zones[0],
                control_state=ControlExecutionState.WINDOW_SUSPENDED,
                reason_code=ControlReason.WINDOW_OPEN,
            ),
        ),
    )
    with (
        patch.object(trace._store, "async_load", AsyncMock(return_value=None)),
        patch.object(trace._store, "async_save", AsyncMock()),
    ):
        await trace.async_load()
        assert trace.record_snapshot(_observation(), policy)
        assert not trace.record_snapshot(_observation(), suspended)
        later_observation = replace(
            _observation(),
            revision=2,
            calculated_at=NOW + timedelta(seconds=1),
        )
        later_policy = replace(
            suspended,
            observation_revision=2,
            evaluated_at_utc=NOW + timedelta(seconds=1),
        )
        assert trace.record_snapshot(later_observation, later_policy)
        points = trace.document.samples_by_zone[ZONE_ID]
        assert len(points) == 2
        assert points[-1].control_context is PresentationControlContext.WINDOW_SUSPENDED
        assert points[-1].timestamp_utc == NOW + timedelta(seconds=1)
        await trace.async_shutdown()
