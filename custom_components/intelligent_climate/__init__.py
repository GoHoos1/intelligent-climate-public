"""Set up the Intelligent Climate observe-only runtime."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

from .const import PLATFORMS, SUBENTRY_TYPE_ZONE
from .models import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
    DEFAULT_OPTIONS,
    PHASE2_CONFIG_MAJOR_VERSION,
    PHASE2_CONFIG_MINOR_VERSION,
    EntryRuntimeConfiguration,
    EquipmentGroupDocument,
    EquipmentRelationship,
    ObservationSourceId,
    RuntimeConfigurationState,
    SchemaMigrationError,
    SchemaValidationError,
    SharedEquipmentPolicy,
    ThermostatBinding,
    ThermostatRole,
    ZoneConfig,
    decode_configuration_graph,
    encode_equipment_group_document,
    encode_zone_config,
)
from .schema_compat import (
    decode_active_equipment_group,
    decode_active_observation_options,
    decode_active_zone,
    encode_active_equipment_group,
)
from .type_aliases import IntelligentClimateConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, _config: dict[str, object]) -> bool:
    """Register entry-independent Phase 2 backend API contracts once."""
    from .frontend import async_setup_frontend
    from .websocket import async_register_websocket_api

    async_register_websocket_api(hass)
    await async_setup_frontend(hass)
    return True


def _is_empty_zone_skeleton(zone: ZoneConfig) -> bool:
    """Return whether every Task 4 zone binding collection remains empty."""
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


def _normalize_graph_after_zone_removal(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
) -> None:
    """Keep parent membership and shared metadata aligned after zone removal."""
    group = decode_active_equipment_group(
        entry.data,
        version=entry.version,
        minor_version=entry.minor_version,
    )
    if any(
        subentry.subentry_type != SUBENTRY_TYPE_ZONE
        for subentry in entry.subentries.values()
    ):
        return

    zone_ids = tuple(
        decode_active_zone(subentry.data).zone_id
        for subentry in entry.subentries.values()
    )
    zones = tuple(
        decode_active_zone(subentry.data) for subentry in entry.subentries.values()
    )
    if zones and any(
        not zone.thermostat_entity_ids or not zone.temperature_sources for zone in zones
    ):
        return
    assigned = {entity_id for zone in zones for entity_id in zone.thermostat_entity_ids}
    if zones:
        retained_entity_ids = tuple(
            binding.entity_id
            for binding in group.thermostats
            if binding.entity_id in assigned
        )
        thermostats = tuple(
            ThermostatBinding(
                entity_id=entity_id,
                role=(
                    ThermostatRole.PRIMARY if index == 0 else ThermostatRole.SECONDARY
                ),
            )
            for index, entity_id in enumerate(retained_entity_ids)
        )
    else:
        thermostats = group.thermostats

    relationship = group.relationship
    shared_policy = group.shared_policy
    if zones and len(thermostats) == 1:
        relationship = EquipmentRelationship.SINGLE_SYSTEM
        shared_policy = None
    elif not zone_ids and relationship is EquipmentRelationship.SHARED_ZONED:
        relationship = EquipmentRelationship.INDEPENDENT
        shared_policy = None
    elif relationship is EquipmentRelationship.SHARED_ZONED:
        assert shared_policy is not None
        retained = tuple(
            item for item in shared_policy.zone_priority_order if item in zone_ids
        )
        added = tuple(item for item in zone_ids if item not in retained)
        shared_policy = SharedEquipmentPolicy(
            zone_priority_order=(*retained, *added),
            conflict_policy=shared_policy.conflict_policy,
        )

    updated_group = replace(
        group,
        relationship=relationship,
        thermostats=thermostats,
        shared_policy=shared_policy,
    )
    if updated_group == group:
        return

    hass.config_entries.async_update_entry(
        entry,
        data=encode_active_equipment_group(
            updated_group,
            version=entry.version,
            minor_version=entry.minor_version,
            current_data=entry.data,
            time_zone=hass.config.time_zone,
        ),
    )
    _LOGGER.info(
        "Equipment graph normalized after zone removal: config_entry_id=%s "
        "reason_code=zone_membership_removed",
        entry.entry_id,
    )


def _decode_runtime_configuration(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
) -> EntryRuntimeConfiguration:
    """Decode and validate one complete persisted config-entry hierarchy."""
    from .validation import (
        validate_persisted_temperature_sources,
        validate_persisted_thermostat_reference,
    )

    equipment_group = decode_active_equipment_group(
        entry.data,
        version=entry.version,
        minor_version=entry.minor_version,
    )
    zone_ids: set[str] = set()
    normalized_names: set[str] = set()
    source_ids: set[ObservationSourceId] = set()
    zones: list[ZoneConfig] = []
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            raise SchemaValidationError(
                "subentry_type",
                "unsupported config subentry type",
            )
        zone = decode_active_zone(subentry.data)
        zone_id = str(zone.zone_id)
        if subentry.unique_id != zone_id or subentry.data.get("zone_id") != zone_id:
            raise SchemaValidationError(
                "zone_id",
                "must match the config subentry unique ID",
            )
        if subentry.title != zone.name:
            raise SchemaValidationError(
                "title",
                "must match the encoded zone name",
            )
        normalized_name = zone.name.casefold()
        if zone_id in zone_ids:
            raise SchemaValidationError("zones", "duplicate zone_id")
        if normalized_name in normalized_names:
            raise SchemaValidationError("zones", "duplicate zone name")
        zone_ids.add(zone_id)
        normalized_names.add(normalized_name)
        zones.append(zone)

    options = (
        decode_active_observation_options(
            entry.options,
            version=entry.version,
            minor_version=entry.minor_version,
        )
        if entry.options
        else DEFAULT_OPTIONS
    )

    if not equipment_group.thermostats:
        if any(not _is_empty_zone_skeleton(zone) for zone in zones):
            raise SchemaValidationError(
                "zones",
                "partially bound legacy configuration is not supported",
            )
        return EntryRuntimeConfiguration(
            equipment_group=equipment_group,
            zones=tuple(zones),
            options=options,
            state=RuntimeConfigurationState.TRANSITIONAL_EMPTY_SKELETON,
        )

    if (
        sum(
            binding.role is ThermostatRole.PRIMARY
            for binding in equipment_group.thermostats
        )
        != 1
        or (
            equipment_group.relationship is EquipmentRelationship.SINGLE_SYSTEM
            and len(equipment_group.thermostats) != 1
        )
        or (
            equipment_group.relationship is not EquipmentRelationship.SINGLE_SYSTEM
            and len(equipment_group.thermostats) < 2
        )
    ):
        raise SchemaValidationError(
            "equipment_group.thermostats",
            "invalid parent thermostat",
        )
    thermostat_entity_ids = tuple(
        binding.entity_id for binding in equipment_group.thermostats
    )
    for thermostat_entity_id in thermostat_entity_ids:
        validate_persisted_thermostat_reference(
            hass,
            thermostat_entity_id,
            exclude_entry_id=entry.entry_id,
        )
    if not zones:
        return EntryRuntimeConfiguration(
            equipment_group=equipment_group,
            zones=(),
            options=options,
            state=RuntimeConfigurationState.AWAITING_FIRST_ZONE,
        )

    for zone in zones:
        if not zone.thermostat_entity_ids or not set(
            zone.thermostat_entity_ids
        ).issubset(thermostat_entity_ids):
            raise SchemaValidationError(
                "thermostat_entity_ids",
                "must contain only owning parent thermostats",
            )
        validate_persisted_temperature_sources(zone.temperature_sources)
        for source in zone.temperature_sources:
            if source.source_id in source_ids:
                raise SchemaValidationError(
                    "temperature_sources",
                    "duplicate observation source_id",
                )
            source_ids.add(source.source_id)
        for humidity_source in zone.humidity_sources:
            if humidity_source.source_id in source_ids:
                raise SchemaValidationError(
                    "temperature_sources",
                    "duplicate observation source_id",
                )
            source_ids.add(humidity_source.source_id)
    decode_configuration_graph(
        dict(encode_equipment_group_document(EquipmentGroupDocument(equipment_group))),
        [dict(encode_zone_config(zone)) for zone in zones],
    )
    return EntryRuntimeConfiguration(
        equipment_group=equipment_group,
        zones=tuple(zones),
        options=options,
        state=RuntimeConfigurationState.CONFIGURED,
    )


async def async_migrate_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
) -> bool:
    """Crash-safely migrate one validated config-entry graph to Phase 2."""
    from .migration import Phase2MigrationError, async_migrate_phase1_entry
    from .repairs import MigrationFailureCategory, RepairsManager
    from .validation import EntityValidationError

    issue_manager = RepairsManager(hass, entry.entry_id)
    if (entry.version, entry.minor_version) == (
        PHASE2_CONFIG_MAJOR_VERSION,
        PHASE2_CONFIG_MINOR_VERSION,
    ):
        return True
    if entry.version != CONFIG_ENTRY_MAJOR_VERSION or not (
        0 <= entry.minor_version <= CONFIG_ENTRY_MINOR_VERSION
    ):
        issue_manager.async_report_migration_failure(
            MigrationFailureCategory.SCHEMA_MIGRATION
        )
        return False

    try:
        configuration = _decode_runtime_configuration(hass, entry)
        state = await async_migrate_phase1_entry(
            hass,
            entry,
            configuration,
            repairs=issue_manager,
        )
    except EntityValidationError:
        issue_manager.async_report_migration_failure(
            MigrationFailureCategory.ENTITY_VALIDATION
        )
        return False
    except Phase2MigrationError as err:
        _LOGGER.error(
            "Phase 2 migration failed: config_entry_id=%s "
            "failure_category=%s reason_code=phase2_migration_failed detail=%s",
            entry.entry_id,
            err.category.value,
            err,
        )
        issue_manager.async_report_migration_failure(err.category)
        return False
    except asyncio.CancelledError:
        raise
    except (
        KeyError,
        SchemaMigrationError,
        SchemaValidationError,
        TypeError,
        ValueError,
    ) as err:
        _LOGGER.error(
            "Phase 2 migration candidate validation failed: "
            "config_entry_id=%s reason_code=phase2_schema_validation_failed %s",
            entry.entry_id,
            err,
        )
        issue_manager.async_report_migration_failure(
            MigrationFailureCategory.SCHEMA_VALIDATION
        )
        return False

    if not state.runtime_quarantine_present:
        issue_manager.async_clear_migration_failure()
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
) -> bool:
    """Set up an Intelligent Climate config entry."""
    from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

    from .activity import ActivityPublisher
    from .coordinator import IntelligentClimateCoordinator
    from .frontend import async_register_frontend_entry
    from .history import ActivityHistory
    from .migration import (
        Phase2MigrationError,
        PresentationTraceInitializationStatus,
        async_initialize_presentation_trace,
        async_reconcile_phase2_migration,
    )
    from .presentation_trace import PresentationTraceRuntime
    from .repairs import MigrationFailureCategory, RepairsManager
    from .runtime import Phase2CoordinatorRuntime, build_schedule_validation_context
    from .schedule_storage import ScheduleStore
    from .storage import RuntimeStore, StoreLoadStatus
    from .validation import EntityValidationError

    issue_manager = RepairsManager(hass, entry.entry_id)
    phase2_state = None
    try:
        if (entry.version, entry.minor_version) == (
            PHASE2_CONFIG_MAJOR_VERSION,
            PHASE2_CONFIG_MINOR_VERSION,
        ):
            phase2_state = await async_reconcile_phase2_migration(
                hass,
                entry,
                repairs=issue_manager,
            )
        _normalize_graph_after_zone_removal(hass, entry)
        configuration = _decode_runtime_configuration(hass, entry)
    except Phase2MigrationError as err:
        issue_manager.async_report_migration_failure(err.category)
        raise ConfigEntryError("Invalid Intelligent Climate configuration") from err
    except EntityValidationError as err:
        issue_manager.async_report_migration_failure(
            MigrationFailureCategory.ENTITY_VALIDATION
        )
        _LOGGER.error(
            (
                "Invalid persisted Intelligent Climate entity reference: "
                "config_entry_id=%s validation_code=%s "
                "structural_context=config_entry_hierarchy"
            ),
            entry.entry_id,
            err.code.value,
        )
        raise ConfigEntryError("Invalid Intelligent Climate configuration") from err
    except SchemaMigrationError as err:
        issue_manager.async_report_migration_failure(
            MigrationFailureCategory.SCHEMA_MIGRATION
        )
        _LOGGER.error(
            "Unable to migrate persisted Intelligent Climate configuration: "
            "config_entry_id=%s failure_category=schema_migration",
            entry.entry_id,
        )
        raise ConfigEntryError("Invalid Intelligent Climate configuration") from err
    except SchemaValidationError as err:
        issue_manager.async_report_migration_failure(
            MigrationFailureCategory.SCHEMA_VALIDATION
        )
        _LOGGER.error(
            "Invalid persisted Intelligent Climate schema: config_entry_id=%s %s",
            entry.entry_id,
            err,
        )
        raise ConfigEntryError("Invalid Intelligent Climate configuration") from err
    except (KeyError, ValueError) as err:
        issue_manager.async_report_migration_failure(
            MigrationFailureCategory.SCHEMA_VALIDATION
        )
        raise ConfigEntryError("Invalid Intelligent Climate configuration") from err

    history = ActivityHistory(
        max_records=configuration.options.history_max_records,
        max_age_days=configuration.options.history_max_age_days,
    )
    runtime_store = RuntimeStore(
        hass,
        entry_id=entry.entry_id,
        configuration=configuration,
        history=history,
        repairs=issue_manager,
        phase2_runtime=None if phase2_state is None else phase2_state.runtime,
    )
    await runtime_store.async_load()
    activity = ActivityPublisher(
        hass,
        entry_id=entry.entry_id,
        equipment_group_id=configuration.equipment_group.equipment_group_id,
        history=history,
    )
    issue_manager.set_activity_reporter(activity)
    issue_manager.async_prepare_clean_setup(
        preserve_migration_failure=runtime_store.requires_repair
    )
    issue_manager.async_sync_zone_presence(has_zones=bool(configuration.zones))
    if (failure_category := runtime_store.migration_failure_category) is not None:
        issue_manager.async_report_migration_failure(failure_category)
    coordinator: IntelligentClimateCoordinator | None = None
    phase2_runtime: Phase2CoordinatorRuntime | None = None
    try:
        if phase2_state is not None:
            presentation_status = await async_initialize_presentation_trace(
                hass,
                entry_id=entry.entry_id,
                runtime=phase2_state.runtime,
            )
            if presentation_status in {
                PresentationTraceInitializationStatus.FAILED,
                PresentationTraceInitializationStatus.UNSUPPORTED,
            }:
                issue_manager.async_report_migration_failure(
                    MigrationFailureCategory.STORE_LOAD
                )
            schedule_store = ScheduleStore(
                hass,
                entry_id=entry.entry_id,
                validation_context=build_schedule_validation_context(phase2_state),
            )
            await schedule_store.async_load()
            if configuration.zones:
                presentation_trace = PresentationTraceRuntime(
                    hass,
                    entry_id=entry.entry_id,
                    equipment_group_id=(
                        configuration.equipment_group.equipment_group_id
                    ),
                    zone_ids=tuple(zone.zone_id for zone in configuration.zones),
                )
                await presentation_trace.async_load()
                phase2_runtime = Phase2CoordinatorRuntime(
                    migration=phase2_state,
                    schedule_store=schedule_store,
                    presentation_trace=presentation_trace,
                    started_at_utc=phase2_state.runtime.saved_at,
                )
        coordinator = IntelligentClimateCoordinator(
            hass,
            entry,
            configuration,
            issue_manager=issue_manager,
            history=history,
            activity=activity,
            runtime_store=runtime_store,
            phase2_runtime=phase2_runtime,
            restored_source_baselines=runtime_store.restored_source_baselines,
        )
        runtime_store.attach_runtime(coordinator, activity)
        if runtime_store.load_status is StoreLoadStatus.MIGRATED:
            coordinator.async_record_store_migrated()
        if runtime_store.previous_clean_shutdown is False:
            coordinator.async_record_unclean_shutdown()
        await coordinator.async_start()
    except ConfigEntryNotReady as err:
        if coordinator is not None:
            await coordinator.async_shutdown()
        else:
            await runtime_store.async_shutdown()
            activity.close()
        issue_manager.async_report_migration_failure(
            MigrationFailureCategory.RUNTIME_VALIDATION
        )
        cause = err.__cause__ or err
        raise ConfigEntryError(
            "Invalid Intelligent Climate runtime configuration"
        ) from cause
    except (KeyError, ValueError) as err:
        if coordinator is not None:
            await coordinator.async_shutdown()
        else:
            await runtime_store.async_shutdown()
            activity.close()
        issue_manager.async_report_migration_failure(
            MigrationFailureCategory.RUNTIME_VALIDATION
        )
        raise ConfigEntryError(
            "Invalid Intelligent Climate runtime configuration"
        ) from err
    assert coordinator is not None
    entry.runtime_data = coordinator
    try:
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    except Exception as err:
        await coordinator.async_shutdown()
        object.__delattr__(entry, "runtime_data")
        raise ConfigEntryError(
            "Unable to set up the Intelligent Climate entity platforms"
        ) from err
    try:
        await async_register_frontend_entry(
            hass,
            entry_id=entry.entry_id,
            title=entry.title,
        )
    except Exception as err:
        await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        await coordinator.async_shutdown()
        object.__delattr__(entry, "runtime_data")
        raise ConfigEntryError(
            "Unable to set up the Intelligent Climate frontend"
        ) from err
    coordinator.async_add_core_shutdown_job()
    coordinator.async_record_setup_complete()
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
) -> bool:
    """Unload an Intelligent Climate config entry."""
    coordinator = getattr(entry, "runtime_data", None)
    if coordinator is None:
        return True
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    from .frontend import async_unregister_frontend_entry

    coordinator.async_unregister_core_shutdown_job()
    coordinator.async_record_unload()
    if coordinator.runtime_store is not None:
        await coordinator.runtime_store.async_final_save()
    await coordinator.async_shutdown()
    await async_unregister_frontend_entry(hass, entry_id=entry.entry_id)
    return True
