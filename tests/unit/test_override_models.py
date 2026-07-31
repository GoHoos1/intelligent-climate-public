"""Exhaustive typed and restart-safe manual-override model tests."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from custom_components.intelligent_climate.models.identifiers import (
    EquipmentGroupId,
    OverrideId,
    ZoneId,
)
from custom_components.intelligent_climate.models.override import (
    MAX_OVERRIDE_DURATION_SECONDS,
    MIN_OVERRIDE_DURATION_SECONDS,
    ControlledField,
    ControlledValues,
    ManualOverride,
    OverrideEndReason,
    OverrideExpirationKind,
    OverrideExpirationPolicy,
    OverrideReasonCode,
    OverrideSource,
    OverrideState,
    OverrideValidationContext,
    decode_manual_override,
    encode_manual_override,
    project_manual_override,
    validate_controlled_values,
    validate_manual_override,
)
from custom_components.intelligent_climate.models.phase2_schema import (
    Phase2RuntimeStoreDocument,
    decode_phase2_runtime_store_document,
    dry_run_phase2_migration,
    encode_phase2_runtime_store_document,
)
from custom_components.intelligent_climate.models.schedule import LocalTime
from custom_components.intelligent_climate.models.schema import SchemaValidationError

ENTRY_ID = "entry-1"
GROUP_ID = EquipmentGroupId.parse("30000000-0000-4000-8000-000000000001")
ZONE_ID = ZoneId.parse("10000000-0000-4000-8000-000000000001")
OTHER_ZONE_ID = ZoneId.parse("10000000-0000-4000-8000-000000000002")
OVERRIDE_ID = OverrideId.parse("50000000-0000-4000-8000-000000000001")
START = datetime(2026, 7, 30, 12, tzinfo=UTC)
ALL_FIELDS = frozenset(ControlledField)
FIXTURE = Path(__file__).parents[1] / "fixtures" / "phase_1_0_0_8_baseline.json"


def _context(
    *,
    entry_id: str = ENTRY_ID,
    group_id: EquipmentGroupId = GROUP_ID,
    fields: frozenset[ControlledField] = ALL_FIELDS,
) -> OverrideValidationContext:
    return OverrideValidationContext(
        entry_id=entry_id,
        equipment_group_id=group_id,
        controlled_fields_by_zone={ZONE_ID: fields},
    )


def _override(**changes: Any) -> ManualOverride:
    value = ManualOverride(
        override_id=OVERRIDE_ID,
        entry_id=ENTRY_ID,
        equipment_group_id=GROUP_ID,
        zone_id=ZONE_ID,
        controlled_fields=frozenset({ControlledField.TARGET}),
        source=OverrideSource.INTELLIGENT_CLIMATE_UI,
        source_context_id="context-1",
        requested_values=ControlledValues(target_c=21.0),
        started_at_utc=START,
        last_updated_at_utc=START,
        expiration_policy=OverrideExpirationPolicy(
            OverrideExpirationKind.DURATION,
            duration_seconds=3600,
        ),
        expires_at_utc=START + timedelta(hours=1),
        anchor_transition_key=None,
        state=OverrideState.ACTIVE,
    )
    return replace(value, **changes)


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
        saved_at=START,
    ).runtime


def test_override_round_trip_is_deterministic_and_restart_safe() -> None:
    value = _override()

    encoded = encode_manual_override(value, validation_context=_context())
    decoded = decode_manual_override(encoded, validation_context=_context())

    assert decoded == value
    assert encode_manual_override(decoded, validation_context=_context()) == encoded
    assert encoded["override_id"] == str(OVERRIDE_ID)
    assert encoded["controlled_fields"] == ["target"]


def test_override_record_survives_authorized_runtime_v2_generic_slot() -> None:
    record = encode_manual_override(_override(), validation_context=_context())
    runtime = replace(_phase2_runtime_document(), overrides=(record,))

    decoded_runtime = decode_phase2_runtime_store_document(
        encode_phase2_runtime_store_document(runtime)
    )
    restored = decode_manual_override(
        dict(decoded_runtime.overrides[0]),
        validation_context=_context(),
    )

    assert restored == _override()


@pytest.mark.parametrize(
    ("fields", "values"),
    [
        (frozenset({ControlledField.TARGET}), ControlledValues(target_c=21.25)),
        (
            frozenset({ControlledField.RANGE}),
            ControlledValues(heat_target_c=19.0, cool_target_c=24.0),
        ),
        (
            frozenset({ControlledField.HVAC_MODE}),
            ControlledValues(hvac_mode="heat"),
        ),
        (frozenset({ControlledField.PRESET}), ControlledValues(preset="eco")),
        (
            frozenset({ControlledField.FAN_MODE}),
            ControlledValues(fan_mode="circulate"),
        ),
        (frozenset({ControlledField.HOLD}), ControlledValues(hold=True)),
        (
            frozenset(
                {
                    ControlledField.TARGET,
                    ControlledField.HVAC_MODE,
                    ControlledField.FAN_MODE,
                }
            ),
            ControlledValues(
                target_c=22.0,
                hvac_mode="cool",
                fan_mode="auto",
            ),
        ),
    ],
)
def test_each_authorized_controlled_value_shape(
    fields: frozenset[ControlledField],
    values: ControlledValues,
) -> None:
    validate_manual_override(
        _override(controlled_fields=fields, requested_values=values),
        validation_context=_context(),
    )


@pytest.mark.parametrize("source", list(OverrideSource))
def test_every_source_category_round_trips(source: OverrideSource) -> None:
    value = _override(source=source)
    assert (
        decode_manual_override(
            encode_manual_override(value, validation_context=_context()),
            validation_context=_context(),
        ).source
        is source
    )


@pytest.mark.parametrize(
    "policy",
    [
        OverrideExpirationPolicy(
            OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
        ),
        OverrideExpirationPolicy(
            OverrideExpirationKind.DURATION,
            duration_seconds=MIN_OVERRIDE_DURATION_SECONDS,
        ),
        OverrideExpirationPolicy(
            OverrideExpirationKind.DURATION,
            duration_seconds=MAX_OVERRIDE_DURATION_SECONDS,
        ),
        OverrideExpirationPolicy(OverrideExpirationKind.NEXT_OCCUPANCY_TRANSITION),
        OverrideExpirationPolicy(
            OverrideExpirationKind.SPECIFIED_LOCAL_TIME,
            local_time=LocalTime(22, 30),
        ),
        OverrideExpirationPolicy(OverrideExpirationKind.MANUAL_CANCELLATION),
        OverrideExpirationPolicy(OverrideExpirationKind.NEXT_DAY_SCHEDULE_START),
    ],
)
def test_every_expiration_policy_round_trips(
    policy: OverrideExpirationPolicy,
) -> None:
    deadline = (
        None
        if policy.kind is OverrideExpirationKind.MANUAL_CANCELLATION
        else START + timedelta(days=1)
    )
    value = _override(
        expiration_policy=policy,
        expires_at_utc=deadline,
    )

    assert (
        decode_manual_override(
            encode_manual_override(value, validation_context=_context()),
            validation_context=_context(),
        ).expiration_policy
        == policy
    )


@pytest.mark.parametrize(
    ("fields", "values", "message"),
    [
        (frozenset(), ControlledValues(), "nonempty immutable set"),
        (
            frozenset({ControlledField.TARGET, ControlledField.RANGE}),
            ControlledValues(
                target_c=20.0,
                heat_target_c=18.0,
                cool_target_c=24.0,
            ),
            "cannot be controlled together",
        ),
        (
            frozenset({ControlledField.TARGET}),
            ControlledValues(),
            "target_c: is required",
        ),
        (
            frozenset({ControlledField.TARGET}),
            ControlledValues(target_c=float("nan")),
            "finite number",
        ),
        (
            frozenset({ControlledField.RANGE}),
            ControlledValues(heat_target_c=24.0, cool_target_c=20.0),
            "must be less",
        ),
        (
            frozenset({ControlledField.HVAC_MODE}),
            ControlledValues(hvac_mode=""),
            "nonempty string",
        ),
        (
            frozenset({ControlledField.HOLD}),
            ControlledValues(hold=1),  # type: ignore[arg-type]
            "boolean",
        ),
        (
            frozenset({ControlledField.HVAC_MODE}),
            ControlledValues(hvac_mode="heat", target_c=20.0),
            "without target ownership",
        ),
    ],
)
def test_invalid_controlled_values_fail_closed(
    fields: frozenset[ControlledField],
    values: ControlledValues,
    message: str,
) -> None:
    with pytest.raises(SchemaValidationError, match=message):
        validate_controlled_values(fields, values)


@pytest.mark.parametrize(
    ("changes", "context", "message"),
    [
        ({"entry_id": "wrong"}, _context(), "loaded entry"),
        (
            {"equipment_group_id": EquipmentGroupId.new()},
            _context(),
            "loaded equipment group",
        ),
        ({"zone_id": OTHER_ZONE_ID}, _context(), "not owned"),
        (
            {"controlled_fields": frozenset({ControlledField.FAN_MODE})},
            _context(fields=frozenset({ControlledField.TARGET})),
            "not owned",
        ),
        (
            {"last_updated_at_utc": START - timedelta(seconds=1)},
            _context(),
            "must not precede",
        ),
        (
            {"expires_at_utc": START - timedelta(seconds=1)},
            _context(),
            "must not precede",
        ),
        (
            {
                "state": OverrideState.ENDED,
                "ended_at_utc": None,
                "end_reason": None,
            },
            _context(),
            "require ended_at",
        ),
        (
            {
                "state": OverrideState.ACTIVE,
                "ended_at_utc": START,
                "end_reason": OverrideEndReason.REPLACED,
            },
            _context(),
            "non-ended",
        ),
    ],
)
def test_identity_ownership_and_lifecycle_validation_fail_closed(
    changes: dict[str, object],
    context: OverrideValidationContext,
    message: str,
) -> None:
    with pytest.raises(SchemaValidationError, match=message):
        validate_manual_override(_override(**changes), validation_context=context)


@pytest.mark.parametrize(
    "policy",
    [
        lambda: OverrideExpirationPolicy(
            OverrideExpirationKind.DURATION,
            duration_seconds=899,
        ),
        lambda: OverrideExpirationPolicy(
            OverrideExpirationKind.DURATION,
            duration_seconds=604801,
        ),
        lambda: OverrideExpirationPolicy(OverrideExpirationKind.DURATION),
        lambda: OverrideExpirationPolicy(OverrideExpirationKind.SPECIFIED_LOCAL_TIME),
        lambda: OverrideExpirationPolicy(
            OverrideExpirationKind.MANUAL_CANCELLATION,
            duration_seconds=900,
        ),
    ],
)
def test_malformed_expiration_policies_are_rejected(
    policy: Callable[[], OverrideExpirationPolicy],
) -> None:
    with pytest.raises(SchemaValidationError):
        policy()


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(extra=True), "unknown field"),
        (lambda value: value.pop("source"), "missing field"),
        (
            lambda value: value.update(controlled_fields=["unsupported"]),
            "unsupported value",
        ),
        (
            lambda value: value.update(started_at_utc="2026-07-30T12:00:00"),
            "timezone-aware",
        ),
        (
            lambda value: value.update(
                requested_values={
                    **value["requested_values"],
                    "target_c": float("inf"),
                }
            ),
            "finite number",
        ),
    ],
)
def test_malformed_serialized_records_are_rejected(
    mutation: Callable[[dict[str, Any]], object],
    message: str,
) -> None:
    encoded = encode_manual_override(_override(), validation_context=_context())
    mutation(encoded)
    with pytest.raises(SchemaValidationError, match=message):
        decode_manual_override(encoded, validation_context=_context())


def test_manual_cancellation_policy_rejects_automatic_deadline() -> None:
    value = _override(
        expiration_policy=OverrideExpirationPolicy(
            OverrideExpirationKind.MANUAL_CANCELLATION
        ),
    )
    with pytest.raises(SchemaValidationError, match="cannot have"):
        validate_manual_override(value, validation_context=_context())


def test_privacy_projection_omits_raw_identity_and_context() -> None:
    value = _override(source_context_id="private-context-value")

    projection = project_manual_override(value)
    rendered = repr(projection)

    assert projection.reason_code is OverrideReasonCode.ACTIVE
    assert projection.explanation == "A manual override is active."
    assert ENTRY_ID not in rendered
    assert str(GROUP_ID) not in rendered
    assert str(ZONE_ID) not in rendered
    assert str(OVERRIDE_ID) not in rendered
    assert "private-context-value" not in rendered


def test_ended_projection_uses_privacy_safe_cancel_reason() -> None:
    ended = _override(
        state=OverrideState.ENDED,
        last_updated_at_utc=START + timedelta(minutes=5),
        ended_at_utc=START + timedelta(minutes=5),
        end_reason=OverrideEndReason.MANUALLY_CANCELLED,
    )

    projection = project_manual_override(ended)

    assert projection.reason_code is OverrideReasonCode.MANUALLY_CANCELLED
    assert projection.explanation == "The manual override was cancelled."


def test_projection_covers_expiring_and_other_terminal_reasons() -> None:
    expiring = _override(state=OverrideState.EXPIRING)
    ended = _override(
        state=OverrideState.ENDED,
        last_updated_at_utc=START + timedelta(minutes=5),
        ended_at_utc=START + timedelta(minutes=5),
        end_reason=OverrideEndReason.RECONCILED,
    )

    assert (
        project_manual_override(expiring).reason_code
        is OverrideReasonCode.EXPIRATION_DUE
    )
    assert project_manual_override(ended).reason_code is OverrideReasonCode.ENDED


def test_context_free_source_and_valid_ended_record_cover_optional_paths() -> None:
    active = _override(source_context_id=None)
    ended = _override(
        source_context_id=None,
        state=OverrideState.ENDED,
        last_updated_at_utc=START + timedelta(minutes=5),
        ended_at_utc=START + timedelta(minutes=5),
        end_reason=OverrideEndReason.EXPIRED,
    )

    validate_manual_override(active, validation_context=_context())
    validate_manual_override(ended, validation_context=_context())


@pytest.mark.parametrize(
    "build",
    [
        lambda: OverrideExpirationPolicy(
            cast(Any, "unsupported"),
        ),
        lambda: OverrideExpirationPolicy(
            OverrideExpirationKind.DURATION,
            duration_seconds=900,
            local_time=LocalTime(1, 0),
        ),
        lambda: OverrideExpirationPolicy(
            OverrideExpirationKind.SPECIFIED_LOCAL_TIME,
            duration_seconds=900,
            local_time=LocalTime(1, 0),
        ),
    ],
)
def test_additional_contradictory_policy_branches_fail_closed(
    build: Callable[[], OverrideExpirationPolicy],
) -> None:
    with pytest.raises(SchemaValidationError):
        build()


@pytest.mark.parametrize(
    ("fields", "values"),
    [
        (
            cast(Any, {ControlledField.TARGET}),
            ControlledValues(target_c=20.0),
        ),
        (
            cast(Any, frozenset({"target"})),
            ControlledValues(target_c=20.0),
        ),
        (
            frozenset({ControlledField.RANGE}),
            ControlledValues(heat_target_c=18.0),
        ),
        (
            frozenset({ControlledField.HVAC_MODE}),
            ControlledValues(heat_target_c=18.0, cool_target_c=24.0),
        ),
        (
            frozenset({ControlledField.HVAC_MODE}),
            ControlledValues(hvac_mode="heat", fan_mode="auto"),
        ),
        (
            frozenset({ControlledField.HVAC_MODE}),
            ControlledValues(hvac_mode="heat", hold=True),
        ),
    ],
)
def test_additional_controlled_field_validation_branches(
    fields: frozenset[ControlledField],
    values: ControlledValues,
) -> None:
    with pytest.raises(SchemaValidationError):
        validate_controlled_values(fields, values)


@pytest.mark.parametrize(
    "changes",
    [
        {"source": cast(Any, "unsupported")},
        {"expires_at_utc": None},
        {"anchor_transition_key": "\n"},
        {"state": cast(Any, "unsupported")},
        {
            "state": OverrideState.ENDED,
            "last_updated_at_utc": START + timedelta(minutes=10),
            "ended_at_utc": START + timedelta(minutes=9),
            "end_reason": OverrideEndReason.EXPIRED,
        },
    ],
)
def test_additional_manual_override_validation_branches(
    changes: dict[str, Any],
) -> None:
    with pytest.raises(SchemaValidationError):
        validate_manual_override(_override(**changes), validation_context=_context())


@pytest.mark.parametrize(
    "mutation",
    [
        lambda value: value["expiration_policy"].update(local_time="2:30"),
        lambda value: value["expiration_policy"].update(local_time=123),
        lambda value: value.update(controlled_fields="target"),
        lambda value: value.update(source=1),
        lambda value: value.update(source_context_id=1),
        lambda value: value["requested_values"].update(hold=1),
        lambda value: value.update(started_at_utc="not-a-datetime"),
        lambda value: value.update(started_at_utc=123),
        lambda value: value.update(started_at_utc="2026-07-30T08:00:00-04:00"),
        lambda value: value.update(override_id="not-a-uuid"),
        lambda value: value.update(equipment_group_id="not-a-uuid"),
        lambda value: value.update(zone_id="not-a-uuid"),
    ],
)
def test_codec_helper_failure_branches_reject_malformed_values(
    mutation: Callable[[dict[str, Any]], object],
) -> None:
    encoded = encode_manual_override(_override(), validation_context=_context())
    mutation(encoded)
    with pytest.raises(SchemaValidationError):
        decode_manual_override(encoded, validation_context=_context())


def test_codec_rejects_non_object_and_non_string_object_keys() -> None:
    with pytest.raises(SchemaValidationError, match="object"):
        decode_manual_override([], validation_context=_context())
    with pytest.raises(SchemaValidationError, match="keys"):
        decode_manual_override(
            cast(Any, {1: "bad"}),
            validation_context=_context(),
        )
