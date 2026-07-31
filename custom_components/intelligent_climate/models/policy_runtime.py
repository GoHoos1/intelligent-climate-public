"""Immutable coordinator-policy projections for Phase 2 runtime wiring."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .control import ControlExecutionState, ControlReason
from .identifiers import SchedulePeriodId, ScheduleProfileId, ZoneId
from .safety import SafetyGateDecision
from .schedule import TargetSpec
from .shadow import ShadowReadinessEntitySnapshot


@dataclass(frozen=True, slots=True)
class ZonePolicySnapshot:
    """One zone's nonauthoritative presentation of the suppressed policy path."""

    zone_id: ZoneId
    control_state: ControlExecutionState
    reason_code: ControlReason
    scheduled_target: TargetSpec | None
    effective_target: TargetSpec | None
    profile_id: ScheduleProfileId | None
    period_id: SchedulePeriodId | None
    next_transition_utc: datetime | None
    safety_decision: SafetyGateDecision | None
    would_command: bool


@dataclass(frozen=True, slots=True)
class Phase2PolicySnapshot:
    """Entry-scoped result published after one live observation evaluation."""

    entry_id: str
    observation_revision: int
    evaluated_at_utc: datetime
    control_state: ControlExecutionState
    reason_code: ControlReason
    zones: tuple[ZonePolicySnapshot, ...]
    shadow_readiness: ShadowReadinessEntitySnapshot | None
    next_evaluation_at_utc: datetime | None

    def zone(self, zone_id: ZoneId) -> ZonePolicySnapshot | None:
        """Return one stable zone projection without exposing mutable indexes."""
        return next((item for item in self.zones if item.zone_id == zone_id), None)
