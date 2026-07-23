"""Test the observation-only command boundary."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from custom_components.intelligent_climate.control import (
    ObservationIntent,
    ObserveOnlyCommandSink,
)


@dataclass(slots=True)
class RecordingServices:
    """Service registry stand-in that records attempted calls."""

    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)

    async def async_call(self, *args: Any, **kwargs: Any) -> None:
        """Record a service call attempt."""
        self.calls.append((args, kwargs))


@dataclass(slots=True)
class FakeHass:
    """Minimal Home Assistant stand-in with a service registry."""

    services: RecordingServices = field(default_factory=RecordingServices)


async def test_observe_only_command_sink_suppresses_intent() -> None:
    """Test command intents are only recorded as suppressed."""
    sink = ObserveOnlyCommandSink()
    intent = ObservationIntent(
        source="unit-test",
        description="Would adjust a thermostat in a later phase.",
    )

    result = await sink.async_record_intent(intent)

    assert result.status == "suppressed_observe_only"
    assert result.intent is intent


async def test_observe_only_command_sink_does_not_call_hass_services() -> None:
    """Test the command boundary has no Home Assistant service-call path."""
    hass = FakeHass()
    sink = ObserveOnlyCommandSink()
    intent = ObservationIntent(
        source="unit-test",
        description="A physical command must remain impossible.",
    )

    await sink.async_record_intent(intent)

    assert hass.services.calls == []
