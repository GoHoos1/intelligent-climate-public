"""Physically inert Observe Only command sink for Phase 2 Task 17."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

from ..command.dependencies import UtcClock
from ..models.plan import (
    CommandPlan,
    CommandSinkDisposition,
    CommandSinkResult,
    validate_command_plan,
)
from ..models.safety import SafetyGateDecision, SafetyReasonCode
from ..models.schema import SchemaValidationError

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ObservationIntent:
    """Legacy Phase 1 invariant probe retained until Task 19 wiring."""

    source: str
    description: str


@dataclass(frozen=True, slots=True)
class CommandBoundaryResult:
    """Legacy result from the Phase 1 invariant probe."""

    status: Literal["suppressed_observe_only"]
    intent: ObservationIntent


class CommandViolationReporter(Protocol):
    """Report an unexpected legacy free-text boundary probe."""

    def async_report_command_boundary_violation(self) -> None:
        """Create the existing entry-scoped invariant Repair."""


class ObserveOnlyCommandSink:
    """Record a validated plan as suppressed without any physical call path."""

    def __init__(
        self,
        violation_reporter: CommandViolationReporter | None = None,
        *,
        clock: UtcClock | None = None,
    ) -> None:
        """Retain the Phase 1 probe and accept an injected Task 17 clock."""
        self._violation_reporter = violation_reporter
        self._clock = clock

    async def async_record_intent(
        self,
        intent: ObservationIntent,
    ) -> CommandBoundaryResult:
        """Retain the Phase 1 no-command invariant until Task 19 replaces wiring."""
        if intent.source or intent.description:
            _LOGGER.error(
                "Physical command intent suppressed: "
                "reason_code=command_boundary_violation"
            )
            if self._violation_reporter is not None:
                self._violation_reporter.async_report_command_boundary_violation()
        return CommandBoundaryResult(
            status="suppressed_observe_only",
            intent=intent,
        )

    async def async_record_plan(
        self,
        plan: CommandPlan,
        safety_decision: SafetyGateDecision,
    ) -> CommandSinkResult:
        """Return a bounded Observe Only suppression result."""
        validate_command_plan(plan)
        if not isinstance(safety_decision, SafetyGateDecision):
            raise SchemaValidationError("safety_decision", "must be a safety decision")
        if (
            safety_decision.safety_evaluation_id != plan.safety_evaluation_id
            or not safety_decision.hard_checks_passed
            or safety_decision.reason_code is not SafetyReasonCode.OBSERVE_ONLY
        ):
            raise SchemaValidationError(
                "safety_decision",
                "must be the matching Observe Only safety result",
            )
        if self._clock is None:
            raise SchemaValidationError("clock", "is required for typed command plans")
        recorded_at = self._clock.now_utc()
        offset = recorded_at.utcoffset()
        if recorded_at.tzinfo is None or offset is None:
            raise SchemaValidationError("clock", "must return timezone-aware UTC")
        if offset.total_seconds() != 0:
            raise SchemaValidationError("clock", "must return UTC")
        if recorded_at < plan.created_at_utc:
            raise SchemaValidationError("clock", "must not precede plan creation")
        return CommandSinkResult(
            disposition=CommandSinkDisposition.SUPPRESSED_OBSERVE_ONLY,
            command_id=plan.command_id,
            decision_id=plan.decision_id,
            safety_evaluation_id=plan.safety_evaluation_id,
            reason_code=SafetyReasonCode.OBSERVE_ONLY,
            recorded_at_utc=recorded_at,
        )
