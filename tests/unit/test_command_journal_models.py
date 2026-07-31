"""Task 11 command-journal model and codec tests."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast
from uuid import UUID

import pytest

from custom_components.intelligent_climate.models.command import (
    MAX_JOURNAL_RECORDS,
    CommandAuthority,
    CommandCause,
    CommandControlledField,
    CommandJournalRecord,
    CommandJournalStatus,
    CommandKind,
    CommandReasonCode,
    NormalizedCommandValues,
    NormalizedStateEvidence,
    command_journal_projection,
    decode_command_journal,
    decode_command_journal_record,
    encode_command_journal,
    encode_command_journal_record,
    prune_command_journal,
    validate_command_journal_record,
)
from custom_components.intelligent_climate.models.identifiers import (
    CommandId,
    CorrelationId,
    DecisionId,
    EquipmentGroupId,
    SafetyEvaluationId,
    ZoneId,
)
from custom_components.intelligent_climate.models.phase2_schema import (
    Phase2RuntimeStoreDocument,
    decode_phase2_runtime_store_document,
    dry_run_phase2_migration,
    encode_phase2_runtime_store_document,
)
from custom_components.intelligent_climate.models.schema import SchemaValidationError

NOW = datetime(2026, 7, 30, 12, tzinfo=UTC)
COMMAND_ID = CommandId(UUID("00000000-0000-4000-8000-000000000061"))
CORRELATION_ID = CorrelationId(UUID("00000000-0000-4000-8000-000000000062"))
DECISION_ID = DecisionId(UUID("00000000-0000-4000-8000-000000000063"))
SAFETY_ID = SafetyEvaluationId(UUID("00000000-0000-4000-8000-000000000064"))
GROUP_ID = EquipmentGroupId(UUID("00000000-0000-4000-8000-000000000065"))
ZONE_ID = ZoneId(UUID("00000000-0000-4000-8000-000000000066"))
FIXTURE = Path(__file__).parents[1] / "fixtures" / "phase_1_0_0_8_baseline.json"


def _state(
    *,
    revision: int = 7,
    when: datetime = NOW - timedelta(seconds=1),
    values: NormalizedCommandValues | None = None,
    available: bool = True,
) -> NormalizedStateEvidence:
    return NormalizedStateEvidence(
        revision=revision,
        observed_at_utc=when,
        available=available,
        values=values or NormalizedCommandValues(target_c=20.0, hvac_mode="heat"),
    )


def _record(**changes: Any) -> CommandJournalRecord:
    values: dict[str, Any] = {
        "command_id": COMMAND_ID,
        "correlation_id": CORRELATION_ID,
        "decision_id": DECISION_ID,
        "safety_evaluation_id": SAFETY_ID,
        "entry_id": "entry-1",
        "equipment_group_id": GROUP_ID,
        "zone_id": ZONE_ID,
        "target_entity_id": "climate.living_room",
        "command_kind": CommandKind.SET_TARGET,
        "requested_fields": frozenset({CommandControlledField.TARGET}),
        "requested_values": NormalizedCommandValues(target_c=21.0),
        "temperature_tolerance_c": 0.25,
        "observed_precondition": _state(),
        "requested_against_revision": 7,
        "authority": CommandAuthority.MANUAL,
        "cause": CommandCause.MANUAL_USER,
        "user_context_id": "user-context",
        "created_at_utc": NOW,
        "not_before_utc": NOW,
        "acknowledgement_deadline_utc": NOW + timedelta(seconds=30),
        "status": CommandJournalStatus.PENDING,
        "reason_code": CommandReasonCode.REQUEST_ACCEPTED,
    }
    values.update(changes)
    return CommandJournalRecord(**values)


def _precondition_for(
    fields: frozenset[CommandControlledField],
) -> NormalizedStateEvidence:
    return _state(
        values=NormalizedCommandValues(
            target_c=20.0 if CommandControlledField.TARGET in fields else None,
            heat_target_c=(18.0 if CommandControlledField.RANGE in fields else None),
            cool_target_c=(25.0 if CommandControlledField.RANGE in fields else None),
            hvac_mode=("off" if CommandControlledField.HVAC_MODE in fields else None),
            fan_mode=("auto" if CommandControlledField.FAN_MODE in fields else None),
            fan_state=("off" if CommandControlledField.FAN_STATE in fields else None),
        )
    )


def _phase2_runtime_document() -> Phase2RuntimeStoreDocument:
    baseline = cast(
        dict[str, Any],
        json.loads(FIXTURE.read_text(encoding="utf-8")),
    )
    config = baseline["config_entry"]
    return dry_run_phase2_migration(
        entry_id=baseline["runtime_store"]["data"]["entry_id"],
        config_data=config["data"],
        config_version=config["version"],
        config_minor_version=config["minor_version"],
        options_data=baseline["options"],
        zone_data=[baseline["zone_subentry"]],
        runtime_data=baseline["runtime_store"]["data"],
        time_zone="America/New_York",
        saved_at=NOW,
    ).runtime


@pytest.mark.parametrize(
    ("status", "reason", "lifecycle"),
    [
        (
            CommandJournalStatus.PENDING,
            CommandReasonCode.REQUEST_ACCEPTED,
            {},
        ),
        (
            CommandJournalStatus.DISPATCHED,
            CommandReasonCode.DISPATCH_RECORDED,
            {
                "dispatched_at_utc": NOW + timedelta(seconds=1),
                "action_context_id": "action-context",
                "service_completed_at_utc": NOW + timedelta(seconds=2),
            },
        ),
        (
            CommandJournalStatus.ACKNOWLEDGED,
            CommandReasonCode.SEMANTIC_ACKNOWLEDGEMENT,
            {
                "dispatched_at_utc": NOW + timedelta(seconds=1),
                "action_context_id": "action-context",
                "service_completed_at_utc": NOW + timedelta(seconds=2),
                "acknowledged_at_utc": NOW + timedelta(seconds=3),
                "observed_result": _state(
                    revision=8,
                    when=NOW + timedelta(seconds=3),
                    values=NormalizedCommandValues(target_c=21.0),
                ),
            },
        ),
        (
            CommandJournalStatus.FAILED,
            CommandReasonCode.ACTION_FAILED,
            {
                "dispatched_at_utc": NOW + timedelta(seconds=1),
                "failed_at_utc": NOW + timedelta(seconds=2),
            },
        ),
        (
            CommandJournalStatus.FAILED,
            CommandReasonCode.ACKNOWLEDGEMENT_DEADLINE_EXPIRED,
            {
                "dispatched_at_utc": NOW + timedelta(seconds=1),
                "service_completed_at_utc": NOW + timedelta(seconds=2),
                "failed_at_utc": NOW + timedelta(seconds=31),
            },
        ),
        (
            CommandJournalStatus.UNCERTAIN,
            CommandReasonCode.DISPATCH_OUTCOME_UNKNOWN,
            {"failed_at_utc": NOW + timedelta(seconds=1)},
        ),
        (
            CommandJournalStatus.SUPPRESSED,
            CommandReasonCode.REJECTED_BEFORE_DISPATCH,
            {"suppressed_at_utc": NOW + timedelta(seconds=1)},
        ),
    ],
)
def test_every_journal_lifecycle_round_trips(
    status: CommandJournalStatus,
    reason: CommandReasonCode,
    lifecycle: dict[str, Any],
) -> None:
    record = _record(status=status, reason_code=reason, **lifecycle)
    encoded = encode_command_journal_record(record)

    assert decode_command_journal_record(encoded) == record
    assert command_journal_projection(record).status is status
    assert "user-context" not in repr(command_journal_projection(record))
    assert "climate.living_room" not in repr(command_journal_projection(record))


@pytest.mark.parametrize(
    ("kind", "fields", "values"),
    [
        (
            CommandKind.SET_TARGET,
            frozenset({CommandControlledField.TARGET}),
            NormalizedCommandValues(target_c=21.0),
        ),
        (
            CommandKind.SET_TARGET,
            frozenset(
                {
                    CommandControlledField.TARGET,
                    CommandControlledField.HVAC_MODE,
                }
            ),
            NormalizedCommandValues(target_c=21.0, hvac_mode="heat"),
        ),
        (
            CommandKind.SET_RANGE,
            frozenset({CommandControlledField.RANGE}),
            NormalizedCommandValues(heat_target_c=19.0, cool_target_c=24.0),
        ),
        (
            CommandKind.SET_RANGE,
            frozenset(
                {
                    CommandControlledField.RANGE,
                    CommandControlledField.HVAC_MODE,
                }
            ),
            NormalizedCommandValues(
                heat_target_c=19.0,
                cool_target_c=24.0,
                hvac_mode="heat_cool",
            ),
        ),
        (
            CommandKind.SET_HVAC_MODE,
            frozenset({CommandControlledField.HVAC_MODE}),
            NormalizedCommandValues(hvac_mode="cool"),
        ),
        (
            CommandKind.SET_FAN_MODE,
            frozenset({CommandControlledField.FAN_MODE}),
            NormalizedCommandValues(fan_mode="circulate"),
        ),
        (
            CommandKind.FAN_ON,
            frozenset({CommandControlledField.FAN_STATE}),
            NormalizedCommandValues(fan_state="on"),
        ),
        (
            CommandKind.FAN_OFF,
            frozenset({CommandControlledField.FAN_STATE}),
            NormalizedCommandValues(fan_state="off"),
        ),
    ],
)
def test_command_kind_and_normalized_value_matrix(
    kind: CommandKind,
    fields: frozenset[CommandControlledField],
    values: NormalizedCommandValues,
) -> None:
    record = _record(
        command_kind=kind,
        requested_fields=fields,
        requested_values=values,
        observed_precondition=_precondition_for(fields),
    )

    assert (
        decode_command_journal_record(encode_command_journal_record(record)) == record
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"entry_id": ""},
        {"target_entity_id": "sensor.room"},
        {"requested_against_revision": 0},
        {"requested_against_revision": 8},
        {"temperature_tolerance_c": float("nan")},
        {"temperature_tolerance_c": 5.1},
        {"user_context_id": None},
        {"authority": CommandAuthority.SCHEDULED},
        {
            "authority": CommandAuthority.SCHEDULED,
            "cause": CommandCause.SCHEDULE,
            "user_context_id": "forbidden",
        },
        {"cause": CommandCause.SCHEDULE},
        {
            "requested_fields": frozenset({CommandControlledField.RANGE}),
            "requested_values": NormalizedCommandValues(target_c=21.0),
        },
        {
            "requested_fields": frozenset({CommandControlledField.TARGET}),
            "requested_values": NormalizedCommandValues(
                target_c=21.0,
                hvac_mode="heat",
            ),
        },
        {"requested_values": NormalizedCommandValues(target_c=float("nan"))},
        {"requested_values": NormalizedCommandValues(target_c=float("inf"))},
        {
            "command_kind": CommandKind.FAN_ON,
            "requested_fields": frozenset({CommandControlledField.FAN_STATE}),
            "requested_values": NormalizedCommandValues(fan_state="off"),
        },
        {"created_at_utc": NOW.replace(tzinfo=None)},
        {"not_before_utc": NOW - timedelta(seconds=1)},
        {"acknowledgement_deadline_utc": NOW},
        {"acknowledgement_deadline_utc": NOW + timedelta(minutes=6)},
        {
            "status": CommandJournalStatus.DISPATCHED,
            "reason_code": CommandReasonCode.DISPATCH_RECORDED,
        },
        {
            "status": CommandJournalStatus.ACKNOWLEDGED,
            "reason_code": CommandReasonCode.SEMANTIC_ACKNOWLEDGEMENT,
            "dispatched_at_utc": NOW + timedelta(seconds=1),
            "acknowledged_at_utc": NOW + timedelta(seconds=31),
            "observed_result": _state(
                revision=8,
                when=NOW + timedelta(seconds=31),
            ),
        },
        {
            "status": CommandJournalStatus.ACKNOWLEDGED,
            "reason_code": CommandReasonCode.SEMANTIC_ACKNOWLEDGEMENT,
            "dispatched_at_utc": NOW + timedelta(seconds=1),
            "acknowledged_at_utc": NOW + timedelta(seconds=2),
            "observed_result": _state(
                revision=7,
                when=NOW + timedelta(seconds=2),
            ),
        },
        {
            "status": CommandJournalStatus.PENDING,
            "reason_code": CommandReasonCode.ACTION_FAILED,
        },
        {
            "status": CommandJournalStatus.SUPPRESSED,
            "reason_code": CommandReasonCode.REJECTED_BEFORE_DISPATCH,
            "suppressed_at_utc": NOW + timedelta(seconds=1),
            "failed_at_utc": NOW + timedelta(seconds=1),
        },
    ],
)
def test_direct_construction_rejects_contradictory_or_unsafe_records(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(SchemaValidationError):
        _record(**changes)


def test_normalized_state_rejects_contradictory_range_evidence() -> None:
    with pytest.raises(SchemaValidationError):
        _state(
            values=NormalizedCommandValues(
                heat_target_c=22.0,
                cool_target_c=20.0,
            )
        )


@pytest.mark.parametrize(
    ("field", "bad_value"),
    [
        ("command_kind", "set_target"),
        ("authority", "manual"),
        ("cause", "manual_user"),
        ("status", "pending"),
        ("reason_code", "request_accepted"),
    ],
)
def test_record_validator_rejects_untyped_enum_values(
    field: str,
    bad_value: object,
) -> None:
    record = _record()
    object.__setattr__(record, field, bad_value)

    with pytest.raises(SchemaValidationError):
        validate_command_journal_record(record)


def test_state_validator_rejects_nonboolean_availability() -> None:
    state = _state()
    object.__setattr__(state, "available", 1)

    with pytest.raises(SchemaValidationError):
        _record(observed_precondition=state)


@pytest.mark.parametrize(
    "changes",
    [
        {
            "observed_precondition": _state(
                when=NOW + timedelta(seconds=1),
            )
        },
        {
            "status": CommandJournalStatus.FAILED,
            "reason_code": CommandReasonCode.ACTION_FAILED,
            "failed_at_utc": NOW - timedelta(seconds=1),
        },
        {
            "status": CommandJournalStatus.DISPATCHED,
            "reason_code": CommandReasonCode.DISPATCH_RECORDED,
            "not_before_utc": NOW + timedelta(seconds=2),
            "dispatched_at_utc": NOW + timedelta(seconds=1),
        },
        {
            "status": CommandJournalStatus.DISPATCHED,
            "reason_code": CommandReasonCode.DISPATCH_RECORDED,
            "dispatched_at_utc": NOW + timedelta(seconds=2),
            "service_completed_at_utc": NOW + timedelta(seconds=1),
        },
        {
            "status": CommandJournalStatus.ACKNOWLEDGED,
            "reason_code": CommandReasonCode.SEMANTIC_ACKNOWLEDGEMENT,
            "dispatched_at_utc": NOW + timedelta(seconds=1),
            "acknowledged_at_utc": NOW + timedelta(seconds=2),
            "observed_result": _state(
                revision=8,
                when=NOW - timedelta(seconds=1),
            ),
        },
        {
            "requested_values": NormalizedCommandValues(),
        },
        {
            "observed_precondition": _state(
                values=NormalizedCommandValues(hvac_mode="heat"),
            )
        },
        {
            "status": CommandJournalStatus.ACKNOWLEDGED,
            "reason_code": CommandReasonCode.SEMANTIC_ACKNOWLEDGEMENT,
            "dispatched_at_utc": NOW + timedelta(seconds=1),
            "acknowledged_at_utc": NOW + timedelta(seconds=2),
            "observed_result": _state(
                revision=8,
                when=NOW + timedelta(seconds=2),
                values=NormalizedCommandValues(target_c=19.0),
            ),
        },
        {
            "command_kind": CommandKind.FAN_OFF,
            "requested_fields": frozenset({CommandControlledField.FAN_STATE}),
            "requested_values": NormalizedCommandValues(fan_state="on"),
        },
        {
            "requested_values": "bad",
        },
        {
            "command_kind": CommandKind.SET_RANGE,
            "requested_fields": frozenset({CommandControlledField.RANGE}),
            "requested_values": NormalizedCommandValues(heat_target_c=19.0),
        },
        {
            "command_kind": CommandKind.FAN_ON,
            "requested_fields": frozenset({CommandControlledField.FAN_STATE}),
            "requested_values": NormalizedCommandValues(fan_state="invalid"),
        },
        {
            "created_at_utc": datetime(
                2026,
                7,
                30,
                13,
                tzinfo=timezone(timedelta(hours=1)),
            ),
        },
    ],
)
def test_validation_table_rejects_missing_stale_or_contradictory_evidence(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(SchemaValidationError):
        _record(**changes)


@pytest.mark.parametrize(
    ("path", "bad_value"),
    [
        ("command_kind", "unsupported"),
        ("authority", "root"),
        ("status", "complete"),
        ("requested_against_revision", True),
        ("created_at_utc", "bad-time"),
        ("command_id", "not-a-uuid"),
        ("requested_fields", []),
        ("requested_fields", ["target", "target"]),
        ("user_context_id", 42),
        ("observed_result", []),
        ("temperature_tolerance_c", None),
    ],
)
def test_codec_rejects_malformed_fields(path: str, bad_value: object) -> None:
    encoded = encode_command_journal_record(_record())
    encoded[path] = bad_value

    with pytest.raises(SchemaValidationError):
        decode_command_journal_record(encoded)


def test_codec_rejects_missing_unknown_and_non_object_documents() -> None:
    encoded = encode_command_journal_record(_record())
    encoded["unexpected"] = True
    with pytest.raises(SchemaValidationError):
        decode_command_journal_record(encoded)
    encoded.pop("unexpected")
    encoded.pop("entry_id")
    with pytest.raises(SchemaValidationError):
        decode_command_journal_record(encoded)
    with pytest.raises(SchemaValidationError):
        decode_command_journal_record([])


@pytest.mark.parametrize(
    ("path", "bad_value"),
    [
        ("command_kind", 1),
        ("created_at_utc", 1),
        ("created_at_utc", "2026-07-30T13:00:00+01:00"),
    ],
)
def test_codec_rejects_nonstring_and_nonutc_scalars(
    path: str,
    bad_value: object,
) -> None:
    encoded = encode_command_journal_record(_record())
    encoded[path] = bad_value

    with pytest.raises(SchemaValidationError):
        decode_command_journal_record(encoded)


def test_codec_rejects_malformed_nested_state_and_value_objects() -> None:
    encoded = encode_command_journal_record(_record())
    encoded["observed_precondition"]["available"] = 1
    with pytest.raises(SchemaValidationError):
        decode_command_journal_record(encoded)

    encoded = encode_command_journal_record(_record())
    encoded["requested_values"]["target_c"] = "bad"
    with pytest.raises(SchemaValidationError):
        decode_command_journal_record(encoded)

    encoded = encode_command_journal_record(_record())
    encoded["requested_values"] = {1: None}
    with pytest.raises(SchemaValidationError):
        decode_command_journal_record(encoded)


def test_collection_codec_is_canonical_bounded_and_identity_safe() -> None:
    first = _record()
    second = _record(
        command_id=CommandId(UUID("00000000-0000-4000-8000-000000000071")),
        correlation_id=CorrelationId(UUID("00000000-0000-4000-8000-000000000072")),
        created_at_utc=NOW + timedelta(minutes=1),
        not_before_utc=NOW + timedelta(minutes=1),
        acknowledgement_deadline_utc=NOW + timedelta(minutes=1, seconds=30),
        observed_precondition=_state(
            revision=8,
            when=NOW + timedelta(seconds=59),
        ),
        requested_against_revision=8,
    )
    records = (first, second)

    assert decode_command_journal(encode_command_journal(records)) == records
    with pytest.raises(SchemaValidationError):
        encode_command_journal((second, first))
    with pytest.raises(SchemaValidationError):
        encode_command_journal((first, first))
    duplicate_correlation = replace(
        second,
        correlation_id=first.correlation_id,
    )
    with pytest.raises(SchemaValidationError):
        encode_command_journal((first, duplicate_correlation))
    with pytest.raises(SchemaValidationError):
        decode_command_journal({})
    with pytest.raises(SchemaValidationError):
        encode_command_journal([first])  # type: ignore[arg-type]
    with pytest.raises(SchemaValidationError):
        encode_command_journal(tuple(first for _ in range(MAX_JOURNAL_RECORDS + 1)))


def test_pruning_uses_only_caller_clock_and_authorized_bounds() -> None:
    records: list[CommandJournalRecord] = []
    for index in range(105):
        created = NOW - timedelta(days=13) + timedelta(minutes=index)
        records.append(
            _record(
                command_id=CommandId(UUID(f"00000000-0000-4000-8000-{index + 1:012d}")),
                correlation_id=CorrelationId(
                    UUID(f"10000000-0000-4000-8000-{index + 1:012d}")
                ),
                created_at_utc=created,
                not_before_utc=created,
                acknowledgement_deadline_utc=created + timedelta(seconds=30),
                observed_precondition=_state(when=created - timedelta(seconds=1)),
            )
        )
    stale = replace(
        records[0],
        command_id=CommandId(UUID("20000000-0000-4000-8000-000000000001")),
        correlation_id=CorrelationId(UUID("20000000-0000-4000-8000-000000000002")),
        created_at_utc=NOW - timedelta(days=15),
        not_before_utc=NOW - timedelta(days=15),
        acknowledgement_deadline_utc=NOW - timedelta(days=15) + timedelta(seconds=30),
        observed_precondition=_state(when=NOW - timedelta(days=15, seconds=1)),
    )

    retained = prune_command_journal((stale, *records), now_utc=NOW)

    assert len(retained) == 100
    assert stale not in retained
    with pytest.raises(SchemaValidationError):
        prune_command_journal(
            (
                _record(
                    created_at_utc=NOW + timedelta(seconds=1),
                    not_before_utc=NOW + timedelta(seconds=1),
                    acknowledgement_deadline_utc=NOW + timedelta(seconds=31),
                    observed_precondition=_state(when=NOW),
                ),
            ),
            now_utc=NOW,
        )
    with pytest.raises(SchemaValidationError):
        prune_command_journal((), now_utc=NOW.replace(tzinfo=None))


def test_runtime_store_v2_authorized_slot_round_trip_is_restart_safe() -> None:
    record = _record()
    runtime = replace(
        _phase2_runtime_document(),
        command_journal=tuple(encode_command_journal((record,))),
    )

    restored = decode_phase2_runtime_store_document(
        encode_phase2_runtime_store_document(runtime)
    )
    decoded = decode_command_journal(restored.command_journal)

    assert decoded == (record,)


def test_projection_uses_fixed_bounded_explanation_only() -> None:
    record = _record()
    projection = command_journal_projection(record)

    assert projection.reason_code is CommandReasonCode.REQUEST_ACCEPTED
    assert projection.explanation == "The request is awaiting dispatch."
    assert str(record.command_id) not in repr(projection)
    assert record.user_context_id is not None
    assert record.user_context_id not in repr(projection)
