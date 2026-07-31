"""Test Phase 1 schema models and JSON boundary helpers."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from math import inf, nan
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from custom_components.intelligent_climate.models import (
    DEFAULT_OPTIONS,
    AggregationStrategy,
    ControlState,
    EquipmentRelationship,
    EquipmentType,
    ObservationSourceId,
    SchemaMigrationError,
    SchemaValidationError,
    ThermostatRole,
    decode_configuration_graph,
    decode_equipment_group_document,
    decode_equipment_group_documents,
    decode_options,
    decode_runtime_store_document,
    decode_zone_config,
    encode_configuration_graph,
    encode_equipment_group_document,
    encode_options,
    encode_runtime_store_document,
    encode_zone_config,
    migrate_config_entry_document,
    migrate_options_document,
    migrate_runtime_store_document,
    migrate_zone_document,
)

ROOT = Path(__file__).parents[2]
INTEGRATION_DIR = ROOT / "custom_components" / "intelligent_climate"

GROUP_ID = "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
ZONE_ID = "99246285-6f02-4e8a-94ed-bdfd4a5e62c4"
ZONE_ID_2 = "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8"
TEMP_SOURCE_ID = "f15f73b1-ea59-4b28-819f-7b99acf065bf"
HUMIDITY_SOURCE_ID = "ce30dafc-fadd-4cc4-b261-8a896d5a6d12"
TEMP_SOURCE_ID_2 = "52c7a2d9-8de8-4474-bf1a-e2b0a7ce0a50"
HUMIDITY_SOURCE_ID_2 = "c5f3d57f-d900-4b6d-9f87-c421e48f6220"
DECISION_ID = "37eaa5de-8a48-47ea-9988-bb0fc2e10a24"


def equipment_group_document() -> dict[str, Any]:
    """Return a valid parent config-entry document."""
    return {
        "equipment_group": {
            "equipment_group_id": GROUP_ID,
            "name": "Main Floor HVAC",
            "equipment_type": "air_source_heat_pump",
            "relationship": "single_system",
            "thermostats": [
                {
                    "entity_id": "climate.dining_room",
                    "role": "primary",
                }
            ],
            "shared_policy": None,
        }
    }


def zone_document() -> dict[str, Any]:
    """Return a valid zone config-subentry document."""
    return {
        "data_version": 1,
        "zone_id": ZONE_ID,
        "name": "Dining Room",
        "thermostat_entity_ids": ["climate.dining_room"],
        "temperature_sources": [
            {
                "source_id": TEMP_SOURCE_ID,
                "entity_id": "climate.dining_room",
                "attribute": "current_temperature",
                "offset_c": 0.0,
                "weight": 1.0,
                "priority": 0,
                "enabled": True,
            }
        ],
        "humidity_sources": [
            {
                "source_id": HUMIDITY_SOURCE_ID,
                "entity_id": "climate.dining_room",
                "attribute": "current_humidity",
                "offset_pct": 0.0,
                "weight": 1.0,
                "priority": 0,
                "enabled": True,
            }
        ],
        "window_door_entity_ids": [],
        "occupancy_entity_ids": [],
        "stage_entity_ids": [],
        "fan_entity_ids": [],
    }


def zone_skeleton_document() -> dict[str, Any]:
    """Return a valid standalone pre-binding zone document."""
    document = zone_document()
    document["thermostat_entity_ids"] = []
    document["temperature_sources"] = []
    document["humidity_sources"] = []
    return document


def options_document() -> dict[str, Any]:
    """Return the valid default options document."""
    return dict(encode_options(DEFAULT_OPTIONS))


def runtime_store_document() -> dict[str, Any]:
    """Return a valid runtime Store v1 document."""
    return {
        "schema_version": 1,
        "entry_id": "01JEXAMPLEENTRY",
        "equipment_group_id": GROUP_ID,
        "saved_at": "2026-07-20T15:30:00+00:00",
        "last_clean_shutdown": True,
        "zones": {
            ZONE_ID: {
                "last_runtime_state": "observing",
                "last_live_observation_at": "2026-07-20T15:29:48+00:00",
                "last_effective_temperature_c": 23.7,
                "last_effective_humidity_pct": 50.0,
                "last_decision_id": DECISION_ID,
            }
        },
        "source_baselines": {
            TEMP_SOURCE_ID: {
                "last_accepted_value": 23.7,
                "last_accepted_at": "2026-07-20T15:29:48+00:00",
            }
        },
        "decisions": [],
        "command_journal": [],
    }


def activity_document() -> dict[str, Any]:
    """Return one valid strict activity stored in the legacy decisions field."""
    return {
        "record_id": DECISION_ID,
        "timestamp": "2026-07-20T15:29:50+00:00",
        "equipment_group_id": GROUP_ID,
        "zone_id": ZONE_ID,
        "activity_type": "source_quality_changed",
        "reason_code": "source_excluded",
        "severity": "warning",
        "explanation": "A configured observation source was excluded.",
        "detail": {
            "source_id": TEMP_SOURCE_ID,
            "new_quality": "stale",
        },
    }


def assert_error(document: object, expected: str) -> None:
    """Assert a document raises a path-aware schema validation error."""
    with pytest.raises(SchemaValidationError, match=expected):
        if isinstance(document, tuple):
            decode_configuration_graph(document[0], document[1])
        else:
            decode_zone_config(document)


def test_valid_minimal_one_group_one_zone_schema_decodes() -> None:
    """Test a valid one-equipment-group/one-zone graph."""
    graph = decode_configuration_graph(equipment_group_document(), [zone_document()])

    assert graph.equipment_group.name == "Main Floor HVAC"
    assert graph.equipment_group.equipment_type is EquipmentType.AIR_SOURCE_HEAT_PUMP
    assert graph.equipment_group.relationship is EquipmentRelationship.SINGLE_SYSTEM
    assert graph.equipment_group.thermostats[0].role is ThermostatRole.PRIMARY
    assert graph.zones[0].name == "Dining Room"
    assert graph.zones[0].temperature_sources[0].source_id == ObservationSourceId.parse(
        TEMP_SOURCE_ID
    )


def test_valid_schema_round_trips_and_preserves_stable_identifiers() -> None:
    """Test deterministic encode/decode preserves semantic equality and IDs."""
    graph = decode_configuration_graph(equipment_group_document(), [zone_document()])
    encoded = encode_configuration_graph(graph)

    assert encoded == encode_configuration_graph(
        decode_configuration_graph(
            {"equipment_group": encoded["equipment_group"]},
            encoded["zones"],
        )
    )
    assert encoded["equipment_group"]["equipment_group_id"] == GROUP_ID
    assert encoded["zones"][0]["zone_id"] == ZONE_ID
    assert encoded["zones"][0]["temperature_sources"][0]["source_id"] == TEMP_SOURCE_ID


def test_standalone_empty_zone_skeleton_round_trips() -> None:
    """Test Task 4 can persist a strict zone before Task 5 bindings exist."""
    document = zone_skeleton_document()

    encoded = dict(encode_zone_config(decode_zone_config(document)))

    assert encoded == document
    assert dict(encode_zone_config(decode_zone_config(encoded))) == document
    json.dumps(encoded)


def test_mapping_wrapped_zone_skeleton_decodes() -> None:
    """Test Home Assistant immutable root mappings cross the zone boundary."""
    document = zone_skeleton_document()

    zone = decode_zone_config(MappingProxyType(document))

    assert str(zone.zone_id) == ZONE_ID
    assert zone.thermostat_entity_ids == ()
    assert zone.temperature_sources == ()


def test_models_are_immutable() -> None:
    """Test decoded models are frozen."""
    graph = decode_configuration_graph(equipment_group_document(), [zone_document()])

    with pytest.raises(FrozenInstanceError):
        graph.equipment_group.name = "Renamed"  # type: ignore[misc]


def test_missing_required_field_has_precise_path() -> None:
    """Test missing fields identify the failing path."""
    document = zone_document()
    del document["name"]

    with pytest.raises(SchemaValidationError, match="name: missing required field"):
        decode_zone_config(document)


def test_incorrect_json_type_has_precise_path() -> None:
    """Test wrong JSON value types are rejected."""
    document = zone_document()
    document["temperature_sources"] = {"not": "a list"}

    with pytest.raises(
        SchemaValidationError,
        match=r"temperature_sources: must be a list",
    ):
        decode_zone_config(document)


def test_malformed_uuid_is_rejected() -> None:
    """Test invalid stable identifiers are rejected."""
    document = zone_document()
    document["zone_id"] = "not-a-uuid"

    with pytest.raises(SchemaValidationError, match="zone_id: must be a valid UUID"):
        decode_zone_config(document)


def test_empty_names_are_rejected() -> None:
    """Test user-visible names must not be empty or whitespace."""
    document = zone_document()
    document["name"] = "   "

    with pytest.raises(SchemaValidationError, match="name: must not be empty"):
        decode_zone_config(document)


def test_padded_persisted_zone_name_is_rejected() -> None:
    """Test persisted zone names must already be normalized."""
    document = zone_skeleton_document()
    document["name"] = " Dining Room "

    with pytest.raises(
        SchemaValidationError,
        match="name: must not have surrounding whitespace",
    ):
        decode_zone_config(document)


def test_strings_with_surrounding_whitespace_are_rejected() -> None:
    """Test persisted identifiers and entity IDs are not silently trimmed."""
    document = zone_document()
    document["temperature_sources"][0]["entity_id"] = " climate.dining_room "

    with pytest.raises(
        SchemaValidationError,
        match=r"temperature_sources\[0\]\.entity_id: "
        "must not have surrounding whitespace",
    ):
        decode_zone_config(document)


def test_out_of_phase_operating_mode_is_rejected_by_existing_model() -> None:
    """Task 2 vocabulary does not admit later predictive-control intent."""
    from custom_components.intelligent_climate.models import parse_operating_mode

    with pytest.raises(ValueError):
        parse_operating_mode("predictive_control")


def test_duplicate_equipment_group_ids_are_rejected() -> None:
    """Test duplicate group IDs are rejected across parent documents."""
    documents = [equipment_group_document(), equipment_group_document()]

    with pytest.raises(
        SchemaValidationError,
        match="equipment_groups: duplicate equipment_group_id",
    ):
        decode_equipment_group_documents(documents)


def test_multiple_unique_equipment_group_ids_are_accepted() -> None:
    """Test multiple unique group documents decode for duplicate checks."""
    second = equipment_group_document()
    second["equipment_group"]["equipment_group_id"] = (
        "55caa4e2-3e1f-4030-8068-3f0d20720baa"
    )
    second["equipment_group"]["name"] = "Upstairs HVAC"

    documents = decode_equipment_group_documents([equipment_group_document(), second])

    assert [document.equipment_group.name for document in documents] == [
        "Main Floor HVAC",
        "Upstairs HVAC",
    ]


def test_duplicate_zone_ids_are_rejected() -> None:
    """Test one zone ID cannot appear twice in one graph."""
    zones = [zone_document(), zone_document()]

    with pytest.raises(SchemaValidationError, match="zones: duplicate zone_id"):
        decode_configuration_graph(equipment_group_document(), zones)


def test_empty_zone_collection_is_rejected() -> None:
    """Test one equipment group must have at least one zone."""
    with pytest.raises(SchemaValidationError, match="zones: must not be empty"):
        decode_configuration_graph(equipment_group_document(), [])


def test_complete_graph_rejects_duplicate_source_ids_across_zones() -> None:
    """Test complete-graph validation rejects source IDs reused by zones."""
    second_zone = zone_document()
    second_zone["zone_id"] = ZONE_ID_2
    second_zone["name"] = "Living Room"
    second_zone["humidity_sources"][0]["source_id"] = HUMIDITY_SOURCE_ID_2
    second_zone["temperature_sources"][0]["entity_id"] = (
        "sensor.living_room_temperature"
    )

    with pytest.raises(
        SchemaValidationError,
        match="zones: duplicate observation source_id",
    ):
        decode_configuration_graph(
            equipment_group_document(),
            [zone_document(), second_zone],
        )


def test_standalone_zone_rejects_duplicate_temperature_source_ids() -> None:
    """Test duplicate temperature IDs report the temperature collection."""
    document = zone_document()
    duplicate = deepcopy(document["temperature_sources"][0])
    duplicate["entity_id"] = "sensor.living_room_temperature"
    document["temperature_sources"].append(duplicate)

    with pytest.raises(SchemaValidationError) as err:
        decode_zone_config(document)

    assert err.value.path == "temperature_sources"
    assert err.value.message == "duplicate observation source_id"


def test_standalone_zone_rejects_duplicate_humidity_source_ids() -> None:
    """Test duplicate humidity IDs report the humidity collection."""
    document = zone_document()
    duplicate = deepcopy(document["humidity_sources"][0])
    duplicate["entity_id"] = "sensor.living_room_humidity"
    document["humidity_sources"].append(duplicate)

    with pytest.raises(SchemaValidationError) as err:
        decode_zone_config(document)

    assert err.value.path == "humidity_sources"
    assert err.value.message == "duplicate observation source_id"


def test_standalone_zone_reports_cross_type_source_id_on_humidity_path() -> None:
    """Test cross-type reuse reports the conflicting later collection."""
    document = zone_document()
    document["humidity_sources"][0]["source_id"] = TEMP_SOURCE_ID

    with pytest.raises(SchemaValidationError) as err:
        decode_zone_config(document)

    assert err.value.path == "humidity_sources"
    assert err.value.message == "duplicate observation source_id"


def test_duplicate_source_entity_attribute_in_one_zone_is_rejected() -> None:
    """Test one zone cannot bind the same source entity and attribute twice."""
    document = zone_document()
    duplicate = deepcopy(document["temperature_sources"][0])
    duplicate["source_id"] = TEMP_SOURCE_ID_2
    document["temperature_sources"].append(duplicate)

    with pytest.raises(
        SchemaValidationError,
        match="temperature_sources: must not repeat",
    ):
        decode_zone_config(document)


def test_duplicate_humidity_source_entity_attribute_in_one_zone_is_rejected() -> None:
    """Test one zone cannot bind the same humidity entity and attribute twice."""
    document = zone_document()
    duplicate = deepcopy(document["humidity_sources"][0])
    duplicate["source_id"] = TEMP_SOURCE_ID_2
    document["humidity_sources"].append(duplicate)

    with pytest.raises(
        SchemaValidationError,
        match="humidity_sources: must not repeat",
    ):
        decode_zone_config(document)


def test_cross_type_duplicate_entity_attribute_is_rejected() -> None:
    """Temperature and humidity collections cannot repeat one exact binding."""
    document = zone_document()
    document["humidity_sources"][0]["attribute"] = "current_temperature"

    with pytest.raises(
        SchemaValidationError,
        match="temperature_sources: must not repeat",
    ):
        decode_zone_config(document)


def test_source_entity_attribute_reuse_across_zones_is_allowed() -> None:
    """Test shared entities can be reused across zones with stable source IDs."""
    second_zone = zone_document()
    second_zone["zone_id"] = ZONE_ID_2
    second_zone["name"] = "Living Room"
    second_zone["temperature_sources"][0]["source_id"] = TEMP_SOURCE_ID_2
    second_zone["humidity_sources"][0]["source_id"] = HUMIDITY_SOURCE_ID_2

    graph = decode_configuration_graph(
        equipment_group_document(),
        [zone_document(), second_zone],
    )

    assert [str(zone.zone_id) for zone in graph.zones] == [ZONE_ID, ZONE_ID_2]


def test_complete_graph_rejects_missing_temperature_sources() -> None:
    """Test graph readiness still requires a temperature source."""
    document = zone_document()
    document["temperature_sources"] = []

    with pytest.raises(
        SchemaValidationError,
        match=r"zones\[0\]\.temperature_sources: must not be empty",
    ):
        decode_configuration_graph(equipment_group_document(), [document])


def test_complete_graph_rejects_empty_zone_skeleton() -> None:
    """Test a structurally valid skeleton is not a ready complete graph."""
    with pytest.raises(
        SchemaValidationError,
        match=r"zones\[0\]\.thermostat_entity_ids: must not be empty",
    ):
        decode_configuration_graph(
            equipment_group_document(),
            [zone_skeleton_document()],
        )


@pytest.mark.parametrize(
    "field",
    [
        "thermostat_entity_ids",
        "temperature_sources",
        "humidity_sources",
        "window_door_entity_ids",
        "occupancy_entity_ids",
        "stage_entity_ids",
        "fan_entity_ids",
    ],
)
def test_zone_skeleton_binding_fields_must_be_lists(field: str) -> None:
    """Test every deferred-binding collection retains strict list typing."""
    document = zone_skeleton_document()
    document[field] = ()

    with pytest.raises(SchemaValidationError, match=f"{field}: must be a list"):
        decode_zone_config(document)


def test_duplicate_zone_thermostat_ids_are_rejected() -> None:
    """Test thermostat membership cannot repeat in one zone."""
    document = zone_document()
    document["thermostat_entity_ids"] = ["climate.dining_room", "climate.dining_room"]

    with pytest.raises(
        SchemaValidationError,
        match="thermostat_entity_ids: must not contain duplicates",
    ):
        decode_zone_config(document)


def test_duplicate_equipment_group_thermostat_bindings_are_rejected() -> None:
    """Test one equipment group cannot bind the same thermostat twice."""
    group = equipment_group_document()
    group["equipment_group"]["thermostats"].append(
        {"entity_id": "climate.dining_room", "role": "secondary"}
    )

    with pytest.raises(
        SchemaValidationError,
        match=r"equipment_group\.thermostats: must not contain duplicate entity IDs",
    ):
        decode_equipment_group_document(group)


def test_broken_zone_thermostat_reference_is_rejected() -> None:
    """Test zones cannot reference thermostats outside the equipment group."""
    document = zone_document()
    document["thermostat_entity_ids"] = ["climate.other"]

    with pytest.raises(
        SchemaValidationError,
        match=r"zones\[0\]\.thermostat_entity_ids: references thermostat",
    ):
        decode_configuration_graph(equipment_group_document(), [document])


def test_unassigned_group_thermostat_is_rejected() -> None:
    """Test every equipment group thermostat must belong to at least one zone."""
    group = equipment_group_document()
    group["equipment_group"]["thermostats"].append(
        {"entity_id": "climate.upstairs", "role": "secondary"}
    )

    with pytest.raises(
        SchemaValidationError,
        match=r"equipment_group\.thermostats: every thermostat",
    ):
        decode_configuration_graph(group, [zone_document()])


def test_standalone_equipment_group_skeleton_allows_empty_thermostats() -> None:
    """Test an incomplete parent entry can precede thermostat selection."""
    group = equipment_group_document()
    group["equipment_group"]["thermostats"] = []

    document = decode_equipment_group_document(group)

    assert document.equipment_group.thermostats == ()
    assert encode_equipment_group_document(document) == group


def test_equipment_group_document_accepts_mapping_proxy_root() -> None:
    """Test immutable Home Assistant-style root mappings decode normally."""
    caller_document = equipment_group_document()
    original_document = deepcopy(caller_document)
    immutable_root = MappingProxyType(caller_document)

    decoded = decode_equipment_group_document(immutable_root)

    assert decoded == decode_equipment_group_document(original_document)
    assert caller_document == original_document


def test_mapping_root_normalizes_to_independent_plain_dict() -> None:
    """Test mapping normalization retains no caller-owned root or nested objects."""
    caller_document = equipment_group_document()
    original_document = deepcopy(caller_document)
    immutable_root = MappingProxyType(caller_document)

    normalized = migrate_config_entry_document(
        immutable_root,
        version=1,
        minor_version=0,
    )

    assert type(normalized) is dict
    assert normalized == original_document
    assert normalized is not immutable_root
    assert normalized["equipment_group"] is not caller_document["equipment_group"]
    normalized["equipment_group"]["name"] = "Changed"
    assert caller_document == original_document


def test_mapping_root_rejects_non_string_keys() -> None:
    """Test immutable mappings retain the JSON string-key boundary."""
    invalid_root = MappingProxyType({1: equipment_group_document()["equipment_group"]})

    with pytest.raises(
        SchemaValidationError,
        match="<root>: object keys must be strings",
    ):
        decode_equipment_group_document(invalid_root)


@pytest.mark.parametrize(
    ("mapping", "message"),
    [
        ({}, "equipment_group: missing required field"),
        (
            {
                "equipment_group": equipment_group_document()["equipment_group"],
                "future_field": True,
            },
            "future_field: unknown field",
        ),
    ],
)
def test_mapping_root_preserves_strict_field_validation(
    mapping: dict[str, Any],
    message: str,
) -> None:
    """Test mapping compatibility does not relax required or unknown fields."""
    with pytest.raises(SchemaValidationError, match=message):
        decode_equipment_group_document(MappingProxyType(mapping))


@pytest.mark.parametrize(
    "invalid_root",
    [[], [("equipment_group", {})], (), "equipment_group", 1],
)
def test_equipment_group_document_rejects_non_mapping_roots(
    invalid_root: object,
) -> None:
    """Test sequences and other non-mappings are never coerced into objects."""
    with pytest.raises(SchemaValidationError, match="<root>: must be an object"):
        decode_equipment_group_document(invalid_root)


def test_complete_graph_equipment_group_thermostats_must_not_be_empty() -> None:
    """Test a complete configuration graph still needs a thermostat binding."""
    group = equipment_group_document()
    group["equipment_group"]["thermostats"] = []

    with pytest.raises(
        SchemaValidationError,
        match=r"equipment_group\.thermostats: must not be empty",
    ):
        decode_configuration_graph(group, [zone_document()])


def test_shared_zoned_relationship_requires_policy() -> None:
    """Test shared/zoned equipment must include explicit metadata."""
    group = equipment_group_document()
    group["equipment_group"]["relationship"] = "shared_zoned"

    with pytest.raises(
        SchemaValidationError,
        match=r"equipment_group\.shared_policy: is required",
    ):
        decode_equipment_group_document(group)


def test_non_shared_relationship_rejects_shared_policy() -> None:
    """Test shared policy cannot appear for single-system equipment."""
    group = equipment_group_document()
    group["equipment_group"]["shared_policy"] = {
        "zone_priority_order": [ZONE_ID],
        "conflict_policy": "future_manual_review",
    }

    with pytest.raises(
        SchemaValidationError,
        match=r"equipment_group\.shared_policy: must be null",
    ):
        decode_equipment_group_document(group)


def test_shared_policy_zone_priority_must_not_be_empty() -> None:
    """Test shared policy priority order cannot be empty."""
    group = equipment_group_document()
    group["equipment_group"]["relationship"] = "shared_zoned"
    group["equipment_group"]["shared_policy"] = {
        "zone_priority_order": [],
        "conflict_policy": "future_manual_review",
    }

    with pytest.raises(
        SchemaValidationError,
        match="zone_priority_order: must not be empty",
    ):
        decode_equipment_group_document(group)


def test_shared_policy_zone_priority_must_not_duplicate_zones() -> None:
    """Test shared policy priority order cannot repeat zones."""
    group = equipment_group_document()
    group["equipment_group"]["relationship"] = "shared_zoned"
    group["equipment_group"]["shared_policy"] = {
        "zone_priority_order": [ZONE_ID, ZONE_ID],
        "conflict_policy": "future_manual_review",
    }

    with pytest.raises(
        SchemaValidationError,
        match="zone_priority_order: must not contain duplicate",
    ):
        decode_equipment_group_document(group)


def test_shared_policy_must_reference_existing_zones() -> None:
    """Test shared policy priority order cannot reference nonexistent zones."""
    group = equipment_group_document()
    group["equipment_group"]["relationship"] = "shared_zoned"
    group["equipment_group"]["shared_policy"] = {
        "zone_priority_order": [ZONE_ID_2],
        "conflict_policy": "future_manual_review",
    }

    with pytest.raises(
        SchemaValidationError,
        match="zone_priority_order: must contain every configured zone",
    ):
        decode_configuration_graph(group, [zone_document()])


def test_unknown_fields_are_rejected() -> None:
    """Test persisted unknown fields are not silently discarded."""
    document = zone_document()
    document["future_field"] = True

    with pytest.raises(SchemaValidationError, match="future_field: unknown field"):
        decode_zone_config(document)


def test_current_versions_are_accepted() -> None:
    """Test current config, zone, and Store versions are supported."""
    assert (
        migrate_config_entry_document(
            equipment_group_document(),
            version=1,
            minor_version=0,
        )
        is not None
    )
    assert migrate_zone_document(zone_document()) is not None
    assert migrate_runtime_store_document(runtime_store_document()) is not None


@pytest.mark.parametrize(
    ("mutator", "expected"),
    [
        (
            lambda document: document.update({"data_version": 2}),
            "data_version: future zone data version is unsupported",
        ),
        (
            lambda document: document.update({"data_version": 0}),
            "data_version: no migration path for zone data version",
        ),
    ],
)
def test_zone_unsupported_versions_are_rejected(
    mutator: Any,
    expected: str,
) -> None:
    """Test unsupported zone versions fail explicitly."""
    document = zone_document()
    mutator(document)

    with pytest.raises(SchemaMigrationError, match=expected):
        migrate_zone_document(document)


def test_config_future_version_is_rejected() -> None:
    """Test future config-entry versions are unsupported."""
    with pytest.raises(SchemaMigrationError, match="future config-entry version"):
        migrate_config_entry_document(
            equipment_group_document(),
            version=2,
            minor_version=0,
        )


def test_config_future_minor_version_is_rejected() -> None:
    """Test future config-entry minor versions are unsupported."""
    with pytest.raises(SchemaMigrationError, match="future config-entry minor version"):
        migrate_config_entry_document(
            equipment_group_document(),
            version=1,
            minor_version=2,
        )


def test_options_future_minor_version_is_rejected() -> None:
    """Options use the same fail-closed config-entry minor-version boundary."""
    with pytest.raises(SchemaMigrationError, match="future config-entry minor version"):
        migrate_options_document(
            options_document(),
            version=1,
            minor_version=2,
        )


def test_config_old_version_without_migration_path_is_rejected() -> None:
    """Test undocumented historical config versions fail explicitly."""
    with pytest.raises(SchemaMigrationError, match="no migration path"):
        migrate_config_entry_document(
            equipment_group_document(),
            version=0,
            minor_version=0,
        )


def test_options_future_config_version_is_rejected() -> None:
    """Test options use config-entry versioning without an options version."""
    with pytest.raises(SchemaMigrationError, match="future config-entry version"):
        migrate_options_document(
            options_document(),
            version=2,
            minor_version=0,
        )


def test_options_old_config_version_without_migration_path_is_rejected() -> None:
    """Test undocumented historical options config versions fail explicitly."""
    with pytest.raises(SchemaMigrationError, match="no migration path"):
        migrate_options_document(
            options_document(),
            version=0,
            minor_version=0,
        )


def test_runtime_store_future_version_is_rejected() -> None:
    """Test future Store versions are unsupported."""
    document = runtime_store_document()
    document["schema_version"] = 2

    with pytest.raises(SchemaMigrationError, match="future runtime Store version"):
        migrate_runtime_store_document(document)


def test_future_zone_version_precedes_unknown_field_rejection() -> None:
    """Test future zone data is rejected by version before new fields."""
    document = zone_document()
    document["data_version"] = 2
    document["future_field"] = True

    with pytest.raises(
        SchemaMigrationError,
        match="data_version: future zone data version is unsupported",
    ):
        decode_zone_config(document)


def test_future_store_version_precedes_unknown_field_rejection() -> None:
    """Test future Store data is rejected by version before new fields."""
    document = runtime_store_document()
    document["schema_version"] = 2
    document["future_field"] = True

    with pytest.raises(
        SchemaMigrationError,
        match="schema_version: future runtime Store version is unsupported",
    ):
        decode_runtime_store_document(document)


def test_future_options_config_version_precedes_unknown_field_rejection() -> None:
    """Test future options data is rejected by config version before new fields."""
    document = options_document()
    document["future_field"] = True

    with pytest.raises(
        SchemaMigrationError,
        match="version: future config-entry version is unsupported",
    ):
        decode_options(document, version=2, minor_version=0)


def test_zone_missing_version_is_rejected_by_migration() -> None:
    """Test zone migration requires explicit data_version."""
    document = zone_document()
    del document["data_version"]

    with pytest.raises(
        SchemaMigrationError,
        match="data_version: missing required field",
    ):
        migrate_zone_document(document)


def test_runtime_store_missing_version_is_rejected_by_migration() -> None:
    """Test runtime Store migration requires explicit schema_version."""
    document = runtime_store_document()
    del document["schema_version"]

    with pytest.raises(
        SchemaMigrationError,
        match="schema_version: missing required field",
    ):
        migrate_runtime_store_document(document)


def test_migration_functions_do_not_mutate_caller_input() -> None:
    """Test migration scaffolding leaves caller dictionaries unchanged."""
    config = equipment_group_document()
    zone = zone_document()
    options = options_document()
    store = runtime_store_document()
    originals = deepcopy((config, zone, options, store))

    migrated_config = migrate_config_entry_document(config, version=1, minor_version=0)
    migrated_zone = migrate_zone_document(zone)
    migrated_options = migrate_options_document(options)
    migrated_store = migrate_runtime_store_document(store)

    assert (config, zone, options, store) == originals
    assert migrated_config == config
    assert migrated_zone == zone
    assert migrated_options == options
    assert migrated_store == store

    assert isinstance(migrated_config, dict)
    assert isinstance(migrated_zone, dict)
    assert isinstance(migrated_options, dict)
    assert isinstance(migrated_store, dict)
    assert migrated_config is not config
    assert migrated_config["equipment_group"] is not config["equipment_group"]
    assert migrated_zone is not zone
    assert migrated_zone["temperature_sources"] is not zone["temperature_sources"]
    assert migrated_options is not options
    assert migrated_store is not store
    assert migrated_store["zones"] is not store["zones"]


def test_options_decode_encode_defaults() -> None:
    """Test options schema decodes enums and numeric thresholds."""
    options = decode_options(options_document())

    assert options.temperature_strategy is AggregationStrategy.MEDIAN
    assert encode_options(options) == options_document()


def test_options_reject_bool_for_numeric_field() -> None:
    """Test booleans are not accepted for numeric-only fields."""
    document = options_document()
    document["history_max_records"] = True

    with pytest.raises(
        SchemaValidationError,
        match="history_max_records: must be an integer",
    ):
        decode_options(document)


@pytest.mark.parametrize("bad_value", [nan, inf, -inf])
def test_options_reject_nonfinite_numbers(bad_value: float) -> None:
    """Test NaN and infinity are rejected where numeric values are permitted."""
    document = options_document()
    document["outlier_floor_c"] = bad_value

    with pytest.raises(SchemaValidationError, match="outlier_floor_c: must be finite"):
        decode_options(document)


def test_options_reject_non_boolean_toggle() -> None:
    """Test boolean option fields require JSON booleans."""
    document = options_document()
    document["observation_enabled"] = "true"

    with pytest.raises(
        SchemaValidationError,
        match="observation_enabled: must be a boolean",
    ):
        decode_options(document)


def test_options_reject_zero_positive_int() -> None:
    """Test positive integer options must be at least one."""
    document = options_document()
    document["source_stale_after_seconds"] = 0

    with pytest.raises(
        SchemaValidationError,
        match="source_stale_after_seconds: must be at least 1",
    ):
        decode_options(document)


def test_options_reject_non_numeric_threshold() -> None:
    """Test numeric threshold fields require numbers."""
    document = options_document()
    document["jump_limit_c_per_5_minutes"] = "2.8"

    with pytest.raises(
        SchemaValidationError,
        match="jump_limit_c_per_5_minutes: must be a finite number",
    ):
        decode_options(document)


def test_options_reject_non_positive_weight_like_threshold() -> None:
    """Test positive float options must be greater than zero."""
    document = options_document()
    document["outlier_floor_c"] = 0.0

    with pytest.raises(
        SchemaValidationError,
        match="outlier_floor_c: must be greater than zero",
    ):
        decode_options(document)


def test_options_reject_history_limit_above_phase_1_cap() -> None:
    """Test history count is capped by the Phase 1 design."""
    document = options_document()
    document["history_max_records"] = 501

    with pytest.raises(
        SchemaValidationError,
        match="history_max_records: must be at most 500",
    ):
        decode_options(document)


def test_options_reject_invalid_enum_value() -> None:
    """Test unsupported enum values are rejected."""
    document = options_document()
    document["temperature_strategy"] = "occupied_room"

    with pytest.raises(
        SchemaValidationError,
        match="temperature_strategy: unsupported value",
    ):
        decode_options(document)


def test_options_reject_invalid_bounds() -> None:
    """Test min/max temperature bounds must be meaningful."""
    document = options_document()
    document["indoor_temperature_min_c"] = 43.3
    document["indoor_temperature_max_c"] = 1.7

    with pytest.raises(
        SchemaValidationError,
        match="indoor_temperature_min_c: must be less",
    ):
        decode_options(document)


@pytest.mark.parametrize(
    ("document_factory", "mutator", "decoder", "expected"),
    [
        (
            equipment_group_document,
            lambda document: document["equipment_group"].update(
                {"equipment_group_id": 42}
            ),
            decode_equipment_group_document,
            "equipment_group.equipment_group_id: must be a string",
        ),
        (
            equipment_group_document,
            lambda document: document["equipment_group"].update({"name": 42}),
            decode_equipment_group_document,
            "equipment_group.name: must be a string",
        ),
        (
            equipment_group_document,
            lambda document: document["equipment_group"].update({"equipment_type": 42}),
            decode_equipment_group_document,
            "equipment_group.equipment_type: must be a string",
        ),
        (
            zone_document,
            lambda document: document.update({"zone_id": 42}),
            decode_zone_config,
            "zone_id: must be a string",
        ),
    ],
)
def test_schema_identifier_name_and_enum_boundaries_reject_nonstrings(
    document_factory: Any,
    mutator: Any,
    decoder: Any,
    expected: str,
) -> None:
    """Strict scalar boundaries fail before values can enter typed models."""
    document = document_factory()
    mutator(document)

    with pytest.raises(SchemaValidationError, match=expected):
        decoder(document)


def test_runtime_store_round_trips_deterministically() -> None:
    """Test runtime Store decode/encode is deterministic and JSON-compatible."""
    document = decode_runtime_store_document(runtime_store_document())
    encoded = encode_runtime_store_document(document)

    assert encoded == runtime_store_document()
    assert encoded == encode_runtime_store_document(
        decode_runtime_store_document(encoded)
    )
    assert (
        encoded["zones"][ZONE_ID]["last_runtime_state"] == ControlState.OBSERVING.value
    )


def test_runtime_store_accepts_optional_null_zone_values() -> None:
    """Test runtime Store nullable fields decode and encode deterministically."""
    document = runtime_store_document()
    state = document["zones"][ZONE_ID]
    state["last_live_observation_at"] = None
    state["last_effective_temperature_c"] = None
    state["last_effective_humidity_pct"] = None
    state["last_decision_id"] = None

    decoded = decode_runtime_store_document(document)

    assert encode_runtime_store_document(decoded) == document


def test_runtime_store_decisions_are_bounded() -> None:
    """Test persisted decision history is schema-bounded without pruning."""
    document = runtime_store_document()
    document["decisions"] = [{} for _ in range(501)]

    with pytest.raises(
        SchemaValidationError,
        match="decisions: must contain at most 500 items",
    ):
        decode_runtime_store_document(document)


def test_runtime_store_decisions_are_decoded_immutably() -> None:
    """Test decoded activity records do not retain caller mapping references."""
    document = runtime_store_document()
    activity = activity_document()
    document["decisions"] = [activity]

    decoded = decode_runtime_store_document(document)
    activity["detail"]["new_quality"] = "valid"

    assert encode_runtime_store_document(decoded)["decisions"] == [activity_document()]
    with pytest.raises(TypeError):
        decoded.decisions[0].detail["new_quality"] = "changed"  # type: ignore[index]


def test_runtime_store_activity_ordering_and_duplicate_ids_are_strict() -> None:
    """Typed Store history sorts deterministically and rejects duplicate IDs."""
    document = runtime_store_document()
    later = activity_document()
    earlier = {
        **activity_document(),
        "record_id": "76907d21-8ae2-4dbb-b58c-2ded09b3b88b",
        "timestamp": "2026-07-20T15:29:49+00:00",
    }
    document["decisions"] = [later, earlier]

    decoded = decode_runtime_store_document(document)

    assert [str(record.record_id) for record in decoded.decisions] == [
        earlier["record_id"],
        later["record_id"],
    ]

    document["decisions"] = [later, {**earlier, "record_id": later["record_id"]}]
    with pytest.raises(SchemaValidationError, match="duplicate activity record_id"):
        decode_runtime_store_document(document)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (inf, "bounded scalars"),
        (object(), "must be a scalar"),
    ],
)
def test_runtime_store_rejects_unsafe_nested_decision_values(
    value: object,
    expected: str,
) -> None:
    """Typed activity detail still enforces the strict scalar safety boundary."""
    document = runtime_store_document()
    activity = activity_document()
    activity["detail"] = {"source_id": value}
    document["decisions"] = [activity]

    with pytest.raises(SchemaValidationError, match=expected):
        decode_runtime_store_document(document)


def test_runtime_store_rejects_invalid_humidity_percentage() -> None:
    """Test persisted humidity percentages must be plausible."""
    document = runtime_store_document()
    document["zones"][ZONE_ID]["last_effective_humidity_pct"] = 101.0

    with pytest.raises(SchemaValidationError, match="must be between 0 and 100"):
        decode_runtime_store_document(document)


@pytest.mark.parametrize(
    ("field_path", "mutator"),
    [
        (
            r"zones\." + ZONE_ID + r"\.last_effective_temperature_c: must be finite",
            lambda document: document["zones"][ZONE_ID].update(
                {"last_effective_temperature_c": inf}
            ),
        ),
        (
            r"source_baselines\."
            + TEMP_SOURCE_ID
            + r"\.last_accepted_value: must be finite",
            lambda document: document["source_baselines"][TEMP_SOURCE_ID].update(
                {"last_accepted_value": nan}
            ),
        ),
    ],
)
def test_runtime_store_rejects_nonfinite_numeric_values(
    field_path: str,
    mutator: Any,
) -> None:
    """Test persisted runtime temperatures and baselines must be finite."""
    document = runtime_store_document()
    mutator(document)

    with pytest.raises(SchemaValidationError, match=field_path):
        decode_runtime_store_document(document)


def test_runtime_store_rejects_non_object_map_keys() -> None:
    """Test JSON object keys must be strings."""
    document = runtime_store_document()
    document["zones"] = {1: document["zones"][ZONE_ID]}

    with pytest.raises(
        SchemaValidationError,
        match="zones: object keys must be strings",
    ):
        decode_runtime_store_document(document)


def test_runtime_store_rejects_invalid_datetime() -> None:
    """Test datetime strings must be valid ISO 8601 values."""
    document = runtime_store_document()
    document["saved_at"] = "not-a-datetime"

    with pytest.raises(
        SchemaValidationError,
        match="saved_at: must be an ISO 8601 datetime",
    ):
        decode_runtime_store_document(document)


def test_runtime_store_rejects_naive_datetime() -> None:
    """Test persisted datetimes must include timezone information."""
    document = runtime_store_document()
    document["saved_at"] = "2026-07-20T15:30:00"

    with pytest.raises(
        SchemaValidationError,
        match="saved_at: must include timezone information",
    ):
        decode_runtime_store_document(document)


def test_runtime_store_rejects_invalid_source_baseline_id() -> None:
    """Test source baseline keys must be valid source UUIDs."""
    document = runtime_store_document()
    document["source_baselines"] = {
        "not-a-uuid": document["source_baselines"][TEMP_SOURCE_ID]
    }

    with pytest.raises(SchemaValidationError, match="must be a valid UUID"):
        decode_runtime_store_document(document)


def test_runtime_store_rejects_command_journal_entries() -> None:
    """Test Phase 1 Store command journal remains empty."""
    document = runtime_store_document()
    document["command_journal"] = [{"intent": "turn on heat"}]

    with pytest.raises(
        SchemaValidationError,
        match="command_journal: must remain empty",
    ):
        decode_runtime_store_document(document)


def test_runtime_store_rejects_malformed_root_document() -> None:
    """Test root Store data must be a JSON object."""
    with pytest.raises(SchemaValidationError, match="<root>: must be an object"):
        decode_runtime_store_document([])


def test_source_enabled_defaults_true_for_design_example_compatibility() -> None:
    """Test source JSON without enabled still decodes to enabled=True."""
    document = zone_document()
    del document["temperature_sources"][0]["enabled"]
    del document["humidity_sources"][0]["enabled"]

    zone = decode_zone_config(document)

    assert zone.temperature_sources[0].enabled is True
    assert zone.humidity_sources[0].enabled is True
    assert encode_zone_config(zone)["temperature_sources"][0]["enabled"] is True


def test_source_attribute_can_be_null() -> None:
    """Test sources may read entity state directly when attribute is null."""
    document = zone_document()
    document["temperature_sources"][0]["attribute"] = None

    zone = decode_zone_config(document)

    assert zone.temperature_sources[0].attribute is None


def test_source_rejects_non_string_source_id() -> None:
    """Test source IDs must be string UUIDs."""
    document = zone_document()
    document["temperature_sources"][0]["source_id"] = 123

    with pytest.raises(
        SchemaValidationError,
        match=r"temperature_sources\[0\]\.source_id: must be a string",
    ):
        decode_zone_config(document)


def test_source_rejects_malformed_source_id() -> None:
    """Test source IDs must be valid UUIDs."""
    document = zone_document()
    document["temperature_sources"][0]["source_id"] = "not-a-uuid"

    with pytest.raises(
        SchemaValidationError,
        match=r"temperature_sources\[0\]\.source_id: must be a valid UUID",
    ):
        decode_zone_config(document)


def test_entity_id_shape_is_validated() -> None:
    """Test entity references must look like Home Assistant entity IDs."""
    document = zone_document()
    document["temperature_sources"][0]["entity_id"] = "sensor_without_domain"

    with pytest.raises(
        SchemaValidationError,
        match="must be a Home Assistant entity_id",
    ):
        decode_zone_config(document)


def test_observation_source_id_generation_is_unique() -> None:
    """Test the new stable source identifier can be generated."""
    assert ObservationSourceId.new() != ObservationSourceId.new()


def test_decode_equipment_group_document_round_trips() -> None:
    """Test parent config-entry document encoding is deterministic."""
    document = decode_equipment_group_document(equipment_group_document())

    assert encode_equipment_group_document(document) == equipment_group_document()


def test_schema_layer_has_no_home_assistant_persistence_writes() -> None:
    """Test schema modules do not use Home Assistant Store or save APIs."""
    offenders = [
        str(path.relative_to(ROOT))
        for path in (INTEGRATION_DIR / "models").rglob("*.py")
        if "Store(" in path.read_text() or "async_save" in path.read_text()
    ]

    assert offenders == []


def test_schema_module_has_no_home_assistant_runtime_dependency() -> None:
    """Test schema.py remains a pure model module without HA imports."""
    schema_source = (INTEGRATION_DIR / "models" / "schema.py").read_text()

    assert "homeassistant" not in schema_source


def test_integration_code_still_has_no_home_assistant_service_call_path() -> None:
    """Test schema work did not add direct Home Assistant service calls."""
    offenders = [
        str(path.relative_to(ROOT))
        for path in INTEGRATION_DIR.rglob("*.py")
        if "services.async_call" in path.read_text()
    ]

    assert offenders == []
