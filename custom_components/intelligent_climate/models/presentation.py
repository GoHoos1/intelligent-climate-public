"""Strict, bounded, nonauthoritative Phase 2 presentation-trace schema."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any
from uuid import UUID

from .identifiers import EquipmentGroupId, ZoneId
from .schedule import TargetKind, TargetSpec
from .schema import SchemaMigrationError, SchemaValidationError

PRESENTATION_TRACE_STORE_VERSION = 1
PRESENTATION_TRACE_STORE_MINOR_VERSION = 0
PRESENTATION_TRACE_SCHEMA_VERSION = 1
PRESENTATION_TRACE_RETENTION_HOURS = 48
PRESENTATION_TRACE_BUCKET_MINUTES = 5
PRESENTATION_TRACE_MAX_SAMPLES_PER_ZONE = 1024
PRESENTATION_TRACE_MAX_ANNOTATIONS = 500

type JsonObject = Mapping[str, Any]


class PresentationPointKind(StrEnum):
    """Why a presentation point exists."""

    FIVE_MINUTE_BUCKET = "five_minute_bucket"
    MATERIAL_CHANGE = "material_change"


class PresentationHvacAction(StrEnum):
    """Allowlisted factual thermostat action values."""

    OFF = "off"
    IDLE = "idle"
    HEATING = "heating"
    COOLING = "cooling"
    DRYING = "drying"
    FAN = "fan"
    NOT_REPORTED = "not_reported"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class PresentationFanAction(StrEnum):
    """Allowlisted factual fan-only circulation values."""

    OFF = "off"
    ON = "on"
    NOT_REPORTED = "not_reported"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class PresentationQualityFlag(StrEnum):
    """Privacy-safe source-quality summaries stored for chart gaps."""

    TEMPERATURE_VALID = "temperature_valid"
    TEMPERATURE_DEGRADED = "temperature_degraded"
    HUMIDITY_VALID = "humidity_valid"
    HUMIDITY_DEGRADED = "humidity_degraded"
    OUTDOOR_VALID = "outdoor_valid"
    OUTDOOR_DEGRADED = "outdoor_degraded"
    THERMOSTAT_VALID = "thermostat_valid"
    THERMOSTAT_DEGRADED = "thermostat_degraded"


class PresentationAnnotationKind(StrEnum):
    """Material event types supported by the Phase 2 Today timeline."""

    SCHEDULE_TRANSITION = "schedule_transition"
    OVERRIDE_STARTED = "override_started"
    OVERRIDE_ENDED = "override_ended"
    OCCUPANCY_CHANGED = "occupancy_changed"
    CONTACT_SUSPENDED = "contact_suspended"
    CONTACT_RESUMED = "contact_resumed"
    SAFE_FALLBACK_STARTED = "safe_fallback_started"
    SAFE_FALLBACK_ENDED = "safe_fallback_ended"
    CONTROL_PAUSED = "control_paused"
    COMMAND_ATTEMPTED = "command_attempted"
    COMMAND_ACKNOWLEDGED = "command_acknowledged"
    COMMAND_FAILED = "command_failed"
    SENSOR_DEGRADED = "sensor_degraded"
    WEATHER_DEGRADED = "weather_degraded"


@dataclass(frozen=True, slots=True)
class PresentationTracePoint:
    """One rounded observation bucket or immediate material-change point."""

    point_id: UUID
    zone_id: ZoneId
    timestamp_utc: datetime
    kind: PresentationPointKind
    effective_temperature_c: float | None
    effective_humidity_pct: float | None
    outdoor_temperature_c: float | None
    scheduled_target: TargetSpec | None
    effective_target: TargetSpec | None
    hvac_action: PresentationHvacAction
    fan_action: PresentationFanAction
    quality_flags: tuple[PresentationQualityFlag, ...]
    annotation_ids: tuple[UUID, ...]


@dataclass(frozen=True, slots=True)
class PresentationTraceAnnotation:
    """One typed reference to a material activity record."""

    annotation_id: UUID
    zone_id: ZoneId
    timestamp_utc: datetime
    kind: PresentationAnnotationKind
    activity_record_id: UUID


@dataclass(frozen=True, slots=True)
class PresentationTraceDocument:
    """Auxiliary presentation trace inner schema 1."""

    entry_id: str
    equipment_group_id: EquipmentGroupId
    saved_at_utc: datetime
    samples_by_zone: Mapping[ZoneId, tuple[PresentationTracePoint, ...]]
    annotations: tuple[PresentationTraceAnnotation, ...]


def empty_presentation_trace(
    *,
    entry_id: str,
    equipment_group_id: EquipmentGroupId,
    zone_ids: tuple[ZoneId, ...],
    saved_at_utc: datetime,
) -> PresentationTraceDocument:
    """Create the only valid migration-time presentation trace: empty."""
    _non_empty_string(entry_id, "entry_id")
    saved_at = _utc_datetime(saved_at_utc, "saved_at_utc")
    if not zone_ids:
        raise SchemaValidationError("zone_ids", "must not be empty")
    if len(set(zone_ids)) != len(zone_ids):
        raise SchemaValidationError("zone_ids", "must not contain duplicates")
    document = PresentationTraceDocument(
        entry_id=entry_id,
        equipment_group_id=equipment_group_id,
        saved_at_utc=saved_at,
        samples_by_zone=MappingProxyType(dict.fromkeys(sorted(zone_ids, key=str), ())),
        annotations=(),
    )
    validate_presentation_trace(document, expected_zone_ids=frozenset(zone_ids))
    return document


def decode_presentation_trace_document(
    value: object,
    *,
    expected_entry_id: str,
    expected_equipment_group_id: EquipmentGroupId,
    expected_zone_ids: frozenset[ZoneId],
) -> PresentationTraceDocument:
    """Decode a strict, identity-bound presentation trace."""
    root = _object(value, "")
    expected = {
        "presentation_schema_version",
        "entry_id",
        "equipment_group_id",
        "saved_at_utc",
        "samples_by_zone",
        "annotations",
    }
    _reject_unknown(root, expected, "")
    _require_version(root.get("presentation_schema_version"))
    samples_root = _object(root.get("samples_by_zone"), "samples_by_zone")
    samples: dict[ZoneId, tuple[PresentationTracePoint, ...]] = {}
    for raw_zone_id, raw_points in samples_root.items():
        zone_id = _zone_id(raw_zone_id, f"samples_by_zone.{raw_zone_id}")
        points = tuple(
            _decode_point(item, f"samples_by_zone.{raw_zone_id}[{index}]")
            for index, item in enumerate(
                _list(raw_points, f"samples_by_zone.{raw_zone_id}")
            )
        )
        samples[zone_id] = points
    annotations = tuple(
        _decode_annotation(item, f"annotations[{index}]")
        for index, item in enumerate(_list(root.get("annotations"), "annotations"))
    )
    document = PresentationTraceDocument(
        entry_id=_non_empty_string(root.get("entry_id"), "entry_id"),
        equipment_group_id=_equipment_group_id(
            root.get("equipment_group_id"), "equipment_group_id"
        ),
        saved_at_utc=_utc_datetime(root.get("saved_at_utc"), "saved_at_utc"),
        samples_by_zone=MappingProxyType(samples),
        annotations=annotations,
    )
    if document.entry_id != expected_entry_id:
        raise SchemaValidationError("entry_id", "does not match loaded config entry")
    if document.equipment_group_id != expected_equipment_group_id:
        raise SchemaValidationError(
            "equipment_group_id", "does not match loaded equipment group"
        )
    validate_presentation_trace(
        document,
        expected_zone_ids=expected_zone_ids,
    )
    return document


def encode_presentation_trace_document(
    document: PresentationTraceDocument,
    *,
    expected_zone_ids: frozenset[ZoneId],
) -> JsonObject:
    """Encode a canonical presentation trace."""
    validate_presentation_trace(
        document,
        expected_zone_ids=expected_zone_ids,
    )
    return {
        "presentation_schema_version": PRESENTATION_TRACE_SCHEMA_VERSION,
        "entry_id": document.entry_id,
        "equipment_group_id": str(document.equipment_group_id),
        "saved_at_utc": document.saved_at_utc.isoformat(),
        "samples_by_zone": {
            str(zone_id): [_encode_point(point) for point in points]
            for zone_id, points in sorted(
                document.samples_by_zone.items(),
                key=lambda item: str(item[0]),
            )
        },
        "annotations": [
            _encode_annotation(annotation) for annotation in document.annotations
        ],
    }


def validate_presentation_trace(
    document: PresentationTraceDocument,
    *,
    expected_zone_ids: frozenset[ZoneId],
) -> None:
    """Validate retention, rounding, identity, references, and ordering."""
    _non_empty_string(document.entry_id, "entry_id")
    saved_at = _utc_datetime(document.saved_at_utc, "saved_at_utc")
    if set(document.samples_by_zone) != set(expected_zone_ids):
        raise SchemaValidationError(
            "samples_by_zone",
            "must contain every configured zone exactly once",
        )
    earliest = saved_at - timedelta(hours=PRESENTATION_TRACE_RETENTION_HOURS)
    annotation_ids = tuple(item.annotation_id for item in document.annotations)
    if len(annotation_ids) != len(set(annotation_ids)):
        raise SchemaValidationError("annotations", "duplicate annotation_id")
    if len(document.annotations) > PRESENTATION_TRACE_MAX_ANNOTATIONS:
        raise SchemaValidationError(
            "annotations",
            f"must contain at most {PRESENTATION_TRACE_MAX_ANNOTATIONS} items",
        )
    _chronological(
        document.annotations,
        "annotations",
        key=lambda item: (item.timestamp_utc, item.annotation_id.hex),
    )
    annotation_index = {item.annotation_id: item for item in document.annotations}
    activity_ids = tuple(item.activity_record_id for item in document.annotations)
    if len(activity_ids) != len(set(activity_ids)):
        raise SchemaValidationError("annotations", "duplicate activity_record_id")
    for index, annotation in enumerate(document.annotations):
        _validate_annotation(
            annotation,
            f"annotations[{index}]",
            earliest=earliest,
            latest=saved_at,
            expected_zone_ids=expected_zone_ids,
        )

    point_ids: set[UUID] = set()
    for zone_id, points in document.samples_by_zone.items():
        path = f"samples_by_zone.{zone_id}"
        if len(points) > PRESENTATION_TRACE_MAX_SAMPLES_PER_ZONE:
            raise SchemaValidationError(
                path,
                f"must contain at most {PRESENTATION_TRACE_MAX_SAMPLES_PER_ZONE} items",
            )
        _chronological(
            points,
            path,
            key=lambda item: (item.timestamp_utc, item.point_id.hex),
        )
        bucket_instants: set[datetime] = set()
        for index, point in enumerate(points):
            point_path = f"{path}[{index}]"
            if point.point_id in point_ids:
                raise SchemaValidationError(point_path, "duplicate point_id")
            point_ids.add(point.point_id)
            if point.zone_id != zone_id:
                raise SchemaValidationError(
                    f"{point_path}.zone_id", "does not match containing zone"
                )
            _validate_point(
                point,
                point_path,
                earliest=earliest,
                latest=saved_at,
            )
            if point.kind is PresentationPointKind.FIVE_MINUTE_BUCKET:
                if point.timestamp_utc in bucket_instants:
                    raise SchemaValidationError(
                        f"{point_path}.timestamp_utc",
                        "duplicate five-minute bucket",
                    )
                bucket_instants.add(point.timestamp_utc)
            if len(point.annotation_ids) != len(set(point.annotation_ids)):
                raise SchemaValidationError(
                    f"{point_path}.annotation_ids", "must not contain duplicates"
                )
            for annotation_id in point.annotation_ids:
                linked_annotation = annotation_index.get(annotation_id)
                if linked_annotation is None:
                    raise SchemaValidationError(
                        f"{point_path}.annotation_ids",
                        "references unknown annotation",
                    )
                if linked_annotation.zone_id != point.zone_id:
                    raise SchemaValidationError(
                        f"{point_path}.annotation_ids",
                        "references annotation for another zone",
                    )


def _validate_point(
    point: PresentationTracePoint,
    path: str,
    *,
    earliest: datetime,
    latest: datetime,
) -> None:
    timestamp = _utc_datetime(point.timestamp_utc, f"{path}.timestamp_utc")
    if not earliest <= timestamp <= latest:
        raise SchemaValidationError(
            f"{path}.timestamp_utc", "must be within the rolling 48-hour window"
        )
    if point.kind is PresentationPointKind.FIVE_MINUTE_BUCKET and (
        timestamp.minute % PRESENTATION_TRACE_BUCKET_MINUTES != 0
        or timestamp.second != 0
        or timestamp.microsecond != 0
    ):
        raise SchemaValidationError(
            f"{path}.timestamp_utc",
            "five-minute buckets must align to UTC five-minute boundaries",
        )
    _rounded_optional(
        point.effective_temperature_c,
        f"{path}.effective_temperature_c",
    )
    _rounded_percentage(
        point.effective_humidity_pct,
        f"{path}.effective_humidity_pct",
    )
    _rounded_optional(
        point.outdoor_temperature_c,
        f"{path}.outdoor_temperature_c",
    )
    for target_name, target in (
        ("scheduled_target", point.scheduled_target),
        ("effective_target", point.effective_target),
    ):
        if target is not None:
            _validate_target(target, f"{path}.{target_name}")
    if len(point.quality_flags) != len(set(point.quality_flags)):
        raise SchemaValidationError(
            f"{path}.quality_flags", "must not contain duplicates"
        )


def _validate_annotation(
    annotation: PresentationTraceAnnotation,
    path: str,
    *,
    earliest: datetime,
    latest: datetime,
    expected_zone_ids: frozenset[ZoneId],
) -> None:
    timestamp = _utc_datetime(annotation.timestamp_utc, f"{path}.timestamp_utc")
    if not earliest <= timestamp <= latest:
        raise SchemaValidationError(
            f"{path}.timestamp_utc", "must be within the rolling 48-hour window"
        )
    if annotation.zone_id not in expected_zone_ids:
        raise SchemaValidationError(f"{path}.zone_id", "references an unknown zone")


def _validate_target(target: TargetSpec, path: str) -> None:
    if target.kind is TargetKind.SINGLE:
        if target.target_c is None:
            raise SchemaValidationError(f"{path}.target_c", "is required")
        _rounded(target.target_c, f"{path}.target_c")
        if target.heat_target_c is not None or target.cool_target_c is not None:
            raise SchemaValidationError(path, "single target has range values")
        return
    if target.heat_target_c is None or target.cool_target_c is None:
        raise SchemaValidationError(path, "range endpoints are required")
    _rounded(target.heat_target_c, f"{path}.heat_target_c")
    _rounded(target.cool_target_c, f"{path}.cool_target_c")
    if target.heat_target_c >= target.cool_target_c:
        raise SchemaValidationError(
            f"{path}.heat_target_c", "must be less than cool_target_c"
        )
    if target.target_c is not None:
        raise SchemaValidationError(path, "range target has single value")


def _decode_point(value: object, path: str) -> PresentationTracePoint:
    root = _object(value, path)
    expected = {
        "point_id",
        "zone_id",
        "timestamp_utc",
        "kind",
        "effective_temperature_c",
        "effective_humidity_pct",
        "outdoor_temperature_c",
        "scheduled_target",
        "effective_target",
        "hvac_action",
        "fan_action",
        "quality_flags",
        "annotation_ids",
    }
    _reject_unknown(root, expected, path)
    return PresentationTracePoint(
        point_id=_uuid(root.get("point_id"), f"{path}.point_id"),
        zone_id=_zone_id(root.get("zone_id"), f"{path}.zone_id"),
        timestamp_utc=_utc_datetime(root.get("timestamp_utc"), f"{path}.timestamp_utc"),
        kind=_enum(PresentationPointKind, root.get("kind"), f"{path}.kind"),
        effective_temperature_c=_optional_finite(
            root.get("effective_temperature_c"),
            f"{path}.effective_temperature_c",
        ),
        effective_humidity_pct=_optional_percentage(
            root.get("effective_humidity_pct"),
            f"{path}.effective_humidity_pct",
        ),
        outdoor_temperature_c=_optional_finite(
            root.get("outdoor_temperature_c"),
            f"{path}.outdoor_temperature_c",
        ),
        scheduled_target=_decode_target(
            root.get("scheduled_target"), f"{path}.scheduled_target"
        ),
        effective_target=_decode_target(
            root.get("effective_target"), f"{path}.effective_target"
        ),
        hvac_action=_enum(
            PresentationHvacAction,
            root.get("hvac_action"),
            f"{path}.hvac_action",
        ),
        fan_action=_enum(
            PresentationFanAction,
            root.get("fan_action"),
            f"{path}.fan_action",
        ),
        quality_flags=tuple(
            _enum(
                PresentationQualityFlag,
                item,
                f"{path}.quality_flags[{index}]",
            )
            for index, item in enumerate(
                _list(root.get("quality_flags"), f"{path}.quality_flags")
            )
        ),
        annotation_ids=tuple(
            _uuid(item, f"{path}.annotation_ids[{index}]")
            for index, item in enumerate(
                _list(root.get("annotation_ids"), f"{path}.annotation_ids")
            )
        ),
    )


def _encode_point(point: PresentationTracePoint) -> JsonObject:
    return {
        "point_id": str(point.point_id),
        "zone_id": str(point.zone_id),
        "timestamp_utc": point.timestamp_utc.isoformat(),
        "kind": point.kind.value,
        "effective_temperature_c": point.effective_temperature_c,
        "effective_humidity_pct": point.effective_humidity_pct,
        "outdoor_temperature_c": point.outdoor_temperature_c,
        "scheduled_target": _encode_target(point.scheduled_target),
        "effective_target": _encode_target(point.effective_target),
        "hvac_action": point.hvac_action.value,
        "fan_action": point.fan_action.value,
        "quality_flags": [item.value for item in point.quality_flags],
        "annotation_ids": [str(item) for item in point.annotation_ids],
    }


def _decode_annotation(
    value: object,
    path: str,
) -> PresentationTraceAnnotation:
    root = _object(value, path)
    _reject_unknown(
        root,
        {
            "annotation_id",
            "zone_id",
            "timestamp_utc",
            "kind",
            "activity_record_id",
        },
        path,
    )
    return PresentationTraceAnnotation(
        annotation_id=_uuid(root.get("annotation_id"), f"{path}.annotation_id"),
        zone_id=_zone_id(root.get("zone_id"), f"{path}.zone_id"),
        timestamp_utc=_utc_datetime(root.get("timestamp_utc"), f"{path}.timestamp_utc"),
        kind=_enum(PresentationAnnotationKind, root.get("kind"), f"{path}.kind"),
        activity_record_id=_uuid(
            root.get("activity_record_id"), f"{path}.activity_record_id"
        ),
    )


def _encode_annotation(
    annotation: PresentationTraceAnnotation,
) -> JsonObject:
    return {
        "annotation_id": str(annotation.annotation_id),
        "zone_id": str(annotation.zone_id),
        "timestamp_utc": annotation.timestamp_utc.isoformat(),
        "kind": annotation.kind.value,
        "activity_record_id": str(annotation.activity_record_id),
    }


def _decode_target(value: object, path: str) -> TargetSpec | None:
    if value is None:
        return None
    root = _object(value, path)
    _reject_unknown(
        root,
        {"kind", "target_c", "heat_target_c", "cool_target_c"},
        path,
    )
    target = TargetSpec(
        kind=_enum(TargetKind, root.get("kind"), f"{path}.kind"),
        target_c=_optional_finite(root.get("target_c"), f"{path}.target_c"),
        heat_target_c=_optional_finite(
            root.get("heat_target_c"), f"{path}.heat_target_c"
        ),
        cool_target_c=_optional_finite(
            root.get("cool_target_c"), f"{path}.cool_target_c"
        ),
    )
    _validate_target(target, path)
    return target


def _encode_target(value: TargetSpec | None) -> JsonObject | None:
    if value is None:
        return None
    return {
        "kind": value.kind.value,
        "target_c": value.target_c,
        "heat_target_c": value.heat_target_c,
        "cool_target_c": value.cool_target_c,
    }


def _require_version(value: object) -> None:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError("presentation_schema_version", "must be an integer")
    if value > PRESENTATION_TRACE_SCHEMA_VERSION:
        raise SchemaMigrationError(
            "presentation_schema_version",
            "future presentation trace version is unsupported",
        )
    if value < PRESENTATION_TRACE_SCHEMA_VERSION:
        raise SchemaMigrationError(
            "presentation_schema_version",
            "no migration path for presentation trace version",
        )


def _object(value: object, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaValidationError(path or "<root>", "must be an object")
    if any(not isinstance(key, str) for key in value):
        raise SchemaValidationError(path or "<root>", "object keys must be strings")
    return dict(value)


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise SchemaValidationError(path, "must be a list")
    return value


def _reject_unknown(root: JsonObject, expected: set[str], path: str) -> None:
    unknown = sorted(set(root) - expected)
    if unknown:
        field = f"{path}.{unknown[0]}" if path else unknown[0]
        raise SchemaValidationError(field, "unknown field")
    missing = sorted(expected - set(root))
    if missing:
        field = f"{path}.{missing[0]}" if path else missing[0]
        raise SchemaValidationError(field, "missing required field")


def _non_empty_string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    if not value or value != value.strip():
        raise SchemaValidationError(
            path, "must be nonempty without surrounding whitespace"
        )
    return value


def _finite(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SchemaValidationError(path, "must be a finite number")
    result = float(value)
    if not isfinite(result):
        raise SchemaValidationError(path, "must be finite")
    return result


def _optional_finite(value: object, path: str) -> float | None:
    return None if value is None else _finite(value, path)


def _optional_percentage(value: object, path: str) -> float | None:
    result = _optional_finite(value, path)
    if result is not None and not 0 <= result <= 100:
        raise SchemaValidationError(path, "must be between 0 and 100")
    return result


def _rounded(value: float, path: str) -> None:
    if not isfinite(value) or round(value, 1) != value:
        raise SchemaValidationError(path, "must be rounded to one decimal place")


def _rounded_optional(value: float | None, path: str) -> None:
    if value is not None:
        _rounded(value, path)


def _rounded_percentage(value: float | None, path: str) -> None:
    if value is not None:
        if not 0 <= value <= 100:
            raise SchemaValidationError(path, "must be between 0 and 100")
        _rounded(value, path)


def _utc_datetime(value: object, path: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    else:
        text = _non_empty_string(value, path)
        try:
            result = datetime.fromisoformat(text)
        except ValueError as err:
            raise SchemaValidationError(path, "must be an ISO 8601 datetime") from err
    if result.tzinfo is None or result.utcoffset() is None:
        raise SchemaValidationError(path, "must include timezone information")
    if result.utcoffset() != timedelta(0):
        raise SchemaValidationError(path, "must be normalized to UTC")
    return result.astimezone(UTC)


def _uuid(value: object, path: str) -> UUID:
    text = _non_empty_string(value, path)
    try:
        return UUID(text)
    except ValueError as err:
        raise SchemaValidationError(path, "must be a UUID") from err


def _zone_id(value: object, path: str) -> ZoneId:
    text = _non_empty_string(value, path)
    try:
        return ZoneId.parse(text)
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err


def _equipment_group_id(value: object, path: str) -> EquipmentGroupId:
    text = _non_empty_string(value, path)
    try:
        return EquipmentGroupId.parse(text)
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err


def _enum[EnumType: StrEnum](
    enum_type: type[EnumType],
    value: object,
    path: str,
) -> EnumType:
    text = _non_empty_string(value, path)
    try:
        return enum_type(text)
    except ValueError as err:
        raise SchemaValidationError(path, "unsupported value") from err


def _chronological[Item](
    values: tuple[Item, ...],
    path: str,
    *,
    key: Any,
) -> None:
    if tuple(sorted(values, key=key)) != values:
        raise SchemaValidationError(path, "must be in canonical chronological order")
