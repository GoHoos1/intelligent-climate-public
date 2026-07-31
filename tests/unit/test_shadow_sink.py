"""Test Task 18 inert Shadow sink and bounded history."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any, cast

import pytest

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
from custom_components.intelligent_climate.models.shadow import (
    MAX_SHADOW_HISTORY_RECORDS,
    ShadowBlockingFault,
    ShadowHistoryOutcome,
    ShadowHistoryRecord,
    ShadowWouldCommand,
)
from custom_components.intelligent_climate.shadow.history import (
    append_shadow_history,
    decode_shadow_history,
    encode_shadow_history,
    shadow_history_record,
    validate_shadow_history,
    validate_shadow_history_record,
)
from custom_components.intelligent_climate.shadow.qualification import (
    empty_shadow_qualification,
)
from custom_components.intelligent_climate.shadow.sink import ShadowCommandSink

NOW = datetime(2026, 7, 31, 16, 0, tzinfo=UTC)
GROUP_ID = EquipmentGroupId.parse("11111111-1111-4111-8111-111111111111")
ZONE_ID = ZoneId.parse("22222222-2222-4222-8222-222222222222")
ZONES = (ZONE_ID,)


@dataclass(slots=True)
class FakeClock:
    value: datetime = NOW

    def now_utc(self) -> datetime:
        return self.value


@dataclass(slots=True)
class RecordingServices:
    calls: list[object]

    async def async_call(self, *args: object, **kwargs: object) -> None:
        self.calls.append((args, kwargs))


def _candidate(
    *,
    safety_id: SafetyEvaluationId | None = None,
    now: datetime = NOW,
    authority: CommandAuthority = CommandAuthority.SCHEDULED,
    cause: CommandCause = CommandCause.SCHEDULE,
) -> SafetyCommandCandidate:
    return SafetyCommandCandidate(
        safety_evaluation_id=safety_id or SafetyEvaluationId.new(),
        entry_id="entry-1",
        equipment_group_id=GROUP_ID,
        zone_id=ZONE_ID,
        target_entity_id="climate.dining_room",
        command_kind=CommandKind.SET_TARGET,
        requested_fields=frozenset({CommandControlledField.TARGET}),
        requested_values=NormalizedCommandValues(target_c=21.0),
        target_direction=SafetyTargetDirection.HEAT,
        authority=authority,
        cause=cause,
        observed_precondition=NormalizedStateEvidence(
            revision=7,
            observed_at_utc=now - timedelta(seconds=2),
            available=True,
            values=NormalizedCommandValues(target_c=20.0),
        ),
        requested_against_revision=7,
        created_at_utc=now - timedelta(seconds=1),
        not_before_utc=now - timedelta(seconds=1),
        expires_at_utc=now + timedelta(minutes=5),
    )


def _decision(
    safety_id: SafetyEvaluationId,
    *,
    reason: SafetyReasonCode = SafetyReasonCode.SHADOW_ONLY,
    disposition: SafetyDisposition = SafetyDisposition.SUPPRESSED,
    hard: bool = True,
) -> SafetyGateDecision:
    return SafetyGateDecision(
        safety_evaluation_id=safety_id,
        disposition=disposition,
        reason_code=reason,
        hard_checks_passed=hard,
        reevaluate_at_utc=None,
        explanation="bounded",
    )


def _plan_and_decision() -> tuple[Any, SafetyGateDecision]:
    candidate = _candidate()
    decision = _decision(candidate.safety_evaluation_id)
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


def _sink(clock: FakeClock | None = None) -> ShadowCommandSink:
    return ShadowCommandSink(
        clock=clock or FakeClock(),
        qualification=empty_shadow_qualification(ZONES),
        history=(),
        all_zone_ids=ZONES,
        enabled_zone_ids=ZONES,
    )


def _invalid_record(
    record: ShadowHistoryRecord,
    changes: dict[str, object],
) -> ShadowHistoryRecord:
    values = {name: getattr(record, name) for name in record.__dataclass_fields__}
    values.update(changes)
    constructor = cast(Any, ShadowHistoryRecord)
    result: ShadowHistoryRecord = constructor(**values)
    return result


async def test_shadow_plan_is_recorded_exactly_without_service_call() -> None:
    services = RecordingServices([])
    plan, decision = _plan_and_decision()
    sink = _sink()

    result = await sink.async_record_plan(plan, decision)

    assert result.disposition is CommandSinkDisposition.SUPPRESSED_SHADOW
    assert result.reason_code is SafetyReasonCode.SHADOW_ONLY
    assert services.calls == []
    assert sink.qualification.evaluated_decisions == 1
    assert sink.qualification.valid_evaluations == 1
    record = sink.history[-1]
    assert record.outcome is ShadowHistoryOutcome.WOULD_COMMAND
    assert record.would_command is not None
    assert record.would_command.desired == plan.desired
    assert record.would_command.dedupe_fingerprint == plan.dedupe_fingerprint
    assert not hasattr(record.would_command, "target_entity_id")
    assert not hasattr(record.would_command, "user_context_id")


async def test_invalid_shadow_evaluation_is_bounded_and_blocks_readiness() -> None:
    sink = _sink()
    safety_id = SafetyEvaluationId.new()
    decision = _decision(
        safety_id,
        reason=SafetyReasonCode.CAPABILITY_UNAVAILABLE,
        disposition=SafetyDisposition.BLOCKED,
        hard=False,
    )

    snapshot = await sink.async_record_evaluation(
        plan=None,
        safety_decision=decision,
        material_transition_zone_id=None,
        active_faults=(ShadowBlockingFault.CAPABILITY,),
    )

    assert snapshot.record.outcome is ShadowHistoryOutcome.BLOCKED
    assert snapshot.record.would_command is None
    assert not snapshot.readiness.ready
    assert sink.qualification.valid_evaluations == 0
    assert sink.qualification.blocking_fault_codes == (
        ShadowBlockingFault.CAPABILITY.value,
        ShadowBlockingFault.SAFETY_EVALUATION.value,
    )


async def test_sink_reaches_readiness_at_exact_package_requirements() -> None:
    clock = FakeClock(NOW - timedelta(hours=24))
    sink = _sink(clock)
    last = None
    for index in range(20):
        evaluation_time = NOW - timedelta(hours=24) + timedelta(minutes=index)
        candidate = _candidate(now=evaluation_time)
        decision = _decision(candidate.safety_evaluation_id)
        plan = build_command_plan(
            candidate,
            decision,
            command_id=CommandId.new(),
            decision_id=DecisionId.new(),
            user_context_id=None,
        )
        clock.value = evaluation_time
        last = await sink.async_record_evaluation(
            plan=plan,
            safety_decision=decision,
            material_transition_zone_id=(ZONE_ID if index in {0, 1} else None),
            active_faults=(),
        )
    assert last is not None
    clock.value = NOW
    candidate = _candidate()
    decision = _decision(candidate.safety_evaluation_id)
    plan = build_command_plan(
        candidate,
        decision,
        command_id=CommandId.new(),
        decision_id=DecisionId.new(),
        user_context_id=None,
    )
    last = await sink.async_record_evaluation(
        plan=plan,
        safety_decision=decision,
        material_transition_zone_id=None,
        active_faults=(),
    )
    assert last.readiness.ready
    assert last.readiness.qualification_percent == 100.0


@pytest.mark.parametrize(
    ("plan_present", "reason", "hard"),
    [
        (True, SafetyReasonCode.MINIMUM_INTERVAL, False),
        (True, SafetyReasonCode.SHADOW_ONLY, False),
        (False, SafetyReasonCode.SHADOW_ONLY, True),
        (False, SafetyReasonCode.MINIMUM_INTERVAL, True),
    ],
)
async def test_sink_rejects_contradictory_plan_and_safety_result(
    plan_present: bool,
    reason: SafetyReasonCode,
    hard: bool,
) -> None:
    plan, original = _plan_and_decision()
    decision = replace(original, reason_code=reason, hard_checks_passed=hard)
    with pytest.raises(SchemaValidationError):
        await _sink().async_record_evaluation(
            plan=plan if plan_present else None,
            safety_decision=decision,
            material_transition_zone_id=None,
            active_faults=(),
        )


def test_history_projects_suppressed_and_blocked_outcomes() -> None:
    for disposition, expected in (
        (SafetyDisposition.SUPPRESSED, ShadowHistoryOutcome.SUPPRESSED),
        (SafetyDisposition.BLOCKED, ShadowHistoryOutcome.BLOCKED),
    ):
        decision = _decision(
            SafetyEvaluationId.new(),
            reason=SafetyReasonCode.MINIMUM_INTERVAL,
            disposition=disposition,
            hard=False,
        )
        record = shadow_history_record(
            plan=None,
            safety_decision=decision,
            evaluated_at_utc=NOW,
        )
        assert record.outcome is expected


def test_history_append_prunes_age_count_and_rejects_duplicates() -> None:
    records: tuple[ShadowHistoryRecord, ...] = ()
    for index in range(MAX_SHADOW_HISTORY_RECORDS + 2):
        decision = _decision(
            SafetyEvaluationId.new(),
            reason=SafetyReasonCode.MINIMUM_INTERVAL,
            hard=False,
        )
        record = shadow_history_record(
            plan=None,
            safety_decision=decision,
            evaluated_at_utc=NOW - timedelta(minutes=101 - index),
        )
        records = append_shadow_history(records, record, now_utc=NOW)
    assert len(records) == MAX_SHADOW_HISTORY_RECORDS
    with pytest.raises(SchemaValidationError, match="duplicates"):
        append_shadow_history(records, records[-1], now_utc=NOW)

    old = shadow_history_record(
        plan=None,
        safety_decision=_decision(
            SafetyEvaluationId.new(),
            reason=SafetyReasonCode.MINIMUM_INTERVAL,
            hard=False,
        ),
        evaluated_at_utc=NOW - timedelta(days=15),
    )
    current = shadow_history_record(
        plan=None,
        safety_decision=_decision(
            SafetyEvaluationId.new(),
            reason=SafetyReasonCode.MINIMUM_INTERVAL,
            hard=False,
        ),
        evaluated_at_utc=NOW,
    )
    assert append_shadow_history((old,), current, now_utc=NOW) == (current,)


def test_history_validation_rejects_shape_order_bound_and_future() -> None:
    decision = _decision(
        SafetyEvaluationId.new(),
        reason=SafetyReasonCode.MINIMUM_INTERVAL,
        hard=False,
    )
    record = shadow_history_record(
        plan=None,
        safety_decision=decision,
        evaluated_at_utc=NOW,
    )
    with pytest.raises(SchemaValidationError, match="immutable"):
        validate_shadow_history(cast(Any, [record]), enforce_bound=True)
    with pytest.raises(SchemaValidationError, match="100-record"):
        validate_shadow_history((record,) * 101, enforce_bound=True)
    with pytest.raises(SchemaValidationError, match="duplicate"):
        validate_shadow_history((record, record), enforce_bound=False)
    earlier = replace(
        record,
        safety_evaluation_id=SafetyEvaluationId.new(),
        evaluated_at_utc=NOW - timedelta(seconds=1),
    )
    with pytest.raises(SchemaValidationError, match="chronological"):
        validate_shadow_history((record, earlier), enforce_bound=True)
    future = replace(
        record,
        safety_evaluation_id=SafetyEvaluationId.new(),
        evaluated_at_utc=NOW + timedelta(seconds=1),
    )
    with pytest.raises(SchemaValidationError, match="caller clock"):
        append_shadow_history((), future, now_utc=NOW)


@pytest.mark.parametrize(
    "record",
    [
        cast(Any, object()),
        replace(
            shadow_history_record(
                plan=None,
                safety_decision=_decision(
                    SafetyEvaluationId.new(),
                    reason=SafetyReasonCode.MINIMUM_INTERVAL,
                    hard=False,
                ),
                evaluated_at_utc=NOW,
            ),
            outcome=cast(Any, "blocked"),
        ),
    ],
)
def test_history_record_validation_rejects_malformed(record: object) -> None:
    with pytest.raises(SchemaValidationError):
        validate_shadow_history_record(cast(Any, record))


@pytest.mark.parametrize(
    "changes",
    [
        {"safety_evaluation_id": object()},
        {"evaluated_at_utc": NOW.replace(tzinfo=None)},
        {"evaluated_at_utc": NOW.astimezone(timezone(timedelta(hours=-4)))},
        {"safety_disposition": "blocked"},
        {"reason_code": "minimum_interval"},
        {"hard_checks_passed": 1},
        {"hard_checks_passed": True},
        {"would_command": object()},
        {"outcome": ShadowHistoryOutcome.BLOCKED},
    ],
)
def test_history_record_remaining_validation_branches(
    changes: dict[str, object],
) -> None:
    decision = _decision(
        SafetyEvaluationId.new(),
        reason=SafetyReasonCode.MINIMUM_INTERVAL,
        hard=False,
    )
    record = shadow_history_record(
        plan=None,
        safety_decision=decision,
        evaluated_at_utc=NOW,
    )
    with pytest.raises(SchemaValidationError):
        validate_shadow_history_record(_invalid_record(record, changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"command_id": object()},
        {"decision_id": object()},
        {"command_kind": "set_target"},
        {"desired_fields": ()},
        {"desired_fields": (CommandControlledField.TARGET,) * 2},
        {"desired_fields": ("target",)},
        {
            "desired_fields": (
                CommandControlledField.TARGET,
                CommandControlledField.HVAC_MODE,
            ),
            "desired": NormalizedCommandValues(target_c=21.0, hvac_mode="heat"),
        },
        {"desired_fields": (CommandControlledField.FAN_STATE,)},
        {"desired": object()},
        {"desired": NormalizedCommandValues(hvac_mode="heat")},
        {"desired": NormalizedCommandValues(target_c=float("nan"))},
        {"desired": NormalizedCommandValues(heat_target_c=22.0, cool_target_c=21.0)},
        {"desired": NormalizedCommandValues(target_c=21.0, fan_mode="")},
        {"desired": NormalizedCommandValues(target_c=21.0, fan_mode="x" * 65)},
        {"desired": NormalizedCommandValues(fan_state="invalid")},
        {"authority": "scheduled"},
        {"cause": "schedule"},
        {"authority": CommandAuthority.MANUAL},
        {"dedupe_fingerprint": "x" * 64},
    ],
)
def test_would_command_projection_validation_is_strict(
    changes: dict[str, object],
) -> None:
    plan, decision = _plan_and_decision()
    record = shadow_history_record(
        plan=plan,
        safety_decision=decision,
        evaluated_at_utc=NOW,
    )
    assert record.would_command is not None
    values = {
        name: getattr(record.would_command, name)
        for name in record.would_command.__dataclass_fields__
    }
    values.update(changes)
    malformed = cast(Any, ShadowWouldCommand)(**values)
    with pytest.raises(SchemaValidationError):
        validate_shadow_history_record(replace(record, would_command=malformed))


@pytest.mark.parametrize(
    "changes",
    [
        {"would_command": None},
        {"hard_checks_passed": False},
        {"safety_disposition": SafetyDisposition.BLOCKED},
        {"reason_code": SafetyReasonCode.MINIMUM_INTERVAL},
    ],
)
def test_would_command_requires_exact_shadow_safety_proof(
    changes: dict[str, object],
) -> None:
    plan, decision = _plan_and_decision()
    record = shadow_history_record(
        plan=plan,
        safety_decision=decision,
        evaluated_at_utc=NOW,
    )
    with pytest.raises(SchemaValidationError, match="passed hard checks"):
        validate_shadow_history_record(_invalid_record(record, changes))


def test_history_rejects_plan_safety_mismatch_and_early_clock() -> None:
    plan, decision = _plan_and_decision()
    for changed, evaluated in (
        (replace(decision, safety_evaluation_id=SafetyEvaluationId.new()), NOW),
        (decision, NOW - timedelta(minutes=2)),
    ):
        with pytest.raises(SchemaValidationError):
            shadow_history_record(
                plan=plan,
                safety_decision=changed,
                evaluated_at_utc=evaluated,
            )


def test_history_rejects_wrong_safety_result_and_clock() -> None:
    for decision, evaluated in (
        (cast(Any, object()), NOW),
        (_decision(SafetyEvaluationId.new()), NOW.replace(tzinfo=None)),
    ):
        with pytest.raises(SchemaValidationError):
            shadow_history_record(
                plan=None,
                safety_decision=decision,
                evaluated_at_utc=evaluated,
            )


def test_shadow_history_codec_round_trips_exact_projection() -> None:
    plan, decision = _plan_and_decision()
    would = shadow_history_record(
        plan=plan,
        safety_decision=decision,
        evaluated_at_utc=NOW,
    )
    blocked = shadow_history_record(
        plan=None,
        safety_decision=_decision(
            SafetyEvaluationId.new(),
            reason=SafetyReasonCode.CAPABILITY_UNAVAILABLE,
            disposition=SafetyDisposition.BLOCKED,
            hard=False,
        ),
        evaluated_at_utc=NOW + timedelta(seconds=1),
    )

    encoded = encode_shadow_history((would, blocked))

    assert decode_shadow_history(encoded) == (would, blocked)
    assert encoded[0]["would_command"]["desired"]["target_c"] == 21.0
    assert "target_entity_id" not in encoded[0]["would_command"]


@pytest.mark.parametrize(
    "mutate",
    [
        lambda value: value[0].update(unknown=True),
        lambda value: value[0].update(safety_evaluation_id="bad"),
        lambda value: value[0].update(evaluated_at_utc="bad"),
        lambda value: value[0].update(evaluated_at_utc=1),
        lambda value: value[0].update(outcome="bad"),
        lambda value: value[0].update(hard_checks_passed=1),
        lambda value: value[0]["would_command"].update(unknown=True),
        lambda value: value[0]["would_command"].update(command_id="bad"),
        lambda value: value[0]["would_command"].update(desired_fields=[]),
        lambda value: value[0]["would_command"].update(desired_fields=[1]),
        lambda value: value[0]["would_command"]["desired"].update(unknown=True),
        lambda value: value[0]["would_command"]["desired"].update(target_c="bad"),
        lambda value: value[0]["would_command"]["desired"].update(
            target_c=float("nan")
        ),
        lambda value: value[0]["would_command"].update(dedupe_fingerprint=1),
    ],
)
def test_shadow_history_codec_rejects_malformed_fields(mutate: Any) -> None:
    plan, decision = _plan_and_decision()
    encoded = encode_shadow_history(
        (
            shadow_history_record(
                plan=plan,
                safety_decision=decision,
                evaluated_at_utc=NOW,
            ),
        )
    )
    mutate(encoded)
    with pytest.raises(SchemaValidationError):
        decode_shadow_history(encoded)


def test_shadow_history_codec_rejects_wrong_container_and_bound() -> None:
    with pytest.raises(SchemaValidationError, match="array"):
        decode_shadow_history({})
    with pytest.raises(SchemaValidationError, match="100-record"):
        decode_shadow_history([{}] * 101)
    for value in ([1], [{1: "bad"}]):
        with pytest.raises(SchemaValidationError, match="object"):
            decode_shadow_history(value)


async def test_sink_rejects_wrong_safety_object_before_attribute_access() -> None:
    with pytest.raises(SchemaValidationError, match="safety_decision"):
        await _sink().async_record_evaluation(
            plan=None,
            safety_decision=cast(Any, object()),
            material_transition_zone_id=None,
            active_faults=(),
        )


async def test_sink_rejects_manual_plan_from_shadow_qualification() -> None:
    candidate = _candidate(
        authority=CommandAuthority.MANUAL,
        cause=CommandCause.MANUAL_USER,
    )
    decision = _decision(candidate.safety_evaluation_id)
    plan = build_command_plan(
        candidate,
        decision,
        command_id=CommandId.new(),
        decision_id=DecisionId.new(),
        user_context_id="context-1",
    )
    with pytest.raises(SchemaValidationError, match="scheduled authority"):
        await _sink().async_record_plan(plan, decision)


def test_sink_constructor_validates_restored_history() -> None:
    with pytest.raises(SchemaValidationError, match="immutable"):
        ShadowCommandSink(
            clock=FakeClock(),
            qualification=empty_shadow_qualification(ZONES),
            history=cast(Any, []),
            all_zone_ids=ZONES,
            enabled_zone_ids=ZONES,
        )
