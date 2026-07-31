"""Test Task 17 typed command plans and explicit dependency boundaries."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

import pytest

from custom_components.intelligent_climate.command.dependencies import (
    CommandInputProvider,
    CommandPlanSink,
    UtcClock,
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
    DEDUPE_FINGERPRINT_LENGTH,
    CommandPlan,
    build_command_plan,
    command_dedupe_fingerprint,
    validate_command_plan,
    validate_plan_safety_decision,
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
GROUP_ID = EquipmentGroupId.parse("11111111-1111-4111-8111-111111111111")
ZONE_ID = ZoneId.parse("22222222-2222-4222-8222-222222222222")
SAFETY_ID = SafetyEvaluationId.parse("33333333-3333-4333-8333-333333333333")
COMMAND_ID = CommandId.parse("44444444-4444-4444-8444-444444444444")
DECISION_ID = DecisionId.parse("55555555-5555-4555-8555-555555555555")


def _candidate(**changes: Any) -> SafetyCommandCandidate:
    values: dict[str, Any] = {
        "safety_evaluation_id": SAFETY_ID,
        "entry_id": "entry-1",
        "equipment_group_id": GROUP_ID,
        "zone_id": ZONE_ID,
        "target_entity_id": "climate.dining_room",
        "command_kind": CommandKind.SET_TARGET,
        "requested_fields": frozenset({CommandControlledField.TARGET}),
        "requested_values": NormalizedCommandValues(target_c=21.0),
        "target_direction": SafetyTargetDirection.HEAT,
        "authority": CommandAuthority.SCHEDULED,
        "cause": CommandCause.SCHEDULE,
        "observed_precondition": NormalizedStateEvidence(
            revision=7,
            observed_at_utc=NOW - timedelta(seconds=2),
            available=True,
            values=NormalizedCommandValues(target_c=20.0),
        ),
        "requested_against_revision": 7,
        "created_at_utc": NOW - timedelta(seconds=1),
        "not_before_utc": NOW - timedelta(seconds=1),
        "expires_at_utc": NOW + timedelta(minutes=5),
    }
    values.update(changes)
    return SafetyCommandCandidate(**values)


def _decision(
    *,
    safety_id: SafetyEvaluationId = SAFETY_ID,
    reason: SafetyReasonCode = SafetyReasonCode.SHADOW_ONLY,
    hard_checks_passed: bool = True,
    disposition: SafetyDisposition = SafetyDisposition.SUPPRESSED,
) -> SafetyGateDecision:
    return SafetyGateDecision(
        safety_evaluation_id=safety_id,
        disposition=disposition,
        reason_code=reason,
        hard_checks_passed=hard_checks_passed,
        reevaluate_at_utc=None,
        explanation="bounded",
    )


def _plan(
    candidate: SafetyCommandCandidate | None = None,
    decision: SafetyGateDecision | None = None,
    *,
    user_context_id: str | None = None,
) -> CommandPlan:
    return build_command_plan(
        candidate or _candidate(),
        decision or _decision(),
        command_id=COMMAND_ID,
        decision_id=DECISION_ID,
        user_context_id=user_context_id,
    )


@pytest.mark.parametrize(
    "reason",
    [
        SafetyReasonCode.OBSERVE_ONLY,
        SafetyReasonCode.SHADOW_ONLY,
        SafetyReasonCode.ALL_HARD_GATES_PASSED,
    ],
)
def test_plan_builds_after_each_complete_safety_outcome(
    reason: SafetyReasonCode,
) -> None:
    disposition = (
        SafetyDisposition.ELIGIBLE
        if reason is SafetyReasonCode.ALL_HARD_GATES_PASSED
        else SafetyDisposition.SUPPRESSED
    )
    plan = _plan(decision=_decision(reason=reason, disposition=disposition))

    assert plan.command_id == COMMAND_ID
    assert plan.decision_id == DECISION_ID
    assert plan.safety_evaluation_id == SAFETY_ID
    assert plan.desired == NormalizedCommandValues(target_c=21.0)
    assert len(plan.dedupe_fingerprint) == DEDUPE_FINGERPRINT_LENGTH
    assert plan.dedupe_fingerprint.isascii()
    validate_command_plan(plan)


def test_safety_decision_accepts_utc_reevaluation_time() -> None:
    validate_plan_safety_decision(
        replace(_decision(), reevaluate_at_utc=NOW + timedelta(minutes=1))
    )


def test_dedupe_uses_semantics_not_volatile_identities_or_timestamps() -> None:
    first = _candidate()
    second = replace(
        first,
        safety_evaluation_id=SafetyEvaluationId.new(),
        created_at_utc=NOW,
        not_before_utc=NOW,
        expires_at_utc=NOW + timedelta(minutes=10),
    )
    changed = replace(
        second,
        requested_against_revision=8,
        observed_precondition=replace(second.observed_precondition, revision=8),
    )

    assert command_dedupe_fingerprint(first) == command_dedupe_fingerprint(second)
    assert command_dedupe_fingerprint(first) != command_dedupe_fingerprint(changed)


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (
            _candidate(
                command_kind=CommandKind.SET_RANGE,
                requested_fields=frozenset({CommandControlledField.RANGE}),
                requested_values=NormalizedCommandValues(
                    heat_target_c=19.0,
                    cool_target_c=24.0,
                ),
                target_direction=None,
                observed_precondition=NormalizedStateEvidence(
                    revision=7,
                    observed_at_utc=NOW - timedelta(seconds=2),
                    available=True,
                    values=NormalizedCommandValues(
                        heat_target_c=18.0,
                        cool_target_c=25.0,
                    ),
                ),
            ),
            "range",
        ),
        (
            _candidate(
                command_kind=CommandKind.SET_HVAC_MODE,
                requested_fields=frozenset({CommandControlledField.HVAC_MODE}),
                requested_values=NormalizedCommandValues(hvac_mode="heat"),
                target_direction=None,
                observed_precondition=NormalizedStateEvidence(
                    revision=7,
                    observed_at_utc=NOW - timedelta(seconds=2),
                    available=True,
                    values=NormalizedCommandValues(hvac_mode="off"),
                ),
            ),
            "hvac_mode",
        ),
        (
            _candidate(
                target_entity_id="fan.air_handler",
                command_kind=CommandKind.FAN_ON,
                requested_fields=frozenset({CommandControlledField.FAN_STATE}),
                requested_values=NormalizedCommandValues(fan_state="on"),
                target_direction=None,
                cause=CommandCause.FAN_POLICY,
                observed_precondition=NormalizedStateEvidence(
                    revision=7,
                    observed_at_utc=NOW - timedelta(seconds=2),
                    available=True,
                    values=NormalizedCommandValues(fan_state="off"),
                ),
            ),
            "fan_state",
        ),
    ],
)
def test_plan_is_lossless_for_every_payload_family(
    candidate: SafetyCommandCandidate,
    expected: str,
) -> None:
    plan = _plan(candidate)

    assert expected in {field.value for field in plan.desired_fields}
    assert plan.target_direction == candidate.target_direction
    assert plan.observed_precondition is candidate.observed_precondition


def test_manual_plan_requires_bounded_user_context() -> None:
    candidate = _candidate(
        authority=CommandAuthority.MANUAL,
        cause=CommandCause.MANUAL_USER,
    )
    plan = _plan(candidate, user_context_id="context-1")
    assert plan.user_context_id == "context-1"

    for invalid in (None, "", " ", "x" * 256):
        with pytest.raises(SchemaValidationError, match="user_context_id"):
            _plan(candidate, user_context_id=invalid)


def test_scheduled_plan_rejects_user_context() -> None:
    with pytest.raises(SchemaValidationError, match="must not be retained"):
        _plan(user_context_id="context-1")


@pytest.mark.parametrize(
    "decision",
    [
        _decision(safety_id=SafetyEvaluationId.new()),
        _decision(hard_checks_passed=False),
        _decision(
            reason=SafetyReasonCode.MINIMUM_INTERVAL,
            hard_checks_passed=True,
        ),
    ],
)
def test_plan_rejects_missing_or_mismatched_safety_proof(
    decision: SafetyGateDecision,
) -> None:
    with pytest.raises(SchemaValidationError):
        _plan(decision=decision)


def test_plan_rejects_wrong_safety_object() -> None:
    with pytest.raises(SchemaValidationError, match="safety_decision"):
        build_command_plan(
            _candidate(),
            cast(Any, object()),
            command_id=COMMAND_ID,
            decision_id=DECISION_ID,
            user_context_id=None,
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"safety_evaluation_id": object()},
        {"disposition": "suppressed"},
        {"reason_code": "shadow_only"},
        {"hard_checks_passed": 1},
        {"explanation": ""},
        {"explanation": "x" * 256},
        {"reevaluate_at_utc": NOW.replace(tzinfo=None)},
        {"reevaluate_at_utc": NOW.astimezone(timezone(timedelta(hours=-4)))},
        {"reason_code": SafetyReasonCode.MINIMUM_INTERVAL},
        {"disposition": SafetyDisposition.BLOCKED},
    ],
)
def test_safety_decision_boundary_rejects_malformed_or_contradictory_results(
    changes: dict[str, object],
) -> None:
    decision = _decision()
    values = {name: getattr(decision, name) for name in decision.__dataclass_fields__}
    values.update(changes)
    malformed = cast(Any, SafetyGateDecision)(**values)
    with pytest.raises(SchemaValidationError):
        validate_plan_safety_decision(malformed)


@pytest.mark.parametrize(
    "changes",
    [
        {"command_id": object()},
        {"decision_id": object()},
        {"dedupe_fingerprint": "0" * DEDUPE_FINGERPRINT_LENGTH},
        {"desired": NormalizedCommandValues(target_c=22.0)},
    ],
)
def test_direct_plan_construction_fails_closed(changes: dict[str, object]) -> None:
    plan = _plan()
    values = {name: getattr(plan, name) for name in plan.__dataclass_fields__}
    values.update(changes)
    with pytest.raises(SchemaValidationError):
        cast(Any, CommandPlan)(**values)


def test_plan_validator_rejects_wrong_top_level_type() -> None:
    with pytest.raises(SchemaValidationError, match="command_plan"):
        validate_command_plan(cast(Any, object()))


def test_dependency_protocols_have_only_explicit_boundary_methods() -> None:
    assert set(CommandInputProvider.__dict__) >= {"async_get_candidate"}
    assert set(UtcClock.__dict__) >= {"now_utc"}
    assert set(CommandPlanSink.__dict__) >= {"async_record_plan"}
    assert (
        "homeassistant"
        not in __import__(
            "custom_components.intelligent_climate.command.dependencies",
            fromlist=["x"],
        ).__dict__
    )


def test_fingerprint_rejects_invalid_candidate() -> None:
    with pytest.raises(SchemaValidationError):
        command_dedupe_fingerprint(cast(Any, object()))
