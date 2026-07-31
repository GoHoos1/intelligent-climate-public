"""Test the observation-only command boundary."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

import pytest

from custom_components.intelligent_climate.control import (
    ObservationIntent,
    ObserveOnlyCommandSink,
)
from custom_components.intelligent_climate.models.command import (
    CommandAuthority,
    CommandCause,
    CommandControlledField,
    CommandKind,
    NormalizedCommandValues,
    NormalizedStateEvidence,
)
from custom_components.intelligent_climate.models.identifiers import (
    CommandId,
    DecisionId,
    EquipmentGroupId,
    SafetyEvaluationId,
    ZoneId,
)
from custom_components.intelligent_climate.models.plan import (
    CommandSinkDisposition,
    build_command_plan,
)
from custom_components.intelligent_climate.models.safety import (
    SafetyCommandCandidate,
    SafetyDisposition,
    SafetyGateDecision,
    SafetyReasonCode,
    SafetyTargetDirection,
)
from custom_components.intelligent_climate.models.schema import SchemaValidationError

NOW = datetime(2026, 7, 31, 16, 0, tzinfo=UTC)


@dataclass(slots=True)
class FakeClock:
    """Injected deterministic Task 17 clock."""

    value: datetime = NOW

    def now_utc(self) -> datetime:
        return self.value


def _plan_and_decision() -> tuple[Any, SafetyGateDecision]:
    safety_id = SafetyEvaluationId.new()
    candidate = SafetyCommandCandidate(
        safety_evaluation_id=safety_id,
        entry_id="entry-1",
        equipment_group_id=EquipmentGroupId.new(),
        zone_id=ZoneId.new(),
        target_entity_id="climate.dining_room",
        command_kind=CommandKind.SET_TARGET,
        requested_fields=frozenset({CommandControlledField.TARGET}),
        requested_values=NormalizedCommandValues(target_c=21.0),
        target_direction=SafetyTargetDirection.HEAT,
        authority=CommandAuthority.SCHEDULED,
        cause=CommandCause.SCHEDULE,
        observed_precondition=NormalizedStateEvidence(
            revision=1,
            observed_at_utc=NOW - timedelta(seconds=2),
            available=True,
            values=NormalizedCommandValues(target_c=20.0),
        ),
        requested_against_revision=1,
        created_at_utc=NOW - timedelta(seconds=1),
        not_before_utc=NOW - timedelta(seconds=1),
        expires_at_utc=NOW + timedelta(minutes=5),
    )
    decision = SafetyGateDecision(
        safety_evaluation_id=safety_id,
        disposition=SafetyDisposition.SUPPRESSED,
        reason_code=SafetyReasonCode.OBSERVE_ONLY,
        hard_checks_passed=True,
        reevaluate_at_utc=None,
        explanation="Observe Only cannot execute a command.",
    )
    return (
        build_command_plan(
            candidate,
            decision,
            command_id=CommandId.new(),
            decision_id=DecisionId.new(),
            user_context_id=None,
        ),
        decision,
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


@dataclass(slots=True)
class RecordingReporter:
    reports: int = 0

    def async_report_command_boundary_violation(self) -> None:
        self.reports += 1


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


async def test_legacy_probe_empty_and_reporter_branches_remain_bounded() -> None:
    reporter = RecordingReporter()
    sink = ObserveOnlyCommandSink(reporter)

    empty = await sink.async_record_intent(ObservationIntent("", ""))
    nonempty = await sink.async_record_intent(ObservationIntent("legacy", "probe"))

    assert empty.status == "suppressed_observe_only"
    assert nonempty.status == "suppressed_observe_only"
    assert reporter.reports == 1


async def test_typed_observe_sink_records_suppression_without_service_call() -> None:
    hass = FakeHass()
    plan, decision = _plan_and_decision()
    sink = ObserveOnlyCommandSink(clock=FakeClock())

    result = await sink.async_record_plan(plan, decision)

    assert result.disposition is CommandSinkDisposition.SUPPRESSED_OBSERVE_ONLY
    assert result.command_id == plan.command_id
    assert result.reason_code is SafetyReasonCode.OBSERVE_ONLY
    assert result.recorded_at_utc == NOW
    assert hass.services.calls == []


@pytest.mark.parametrize(
    "decision",
    [
        object(),
        SafetyGateDecision(
            SafetyEvaluationId.new(),
            SafetyDisposition.SUPPRESSED,
            SafetyReasonCode.OBSERVE_ONLY,
            True,
            None,
            "bounded",
        ),
        SafetyGateDecision(
            SafetyEvaluationId.new(),
            SafetyDisposition.SUPPRESSED,
            SafetyReasonCode.SHADOW_ONLY,
            True,
            None,
            "bounded",
        ),
        SafetyGateDecision(
            SafetyEvaluationId.new(),
            SafetyDisposition.SUPPRESSED,
            SafetyReasonCode.OBSERVE_ONLY,
            False,
            None,
            "bounded",
        ),
    ],
)
async def test_typed_observe_sink_rejects_invalid_safety_result(
    decision: object,
) -> None:
    plan, _ = _plan_and_decision()
    if isinstance(decision, SafetyGateDecision):
        decision = replace(
            decision,
            safety_evaluation_id=(
                plan.safety_evaluation_id
                if decision.reason_code is not SafetyReasonCode.OBSERVE_ONLY
                or not decision.hard_checks_passed
                else decision.safety_evaluation_id
            ),
        )
    with pytest.raises(SchemaValidationError, match="safety_decision"):
        await ObserveOnlyCommandSink(clock=FakeClock()).async_record_plan(
            plan,
            cast(Any, decision),
        )


@pytest.mark.parametrize(
    "clock_value",
    [
        NOW.replace(tzinfo=None),
        NOW.astimezone(timezone(timedelta(hours=-4))),
        NOW - timedelta(minutes=1),
    ],
)
async def test_typed_observe_sink_rejects_invalid_clock(clock_value: datetime) -> None:
    plan, decision = _plan_and_decision()
    with pytest.raises(SchemaValidationError, match="clock"):
        await ObserveOnlyCommandSink(clock=FakeClock(clock_value)).async_record_plan(
            plan,
            decision,
        )


async def test_typed_observe_sink_requires_injected_clock() -> None:
    plan, decision = _plan_and_decision()
    with pytest.raises(SchemaValidationError, match="clock"):
        await ObserveOnlyCommandSink().async_record_plan(plan, decision)
