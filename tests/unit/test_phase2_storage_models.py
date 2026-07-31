"""Test Phase 2 target schemas and side-effect-free migration dry runs."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

import pytest

from custom_components.intelligent_climate.models import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
    DEFAULT_PHASE2_COMMAND_TIMING,
    DEFAULT_PHASE2_SAFETY_LIMITS,
    PHASE2_CONFIG_MAJOR_VERSION,
    PHASE2_CONFIG_MINOR_VERSION,
    PHASE2_RUNTIME_STORE_ENVELOPE_MINOR_VERSION,
    PHASE2_RUNTIME_STORE_ENVELOPE_VERSION,
    PHASE2_RUNTIME_STORE_SCHEMA_VERSION,
    PHASE2_ZONE_DATA_VERSION,
    RUNTIME_STORE_SCHEMA_VERSION,
    ZONE_DATA_VERSION,
    ControlExecutionState,
    OperatingMode,
    Phase2BindingCandidate,
    Phase2ControlIntent,
    SchemaMigrationError,
    SchemaValidationError,
    decode_phase2_equipment_group_document,
    decode_phase2_options,
    decode_phase2_runtime_store_document,
    decode_phase2_zone_config,
    dry_run_phase2_migration,
    encode_phase2_equipment_group_document,
    encode_phase2_options,
    encode_phase2_runtime_store_document,
    encode_phase2_zone_config,
)
from custom_components.intelligent_climate.schema_compat import (
    encode_reviewed_active_zone,
)

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "phase_1_0_0_8_baseline.json"
INTEGRATION = ROOT / "custom_components" / "intelligent_climate"
SAVED_AT = datetime(2026, 7, 30, 17, 30, tzinfo=UTC)


def _baseline() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(FIXTURE.read_text(encoding="utf-8")))


def _dry_run(
    *,
    baseline: dict[str, Any] | None = None,
) -> Any:
    source = _baseline() if baseline is None else baseline
    config = source["config_entry"]
    return dry_run_phase2_migration(
        entry_id=source["runtime_store"]["data"]["entry_id"],
        config_data=config["data"],
        config_version=config["version"],
        config_minor_version=config["minor_version"],
        options_data=source["options"],
        zone_data=[source["zone_subentry"]],
        runtime_data=source["runtime_store"]["data"],
        time_zone="America/New_York",
        saved_at=SAVED_AT,
    )


def test_phase2_target_versions_are_explicit_without_advancing_live_phase1() -> None:
    """Task 7 describes targets while Task 8 still owns the live version bump."""
    assert (
        PHASE2_CONFIG_MAJOR_VERSION,
        PHASE2_CONFIG_MINOR_VERSION,
        PHASE2_ZONE_DATA_VERSION,
        PHASE2_RUNTIME_STORE_ENVELOPE_VERSION,
        PHASE2_RUNTIME_STORE_ENVELOPE_MINOR_VERSION,
        PHASE2_RUNTIME_STORE_SCHEMA_VERSION,
    ) == (2, 0, 2, 2, 0, 2)
    assert (
        CONFIG_ENTRY_MAJOR_VERSION,
        CONFIG_ENTRY_MINOR_VERSION,
        ZONE_DATA_VERSION,
        RUNTIME_STORE_SCHEMA_VERSION,
    ) == (1, 1, 1, 1)


def test_accepted_baseline_dry_run_is_observe_only_and_identity_preserving() -> None:
    """A complete 0.0.8 graph produces safe, validated Phase 2 candidates."""
    baseline = _baseline()
    result = _dry_run(baseline=baseline)
    phase1_config = baseline["config_entry"]["data"]["equipment_group"]
    phase1_zone = baseline["zone_subentry"]
    phase1_runtime = baseline["runtime_store"]["data"]

    assert (
        str(result.config.equipment_group.equipment_group_id)
        == phase1_config["equipment_group_id"]
    )
    assert tuple(
        item.entity_id for item in result.config.equipment_group.thermostats
    ) == ("climate.dining_room",)
    assert result.config.automation_enabled is False
    assert result.config.desired_operating_mode is OperatingMode.OBSERVE_ONLY
    assert result.config.command_authority_entity_ids == ("climate.dining_room",)
    assert result.config.authority_review_required is False
    assert result.config.acknowledged_time_zone == "America/New_York"

    migrated_zone = result.zones[0]
    assert str(migrated_zone.zone.zone_id) == phase1_zone["zone_id"]
    assert tuple(
        str(item.source_id) for item in migrated_zone.zone.temperature_sources
    ) == (phase1_zone["temperature_sources"][0]["source_id"],)
    assert migrated_zone.contact_bindings == ()
    assert migrated_zone.occupancy_bindings == ()
    assert migrated_zone.fan_bindings == ()

    runtime = result.runtime
    assert runtime.entry_id == phase1_runtime["entry_id"]
    assert str(runtime.equipment_group_id) == phase1_runtime["equipment_group_id"]
    assert runtime.saved_at == SAVED_AT
    assert set(runtime.zones) == {migrated_zone.zone.zone_id}
    assert (
        next(iter(runtime.zones.values())).control_state
        is ControlExecutionState.RECONCILING
    )
    assert runtime.command_journal == ()
    assert runtime.overrides == ()
    assert runtime.transition_ledger == ()
    assert runtime.occupancy_timers == ()
    assert runtime.contact_timers == ()
    assert runtime.fan_runtime_budget == ()
    assert runtime.failure_counters == ()
    assert runtime.shadow_qualification.evaluated_decisions == 0
    assert runtime.shadow_qualification.valid_evaluations == 0
    assert runtime.control_intent.desired_operating_mode is OperatingMode.OBSERVE_ONLY
    assert runtime.control_intent.automation_enabled is False
    assert runtime.control_intent.active_control_armed is False


def test_dry_run_preserves_legacy_binding_ids_but_disables_every_behavior() -> None:
    """Configured candidates survive migration but gain no automatic behavior."""
    baseline = _baseline()
    zone = baseline["zone_subentry"]
    zone["window_door_entity_ids"] = ["binary_sensor.window"]
    zone["occupancy_entity_ids"] = ["person.household"]
    zone["fan_entity_ids"] = ["fan.air_handler"]

    migrated = _dry_run(baseline=baseline).zones[0]

    assert migrated.contact_bindings == (
        Phase2BindingCandidate(
            entity_id="binary_sensor.window",
            enabled=False,
            reviewed=False,
        ),
    )
    assert migrated.occupancy_bindings[0].enabled is False
    assert migrated.occupancy_bindings[0].reviewed is False
    assert migrated.fan_bindings[0].enabled is False
    assert migrated.fan_bindings[0].reviewed is False
    encoded = encode_phase2_zone_config(migrated)
    assert encoded["window_door_entity_ids"] == [
        {
            "entity_id": "binary_sensor.window",
            "enabled": False,
            "reviewed": False,
        }
    ]


def test_explicit_zone_review_enables_only_submitted_binding_groups() -> None:
    """Saving one selector cannot silently review a different migrated group."""
    baseline = _baseline()
    zone_data = baseline["zone_subentry"]
    zone_data["window_door_entity_ids"] = ["binary_sensor.window"]
    zone_data["occupancy_entity_ids"] = ["person.household"]
    migrated = _dry_run(baseline=baseline).zones[0]
    current = dict(encode_phase2_zone_config(migrated))

    encoded = encode_reviewed_active_zone(
        migrated.zone,
        target_data_version=PHASE2_ZONE_DATA_VERSION,
        current_data=current,
        reviewed_fields=frozenset({"window_door_entity_ids"}),
    )
    decoded = decode_phase2_zone_config(encoded)

    assert decoded.contact_bindings[0].reviewed is True
    assert decoded.contact_bindings[0].enabled is True
    assert decoded.occupancy_bindings[0].reviewed is False
    assert decoded.occupancy_bindings[0].enabled is False


def test_dry_run_does_not_mutate_any_caller_document() -> None:
    """Candidate creation is safe to run before a transactional commit."""
    baseline = _baseline()
    before = deepcopy(baseline)

    _dry_run(baseline=baseline)

    assert baseline == before


def test_all_phase2_candidate_documents_round_trip_canonically() -> None:
    """Config, options, zone, and runtime schema 2 codecs are deterministic."""
    result = _dry_run()

    config_json = dict(encode_phase2_equipment_group_document(result.config))
    options_json = dict(encode_phase2_options(result.options))
    zone_json = dict(encode_phase2_zone_config(result.zones[0]))
    runtime_json = dict(encode_phase2_runtime_store_document(result.runtime))

    assert (
        dict(
            encode_phase2_equipment_group_document(
                decode_phase2_equipment_group_document(config_json)
            )
        )
        == config_json
    )
    assert dict(encode_phase2_options(decode_phase2_options(options_json))) == (
        options_json
    )
    assert (
        dict(encode_phase2_zone_config(decode_phase2_zone_config(zone_json)))
        == zone_json
    )
    assert (
        dict(
            encode_phase2_runtime_store_document(
                decode_phase2_runtime_store_document(runtime_json)
            )
        )
        == runtime_json
    )
    assert zone_json["data_version"] == 2
    assert runtime_json["schema_version"] == 2


def test_phase2_defaults_match_the_approved_safety_and_timing_values() -> None:
    """The dry-run target records the approved Celsius and seconds defaults."""
    result = _dry_run()

    assert result.options.safety_limits == DEFAULT_PHASE2_SAFETY_LIMITS
    assert result.options.command_timing == DEFAULT_PHASE2_COMMAND_TIMING
    assert result.options.safety_limits == replace(
        result.options.safety_limits,
        minimum_heating_target_c=7.2,
        maximum_heating_target_c=26.7,
        minimum_cooling_target_c=15.6,
        maximum_cooling_target_c=35.0,
        minimum_heat_cool_separation_c=1.7,
        emergency_protection_enabled=False,
        emergency_low_threshold_c=7.2,
        emergency_low_target_c=10.0,
        emergency_high_threshold_c=32.2,
        emergency_high_target_c=29.4,
    )
    assert result.options.command_timing.startup_quiet_period_seconds == 120
    assert result.options.command_timing.automatic_minimum_interval_seconds == 300
    assert result.options.command_timing.manual_control_minimum_interval_seconds == 2


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("version", 0, "accepted config-entry version 1.1"),
        ("minor_version", 0, "accepted config-entry version 1.1"),
        ("time_zone", "Not/AZone", "IANA time zone"),
        ("saved_at", datetime(2026, 7, 30), "timezone information"),
    ],
)
def test_dry_run_rejects_unsupported_source_or_clock_inputs(
    field: str,
    value: object,
    message: str,
) -> None:
    """Migration candidates require the exact accepted baseline and aware clock."""
    baseline = _baseline()
    config = baseline["config_entry"]
    arguments: dict[str, object] = {
        "entry_id": baseline["runtime_store"]["data"]["entry_id"],
        "config_data": config["data"],
        "config_version": config["version"],
        "config_minor_version": config["minor_version"],
        "options_data": baseline["options"],
        "zone_data": [baseline["zone_subentry"]],
        "runtime_data": baseline["runtime_store"]["data"],
        "time_zone": "America/New_York",
        "saved_at": SAVED_AT,
    }
    key = {
        "version": "config_version",
        "minor_version": "config_minor_version",
    }.get(field, field)
    arguments[key] = value

    with pytest.raises(SchemaValidationError, match=message):
        dry_run_phase2_migration(**arguments)  # type: ignore[arg-type]


def test_dry_run_rejects_identity_and_complete_zone_mismatches() -> None:
    """A candidate cannot combine documents from different entry graphs."""
    baseline = _baseline()
    baseline["runtime_store"]["data"]["entry_id"] = "different-entry"
    with pytest.raises(SchemaValidationError, match="does not match config entry"):
        dry_run_phase2_migration(
            entry_id="expected-entry",
            config_data=baseline["config_entry"]["data"],
            config_version=1,
            config_minor_version=1,
            options_data=baseline["options"],
            zone_data=[baseline["zone_subentry"]],
            runtime_data=baseline["runtime_store"]["data"],
            time_zone="America/New_York",
            saved_at=SAVED_AT,
        )

    baseline = _baseline()
    baseline["runtime_store"]["data"]["zones"] = {}
    with pytest.raises(
        SchemaValidationError,
        match="every configured zone exactly once",
    ):
        _dry_run(baseline=baseline)


def test_phase2_codecs_reject_future_unknown_and_unsafe_documents() -> None:
    """Strict target codecs cannot silently accept or arm unsafe state."""
    result = _dry_run()
    config = dict(encode_phase2_equipment_group_document(result.config))
    with pytest.raises(SchemaMigrationError, match="future config-entry version"):
        decode_phase2_equipment_group_document(config, version=3)
    config["unknown"] = True
    with pytest.raises(SchemaValidationError, match="unknown field"):
        decode_phase2_equipment_group_document(config)

    runtime = dict(encode_phase2_runtime_store_document(result.runtime))
    runtime["schema_version"] = 3
    with pytest.raises(SchemaMigrationError, match="future runtime Store"):
        decode_phase2_runtime_store_document(runtime)

    runtime = dict(encode_phase2_runtime_store_document(result.runtime))
    runtime["control_intent"] = {
        "automation_enabled": False,
        "desired_operating_mode": "observe_only",
        "active_control_armed": True,
        "time_zone_acknowledgement_required": False,
    }
    with pytest.raises(SchemaValidationError, match="requires enabled"):
        decode_phase2_runtime_store_document(runtime)


def test_binding_and_policy_validation_fail_closed() -> None:
    """Unreviewed behavior cannot become enabled and unsafe limits fail wholly."""
    result = _dry_run()
    zone = dict(encode_phase2_zone_config(result.zones[0]))
    zone["window_door_entity_ids"] = [
        {
            "entity_id": "binary_sensor.window",
            "enabled": True,
            "reviewed": False,
        }
    ]
    with pytest.raises(SchemaValidationError, match="enabled before review"):
        decode_phase2_zone_config(zone)

    options = dict(encode_phase2_options(result.options))
    options["safety_limits"] = dict(cast(dict[str, object], options["safety_limits"]))
    options["safety_limits"]["minimum_heating_target_c"] = 30.0
    with pytest.raises(SchemaValidationError, match="less than"):
        decode_phase2_options(options)

    options = dict(encode_phase2_options(result.options))
    options["command_timing"] = dict(cast(dict[str, object], options["command_timing"]))
    options["command_timing"]["startup_quiet_period_seconds"] = 119
    with pytest.raises(SchemaValidationError, match="at least 120"):
        decode_phase2_options(options)


def test_phase2_candidates_are_immutable_at_mapping_boundaries() -> None:
    """Decoded runtime maps cannot be mutated after validation."""
    result = _dry_run()
    zone_id = next(iter(result.runtime.zones))

    with pytest.raises(TypeError):
        cast(dict[Any, Any], result.runtime.zones)[zone_id] = result.runtime.zones[
            zone_id
        ]
    with pytest.raises(TypeError):
        cast(
            dict[Any, Any],
            result.runtime.shadow_qualification.material_transitions_by_zone,
        )[zone_id] = 0


def test_task8_activates_only_migration_and_safe_runtime_persistence() -> None:
    """Task 8 wires schemas into migration without creating a command path."""
    target = (INTEGRATION / "models" / "phase2_schema.py").read_text(encoding="utf-8")
    setup = (INTEGRATION / "__init__.py").read_text(encoding="utf-8")
    storage = (INTEGRATION / "storage.py").read_text(encoding="utf-8")
    migration = (INTEGRATION / "migration.py").read_text(encoding="utf-8")
    forbidden = (
        "homeassistant",
        "Store(",
        "async_save",
        "async_load",
        "services.async_call",
        "command_adapter",
        "ScheduleStore(",
    )

    assert all(item not in target for item in forbidden)
    assert "PHASE2_CONFIG_MAJOR_VERSION" in setup
    assert "PHASE2_RUNTIME_STORE_ENVELOPE_VERSION" in storage
    assert "async_migrate_phase1_entry" in migration
    assert "async_initialize_presentation_trace" in migration
    assert "Store(" in migration
    assert "services.async_call" not in setup
    assert "services.async_call" not in storage
    assert "services.async_call" not in migration
    assert "command_adapter" not in setup
    assert "command_adapter" not in storage
    assert "command_adapter" not in migration


def test_shared_group_dry_run_proposes_only_primary_and_requires_review() -> None:
    """Shared control authority is proposed but never silently approved."""
    baseline = _baseline()
    group = baseline["config_entry"]["data"]["equipment_group"]
    group["relationship"] = "shared_zoned"
    group["shared_policy"] = {
        "zone_priority_order": [baseline["zone_subentry"]["zone_id"]],
        "conflict_policy": "suppress",
    }

    result = _dry_run(baseline=baseline)

    assert result.config.command_authority_entity_ids == ("climate.dining_room",)
    assert result.config.authority_review_required is True
    assert result.config.automation_enabled is False


def test_runtime_group_identity_mismatch_fails_dry_run() -> None:
    """Runtime state from another equipment group cannot be combined."""
    baseline = _baseline()
    baseline["runtime_store"]["data"]["equipment_group_id"] = (
        "89246285-6f02-4e8a-94ed-bdfd4a5e62c4"
    )

    with pytest.raises(SchemaValidationError, match="does not match equipment"):
        _dry_run(baseline=baseline)


@pytest.mark.parametrize(
    ("changes", "match"),
    [
        (
            {
                "desired_operating_mode": OperatingMode.SCHEDULED_CONTROL,
                "automation_enabled": False,
            },
            "requires automation_enabled",
        ),
        (
            {
                "desired_operating_mode": OperatingMode.SCHEDULED_CONTROL,
                "automation_enabled": True,
                "authority_review_required": True,
            },
            "must be false",
        ),
        (
            {
                "command_authority_entity_ids": (
                    "climate.dining_room",
                    "climate.dining_room",
                )
            },
            "duplicates",
        ),
        (
            {"command_authority_entity_ids": ("climate.foreign",)},
            "configured thermostats",
        ),
        (
            {
                "command_authority_entity_ids": (),
                "authority_review_required": False,
            },
            "must not be empty",
        ),
    ],
)
def test_config_encoder_rejects_unsafe_authority_states(
    changes: dict[str, object],
    match: str,
) -> None:
    """No invalid authority candidate can be serialized for a commit."""
    config = _dry_run().config

    with pytest.raises(SchemaValidationError, match=match):
        encode_phase2_equipment_group_document(replace(config, **changes))


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("minimum_heating_target_c", float("nan"), "finite"),
        ("minimum_cooling_target_c", 40.0, "less than"),
        ("minimum_heat_cool_separation_c", 0.0, "greater than zero"),
        ("emergency_low_target_c", 40.0, "strictly ordered"),
    ],
)
def test_safety_limit_validation_rejects_every_unsafe_relationship(
    field: str,
    value: float,
    match: str,
) -> None:
    """Safety limits remain finite and logically ordered."""
    options = _dry_run().options
    limits = replace(options.safety_limits, **{field: value})

    with pytest.raises(SchemaValidationError, match=match):
        encode_phase2_options(replace(options, safety_limits=limits))


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("automatic_minimum_interval_seconds", 0, "positive"),
        ("manual_control_minimum_interval_seconds", True, "positive"),
        ("target_deadband_c", float("nan"), "positive finite"),
        ("target_deadband_c", 0.0, "positive finite"),
    ],
)
def test_command_timing_validation_rejects_nonpositive_or_nonfinite_values(
    field: str,
    value: object,
    match: str,
) -> None:
    """Timing gates cannot be disabled through malformed persisted values."""
    options = _dry_run().options
    timing = replace(options.command_timing, **{field: value})

    with pytest.raises(SchemaValidationError, match=match):
        encode_phase2_options(replace(options, command_timing=timing))


@pytest.mark.parametrize(
    ("version", "minor", "match"),
    [
        (1, 0, "no migration path"),
        (2, 1, "future.*minor"),
        (2, -1, "no migration path.*minor"),
        (True, 0, "version.*integer"),
        (2, True, "minor_version.*integer"),
    ],
)
def test_phase2_config_codec_rejects_every_unsupported_version_shape(
    version: object,
    minor: object,
    match: str,
) -> None:
    """Only the exact 2.0 target contract is readable."""
    encoded = dict(encode_phase2_equipment_group_document(_dry_run().config))

    with pytest.raises(SchemaValidationError, match=match):
        decode_phase2_equipment_group_document(
            encoded,
            version=version,  # type: ignore[arg-type]
            minor_version=minor,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda value: value.pop("name"), "missing required field"),
        (lambda value: value.update(data_version=1), "no migration path"),
        (lambda value: value.update(data_version=3), "future zone data"),
        (
            lambda value: value.update(
                window_door_entity_ids=[
                    {
                        "entity_id": "binary_sensor.window",
                        "enabled": False,
                        "reviewed": False,
                    },
                    {
                        "entity_id": "binary_sensor.window",
                        "enabled": False,
                        "reviewed": False,
                    },
                ]
            ),
            "duplicate entity",
        ),
        (
            lambda value: value.update(
                fan_entity_ids=[
                    {"entity_id": "invalid", "enabled": False, "reviewed": False}
                ]
            ),
            "entity_id",
        ),
    ],
)
def test_zone_v2_codec_rejects_malformed_documents(
    mutation: Any,
    match: str,
) -> None:
    """Zone v2 is strict at version, field, identity, and binding boundaries."""
    encoded = dict(encode_phase2_zone_config(_dry_run().zones[0]))
    mutation(encoded)

    with pytest.raises(SchemaValidationError, match=match):
        decode_phase2_zone_config(encoded)


def test_zone_encoder_rejects_hand_constructed_binding_mismatch() -> None:
    """Direct model construction cannot bypass preserved binding identity."""
    zone = _dry_run().zones[0]
    changed = replace(
        zone,
        contact_bindings=(
            Phase2BindingCandidate(
                entity_id="binary_sensor.window",
                enabled=False,
                reviewed=False,
            ),
        ),
    )

    with pytest.raises(SchemaValidationError, match="configured entity order"):
        encode_phase2_zone_config(changed)


def test_dry_run_rejects_empty_duplicate_and_foreign_zone_graphs() -> None:
    """The complete target graph must remain coherent before any commit."""
    baseline = _baseline()
    arguments = {
        "entry_id": baseline["runtime_store"]["data"]["entry_id"],
        "config_data": baseline["config_entry"]["data"],
        "config_version": 1,
        "config_minor_version": 1,
        "options_data": baseline["options"],
        "runtime_data": baseline["runtime_store"]["data"],
        "time_zone": "America/New_York",
        "saved_at": SAVED_AT,
    }
    with pytest.raises(
        SchemaValidationError,
        match="must contain every configured zone",
    ):
        dry_run_phase2_migration(zone_data=[], **arguments)

    duplicate = deepcopy(baseline["zone_subentry"])
    with pytest.raises(SchemaValidationError, match="duplicate zone_id"):
        dry_run_phase2_migration(
            zone_data=[baseline["zone_subentry"], duplicate],
            **arguments,
        )

    foreign = deepcopy(baseline["zone_subentry"])
    foreign["thermostat_entity_ids"] = ["climate.foreign"]
    baseline["runtime_store"]["data"]["zones"] = {
        foreign["zone_id"]: baseline["runtime_store"]["data"]["zones"][
            baseline["zone_subentry"]["zone_id"]
        ]
    }
    with pytest.raises(SchemaValidationError, match="outside equipment group"):
        dry_run_phase2_migration(zone_data=[foreign], **arguments)


def test_runtime_codec_accepts_bounded_nested_records_and_thaws_them() -> None:
    """Reserved v2 collections are immutable internally and canonical JSON outside."""
    runtime = _dry_run().runtime
    record = MappingProxyType(
        {
            "z": (MappingProxyType({"nested": 1}),),
            "a": True,
            "none": None,
        }
    )
    changed = replace(
        runtime,
        command_journal=(record,),
        overrides=(record,),
        transition_ledger=(record,),
        occupancy_timers=(record,),
        contact_timers=(record,),
        fan_runtime_budget=(record,),
        failure_counters=(record,),
    )

    encoded = dict(encode_phase2_runtime_store_document(changed))
    decoded = decode_phase2_runtime_store_document(encoded)

    assert encoded["command_journal"] == [
        {"a": True, "none": None, "z": [{"nested": 1}]}
    ]
    assert decoded.command_journal[0]["z"] == (MappingProxyType({"nested": 1}),)


@pytest.mark.parametrize(
    ("change", "match"),
    [
        (
            lambda value: value["shadow_qualification"].update(
                evaluated_decisions=0, valid_evaluations=1
            ),
            "cannot exceed",
        ),
        (
            lambda value: value["shadow_qualification"].update(evaluated_decisions=-1),
            "nonnegative",
        ),
        (
            lambda value: value["shadow_qualification"].update(
                material_transitions_by_zone={}
            ),
            "every runtime zone",
        ),
        (
            lambda value: value.update(command_journal=[{}] * 101),
            "at most 100",
        ),
        (
            lambda value: value.update(decisions=[{}] * 501),
            "at most 500",
        ),
        (
            lambda value: value["zones"][next(iter(value["zones"]))].update(
                control_state="not-a-state"
            ),
            "unsupported value",
        ),
        (
            lambda value: value["zones"][next(iter(value["zones"]))].update(
                comparison_humidity_pct=101
            ),
            "between 0 and 100",
        ),
        (
            lambda value: value["source_baselines"].update(
                {
                    "not-a-uuid": {
                        "last_accepted_value": 1,
                        "last_accepted_at": SAVED_AT.isoformat(),
                    }
                }
            ),
            "valid UUID",
        ),
    ],
)
def test_runtime_v2_codec_rejects_malformed_state(
    change: Any,
    match: str,
) -> None:
    """Runtime v2 fails closed across bounds, types, states, and identities."""
    encoded = deepcopy(dict(encode_phase2_runtime_store_document(_dry_run().runtime)))
    change(encoded)

    with pytest.raises(SchemaValidationError, match=match):
        decode_phase2_runtime_store_document(encoded)


def test_runtime_encoder_rejects_invalid_hand_constructed_qualification() -> None:
    """Direct dataclass construction receives the same fail-closed validation."""
    runtime = _dry_run().runtime
    invalid = replace(
        runtime.shadow_qualification,
        evaluated_decisions=1,
        valid_evaluations=2,
    )
    with pytest.raises(SchemaValidationError, match="cannot exceed"):
        encode_phase2_runtime_store_document(
            replace(runtime, shadow_qualification=invalid)
        )

    invalid = replace(
        runtime.shadow_qualification,
        material_transitions_by_zone=MappingProxyType({}),
    )
    with pytest.raises(SchemaValidationError, match="every runtime zone"):
        encode_phase2_runtime_store_document(
            replace(runtime, shadow_qualification=invalid)
        )


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("entry_id", " ", "nonempty"),
        ("saved_at", datetime(2026, 7, 30), "timezone"),
        (
            "control_intent",
            Phase2ControlIntent(
                automation_enabled=True,
                desired_operating_mode=OperatingMode.OBSERVE_ONLY,
                active_control_armed=True,
                time_zone_acknowledgement_required=False,
            ),
            "requires enabled scheduled",
        ),
    ],
)
def test_runtime_encoder_rejects_invalid_top_level_models(
    field: str,
    value: object,
    match: str,
) -> None:
    """The encoder validates hand-created runtime models before output."""
    runtime = _dry_run().runtime
    with pytest.raises(SchemaValidationError, match=match):
        encode_phase2_runtime_store_document(replace(runtime, **{field: value}))


def test_valid_reviewed_scheduled_config_candidate_round_trips() -> None:
    """The target codec can represent reviewed future intent without activating it."""
    config = replace(
        _dry_run().config,
        automation_enabled=True,
        desired_operating_mode=OperatingMode.SCHEDULED_CONTROL,
        authority_review_required=False,
    )

    decoded = decode_phase2_equipment_group_document(
        encode_phase2_equipment_group_document(config)
    )

    assert decoded == config


def test_hand_constructed_zone_and_runtime_bounds_fail_encoder_validation() -> None:
    """Encoder-side validation covers callers that bypass the JSON decoder."""
    zone = _dry_run().zones[0]
    duplicate_base = replace(
        zone.zone,
        window_door_entity_ids=(
            "binary_sensor.window",
            "binary_sensor.window",
        ),
    )
    duplicate_bindings = (
        Phase2BindingCandidate("binary_sensor.window", False, False),
        Phase2BindingCandidate("binary_sensor.window", False, False),
    )
    with pytest.raises(SchemaValidationError, match="duplicates"):
        encode_phase2_zone_config(
            replace(
                zone,
                zone=duplicate_base,
                contact_bindings=duplicate_bindings,
            )
        )

    runtime = _dry_run().runtime
    with pytest.raises(SchemaValidationError, match="at most 500"):
        encode_phase2_runtime_store_document(
            replace(runtime, decisions=tuple(MappingProxyType({}) for _ in range(501)))
        )
    with pytest.raises(SchemaValidationError, match="at most 100"):
        encode_phase2_runtime_store_document(
            replace(
                runtime,
                command_journal=tuple(MappingProxyType({}) for _ in range(101)),
            )
        )
    zone_id = next(iter(runtime.zones))
    negative = replace(
        runtime.shadow_qualification,
        material_transitions_by_zone=MappingProxyType({zone_id: -1}),
    )
    with pytest.raises(SchemaValidationError, match="nonnegative integers"):
        encode_phase2_runtime_store_document(
            replace(runtime, shadow_qualification=negative)
        )


def test_shared_policy_must_match_complete_migrated_zone_set() -> None:
    """A stale shared priority list cannot become a Phase 2 candidate."""
    baseline = _baseline()
    group = baseline["config_entry"]["data"]["equipment_group"]
    group["relationship"] = "shared_zoned"
    group["shared_policy"] = {
        "zone_priority_order": ["89246285-6f02-4e8a-94ed-bdfd4a5e62c4"],
        "conflict_policy": "suppress",
    }

    with pytest.raises(SchemaValidationError, match="every configured zone"):
        _dry_run(baseline=baseline)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda value: value.clear(), "must be an object"),
        (lambda value: value.update({1: "bad"}), "keys must be strings"),
        (
            lambda value: value.update(automation_enabled="false"),
            "must be a boolean",
        ),
        (
            lambda value: value.update(acknowledged_time_zone=123),
            "must be a string",
        ),
        (
            lambda value: value.update(desired_operating_mode="bad"),
            "unsupported value",
        ),
    ],
)
def test_config_decoder_rejects_invalid_container_and_scalar_types(
    mutate: Any,
    match: str,
) -> None:
    """Strict config decoding rejects malformed JSON-compatible shapes."""
    encoded: Any = dict(encode_phase2_equipment_group_document(_dry_run().config))
    mutate(encoded)
    value: object = encoded if encoded else []

    with pytest.raises(SchemaValidationError, match=match):
        decode_phase2_equipment_group_document(value)


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("minimum_heating_target_c", "cold", "finite number"),
        ("maximum_heating_target_c", float("inf"), "finite"),
    ],
)
def test_options_decoder_rejects_nonnumeric_and_nonfinite_limits(
    field: str,
    value: object,
    match: str,
) -> None:
    """JSON decoding validates numeric safety fields independently."""
    encoded = dict(encode_phase2_options(_dry_run().options))
    safety = cast(dict[str, object], encoded["safety_limits"])
    safety[field] = value

    with pytest.raises(SchemaValidationError, match=match):
        decode_phase2_options(encoded)


def test_options_decoder_rejects_zero_positive_timing() -> None:
    """Positive timing fields reject zero before policy-level validation."""
    encoded = dict(encode_phase2_options(_dry_run().options))
    timing = cast(dict[str, object], encoded["command_timing"])
    timing["retry_delay_seconds"] = 0

    with pytest.raises(SchemaValidationError, match="greater than zero"):
        decode_phase2_options(encoded)


def test_config_decoder_requires_authority_collection_to_be_a_list() -> None:
    """Tuple-like authority data cannot bypass the JSON list contract."""
    encoded = dict(encode_phase2_equipment_group_document(_dry_run().config))
    encoded["command_authority_entity_ids"] = {}

    with pytest.raises(SchemaValidationError, match="must be a list"):
        decode_phase2_equipment_group_document(encoded)


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (
            lambda value: value.update(schema_version="2"),
            "must be an integer",
        ),
        (
            lambda value: value.update(saved_at="not-a-date"),
            "ISO 8601",
        ),
        (
            lambda value: value.update(equipment_group_id="not-a-uuid"),
            "valid UUID",
        ),
        (
            lambda value: value.update(
                zones={"not-a-uuid": next(iter(value["zones"].values()))}
            ),
            "valid UUID",
        ),
        (
            lambda value: value.update(command_journal=[{"bad": {1, 2}}]),
            "JSON-compatible",
        ),
        (
            lambda value: value.update(command_journal=[{"bad": float("nan")}]),
            "finite",
        ),
    ],
)
def test_runtime_decoder_rejects_invalid_version_dates_ids_and_json(
    mutate: Any,
    match: str,
) -> None:
    """Runtime schema rejects malformed primitive and reserved-record values."""
    encoded = deepcopy(dict(encode_phase2_runtime_store_document(_dry_run().runtime)))
    mutate(encoded)

    with pytest.raises(SchemaValidationError, match=match):
        decode_phase2_runtime_store_document(encoded)


def test_runtime_decode_preserves_optional_null_zone_fields() -> None:
    """Comparison-only restart values may be explicitly unavailable."""
    encoded = deepcopy(dict(encode_phase2_runtime_store_document(_dry_run().runtime)))
    state = next(iter(cast(dict[str, dict[str, object]], encoded["zones"]).values()))
    state["last_live_observation_at"] = None
    state["comparison_temperature_c"] = None
    state["comparison_humidity_pct"] = None
    state["last_decision_id"] = None

    decoded = decode_phase2_runtime_store_document(encoded)
    zone = next(iter(decoded.zones.values()))

    assert zone.last_live_observation_at is None
    assert zone.comparison_temperature_c is None
    assert zone.last_decision_id is None
