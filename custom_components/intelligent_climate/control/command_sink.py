"""Observation-only command boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True, slots=True)
class ObservationIntent:
    """A future decision intent recorded without executing any command."""

    source: str
    description: str


@dataclass(frozen=True, slots=True)
class CommandBoundaryResult:
    """Result returned by the observation-only command boundary."""

    status: Literal["suppressed_observe_only"]
    intent: ObservationIntent


class CommandSink(Protocol):
    """Protocol for recording future command intents."""

    async def async_record_intent(
        self,
        intent: ObservationIntent,
    ) -> CommandBoundaryResult:
        """Record an intent without physical control."""


class ObserveOnlyCommandSink:
    """Command sink that can only suppress and report an intent."""

    async def async_record_intent(
        self,
        intent: ObservationIntent,
    ) -> CommandBoundaryResult:
        """Record an intent as suppressed by the observation-only boundary."""
        return CommandBoundaryResult(
            status="suppressed_observe_only",
            intent=intent,
        )
