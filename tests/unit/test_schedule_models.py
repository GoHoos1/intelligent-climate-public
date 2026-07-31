"""Test Phase 2 Task 3 weekly schedule models and strict validation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Any

import pytest

from custom_components.intelligent_climate.models import (
    MAX_PERIODS_PER_DAY,
    SCHEDULE_SCHEMA_VERSION,
    EquipmentGroupId,
    LocalTime,
    ScheduleDocument,
    ScheduleOccupancyLabel,
    SchedulePeriod,
    ScheduleProfileId,
    ScheduleValidationContext,
    ScheduleZoneConstraints,
    SchemaMigrationError,
    SchemaValidationError,
    TargetKind,
    Weekday,
    WeeklyScheduleProfile,
    ZoneId,
    ZoneScheduleSet,
    decode_schedule_document,
    encode_schedule_document,
    validate_schedule_document,
)

ENTRY_ID = "entry-01"
GROUP_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
ZONE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"
OTHER_ZONE_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc"
PROFILE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd"
OTHER_PROFILE_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"
PERIOD_ID = "11111111-1111-4111-8111-111111111111"
OTHER_PERIOD_ID = "22222222-2222-4222-8222-222222222222"
TIME_ZONE = "America/New_York"


def _context(
    *,
    zone_id: str = ZONE_ID,
    supports_single_target: bool = True,
    supports_target_range: bool = True,
    occupancy_profile_ids: frozenset[ScheduleProfileId] = frozenset(),
) -> ScheduleValidationContext:
    parsed_zone_id = ZoneId.parse(zone_id)
    return ScheduleValidationContext(
        entry_id=ENTRY_ID,
        equipment_group_id=EquipmentGroupId.parse(GROUP_ID),
        time_zone=TIME_ZONE,
        zone_constraints={
            parsed_zone_id: ScheduleZoneConstraints(
                zone_id=parsed_zone_id,
                supports_single_target=supports_single_target,
                supports_target_range=supports_target_range,
                single_target_min_c=10.0,
                single_target_max_c=30.0,
                heat_target_min_c=7.2,
                heat_target_max_c=26.7,
                cool_target_min_c=15.6,
                cool_target_max_c=35.0,
                minimum_heat_cool_separation_c=1.1,
            )
        },
        occupancy_profile_ids=(
            {parsed_zone_id: occupancy_profile_ids} if occupancy_profile_ids else {}
        ),
    )


def _target(*, range_target: bool = False) -> dict[str, object]:
    if range_target:
        return {
            "kind": "range",
            "target_c": None,
            "heat_target_c": 20.0,
            "cool_target_c": 24.0,
        }
    return {
        "kind": "single",
        "target_c": 22.0,
        "heat_target_c": None,
        "cool_target_c": None,
    }


def _period(
    *,
    period_id: str = PERIOD_ID,
    local_start: str = "06:30",
    range_target: bool = False,
) -> dict[str, object]:
    return {
        "period_id": period_id,
        "local_start": local_start,
        "label": "Morning",
        "occupancy_label": "home",
        "target": _target(range_target=range_target),
        "tolerance_c": 0.5,
    }


def _days(periods: list[dict[str, object]] | None = None) -> dict[str, object]:
    result: dict[str, object] = {weekday.value: [] for weekday in Weekday}
    result["monday"] = periods if periods is not None else [_period()]
    return result


def _profile(
    *,
    profile_id: str = PROFILE_ID,
    name: str = "Normal",
    enabled: bool = True,
    periods: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "profile_id": profile_id,
        "name": name,
        "enabled": enabled,
        "days": _days(periods),
    }


def _payload(*, range_target: bool = False) -> dict[str, object]:
    return {
        "schedule_schema_version": SCHEDULE_SCHEMA_VERSION,
        "entry_id": ENTRY_ID,
        "equipment_group_id": GROUP_ID,
        "time_zone": TIME_ZONE,
        "revision": 0,
        "zones": {
            ZONE_ID: {
                "zone_id": ZONE_ID,
                "enabled": True,
                "selected_profile_id": PROFILE_ID,
                "profiles": [
                    _profile(
                        periods=[_period(range_target=range_target)],
                    )
                ],
            }
        },
        "saved_at_utc": "2026-07-30T15:00:00+00:00",
    }


def _decode(
    payload: object,
    *,
    context: ScheduleValidationContext | None = None,
) -> ScheduleDocument:
    return decode_schedule_document(
        payload,
        validation_context=context or _context(),
    )


def _error(payload: object, path: str) -> SchemaValidationError:
    with pytest.raises(SchemaValidationError) as captured:
        _decode(payload)
    assert captured.value.path == path
    return captured.value


def test_valid_schedule_round_trips_canonically_and_immutably() -> None:
    """A complete document survives strict decode and deterministic encode."""
    payload = _payload()
    document = _decode(payload)

    assert document.entry_id == ENTRY_ID
    assert document.schedule_schema_version == 1
    assert document.saved_at_utc == datetime(2026, 7, 30, 15, tzinfo=UTC)
    assert isinstance(document.zones, MappingProxyType)
    zone = document.zones[ZoneId.parse(ZONE_ID)]
    assert zone.profiles[0].days[Weekday.MONDAY][0].local_start == LocalTime(6, 30)
    assert str(zone.profiles[0].days[Weekday.MONDAY][0].local_start) == "06:30"
    assert (
        encode_schedule_document(
            document,
            validation_context=_context(),
        )
        == payload
    )
    with pytest.raises(TypeError):
        document.zones[ZoneId.new()] = zone  # type: ignore[index]
    with pytest.raises(TypeError):
        zone.profiles[0].days[Weekday.TUESDAY] = ()
    with pytest.raises(FrozenInstanceError):
        zone.enabled = False


def test_encoder_canonicalizes_zone_profile_and_period_order() -> None:
    """Encoding has one stable order independent of input mapping order."""
    payload = _payload()
    zone = payload["zones"][ZONE_ID]  # type: ignore[index]
    second_profile = _profile(
        profile_id=OTHER_PROFILE_ID,
        name="Vacation",
        periods=[
            _period(period_id=OTHER_PERIOD_ID, local_start="18:00"),
            _period(
                period_id="33333333-3333-4333-8333-333333333333",
                local_start="22:00",
            ),
        ],
    )
    zone["profiles"].insert(0, second_profile)
    document = _decode(payload)

    encoded = encode_schedule_document(document, validation_context=_context())
    profiles = encoded["zones"][ZONE_ID]["profiles"]  # type: ignore[index]
    assert [item["profile_id"] for item in profiles] == [
        PROFILE_ID,
        OTHER_PROFILE_ID,
    ]
    assert [item["local_start"] for item in profiles[1]["days"]["monday"]] == [
        "18:00",
        "22:00",
    ]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("00:00", LocalTime(0, 0)),
        ("23:59", LocalTime(23, 59)),
    ],
)
def test_local_time_accepts_exact_minute_precision(
    value: str,
    expected: LocalTime,
) -> None:
    assert LocalTime.parse(value) == expected


@pytest.mark.parametrize(
    "value",
    ["0:00", "00:0", "24:00", "12:60", "12:00:00", "noon", ""],
)
def test_local_time_rejects_noncanonical_or_out_of_range_values(value: str) -> None:
    with pytest.raises(ValueError):
        LocalTime.parse(value)


@pytest.mark.parametrize(
    ("hour", "minute"),
    [(True, 0), (0, False), (-1, 0), (24, 0), (0, -1), (0, 60)],
)
def test_local_time_constructor_rejects_invalid_components(
    hour: Any,
    minute: Any,
) -> None:
    with pytest.raises(ValueError):
        LocalTime(hour, minute)


@pytest.mark.parametrize(
    ("field", "value", "path"),
    [
        ("schedule_schema_version", 0, "schedule_schema_version"),
        ("schedule_schema_version", True, "schedule_schema_version"),
        ("entry_id", "", "entry_id"),
        ("entry_id", " wrong ", "entry_id"),
        ("equipment_group_id", "not-a-uuid", "equipment_group_id"),
        ("time_zone", "Mars/Olympus", "time_zone"),
        ("revision", -1, "revision"),
        ("revision", True, "revision"),
        ("saved_at_utc", "not-a-date", "saved_at_utc"),
        ("saved_at_utc", "2026-07-30T15:00:00", "saved_at_utc"),
        ("saved_at_utc", "2026-07-30T11:00:00-04:00", "saved_at_utc"),
    ],
)
def test_root_scalar_fields_are_strict(
    field: str,
    value: object,
    path: str,
) -> None:
    payload = _payload()
    payload[field] = value
    _error(payload, path)


def test_future_and_past_schedule_versions_fail_with_migration_error() -> None:
    for version, message in (
        (2, "future schedule schema version"),
        (0, "no migration path"),
    ):
        payload = _payload()
        payload["schedule_schema_version"] = version
        with pytest.raises(SchemaValidationError, match=message):
            _decode(payload)

    assert issubclass(SchemaMigrationError, SchemaValidationError)


@pytest.mark.parametrize("field", list(_payload()))
def test_every_root_field_is_required(field: str) -> None:
    payload = _payload()
    del payload[field]
    _error(payload, field)


def test_unknown_fields_are_rejected_at_every_object_level() -> None:
    paths_and_objects = [
        ("future", _payload()),
        ("zones." + ZONE_ID + ".future", _payload()["zones"][ZONE_ID]),  # type: ignore[index]
        (
            "zones." + ZONE_ID + ".profiles[0].future",
            _payload()["zones"][ZONE_ID]["profiles"][0],  # type: ignore[index]
        ),
        (
            "zones." + ZONE_ID + ".profiles[0].days.future",
            _payload()["zones"][ZONE_ID]["profiles"][0]["days"],  # type: ignore[index]
        ),
        (
            "zones." + ZONE_ID + ".profiles[0].days.monday[0].future",
            _payload()["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0],  # type: ignore[index]
        ),
        (
            "zones." + ZONE_ID + ".profiles[0].days.monday[0].target.future",
            _payload()["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0]["target"],  # type: ignore[index]
        ),
    ]
    for expected_path, target in paths_and_objects:
        payload = _payload()
        if expected_path == "future":
            target = payload
        elif ".target." in expected_path:
            target = payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0][  # type: ignore[index]
                "target"
            ]
        elif ".days.monday[0]." in expected_path:
            target = payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0]  # type: ignore[index]
        elif ".days." in expected_path:
            target = payload["zones"][ZONE_ID]["profiles"][0]["days"]  # type: ignore[index]
        elif ".profiles[0]." in expected_path:
            target = payload["zones"][ZONE_ID]["profiles"][0]  # type: ignore[index]
        else:
            target = payload["zones"][ZONE_ID]  # type: ignore[index]
        target["future"] = True
        _error(payload, expected_path)


def test_non_objects_and_non_string_object_keys_are_rejected() -> None:
    _error([], "<root>")

    payload = _payload()
    payload["zones"] = {1: payload["zones"][ZONE_ID]}  # type: ignore[index]
    _error(payload, "zones")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("enabled", 1),
        ("selected_profile_id", "not-a-uuid"),
        ("profiles", {}),
    ],
)
def test_zone_schedule_set_scalar_types_are_strict(field: str, value: object) -> None:
    payload = _payload()
    payload["zones"][ZONE_ID][field] = value  # type: ignore[index]
    _error(payload, f"zones.{ZONE_ID}.{field}")


def test_zone_key_and_inner_identity_must_match() -> None:
    payload = _payload()
    payload["zones"][ZONE_ID]["zone_id"] = OTHER_ZONE_ID  # type: ignore[index]
    _error(payload, f"zones.{ZONE_ID}.zone_id")


def test_document_identity_timezone_and_zone_set_must_match_context() -> None:
    variants = [
        ("entry_id", "other-entry", _context(), "entry_id"),
        ("equipment_group_id", OTHER_ZONE_ID, _context(), "equipment_group_id"),
        (
            "time_zone",
            "America/Chicago",
            _context(),
            "time_zone",
        ),
    ]
    for field, value, context, path in variants:
        payload = _payload()
        payload[field] = value
        with pytest.raises(SchemaValidationError) as captured:
            _decode(payload, context=context)
        assert captured.value.path == path

    payload = _payload()
    context = _context(zone_id=OTHER_ZONE_ID)
    with pytest.raises(SchemaValidationError, match="missing configured zone"):
        _decode(payload, context=context)


def test_unknown_zone_is_rejected_after_all_configured_zones_exist() -> None:
    payload = _payload()
    payload["zones"][OTHER_ZONE_ID] = deepcopy(payload["zones"][ZONE_ID])  # type: ignore[index]
    payload["zones"][OTHER_ZONE_ID]["zone_id"] = OTHER_ZONE_ID  # type: ignore[index]
    with pytest.raises(SchemaValidationError, match="unknown zone"):
        _decode(payload)


def test_profiles_must_exist_and_selected_profile_must_resolve() -> None:
    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"] = []  # type: ignore[index]
    _error(payload, f"zones.{ZONE_ID}.profiles")

    payload = _payload()
    payload["zones"][ZONE_ID]["selected_profile_id"] = OTHER_PROFILE_ID  # type: ignore[index]
    _error(payload, f"zones.{ZONE_ID}.selected_profile_id")


def test_enabled_zone_requires_enabled_nonempty_selected_profile() -> None:
    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"][0]["enabled"] = False  # type: ignore[index]
    _error(payload, f"zones.{ZONE_ID}.selected_profile_id")

    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"][0]["days"] = _days([])  # type: ignore[index]
    _error(payload, f"zones.{ZONE_ID}.selected_profile_id")

    payload["zones"][ZONE_ID]["enabled"] = False  # type: ignore[index]
    _decode(payload)


def test_profile_names_are_nonblank_plain_and_casefold_unique() -> None:
    for name in ("", " Normal ", "<b>Normal</b>", "Line\nBreak", "x" * 65):
        payload = _payload()
        payload["zones"][ZONE_ID]["profiles"][0]["name"] = name  # type: ignore[index]
        _error(payload, f"zones.{ZONE_ID}.profiles[0].name")

    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"].append(  # type: ignore[index]
        _profile(profile_id=OTHER_PROFILE_ID, name="normal")
    )
    _error(payload, f"zones.{ZONE_ID}.profiles[1].name")


def test_profile_ids_and_period_ids_are_unique_across_the_entry() -> None:
    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"].append(  # type: ignore[index]
        _profile(profile_id=PROFILE_ID, name="Other")
    )
    _error(payload, f"zones.{ZONE_ID}.profiles[1].profile_id")

    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"].append(  # type: ignore[index]
        _profile(profile_id=OTHER_PROFILE_ID, name="Other")
    )
    _error(
        payload,
        f"zones.{ZONE_ID}.profiles[1].days.monday[0].period_id",
    )


def test_days_require_exact_weekday_set_and_period_lists() -> None:
    payload = _payload()
    del payload["zones"][ZONE_ID]["profiles"][0]["days"]["sunday"]  # type: ignore[index]
    _error(payload, f"zones.{ZONE_ID}.profiles[0].days.sunday")

    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"] = {}  # type: ignore[index]
    _error(payload, f"zones.{ZONE_ID}.profiles[0].days.monday")


def test_day_rejects_more_than_24_periods_duplicate_times_and_unsorted_times() -> None:
    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"] = [  # type: ignore[index]
        _period(
            period_id=f"10000000-0000-4000-8000-{index:012d}",
            local_start=f"{index:02d}:00",
        )
        for index in range(MAX_PERIODS_PER_DAY)
    ] + [
        _period(
            period_id="10000000-0000-4000-8000-999999999999",
            local_start="23:30",
        )
    ]
    _error(payload, f"zones.{ZONE_ID}.profiles[0].days.monday")

    for starts in (("06:30", "06:30"), ("18:00", "06:30")):
        payload = _payload()
        payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"] = [  # type: ignore[index]
            _period(period_id=PERIOD_ID, local_start=starts[0]),
            _period(period_id=OTHER_PERIOD_ID, local_start=starts[1]),
        ]
        _error(
            payload,
            f"zones.{ZONE_ID}.profiles[0].days.monday[1].local_start",
        )


def test_period_fields_are_strict_and_field_addressable() -> None:
    variants = [
        ("period_id", "bad", "period_id"),
        ("local_start", "6:30", "local_start"),
        ("label", " Morning ", "label"),
        ("label", "<b>Morning</b>", "label"),
        ("occupancy_label", "work", "occupancy_label"),
        ("tolerance_c", True, "tolerance_c"),
        ("tolerance_c", float("nan"), "tolerance_c"),
        ("tolerance_c", 0.09, "tolerance_c"),
        ("tolerance_c", 2.81, "tolerance_c"),
    ]
    for field, value, path_suffix in variants:
        payload = _payload()
        payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0][field] = (  # type: ignore[index]
            value
        )
        _error(
            payload,
            f"zones.{ZONE_ID}.profiles[0].days.monday[0].{path_suffix}",
        )

    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0][  # type: ignore[index]
        "local_start"
    ] = 630
    _error(payload, f"zones.{ZONE_ID}.profiles[0].days.monday[0].local_start")

    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0][  # type: ignore[index]
        "occupancy_label"
    ] = 1
    _error(payload, f"zones.{ZONE_ID}.profiles[0].days.monday[0].occupancy_label")


@pytest.mark.parametrize(
    "occupancy_label",
    [item.value for item in ScheduleOccupancyLabel],
)
def test_all_schedule_occupancy_labels_are_supported(occupancy_label: str) -> None:
    payload = _payload()
    payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0][  # type: ignore[index]
        "occupancy_label"
    ] = occupancy_label
    _decode(payload)


def test_single_target_requires_exact_union_shape_support_and_limits() -> None:
    base_path = f"zones.{ZONE_ID}.profiles[0].days.monday[0].target"
    variants = [
        ({"target_c": None}, base_path),
        ({"heat_target_c": 20.0}, base_path),
        ({"cool_target_c": 24.0}, base_path),
        ({"target_c": float("inf")}, base_path + ".target_c"),
        ({"target_c": 9.9}, base_path + ".target_c"),
        ({"target_c": 30.1}, base_path + ".target_c"),
    ]
    for changes, expected_path in variants:
        payload = _payload()
        payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0][  # type: ignore[index]
            "target"
        ].update(changes)
        _error(payload, expected_path)

    with pytest.raises(SchemaValidationError, match="single targets are not supported"):
        _decode(_payload(), context=_context(supports_single_target=False))


def test_range_target_requires_shape_support_limits_and_separation() -> None:
    base_path = f"zones.{ZONE_ID}.profiles[0].days.monday[0].target"
    valid = _payload(range_target=True)
    document = _decode(valid)
    assert (
        document.zones[ZoneId.parse(ZONE_ID)]
        .profiles[0]
        .days[Weekday.MONDAY][0]
        .target.kind
        is TargetKind.RANGE
    )

    variants = [
        ({"target_c": 22.0}, base_path),
        ({"heat_target_c": None}, base_path),
        ({"cool_target_c": None}, base_path),
        ({"heat_target_c": 7.1}, base_path + ".heat_target_c"),
        ({"heat_target_c": 26.8}, base_path + ".heat_target_c"),
        ({"cool_target_c": 15.5}, base_path + ".cool_target_c"),
        ({"cool_target_c": 35.1}, base_path + ".cool_target_c"),
        (
            {"heat_target_c": 23.5, "cool_target_c": 24.0},
            base_path + ".cool_target_c",
        ),
    ]
    for changes, expected_path in variants:
        payload = _payload(range_target=True)
        payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0][  # type: ignore[index]
            "target"
        ].update(changes)
        _error(payload, expected_path)

    with pytest.raises(SchemaValidationError, match="range targets are not supported"):
        _decode(
            _payload(range_target=True),
            context=_context(supports_target_range=False),
        )


def test_target_kind_and_target_scalar_types_are_strict() -> None:
    payload = _payload()
    target = payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0]["target"]  # type: ignore[index]
    target["kind"] = "adaptive"
    _error(payload, f"zones.{ZONE_ID}.profiles[0].days.monday[0].target.kind")

    payload = _payload()
    target = payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0]["target"]  # type: ignore[index]
    target["target_c"] = "22"
    _error(payload, f"zones.{ZONE_ID}.profiles[0].days.monday[0].target.target_c")


def test_occupancy_referenced_profiles_must_exist_in_the_same_zone() -> None:
    with pytest.raises(
        SchemaValidationError,
        match="occupancy-referenced profile",
    ):
        _decode(
            _payload(),
            context=_context(
                occupancy_profile_ids=frozenset(
                    {ScheduleProfileId.parse(OTHER_PROFILE_ID)}
                )
            ),
        )

    _decode(
        _payload(),
        context=_context(
            occupancy_profile_ids=frozenset({ScheduleProfileId.parse(PROFILE_ID)})
        ),
    )


def test_validation_context_is_immutable_and_strict() -> None:
    context = _context()
    assert isinstance(context.zone_constraints, MappingProxyType)
    assert isinstance(context.occupancy_profile_ids, MappingProxyType)
    with pytest.raises(TypeError):
        context.zone_constraints[ZoneId.new()] = next(  # type: ignore[index]
            iter(context.zone_constraints.values())
        )

    empty_context = replace(context, zone_constraints={})
    with pytest.raises(SchemaValidationError, match="must not be empty"):
        _decode(_payload(), context=empty_context)

    zone_id = ZoneId.parse(ZONE_ID)
    constraints = context.zone_constraints[zone_id]
    mismatched = replace(
        context,
        zone_constraints={
            zone_id: replace(constraints, zone_id=ZoneId.parse(OTHER_ZONE_ID))
        },
    )
    with pytest.raises(SchemaValidationError, match="must match"):
        _decode(_payload(), context=mismatched)

    unknown_occupancy = replace(
        context,
        occupancy_profile_ids={ZoneId.parse(OTHER_ZONE_ID): frozenset()},
    )
    with pytest.raises(SchemaValidationError, match="unknown zone"):
        _decode(_payload(), context=unknown_occupancy)


@pytest.mark.parametrize(
    ("field", "minimum", "maximum"),
    [
        ("single_target", 31.0, 30.0),
        ("heat_target", 27.0, 26.0),
        ("cool_target", 36.0, 35.0),
    ],
)
def test_validation_context_rejects_reversed_bounds(
    field: str,
    minimum: float,
    maximum: float,
) -> None:
    context = _context()
    zone_id = ZoneId.parse(ZONE_ID)
    constraints = context.zone_constraints[zone_id]
    if field == "single_target":
        changed = replace(
            constraints,
            single_target_min_c=minimum,
            single_target_max_c=maximum,
        )
    elif field == "heat_target":
        changed = replace(
            constraints,
            heat_target_min_c=minimum,
            heat_target_max_c=maximum,
        )
    else:
        changed = replace(
            constraints,
            cool_target_min_c=minimum,
            cool_target_max_c=maximum,
        )
    invalid = replace(context, zone_constraints={zone_id: changed})
    with pytest.raises(SchemaValidationError, match="must not exceed"):
        _decode(_payload(), context=invalid)


def test_validation_context_rejects_nonfinite_bounds_and_negative_separation() -> None:
    context = _context()
    zone_id = ZoneId.parse(ZONE_ID)
    constraints = context.zone_constraints[zone_id]

    invalid_bound = replace(
        context,
        zone_constraints={
            zone_id: replace(constraints, single_target_min_c=float("nan"))
        },
    )
    with pytest.raises(SchemaValidationError, match="must be finite"):
        _decode(_payload(), context=invalid_bound)

    invalid_separation = replace(
        context,
        zone_constraints={
            zone_id: replace(
                constraints,
                minimum_heat_cool_separation_c=-0.1,
            )
        },
    )
    with pytest.raises(SchemaValidationError, match="must be at least zero"):
        _decode(_payload(), context=invalid_separation)


def test_encoder_revalidates_hand_constructed_models() -> None:
    document = _decode(_payload())
    zone_id = ZoneId.parse(ZONE_ID)
    zone = document.zones[zone_id]
    period = zone.profiles[0].days[Weekday.MONDAY][0]
    invalid_period = replace(period, tolerance_c=9.0)
    invalid_profile = replace(
        zone.profiles[0],
        days={
            **zone.profiles[0].days,
            Weekday.MONDAY: (invalid_period,),
        },
    )
    invalid_document = replace(
        document,
        zones={
            zone_id: replace(zone, profiles=(invalid_profile,)),
        },
    )
    with pytest.raises(SchemaValidationError, match="tolerance_c"):
        encode_schedule_document(
            invalid_document,
            validation_context=_context(),
        )


def test_validate_rejects_invalid_model_only_types_and_target_kind() -> None:
    document = _decode(_payload())
    zone_id = ZoneId.parse(ZONE_ID)
    zone = document.zones[zone_id]
    profile = zone.profiles[0]
    period = profile.days[Weekday.MONDAY][0]

    invalid_period = replace(
        period,
        occupancy_label="home",  # type: ignore[arg-type]
    )
    invalid_profile = replace(
        profile,
        days={**profile.days, Weekday.MONDAY: (invalid_period,)},
    )
    invalid_document = replace(
        document,
        zones={zone_id: replace(zone, profiles=(invalid_profile,))},
    )
    with pytest.raises(SchemaValidationError, match="occupancy label"):
        validate_schedule_document(
            invalid_document,
            validation_context=_context(),
        )

    invalid_target = replace(
        period.target,
        kind="adaptive",  # type: ignore[arg-type]
    )
    invalid_period = replace(period, target=invalid_target)
    invalid_profile = replace(
        profile,
        days={**profile.days, Weekday.MONDAY: (invalid_period,)},
    )
    invalid_document = replace(
        document,
        zones={zone_id: replace(zone, profiles=(invalid_profile,))},
    )
    with pytest.raises(SchemaValidationError, match=r"target\.kind"):
        validate_schedule_document(
            invalid_document,
            validation_context=_context(),
        )


def test_validate_rejects_invalid_hand_constructed_document_shapes() -> None:
    document = _decode(_payload())
    zone_id = ZoneId.parse(ZONE_ID)
    zone = document.zones[zone_id]
    profile = zone.profiles[0]
    period = profile.days[Weekday.MONDAY][0]

    invalid_documents = [
        replace(document, schedule_schema_version=2),
        replace(document, saved_at_utc="2026-07-30T15:00:00Z"),  # type: ignore[arg-type]
        replace(
            document,
            zones={zone_id: replace(zone, zone_id=ZoneId.parse(OTHER_ZONE_ID))},
        ),
        replace(
            document,
            zones={
                zone_id: replace(
                    zone,
                    profiles=(
                        replace(
                            profile,
                            days={Weekday.MONDAY: (period,)},
                        ),
                    ),
                )
            },
        ),
        replace(
            document,
            zones={
                zone_id: replace(
                    zone,
                    profiles=(
                        replace(
                            profile,
                            days={
                                **profile.days,
                                Weekday.MONDAY: [period],  # type: ignore[dict-item]
                            },
                        ),
                    ),
                )
            },
        ),
        replace(
            document,
            zones={
                zone_id: replace(
                    zone,
                    profiles=(
                        replace(
                            profile,
                            days={
                                **profile.days,
                                Weekday.MONDAY: (
                                    replace(
                                        period,
                                        local_start="06:30",  # type: ignore[arg-type]
                                    ),
                                ),
                            },
                        ),
                    ),
                )
            },
        ),
    ]
    expected_paths = [
        "schedule_schema_version",
        "saved_at_utc",
        f"zones.{ZONE_ID}.zone_id",
        f"zones.{ZONE_ID}.profiles[0].days",
        f"zones.{ZONE_ID}.profiles[0].days.monday",
        f"zones.{ZONE_ID}.profiles[0].days.monday[0].local_start",
    ]
    for invalid, expected_path in zip(
        invalid_documents,
        expected_paths,
        strict=True,
    ):
        with pytest.raises(SchemaValidationError) as captured:
            validate_schedule_document(
                invalid,
                validation_context=_context(),
            )
        assert captured.value.path == expected_path


@pytest.mark.parametrize(
    ("field_path", "value", "expected_path"),
    [
        ("entry_id", 1, "entry_id"),
        (
            f"zones.{ZONE_ID}.zone_id",
            1,
            f"zones.{ZONE_ID}.zone_id",
        ),
        (
            f"zones.{ZONE_ID}.profiles[0].profile_id",
            1,
            f"zones.{ZONE_ID}.profiles[0].profile_id",
        ),
        (
            f"zones.{ZONE_ID}.profiles[0].days.monday[0].period_id",
            1,
            f"zones.{ZONE_ID}.profiles[0].days.monday[0].period_id",
        ),
    ],
)
def test_string_boundaries_reject_non_strings(
    field_path: str,
    value: object,
    expected_path: str,
) -> None:
    payload = _payload()
    if field_path == "entry_id":
        payload["entry_id"] = value
    elif field_path.endswith(".zone_id"):
        payload["zones"][ZONE_ID]["zone_id"] = value  # type: ignore[index]
    elif field_path.endswith(".profile_id"):
        payload["zones"][ZONE_ID]["profiles"][0]["profile_id"] = value  # type: ignore[index]
    else:
        payload["zones"][ZONE_ID]["profiles"][0]["days"]["monday"][0][  # type: ignore[index]
            "period_id"
        ] = value
    _error(payload, expected_path)


def test_codec_has_no_runtime_persistence_or_command_side_effects() -> None:
    """Task 3 remains a pure model/codec slice."""
    document = _decode(_payload())

    assert document.revision == 0
    assert not hasattr(document, "async_save")
    assert not hasattr(document, "evaluate")
    assert not hasattr(document, "command")
    assert SchedulePeriod.__module__.endswith(".models.schedule")
    assert WeeklyScheduleProfile.__module__.endswith(".models.schedule")
    assert ZoneScheduleSet.__module__.endswith(".models.schedule")
