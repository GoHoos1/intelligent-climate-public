"""Test the isolated bounded Phase 2 presentation-trace schema."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast
from uuid import UUID

import pytest

from custom_components.intelligent_climate.models import (
    PRESENTATION_TRACE_BUCKET_MINUTES,
    PRESENTATION_TRACE_MAX_ANNOTATIONS,
    PRESENTATION_TRACE_MAX_SAMPLES_PER_ZONE,
    PRESENTATION_TRACE_RETENTION_HOURS,
    PRESENTATION_TRACE_SCHEMA_VERSION,
    PRESENTATION_TRACE_STORE_MINOR_VERSION,
    PRESENTATION_TRACE_STORE_VERSION,
    EquipmentGroupId,
    PresentationAnnotationKind,
    PresentationContactState,
    PresentationControlContext,
    PresentationFanAction,
    PresentationHvacAction,
    PresentationPointKind,
    PresentationQualityFlag,
    PresentationTraceAnnotation,
    PresentationTraceDocument,
    PresentationTracePoint,
    SchemaMigrationError,
    SchemaValidationError,
    TargetKind,
    TargetSpec,
    ZoneId,
    decode_presentation_trace_document,
    empty_presentation_trace,
    encode_presentation_trace_document,
    validate_presentation_trace,
)

ROOT = Path(__file__).parents[2]
INTEGRATION = ROOT / "custom_components" / "intelligent_climate"
ENTRY_ID = "01JEXAMPLEENTRY"
GROUP_ID = EquipmentGroupId.parse("b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3")
ZONE_ID = ZoneId.parse("99246285-6f02-4e8a-94ed-bdfd4a5e62c4")
OTHER_ZONE_ID = ZoneId.parse("89246285-6f02-4e8a-94ed-bdfd4a5e62c4")
SAVED_AT = datetime(2026, 7, 30, 18, 0, tzinfo=UTC)
POINT_ID = UUID("11111111-1111-4111-8111-111111111111")
ANNOTATION_ID = UUID("22222222-2222-4222-8222-222222222222")
ACTIVITY_ID = UUID("33333333-3333-4333-8333-333333333333")


def _annotation(
    *,
    zone_id: ZoneId = ZONE_ID,
    timestamp: datetime | None = None,
) -> PresentationTraceAnnotation:
    return PresentationTraceAnnotation(
        annotation_id=ANNOTATION_ID,
        zone_id=zone_id,
        timestamp_utc=timestamp or SAVED_AT - timedelta(minutes=5),
        kind=PresentationAnnotationKind.SCHEDULE_TRANSITION,
        activity_record_id=ACTIVITY_ID,
    )


def _point(
    *,
    zone_id: ZoneId = ZONE_ID,
    timestamp: datetime | None = None,
    kind: PresentationPointKind = PresentationPointKind.FIVE_MINUTE_BUCKET,
    annotation_ids: tuple[UUID, ...] = (ANNOTATION_ID,),
) -> PresentationTracePoint:
    return PresentationTracePoint(
        point_id=POINT_ID,
        zone_id=zone_id,
        timestamp_utc=timestamp or SAVED_AT - timedelta(minutes=5),
        kind=kind,
        effective_temperature_c=23.7,
        effective_humidity_pct=50.0,
        outdoor_temperature_c=31.2,
        scheduled_target=TargetSpec(
            kind=TargetKind.SINGLE,
            target_c=23.3,
            heat_target_c=None,
            cool_target_c=None,
        ),
        effective_target=TargetSpec(
            kind=TargetKind.RANGE,
            target_c=None,
            heat_target_c=20.0,
            cool_target_c=24.0,
        ),
        hvac_action=PresentationHvacAction.COOLING,
        fan_action=PresentationFanAction.ON,
        quality_flags=(
            PresentationQualityFlag.TEMPERATURE_VALID,
            PresentationQualityFlag.HUMIDITY_VALID,
            PresentationQualityFlag.OUTDOOR_VALID,
            PresentationQualityFlag.THERMOSTAT_VALID,
        ),
        annotation_ids=annotation_ids,
    )


def _document(
    *,
    point: PresentationTracePoint | None = None,
    annotation: PresentationTraceAnnotation | None = None,
    zone_ids: tuple[ZoneId, ...] = (ZONE_ID,),
) -> PresentationTraceDocument:
    samples: dict[ZoneId, tuple[PresentationTracePoint, ...]] = dict.fromkeys(
        zone_ids, ()
    )
    samples[ZONE_ID] = (_point() if point is None else point,)
    return PresentationTraceDocument(
        entry_id=ENTRY_ID,
        equipment_group_id=GROUP_ID,
        saved_at_utc=SAVED_AT,
        samples_by_zone=MappingProxyType(samples),
        annotations=(_annotation() if annotation is None else annotation,),
    )


def _encode(
    document: PresentationTraceDocument | None = None,
    *,
    zone_ids: frozenset[ZoneId] = frozenset({ZONE_ID}),
) -> dict[str, Any]:
    return dict(
        encode_presentation_trace_document(
            _document() if document is None else document,
            expected_zone_ids=zone_ids,
        )
    )


def test_presentation_trace_contract_is_versioned_bounded_and_auxiliary() -> None:
    """The trace has its own v1 Store and strict finite retention limits."""
    assert (
        PRESENTATION_TRACE_STORE_VERSION,
        PRESENTATION_TRACE_STORE_MINOR_VERSION,
        PRESENTATION_TRACE_SCHEMA_VERSION,
    ) == (1, 0, 2)
    assert PRESENTATION_TRACE_RETENTION_HOURS == 48
    assert PRESENTATION_TRACE_BUCKET_MINUTES == 5
    assert PRESENTATION_TRACE_MAX_SAMPLES_PER_ZONE == 1024
    assert PRESENTATION_TRACE_MAX_ANNOTATIONS == 500


def test_empty_migration_trace_contains_all_zones_and_no_phase1_measurements() -> None:
    """Migration initializes visualization history empty by construction."""
    document = empty_presentation_trace(
        entry_id=ENTRY_ID,
        equipment_group_id=GROUP_ID,
        zone_ids=(OTHER_ZONE_ID, ZONE_ID),
        saved_at_utc=SAVED_AT,
    )

    assert tuple(document.samples_by_zone) == (OTHER_ZONE_ID, ZONE_ID)
    assert document.samples_by_zone[ZONE_ID] == ()
    assert document.samples_by_zone[OTHER_ZONE_ID] == ()
    assert document.annotations == ()
    assert dict(
        encode_presentation_trace_document(
            document,
            expected_zone_ids=frozenset({ZONE_ID, OTHER_ZONE_ID}),
        )
    )["samples_by_zone"] == {
        str(OTHER_ZONE_ID): [],
        str(ZONE_ID): [],
    }


def test_complete_trace_round_trips_with_only_rounded_factual_fields() -> None:
    """The strict codec preserves canonical factual points and references."""
    encoded = _encode()
    decoded = decode_presentation_trace_document(
        encoded,
        expected_entry_id=ENTRY_ID,
        expected_equipment_group_id=GROUP_ID,
        expected_zone_ids=frozenset({ZONE_ID}),
    )

    assert _encode(decoded) == encoded
    point = decoded.samples_by_zone[ZONE_ID][0]
    assert point.effective_temperature_c == 23.7
    assert point.scheduled_target == TargetSpec(
        kind=TargetKind.SINGLE,
        target_c=23.3,
        heat_target_c=None,
        cool_target_c=None,
    )
    assert point.effective_target == TargetSpec(
        kind=TargetKind.RANGE,
        target_c=None,
        heat_target_c=20.0,
        cool_target_c=24.0,
    )
    assert point.annotation_ids == (ANNOTATION_ID,)
    assert point.contact_state is PresentationContactState.NOT_CONFIGURED
    assert point.control_context is PresentationControlContext.NOT_REPORTED
    assert decoded.annotations[0].activity_record_id == ACTIVITY_ID


@pytest.mark.parametrize(
    ("hvac_action", "fan_action"),
    [
        (PresentationHvacAction.NOT_REPORTED, PresentationFanAction.NOT_REPORTED),
        (PresentationHvacAction.UNAVAILABLE, PresentationFanAction.UNAVAILABLE),
        (PresentationHvacAction.UNKNOWN, PresentationFanAction.UNKNOWN),
    ],
)
def test_trace_round_trips_honest_missing_equipment_states(
    hvac_action: PresentationHvacAction,
    fan_action: PresentationFanAction,
) -> None:
    point = replace(
        _point(),
        hvac_action=hvac_action,
        fan_action=fan_action,
    )
    document = _document(point=point)
    encoded = _encode(document)
    decoded = decode_presentation_trace_document(
        encoded,
        expected_entry_id=ENTRY_ID,
        expected_equipment_group_id=GROUP_ID,
        expected_zone_ids=frozenset({ZONE_ID}),
    )
    restored = decoded.samples_by_zone[ZONE_ID][0]
    assert restored.hvac_action is hvac_action
    assert restored.fan_action is fan_action


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda data: data.update(unknown=True), "unknown field"),
        (
            lambda data: data.update(presentation_schema_version=3),
            "future presentation trace",
        ),
        (
            lambda data: data.update(presentation_schema_version=0),
            "no migration path",
        ),
        (lambda data: data.update(entry_id="other"), "loaded config entry"),
        (
            lambda data: data.update(
                equipment_group_id="89246285-6f02-4e8a-94ed-bdfd4a5e62c4"
            ),
            "loaded equipment group",
        ),
    ],
)
def test_trace_decode_rejects_unknown_future_and_foreign_documents(
    mutation: Any,
    match: str,
) -> None:
    """Corrupt/future/foreign trace data cannot enter the canonical model."""
    encoded = _encode()
    mutation(encoded)

    with pytest.raises(
        (SchemaMigrationError, SchemaValidationError),
        match=match,
    ):
        decode_presentation_trace_document(
            encoded,
            expected_entry_id=ENTRY_ID,
            expected_equipment_group_id=GROUP_ID,
            expected_zone_ids=frozenset({ZONE_ID}),
        )


def test_schema_one_trace_migrates_without_inventing_context() -> None:
    """Existing history remains readable and gains honest missing context."""
    encoded = _encode()
    encoded["presentation_schema_version"] = 1
    point = cast(
        list[dict[str, object]],
        cast(dict[str, object], encoded["samples_by_zone"])[str(ZONE_ID)],
    )[0]
    point.pop("contact_state")
    point.pop("control_context")

    decoded = decode_presentation_trace_document(
        encoded,
        expected_entry_id=ENTRY_ID,
        expected_equipment_group_id=GROUP_ID,
        expected_zone_ids=frozenset({ZONE_ID}),
    )

    restored = decoded.samples_by_zone[ZONE_ID][0]
    assert restored.contact_state is PresentationContactState.NOT_CONFIGURED
    assert restored.control_context is PresentationControlContext.NOT_REPORTED
    assert _encode(decoded)["presentation_schema_version"] == 2


@pytest.mark.parametrize(
    ("timestamp", "match"),
    [
        (SAVED_AT - timedelta(hours=48, seconds=1), "rolling 48-hour"),
        (SAVED_AT + timedelta(seconds=1), "rolling 48-hour"),
        (datetime(2026, 7, 30, 17, 55), "timezone information"),
        (
            datetime(
                2026,
                7,
                30,
                13,
                55,
                tzinfo=timezone(timedelta(hours=-4)),
            ),
            "normalized to UTC",
        ),
        (SAVED_AT - timedelta(minutes=3), "five-minute boundaries"),
    ],
)
def test_trace_points_require_utc_alignment_and_rolling_retention(
    timestamp: datetime,
    match: str,
) -> None:
    """Bucket time is explicit UTC and never exceeds the 48-hour window."""
    document = _document(point=_point(timestamp=timestamp))

    with pytest.raises(SchemaValidationError, match=match):
        validate_presentation_trace(
            document,
            expected_zone_ids=frozenset({ZONE_ID}),
        )


def test_material_change_points_need_not_align_to_five_minutes() -> None:
    """Material changes preserve immediate whole instants between buckets."""
    point = _point(
        timestamp=SAVED_AT - timedelta(minutes=3, seconds=17),
        kind=PresentationPointKind.MATERIAL_CHANGE,
    )

    validate_presentation_trace(
        _document(point=point),
        expected_zone_ids=frozenset({ZONE_ID}),
    )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("effective_temperature_c", 23.71, "one decimal"),
        ("effective_humidity_pct", 101.0, "between 0 and 100"),
        ("outdoor_temperature_c", float("nan"), "one decimal"),
    ],
)
def test_trace_rejects_unrounded_nonfinite_or_out_of_range_values(
    field: str,
    value: float,
    match: str,
) -> None:
    """The UI store never retains raw precision or nonfinite observations."""
    point = _point()
    changed = {
        "effective_temperature_c": replace(point, effective_temperature_c=value),
        "effective_humidity_pct": replace(point, effective_humidity_pct=value),
        "outdoor_temperature_c": replace(point, outdoor_temperature_c=value),
    }[field]
    document = _document(point=changed)

    with pytest.raises(SchemaValidationError, match=match):
        validate_presentation_trace(
            document,
            expected_zone_ids=frozenset({ZONE_ID}),
        )


def test_trace_rejects_missing_cross_zone_and_duplicate_annotation_links() -> None:
    """Annotations are typed references, never heuristic frontend joins."""
    unknown = _document(
        point=_point(annotation_ids=(UUID("44444444-4444-4444-8444-444444444444"),))
    )
    with pytest.raises(SchemaValidationError, match="unknown annotation"):
        validate_presentation_trace(
            unknown,
            expected_zone_ids=frozenset({ZONE_ID}),
        )

    cross_zone = _document(
        annotation=_annotation(zone_id=OTHER_ZONE_ID),
        zone_ids=(ZONE_ID, OTHER_ZONE_ID),
    )
    with pytest.raises(SchemaValidationError, match="another zone"):
        validate_presentation_trace(
            cross_zone,
            expected_zone_ids=frozenset({ZONE_ID, OTHER_ZONE_ID}),
        )

    duplicate = _document(point=_point(annotation_ids=(ANNOTATION_ID, ANNOTATION_ID)))
    with pytest.raises(SchemaValidationError, match="duplicates"):
        validate_presentation_trace(
            duplicate,
            expected_zone_ids=frozenset({ZONE_ID}),
        )


def test_trace_requires_canonical_order_and_complete_zone_set() -> None:
    """Stable encoding cannot depend on caller order or omit a configured zone."""
    earlier = replace(
        _point(),
        point_id=UUID("55555555-5555-4555-8555-555555555555"),
        timestamp_utc=SAVED_AT - timedelta(minutes=10),
        annotation_ids=(),
    )
    reversed_points = replace(
        _document(),
        samples_by_zone=MappingProxyType({ZONE_ID: (_point(), earlier)}),
    )
    with pytest.raises(SchemaValidationError, match="chronological order"):
        validate_presentation_trace(
            reversed_points,
            expected_zone_ids=frozenset({ZONE_ID}),
        )

    with pytest.raises(SchemaValidationError, match="every configured zone"):
        validate_presentation_trace(
            _document(),
            expected_zone_ids=frozenset({ZONE_ID, OTHER_ZONE_ID}),
        )


def test_trace_decode_rejects_predicted_planned_and_private_payload_fields() -> None:
    """Phase 2 storage cannot smuggle model output, contexts, or raw attributes."""
    encoded = _encode()
    point = cast(
        list[dict[str, object]],
        cast(dict[str, object], encoded["samples_by_zone"])[str(ZONE_ID)],
    )[0]

    for forbidden in (
        "predicted_temperature_c",
        "planned_target_c",
        "user_id",
        "context_id",
        "raw_attributes",
        "command_payload",
        "exception_text",
    ):
        modified = _encode()
        cast(
            list[dict[str, object]],
            cast(dict[str, object], modified["samples_by_zone"])[str(ZONE_ID)],
        )[0][forbidden] = point.get(forbidden, "forbidden")
        with pytest.raises(SchemaValidationError, match="unknown field"):
            decode_presentation_trace_document(
                modified,
                expected_entry_id=ENTRY_ID,
                expected_equipment_group_id=GROUP_ID,
                expected_zone_ids=frozenset({ZONE_ID}),
            )


def test_presentation_schema_is_structurally_isolated_from_runtime_authority() -> None:
    """Presentation data is an output dependency, never a control input."""
    presentation_source = (INTEGRATION / "models" / "presentation.py").read_text(
        encoding="utf-8"
    )
    prohibited = (
        "homeassistant",
        "Store(",
        "async_save",
        "async_load",
        "services.async_call",
        "command_adapter",
        "SafetyGate",
        "ScheduleEvaluation",
        "shadow_qualification",
        "model_ready",
        "prediction",
    )
    consumers = (
        INTEGRATION / "schedule",
        INTEGRATION / "control",
        INTEGRATION / "coordinator.py",
        INTEGRATION / "storage.py",
    )

    assert all(item not in presentation_source for item in prohibited)
    for consumer in consumers:
        paths = (consumer,) if consumer.is_file() else tuple(consumer.rglob("*.py"))
        for path in paths:
            source = path.read_text(encoding="utf-8")
            assert "models.presentation" not in source
            assert "PresentationTrace" not in source


def test_empty_trace_rejects_empty_duplicate_zones_and_non_utc_time() -> None:
    """Even an empty auxiliary trace has complete identity and UTC bounds."""
    with pytest.raises(SchemaValidationError, match="must not be empty"):
        empty_presentation_trace(
            entry_id=ENTRY_ID,
            equipment_group_id=GROUP_ID,
            zone_ids=(),
            saved_at_utc=SAVED_AT,
        )
    with pytest.raises(SchemaValidationError, match="duplicates"):
        empty_presentation_trace(
            entry_id=ENTRY_ID,
            equipment_group_id=GROUP_ID,
            zone_ids=(ZONE_ID, ZONE_ID),
            saved_at_utc=SAVED_AT,
        )
    with pytest.raises(SchemaValidationError, match="normalized to UTC"):
        empty_presentation_trace(
            entry_id=ENTRY_ID,
            equipment_group_id=GROUP_ID,
            zone_ids=(ZONE_ID,),
            saved_at_utc=datetime(
                2026,
                7,
                30,
                14,
                tzinfo=timezone(timedelta(hours=-4)),
            ),
        )


def test_annotation_validation_rejects_duplicates_order_bounds_and_unknown_zone() -> (
    None
):
    """Material annotations are unique, ordered, retained, and zone-bound."""
    annotation = _annotation()
    duplicate_id = replace(
        annotation,
        activity_record_id=UUID("44444444-4444-4444-8444-444444444444"),
    )
    with pytest.raises(SchemaValidationError, match="duplicate annotation_id"):
        validate_presentation_trace(
            replace(_document(), annotations=(annotation, duplicate_id)),
            expected_zone_ids=frozenset({ZONE_ID}),
        )

    duplicate_activity = replace(
        annotation,
        annotation_id=UUID("44444444-4444-4444-8444-444444444444"),
    )
    with pytest.raises(SchemaValidationError, match="duplicate activity_record_id"):
        validate_presentation_trace(
            replace(_document(), annotations=(annotation, duplicate_activity)),
            expected_zone_ids=frozenset({ZONE_ID}),
        )

    earlier = replace(
        annotation,
        annotation_id=UUID("55555555-5555-4555-8555-555555555555"),
        activity_record_id=UUID("66666666-6666-4666-8666-666666666666"),
        timestamp_utc=annotation.timestamp_utc - timedelta(minutes=5),
    )
    with pytest.raises(SchemaValidationError, match="chronological order"):
        validate_presentation_trace(
            replace(_document(), annotations=(annotation, earlier)),
            expected_zone_ids=frozenset({ZONE_ID}),
        )

    too_old = replace(
        annotation,
        timestamp_utc=SAVED_AT - timedelta(hours=48, seconds=1),
    )
    with pytest.raises(SchemaValidationError, match="rolling 48-hour"):
        validate_presentation_trace(
            replace(_document(), annotations=(too_old,)),
            expected_zone_ids=frozenset({ZONE_ID}),
        )

    unknown_zone = replace(annotation, zone_id=OTHER_ZONE_ID)
    with pytest.raises(SchemaValidationError, match="unknown zone"):
        validate_presentation_trace(
            replace(_document(), annotations=(unknown_zone,)),
            expected_zone_ids=frozenset({ZONE_ID}),
        )


def test_annotation_and_sample_hard_count_bounds_are_enforced() -> None:
    """Material bursts cannot make the auxiliary Store unbounded."""
    annotations = tuple(
        replace(
            _annotation(),
            annotation_id=UUID(int=index + 1),
            activity_record_id=UUID(int=index + 1000),
        )
        for index in range(PRESENTATION_TRACE_MAX_ANNOTATIONS + 1)
    )
    with pytest.raises(SchemaValidationError, match="at most 500"):
        validate_presentation_trace(
            replace(_document(), annotations=annotations),
            expected_zone_ids=frozenset({ZONE_ID}),
        )

    points = tuple(
        replace(
            _point(annotation_ids=(), kind=PresentationPointKind.MATERIAL_CHANGE),
            point_id=UUID(int=index + 1),
        )
        for index in range(PRESENTATION_TRACE_MAX_SAMPLES_PER_ZONE + 1)
    )
    with pytest.raises(SchemaValidationError, match="at most 1024"):
        validate_presentation_trace(
            replace(
                _document(),
                samples_by_zone=MappingProxyType({ZONE_ID: points}),
                annotations=(),
            ),
            expected_zone_ids=frozenset({ZONE_ID}),
        )


def test_point_validation_rejects_duplicate_ids_buckets_zone_and_quality() -> None:
    """Every chart point has stable identity and unambiguous semantics."""
    first = _point(annotation_ids=())
    second_same_id = replace(
        first,
        timestamp_utc=first.timestamp_utc + timedelta(minutes=5),
    )
    with pytest.raises(SchemaValidationError, match="duplicate point_id"):
        validate_presentation_trace(
            replace(
                _document(),
                samples_by_zone=MappingProxyType({ZONE_ID: (first, second_same_id)}),
                annotations=(),
            ),
            expected_zone_ids=frozenset({ZONE_ID}),
        )

    duplicate_bucket = replace(
        first,
        point_id=UUID("55555555-5555-4555-8555-555555555555"),
    )
    with pytest.raises(SchemaValidationError, match="duplicate five-minute"):
        validate_presentation_trace(
            replace(
                _document(),
                samples_by_zone=MappingProxyType({ZONE_ID: (first, duplicate_bucket)}),
                annotations=(),
            ),
            expected_zone_ids=frozenset({ZONE_ID}),
        )

    wrong_zone = replace(first, zone_id=OTHER_ZONE_ID)
    with pytest.raises(SchemaValidationError, match="containing zone"):
        validate_presentation_trace(
            replace(
                _document(),
                samples_by_zone=MappingProxyType({ZONE_ID: (wrong_zone,)}),
                annotations=(),
            ),
            expected_zone_ids=frozenset({ZONE_ID}),
        )

    duplicate_quality = replace(
        first,
        quality_flags=(
            PresentationQualityFlag.TEMPERATURE_VALID,
            PresentationQualityFlag.TEMPERATURE_VALID,
        ),
    )
    with pytest.raises(SchemaValidationError, match="duplicates"):
        validate_presentation_trace(
            replace(
                _document(),
                samples_by_zone=MappingProxyType({ZONE_ID: (duplicate_quality,)}),
                annotations=(),
            ),
            expected_zone_ids=frozenset({ZONE_ID}),
        )


@pytest.mark.parametrize(
    ("target", "match"),
    [
        (
            TargetSpec(
                kind=TargetKind.SINGLE,
                target_c=None,
                heat_target_c=None,
                cool_target_c=None,
            ),
            "target_c.*required",
        ),
        (
            TargetSpec(
                kind=TargetKind.SINGLE,
                target_c=23.0,
                heat_target_c=20.0,
                cool_target_c=None,
            ),
            "range values",
        ),
        (
            TargetSpec(
                kind=TargetKind.RANGE,
                target_c=None,
                heat_target_c=None,
                cool_target_c=24.0,
            ),
            "range endpoints",
        ),
        (
            TargetSpec(
                kind=TargetKind.RANGE,
                target_c=None,
                heat_target_c=25.0,
                cool_target_c=24.0,
            ),
            "less than",
        ),
        (
            TargetSpec(
                kind=TargetKind.RANGE,
                target_c=22.0,
                heat_target_c=20.0,
                cool_target_c=24.0,
            ),
            "single value",
        ),
    ],
)
def test_trace_rejects_every_malformed_target_union(
    target: TargetSpec,
    match: str,
) -> None:
    """Presentation target unions are as strict as schedule target unions."""
    point = replace(_point(), scheduled_target=target)
    with pytest.raises(SchemaValidationError, match=match):
        validate_presentation_trace(
            _document(point=point),
            expected_zone_ids=frozenset({ZONE_ID}),
        )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("point_id", "not-a-uuid", "must be a UUID"),
        ("zone_id", "not-a-uuid", "valid UUID"),
        ("kind", "unknown", "unsupported value"),
        ("hvac_action", "unknown-action", "unsupported value"),
        ("fan_action", "unknown-action", "unsupported value"),
        ("contact_state", "unknown-contact", "unsupported value"),
        ("control_context", "unknown-context", "unsupported value"),
        ("quality_flags", ["unknown"], "unsupported value"),
        ("annotation_ids", ["not-a-uuid"], "must be a UUID"),
        ("effective_temperature_c", "hot", "finite number"),
    ],
)
def test_point_decoder_rejects_invalid_scalar_and_enum_fields(
    field: str,
    value: object,
    match: str,
) -> None:
    """Malformed persisted scalar values never reach the trace model."""
    encoded = _encode()
    point = cast(
        list[dict[str, object]],
        cast(dict[str, object], encoded["samples_by_zone"])[str(ZONE_ID)],
    )[0]
    point[field] = value

    with pytest.raises(SchemaValidationError, match=match):
        decode_presentation_trace_document(
            encoded,
            expected_entry_id=ENTRY_ID,
            expected_equipment_group_id=GROUP_ID,
            expected_zone_ids=frozenset({ZONE_ID}),
        )


def test_annotation_decoder_rejects_invalid_ids_kind_and_timestamp() -> None:
    """Annotation decoding remains strict at every persisted field."""
    mutations = (
        ("annotation_id", "bad", "must be a UUID"),
        ("zone_id", "bad", "valid UUID"),
        ("kind", "bad", "unsupported value"),
        ("activity_record_id", "bad", "must be a UUID"),
        ("timestamp_utc", "not-a-date", "ISO 8601"),
    )
    for field, value, match in mutations:
        encoded = _encode()
        annotation = cast(list[dict[str, object]], encoded["annotations"])[0]
        annotation[field] = value
        with pytest.raises(SchemaValidationError, match=match):
            decode_presentation_trace_document(
                encoded,
                expected_entry_id=ENTRY_ID,
                expected_equipment_group_id=GROUP_ID,
                expected_zone_ids=frozenset({ZONE_ID}),
            )


def test_decode_accepts_missing_optional_measurements_but_rejects_bad_targets() -> None:
    """Unavailable factual series stay null rather than becoming zero."""
    encoded = _encode()
    point = cast(
        list[dict[str, object]],
        cast(dict[str, object], encoded["samples_by_zone"])[str(ZONE_ID)],
    )[0]
    point["effective_temperature_c"] = None
    point["effective_humidity_pct"] = None
    point["outdoor_temperature_c"] = None
    point["scheduled_target"] = None
    point["effective_target"] = None

    decoded = decode_presentation_trace_document(
        encoded,
        expected_entry_id=ENTRY_ID,
        expected_equipment_group_id=GROUP_ID,
        expected_zone_ids=frozenset({ZONE_ID}),
    )
    decoded_point = decoded.samples_by_zone[ZONE_ID][0]
    assert decoded_point.effective_temperature_c is None
    assert decoded_point.scheduled_target is None
    assert _encode(decoded) == encoded

    for target in (
        {
            "kind": "single",
            "target_c": None,
            "heat_target_c": None,
            "cool_target_c": None,
        },
        {
            "kind": "range",
            "target_c": None,
            "heat_target_c": 25.0,
            "cool_target_c": 24.0,
        },
    ):
        modified = _encode()
        cast(
            list[dict[str, object]],
            cast(dict[str, object], modified["samples_by_zone"])[str(ZONE_ID)],
        )[0]["scheduled_target"] = target
        with pytest.raises(SchemaValidationError):
            decode_presentation_trace_document(
                modified,
                expected_entry_id=ENTRY_ID,
                expected_equipment_group_id=GROUP_ID,
                expected_zone_ids=frozenset({ZONE_ID}),
            )


@pytest.mark.parametrize(
    ("mutation", "replacement", "match"),
    [
        (
            lambda value: value.update(presentation_schema_version=True),
            None,
            "must be an integer",
        ),
        (lambda value: value.clear(), [], "must be an object"),
        (lambda value: value.update({1: "bad"}), None, "keys must be strings"),
        (
            lambda value: value.pop("entry_id"),
            None,
            "missing required field",
        ),
        (
            lambda value: value.update(entry_id=123),
            None,
            "must be a string",
        ),
        (
            lambda value: value.update(entry_id=" "),
            None,
            "must be nonempty",
        ),
        (
            lambda value: value.update(equipment_group_id="bad"),
            None,
            "valid UUID",
        ),
        (
            lambda value: value.update(annotations={}),
            None,
            "must be a list",
        ),
    ],
)
def test_document_decoder_rejects_invalid_container_and_primitive_shapes(
    mutation: Any,
    replacement: object | None,
    match: str,
) -> None:
    """Top-level trace boundaries reject malformed persisted JSON shapes."""
    encoded: Any = _encode()
    mutation(encoded)
    value = encoded if replacement is None else replacement

    with pytest.raises(SchemaValidationError, match=match):
        decode_presentation_trace_document(
            value,
            expected_entry_id=ENTRY_ID,
            expected_equipment_group_id=GROUP_ID,
            expected_zone_ids=frozenset({ZONE_ID}),
        )


def test_point_decoder_rejects_nonfinite_and_out_of_range_humidity() -> None:
    """Decode-time numeric checks fail before model publication."""
    for value, match in (
        (float("nan"), "finite"),
        (101.0, "between 0 and 100"),
    ):
        encoded = _encode()
        point = cast(
            list[dict[str, object]],
            cast(dict[str, object], encoded["samples_by_zone"])[str(ZONE_ID)],
        )[0]
        point["effective_humidity_pct"] = value
        with pytest.raises(SchemaValidationError, match=match):
            decode_presentation_trace_document(
                encoded,
                expected_entry_id=ENTRY_ID,
                expected_equipment_group_id=GROUP_ID,
                expected_zone_ids=frozenset({ZONE_ID}),
            )


def test_annotation_decoder_rejects_non_string_ids() -> None:
    """UUID boundaries reject non-string values as well as malformed strings."""
    encoded = _encode()
    annotation = cast(list[dict[str, object]], encoded["annotations"])[0]
    annotation["annotation_id"] = 123

    with pytest.raises(SchemaValidationError, match="must be a string"):
        decode_presentation_trace_document(
            encoded,
            expected_entry_id=ENTRY_ID,
            expected_equipment_group_id=GROUP_ID,
            expected_zone_ids=frozenset({ZONE_ID}),
        )
