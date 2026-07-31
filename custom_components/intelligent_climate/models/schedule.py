"""Immutable weekly schedule models and their strict JSON boundary."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any
from unicodedata import category
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .identifiers import (
    EquipmentGroupId,
    SchedulePeriodId,
    ScheduleProfileId,
    ZoneId,
)
from .schema import SchemaMigrationError, SchemaValidationError

SCHEDULE_SCHEMA_VERSION = 1
MAX_PERIODS_PER_DAY = 24
MAX_SCHEDULE_LABEL_LENGTH = 64
MIN_TOLERANCE_C = 0.1
MAX_TOLERANCE_C = 2.8


class Weekday(StrEnum):
    """Canonical local-wall-time weekdays."""

    MONDAY = "monday"
    TUESDAY = "tuesday"
    WEDNESDAY = "wednesday"
    THURSDAY = "thursday"
    FRIDAY = "friday"
    SATURDAY = "saturday"
    SUNDAY = "sunday"


WEEKDAYS = tuple(Weekday)


class ScheduleOccupancyLabel(StrEnum):
    """Descriptive occupancy label attached to a schedule period."""

    NONE = "none"
    HOME = "home"
    AWAY = "away"
    SLEEP = "sleep"
    VACATION = "vacation"
    GUEST = "guest"
    CUSTOM = "custom"


class TargetKind(StrEnum):
    """Shape of one literal scheduled temperature target."""

    SINGLE = "single"
    RANGE = "range"


@dataclass(frozen=True, slots=True, order=True)
class LocalTime:
    """Minute-precision local wall time with no date or time zone."""

    hour: int
    minute: int

    def __post_init__(self) -> None:
        """Reject values that cannot be represented as ``HH:MM``."""
        if isinstance(self.hour, bool) or not isinstance(self.hour, int):
            raise ValueError("hour must be an integer")
        if isinstance(self.minute, bool) or not isinstance(self.minute, int):
            raise ValueError("minute must be an integer")
        if not 0 <= self.hour <= 23:
            raise ValueError("hour must be between 0 and 23")
        if not 0 <= self.minute <= 59:
            raise ValueError("minute must be between 0 and 59")

    @classmethod
    def parse(cls, value: str) -> LocalTime:
        """Parse an exact minute-precision ``HH:MM`` value."""
        if (
            len(value) != 5
            or value[2] != ":"
            or not value[:2].isdigit()
            or not value[3:].isdigit()
        ):
            raise ValueError("must use HH:MM minute precision")
        return cls(hour=int(value[:2]), minute=int(value[3:]))

    def __str__(self) -> str:
        """Return the canonical minute-precision value."""
        return f"{self.hour:02d}:{self.minute:02d}"


@dataclass(frozen=True, slots=True)
class TargetSpec:
    """Literal Celsius target for one weekly schedule period."""

    kind: TargetKind
    target_c: float | None
    heat_target_c: float | None
    cool_target_c: float | None


@dataclass(frozen=True, slots=True)
class SchedulePeriod:
    """One local-wall-time boundary and the target active after it."""

    period_id: SchedulePeriodId
    local_start: LocalTime
    label: str
    occupancy_label: ScheduleOccupancyLabel
    target: TargetSpec
    tolerance_c: float


@dataclass(frozen=True, slots=True)
class WeeklyScheduleProfile:
    """One named seven-day schedule profile."""

    profile_id: ScheduleProfileId
    name: str
    enabled: bool
    days: Mapping[Weekday, tuple[SchedulePeriod, ...]]

    def __post_init__(self) -> None:
        """Freeze the weekday mapping against caller mutation."""
        object.__setattr__(self, "days", MappingProxyType(dict(self.days)))


@dataclass(frozen=True, slots=True)
class ZoneScheduleSet:
    """All weekly schedule profiles configured for one zone."""

    zone_id: ZoneId
    enabled: bool
    selected_profile_id: ScheduleProfileId
    profiles: tuple[WeeklyScheduleProfile, ...]


@dataclass(frozen=True, slots=True)
class ScheduleDocument:
    """Complete independently versioned weekly schedule document."""

    schedule_schema_version: int
    entry_id: str
    equipment_group_id: EquipmentGroupId
    time_zone: str
    revision: int
    zones: Mapping[ZoneId, ZoneScheduleSet]
    saved_at_utc: datetime

    def __post_init__(self) -> None:
        """Freeze the zone mapping against caller mutation."""
        object.__setattr__(self, "zones", MappingProxyType(dict(self.zones)))


@dataclass(frozen=True, slots=True)
class ScheduleZoneConstraints:
    """Precomputed safe target capability intersection for one zone."""

    zone_id: ZoneId
    supports_single_target: bool
    supports_target_range: bool
    single_target_min_c: float
    single_target_max_c: float
    heat_target_min_c: float
    heat_target_max_c: float
    cool_target_min_c: float
    cool_target_max_c: float
    minimum_heat_cool_separation_c: float


@dataclass(frozen=True, slots=True)
class ScheduleValidationContext:
    """Authoritative external identity, timezone, zone, and capability context."""

    entry_id: str
    equipment_group_id: EquipmentGroupId
    time_zone: str
    zone_constraints: Mapping[ZoneId, ScheduleZoneConstraints]
    occupancy_profile_ids: Mapping[ZoneId, frozenset[ScheduleProfileId]] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        """Freeze caller-provided validation mappings."""
        object.__setattr__(
            self,
            "zone_constraints",
            MappingProxyType(dict(self.zone_constraints)),
        )
        object.__setattr__(
            self,
            "occupancy_profile_ids",
            MappingProxyType(dict(self.occupancy_profile_ids)),
        )


def decode_schedule_document(
    value: object,
    *,
    validation_context: ScheduleValidationContext,
) -> ScheduleDocument:
    """Strictly decode and fully validate one schedule document."""
    root = _object(value, "")
    _reject_unknown(
        root,
        {
            "schedule_schema_version",
            "entry_id",
            "equipment_group_id",
            "time_zone",
            "revision",
            "zones",
            "saved_at_utc",
        },
        "",
    )
    version = _integer(
        root.get("schedule_schema_version"),
        "schedule_schema_version",
        minimum=0,
    )
    if version > SCHEDULE_SCHEMA_VERSION:
        raise SchemaMigrationError(
            "schedule_schema_version",
            "future schedule schema version is unsupported",
        )
    if version < SCHEDULE_SCHEMA_VERSION:
        raise SchemaMigrationError(
            "schedule_schema_version",
            "no migration path for schedule schema version",
        )

    zones_root = _object(root.get("zones"), "zones")
    zones: dict[ZoneId, ZoneScheduleSet] = {}
    for zone_key, zone_value in zones_root.items():
        zone_id = _parse_zone_id(zone_key, f"zones.{zone_key}")
        zone_set = _decode_zone_schedule_set(
            zone_value,
            f"zones.{zone_key}",
        )
        if zone_set.zone_id != zone_id:
            raise SchemaValidationError(
                f"zones.{zone_key}.zone_id",
                "must match its zones object key",
            )
        zones[zone_id] = zone_set

    document = ScheduleDocument(
        schedule_schema_version=version,
        entry_id=_plain_text(
            root.get("entry_id"),
            "entry_id",
            maximum_length=255,
            require_nonblank=True,
        ),
        equipment_group_id=_parse_equipment_group_id(
            root.get("equipment_group_id"),
            "equipment_group_id",
        ),
        time_zone=_time_zone(root.get("time_zone"), "time_zone"),
        revision=_integer(root.get("revision"), "revision", minimum=0),
        zones=zones,
        saved_at_utc=_utc_datetime(root.get("saved_at_utc"), "saved_at_utc"),
    )
    validate_schedule_document(document, validation_context=validation_context)
    return document


def encode_schedule_document(
    document: ScheduleDocument,
    *,
    validation_context: ScheduleValidationContext,
) -> dict[str, object]:
    """Validate and deterministically encode one schedule document."""
    validate_schedule_document(document, validation_context=validation_context)
    return {
        "schedule_schema_version": document.schedule_schema_version,
        "entry_id": document.entry_id,
        "equipment_group_id": str(document.equipment_group_id),
        "time_zone": document.time_zone,
        "revision": document.revision,
        "zones": {
            str(zone_id): _encode_zone_schedule_set(zone_set)
            for zone_id, zone_set in sorted(
                document.zones.items(),
                key=lambda item: str(item[0]),
            )
        },
        "saved_at_utc": document.saved_at_utc.astimezone(UTC).isoformat(),
    }


def validate_schedule_document(
    document: ScheduleDocument,
    *,
    validation_context: ScheduleValidationContext,
) -> None:
    """Validate the complete schedule atomically against current safe context."""
    _validate_context(validation_context)
    if document.schedule_schema_version != SCHEDULE_SCHEMA_VERSION:
        raise SchemaValidationError(
            "schedule_schema_version",
            f"must equal {SCHEDULE_SCHEMA_VERSION}",
        )
    if document.entry_id != validation_context.entry_id:
        raise SchemaValidationError("entry_id", "does not match the loaded entry")
    if document.equipment_group_id != validation_context.equipment_group_id:
        raise SchemaValidationError(
            "equipment_group_id",
            "does not match the loaded equipment group",
        )
    _time_zone(document.time_zone, "time_zone")
    if document.time_zone != validation_context.time_zone:
        raise SchemaValidationError(
            "time_zone",
            "does not match the acknowledged Home Assistant time zone",
        )
    _integer(document.revision, "revision", minimum=0)
    _validate_utc_datetime(document.saved_at_utc, "saved_at_utc")

    configured_zone_ids = set(validation_context.zone_constraints)
    document_zone_ids = set(document.zones)
    missing_zone_ids = configured_zone_ids - document_zone_ids
    if missing_zone_ids:
        raise SchemaValidationError(
            "zones",
            f"missing configured zone {min(str(item) for item in missing_zone_ids)}",
        )
    unknown_zone_ids = document_zone_ids - configured_zone_ids
    if unknown_zone_ids:
        raise SchemaValidationError(
            "zones",
            f"contains unknown zone {min(str(item) for item in unknown_zone_ids)}",
        )

    profile_ids: set[ScheduleProfileId] = set()
    period_ids: set[SchedulePeriodId] = set()
    for zone_id, zone_set in sorted(
        document.zones.items(),
        key=lambda item: str(item[0]),
    ):
        zone_path = f"zones.{zone_id}"
        if zone_set.zone_id != zone_id:
            raise SchemaValidationError(
                f"{zone_path}.zone_id",
                "must match its zones object key",
            )
        constraints = validation_context.zone_constraints[zone_id]
        _validate_zone_schedule_set(
            zone_set,
            constraints=constraints,
            path=zone_path,
            entry_profile_ids=profile_ids,
            entry_period_ids=period_ids,
        )
        profile_ids.update(profile.profile_id for profile in zone_set.profiles)
        period_ids.update(
            period.period_id
            for profile in zone_set.profiles
            for periods in profile.days.values()
            for period in periods
        )
        required_profiles = validation_context.occupancy_profile_ids.get(
            zone_id,
            frozenset(),
        )
        available_profiles = {profile.profile_id for profile in zone_set.profiles}
        missing_profiles = required_profiles - available_profiles
        if missing_profiles:
            raise SchemaValidationError(
                f"{zone_path}.profiles",
                "does not contain an occupancy-referenced profile",
            )


def _decode_zone_schedule_set(value: object, path: str) -> ZoneScheduleSet:
    root = _object(value, path)
    _reject_unknown(
        root,
        {"zone_id", "enabled", "selected_profile_id", "profiles"},
        path,
    )
    return ZoneScheduleSet(
        zone_id=_parse_zone_id(root.get("zone_id"), f"{path}.zone_id"),
        enabled=_boolean(root.get("enabled"), f"{path}.enabled"),
        selected_profile_id=_parse_profile_id(
            root.get("selected_profile_id"),
            f"{path}.selected_profile_id",
        ),
        profiles=tuple(
            _decode_profile(profile, f"{path}.profiles[{index}]")
            for index, profile in enumerate(
                _list(root.get("profiles"), f"{path}.profiles")
            )
        ),
    )


def _decode_profile(value: object, path: str) -> WeeklyScheduleProfile:
    root = _object(value, path)
    _reject_unknown(root, {"profile_id", "name", "enabled", "days"}, path)
    days_root = _object(root.get("days"), f"{path}.days")
    _reject_unknown(days_root, {weekday.value for weekday in WEEKDAYS}, f"{path}.days")
    return WeeklyScheduleProfile(
        profile_id=_parse_profile_id(
            root.get("profile_id"),
            f"{path}.profile_id",
        ),
        name=_plain_text(
            root.get("name"),
            f"{path}.name",
            maximum_length=MAX_SCHEDULE_LABEL_LENGTH,
            require_nonblank=True,
        ),
        enabled=_boolean(root.get("enabled"), f"{path}.enabled"),
        days={
            weekday: tuple(
                _decode_period(period, f"{path}.days.{weekday.value}[{index}]")
                for index, period in enumerate(
                    _list(
                        days_root.get(weekday.value),
                        f"{path}.days.{weekday.value}",
                    )
                )
            )
            for weekday in WEEKDAYS
        },
    )


def _decode_period(value: object, path: str) -> SchedulePeriod:
    root = _object(value, path)
    _reject_unknown(
        root,
        {
            "period_id",
            "local_start",
            "label",
            "occupancy_label",
            "target",
            "tolerance_c",
        },
        path,
    )
    return SchedulePeriod(
        period_id=_parse_period_id(root.get("period_id"), f"{path}.period_id"),
        local_start=_local_time(root.get("local_start"), f"{path}.local_start"),
        label=_plain_text(
            root.get("label"),
            f"{path}.label",
            maximum_length=MAX_SCHEDULE_LABEL_LENGTH,
            require_nonblank=False,
        ),
        occupancy_label=_enum(
            ScheduleOccupancyLabel,
            root.get("occupancy_label"),
            f"{path}.occupancy_label",
        ),
        target=_decode_target(root.get("target"), f"{path}.target"),
        tolerance_c=_finite_number(
            root.get("tolerance_c"),
            f"{path}.tolerance_c",
        ),
    )


def _decode_target(value: object, path: str) -> TargetSpec:
    root = _object(value, path)
    _reject_unknown(
        root,
        {"kind", "target_c", "heat_target_c", "cool_target_c"},
        path,
    )
    return TargetSpec(
        kind=_enum(TargetKind, root.get("kind"), f"{path}.kind"),
        target_c=_optional_finite_number(root.get("target_c"), f"{path}.target_c"),
        heat_target_c=_optional_finite_number(
            root.get("heat_target_c"),
            f"{path}.heat_target_c",
        ),
        cool_target_c=_optional_finite_number(
            root.get("cool_target_c"),
            f"{path}.cool_target_c",
        ),
    )


def _encode_zone_schedule_set(zone_set: ZoneScheduleSet) -> dict[str, object]:
    return {
        "zone_id": str(zone_set.zone_id),
        "enabled": zone_set.enabled,
        "selected_profile_id": str(zone_set.selected_profile_id),
        "profiles": [
            _encode_profile(profile)
            for profile in sorted(
                zone_set.profiles,
                key=lambda item: str(item.profile_id),
            )
        ],
    }


def _encode_profile(profile: WeeklyScheduleProfile) -> dict[str, object]:
    return {
        "profile_id": str(profile.profile_id),
        "name": profile.name,
        "enabled": profile.enabled,
        "days": {
            weekday.value: [
                _encode_period(period)
                for period in sorted(
                    profile.days[weekday],
                    key=lambda item: item.local_start,
                )
            ]
            for weekday in WEEKDAYS
        },
    }


def _encode_period(period: SchedulePeriod) -> dict[str, object]:
    return {
        "period_id": str(period.period_id),
        "local_start": str(period.local_start),
        "label": period.label,
        "occupancy_label": period.occupancy_label.value,
        "target": {
            "kind": period.target.kind.value,
            "target_c": period.target.target_c,
            "heat_target_c": period.target.heat_target_c,
            "cool_target_c": period.target.cool_target_c,
        },
        "tolerance_c": period.tolerance_c,
    }


def _validate_context(context: ScheduleValidationContext) -> None:
    _plain_text(
        context.entry_id,
        "validation_context.entry_id",
        maximum_length=255,
        require_nonblank=True,
    )
    _time_zone(context.time_zone, "validation_context.time_zone")
    if not context.zone_constraints:
        raise SchemaValidationError(
            "validation_context.zone_constraints",
            "must not be empty",
        )
    for zone_id, constraints in context.zone_constraints.items():
        path = f"validation_context.zone_constraints.{zone_id}"
        if constraints.zone_id != zone_id:
            raise SchemaValidationError(
                f"{path}.zone_id",
                "must match its zone_constraints object key",
            )
        _boolean(
            constraints.supports_single_target,
            f"{path}.supports_single_target",
        )
        _boolean(
            constraints.supports_target_range,
            f"{path}.supports_target_range",
        )
        bounds = (
            (
                "single_target",
                constraints.single_target_min_c,
                constraints.single_target_max_c,
            ),
            (
                "heat_target",
                constraints.heat_target_min_c,
                constraints.heat_target_max_c,
            ),
            (
                "cool_target",
                constraints.cool_target_min_c,
                constraints.cool_target_max_c,
            ),
        )
        for label, minimum, maximum in bounds:
            _finite_number(minimum, f"{path}.{label}_min_c")
            _finite_number(maximum, f"{path}.{label}_max_c")
            if minimum > maximum:
                raise SchemaValidationError(
                    f"{path}.{label}_min_c",
                    f"must not exceed {label}_max_c",
                )
        separation = _finite_number(
            constraints.minimum_heat_cool_separation_c,
            f"{path}.minimum_heat_cool_separation_c",
        )
        if separation < 0:
            raise SchemaValidationError(
                f"{path}.minimum_heat_cool_separation_c",
                "must be at least zero",
            )
    unknown_occupancy_zones = set(context.occupancy_profile_ids) - set(
        context.zone_constraints
    )
    if unknown_occupancy_zones:
        raise SchemaValidationError(
            "validation_context.occupancy_profile_ids",
            "contains an unknown zone",
        )


def _validate_zone_schedule_set(
    zone_set: ZoneScheduleSet,
    *,
    constraints: ScheduleZoneConstraints,
    path: str,
    entry_profile_ids: set[ScheduleProfileId],
    entry_period_ids: set[SchedulePeriodId],
) -> None:
    _boolean(zone_set.enabled, f"{path}.enabled")
    if not zone_set.profiles:
        raise SchemaValidationError(f"{path}.profiles", "must not be empty")

    local_profile_ids: set[ScheduleProfileId] = set()
    folded_names: set[str] = set()
    selected_profile: WeeklyScheduleProfile | None = None
    local_period_ids: set[SchedulePeriodId] = set()
    for profile_index, profile in enumerate(zone_set.profiles):
        profile_path = f"{path}.profiles[{profile_index}]"
        if profile.profile_id in entry_profile_ids | local_profile_ids:
            raise SchemaValidationError(
                f"{profile_path}.profile_id",
                "must be unique within the schedule document",
            )
        local_profile_ids.add(profile.profile_id)
        folded_name = profile.name.casefold()
        if folded_name in folded_names:
            raise SchemaValidationError(
                f"{profile_path}.name",
                "must be unique within the zone after case folding",
            )
        folded_names.add(folded_name)
        if profile.profile_id == zone_set.selected_profile_id:
            selected_profile = profile
        _validate_profile(
            profile,
            constraints=constraints,
            path=profile_path,
            entry_period_ids=entry_period_ids,
            local_period_ids=local_period_ids,
        )

    if selected_profile is None:
        raise SchemaValidationError(
            f"{path}.selected_profile_id",
            "must reference a profile in this zone",
        )
    if zone_set.enabled:
        if not selected_profile.enabled:
            raise SchemaValidationError(
                f"{path}.selected_profile_id",
                "must reference an enabled profile when the zone schedule is enabled",
            )
        if not any(selected_profile.days.values()):
            raise SchemaValidationError(
                f"{path}.selected_profile_id",
                "selected enabled profile must contain at least one weekly period",
            )


def _validate_profile(
    profile: WeeklyScheduleProfile,
    *,
    constraints: ScheduleZoneConstraints,
    path: str,
    entry_period_ids: set[SchedulePeriodId],
    local_period_ids: set[SchedulePeriodId],
) -> None:
    _plain_text(
        profile.name,
        f"{path}.name",
        maximum_length=MAX_SCHEDULE_LABEL_LENGTH,
        require_nonblank=True,
    )
    _boolean(profile.enabled, f"{path}.enabled")
    if set(profile.days) != set(WEEKDAYS):
        raise SchemaValidationError(
            f"{path}.days",
            "must contain each weekday exactly once",
        )
    for weekday in WEEKDAYS:
        periods = profile.days[weekday]
        day_path = f"{path}.days.{weekday.value}"
        if not isinstance(periods, tuple):
            raise SchemaValidationError(day_path, "must be an immutable tuple")
        if len(periods) > MAX_PERIODS_PER_DAY:
            raise SchemaValidationError(
                day_path,
                f"must contain at most {MAX_PERIODS_PER_DAY} periods",
            )
        previous_start: LocalTime | None = None
        for period_index, period in enumerate(periods):
            period_path = f"{day_path}[{period_index}]"
            if period.period_id in entry_period_ids | local_period_ids:
                raise SchemaValidationError(
                    f"{period_path}.period_id",
                    "must be unique within the schedule document",
                )
            local_period_ids.add(period.period_id)
            if previous_start is not None and period.local_start <= previous_start:
                raise SchemaValidationError(
                    f"{period_path}.local_start",
                    "must be unique and in ascending local-time order",
                )
            previous_start = period.local_start
            _validate_period(period, constraints=constraints, path=period_path)


def _validate_period(
    period: SchedulePeriod,
    *,
    constraints: ScheduleZoneConstraints,
    path: str,
) -> None:
    if not isinstance(period.local_start, LocalTime):
        raise SchemaValidationError(
            f"{path}.local_start",
            "must be a minute-precision LocalTime",
        )
    _plain_text(
        period.label,
        f"{path}.label",
        maximum_length=MAX_SCHEDULE_LABEL_LENGTH,
        require_nonblank=False,
    )
    if not isinstance(period.occupancy_label, ScheduleOccupancyLabel):
        raise SchemaValidationError(
            f"{path}.occupancy_label",
            "must be a supported occupancy label",
        )
    tolerance = _finite_number(period.tolerance_c, f"{path}.tolerance_c")
    if not MIN_TOLERANCE_C <= tolerance <= MAX_TOLERANCE_C:
        raise SchemaValidationError(
            f"{path}.tolerance_c",
            f"must be between {MIN_TOLERANCE_C} and {MAX_TOLERANCE_C}",
        )
    _validate_target(period.target, constraints=constraints, path=f"{path}.target")


def _validate_target(
    target: TargetSpec,
    *,
    constraints: ScheduleZoneConstraints,
    path: str,
) -> None:
    if target.kind is TargetKind.SINGLE:
        if not constraints.supports_single_target:
            raise SchemaValidationError(path, "single targets are not supported")
        if (
            target.target_c is None
            or target.heat_target_c is not None
            or target.cool_target_c is not None
        ):
            raise SchemaValidationError(
                path,
                "single target requires only target_c",
            )
        value = _finite_number(target.target_c, f"{path}.target_c")
        if not (
            constraints.single_target_min_c <= value <= constraints.single_target_max_c
        ):
            raise SchemaValidationError(
                f"{path}.target_c",
                "is outside the allowed single-target limits",
            )
        return

    if target.kind is TargetKind.RANGE:
        if not constraints.supports_target_range:
            raise SchemaValidationError(path, "range targets are not supported")
        if (
            target.target_c is not None
            or target.heat_target_c is None
            or target.cool_target_c is None
        ):
            raise SchemaValidationError(
                path,
                "range target requires only heat_target_c and cool_target_c",
            )
        heat = _finite_number(target.heat_target_c, f"{path}.heat_target_c")
        cool = _finite_number(target.cool_target_c, f"{path}.cool_target_c")
        if not constraints.heat_target_min_c <= heat <= constraints.heat_target_max_c:
            raise SchemaValidationError(
                f"{path}.heat_target_c",
                "is outside the allowed heating-target limits",
            )
        if not constraints.cool_target_min_c <= cool <= constraints.cool_target_max_c:
            raise SchemaValidationError(
                f"{path}.cool_target_c",
                "is outside the allowed cooling-target limits",
            )
        if cool - heat < constraints.minimum_heat_cool_separation_c:
            raise SchemaValidationError(
                f"{path}.cool_target_c",
                "does not satisfy the minimum heat/cool separation",
            )
        return

    raise SchemaValidationError(f"{path}.kind", "must be a supported target kind")


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


def _reject_unknown(value: Mapping[str, object], expected: set[str], path: str) -> None:
    unknown = sorted(set(value) - expected)
    if unknown:
        field_path = f"{path}.{unknown[0]}" if path else unknown[0]
        raise SchemaValidationError(field_path, "unknown field")
    missing = sorted(expected - set(value))
    if missing:
        field_path = f"{path}.{missing[0]}" if path else missing[0]
        raise SchemaValidationError(field_path, "missing required field")


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(path, "must be a boolean")
    return value


def _integer(value: object, path: str, *, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaValidationError(path, "must be an integer")
    if value < minimum:
        raise SchemaValidationError(path, f"must be at least {minimum}")
    return value


def _finite_number(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SchemaValidationError(path, "must be a finite number")
    numeric = float(value)
    if not isfinite(numeric):
        raise SchemaValidationError(path, "must be finite")
    return numeric


def _optional_finite_number(value: object, path: str) -> float | None:
    if value is None:
        return None
    return _finite_number(value, path)


def _plain_text(
    value: object,
    path: str,
    *,
    maximum_length: int,
    require_nonblank: bool,
) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    if value != value.strip():
        raise SchemaValidationError(path, "must not have surrounding whitespace")
    if require_nonblank and not value:
        raise SchemaValidationError(path, "must not be empty")
    if len(value) > maximum_length:
        raise SchemaValidationError(
            path,
            f"must contain at most {maximum_length} characters",
        )
    if any(category(character).startswith("C") for character in value):
        raise SchemaValidationError(path, "must not contain control characters")
    if "<" in value or ">" in value:
        raise SchemaValidationError(path, "must not contain markup")
    return value


def _enum[T: StrEnum](enum_type: type[T], value: object, path: str) -> T:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    try:
        return enum_type(value)
    except ValueError as err:
        raise SchemaValidationError(path, "unsupported value") from err


def _local_time(value: object, path: str) -> LocalTime:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    try:
        return LocalTime.parse(value)
    except ValueError as err:
        raise SchemaValidationError(path, str(err)) from err


def _time_zone(value: object, path: str) -> str:
    text = _plain_text(
        value,
        path,
        maximum_length=255,
        require_nonblank=True,
    )
    try:
        ZoneInfo(text)
    except (ValueError, ZoneInfoNotFoundError) as err:
        raise SchemaValidationError(path, "must be a valid IANA time zone") from err
    return text


def _utc_datetime(value: object, path: str) -> datetime:
    text = _plain_text(
        value,
        path,
        maximum_length=64,
        require_nonblank=True,
    )
    try:
        result = datetime.fromisoformat(text)
    except ValueError as err:
        raise SchemaValidationError(path, "must be an ISO 8601 datetime") from err
    _validate_utc_datetime(result, path)
    return result


def _validate_utc_datetime(value: object, path: str) -> datetime:
    if not isinstance(value, datetime):
        raise SchemaValidationError(path, "must be a datetime")
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise SchemaValidationError(path, "must include a UTC offset")
    return value


def _parse_equipment_group_id(value: object, path: str) -> EquipmentGroupId:
    return _parse_identifier(EquipmentGroupId, value, path)


def _parse_zone_id(value: object, path: str) -> ZoneId:
    return _parse_identifier(ZoneId, value, path)


def _parse_profile_id(value: object, path: str) -> ScheduleProfileId:
    return _parse_identifier(ScheduleProfileId, value, path)


def _parse_period_id(value: object, path: str) -> SchedulePeriodId:
    return _parse_identifier(SchedulePeriodId, value, path)


def _parse_identifier[T](
    identifier_type: type[T],
    value: object,
    path: str,
) -> T:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    try:
        return identifier_type.parse(value)  # type: ignore[attr-defined,no-any-return]
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err
