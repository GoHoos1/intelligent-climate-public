"""Entry-scoped Phase 2 suppressed-policy composition and coordinator bridge."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from homeassistant.components.climate.const import HVACMode

from .arbitration.resolver import (
    ArbitrationOutcome,
    SharedArbitrationDecision,
    SharedArbitrationInput,
    resolve_shared_equipment,
)
from .control.precedence import ControlPrecedenceInput, resolve_control_precedence
from .control.safety import SafetyGateInput, evaluate_safety_gate
from .migration import Phase2MigrationState
from .models.arbitration import (
    DemandSuppression,
    EquipmentDirection,
    RelatedThermostatDisposition,
    RelatedThermostatObservation,
    SharedEquipmentArbitrationPolicy,
    ZoneDemand,
    ZoneDemandDirection,
)
from .models.command import (
    CommandAuthority,
    CommandCause,
    CommandControlledField,
    CommandKind,
    NormalizedCommandValues,
    NormalizedStateEvidence,
)
from .models.control import ControlExecutionState
from .models.identifiers import CommandId, DecisionId, SafetyEvaluationId, ZoneId
from .models.modes import OperatingMode
from .models.override import ControlledField, OverrideValidationContext
from .models.phase2_schema import Phase2MigrationDryRun
from .models.plan import build_command_plan
from .models.policy_runtime import Phase2PolicySnapshot, ZonePolicySnapshot
from .models.runtime import EntryObservationSnapshot, ThermostatRuntimeSnapshot
from .models.safety import (
    SafetyAuthorityEvidence,
    SafetyCapabilitySnapshot,
    SafetyCommandCandidate,
    SafetyCorrelationState,
    SafetyDisposition,
    SafetyGateDecision,
    SafetyOwnership,
    SafetyReasonCode,
    SafetyTargetDirection,
    SafetyTimingEvidence,
)
from .models.schedule import (
    ScheduleDocument,
    ScheduleValidationContext,
    ScheduleZoneConstraints,
    TargetKind,
    TargetSpec,
)
from .models.schema import EquipmentRelationship
from .models.shadow import ShadowBlockingFault, ShadowReadinessEntitySnapshot
from .presentation_trace import PresentationTraceRuntime
from .schedule.evaluate import (
    ScheduleEvaluation,
    ScheduleEvaluationError,
    evaluate_schedule,
)
from .schedule_storage import ScheduleStore
from .shadow.qualification import evaluate_shadow_readiness
from .shadow.sink import ShadowCommandSink

type Phase2RuntimeConfiguration = Phase2MigrationDryRun | Phase2MigrationState

if TYPE_CHECKING:
    from .models.phase2_schema import Phase2ShadowQualification


class _SnapshotClock:
    """Mutable event-loop clock updated only at explicit coordinator evaluations."""

    def __init__(self, value: datetime) -> None:
        self.value = _utc(value)

    def now_utc(self) -> datetime:
        """Return the currently injected evaluation instant."""
        return self.value


class Phase2CoordinatorRuntime:
    """Compose pure policy stages and physically inert sinks for one entry."""

    def __init__(
        self,
        *,
        migration: Phase2RuntimeConfiguration,
        schedule_store: ScheduleStore,
        presentation_trace: PresentationTraceRuntime,
        started_at_utc: datetime,
    ) -> None:
        self.migration = migration
        self.schedule_store = schedule_store
        self.presentation_trace = presentation_trace
        self._clock = _SnapshotClock(started_at_utc)
        zone_ids = tuple(item.zone.zone_id for item in migration.zones)
        self.shadow_sink = ShadowCommandSink(
            clock=self._clock,
            qualification=migration.runtime.shadow_qualification,
            history=(),
            all_zone_ids=zone_ids,
            enabled_zone_ids=zone_ids,
        )
        self.started_at_utc = _utc(started_at_utc)
        self._last_periods: dict[ZoneId, object] = {}
        self._snapshot: Phase2PolicySnapshot | None = None

    @property
    def snapshot(self) -> Phase2PolicySnapshot | None:
        """Return the latest immutable policy projection."""
        return self._snapshot

    @property
    def qualification(self) -> Phase2ShadowQualification:
        """Return the current restart-safe Shadow qualification record."""
        return self.shadow_sink.qualification

    @property
    def schedule_validation_context(self) -> ScheduleValidationContext:
        """Expose the authoritative backend validation context."""
        return self.schedule_store.validation_context

    async def async_process_snapshot(
        self, observation: EntryObservationSnapshot
    ) -> Phase2PolicySnapshot:
        """Evaluate one complete live snapshot and record only suppressed output."""
        now = _utc(observation.calculated_at)
        self._clock.value = now
        intent = self.migration.runtime.control_intent
        schedule = self.schedule_store.document
        readiness = self._readiness(now)
        thermostat_available = bool(observation.thermostats) and all(
            item.state.available for item in observation.thermostats
        )
        capabilities_valid = bool(observation.thermostats) and all(
            item.capability_discovery.capabilities is not None
            for item in observation.thermostats
        )
        sensors_valid = bool(observation.zones) and all(
            not zone.sensor_data_degraded for zone in observation.zones
        )
        precedence = resolve_control_precedence(
            ControlPrecedenceInput(
                operating_mode=intent.desired_operating_mode,
                automation_enabled=intent.automation_enabled,
                loaded=True,
                reconciling=observation.reconciling,
                thermostat_available=thermostat_available,
                capability_valid=capabilities_valid,
                required_autonomous_sensors_valid=sensors_valid,
                schedule_available=schedule is not None,
                control_authority_valid=self._authority_valid,
                shadow_qualified=readiness.ready,
                active_control_armed=intent.active_control_armed,
                time_zone_acknowledgement_required=(
                    intent.time_zone_acknowledgement_required
                ),
            )
        )
        evaluations = self._schedule_evaluations(schedule, observation, now)
        arbitration = self._arbitrate(evaluations, observation)
        zone_results: list[ZonePolicySnapshot] = []
        next_deadlines: list[datetime] = []
        latest_readiness = readiness
        for zone in observation.zones:
            schedule_result = evaluations.get(zone.zone_id)
            if schedule_result is not None:
                next_deadlines.append(schedule_result.next_boundary_utc)
            effective_target = self._effective_target(
                zone.zone_id,
                None if schedule_result is None else schedule_result.effective_target,
                now,
            )
            safety: SafetyGateDecision | None = None
            would_command = False
            if intent.desired_operating_mode is OperatingMode.SCHEDULED_SHADOW:
                (
                    safety,
                    latest_readiness,
                    would_command,
                ) = await self._evaluate_shadow_zone(
                    observation,
                    zone.zone_id,
                    schedule_result,
                    effective_target,
                    precedence.state,
                    arbitration,
                    now,
                )
            zone_results.append(
                ZonePolicySnapshot(
                    zone_id=zone.zone_id,
                    control_state=precedence.state,
                    reason_code=precedence.reason,
                    scheduled_target=(
                        None if schedule_result is None else schedule_result.base_target
                    ),
                    effective_target=effective_target,
                    profile_id=(
                        None if schedule_result is None else schedule_result.profile_id
                    ),
                    period_id=(
                        None
                        if schedule_result is None
                        else schedule_result.base_period_id
                    ),
                    next_transition_utc=(
                        None
                        if schedule_result is None
                        else schedule_result.next_material_transition_utc
                    ),
                    safety_decision=safety,
                    would_command=would_command,
                )
            )
        snapshot = Phase2PolicySnapshot(
            entry_id=observation.entry_id,
            observation_revision=observation.revision,
            evaluated_at_utc=now,
            control_state=precedence.state,
            reason_code=precedence.reason,
            zones=tuple(zone_results),
            shadow_readiness=latest_readiness,
            next_evaluation_at_utc=min(next_deadlines, default=None),
        )
        self._snapshot = snapshot
        self.presentation_trace.record_snapshot(observation, snapshot)
        return snapshot

    async def async_shutdown(self) -> None:
        """Flush only the auxiliary trace; never restore or command equipment."""
        await self.presentation_trace.async_shutdown()

    def async_schedule_updated(self) -> None:
        """Invalidate period identity after an atomic schedule replacement."""
        self._last_periods.clear()

    @property
    def _authority_valid(self) -> bool:
        config = self.migration.config
        return (
            not config.authority_review_required
            and len(config.command_authority_entity_ids) == 1
        )

    def _readiness(self, now: datetime) -> ShadowReadinessEntitySnapshot:
        zone_ids = tuple(item.zone.zone_id for item in self.migration.zones)
        return evaluate_shadow_readiness(
            self.shadow_sink.qualification,
            all_zone_ids=zone_ids,
            enabled_zone_ids=zone_ids,
            now_utc=now,
        )

    def _schedule_evaluations(
        self,
        schedule: ScheduleDocument | None,
        observation: EntryObservationSnapshot,
        now: datetime,
    ) -> dict[ZoneId, ScheduleEvaluation]:
        if schedule is None:
            return {}
        result: dict[ZoneId, ScheduleEvaluation] = {}
        for zone in observation.zones:
            try:
                result[zone.zone_id] = evaluate_schedule(
                    schedule, zone_id=zone.zone_id, at=now
                )
            except ScheduleEvaluationError:
                continue
        return result

    def _effective_target(
        self,
        zone_id: ZoneId,
        scheduled: TargetSpec | None,
        now: datetime,
    ) -> TargetSpec | None:
        """Apply the current typed override stage; contact/occupancy default inert."""
        if scheduled is None:
            return None
        from .models.override import OverrideState, decode_manual_override
        from .override.state_machine import evaluate_override_lifecycle

        for raw in self.migration.runtime.overrides:
            try:
                override = decode_manual_override(
                    raw,
                    validation_context=OverrideValidationContext(
                        entry_id=self.migration.runtime.entry_id,
                        equipment_group_id=(
                            self.migration.config.equipment_group.equipment_group_id
                        ),
                        controlled_fields_by_zone={
                            item.zone.zone_id: frozenset(ControlledField)
                            for item in self.migration.zones
                        },
                    ),
                )
            except KeyError, TypeError, ValueError:
                continue
            if override.zone_id != zone_id:
                continue
            transition = evaluate_override_lifecycle(override, at_utc=now)
            active = transition.override
            if active.state is not OverrideState.ACTIVE:
                continue
            values = active.requested_values
            if ControlledField.TARGET in active.controlled_fields:
                return TargetSpec(TargetKind.SINGLE, values.target_c, None, None)
            if ControlledField.RANGE in active.controlled_fields:
                return TargetSpec(
                    TargetKind.RANGE,
                    None,
                    values.heat_target_c,
                    values.cool_target_c,
                )
        return scheduled

    def _arbitrate(
        self,
        evaluations: dict[ZoneId, ScheduleEvaluation],
        observation: EntryObservationSnapshot,
    ) -> SharedArbitrationDecision | None:
        group = self.migration.config.equipment_group
        if group.relationship is not EquipmentRelationship.SHARED_ZONED:
            return None
        priority = (
            ()
            if group.shared_policy is None
            else group.shared_policy.zone_priority_order
        )
        demands = tuple(
            self._zone_demand(zone_id, evaluations.get(zone_id), observation)
            for zone_id in priority
        )
        policy = SharedEquipmentArbitrationPolicy(
            equipment_group_id=group.equipment_group_id,
            relationship=group.relationship,
            configured_thermostat_entity_ids=tuple(
                item.entity_id for item in group.thermostats
            ),
            command_authority_entity_ids=(
                self.migration.config.command_authority_entity_ids
            ),
            zone_priority_order=priority,
            authority_reviewed=not self.migration.config.authority_review_required,
        )
        related = tuple(
            RelatedThermostatObservation(
                entity_id=item.entity_id,
                disposition=_related_disposition(item),
                origin_certain=item.state.available,
            )
            for item in observation.thermostats
        )
        return resolve_shared_equipment(
            SharedArbitrationInput(
                policy=policy,
                demands=demands,
                equipment_direction=_equipment_direction(observation),
                related_observations=related,
            )
        )

    def _zone_demand(
        self,
        zone_id: ZoneId,
        evaluation: ScheduleEvaluation | None,
        observation: EntryObservationSnapshot,
    ) -> ZoneDemand:
        zone = next(item for item in observation.zones if item.zone_id == zone_id)
        current = zone.effective_temperature_c
        if evaluation is None or current is None:
            return ZoneDemand(
                zone_id,
                ZoneDemandDirection.SUPPRESSED,
                0.0,
                None,
                DemandSuppression.INVALID,
            )
        target = evaluation.effective_target
        mode = zone.thermostat_states[0].hvac_mode if zone.thermostat_states else None
        if target.kind is TargetKind.SINGLE:
            if target.target_c is None or mode not in {HVACMode.HEAT, HVACMode.COOL}:
                return ZoneDemand(
                    zone_id,
                    ZoneDemandDirection.SUPPRESSED,
                    0.0,
                    None,
                    DemandSuppression.INVALID,
                )
            direction = _demand_direction(mode, current, target.target_c)
            return ZoneDemand(
                zone_id,
                direction,
                abs(target.target_c - current),
                target.target_c,
            )
        if (
            mode not in {HVACMode.HEAT_COOL, HVACMode.AUTO}
            or target.heat_target_c is None
            or target.cool_target_c is None
        ):
            return ZoneDemand(
                zone_id,
                ZoneDemandDirection.SUPPRESSED,
                0.0,
                None,
                DemandSuppression.INVALID,
            )
        if current < target.heat_target_c:
            direction = ZoneDemandDirection.HEAT
            requested_target = target.heat_target_c
        elif current > target.cool_target_c:
            direction = ZoneDemandDirection.COOL
            requested_target = target.cool_target_c
        else:
            direction = ZoneDemandDirection.SATISFIED
            requested_target = None
        return ZoneDemand(
            zone_id,
            direction,
            0.0 if requested_target is None else abs(requested_target - current),
            requested_target,
        )

    async def _evaluate_shadow_zone(
        self,
        observation: EntryObservationSnapshot,
        zone_id: ZoneId,
        schedule: ScheduleEvaluation | None,
        target: TargetSpec | None,
        control_state: ControlExecutionState,
        arbitration: SharedArbitrationDecision | None,
        now: datetime,
    ) -> tuple[SafetyGateDecision, ShadowReadinessEntitySnapshot, bool]:
        safety_id = SafetyEvaluationId.new()
        zone = next(item for item in observation.zones if item.zone_id == zone_id)
        fault: ShadowBlockingFault | None = None
        reason: SafetyReasonCode | None = None
        if schedule is None or target is None:
            fault = ShadowBlockingFault.CONFIGURATION
            reason = SafetyReasonCode.CONTROL_STATE_BLOCKED
        elif zone.sensor_data_degraded:
            fault = ShadowBlockingFault.SENSOR
            reason = SafetyReasonCode.PRECONDITION_UNAVAILABLE
        elif not zone.thermostat_states or not zone.thermostat_states[0].available:
            fault = ShadowBlockingFault.THERMOSTAT_UNAVAILABLE
            reason = SafetyReasonCode.PRECONDITION_UNAVAILABLE
        thermostat = _thermostat_for_zone(zone_id, observation, self.migration)
        if thermostat is None or thermostat.capability_discovery.capabilities is None:
            fault = ShadowBlockingFault.CAPABILITY
            reason = SafetyReasonCode.CAPABILITY_UNAVAILABLE
        elif target is not None and not _target_matches_hvac_mode(
            target, thermostat.state.hvac_mode
        ):
            fault = ShadowBlockingFault.SAFETY_EVALUATION
            reason = SafetyReasonCode.HVAC_MODE_UNSUPPORTED
        if reason is not None:
            decision = _blocked_decision(safety_id, reason)
            result = await self.shadow_sink.async_record_evaluation(
                plan=None,
                safety_decision=decision,
                material_transition_zone_id=None,
                active_faults=(fault or ShadowBlockingFault.SAFETY_EVALUATION,),
            )
            return decision, result.readiness, False
        assert thermostat is not None and target is not None and schedule is not None
        candidate = _candidate(
            safety_id=safety_id,
            observation=observation,
            thermostat=thermostat,
            zone_id=zone_id,
            target=target,
            now=now,
        )
        ownership = SafetyOwnership(
            entry_id=observation.entry_id,
            equipment_group_id=observation.equipment_group_id,
            zone_ids=tuple(item.zone_id for item in observation.zones),
            relationship=self.migration.config.equipment_group.relationship,
            owned_entity_ids=tuple(
                item.entity_id
                for item in self.migration.config.equipment_group.thermostats
            ),
            command_authority_entity_ids=(
                self.migration.config.command_authority_entity_ids
            ),
            authority_reviewed=not self.migration.config.authority_review_required,
        )
        capabilities = _capability_snapshot(
            thermostat, target, self.migration.options.safety_limits
        )
        current = candidate.observed_precondition
        decision = evaluate_safety_gate(
            SafetyGateInput(
                candidate=candidate,
                ownership=ownership,
                capabilities=capabilities,
                authority=SafetyAuthorityEvidence(
                    operating_mode=OperatingMode.SCHEDULED_SHADOW,
                    control_state=control_state,
                    manual_intent_authorized=False,
                    shadow_qualified=self._readiness(now).ready,
                    active_control_armed=False,
                ),
                timing_evidence=SafetyTimingEvidence(
                    runtime_started_at_utc=self.started_at_utc
                ),
                safety_limits=self.migration.options.safety_limits,
                command_timing=self.migration.options.command_timing,
                current_state=current,
                correlation_state=SafetyCorrelationState.CLEAR,
                now_utc=now,
                arbitration=arbitration,
            )
        )
        plan = None
        if decision.reason_code is SafetyReasonCode.SHADOW_ONLY:
            plan = build_command_plan(
                candidate,
                decision,
                command_id=CommandId.new(),
                decision_id=DecisionId.new(),
                user_context_id=None,
            )
        previous_period = self._last_periods.get(zone_id)
        material_zone = (
            zone_id
            if previous_period is not None
            and previous_period != schedule.base_period_id
            else None
        )
        self._last_periods[zone_id] = schedule.base_period_id
        faults = _faults_for_decision(decision, arbitration)
        result = await self.shadow_sink.async_record_evaluation(
            plan=plan,
            safety_decision=decision,
            material_transition_zone_id=material_zone,
            active_faults=faults,
        )
        return decision, result.readiness, plan is not None


def build_schedule_validation_context(
    migration: Phase2RuntimeConfiguration,
) -> ScheduleValidationContext:
    """Build conservative backend schedule limits from user safety limits."""
    limits = migration.options.safety_limits
    constraints = {
        item.zone.zone_id: ScheduleZoneConstraints(
            zone_id=item.zone.zone_id,
            supports_single_target=True,
            supports_target_range=True,
            single_target_min_c=min(
                limits.minimum_heating_target_c, limits.minimum_cooling_target_c
            ),
            single_target_max_c=max(
                limits.maximum_heating_target_c, limits.maximum_cooling_target_c
            ),
            heat_target_min_c=limits.minimum_heating_target_c,
            heat_target_max_c=limits.maximum_heating_target_c,
            cool_target_min_c=limits.minimum_cooling_target_c,
            cool_target_max_c=limits.maximum_cooling_target_c,
            minimum_heat_cool_separation_c=(limits.minimum_heat_cool_separation_c),
        )
        for item in migration.zones
    }
    return ScheduleValidationContext(
        entry_id=migration.runtime.entry_id,
        equipment_group_id=migration.config.equipment_group.equipment_group_id,
        time_zone=migration.config.acknowledged_time_zone,
        zone_constraints=constraints,
    )


def _candidate(
    *,
    safety_id: SafetyEvaluationId,
    observation: EntryObservationSnapshot,
    thermostat: ThermostatRuntimeSnapshot,
    zone_id: ZoneId,
    target: TargetSpec,
    now: datetime,
) -> SafetyCommandCandidate:
    state = thermostat.state
    values = NormalizedStateEvidence(
        revision=observation.revision,
        observed_at_utc=now,
        available=state.available,
        values=NormalizedCommandValues(
            target_c=state.target_temperature_c,
            heat_target_c=state.target_low_c,
            cool_target_c=state.target_high_c,
            hvac_mode=None if state.hvac_mode is None else state.hvac_mode.value,
            fan_mode=state.fan_mode,
        ),
    )
    if target.kind is TargetKind.SINGLE:
        assert state.hvac_mode in {HVACMode.HEAT, HVACMode.COOL}
        requested = NormalizedCommandValues(target_c=target.target_c)
        kind = CommandKind.SET_TARGET
        fields = frozenset({CommandControlledField.TARGET})
        direction = (
            SafetyTargetDirection.COOL
            if state.hvac_mode is HVACMode.COOL
            else SafetyTargetDirection.HEAT
        )
    else:
        assert state.hvac_mode in {HVACMode.HEAT_COOL, HVACMode.AUTO}
        requested = NormalizedCommandValues(
            heat_target_c=target.heat_target_c,
            cool_target_c=target.cool_target_c,
        )
        kind = CommandKind.SET_RANGE
        fields = frozenset({CommandControlledField.RANGE})
        direction = None
    return SafetyCommandCandidate(
        safety_evaluation_id=safety_id,
        entry_id=observation.entry_id,
        equipment_group_id=observation.equipment_group_id,
        zone_id=zone_id,
        target_entity_id=thermostat.entity_id,
        command_kind=kind,
        requested_fields=fields,
        requested_values=requested,
        target_direction=direction,
        authority=CommandAuthority.SCHEDULED,
        cause=CommandCause.SCHEDULE,
        observed_precondition=values,
        requested_against_revision=observation.revision,
        created_at_utc=now,
        not_before_utc=now,
        expires_at_utc=now + timedelta(minutes=5),
    )


def _capability_snapshot(
    thermostat: ThermostatRuntimeSnapshot,
    target: TargetSpec,
    limits: object,
) -> SafetyCapabilitySnapshot:
    from .models.phase2_schema import Phase2SafetyLimits

    assert isinstance(limits, Phase2SafetyLimits)
    capabilities = thermostat.capability_discovery.capabilities
    assert capabilities is not None
    supported = set()
    if capabilities.target_temperature:
        supported.add(CommandKind.SET_TARGET)
    if capabilities.target_temperature_range:
        supported.add(CommandKind.SET_RANGE)
    if capabilities.fan_modes:
        supported.add(CommandKind.SET_FAN_MODE)
    supported.add(CommandKind.SET_HVAC_MODE)
    minimum = min(limits.minimum_heating_target_c, limits.minimum_cooling_target_c)
    maximum = max(limits.maximum_heating_target_c, limits.maximum_cooling_target_c)
    return SafetyCapabilitySnapshot(
        entity_id=thermostat.entity_id,
        available=thermostat.state.available,
        supported_command_kinds=frozenset(supported),
        hvac_modes=tuple(item.value for item in capabilities.hvac_modes),
        fan_modes=capabilities.fan_modes,
        advertised_min_target_c=minimum,
        advertised_max_target_c=maximum,
        observed_at_utc=capabilities.discovered_at.astimezone(UTC),
    )


def _thermostat_for_zone(
    zone_id: ZoneId,
    observation: EntryObservationSnapshot,
    migration: Phase2RuntimeConfiguration,
) -> ThermostatRuntimeSnapshot | None:
    config = next(
        (item.zone for item in migration.zones if item.zone.zone_id == zone_id), None
    )
    if config is None:
        return None
    authority = set(migration.config.command_authority_entity_ids)
    preferred = next(
        (item for item in config.thermostat_entity_ids if item in authority), None
    )
    entity_id = preferred or (
        config.thermostat_entity_ids[0] if config.thermostat_entity_ids else None
    )
    return next(
        (item for item in observation.thermostats if item.entity_id == entity_id), None
    )


def _demand_direction(
    mode: HVACMode | None, current: float, target: float
) -> ZoneDemandDirection:
    if abs(target - current) <= 0.3:
        return ZoneDemandDirection.SATISFIED
    if mode is HVACMode.COOL:
        return (
            ZoneDemandDirection.COOL
            if current > target
            else ZoneDemandDirection.SATISFIED
        )
    return (
        ZoneDemandDirection.HEAT if current < target else ZoneDemandDirection.SATISFIED
    )


def _target_matches_hvac_mode(target: TargetSpec, mode: HVACMode | None) -> bool:
    """Require an unambiguous live mode before constructing a target plan."""
    if target.kind is TargetKind.SINGLE:
        return mode in {HVACMode.HEAT, HVACMode.COOL}
    return mode in {HVACMode.HEAT_COOL, HVACMode.AUTO}


def _equipment_direction(observation: EntryObservationSnapshot) -> EquipmentDirection:
    actions = {
        getattr(item.state.hvac_action, "value", None)
        for item in observation.thermostats
    }
    if "heating" in actions:
        return EquipmentDirection.HEAT
    if "cooling" in actions:
        return EquipmentDirection.COOL
    if actions <= {None, "idle", "off"}:
        return EquipmentDirection.IDLE
    return EquipmentDirection.UNKNOWN


def _related_disposition(
    value: ThermostatRuntimeSnapshot,
) -> RelatedThermostatDisposition:
    if not value.state.available:
        return RelatedThermostatDisposition.UNAVAILABLE
    action = getattr(value.state.hvac_action, "value", None)
    if action == "heating":
        return RelatedThermostatDisposition.HEAT
    if action == "cooling":
        return RelatedThermostatDisposition.COOL
    if action in {None, "idle", "off"}:
        return RelatedThermostatDisposition.NEUTRAL
    return RelatedThermostatDisposition.UNCERTAIN


def _faults_for_decision(
    decision: SafetyGateDecision,
    arbitration: SharedArbitrationDecision | None,
) -> tuple[ShadowBlockingFault, ...]:
    if decision.reason_code is SafetyReasonCode.SHADOW_ONLY:
        return ()
    if (
        arbitration is not None
        and arbitration.outcome is not ArbitrationOutcome.SELECTED
    ):
        return (
            ShadowBlockingFault.SHARED_CONFLICT,
            ShadowBlockingFault.SAFETY_EVALUATION,
        )
    mapping = {
        SafetyReasonCode.CAPABILITY_UNAVAILABLE: ShadowBlockingFault.CAPABILITY,
        SafetyReasonCode.CAPABILITY_STALE: ShadowBlockingFault.CAPABILITY,
        SafetyReasonCode.PRECONDITION_UNAVAILABLE: ShadowBlockingFault.SENSOR,
        SafetyReasonCode.PRECONDITION_STALE: ShadowBlockingFault.SENSOR,
        SafetyReasonCode.CORRELATION_AWAITING: ShadowBlockingFault.CORRELATION,
        SafetyReasonCode.CORRELATION_UNCERTAIN: ShadowBlockingFault.CORRELATION,
    }
    fault = mapping.get(decision.reason_code, ShadowBlockingFault.SAFETY_EVALUATION)
    return (fault,)


def _blocked_decision(
    safety_id: SafetyEvaluationId, reason: SafetyReasonCode
) -> SafetyGateDecision:
    return SafetyGateDecision(
        safety_evaluation_id=safety_id,
        disposition=SafetyDisposition.BLOCKED,
        reason_code=reason,
        hard_checks_passed=False,
        reevaluate_at_utc=None,
        explanation="The current live evaluation is not safe for a Shadow plan.",
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("runtime timestamps must be timezone-aware")
    return value.astimezone(UTC)
