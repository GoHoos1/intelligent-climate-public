"""Pure Phase 2 target-schema models and migration dry runs.

This module deliberately does not replace the active Phase 1 codecs.  It builds
and validates complete Phase 2 candidates so the multi-document transaction in
Task 8 can commit them only after every candidate is known to be safe.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from types import MappingProxyType
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .control import ControlExecutionState
from .identifiers import EquipmentGroupId, ObservationSourceId, ZoneId
from .modes import OperatingMode
from .schema import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
    ZONE_DATA_VERSION,
    EquipmentGroupConfig,
    EquipmentGroupDocument,
    EquipmentRelationship,
    IntegrationOptions,
    RuntimeStoreDocument,
    SchemaMigrationError,
    SchemaValidationError,
    SourceBaseline,
    ThermostatRole,
    ZoneConfig,
    decode_configuration_graph,
    decode_equipment_group_document,
    decode_options,
    decode_runtime_store_document,
    decode_zone_config,
    encode_equipment_group_document,
    encode_options,
    encode_runtime_store_document,
    encode_zone_config,
)

PHASE2_CONFIG_MAJOR_VERSION = 2
PHASE2_CONFIG_MINOR_VERSION = 0
PHASE2_ZONE_DATA_VERSION = 2
PHASE2_RUNTIME_STORE_ENVELOPE_VERSION = 2
PHASE2_RUNTIME_STORE_ENVELOPE_MINOR_VERSION = 0
PHASE2_RUNTIME_STORE_SCHEMA_VERSION = 2

MAX_COMMAND_JOURNAL_RECORDS = 100
MAX_RUNTIME_RECORDS = 500

type JsonObject = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Phase2BindingCandidate:
    """A migrated binding that cannot act until explicitly reviewed."""

    entity_id: str
    enabled: bool
    reviewed: bool


@dataclass(frozen=True, slots=True)
class Phase2EquipmentGroupDocument:
    """Phase 2 parent config-entry data."""

    equipment_group: EquipmentGroupConfig
    automation_enabled: bool
    desired_operating_mode: OperatingMode
    command_authority_entity_ids: tuple[str, ...]
    authority_review_required: bool
    acknowledged_time_zone: str


@dataclass(frozen=True, slots=True)
class Phase2SafetyLimits:
    """User-visible absolute control limits, stored in Celsius."""

    minimum_heating_target_c: float
    maximum_heating_target_c: float
    minimum_cooling_target_c: float
    maximum_cooling_target_c: float
    minimum_heat_cool_separation_c: float
    emergency_protection_enabled: bool
    emergency_low_threshold_c: float
    emergency_low_target_c: float
    emergency_high_threshold_c: float
    emergency_high_target_c: float


@dataclass(frozen=True, slots=True)
class Phase2CommandTiming:
    """Phase 2 command timing policy in whole seconds."""

    automatic_minimum_interval_seconds: int
    direct_override_minimum_interval_seconds: int
    manual_control_minimum_interval_seconds: int
    mode_reversal_cooldown_seconds: int
    target_deadband_c: float
    acknowledgement_window_seconds: int
    retry_delay_seconds: int
    failure_cooldown_seconds: int
    repeated_failure_count: int
    repeated_failure_window_seconds: int
    startup_quiet_period_seconds: int


@dataclass(frozen=True, slots=True)
class Phase2IntegrationOptions:
    """Phase 2 options with the accepted observation contract embedded."""

    observation: IntegrationOptions
    safety_limits: Phase2SafetyLimits
    command_timing: Phase2CommandTiming


@dataclass(frozen=True, slots=True)
class Phase2ZoneConfig:
    """Phase 2 zone document with review-gated behavior candidates."""

    zone: ZoneConfig
    contact_bindings: tuple[Phase2BindingCandidate, ...]
    occupancy_bindings: tuple[Phase2BindingCandidate, ...]
    fan_bindings: tuple[Phase2BindingCandidate, ...]


@dataclass(frozen=True, slots=True)
class Phase2RuntimeZoneState:
    """Restart-safe Phase 2 runtime state for one zone."""

    control_state: ControlExecutionState
    last_live_observation_at: datetime | None
    comparison_temperature_c: float | None
    comparison_humidity_pct: float | None
    last_decision_id: str | None


@dataclass(frozen=True, slots=True)
class Phase2ControlIntent:
    """Persisted intent that cannot itself authorize a command."""

    automation_enabled: bool
    desired_operating_mode: OperatingMode
    active_control_armed: bool
    time_zone_acknowledgement_required: bool


@dataclass(frozen=True, slots=True)
class Phase2ShadowQualification:
    """Restart-safe empty or accumulated shadow qualification metrics."""

    started_at_utc: datetime | None
    evaluated_decisions: int
    valid_evaluations: int
    material_transitions_by_zone: Mapping[ZoneId, int]
    blocking_fault_codes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Phase2RuntimeStoreDocument:
    """Runtime Store inner schema 2 candidate."""

    entry_id: str
    equipment_group_id: EquipmentGroupId
    saved_at: datetime
    last_clean_shutdown: bool
    zones: Mapping[ZoneId, Phase2RuntimeZoneState]
    source_baselines: Mapping[ObservationSourceId, SourceBaseline]
    decisions: tuple[JsonObject, ...]
    command_journal: tuple[JsonObject, ...]
    overrides: tuple[JsonObject, ...]
    transition_ledger: tuple[JsonObject, ...]
    occupancy_timers: tuple[JsonObject, ...]
    contact_timers: tuple[JsonObject, ...]
    fan_runtime_budget: tuple[JsonObject, ...]
    shadow_qualification: Phase2ShadowQualification
    failure_counters: tuple[JsonObject, ...]
    control_intent: Phase2ControlIntent


@dataclass(frozen=True, slots=True)
class Phase2MigrationDryRun:
    """Validated, side-effect-free Phase 2 migration candidates."""

    config: Phase2EquipmentGroupDocument
    options: Phase2IntegrationOptions
    zones: tuple[Phase2ZoneConfig, ...]
    runtime: Phase2RuntimeStoreDocument


DEFAULT_PHASE2_SAFETY_LIMITS = Phase2SafetyLimits(
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

DEFAULT_PHASE2_COMMAND_TIMING = Phase2CommandTiming(
    automatic_minimum_interval_seconds=300,
    direct_override_minimum_interval_seconds=60,
    manual_control_minimum_interval_seconds=2,
    mode_reversal_cooldown_seconds=900,
    target_deadband_c=0.3,
    acknowledgement_window_seconds=30,
    retry_delay_seconds=30,
    failure_cooldown_seconds=900,
    repeated_failure_count=3,
    repeated_failure_window_seconds=3600,
    startup_quiet_period_seconds=120,
)


def dry_run_phase2_migration(
    *,
    entry_id: str,
    config_data: object,
    config_version: int,
    config_minor_version: int,
    options_data: object,
    zone_data: object,
    runtime_data: object,
    time_zone: str,
    saved_at: datetime,
) -> Phase2MigrationDryRun:
    """Build all authoritative Phase 2 candidates without changing input/state."""
    _non_empty_string(entry_id, "entry_id")
    _aware_datetime(saved_at, "saved_at")
    _time_zone(time_zone, "time_zone")
    if (config_version, config_minor_version) != (
        CONFIG_ENTRY_MAJOR_VERSION,
        CONFIG_ENTRY_MINOR_VERSION,
    ):
        raise SchemaMigrationError(
            "version",
            "dry run requires the accepted config-entry version 1.1",
        )

    phase1_options = decode_options(
        options_data,
        version=config_version,
        minor_version=config_minor_version,
    )
    raw_zones = _list(zone_data, "zones")
    decoded_parent = decode_equipment_group_document(
        config_data,
        version=config_version,
        minor_version=config_minor_version,
    )
    if raw_zones and decoded_parent.equipment_group.thermostats:
        phase1_graph = decode_configuration_graph(config_data, raw_zones)
        phase1_config = EquipmentGroupDocument(
            equipment_group=phase1_graph.equipment_group
        )
        phase1_zones = phase1_graph.zones
    elif raw_zones:
        phase1_config = decoded_parent
        phase1_zones = tuple(decode_zone_config(item) for item in raw_zones)
        if any(not _is_empty_zone_skeleton(zone) for zone in phase1_zones):
            raise SchemaValidationError(
                "zones",
                "partially bound legacy configuration is not supported",
            )
        zone_ids = [zone.zone_id for zone in phase1_zones]
        zone_names = [zone.name.casefold() for zone in phase1_zones]
        if len(set(zone_ids)) != len(zone_ids):
            raise SchemaValidationError("zones", "duplicate zone_id")
        if len(set(zone_names)) != len(zone_names):
            raise SchemaValidationError("zones", "duplicate zone name")
    else:
        phase1_config = decoded_parent
        phase1_zones = ()
    phase1_runtime = decode_runtime_store_document(runtime_data)

    config = _migrate_config(phase1_config, time_zone=time_zone)
    zones = tuple(_migrate_zone(zone) for zone in phase1_zones)
    runtime = _migrate_runtime(
        phase1_runtime,
        entry_id=entry_id,
        config=config,
        zones=zones,
        saved_at=saved_at,
    )
    options = Phase2IntegrationOptions(
        observation=phase1_options,
        safety_limits=DEFAULT_PHASE2_SAFETY_LIMITS,
        command_timing=DEFAULT_PHASE2_COMMAND_TIMING,
    )
    _validate_phase2_options(options)
    return Phase2MigrationDryRun(
        config=config,
        options=options,
        zones=zones,
        runtime=runtime,
    )


def encode_phase2_equipment_group_document(
    document: Phase2EquipmentGroupDocument,
) -> JsonObject:
    """Encode target config-entry data deterministically."""
    _validate_phase2_config(document)
    base = dict(
        encode_equipment_group_document(
            EquipmentGroupDocument(equipment_group=document.equipment_group)
        )
    )
    return {
        **base,
        "automation_enabled": document.automation_enabled,
        "desired_operating_mode": document.desired_operating_mode.value,
        "command_authority_entity_ids": list(document.command_authority_entity_ids),
        "authority_review_required": document.authority_review_required,
        "acknowledged_time_zone": document.acknowledged_time_zone,
    }


def decode_phase2_equipment_group_document(
    value: object,
    *,
    version: int = PHASE2_CONFIG_MAJOR_VERSION,
    minor_version: int = PHASE2_CONFIG_MINOR_VERSION,
) -> Phase2EquipmentGroupDocument:
    """Decode strict Phase 2 config-entry data."""
    _require_phase2_config_version(version, minor_version)
    root = _object(value, "")
    _reject_unknown(
        root,
        {
            "equipment_group",
            "automation_enabled",
            "desired_operating_mode",
            "command_authority_entity_ids",
            "authority_review_required",
            "acknowledged_time_zone",
        },
        "",
    )
    base = decode_equipment_group_document(
        {"equipment_group": root["equipment_group"]},
        version=CONFIG_ENTRY_MAJOR_VERSION,
        minor_version=CONFIG_ENTRY_MINOR_VERSION,
    )
    document = Phase2EquipmentGroupDocument(
        equipment_group=base.equipment_group,
        automation_enabled=_bool(root.get("automation_enabled"), "automation_enabled"),
        desired_operating_mode=_operating_mode(
            root.get("desired_operating_mode"), "desired_operating_mode"
        ),
        command_authority_entity_ids=_entity_id_tuple(
            root.get("command_authority_entity_ids"),
            "command_authority_entity_ids",
        ),
        authority_review_required=_bool(
            root.get("authority_review_required"),
            "authority_review_required",
        ),
        acknowledged_time_zone=_time_zone(
            root.get("acknowledged_time_zone"),
            "acknowledged_time_zone",
        ),
    )
    _validate_phase2_config(document)
    return document


def encode_phase2_options(options: Phase2IntegrationOptions) -> JsonObject:
    """Encode Phase 2 options deterministically."""
    _validate_phase2_options(options)
    return {
        "observation": dict(encode_options(options.observation)),
        "safety_limits": _encode_safety_limits(options.safety_limits),
        "command_timing": _encode_command_timing(options.command_timing),
    }


def decode_phase2_options(
    value: object,
    *,
    version: int = PHASE2_CONFIG_MAJOR_VERSION,
    minor_version: int = PHASE2_CONFIG_MINOR_VERSION,
) -> Phase2IntegrationOptions:
    """Decode strict Phase 2 options."""
    _require_phase2_config_version(version, minor_version)
    root = _object(value, "")
    _reject_unknown(root, {"observation", "safety_limits", "command_timing"}, "")
    options = Phase2IntegrationOptions(
        observation=decode_options(
            root.get("observation"),
            version=CONFIG_ENTRY_MAJOR_VERSION,
            minor_version=CONFIG_ENTRY_MINOR_VERSION,
        ),
        safety_limits=_decode_safety_limits(root.get("safety_limits")),
        command_timing=_decode_command_timing(root.get("command_timing")),
    )
    _validate_phase2_options(options)
    return options


def encode_phase2_zone_config(zone: Phase2ZoneConfig) -> JsonObject:
    """Encode target zone subentry data deterministically."""
    _validate_phase2_zone(zone)
    base = dict(encode_zone_config(zone.zone))
    base["data_version"] = PHASE2_ZONE_DATA_VERSION
    base["window_door_entity_ids"] = [
        _encode_binding(item) for item in zone.contact_bindings
    ]
    base["occupancy_entity_ids"] = [
        _encode_binding(item) for item in zone.occupancy_bindings
    ]
    base["fan_entity_ids"] = [_encode_binding(item) for item in zone.fan_bindings]
    return base


def decode_phase2_zone_config(value: object) -> Phase2ZoneConfig:
    """Decode strict Phase 2 zone data."""
    root = _object(value, "")
    expected = set(encode_zone_config(_empty_zone()).keys())
    _reject_unknown(root, expected, "")
    _require_exact_version(
        root.get("data_version"),
        PHASE2_ZONE_DATA_VERSION,
        "data_version",
        "zone data",
    )
    contacts = _decode_bindings(
        root.get("window_door_entity_ids"), "window_door_entity_ids"
    )
    occupancy = _decode_bindings(
        root.get("occupancy_entity_ids"), "occupancy_entity_ids"
    )
    fans = _decode_bindings(root.get("fan_entity_ids"), "fan_entity_ids")
    phase1_shape = dict(root)
    phase1_shape["data_version"] = ZONE_DATA_VERSION
    phase1_shape["window_door_entity_ids"] = [item.entity_id for item in contacts]
    phase1_shape["occupancy_entity_ids"] = [item.entity_id for item in occupancy]
    phase1_shape["fan_entity_ids"] = [item.entity_id for item in fans]
    zone = Phase2ZoneConfig(
        zone=decode_zone_config(phase1_shape),
        contact_bindings=contacts,
        occupancy_bindings=occupancy,
        fan_bindings=fans,
    )
    _validate_phase2_zone(zone)
    return zone


def encode_phase2_runtime_store_document(
    document: Phase2RuntimeStoreDocument,
) -> JsonObject:
    """Encode runtime Store inner schema 2 deterministically."""
    _validate_phase2_runtime(document)
    return {
        "schema_version": PHASE2_RUNTIME_STORE_SCHEMA_VERSION,
        "entry_id": document.entry_id,
        "equipment_group_id": str(document.equipment_group_id),
        "saved_at": document.saved_at.isoformat(),
        "last_clean_shutdown": document.last_clean_shutdown,
        "zones": {
            str(zone_id): _encode_phase2_runtime_zone(state)
            for zone_id, state in sorted(
                document.zones.items(), key=lambda item: str(item[0])
            )
        },
        "source_baselines": _encode_source_baselines(document.source_baselines),
        "decisions": [_thaw_json(item) for item in document.decisions],
        "command_journal": [_thaw_json(item) for item in document.command_journal],
        "overrides": [_thaw_json(item) for item in document.overrides],
        "transition_ledger": [_thaw_json(item) for item in document.transition_ledger],
        "occupancy_timers": [_thaw_json(item) for item in document.occupancy_timers],
        "contact_timers": [_thaw_json(item) for item in document.contact_timers],
        "fan_runtime_budget": [
            _thaw_json(item) for item in document.fan_runtime_budget
        ],
        "shadow_qualification": _encode_shadow_qualification(
            document.shadow_qualification
        ),
        "failure_counters": [_thaw_json(item) for item in document.failure_counters],
        "control_intent": _encode_control_intent(document.control_intent),
    }


def decode_phase2_runtime_store_document(
    value: object,
) -> Phase2RuntimeStoreDocument:
    """Decode strict runtime Store inner schema 2."""
    root = _object(value, "")
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
        "overrides",
        "transition_ledger",
        "occupancy_timers",
        "contact_timers",
        "fan_runtime_budget",
        "shadow_qualification",
        "failure_counters",
        "control_intent",
    }
    _reject_unknown(root, expected, "")
    _require_exact_version(
        root.get("schema_version"),
        PHASE2_RUNTIME_STORE_SCHEMA_VERSION,
        "schema_version",
        "runtime Store",
    )
    document = Phase2RuntimeStoreDocument(
        entry_id=_non_empty_string(root.get("entry_id"), "entry_id"),
        equipment_group_id=_equipment_group_id(
            root.get("equipment_group_id"), "equipment_group_id"
        ),
        saved_at=_aware_datetime(root.get("saved_at"), "saved_at"),
        last_clean_shutdown=_bool(
            root.get("last_clean_shutdown"), "last_clean_shutdown"
        ),
        zones=_decode_phase2_runtime_zones(root.get("zones")),
        source_baselines=_decode_source_baselines(root.get("source_baselines")),
        decisions=_json_records(
            root.get("decisions"), "decisions", MAX_RUNTIME_RECORDS
        ),
        command_journal=_json_records(
            root.get("command_journal"),
            "command_journal",
            MAX_COMMAND_JOURNAL_RECORDS,
        ),
        overrides=_json_records(
            root.get("overrides"), "overrides", MAX_RUNTIME_RECORDS
        ),
        transition_ledger=_json_records(
            root.get("transition_ledger"),
            "transition_ledger",
            MAX_RUNTIME_RECORDS,
        ),
        occupancy_timers=_json_records(
            root.get("occupancy_timers"),
            "occupancy_timers",
            MAX_RUNTIME_RECORDS,
        ),
        contact_timers=_json_records(
            root.get("contact_timers"),
            "contact_timers",
            MAX_RUNTIME_RECORDS,
        ),
        fan_runtime_budget=_json_records(
            root.get("fan_runtime_budget"),
            "fan_runtime_budget",
            MAX_RUNTIME_RECORDS,
        ),
        shadow_qualification=_decode_shadow_qualification(
            root.get("shadow_qualification")
        ),
        failure_counters=_json_records(
            root.get("failure_counters"),
            "failure_counters",
            MAX_RUNTIME_RECORDS,
        ),
        control_intent=_decode_control_intent(root.get("control_intent")),
    )
    _validate_phase2_runtime(document)
    return document


def _migrate_config(
    document: EquipmentGroupDocument,
    *,
    time_zone: str,
) -> Phase2EquipmentGroupDocument:
    group = document.equipment_group
    if group.relationship is EquipmentRelationship.SHARED_ZONED:
        authorities = tuple(
            binding.entity_id
            for binding in group.thermostats
            if binding.role is ThermostatRole.PRIMARY
        )
        review_required = True
    else:
        authorities = tuple(binding.entity_id for binding in group.thermostats)
        review_required = not authorities
    candidate = Phase2EquipmentGroupDocument(
        equipment_group=group,
        automation_enabled=False,
        desired_operating_mode=OperatingMode.OBSERVE_ONLY,
        command_authority_entity_ids=authorities,
        authority_review_required=review_required,
        acknowledged_time_zone=time_zone,
    )
    _validate_phase2_config(candidate)
    return candidate


def _migrate_zone(zone: ZoneConfig) -> Phase2ZoneConfig:
    candidate = Phase2ZoneConfig(
        zone=zone,
        contact_bindings=tuple(
            Phase2BindingCandidate(entity_id=item, enabled=False, reviewed=False)
            for item in zone.window_door_entity_ids
        ),
        occupancy_bindings=tuple(
            Phase2BindingCandidate(entity_id=item, enabled=False, reviewed=False)
            for item in zone.occupancy_entity_ids
        ),
        fan_bindings=tuple(
            Phase2BindingCandidate(entity_id=item, enabled=False, reviewed=False)
            for item in zone.fan_entity_ids
        ),
    )
    _validate_phase2_zone(candidate)
    return candidate


def _is_empty_zone_skeleton(zone: ZoneConfig) -> bool:
    """Return whether a legacy transitional zone has no usable bindings."""
    return not any(
        (
            zone.thermostat_entity_ids,
            zone.temperature_sources,
            zone.humidity_sources,
            zone.window_door_entity_ids,
            zone.occupancy_entity_ids,
            zone.stage_entity_ids,
            zone.fan_entity_ids,
        )
    )


def _migrate_runtime(
    document: RuntimeStoreDocument,
    *,
    entry_id: str,
    config: Phase2EquipmentGroupDocument,
    zones: tuple[Phase2ZoneConfig, ...],
    saved_at: datetime,
) -> Phase2RuntimeStoreDocument:
    if document.entry_id != entry_id:
        raise SchemaValidationError("runtime.entry_id", "does not match config entry")
    if document.equipment_group_id != config.equipment_group.equipment_group_id:
        raise SchemaValidationError(
            "runtime.equipment_group_id",
            "does not match equipment group",
        )
    configured_zone_ids = {zone.zone.zone_id for zone in zones}
    if set(document.zones) != configured_zone_ids:
        raise SchemaValidationError(
            "runtime.zones",
            "must contain every configured zone exactly once",
        )
    decisions = tuple(
        _freeze_json(item, f"decisions[{index}]")
        for index, item in enumerate(
            encode_runtime_store_document(document)["decisions"]
        )
    )
    candidate = Phase2RuntimeStoreDocument(
        entry_id=entry_id,
        equipment_group_id=document.equipment_group_id,
        saved_at=saved_at,
        last_clean_shutdown=document.last_clean_shutdown,
        zones=MappingProxyType(
            {
                zone_id: Phase2RuntimeZoneState(
                    control_state=ControlExecutionState.RECONCILING,
                    last_live_observation_at=state.last_live_observation_at,
                    comparison_temperature_c=state.last_effective_temperature_c,
                    comparison_humidity_pct=state.last_effective_humidity_pct,
                    last_decision_id=state.last_decision_id,
                )
                for zone_id, state in document.zones.items()
            }
        ),
        source_baselines=MappingProxyType(dict(document.source_baselines)),
        decisions=decisions,
        command_journal=(),
        overrides=(),
        transition_ledger=(),
        occupancy_timers=(),
        contact_timers=(),
        fan_runtime_budget=(),
        shadow_qualification=Phase2ShadowQualification(
            started_at_utc=None,
            evaluated_decisions=0,
            valid_evaluations=0,
            material_transitions_by_zone=MappingProxyType(
                dict.fromkeys(sorted(configured_zone_ids, key=str), 0)
            ),
            blocking_fault_codes=(),
        ),
        failure_counters=(),
        control_intent=Phase2ControlIntent(
            automation_enabled=False,
            desired_operating_mode=OperatingMode.OBSERVE_ONLY,
            active_control_armed=False,
            time_zone_acknowledgement_required=False,
        ),
    )
    _validate_phase2_runtime(candidate)
    return candidate


def _validate_phase2_config(document: Phase2EquipmentGroupDocument) -> None:
    _time_zone(document.acknowledged_time_zone, "acknowledged_time_zone")
    if document.desired_operating_mode is OperatingMode.SCHEDULED_CONTROL:
        if not document.automation_enabled:
            raise SchemaValidationError(
                "desired_operating_mode",
                "scheduled control requires automation_enabled",
            )
        if document.authority_review_required:
            raise SchemaValidationError(
                "authority_review_required",
                "must be false before scheduled control can be desired",
            )
    configured = {binding.entity_id for binding in document.equipment_group.thermostats}
    authorities = document.command_authority_entity_ids
    if len(set(authorities)) != len(authorities):
        raise SchemaValidationError(
            "command_authority_entity_ids", "must not contain duplicates"
        )
    if not set(authorities) <= configured:
        raise SchemaValidationError(
            "command_authority_entity_ids",
            "must reference configured thermostats only",
        )
    if not authorities and not document.authority_review_required:
        raise SchemaValidationError(
            "command_authority_entity_ids",
            "must not be empty unless authority review is required",
        )


def _validate_phase2_options(options: Phase2IntegrationOptions) -> None:
    limits = options.safety_limits
    values = (
        limits.minimum_heating_target_c,
        limits.maximum_heating_target_c,
        limits.minimum_cooling_target_c,
        limits.maximum_cooling_target_c,
        limits.minimum_heat_cool_separation_c,
        limits.emergency_low_threshold_c,
        limits.emergency_low_target_c,
        limits.emergency_high_threshold_c,
        limits.emergency_high_target_c,
    )
    if any(not isfinite(item) for item in values):
        raise SchemaValidationError("safety_limits", "values must be finite")
    if limits.minimum_heating_target_c >= limits.maximum_heating_target_c:
        raise SchemaValidationError(
            "safety_limits.minimum_heating_target_c",
            "must be less than maximum_heating_target_c",
        )
    if limits.minimum_cooling_target_c >= limits.maximum_cooling_target_c:
        raise SchemaValidationError(
            "safety_limits.minimum_cooling_target_c",
            "must be less than maximum_cooling_target_c",
        )
    if limits.minimum_heat_cool_separation_c <= 0:
        raise SchemaValidationError(
            "safety_limits.minimum_heat_cool_separation_c",
            "must be greater than zero",
        )
    if not (
        limits.emergency_low_threshold_c
        < limits.emergency_low_target_c
        < limits.emergency_high_target_c
        < limits.emergency_high_threshold_c
    ):
        raise SchemaValidationError(
            "safety_limits",
            "emergency thresholds and targets must be strictly ordered",
        )
    timing = options.command_timing
    integer_values = (
        timing.automatic_minimum_interval_seconds,
        timing.direct_override_minimum_interval_seconds,
        timing.manual_control_minimum_interval_seconds,
        timing.mode_reversal_cooldown_seconds,
        timing.acknowledgement_window_seconds,
        timing.retry_delay_seconds,
        timing.failure_cooldown_seconds,
        timing.repeated_failure_count,
        timing.repeated_failure_window_seconds,
        timing.startup_quiet_period_seconds,
    )
    if any(
        not isinstance(item, int) or isinstance(item, bool) or item <= 0
        for item in integer_values
    ):
        raise SchemaValidationError("command_timing", "integer values must be positive")
    if not isfinite(timing.target_deadband_c) or timing.target_deadband_c <= 0:
        raise SchemaValidationError(
            "command_timing.target_deadband_c",
            "must be a positive finite number",
        )
    if timing.startup_quiet_period_seconds < 120:
        raise SchemaValidationError(
            "command_timing.startup_quiet_period_seconds",
            "must be at least 120",
        )


def _validate_phase2_zone(zone: Phase2ZoneConfig) -> None:
    groups = (
        (
            zone.contact_bindings,
            zone.zone.window_door_entity_ids,
            "window_door_entity_ids",
        ),
        (
            zone.occupancy_bindings,
            zone.zone.occupancy_entity_ids,
            "occupancy_entity_ids",
        ),
        (zone.fan_bindings, zone.zone.fan_entity_ids, "fan_entity_ids"),
    )
    for bindings, expected, path in groups:
        entity_ids = tuple(item.entity_id for item in bindings)
        if entity_ids != expected:
            raise SchemaValidationError(
                path, "binding candidates must preserve configured entity order"
            )
        if len(set(entity_ids)) != len(entity_ids):
            raise SchemaValidationError(path, "must not contain duplicates")
        for index, binding in enumerate(bindings):
            _entity_id(binding.entity_id, f"{path}[{index}].entity_id")
            if binding.enabled and not binding.reviewed:
                raise SchemaValidationError(
                    f"{path}[{index}].enabled",
                    "cannot be enabled before review",
                )


def _validate_phase2_runtime(document: Phase2RuntimeStoreDocument) -> None:
    _non_empty_string(document.entry_id, "entry_id")
    _aware_datetime(document.saved_at, "saved_at")
    if len(document.decisions) > MAX_RUNTIME_RECORDS:
        raise SchemaValidationError(
            "decisions", f"must contain at most {MAX_RUNTIME_RECORDS} items"
        )
    if len(document.command_journal) > MAX_COMMAND_JOURNAL_RECORDS:
        raise SchemaValidationError(
            "command_journal",
            f"must contain at most {MAX_COMMAND_JOURNAL_RECORDS} items",
        )
    if document.control_intent.active_control_armed and (
        not document.control_intent.automation_enabled
        or document.control_intent.desired_operating_mode
        is not OperatingMode.SCHEDULED_CONTROL
    ):
        raise SchemaValidationError(
            "control_intent.active_control_armed",
            "requires enabled scheduled-control intent",
        )
    qualification = document.shadow_qualification
    if qualification.valid_evaluations > qualification.evaluated_decisions:
        raise SchemaValidationError(
            "shadow_qualification.valid_evaluations",
            "cannot exceed evaluated_decisions",
        )
    if any(
        not isinstance(value, int) or isinstance(value, bool) or value < 0
        for value in (
            qualification.evaluated_decisions,
            qualification.valid_evaluations,
            *qualification.material_transitions_by_zone.values(),
        )
    ):
        raise SchemaValidationError(
            "shadow_qualification", "counts must be nonnegative integers"
        )
    if set(qualification.material_transitions_by_zone) != set(document.zones):
        raise SchemaValidationError(
            "shadow_qualification.material_transitions_by_zone",
            "must contain every runtime zone exactly once",
        )


def _encode_safety_limits(value: Phase2SafetyLimits) -> JsonObject:
    return {
        "minimum_heating_target_c": value.minimum_heating_target_c,
        "maximum_heating_target_c": value.maximum_heating_target_c,
        "minimum_cooling_target_c": value.minimum_cooling_target_c,
        "maximum_cooling_target_c": value.maximum_cooling_target_c,
        "minimum_heat_cool_separation_c": value.minimum_heat_cool_separation_c,
        "emergency_protection_enabled": value.emergency_protection_enabled,
        "emergency_low_threshold_c": value.emergency_low_threshold_c,
        "emergency_low_target_c": value.emergency_low_target_c,
        "emergency_high_threshold_c": value.emergency_high_threshold_c,
        "emergency_high_target_c": value.emergency_high_target_c,
    }


def _decode_safety_limits(value: object) -> Phase2SafetyLimits:
    root = _object(value, "safety_limits")
    expected = set(_encode_safety_limits(DEFAULT_PHASE2_SAFETY_LIMITS))
    _reject_unknown(root, expected, "safety_limits")
    return Phase2SafetyLimits(
        minimum_heating_target_c=_finite(
            root.get("minimum_heating_target_c"),
            "safety_limits.minimum_heating_target_c",
        ),
        maximum_heating_target_c=_finite(
            root.get("maximum_heating_target_c"),
            "safety_limits.maximum_heating_target_c",
        ),
        minimum_cooling_target_c=_finite(
            root.get("minimum_cooling_target_c"),
            "safety_limits.minimum_cooling_target_c",
        ),
        maximum_cooling_target_c=_finite(
            root.get("maximum_cooling_target_c"),
            "safety_limits.maximum_cooling_target_c",
        ),
        minimum_heat_cool_separation_c=_finite(
            root.get("minimum_heat_cool_separation_c"),
            "safety_limits.minimum_heat_cool_separation_c",
        ),
        emergency_protection_enabled=_bool(
            root.get("emergency_protection_enabled"),
            "safety_limits.emergency_protection_enabled",
        ),
        emergency_low_threshold_c=_finite(
            root.get("emergency_low_threshold_c"),
            "safety_limits.emergency_low_threshold_c",
        ),
        emergency_low_target_c=_finite(
            root.get("emergency_low_target_c"),
            "safety_limits.emergency_low_target_c",
        ),
        emergency_high_threshold_c=_finite(
            root.get("emergency_high_threshold_c"),
            "safety_limits.emergency_high_threshold_c",
        ),
        emergency_high_target_c=_finite(
            root.get("emergency_high_target_c"),
            "safety_limits.emergency_high_target_c",
        ),
    )


def _encode_command_timing(value: Phase2CommandTiming) -> JsonObject:
    return {
        "automatic_minimum_interval_seconds": value.automatic_minimum_interval_seconds,
        "direct_override_minimum_interval_seconds": (
            value.direct_override_minimum_interval_seconds
        ),
        "manual_control_minimum_interval_seconds": (
            value.manual_control_minimum_interval_seconds
        ),
        "mode_reversal_cooldown_seconds": value.mode_reversal_cooldown_seconds,
        "target_deadband_c": value.target_deadband_c,
        "acknowledgement_window_seconds": value.acknowledgement_window_seconds,
        "retry_delay_seconds": value.retry_delay_seconds,
        "failure_cooldown_seconds": value.failure_cooldown_seconds,
        "repeated_failure_count": value.repeated_failure_count,
        "repeated_failure_window_seconds": value.repeated_failure_window_seconds,
        "startup_quiet_period_seconds": value.startup_quiet_period_seconds,
    }


def _decode_command_timing(value: object) -> Phase2CommandTiming:
    root = _object(value, "command_timing")
    expected = set(_encode_command_timing(DEFAULT_PHASE2_COMMAND_TIMING))
    _reject_unknown(root, expected, "command_timing")
    return Phase2CommandTiming(
        automatic_minimum_interval_seconds=_positive_int(
            root.get("automatic_minimum_interval_seconds"),
            "command_timing.automatic_minimum_interval_seconds",
        ),
        direct_override_minimum_interval_seconds=_positive_int(
            root.get("direct_override_minimum_interval_seconds"),
            "command_timing.direct_override_minimum_interval_seconds",
        ),
        manual_control_minimum_interval_seconds=_positive_int(
            root.get("manual_control_minimum_interval_seconds"),
            "command_timing.manual_control_minimum_interval_seconds",
        ),
        mode_reversal_cooldown_seconds=_positive_int(
            root.get("mode_reversal_cooldown_seconds"),
            "command_timing.mode_reversal_cooldown_seconds",
        ),
        target_deadband_c=_finite(
            root.get("target_deadband_c"),
            "command_timing.target_deadband_c",
        ),
        acknowledgement_window_seconds=_positive_int(
            root.get("acknowledgement_window_seconds"),
            "command_timing.acknowledgement_window_seconds",
        ),
        retry_delay_seconds=_positive_int(
            root.get("retry_delay_seconds"),
            "command_timing.retry_delay_seconds",
        ),
        failure_cooldown_seconds=_positive_int(
            root.get("failure_cooldown_seconds"),
            "command_timing.failure_cooldown_seconds",
        ),
        repeated_failure_count=_positive_int(
            root.get("repeated_failure_count"),
            "command_timing.repeated_failure_count",
        ),
        repeated_failure_window_seconds=_positive_int(
            root.get("repeated_failure_window_seconds"),
            "command_timing.repeated_failure_window_seconds",
        ),
        startup_quiet_period_seconds=_positive_int(
            root.get("startup_quiet_period_seconds"),
            "command_timing.startup_quiet_period_seconds",
        ),
    )


def _encode_binding(value: Phase2BindingCandidate) -> JsonObject:
    return {
        "entity_id": value.entity_id,
        "enabled": value.enabled,
        "reviewed": value.reviewed,
    }


def _decode_bindings(value: object, path: str) -> tuple[Phase2BindingCandidate, ...]:
    bindings = tuple(
        _decode_binding(item, f"{path}[{index}]")
        for index, item in enumerate(_list(value, path))
    )
    if len({item.entity_id for item in bindings}) != len(bindings):
        raise SchemaValidationError(path, "must not contain duplicate entity IDs")
    return bindings


def _decode_binding(value: object, path: str) -> Phase2BindingCandidate:
    root = _object(value, path)
    _reject_unknown(root, {"entity_id", "enabled", "reviewed"}, path)
    return Phase2BindingCandidate(
        entity_id=_entity_id(root.get("entity_id"), f"{path}.entity_id"),
        enabled=_bool(root.get("enabled"), f"{path}.enabled"),
        reviewed=_bool(root.get("reviewed"), f"{path}.reviewed"),
    )


def _empty_zone() -> ZoneConfig:
    return ZoneConfig(
        zone_id=ZoneId.parse("00000000-0000-4000-8000-000000000000"),
        name="Schema",
        thermostat_entity_ids=(),
        temperature_sources=(),
        humidity_sources=(),
        window_door_entity_ids=(),
        occupancy_entity_ids=(),
        stage_entity_ids=(),
        fan_entity_ids=(),
    )


def _encode_phase2_runtime_zone(value: Phase2RuntimeZoneState) -> JsonObject:
    return {
        "control_state": value.control_state.value,
        "last_live_observation_at": (
            None
            if value.last_live_observation_at is None
            else value.last_live_observation_at.isoformat()
        ),
        "comparison_temperature_c": value.comparison_temperature_c,
        "comparison_humidity_pct": value.comparison_humidity_pct,
        "last_decision_id": value.last_decision_id,
    }


def _decode_phase2_runtime_zones(
    value: object,
) -> Mapping[ZoneId, Phase2RuntimeZoneState]:
    root = _object(value, "zones")
    zones: dict[ZoneId, Phase2RuntimeZoneState] = {}
    for raw_id, raw_state in root.items():
        zone_id = _zone_id(raw_id, f"zones.{raw_id}")
        state = _object(raw_state, f"zones.{raw_id}")
        _reject_unknown(
            state,
            {
                "control_state",
                "last_live_observation_at",
                "comparison_temperature_c",
                "comparison_humidity_pct",
                "last_decision_id",
            },
            f"zones.{raw_id}",
        )
        zones[zone_id] = Phase2RuntimeZoneState(
            control_state=_control_state(
                state.get("control_state"), f"zones.{raw_id}.control_state"
            ),
            last_live_observation_at=_optional_datetime(
                state.get("last_live_observation_at"),
                f"zones.{raw_id}.last_live_observation_at",
            ),
            comparison_temperature_c=_optional_finite(
                state.get("comparison_temperature_c"),
                f"zones.{raw_id}.comparison_temperature_c",
            ),
            comparison_humidity_pct=_optional_percentage(
                state.get("comparison_humidity_pct"),
                f"zones.{raw_id}.comparison_humidity_pct",
            ),
            last_decision_id=_optional_string(
                state.get("last_decision_id"),
                f"zones.{raw_id}.last_decision_id",
            ),
        )
    return MappingProxyType(zones)


def _encode_source_baselines(
    baselines: Mapping[ObservationSourceId, SourceBaseline],
) -> JsonObject:
    return {
        str(source_id): {
            "last_accepted_value": baseline.last_accepted_value,
            "last_accepted_at": baseline.last_accepted_at.isoformat(),
        }
        for source_id, baseline in sorted(
            baselines.items(), key=lambda item: str(item[0])
        )
    }


def _decode_source_baselines(
    value: object,
) -> Mapping[ObservationSourceId, SourceBaseline]:
    root = _object(value, "source_baselines")
    baselines: dict[ObservationSourceId, SourceBaseline] = {}
    for raw_id, raw_baseline in root.items():
        source_id = _source_id(raw_id, f"source_baselines.{raw_id}")
        baseline = _object(raw_baseline, f"source_baselines.{raw_id}")
        _reject_unknown(
            baseline,
            {"last_accepted_value", "last_accepted_at"},
            f"source_baselines.{raw_id}",
        )
        baselines[source_id] = SourceBaseline(
            last_accepted_value=_finite(
                baseline.get("last_accepted_value"),
                f"source_baselines.{raw_id}.last_accepted_value",
            ),
            last_accepted_at=_aware_datetime(
                baseline.get("last_accepted_at"),
                f"source_baselines.{raw_id}.last_accepted_at",
            ),
        )
    return MappingProxyType(baselines)


def _encode_shadow_qualification(value: Phase2ShadowQualification) -> JsonObject:
    return {
        "started_at_utc": (
            None if value.started_at_utc is None else value.started_at_utc.isoformat()
        ),
        "evaluated_decisions": value.evaluated_decisions,
        "valid_evaluations": value.valid_evaluations,
        "material_transitions_by_zone": {
            str(zone_id): count
            for zone_id, count in sorted(
                value.material_transitions_by_zone.items(),
                key=lambda item: str(item[0]),
            )
        },
        "blocking_fault_codes": list(value.blocking_fault_codes),
    }


def _decode_shadow_qualification(value: object) -> Phase2ShadowQualification:
    root = _object(value, "shadow_qualification")
    _reject_unknown(
        root,
        {
            "started_at_utc",
            "evaluated_decisions",
            "valid_evaluations",
            "material_transitions_by_zone",
            "blocking_fault_codes",
        },
        "shadow_qualification",
    )
    raw_transitions = _object(
        root.get("material_transitions_by_zone"),
        "shadow_qualification.material_transitions_by_zone",
    )
    transitions = MappingProxyType(
        {
            _zone_id(
                key,
                f"shadow_qualification.material_transitions_by_zone.{key}",
            ): _nonnegative_int(
                item,
                f"shadow_qualification.material_transitions_by_zone.{key}",
            )
            for key, item in raw_transitions.items()
        }
    )
    return Phase2ShadowQualification(
        started_at_utc=_optional_datetime(
            root.get("started_at_utc"),
            "shadow_qualification.started_at_utc",
        ),
        evaluated_decisions=_nonnegative_int(
            root.get("evaluated_decisions"),
            "shadow_qualification.evaluated_decisions",
        ),
        valid_evaluations=_nonnegative_int(
            root.get("valid_evaluations"),
            "shadow_qualification.valid_evaluations",
        ),
        material_transitions_by_zone=transitions,
        blocking_fault_codes=_plain_string_tuple(
            root.get("blocking_fault_codes"),
            "shadow_qualification.blocking_fault_codes",
        ),
    )


def _encode_control_intent(value: Phase2ControlIntent) -> JsonObject:
    return {
        "automation_enabled": value.automation_enabled,
        "desired_operating_mode": value.desired_operating_mode.value,
        "active_control_armed": value.active_control_armed,
        "time_zone_acknowledgement_required": (
            value.time_zone_acknowledgement_required
        ),
    }


def _decode_control_intent(value: object) -> Phase2ControlIntent:
    root = _object(value, "control_intent")
    _reject_unknown(
        root,
        {
            "automation_enabled",
            "desired_operating_mode",
            "active_control_armed",
            "time_zone_acknowledgement_required",
        },
        "control_intent",
    )
    return Phase2ControlIntent(
        automation_enabled=_bool(
            root.get("automation_enabled"),
            "control_intent.automation_enabled",
        ),
        desired_operating_mode=_operating_mode(
            root.get("desired_operating_mode"),
            "control_intent.desired_operating_mode",
        ),
        active_control_armed=_bool(
            root.get("active_control_armed"),
            "control_intent.active_control_armed",
        ),
        time_zone_acknowledgement_required=_bool(
            root.get("time_zone_acknowledgement_required"),
            "control_intent.time_zone_acknowledgement_required",
        ),
    )


def _require_phase2_config_version(version: int, minor_version: int) -> None:
    if not isinstance(version, int) or isinstance(version, bool):
        raise SchemaValidationError("version", "must be an integer")
    if not isinstance(minor_version, int) or isinstance(minor_version, bool):
        raise SchemaValidationError("minor_version", "must be an integer")
    if version != PHASE2_CONFIG_MAJOR_VERSION:
        relation = (
            "future"
            if version > PHASE2_CONFIG_MAJOR_VERSION
            else "no migration path for"
        )
        raise SchemaMigrationError(
            "version", f"{relation} config-entry version is unsupported"
        )
    if minor_version != PHASE2_CONFIG_MINOR_VERSION:
        relation = (
            "future"
            if minor_version > PHASE2_CONFIG_MINOR_VERSION
            else "no migration path for"
        )
        raise SchemaMigrationError(
            "minor_version",
            f"{relation} config-entry minor version is unsupported",
        )


def _require_exact_version(
    value: object,
    current: int,
    path: str,
    label: str,
) -> None:
    version = _nonnegative_int(value, path)
    if version > current:
        raise SchemaMigrationError(path, f"future {label} version is unsupported")
    if version < current:
        raise SchemaMigrationError(path, f"no migration path for {label} version")


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


def _bool(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(path, "must be a boolean")
    return value


def _nonnegative_int(value: object, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError(path, "must be an integer")
    if value < 0:
        raise SchemaValidationError(path, "must be nonnegative")
    return value


def _positive_int(value: object, path: str) -> int:
    number = _nonnegative_int(value, path)
    if number == 0:
        raise SchemaValidationError(path, "must be greater than zero")
    return number


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


def _non_empty_string(value: object, path: str) -> str:
    if not isinstance(value, str):
        raise SchemaValidationError(path, "must be a string")
    if not value or value != value.strip():
        raise SchemaValidationError(
            path, "must be nonempty without surrounding whitespace"
        )
    return value


def _optional_string(value: object, path: str) -> str | None:
    return None if value is None else _non_empty_string(value, path)


def _entity_id(value: object, path: str) -> str:
    entity_id = _non_empty_string(value, path)
    if "." not in entity_id or entity_id.startswith(".") or entity_id.endswith("."):
        raise SchemaValidationError(path, "must be a Home Assistant entity_id")
    return entity_id


def _entity_id_tuple(value: object, path: str) -> tuple[str, ...]:
    return tuple(
        _entity_id(item, f"{path}[{index}]")
        for index, item in enumerate(_list(value, path))
    )


def _plain_string_tuple(value: object, path: str) -> tuple[str, ...]:
    return tuple(
        _non_empty_string(item, f"{path}[{index}]")
        for index, item in enumerate(_list(value, path))
    )


def _time_zone(value: object, path: str) -> str:
    name = _non_empty_string(value, path)
    try:
        ZoneInfo(name)
    except ZoneInfoNotFoundError as err:
        raise SchemaValidationError(path, "must be an IANA time zone") from err
    return name


def _aware_datetime(value: object, path: str) -> datetime:
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
    return result


def _optional_datetime(value: object, path: str) -> datetime | None:
    return None if value is None else _aware_datetime(value, path)


def _operating_mode(value: object, path: str) -> OperatingMode:
    text = _non_empty_string(value, path)
    try:
        return OperatingMode(text)
    except ValueError as err:
        raise SchemaValidationError(path, "unsupported value") from err


def _control_state(value: object, path: str) -> ControlExecutionState:
    text = _non_empty_string(value, path)
    try:
        return ControlExecutionState(text)
    except ValueError as err:
        raise SchemaValidationError(path, "unsupported value") from err


def _equipment_group_id(value: object, path: str) -> EquipmentGroupId:
    text = _non_empty_string(value, path)
    try:
        return EquipmentGroupId.parse(text)
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err


def _zone_id(value: object, path: str) -> ZoneId:
    text = _non_empty_string(value, path)
    try:
        return ZoneId.parse(text)
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err


def _source_id(value: object, path: str) -> ObservationSourceId:
    text = _non_empty_string(value, path)
    try:
        return ObservationSourceId.parse(text)
    except ValueError as err:
        raise SchemaValidationError(path, "must be a valid UUID") from err


def _json_records(value: object, path: str, maximum: int) -> tuple[JsonObject, ...]:
    items = _list(value, path)
    if len(items) > maximum:
        raise SchemaValidationError(path, f"must contain at most {maximum} items")
    return tuple(
        _freeze_json(item, f"{path}[{index}]") for index, item in enumerate(items)
    )


def _freeze_json(value: object, path: str) -> JsonObject:
    root = _object(value, path)
    return MappingProxyType(
        {key: _freeze_json_value(item, f"{path}.{key}") for key, item in root.items()}
    )


def _freeze_json_value(value: object, path: str) -> object:
    if isinstance(value, Mapping):
        return _freeze_json(value, path)
    if isinstance(value, list):
        return tuple(
            _freeze_json_value(item, f"{path}[{index}]")
            for index, item in enumerate(value)
        )
    if value is None or isinstance(value, str | bool):
        return value
    if isinstance(value, int | float):
        _finite(value, path)
        return value
    raise SchemaValidationError(path, "must be JSON-compatible")


def _thaw_json(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            key: _thaw_json(item)
            for key, item in sorted(value.items(), key=lambda item: item[0])
        }
    if isinstance(value, tuple):
        return [_thaw_json(item) for item in value]
    return value
