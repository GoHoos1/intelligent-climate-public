"""Explicit input, clock, and sink dependency boundaries for command planning."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from ..models.plan import CommandPlan, CommandSinkResult
from ..models.safety import SafetyCommandCandidate, SafetyGateDecision


class CommandInputProvider(Protocol):
    """Supply one immutable candidate without coupling policy to Home Assistant."""

    async def async_get_candidate(self) -> SafetyCommandCandidate | None:
        """Return the current candidate, or no candidate for this evaluation."""


class UtcClock(Protocol):
    """Provide an injected UTC clock for deterministic command boundaries."""

    def now_utc(self) -> datetime:
        """Return the current timezone-aware UTC instant."""


class CommandPlanSink(Protocol):
    """Consume a typed plan without granting physical-dispatch authority."""

    async def async_record_plan(
        self,
        plan: CommandPlan,
        safety_decision: SafetyGateDecision,
    ) -> CommandSinkResult:
        """Record a suppressed plan and return a bounded result."""
