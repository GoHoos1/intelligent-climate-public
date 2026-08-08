"""Physically inert Shadow sink and qualification accumulator."""

from __future__ import annotations

from ..command.dependencies import UtcClock
from ..models.command import CommandAuthority, CommandCause
from ..models.identifiers import ZoneId
from ..models.phase2_schema import Phase2ShadowQualification
from ..models.plan import (
    CommandPlan,
    CommandSinkDisposition,
    CommandSinkResult,
    validate_plan_safety_decision,
)
from ..models.safety import SafetyGateDecision, SafetyReasonCode
from ..models.schema import SchemaValidationError
from ..models.shadow import (
    ShadowBlockingFault,
    ShadowHistoryRecord,
    ShadowSinkSnapshot,
)
from .history import (
    append_shadow_history,
    shadow_history_record,
    validate_shadow_history,
)
from .qualification import (
    evaluate_shadow_readiness,
    record_shadow_evaluation,
    reset_shadow_qualification,
    validate_shadow_qualification,
)


class ShadowCommandSink:
    """Accumulate Shadow evidence without an adapter or service dependency."""

    def __init__(
        self,
        *,
        clock: UtcClock,
        qualification: Phase2ShadowQualification,
        history: tuple[ShadowHistoryRecord, ...],
        all_zone_ids: tuple[ZoneId, ...],
        enabled_zone_ids: tuple[ZoneId, ...],
    ) -> None:
        """Restore bounded state with explicit clock and zone dependencies."""
        validate_shadow_qualification(qualification, all_zone_ids=all_zone_ids)
        validate_shadow_history(history, enforce_bound=True)
        self._clock = clock
        self._qualification = qualification
        self._history = history
        self._all_zone_ids = all_zone_ids
        self._enabled_zone_ids = enabled_zone_ids
        evaluate_shadow_readiness(
            qualification,
            all_zone_ids=all_zone_ids,
            enabled_zone_ids=enabled_zone_ids,
            now_utc=clock.now_utc(),
        )

    @property
    def qualification(self) -> Phase2ShadowQualification:
        """Return the latest immutable qualification record."""
        return self._qualification

    @property
    def history(self) -> tuple[ShadowHistoryRecord, ...]:
        """Return the latest immutable bounded history."""
        return self._history

    def reset_qualification(self) -> None:
        """Begin a distinct Shadow qualification run without touching equipment."""
        self._qualification = reset_shadow_qualification(
            self._qualification,
            all_zone_ids=self._all_zone_ids,
        )

    async def async_record_plan(
        self,
        plan: CommandPlan,
        safety_decision: SafetyGateDecision,
    ) -> CommandSinkResult:
        """Record one fully validated would-command and no physical call."""
        snapshot = await self.async_record_evaluation(
            plan=plan,
            safety_decision=safety_decision,
            material_transition_zone_id=None,
            active_faults=(),
        )
        return CommandSinkResult(
            disposition=CommandSinkDisposition.SUPPRESSED_SHADOW,
            command_id=plan.command_id,
            decision_id=plan.decision_id,
            safety_evaluation_id=plan.safety_evaluation_id,
            reason_code=snapshot.record.reason_code,
            recorded_at_utc=snapshot.record.evaluated_at_utc,
        )

    async def async_record_evaluation(
        self,
        *,
        plan: CommandPlan | None,
        safety_decision: SafetyGateDecision,
        material_transition_zone_id: ZoneId | None,
        active_faults: tuple[ShadowBlockingFault, ...],
    ) -> ShadowSinkSnapshot:
        """Record one Shadow evaluation and update readiness deterministically."""
        now = self._clock.now_utc()
        validate_plan_safety_decision(safety_decision)
        valid = plan is not None
        if plan is not None:
            if (
                safety_decision.reason_code is not SafetyReasonCode.SHADOW_ONLY
                or not safety_decision.hard_checks_passed
            ):
                raise SchemaValidationError(
                    "safety_decision", "plan requires a matching Shadow-only result"
                )
            if plan.authority is not CommandAuthority.SCHEDULED or plan.cause in {
                CommandCause.MANUAL_USER,
                CommandCause.UI_OVERRIDE,
            }:
                raise SchemaValidationError(
                    "plan.authority",
                    "Shadow qualification accepts scheduled authority only",
                )
        elif (
            safety_decision.reason_code is SafetyReasonCode.SHADOW_ONLY
            or safety_decision.hard_checks_passed
        ):
            raise SchemaValidationError(
                "plan", "is required when all Shadow hard checks passed"
            )
        record = shadow_history_record(
            plan=plan,
            safety_decision=safety_decision,
            evaluated_at_utc=now,
        )
        self._history = append_shadow_history(self._history, record, now_utc=now)
        self._qualification = record_shadow_evaluation(
            self._qualification,
            all_zone_ids=self._all_zone_ids,
            evaluated_at_utc=now,
            valid=valid,
            material_transition_zone_id=material_transition_zone_id,
            active_faults=active_faults,
        )
        readiness = evaluate_shadow_readiness(
            self._qualification,
            all_zone_ids=self._all_zone_ids,
            enabled_zone_ids=self._enabled_zone_ids,
            now_utc=now,
        )
        return ShadowSinkSnapshot(record=record, readiness=readiness)
