"""Task 11 deterministic command-correlation tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from custom_components.intelligent_climate.command.correlation import (
    CorrelationClassification,
    CorrelationInput,
    CorrelationPolicy,
    CorrelationReasonCode,
    ObservedStateChange,
    correlate_state_change,
    semantic_state_matches,
)
from custom_components.intelligent_climate.models.command import (
    CommandAuthority,
    CommandCause,
    CommandControlledField,
    CommandJournalRecord,
    CommandJournalStatus,
    CommandKind,
    CommandReasonCode,
    NormalizedCommandValues,
    NormalizedStateEvidence,
    ObservationOrigin,
)
from custom_components.intelligent_climate.models.identifiers import (
    CommandId,
    CorrelationId,
    DecisionId,
    EquipmentGroupId,
    SafetyEvaluationId,
    ZoneId,
)
from custom_components.intelligent_climate.models.schema import SchemaValidationError

NOW = datetime(2026, 7, 30, 12, tzinfo=UTC)
COMMAND_ID = CommandId(UUID("00000000-0000-4000-8000-000000000081"))
CORRELATION_ID = CorrelationId(UUID("00000000-0000-4000-8000-000000000082"))


def _state(
    *,
    revision: int = 8,
    when: datetime = NOW + timedelta(seconds=2),
    values: NormalizedCommandValues | None = None,
    available: bool = True,
) -> NormalizedStateEvidence:
    return NormalizedStateEvidence(
        revision=revision,
        observed_at_utc=when,
        available=available,
        values=values or NormalizedCommandValues(target_c=21.0),
    )


def _record(**changes: Any) -> CommandJournalRecord:
    values: dict[str, Any] = {
        "command_id": COMMAND_ID,
        "correlation_id": CORRELATION_ID,
        "decision_id": DecisionId(UUID("00000000-0000-4000-8000-000000000083")),
        "safety_evaluation_id": SafetyEvaluationId(
            UUID("00000000-0000-4000-8000-000000000084")
        ),
        "entry_id": "entry-1",
        "equipment_group_id": EquipmentGroupId(
            UUID("00000000-0000-4000-8000-000000000085")
        ),
        "zone_id": ZoneId(UUID("00000000-0000-4000-8000-000000000086")),
        "target_entity_id": "climate.living_room",
        "command_kind": CommandKind.SET_TARGET,
        "requested_fields": frozenset({CommandControlledField.TARGET}),
        "requested_values": NormalizedCommandValues(target_c=21.0),
        "temperature_tolerance_c": 0.25,
        "observed_precondition": NormalizedStateEvidence(
            revision=7,
            observed_at_utc=NOW - timedelta(seconds=1),
            available=True,
            values=NormalizedCommandValues(target_c=20.0),
        ),
        "requested_against_revision": 7,
        "authority": CommandAuthority.MANUAL,
        "cause": CommandCause.MANUAL_USER,
        "user_context_id": "manual-user-context",
        "created_at_utc": NOW,
        "not_before_utc": NOW,
        "acknowledgement_deadline_utc": NOW + timedelta(seconds=30),
        "status": CommandJournalStatus.DISPATCHED,
        "reason_code": CommandReasonCode.DISPATCH_RECORDED,
        "dispatched_at_utc": NOW + timedelta(seconds=1),
        "action_context_id": "action-context",
        "service_completed_at_utc": NOW + timedelta(seconds=1),
    }
    values.update(changes)
    return CommandJournalRecord(**values)


def _observation(**changes: Any) -> ObservedStateChange:
    values: dict[str, Any] = {
        "entry_id": "entry-1",
        "target_entity_id": "climate.living_room",
        "state": _state(),
        "changed_fields": frozenset({CommandControlledField.TARGET}),
        "origin": ObservationOrigin.UNKNOWN,
    }
    values.update(changes)
    return ObservedStateChange(**values)


def _input(**changes: Any) -> CorrelationInput:
    values: dict[str, Any] = {
        "observation": _observation(),
        "journal": (_record(),),
        "policy": CorrelationPolicy(),
    }
    values.update(changes)
    return CorrelationInput(**values)


@pytest.mark.parametrize(
    ("observation_changes", "expected_reason"),
    [
        (
            {"reported_command_id": COMMAND_ID},
            CorrelationReasonCode.COMMAND_ID_AND_STATE_MATCH,
        ),
        (
            {"reported_correlation_id": CORRELATION_ID},
            CorrelationReasonCode.COMMAND_ID_AND_STATE_MATCH,
        ),
        (
            {"context_id": "action-context"},
            CorrelationReasonCode.CONTEXT_AND_STATE_MATCH,
        ),
        (
            {"parent_context_id": "action-context"},
            CorrelationReasonCode.CONTEXT_AND_STATE_MATCH,
        ),
        (
            {"origin": ObservationOrigin.INTELLIGENT_CLIMATE},
            CorrelationReasonCode.SEMANTIC_PENDING_MATCH,
        ),
        ({}, CorrelationReasonCode.STATE_ONLY_MATCH),
    ],
)
def test_pending_semantic_match_acknowledges_with_bounded_evidence(
    observation_changes: dict[str, Any],
    expected_reason: CorrelationReasonCode,
) -> None:
    result = correlate_state_change(
        _input(observation=_observation(**observation_changes))
    )

    assert result.classification is CorrelationClassification.ACKNOWLEDGED
    assert result.reason_code is expected_reason
    assert result.matched_command_id == COMMAND_ID
    assert result.matched_correlation_id == CORRELATION_ID
    assert result.should_acknowledge is True
    assert result.should_suspend_control is False
    assert "action-context" not in result.explanation


@pytest.mark.parametrize(
    "origin",
    [
        ObservationOrigin.HOME_ASSISTANT_USER,
        ObservationOrigin.HOME_ASSISTANT_AUTOMATION,
        ObservationOrigin.PHYSICAL_DEVICE,
    ],
)
def test_explicit_external_origin_wins_over_coincidental_state_match(
    origin: ObservationOrigin,
) -> None:
    result = correlate_state_change(
        _input(observation=_observation(origin=origin, context_id="other-context"))
    )

    assert result.classification is CorrelationClassification.EXTERNAL_CHANGE
    assert result.reason_code is CorrelationReasonCode.EXPLICIT_EXTERNAL_ORIGIN
    assert result.should_acknowledge is False
    assert result.should_suspend_control is True


def test_context_match_does_not_replace_semantic_acknowledgement() -> None:
    result = correlate_state_change(
        _input(
            observation=_observation(
                context_id="action-context",
                state=_state(values=NormalizedCommandValues(target_c=19.0)),
            )
        )
    )

    assert result.classification is CorrelationClassification.CONFLICTING_RESULT
    assert result.reason_code is CorrelationReasonCode.CONTROLLED_STATE_CONFLICT
    assert result.should_suspend_control is True


def test_missing_action_context_cannot_strengthen_external_origin() -> None:
    record = _record(action_context_id=None)
    result = correlate_state_change(
        _input(
            journal=(record,),
            observation=_observation(
                origin=ObservationOrigin.HOME_ASSISTANT_USER,
                context_id="other-context",
            ),
        )
    )

    assert result.classification is CorrelationClassification.EXTERNAL_CHANGE


@pytest.mark.parametrize(
    ("field", "requested", "observed", "matches"),
    [
        (
            CommandControlledField.TARGET,
            NormalizedCommandValues(target_c=21.0),
            NormalizedCommandValues(target_c=21.25),
            True,
        ),
        (
            CommandControlledField.TARGET,
            NormalizedCommandValues(target_c=21.0),
            NormalizedCommandValues(target_c=21.251),
            False,
        ),
        (
            CommandControlledField.RANGE,
            NormalizedCommandValues(heat_target_c=19.0, cool_target_c=24.0),
            NormalizedCommandValues(heat_target_c=19.2, cool_target_c=23.8),
            True,
        ),
        (
            CommandControlledField.RANGE,
            NormalizedCommandValues(heat_target_c=19.0, cool_target_c=24.0),
            NormalizedCommandValues(heat_target_c=19.2, cool_target_c=23.7),
            False,
        ),
        (
            CommandControlledField.HVAC_MODE,
            NormalizedCommandValues(hvac_mode="heat"),
            NormalizedCommandValues(hvac_mode="heat"),
            True,
        ),
        (
            CommandControlledField.HVAC_MODE,
            NormalizedCommandValues(hvac_mode="heat"),
            NormalizedCommandValues(hvac_mode="cool"),
            False,
        ),
        (
            CommandControlledField.FAN_MODE,
            NormalizedCommandValues(fan_mode="circulate"),
            NormalizedCommandValues(fan_mode="circulate"),
            True,
        ),
        (
            CommandControlledField.FAN_STATE,
            NormalizedCommandValues(fan_state="on"),
            NormalizedCommandValues(fan_state="off"),
            False,
        ),
    ],
)
def test_semantic_match_matrix(
    field: CommandControlledField,
    requested: NormalizedCommandValues,
    observed: NormalizedCommandValues,
    matches: bool,
) -> None:
    assert (
        semantic_state_matches(
            frozenset({field}),
            requested,
            observed,
            temperature_deadband_c=0.25,
        )
        is matches
    )


def test_combined_fields_all_must_match() -> None:
    fields = frozenset(
        {CommandControlledField.TARGET, CommandControlledField.HVAC_MODE}
    )
    assert semantic_state_matches(
        fields,
        NormalizedCommandValues(target_c=21.0, hvac_mode="heat"),
        NormalizedCommandValues(target_c=21.1, hvac_mode="heat"),
        temperature_deadband_c=0.25,
    )
    assert not semantic_state_matches(
        fields,
        NormalizedCommandValues(target_c=21.0, hvac_mode="heat"),
        NormalizedCommandValues(target_c=21.1, hvac_mode="cool"),
        temperature_deadband_c=0.25,
    )


def test_late_recent_ack_matches_only_without_intervening_external_change() -> None:
    result_state = _state(revision=8, when=NOW + timedelta(seconds=3))
    acknowledged = _record(
        status=CommandJournalStatus.ACKNOWLEDGED,
        reason_code=CommandReasonCode.SEMANTIC_ACKNOWLEDGEMENT,
        acknowledged_at_utc=NOW + timedelta(seconds=3),
        observed_result=result_state,
    )
    observation = _observation(
        state=_state(revision=9, when=NOW + timedelta(seconds=120))
    )

    result = correlate_state_change(
        _input(observation=observation, journal=(acknowledged,))
    )
    blocked = correlate_state_change(
        _input(
            observation=observation,
            journal=(acknowledged,),
            external_change_after_last_ack=True,
        )
    )

    assert result.classification is CorrelationClassification.INTELLIGENT_CLIMATE_CHANGE
    assert result.reason_code is CorrelationReasonCode.LATE_ACKNOWLEDGED_MATCH
    assert blocked.classification is CorrelationClassification.EXTERNAL_CHANGE
    assert blocked.should_suspend_control is True


def test_acknowledged_conflict_and_expired_late_match_are_external() -> None:
    acknowledged = _record(
        status=CommandJournalStatus.ACKNOWLEDGED,
        reason_code=CommandReasonCode.SEMANTIC_ACKNOWLEDGEMENT,
        acknowledged_at_utc=NOW + timedelta(seconds=3),
        observed_result=_state(revision=8, when=NOW + timedelta(seconds=3)),
    )
    conflict = correlate_state_change(
        _input(
            journal=(acknowledged,),
            observation=_observation(
                state=_state(
                    revision=9,
                    when=NOW + timedelta(seconds=4),
                    values=NormalizedCommandValues(target_c=19.0),
                )
            ),
        )
    )
    late = correlate_state_change(
        _input(
            journal=(acknowledged,),
            observation=_observation(
                state=_state(
                    revision=9,
                    when=NOW + timedelta(seconds=124),
                )
            ),
        )
    )

    assert conflict.classification is CorrelationClassification.EXTERNAL_CHANGE
    assert conflict.reason_code is CorrelationReasonCode.CONTROLLED_STATE_CONFLICT
    assert late.classification is CorrelationClassification.EXTERNAL_CHANGE


def test_delayed_pending_match_after_deadline_fails_closed() -> None:
    observation = _observation(state=_state(when=NOW + timedelta(seconds=31)))

    strict = correlate_state_change(_input(observation=observation))
    uncertain = correlate_state_change(
        _input(
            observation=observation,
            policy=CorrelationPolicy(all_external_changes_are_overrides=False),
        )
    )

    assert strict.classification is CorrelationClassification.EXTERNAL_CHANGE
    assert uncertain.classification is CorrelationClassification.AMBIGUOUS_ORIGIN
    assert uncertain.should_suspend_control is True


def test_delayed_pending_conflict_is_not_acknowledged() -> None:
    result = correlate_state_change(
        _input(
            observation=_observation(
                state=_state(
                    when=NOW + timedelta(seconds=31),
                    values=NormalizedCommandValues(target_c=19.0),
                )
            )
        )
    )

    assert result.classification is CorrelationClassification.CONFLICTING_RESULT
    assert result.should_acknowledge is False
    assert result.should_suspend_control is True


def test_identifier_mismatch_is_never_attributed_to_pending_command() -> None:
    observation = _observation(
        reported_command_id=CommandId(UUID("00000000-0000-4000-8000-000000000099"))
    )

    result = correlate_state_change(_input(observation=observation))

    assert result.classification is CorrelationClassification.EXTERNAL_CHANGE
    assert result.reason_code is CorrelationReasonCode.IDENTIFIER_MISMATCH
    assert result.matched_command_id is None


def test_telemetry_only_and_unrelated_target_are_not_overrides() -> None:
    telemetry = correlate_state_change(
        _input(observation=_observation(changed_fields=frozenset()))
    )
    wrong_target = correlate_state_change(
        _input(
            observation=_observation(
                target_entity_id="climate.bedroom",
                changed_fields=frozenset({CommandControlledField.TARGET}),
            )
        )
    )

    assert telemetry.classification is CorrelationClassification.UNRELATED_OBSERVATION
    assert telemetry.reason_code is CorrelationReasonCode.TELEMETRY_ONLY
    assert (
        wrong_target.classification is CorrelationClassification.UNRELATED_OBSERVATION
    )
    assert wrong_target.reason_code is CorrelationReasonCode.WRONG_TARGET


def test_no_journal_uses_explicit_or_fail_closed_origin_policy() -> None:
    explicit = correlate_state_change(
        _input(
            journal=(),
            observation=_observation(origin=ObservationOrigin.PHYSICAL_DEVICE),
        )
    )
    strict = correlate_state_change(_input(journal=()))
    uncertain = correlate_state_change(
        _input(
            journal=(),
            policy=CorrelationPolicy(all_external_changes_are_overrides=False),
        )
    )

    assert explicit.classification is CorrelationClassification.EXTERNAL_CHANGE
    assert strict.classification is CorrelationClassification.EXTERNAL_CHANGE
    assert uncertain.classification is CorrelationClassification.AMBIGUOUS_ORIGIN


def test_no_journal_telemetry_only_is_unrelated() -> None:
    result = correlate_state_change(
        _input(
            journal=(),
            observation=_observation(changed_fields=frozenset()),
        )
    )

    assert result.classification is CorrelationClassification.UNRELATED_OBSERVATION
    assert result.reason_code is CorrelationReasonCode.TELEMETRY_ONLY


def test_stale_reordered_duplicate_and_contradictory_observations() -> None:
    stale_revision = correlate_state_change(
        _input(observation=_observation(state=_state(revision=6)))
    )
    before_command = correlate_state_change(
        _input(
            observation=_observation(
                state=_state(
                    revision=8,
                    when=NOW - timedelta(seconds=1),
                )
            )
        )
    )
    last = _state(revision=10, when=NOW + timedelta(seconds=4))
    reordered = correlate_state_change(
        _input(
            observation=_observation(
                state=_state(revision=9, when=NOW + timedelta(seconds=5))
            ),
            last_processed_revision=10,
            last_processed_state=last,
        )
    )
    duplicate_state = _state(revision=10, when=NOW + timedelta(seconds=5))
    duplicate = correlate_state_change(
        _input(
            observation=_observation(state=duplicate_state),
            last_processed_revision=10,
            last_processed_state=last,
        )
    )
    newer = correlate_state_change(
        _input(
            observation=_observation(
                state=_state(revision=11, when=NOW + timedelta(seconds=5))
            ),
            last_processed_revision=10,
            last_processed_state=last,
        )
    )

    assert stale_revision.classification is CorrelationClassification.STALE_OBSERVATION
    assert before_command.reason_code is CorrelationReasonCode.BEFORE_COMMAND
    assert reordered.classification is CorrelationClassification.REORDERED_OBSERVATION
    assert duplicate.classification is CorrelationClassification.DUPLICATE_OBSERVATION
    assert newer.classification is CorrelationClassification.ACKNOWLEDGED
    with pytest.raises(SchemaValidationError):
        correlate_state_change(
            _input(
                observation=_observation(
                    state=_state(
                        revision=10,
                        values=NormalizedCommandValues(target_c=19.0),
                    )
                ),
                last_processed_revision=10,
                last_processed_state=last,
            )
        )


@pytest.mark.parametrize(
    "status",
    [
        CommandJournalStatus.FAILED,
        CommandJournalStatus.UNCERTAIN,
        CommandJournalStatus.SUPPRESSED,
    ],
)
def test_terminal_nonacknowledged_journal_states_do_not_claim_origin(
    status: CommandJournalStatus,
) -> None:
    lifecycle: dict[str, Any]
    if status is CommandJournalStatus.FAILED:
        lifecycle = {
            "reason_code": CommandReasonCode.ACTION_FAILED,
            "failed_at_utc": NOW + timedelta(seconds=2),
        }
    elif status is CommandJournalStatus.UNCERTAIN:
        lifecycle = {
            "reason_code": CommandReasonCode.DISPATCH_OUTCOME_UNKNOWN,
            "failed_at_utc": NOW + timedelta(seconds=2),
        }
    else:
        lifecycle = {
            "reason_code": CommandReasonCode.REJECTED_BEFORE_DISPATCH,
            "suppressed_at_utc": NOW + timedelta(seconds=2),
            "dispatched_at_utc": None,
            "action_context_id": None,
            "service_completed_at_utc": None,
        }
    record = _record(status=status, **lifecycle)

    result = correlate_state_change(_input(journal=(record,)))

    assert result.classification is CorrelationClassification.EXTERNAL_CHANGE
    assert result.should_suspend_control is True


def test_terminal_nonacknowledged_conflict_is_classified_separately() -> None:
    failed = _record(
        status=CommandJournalStatus.FAILED,
        reason_code=CommandReasonCode.ACTION_FAILED,
        failed_at_utc=NOW + timedelta(seconds=2),
    )
    result = correlate_state_change(
        _input(
            journal=(failed,),
            observation=_observation(
                state=_state(values=NormalizedCommandValues(target_c=19.0))
            ),
        )
    )

    assert result.classification is CorrelationClassification.CONFLICTING_RESULT
    assert result.reason_code is CorrelationReasonCode.CONTROLLED_STATE_CONFLICT


def test_manual_and_scheduled_authority_are_correlation_neutral_but_preserved() -> None:
    manual = correlate_state_change(_input())
    scheduled_record = _record(
        authority=CommandAuthority.SCHEDULED,
        cause=CommandCause.SCHEDULE,
        user_context_id=None,
    )
    scheduled = correlate_state_change(_input(journal=(scheduled_record,)))

    assert manual.classification is CorrelationClassification.ACKNOWLEDGED
    assert scheduled.classification is CorrelationClassification.ACKNOWLEDGED
    assert scheduled.matched_command_id == scheduled_record.command_id


@pytest.mark.parametrize(
    "changes",
    [
        {"observation": "bad"},
        {
            "observation": _observation(
                entry_id="",
            )
        },
        {
            "observation": _observation(
                target_entity_id="sensor.room",
            )
        },
        {
            "observation": _observation(
                changed_fields={"target"},
            )
        },
        {
            "observation": _observation(
                changed_fields=frozenset({"target"}),
            )
        },
        {
            "observation": _observation(
                origin="unknown",
            )
        },
        {
            "observation": _observation(
                context_id="",
            )
        },
        {"policy": CorrelationPolicy(late_correlation_seconds=301)},
        {
            "policy": CorrelationPolicy(
                all_external_changes_are_overrides=1  # type: ignore[arg-type]
            )
        },
        {"journal": [_record()]},
        {"journal": (_record(), _record())},
        {
            "journal": (
                _record(),
                _record(
                    command_id=CommandId(UUID("00000000-0000-4000-8000-000000000097"))
                ),
            )
        },
        {"last_processed_revision": 0, "last_processed_state": _state()},
        {"last_processed_revision": 8},
        {
            "last_processed_revision": 9,
            "last_processed_state": _state(revision=8),
        },
        {"last_processed_state": _state()},
        {"external_change_after_last_ack": 1},
    ],
)
def test_malformed_correlation_input_is_rejected(changes: dict[str, Any]) -> None:
    with pytest.raises(SchemaValidationError):
        correlate_state_change(_input(**changes))


@pytest.mark.parametrize("deadband", [-0.1, 5.1, float("nan"), True])
def test_semantic_match_rejects_invalid_deadband(deadband: object) -> None:
    with pytest.raises(SchemaValidationError):
        semantic_state_matches(
            frozenset({CommandControlledField.TARGET}),
            NormalizedCommandValues(target_c=21.0),
            NormalizedCommandValues(target_c=21.0),
            temperature_deadband_c=deadband,  # type: ignore[arg-type]
        )


def test_semantic_match_rejects_empty_and_unsupported_fields() -> None:
    with pytest.raises(SchemaValidationError):
        semantic_state_matches(
            frozenset(),
            NormalizedCommandValues(),
            NormalizedCommandValues(),
            temperature_deadband_c=0.25,
        )
    with pytest.raises(SchemaValidationError):
        semantic_state_matches(
            frozenset({"target"}),  # type: ignore[arg-type]
            NormalizedCommandValues(target_c=21.0),
            NormalizedCommandValues(target_c=21.0),
            temperature_deadband_c=0.25,
        )


def test_semantic_match_includes_exact_decimal_deadband_boundary() -> None:
    assert semantic_state_matches(
        frozenset({CommandControlledField.TARGET}),
        NormalizedCommandValues(target_c=20.3),
        NormalizedCommandValues(target_c=20.0),
        temperature_deadband_c=0.3,
    )
    assert not semantic_state_matches(
        frozenset({CommandControlledField.TARGET}),
        NormalizedCommandValues(target_c=20.300001),
        NormalizedCommandValues(target_c=20.0),
        temperature_deadband_c=0.3,
    )


def test_latest_matching_target_record_is_used_deterministically() -> None:
    older = _record()
    newer = replace(
        older,
        command_id=CommandId(UUID("00000000-0000-4000-8000-000000000091")),
        correlation_id=CorrelationId(UUID("00000000-0000-4000-8000-000000000092")),
        created_at_utc=NOW + timedelta(seconds=3),
        not_before_utc=NOW + timedelta(seconds=3),
        acknowledgement_deadline_utc=NOW + timedelta(seconds=33),
        dispatched_at_utc=NOW + timedelta(seconds=4),
        service_completed_at_utc=NOW + timedelta(seconds=4),
        observed_precondition=NormalizedStateEvidence(
            revision=8,
            observed_at_utc=NOW + timedelta(seconds=2),
            available=True,
            values=NormalizedCommandValues(target_c=21.0),
        ),
        requested_against_revision=8,
        requested_values=NormalizedCommandValues(target_c=22.0),
    )
    observation = _observation(
        state=_state(
            revision=9,
            when=NOW + timedelta(seconds=5),
            values=NormalizedCommandValues(target_c=22.0),
        )
    )

    result = correlate_state_change(
        _input(observation=observation, journal=(newer, older))
    )

    assert result.classification is CorrelationClassification.ACKNOWLEDGED
    assert result.matched_command_id == newer.command_id
