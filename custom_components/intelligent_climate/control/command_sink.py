"""Observation-only command boundary."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal, Protocol

_LOGGER = logging.getLogger(__name__)


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


class CommandViolationReporter(Protocol):
    """Protocol for reporting an unexpected nonempty command intent."""

    def async_report_command_boundary_violation(self) -> None:
        """Report a suppressed command-boundary invariant violation."""


class ObserveOnlyCommandSink:
    """Command sink that can only suppress and report an intent."""

    def __init__(
        self,
        violation_reporter: CommandViolationReporter | None = None,
    ) -> None:
        """Initialize with an optional entry-scoped Repairs reporter."""
        self._violation_reporter = violation_reporter

    async def async_record_intent(
        self,
        intent: ObservationIntent,
    ) -> CommandBoundaryResult:
        """Record an intent as suppressed by the observation-only boundary."""
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
