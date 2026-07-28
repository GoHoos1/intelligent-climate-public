"""Versioned schema models and JSON boundary helpers.

Persisted schema documents are decoded strictly: unknown fields are rejected
instead of retained or silently discarded. The Phase 1 design has no extension
bucket and no documented historical migrations, so accepting extra persisted
fields would make migrations ambiguous.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from math import isfinite
from types import MappingProxyType
from typing import Any
from uuid import UUID

from .activity import (
    ActivityReason,
    ActivityRecord,
    ActivitySeverity,
    ActivityType,
)
from .identifiers import EquipmentGroupId, ObservationSourceId, ZoneId

CONFIG_ENTRY_MAJOR_VERSION = 1
CONFIG_ENTRY_MINOR_VERSION = 1
ZONE_DATA_VERSION = 1
RUNTIME_STORE_SCHEMA_VERSION = 1

type JsonObject = Mapping[str, Any]


class SchemaValidationError(ValueError):
    """Raised when a schema document fails validation."""

    def __init__(self, path: str, message: str) -> None:
        """Initialize the path-aware validation error."""
        self.path = path
        self.message = message
        super().__init__(f"{path}: {message}")


class SchemaMigrationError(SchemaValidationError):
    """Raised when a schema document cannot be migrated safely."""


class EquipmentType(StrEnum):
    """Descriptive Phase 1 equipment types."""

    CONVENTIONAL = "conventional"
    AIR_SOURCE_HEAT_PUMP = "air_source_heat_pump"
    HEAT_PUMP_AUX_ELECTRIC = "heat_pump_aux_electric"
    DUAL_FUEL = "dual_fuel"
    BOILER = "boiler"
    RADIANT = "radiant"
    MINI_SPLIT = "mini_split"
    MULTISTAGE = "multistage"
    VARIABLE_CAPACITY = "variable_capacity"
    FAN_COIL = "fan_coil"
    UNKNOWN = "unknown"


class EquipmentRelationship(StrEnum):
    """Phase 1 equipment-to-zone relationship types."""

    SINGLE_SYSTEM = "single_system"
    INDEPENDENT = "independent"
    SHARED_ZONED = "shared_zoned"


class ThermostatRole(StrEnum):
    """Role assigned to a thermostat binding."""

    PRIMARY = "primary"
    SECONDARY = "secondary"


class AggregationStrategy(StrEnum):
    """Supported Phase 1 source aggregation strategies."""

    MEAN = "mean"
    MEDIAN = "median"
    WEIGHTED_AVERAGE = "weighted_average"
    PRIORITY = "priority"


class LogLevelDetail(StrEnum):
    """Supported diagnostic logging detail level."""

    NORMAL = "normal"
    VERBOSE = "verbose"


class ControlState(StrEnum):
    """Phase 1 runtime state values persisted in Store documents."""

    UNLOADED = "unloaded"
    INITIALIZING = "initializing"
    RECONCILING = "reconciling"
    DISABLED = "disabled"
    OBSERVING = "observing"
    DEGRADED = "degraded"
    UNLOADING = "unloading"


@dataclass(frozen=True, slots=True)
class ThermostatBinding:
    """A read-only binding to an existing Home Assistant climate entity."""

    entity_id: str
    role: ThermostatRole


@dataclass(frozen=True, slots=True)
class SharedEquipmentPolicy:
    """Future-safe metadata for shared/zoned equipment relationships."""

    zone_priority_order: tuple[ZoneId, ...]
    conflict_policy: str


@dataclass(frozen=True, slots=True)
class EquipmentGroupConfig:
    """Authoritative parent config-entry equipment data."""

    equipment_group_id: EquipmentGroupId
    name: str
    equipment_type: EquipmentType
    relationship: EquipmentRelationship
    thermostats: tuple[ThermostatBinding, ...]
    shared_policy: SharedEquipmentPolicy | None


@dataclass(frozen=True, slots=True)
class TemperatureSource:
    """Configured temperature observation source."""

    source_id: ObservationSourceId
    entity_id: str
    attribute: str | None
    offset_c: float
    weight: float
    priority: int
    enabled: bool


@dataclass(frozen=True, slots=True)
class HumiditySource:
    """Configured humidity observation source."""

    source_id: ObservationSourceId
    entity_id: str
    attribute: str | None
    offset_pct: float
    weight: float
    priority: int
    enabled: bool


@dataclass(frozen=True, slots=True)
class ZoneConfig:
    """Authoritative zone config-subentry data."""

    zone_id: ZoneId
    name: str
    thermostat_entity_ids: tuple[str, ...]
    temperature_sources: tuple[TemperatureSource, ...]
    humidity_sources: tuple[HumiditySource, ...]
    window_door_entity_ids: tuple[str, ...]
    occupancy_entity_ids: tuple[str, ...]
    stage_entity_ids: tuple[str, ...]
    fan_entity_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IntegrationOptions:
    """Config-entry options for Phase 1 observation behavior."""

    observation_enabled: bool
    temperature_strategy: AggregationStrategy
    humidity_strategy: AggregationStrategy
    min_valid_temperature_sources: int
    min_valid_humidity_sources: int
    source_stale_after_seconds: int
    startup_reconciliation_seconds: int
    jump_limit_c_per_5_minutes: float
    outlier_floor_c: float
    indoor_temperature_min_c: float
    indoor_temperature_max_c: float
    history_max_records: int
    history_max_age_days: int
    log_level_detail: LogLevelDetail


@dataclass(frozen=True, slots=True)
class EquipmentGroupDocument:
    """Decoded parent config-entry document."""

    equipment_group: EquipmentGroupConfig


@dataclass(frozen=True, slots=True)
class ConfigurationGraph:
    """Decoded equipment group and all zones for graph-level validation."""

    equipment_group: EquipmentGroupConfig
    zones: tuple[ZoneConfig, ...]


@dataclass(frozen=True, slots=True)
class RuntimeZoneState:
    """Persisted runtime Store state for one zone."""

    last_runtime_state: ControlState
    last_live_observation_at: datetime | None
    last_effective_temperature_c: float | None
    last_effective_humidity_pct: float | None
    last_decision_id: str | None


@dataclass(frozen=True, slots=True)
class SourceBaseline:
    """Persisted last accepted source value for restart reconciliation."""

    last_accepted_value: float
    last_accepted_at: datetime


@dataclass(frozen=True, slots=True)
class RuntimeStoreDocument:
    """Decoded runtime Store schema version 1 document."""

    entry_id: str
    equipment_group_id: EquipmentGroupId
    saved_at: datetime
    last_clean_shutdown: bool
    zones: dict[ZoneId, RuntimeZoneState]
    source_baselines: dict[ObservationSourceId, SourceBaseline]
    decisions: tuple[ActivityRecord, ...]
    command_journal: tuple[JsonObject, ...]


DEFAULT_OPTIONS = IntegrationOptions(
    observation_enabled=True,
    temperature_strategy=AggregationStrategy.MEDIAN,
    humidity_strategy=AggregationStrategy.MEDIAN,
    min_valid_temperature_sources=1,
    min_valid_humidity_sources=1,
    source_stale_after_seconds=1800,
    startup_reconciliation_seconds=60,
    jump_limit_c_per_5_minutes=2.8,
    outlier_floor_c=1.7,
    indoor_temperature_min_c=1.7,
    indoor_temperature_max_c=43.3,
    history_max_records=500,
    history_max_age_days=30,
    log_level_detail=LogLevelDetail.NORMAL,
)


def decode_equipment_group_document(
    value: object,
    *,
    version: int = CONFIG_ENTRY_MAJOR_VERSION,
    minor_version: int = CONFIG_ENTRY_MINOR_VERSION,
) -> EquipmentGroupDocument:
    """Decode parent config-entry data."""
    migrated = migrate_config_entry_document(
        value,
        version=version,
        minor_version=minor_version,
    )
    root = _object(migrated, "")
    _reject_unknown(root, {"equipment_group"}, "")
    return EquipmentGroupDocument(
        equipment_group=_decode_equipment_group(
            root["equipment_group"],
            "equipment_group",
        )
    )


def encode_equipment_group_document(document: EquipmentGroupDocument) -> JsonObject:
    """Encode parent config-entry data deterministically."""
    return {"equipment_group": _encode_equipment_group(document.equipment_group)}


def decode_zone_config(value: object) -> ZoneConfig:
    """Decode zone config-subentry data."""
    migrated = migrate_zone_document(value)
    root = _object(migrated, "")
    expected = {
        "data_version",
        "zone_id",
        "name",
        "thermostat_entity_ids",
        "temperature_sources",
        "humidity_sources",
        "window_door_entity_ids",
        "occupancy_entity_ids",
        "stage_entity_ids",
        "fan_entity_ids",
    }
    _reject_unknown(root, expected, "")
    _require_version(
        root.get("data_version"),
        ZONE_DATA_VERSION,
        "data_version",
        "zone data",
    )

    temperature_sources = tuple(
        _decode_temperature_source(item, f"temperature_sources[{index}]")
        for index, item in enumerate(
            _list(root.get("temperature_sources"), "temperature_sources")
        )
    )
    humidity_sources = tuple(
        _decode_humidity_source(item, f"humidity_sources[{index}]")
        for index, item in enumerate(
            _list(root.get("humidity_sources"), "humidity_sources")
        )
    )
    zone = ZoneConfig(
        zone_id=_parse_zone_id(root.get("zone_id"), "zone_id"),
        name=_name(root.get("name"), "name"),
        thermostat_entity_ids=_string_tuple(
            root.get("thermostat_entity_ids"),
            "thermostat_entity_ids",
            require_non_empty=False,
        ),
        temperature_sources=temperature_sources,
        humidity_sources=humidity_sources,
        window_door_entity_ids=_string_tuple(
            root.get("window_door_entity_ids"),
            "window_door_entity_ids",
            require_non_empty=False,
        ),
        occupancy_entity_ids=_string_tuple(
            root.get("occupancy_entity_ids"),
            "occupancy_entity_ids",
            require_non_empty=False,
        ),
        stage_entity_ids=_string_tuple(
            root.get("stage_entity_ids"),
            "stage_entity_ids",
            require_non_empty=False,
        ),
        fan_entity_ids=_string_tuple(
            root.get("fan_entity_ids"),
            "fan_entity_ids",
            require_non_empty=False,
        ),
    )
    _validate_zone(zone, "")
    return zone


def encode_zone_config(zone: ZoneConfig) -> JsonObject:
    """Encode zone config-subentry data deterministically."""
    return {
        "data_version": ZONE_DATA_VERSION,
        "zone_id": str(zone.zone_id),
        "name": zone.name,
        "thermostat_entity_ids": list(zone.thermostat_entity_ids),
        "temperature_sources": [
            _encode_temperature_source(source) for source in zone.temperature_sources
        ],
        "humidity_sources": [
            _encode_humidity_source(source) for source in zone.humidity_sources
        ],
        "window_door_entity_ids": list(zone.window_door_entity_ids),
        "occupancy_entity_ids": list(zone.occupancy_entity_ids),
        "stage_entity_ids": list(zone.stage_entity_ids),
        "fan_entity_ids": list(zone.fan_entity_ids),
    }


def decode_configuration_graph(
    equipment_group_data: object,
    zone_data: object,
) -> ConfigurationGraph:
    """Decode and validate a parent equipment group plus zone documents."""
    equipment_group = decode_equipment_group_document(
        equipment_group_data
    ).equipment_group
    zones = tuple(decode_zone_config(item) for item in _list(zone_data, "zones"))
    graph = ConfigurationGraph(equipment_group=equipment_group, zones=zones)
    _validate_graph(graph)
    return graph


def decode_equipment_group_documents(
    value: object,
) -> tuple[EquipmentGroupDocument, ...]:
    """Decode multiple parent documents and reject duplicate group IDs."""
    documents = tuple(
        decode_equipment_group_document(item)
        for item in _list(value, "equipment_groups")
    )
    group_ids = [document.equipment_group.equipment_group_id for document in documents]
    if len(set(group_ids)) != len(group_ids):
        raise SchemaValidationError("equipment_groups", "duplicate equipment_group_id")
    return documents


def encode_configuration_graph(graph: ConfigurationGraph) -> JsonObject:
    """Encode a complete configuration graph deterministically."""
    return {
        "equipment_group": _encode_equipment_group(graph.equipment_group),
        "zones": [encode_zone_config(zone) for zone in graph.zones],
    }


def decode_options(
    value: object,
    *,
    version: int = CONFIG_ENTRY_MAJOR_VERSION,
    minor_version: int = CONFIG_ENTRY_MINOR_VERSION,
) -> IntegrationOptions:
    """Decode config-entry options."""
    migrated = migrate_options_document(
        value,
        version=version,
        minor_version=minor_version,
    )
    root = _object(migrated, "")
    expected = set(_OPTIONS_FIELDS)
    _reject_unknown(root, expected, "")
    options = IntegrationOptions(
        observation_enabled=_bool(
            root.get("observation_enabled"),
            "observation_enabled",
        ),
        temperature_strategy=_enum(
            AggregationStrategy,
            root.get("temperature_strategy"),
            "temperature_strategy",
        ),
        humidity_strategy=_enum(
            AggregationStrategy,
            root.get("humidity_strategy"),
            "humidity_strategy",
        ),
        min_valid_temperature_sources=_positive_int(
            root.get("min_valid_temperature_sources"),
            "min_valid_temperature_sources",
        ),
        min_valid_humidity_sources=_positive_int(
            root.get("min_valid_humidity_sources"),
            "min_valid_humidity_sources",
        ),
        source_stale_after_seconds=_positive_int(
            root.get("source_stale_after_seconds"),
            "source_stale_after_seconds",
        ),
        startup_reconciliation_seconds=_positive_int(
            root.get("startup_reconciliation_seconds"),
            "startup_reconciliation_seconds",
        ),
        jump_limit_c_per_5_minutes=_positive_float(
            root.get("jump_limit_c_per_5_minutes"),
            "jump_limit_c_per_5_minutes",
        ),
        outlier_floor_c=_positive_float(root.get("outlier_floor_c"), "outlier_floor_c"),
        indoor_temperature_min_c=_finite_float(
            root.get("indoor_temperature_min_c"),
            "indoor_temperature_min_c",
        ),
        indoor_temperature_max_c=_finite_float(
            root.get("indoor_temperature_max_c"),
            "indoor_temperature_max_c",
        ),
        history_max_records=_bounded_history_records(
            root.get("history_max_records"),
            "history_max_records",
        ),
        history_max_age_days=_positive_int(
            root.get("history_max_age_days"),
            "history_max_age_days",
        ),
        log_level_detail=_enum(
            LogLevelDetail,
            root.get("log_level_detail"),
            "log_level_detail",
        ),
    )
    if options.indoor_temperature_min_c >= options.indoor_temperature_max_c:
        raise SchemaValidationError(
            "indoor_temperature_min_c",
            "must be less than indoor_temperature_max_c",
        )
    return options


def encode_options(options: IntegrationOptions) -> JsonObject:
    """Encode config-entry options deterministically."""
    return {
        "observation_enabled": options.observation_enabled,
        "temperature_strategy": options.temperature_strategy.value,
        "humidity_strategy": options.humidity_strategy.value,
        "min_valid_temperature_sources": options.min_valid_temperature_sources,
        "min_valid_humidity_sources": options.min_valid_humidity_sources,
        "source_stale_after_seconds": options.source_stale_after_seconds,
        "startup_reconciliation_seconds": options.startup_reconciliation_seconds,
        "jump_limit_c_per_5_minutes": options.jump_limit_c_per_5_minutes,
        "outlier_floor_c": options.outlier_floor_c,
        "indoor_temperature_min_c": options.indoor_temperature_min_c,
        "indoor_temperature_max_c": options.indoor_temperature_max_c,
        "history_max_records": options.history_max_records,
        "history_max_age_days": options.history_max_age_days,
        "log_level_detail": options.log_level_detail.value,
    }


def decode_runtime_store_document(value: object) -> RuntimeStoreDocument:
    """Decode runtime Store schema version 1 data."""
    migrated = migrate_runtime_store_document(value)
    root = _object(migrated, "")
    expected = {
        "schema_version",
        "entry_id",
        "equipment_group_id",
        "saved_at",
        "last_clean_shutdown",
        "zones",
        "source_baselines",
        "decisions",
        "command_journal",
    }
    _reject_unknown(root, expected, "")
    _require_version(
        root.get("schema_version"),
        RUNTIME_STORE_SCHEMA_VERSION,
        "schema_version",
        "runtime Store",
    )
    command_journal = _json_object_tuple(
        root.get("command_journal"),
        "command_journal",
    )
    if command_journal:
        raise SchemaValidationError("command_journal", "must remain empty in Phase 1")

    return RuntimeStoreDocument(
        entry_id=_non_empty_string(root.get("entry_id"), "entry_id"),
        equipment_group_id=_parse_equipment_group_id(
            root.get("equipment_group_id"),
            "equipment_group_id",
        ),
        saved_at=_datetime(root.get("saved_at"), "saved_at"),
        last_clean_shutdown=_bool(
            root.get("last_clean_shutdown"),
            "last_clean_shutdown",
        ),
        zones=_decode_runtime_zones(root.get("zones")),
        source_baselines=_decode_source_baselines(root.get("source_baselines")),
        decisions=_decode_activity_records(root.get("decisions")),
        command_journal=command_journal,
    )


def encode_runtime_store_document(document: RuntimeStoreDocument) -> JsonObject:
    """Encode runtime Store data deterministically."""
    return {
        "schema_version": RUNTIME_STORE_SCHEMA_VERSION,
        "entry_id": document.entry_id,
        "equipment_group_id": str(document.equipment_group_id),
        "saved_at": document.saved_at.isoformat(),
        "last_clean_shutdown": document.last_clean_shutdown,
        "zones": {
            str(zone_id): _encode_runtime_zone_state(state)
            for zone_id, state in sorted(
                document.zones.items(),
                key=lambda item: str(item[0]),
            )
        },
        "source_baselines": {
            str(source_id): _encode_source_baseline(baseline)
            for source_id, baseline in sorted(
                document.source_baselines.items(),
                key=lambda item: str(item[0]),
            )
        },
        "decisions": [
            _encode_activity_record(decision) for decision in document.decisions
        ],
        "command_journal": [
            _encode_json_value(entry) for entry in document.command_journal
        ],
    }


def migrate_config_entry_document(
    value: object,
    *,
    version: int,
    minor_version: int,
) -> object:
    """Validate the supported config-entry version without mutating input."""
    _require_int(version, "version")
    _require_int(minor_version, "minor_version", minimum=0)
    if version > CONFIG_ENTRY_MAJOR_VERSION:
        raise SchemaMigrationError(
            "version",
            "future config-entry version is unsupported",
        )
    if version < CONFIG_ENTRY_MAJOR_VERSION:
        raise SchemaMigrationError(
            "version",
            "no migration path for config-entry version",
        )
    if minor_version > CONFIG_ENTRY_MINOR_VERSION:
        raise SchemaMigrationError(
            "minor_version",
            "future config-entry minor version is unsupported",
        )
    root = _object(value, "")
    return deepcopy(root)


def migrate_zone_document(value: object) -> object:
    """Validate the supported zone data version without mutating input."""
    root = _object(value, "")
    version = root.get("data_version")
    if version is None:
        raise SchemaMigrationError("data_version", "missing required field")
    _require_version(version, ZONE_DATA_VERSION, "data_version", "zone data")
    return deepcopy(root)


def migrate_options_document(
    value: object,
    *,
    version: int = CONFIG_ENTRY_MAJOR_VERSION,
    minor_version: int = CONFIG_ENTRY_MINOR_VERSION,
) -> object:
    """Validate options data without mutating input."""
    _require_int(version, "version")
    _require_int(minor_version, "minor_version", minimum=0)
    if version > CONFIG_ENTRY_MAJOR_VERSION:
        raise SchemaMigrationError(
            "version",
            "future config-entry version is unsupported",
        )
    if version < CONFIG_ENTRY_MAJOR_VERSION:
        raise SchemaMigrationError(
            "version",
            "no migration path for config-entry version",
        )
    if minor_version > CONFIG_ENTRY_MINOR_VERSION:
        raise SchemaMigrationError(
            "minor_version",
            "future config-entry minor version is unsupported",
        )
    root = _object(value, "")
    return deepcopy(root)


def migrate_runtime_store_document(value: object) -> object:
    """Validate the supported runtime Store version without mutating input."""
    root = _object(value, "")
    version = root.get("schema_version")
    if version is None:
        raise SchemaMigrationError("schema_version", "missing required field")
    _require_version(
        version,
        RUNTIME_STORE_SCHEMA_VERSION,
        "schema_version",
        "runtime Store",
    )
    return deepcopy(root)


def _decode_equipment_group(value: object, path: str) -> EquipmentGroupConfig:
    root = _object(value, path)
    expected = {
        "equipment_group_id",
        "name",
        "equipment_type",
        "relationship",
        "thermostats",
        "shared_policy",
    }
    _reject_unknown(root, expected, path)
    thermostats = tuple(
        _decode_thermostat_binding(item, f"{path}.thermostats[{index}]")
        for index, item in enumerate(
            _list(root.get("thermostats"), f"{path}.thermostats")
        )
    )
    thermostat_entity_ids = [thermostat.entity_id for thermostat in thermostats]
    if len(set(thermostat_entity_ids)) != len(thermostat_entity_ids):
        raise SchemaValidationError(
            f"{path}.thermostats",
            "must not contain duplicate entity IDs",
        )

    relationship = _enum(
        EquipmentRelationship,
        root.get("relationship"),
        f"{path}.relationship",
    )
    shared_policy = _decode_shared_policy(
        root.get("shared_policy"),
        f"{path}.shared_policy",
    )
    if relationship is EquipmentRelationship.SHARED_ZONED and shared_policy is None:
        raise SchemaValidationError(
            f"{path}.shared_policy",
            "is required for shared_zoned relationships",
        )
    if (
        relationship is not EquipmentRelationship.SHARED_ZONED
        and shared_policy is not None
    ):
        raise SchemaValidationError(
            f"{path}.shared_policy",
            "must be null unless relationship is shared_zoned",
        )

    return EquipmentGroupConfig(
        equipment_group_id=_parse_equipment_group_id(
            root.get("equipment_group_id"),
            f"{path}.equipment_group_id",
        ),
        name=_name(root.get("name"), f"{path}.name"),
        equipment_type=_enum(
            EquipmentType,
            root.get("equipment_type"),
            f"{path}.equipment_type",
        ),
        relationship=relationship,
        thermostats=thermostats,
        shared_policy=shared_policy,
    )


def _encode_equipment_group(group: EquipmentGroupConfig) -> JsonObject:
    return {
        "equipment_group_id": str(group.equipment_group_id),
        "name": group.name,
        "equipment_type": group.equipment_type.value,
        "relationship": group.relationship.value,
        "thermostats": [
            {"entity_id": thermostat.entity_id, "role": thermostat.role.value}
            for thermostat in group.thermostats
        ],
        "shared_policy": (
            None
            if group.shared_policy is None
            else {
                "zone_priority_order": [
                    str(zone_id) for zone_id in group.shared_policy.zone_priority_order
                ],
                "conflict_policy": group.shared_policy.conflict_policy,
            }
        ),
    }


def _decode_thermostat_binding(value: object, path: str) -> ThermostatBinding:
    root = _object(value, path)
    _reject_unknown(root, {"entity_id", "role"}, path)
    return ThermostatBinding(
        entity_id=_entity_id(root.get("entity_id"), f"{path}.entity_id"),
        role=_enum(ThermostatRole, root.get("role"), f"{path}.role"),
    )


def _decode_shared_policy(value: object, path: str) -> SharedEquipmentPolicy | None:
    if value is None:
        return None
    root = _object(value, path)
    _reject_unknown(root, {"zone_priority_order", "conflict_policy"}, path)
    zone_ids = tuple(
        _parse_zone_id(item, f"{path}.zone_priority_order[{index}]")
        for index, item in enumerate(
            _list(root.get("zone_priority_order"), f"{path}.zone_priority_order")
        )
    )
    if not zone_ids:
        raise SchemaValidationError(f"{path}.zone_priority_order", "must not be empty")
    if len(set(zone_ids)) != len(zone_ids):
        raise SchemaValidationError(
            f"{path}.zone_priority_order",
            "must not contain duplicate zone IDs",
        )
    return SharedEquipmentPolicy(
        zone_priority_order=zone_ids,
        conflict_policy=_name(root.get("conflict_policy"), f"{path}.conflict_policy"),
    )


def _decode_temperature_source(value: object, path: str) -> TemperatureSource:
    root = _object(value, path)
    _reject_unknown_with_optional(
        root,
        {
            "source_id",
            "entity_id",
            "attribute",
            "offset_c",
            "weight",
            "priority",
            "enabled",
        },
        {"enabled"},
        path,
    )
    return TemperatureSource(
        source_id=_parse_source_id(root.get("source_id"), f"{path}.source_id"),
        entity_id=_entity_id(root.get("entity_id"), f"{path}.entity_id"),
        attribute=_optional_name(root.get("attribute"), f"{path}.attribute"),
        offset_c=_finite_float(root.get("offset_c"), f"{path}.offset_c"),
        weight=_positive_float(root.get("weight"), f"{path}.weight"),
        priority=_int(root.get("priority"), f"{path}.priority", minimum=0),
        enabled=_bool(root.get("enabled", True), f"{path}.enabled"),
    )


def _encode_temperature_source(source: TemperatureSource) -> JsonObject:
    return {
        "source_id": str(source.source_id),
        "entity_id": source.entity_id,
        "attribute": source.attribute,
        "offset_c": source.offset_c,
        "weight": source.weight,
        "priority": source.priority,
        "enabled": source.enabled,
    }


def _decode_humidity_source(value: object, path: str) -> HumiditySource:
    root = _object(value, path)
    _reject_unknown_with_optional(
        root,
        {
            "source_id",
            "entity_id",
            "attribute",
            "offset_pct",
            "weight",
            "priority",
            "enabled",
        },
        {"enabled"},
        path,
    )
    return HumiditySource(
        source_id=_parse_source_id(root.get("source_id"), f"{path}.source_id"),
        entity_id=_entity_id(root.get("entity_id"), f"{path}.entity_id"),
        attribute=_optional_name(root.get("attribute"), f"{path}.attribute"),
        offset_pct=_finite_float(root.get("offset_pct"), f"{path}.offset_pct"),
        weight=_positive_float(root.get("weight"), f"{path}.weight"),
        priority=_int(root.get("priority"), f"{path}.priority", minimum=0),
        enabled=_bool(root.get("enabled", True), f"{path}.enabled"),
    )


def _encode_humidity_source(source: HumiditySource) -> JsonObject:
    return {
        "source_id": str(source.source_id),
        "entity_id": source.entity_id,
        "attribute": source.attribute,
        "offset_pct": source.offset_pct,
        "weight": source.weight,
        "priority": source.priority,
        "enabled": source.enabled,
    }


def _validate_zone(zone: ZoneConfig, path: str) -> None:
    prefix = f"{path}." if path else ""
    temperature_source_ids = tuple(
        source.source_id for source in zone.temperature_sources
    )
    if _duplicates(temperature_source_ids):
        raise SchemaValidationError(
            f"{prefix}temperature_sources",
            "duplicate observation source_id",
        )
    humidity_source_ids = tuple(source.source_id for source in zone.humidity_sources)
    if _duplicates(humidity_source_ids):
        raise SchemaValidationError(
            f"{prefix}humidity_sources",
            "duplicate observation source_id",
        )
    if set(temperature_source_ids) & set(humidity_source_ids):
        raise SchemaValidationError(
            f"{prefix}humidity_sources",
            "duplicate observation source_id",
        )

    temperature_bindings = tuple(
        (source.entity_id, source.attribute) for source in zone.temperature_sources
    )
    duplicate_temperature_bindings = _duplicates(temperature_bindings)
    if duplicate_temperature_bindings:
        raise SchemaValidationError(
            f"{prefix}temperature_sources",
            "must not repeat the same entity and attribute in one zone",
        )

    humidity_bindings = tuple(
        (source.entity_id, source.attribute) for source in zone.humidity_sources
    )
    duplicate_humidity_bindings = _duplicates(humidity_bindings)
    if duplicate_humidity_bindings:
        raise SchemaValidationError(
            f"{prefix}humidity_sources",
            "must not repeat the same entity and attribute in one zone",
        )

    duplicate_entity_attributes = _duplicates(
        (*temperature_bindings, *humidity_bindings)
    )
    if duplicate_entity_attributes:
        raise SchemaValidationError(
            f"{prefix}temperature_sources",
            "must not repeat the same entity and attribute in one zone",
        )

    if len(set(zone.thermostat_entity_ids)) != len(zone.thermostat_entity_ids):
        raise SchemaValidationError(
            f"{prefix}thermostat_entity_ids",
            "must not contain duplicates",
        )


def _validate_graph(graph: ConfigurationGraph) -> None:
    if not graph.zones:
        raise SchemaValidationError("zones", "must not be empty")
    if not graph.equipment_group.thermostats:
        raise SchemaValidationError(
            "equipment_group.thermostats",
            "must not be empty",
        )

    zone_ids = [zone.zone_id for zone in graph.zones]
    if len(set(zone_ids)) != len(zone_ids):
        raise SchemaValidationError("zones", "duplicate zone_id")

    group_thermostats = {
        thermostat.entity_id for thermostat in graph.equipment_group.thermostats
    }
    assigned_thermostats: set[str] = set()
    all_source_ids: list[ObservationSourceId] = []
    for zone_index, zone in enumerate(graph.zones):
        zone_path = f"zones[{zone_index}]"
        if not zone.thermostat_entity_ids:
            raise SchemaValidationError(
                f"{zone_path}.thermostat_entity_ids",
                "must not be empty",
            )
        if not zone.temperature_sources:
            raise SchemaValidationError(
                f"{zone_path}.temperature_sources",
                "must not be empty",
            )
        missing = [
            entity_id
            for entity_id in zone.thermostat_entity_ids
            if entity_id not in group_thermostats
        ]
        if missing:
            raise SchemaValidationError(
                f"{zone_path}.thermostat_entity_ids",
                "references thermostat outside equipment group",
            )
        assigned_thermostats.update(zone.thermostat_entity_ids)
        all_source_ids.extend(source.source_id for source in zone.temperature_sources)
        all_source_ids.extend(source.source_id for source in zone.humidity_sources)

    unassigned = group_thermostats - assigned_thermostats
    if unassigned:
        raise SchemaValidationError(
            "equipment_group.thermostats",
            "every thermostat must be assigned to at least one zone",
        )
    if len(set(all_source_ids)) != len(all_source_ids):
        raise SchemaValidationError("zones", "duplicate observation source_id")

    shared_policy = graph.equipment_group.shared_policy
    if shared_policy is not None and set(shared_policy.zone_priority_order) != set(
        zone_ids
    ):
        raise SchemaValidationError(
            "equipment_group.shared_policy.zone_priority_order",
            "must contain every configured zone exactly once",
        )


def _decode_runtime_zones(value: object) -> dict[ZoneId, RuntimeZoneState]:
    root = _object(value, "zones")
    zones: dict[ZoneId, RuntimeZoneState] = {}
    for raw_zone_id, raw_state in root.items():
        zone_id = _parse_zone_id(raw_zone_id, f"zones.{raw_zone_id}")
        zones[zone_id] = _decode_runtime_zone_state(raw_state, f"zones.{raw_zone_id}")
    return zones


def _decode_activity_records(value: object) -> tuple[ActivityRecord, ...]:
    raw_records = _list(value, "decisions")
    if len(raw_records) > 500:
        raise SchemaValidationError("decisions", "must contain at most 500 items")
    records = tuple(
        _decode_activity_record(item, f"decisions[{index}]")
        for index, item in enumerate(raw_records)
    )
    record_ids = tuple(record.record_id for record in records)
    if len(set(record_ids)) != len(record_ids):
        raise SchemaValidationError("decisions", "duplicate activity record_id")
    return tuple(sorted(records, key=lambda item: (item.timestamp, item.record_id.hex)))


def _decode_activity_record(value: object, path: str) -> ActivityRecord:
    root = _object(value, path)
    expected = {
        "record_id",
        "timestamp",
        "equipment_group_id",
        "zone_id",
        "activity_type",
        "reason_code",
        "severity",
        "explanation",
        "detail",
    }
    _reject_unknown(root, expected, path)
    raw_record_id = _non_empty_string(root.get("record_id"), f"{path}.record_id")
    try:
        record_id = UUID(raw_record_id)
    except ValueError as err:
        raise SchemaValidationError(
            f"{path}.record_id",
            "must be a UUID",
        ) from err
    raw_zone_id = root.get("zone_id")
    detail_root = _object(root.get("detail"), f"{path}.detail")
    detail: dict[str, str | int | float | bool | None] = {}
    for key, item in detail_root.items():
        if item is not None and not isinstance(item, str | int | float | bool):
            raise SchemaValidationError(
                f"{path}.detail.{key}",
                "must be a scalar",
            )
        detail[key] = item
    try:
        return ActivityRecord(
            record_id=record_id,
            timestamp=_datetime(root.get("timestamp"), f"{path}.timestamp"),
            equipment_group_id=_parse_equipment_group_id(
                root.get("equipment_group_id"),
                f"{path}.equipment_group_id",
            ),
            zone_id=(
                None
                if raw_zone_id is None
                else _parse_zone_id(raw_zone_id, f"{path}.zone_id")
            ),
            activity_type=_enum(
                ActivityType,
                root.get("activity_type"),
                f"{path}.activity_type",
            ),
            reason_code=_enum(
                ActivityReason,
                root.get("reason_code"),
                f"{path}.reason_code",
            ),
            severity=_enum(
                ActivitySeverity,
                root.get("severity"),
                f"{path}.severity",
            ),
            explanation=_non_empty_string(
                root.get("explanation"),
                f"{path}.explanation",
            ),
            detail=detail,
        )
    except ValueError as err:
        raise SchemaValidationError(path, str(err)) from err


def _encode_activity_record(record: ActivityRecord) -> JsonObject:
    return {
        "record_id": str(record.record_id),
        "timestamp": record.timestamp.isoformat(),
        "equipment_group_id": str(record.equipment_group_id),
        "zone_id": None if record.zone_id is None else str(record.zone_id),
        "activity_type": record.activity_type.value,
        "reason_code": record.reason_code.value,
        "severity": record.severity.value,
        "explanation": record.explanation,
        "detail": dict(record.detail),
    }


def _decode_runtime_zone_state(value: object, path: str) -> RuntimeZoneState:
    root = _object(value, path)
    expected = {
        "last_runtime_state",
        "last_live_observation_at",
        "last_effective_temperature_c",
        "last_effective_humidity_pct",
        "last_decision_id",
    }
    _reject_unknown(root, expected, path)
    return RuntimeZoneState(
        last_runtime_state=_enum(
            ControlState,
            root.get("last_runtime_state"),
            f"{path}.last_runtime_state",
        ),
        last_live_observation_at=_optional_datetime(
            root.get("last_live_observation_at"),
            f"{path}.last_live_observation_at",
        ),
        last_effective_temperature_c=_optional_finite_float(
            root.get("last_effective_temperature_c"),
            f"{path}.last_effective_temperature_c",
        ),
        last_effective_humidity_pct=_optional_percentage(
            root.get("last_effective_humidity_pct"),
            f"{path}.last_effective_humidity_pct",
        ),
        last_decision_id=_optional_string(
            root.get("last_decision_id"),
            f"{path}.last_decision_id",
        ),
    )


def _encode_runtime_zone_state(state: RuntimeZoneState) -> JsonObject:
    return {
        "last_runtime_state": state.last_runtime_state.value,
        "last_live_observation_at": (
            None
            if state.last_live_observation_at is None
            else state.last_live_observation_at.isoformat()
        ),
        "last_effective_temperature_c": state.last_effective_temperature_c,
        "last_effective_humidity_pct": state.last_effective_humidity_pct,
        "last_decision_id": state.last_decision_id,
    }


def _decode_source_baselines(
    value: object,
) -> dict[ObservationSourceId, SourceBaseline]:
    root = _object(value, "source_baselines")
    baselines: dict[ObservationSourceId, SourceBaseline] = {}
    for raw_source_id, raw_baseline in root.items():
        source_id = _parse_source_id(raw_source_id, f"source_baselines.{raw_source_id}")
        baselines[source_id] = _decode_source_baseline(
            raw_baseline,
            f"source_baselines.{raw_source_id}",
        )
    return baselines


def _decode_source_baseline(value: object, path: str) -> SourceBaseline:
    root = _object(value, path)
    _reject_unknown(root, {"last_accepted_value", "last_accepted_at"}, path)
    return SourceBaseline(
        last_accepted_value=_finite_float(
            root.get("last_accepted_value"),
            f"{path}.last_accepted_value",
        ),
        last_accepted_at=_datetime(
            root.get("last_accepted_at"),
            f"{path}.last_accepted_at",
        ),
    )


def _encode_source_baseline(baseline: SourceBaseline) -> JsonObject:
    return {
        "last_accepted_value": baseline.last_accepted_value,
        "last_accepted_at": baseline.last_accepted_at.isoformat(),
    }


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


def _reject_unknown(value: JsonObject, expected: set[str], path: str) -> None:
    _reject_unknown_with_optional(value, expected, set(), path)


def _reject_unknown_with_optional(
    value: JsonObject,
    expected: set[str],
    optional: set[str],
    path: str,
) -> None:
    unknown = sorted(set(value) - expected)
    if unknown:
        field_path = f"{path}.{unknown[0]}" if path else unknown[0]
        raise SchemaValidationError(field_path, "unknown field")
    missing = sorted((expected - optional) - set(value))
    if missing:
        field_path = f"{path}.{missing[0]}" if path else missing[0]
        raise SchemaValidationError(field_path, "missing required field")


def _bool(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(path, "must be a boolean")
    return value


def _int(value: object, path: str, *, minimum: int | None = None) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError(path, "must be an integer")
    if minimum is not None and value < minimum:
        raise SchemaValidationError(path, f"must be at least {minimum}")
    return value


def _positive_int(value: object, path: str) -> int:
    return _int(value, path, minimum=1)


def _require_int(value: object, path: str, *, minimum: int | None = None) -> int:
    return _int(value, path, minimum=minimum)


def _finite_float(value: object, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise SchemaValidationError(path, "must be a finite number")
    numeric = float(value)
    if not isfinite(numeric):
        raise SchemaValidationError(path, "must be finite")
    return numeric


def _optional_finite_float(value: object, path: str) -> float | None:
    if value is None:
        return None
    return _finite_float(value, path)


def _positive_float(value: object, path: str) -> float:
    value_float = _finite_float(value, path)
    if value_float <= 0:
        raise SchemaValidationError(path, "must be greater than zero")
    return value_float


def _optional_percentage(value: object, path: str) -> float | None:
    percentage = _optional_finite_float(value, path)
    if percentage is None:
        return None
    if percentage < 0 or percentage > 100:
        raise SchemaValidationError(path, "must be between 0 and 100")
    return percentage


def _bounded_history_records(value: object, path: str) -> int:
    records = _positive_int(value, path)
    if records > 500:
        raise SchemaValidationError(path, "must be at most 500")
    return records


def _non_empty_string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    if not value.strip():
        raise SchemaValidationError(path, "must not be empty")
    if value != value.strip():
        raise SchemaValidationError(path, "must not have surrounding whitespace")
    return value


def _optional_string(value: object, path: str) -> str | None:
    if value is None:
        return None
    return _non_empty_string(value, path)


def _name(value: object, path: str) -> str:
    text = _non_empty_string(value, path)
    if not text.strip():
        raise SchemaValidationError(path, "must not be empty")
    return text


def _optional_name(value: object, path: str) -> str | None:
    if value is None:
        return None
    return _name(value, path)


def _entity_id(value: object, path: str) -> str:
    text = _non_empty_string(value, path)
    if "." not in text or text.startswith(".") or text.endswith("."):
        raise SchemaValidationError(path, "must be a Home Assistant entity_id")
    return text


def _string_tuple(
    value: object,
    path: str,
    *,
    require_non_empty: bool,
) -> tuple[str, ...]:
    items = _list(value, path)
    if require_non_empty and not items:
        raise SchemaValidationError(path, "must not be empty")
    return tuple(
        _entity_id(item, f"{path}[{index}]") for index, item in enumerate(items)
    )


def _enum(enum_type: type[StrEnum], value: object, path: str) -> Any:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    try:
        return enum_type(value)
    except ValueError as err:
        raise SchemaValidationError(path, "unsupported value") from err


def _parse_equipment_group_id(value: object, path: str) -> EquipmentGroupId:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    try:
        return EquipmentGroupId.parse(value)
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err


def _parse_zone_id(value: object, path: str) -> ZoneId:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    try:
        return ZoneId.parse(value)
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err


def _parse_source_id(value: object, path: str) -> ObservationSourceId:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    try:
        return ObservationSourceId.parse(value)
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err


def _datetime(value: object, path: str) -> datetime:
    text = _non_empty_string(value, path)
    try:
        result = datetime.fromisoformat(text)
    except ValueError as err:
        raise SchemaValidationError(path, "must be an ISO 8601 datetime") from err
    if result.tzinfo is None:
        raise SchemaValidationError(path, "must include timezone information")
    return result


def _optional_datetime(value: object, path: str) -> datetime | None:
    if value is None:
        return None
    return _datetime(value, path)


def _json_object_tuple(
    value: object,
    path: str,
    *,
    max_items: int | None = None,
) -> tuple[JsonObject, ...]:
    items = _list(value, path)
    if max_items is not None and len(items) > max_items:
        raise SchemaValidationError(path, f"must contain at most {max_items} items")
    return tuple(
        _freeze_json_object(item, f"{path}[{index}]")
        for index, item in enumerate(items)
    )


def _freeze_json_object(value: object, path: str) -> JsonObject:
    root = _object(value, path)
    return MappingProxyType(
        {key: _freeze_json_value(item, f"{path}.{key}") for key, item in root.items()}
    )


def _freeze_json_value(value: object, path: str) -> object:
    if isinstance(value, Mapping):
        return _freeze_json_object(value, path)
    if isinstance(value, list):
        return tuple(
            _freeze_json_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, int | float):
        numeric = float(value)
        if not isfinite(numeric):
            raise SchemaValidationError(path, "must be finite")
        return value
    raise SchemaValidationError(path, "must be a JSON-compatible value")


def _encode_json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: _encode_json_value(item)
            for key, item in sorted(value.items(), key=lambda item: item[0])
        }
    if isinstance(value, tuple):
        return [_encode_json_value(item) for item in value]
    return value


def _require_version(
    value: object,
    current: int,
    path: str,
    label: str,
) -> None:
    version = _int(value, path)
    if version > current:
        raise SchemaMigrationError(path, f"future {label} version is unsupported")
    if version < current:
        raise SchemaMigrationError(path, f"no migration path for {label} version")


def _duplicates(values: Iterable[object]) -> set[object]:
    seen: set[object] = set()
    duplicates: set[object] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


_OPTIONS_FIELDS = (
    "observation_enabled",
    "temperature_strategy",
    "humidity_strategy",
    "min_valid_temperature_sources",
    "min_valid_humidity_sources",
    "source_stale_after_seconds",
    "startup_reconciliation_seconds",
    "jump_limit_c_per_5_minutes",
    "outlier_floor_c",
    "indoor_temperature_min_c",
    "indoor_temperature_max_c",
    "history_max_records",
    "history_max_age_days",
    "log_level_detail",
)
