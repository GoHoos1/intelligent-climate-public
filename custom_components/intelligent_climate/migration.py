"""Crash-safe Phase 1 to Phase 2 persistence migration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any, cast

from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import UnsupportedStorageVersionError
from homeassistant.helpers.storage import Store
from homeassistant.util.dt import utcnow

from .const import SUBENTRY_TYPE_ZONE
from .models import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
    PHASE2_CONFIG_MAJOR_VERSION,
    PHASE2_CONFIG_MINOR_VERSION,
    PHASE2_RUNTIME_STORE_ENVELOPE_MINOR_VERSION,
    PHASE2_RUNTIME_STORE_ENVELOPE_VERSION,
    PHASE2_ZONE_DATA_VERSION,
    PRESENTATION_TRACE_STORE_MINOR_VERSION,
    PRESENTATION_TRACE_STORE_VERSION,
    ControlExecutionState,
    ControlState,
    EntryRuntimeConfiguration,
    EquipmentGroupDocument,
    IntegrationOptions,
    Phase2EquipmentGroupDocument,
    Phase2IntegrationOptions,
    Phase2MigrationDryRun,
    Phase2RuntimeStoreDocument,
    Phase2RuntimeZoneState,
    Phase2ZoneConfig,
    RuntimeStoreDocument,
    RuntimeZoneState,
    SchemaMigrationError,
    SchemaValidationError,
    ZoneConfig,
    decode_configuration_graph,
    decode_phase2_equipment_group_document,
    decode_phase2_options,
    decode_phase2_runtime_store_document,
    decode_phase2_zone_config,
    decode_presentation_trace_document,
    decode_runtime_store_document,
    dry_run_phase2_migration,
    empty_presentation_trace,
    encode_equipment_group_document,
    encode_options,
    encode_phase2_equipment_group_document,
    encode_phase2_options,
    encode_phase2_runtime_store_document,
    encode_phase2_zone_config,
    encode_presentation_trace_document,
    encode_zone_config,
)
from .repairs import MigrationFailureCategory, RepairsManager
from .schema_compat import migrate_zone_document
from .type_aliases import IntelligentClimateConfigEntry

_LOGGER = logging.getLogger(__name__)

_RUNTIME_KEY_PREFIX = "intelligent_climate."
_SCHEDULE_KEY_PREFIX = "intelligent_climate.schedule."
_PRESENTATION_KEY_PREFIX = "intelligent_climate.presentation."
_QUARANTINE_SUFFIX = ".quarantine"

type NowFunction = Callable[[], datetime]


class Phase2MigrationError(RuntimeError):
    """Bounded migration failure with a user-safe Repairs category."""

    def __init__(
        self,
        category: MigrationFailureCategory,
        message: str,
    ) -> None:
        self.category = category
        super().__init__(message)


class PresentationTraceInitializationStatus(StrEnum):
    """Non-authoritative presentation Store initialization result."""

    SKIPPED_NO_ZONES = "skipped_no_zones"
    CREATED = "created"
    LOADED = "loaded"
    RECOVERED = "recovered"
    UNSUPPORTED = "unsupported"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class Phase2MigrationState:
    """Validated canonical state required before coordinator construction."""

    config: Phase2EquipmentGroupDocument
    options: Phase2IntegrationOptions
    zones: tuple[Phase2ZoneConfig, ...]
    runtime: Phase2RuntimeStoreDocument
    runtime_quarantine_present: bool


class _LegacyRuntimeEnvelopeError(Exception):
    """Carry an older runtime envelope without mutating or saving it."""

    def __init__(
        self,
        *,
        major_version: int,
        minor_version: int,
        data: object,
    ) -> None:
        self.major_version = major_version
        self.minor_version = minor_version
        self.data = data
        super().__init__("legacy runtime Store envelope")


class _Phase2RuntimeDataStore(Store[dict[str, Any]]):
    """Exact Phase 2 Store reader that exposes legacy data without migrating."""

    def __init__(self, hass: HomeAssistant, key: str) -> None:
        super().__init__(
            hass,
            PHASE2_RUNTIME_STORE_ENVELOPE_VERSION,
            key,
            atomic_writes=True,
            max_readable_version=PHASE2_RUNTIME_STORE_ENVELOPE_VERSION,
            minor_version=PHASE2_RUNTIME_STORE_ENVELOPE_MINOR_VERSION,
        )

    async def _async_migrate_func(
        self,
        old_major_version: int,
        old_minor_version: int,
        old_data: object,
    ) -> dict[str, Any]:
        raise _LegacyRuntimeEnvelopeError(
            major_version=old_major_version,
            minor_version=old_minor_version,
            data=old_data,
        )


class _PresentationTraceDataStore(Store[dict[str, Any]]):
    """Exact auxiliary Presentation Trace Store v1."""

    def __init__(self, hass: HomeAssistant, key: str) -> None:
        super().__init__(
            hass,
            PRESENTATION_TRACE_STORE_VERSION,
            key,
            atomic_writes=True,
            max_readable_version=PRESENTATION_TRACE_STORE_VERSION,
            minor_version=PRESENTATION_TRACE_STORE_MINOR_VERSION,
        )


async def async_migrate_phase1_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
    configuration: EntryRuntimeConfiguration,
    *,
    repairs: RepairsManager,
    now_fn: NowFunction = utcnow,
) -> Phase2MigrationState:
    """Commit the complete accepted Phase 1 graph as safe Phase 2 documents."""
    saved_at = _now(now_fn)
    runtime_raw, runtime_quarantined = await _async_phase1_runtime_source(
        hass,
        entry=entry,
        configuration=configuration,
        repairs=repairs,
        saved_at=saved_at,
    )
    await _async_require_absent_schedule_store(hass, entry.entry_id)
    candidates = dry_run_phase2_migration(
        entry_id=entry.entry_id,
        config_data=dict(
            encode_equipment_group_document(
                EquipmentGroupDocument(configuration.equipment_group)
            )
        ),
        config_version=CONFIG_ENTRY_MAJOR_VERSION,
        config_minor_version=CONFIG_ENTRY_MINOR_VERSION,
        options_data=dict(encode_options(configuration.options)),
        zone_data=[dict(encode_zone_config(zone)) for zone in configuration.zones],
        runtime_data=runtime_raw,
        time_zone=hass.config.time_zone,
        saved_at=saved_at,
    )
    encoded = _encode_and_verify_candidates(candidates)

    hass.config_entries.async_update_entry(
        entry,
        data=encoded.config,
        options=encoded.options,
        version=PHASE2_CONFIG_MAJOR_VERSION,
        minor_version=PHASE2_CONFIG_MINOR_VERSION,
    )
    zones_by_id = {str(zone.zone.zone_id): zone for zone in candidates.zones}
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            raise Phase2MigrationError(
                MigrationFailureCategory.SCHEMA_VALIDATION,
                "unsupported config subentry type",
            )
        candidate = (
            None if subentry.unique_id is None else zones_by_id.get(subentry.unique_id)
        )
        if candidate is None:
            raise Phase2MigrationError(
                MigrationFailureCategory.SCHEMA_VALIDATION,
                "zone identity changed during migration",
            )
        updated = hass.config_entries.async_update_subentry(
            entry,
            subentry,
            data=dict(encode_phase2_zone_config(candidate)),
        )
        if not updated:
            raise Phase2MigrationError(
                MigrationFailureCategory.SCHEMA_MIGRATION,
                "Home Assistant rejected a zone migration update",
            )

    runtime = await _async_save_phase2_runtime(
        hass,
        entry_id=entry.entry_id,
        encoded=encoded.runtime,
        expected_group_id=str(candidates.config.equipment_group.equipment_group_id),
        expected_zone_ids=frozenset(zones_by_id),
    )
    return Phase2MigrationState(
        config=candidates.config,
        options=candidates.options,
        zones=candidates.zones,
        runtime=runtime,
        runtime_quarantine_present=runtime_quarantined,
    )


async def async_reconcile_phase2_migration(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
    *,
    repairs: RepairsManager,
    now_fn: NowFunction = utcnow,
) -> Phase2MigrationState:
    """Finish or verify an interrupted migration before runtime construction."""
    if (entry.version, entry.minor_version) != (
        PHASE2_CONFIG_MAJOR_VERSION,
        PHASE2_CONFIG_MINOR_VERSION,
    ):
        raise Phase2MigrationError(
            MigrationFailureCategory.SCHEMA_MIGRATION,
            "entry is not at the Phase 2 config version",
        )
    try:
        config = decode_phase2_equipment_group_document(
            entry.data,
            version=entry.version,
            minor_version=entry.minor_version,
        )
        options = decode_phase2_options(
            entry.options,
            version=entry.version,
            minor_version=entry.minor_version,
        )
        _require_migration_safe_config(config)
        zones = tuple(
            migrate_zone_document(subentry.data)
            for subentry in entry.subentries.values()
            if subentry.subentry_type == SUBENTRY_TYPE_ZONE
        )
        if len(zones) != len(entry.subentries):
            raise SchemaValidationError(
                "subentry_type", "unsupported config subentry type"
            )
        _validate_phase2_graph(config, zones)
    except (
        KeyError,
        SchemaMigrationError,
        SchemaValidationError,
        TypeError,
        ValueError,
    ) as err:
        raise Phase2MigrationError(
            MigrationFailureCategory.SCHEMA_VALIDATION,
            "Phase 2 configuration is invalid",
        ) from err

    zones_by_id = {str(zone.zone.zone_id): zone for zone in zones}
    for subentry in entry.subentries.values():
        candidate = (
            None if subentry.unique_id is None else zones_by_id.get(subentry.unique_id)
        )
        if candidate is None:
            raise Phase2MigrationError(
                MigrationFailureCategory.SCHEMA_VALIDATION,
                "zone identity does not match its subentry",
            )
        if not (
            isinstance(subentry.data, Mapping)
            and subentry.data.get("data_version") == PHASE2_ZONE_DATA_VERSION
        ):
            updated = hass.config_entries.async_update_subentry(
                entry,
                subentry,
                data=dict(encode_phase2_zone_config(candidate)),
            )
            if not updated:
                raise Phase2MigrationError(
                    MigrationFailureCategory.SCHEMA_MIGRATION,
                    "Home Assistant rejected interrupted zone recovery",
                )

    saved_at = _now(now_fn)
    runtime, quarantined = await _async_load_or_create_phase2_runtime(
        hass,
        entry_id=entry.entry_id,
        config=config,
        options_data=options.observation,
        zones=zones,
        repairs=repairs,
        saved_at=saved_at,
    )
    runtime = await _async_reconcile_runtime_configuration(
        hass,
        runtime=runtime,
        entry_id=entry.entry_id,
        config=config,
        zones=zones,
        saved_at=saved_at,
    )
    _validate_runtime_identity(
        runtime,
        entry_id=entry.entry_id,
        group_id=str(config.equipment_group.equipment_group_id),
        zone_ids=frozenset(zones_by_id),
        source_ids=frozenset(
            {
                str(source.source_id)
                for zone in zones
                for source in zone.zone.temperature_sources
            }
            | {
                str(source.source_id)
                for zone in zones
                for source in zone.zone.humidity_sources
            }
        ),
    )
    return Phase2MigrationState(
        config=config,
        options=options,
        zones=zones,
        runtime=runtime,
        runtime_quarantine_present=quarantined,
    )


async def _async_reconcile_runtime_configuration(
    hass: HomeAssistant,
    *,
    runtime: Phase2RuntimeStoreDocument,
    entry_id: str,
    config: Phase2EquipmentGroupDocument,
    zones: tuple[Phase2ZoneConfig, ...],
    saved_at: datetime,
) -> Phase2RuntimeStoreDocument:
    """Align safe observation-only runtime identities after zone configuration."""
    zone_ids = tuple(sorted((zone.zone.zone_id for zone in zones), key=str))
    zone_id_set = frozenset(zone_ids)
    source_ids = frozenset(
        {source.source_id for zone in zones for source in zone.zone.temperature_sources}
        | {source.source_id for zone in zones for source in zone.zone.humidity_sources}
    )
    runtime_zones = MappingProxyType(
        {
            zone_id: runtime.zones.get(
                zone_id,
                Phase2RuntimeZoneState(
                    control_state=ControlExecutionState.RECONCILING,
                    last_live_observation_at=None,
                    comparison_temperature_c=None,
                    comparison_humidity_pct=None,
                    last_decision_id=None,
                ),
            )
            for zone_id in zone_ids
        }
    )
    baselines = MappingProxyType(
        {
            source_id: baseline
            for source_id, baseline in runtime.source_baselines.items()
            if source_id in source_ids
        }
    )
    decisions = tuple(
        record
        for record in runtime.decisions
        if record.get("equipment_group_id")
        == str(config.equipment_group.equipment_group_id)
        and (
            record.get("zone_id") is None
            or record.get("zone_id") in {str(zone_id) for zone_id in zone_id_set}
        )
    )
    qualification = replace(
        runtime.shadow_qualification,
        material_transitions_by_zone=MappingProxyType(
            {
                zone_id: runtime.shadow_qualification.material_transitions_by_zone.get(
                    zone_id,
                    0,
                )
                for zone_id in zone_ids
            }
        ),
    )
    candidate = replace(
        runtime,
        zones=runtime_zones,
        source_baselines=baselines,
        decisions=decisions,
        shadow_qualification=qualification,
    )
    if candidate == runtime:
        return runtime
    candidate = replace(candidate, saved_at=saved_at)
    return await _async_save_phase2_runtime(
        hass,
        entry_id=entry_id,
        encoded=dict(encode_phase2_runtime_store_document(candidate)),
        expected_group_id=str(config.equipment_group.equipment_group_id),
        expected_zone_ids=frozenset(str(zone_id) for zone_id in zone_ids),
    )


async def async_initialize_presentation_trace(
    hass: HomeAssistant,
    *,
    entry_id: str,
    runtime: Phase2RuntimeStoreDocument,
    now_fn: NowFunction = utcnow,
) -> PresentationTraceInitializationStatus:
    """Load or create the isolated empty presentation trace after reconciliation."""
    zone_ids = tuple(sorted(runtime.zones, key=str))
    if not zone_ids:
        return PresentationTraceInitializationStatus.SKIPPED_NO_ZONES
    key = f"{_PRESENTATION_KEY_PREFIX}{entry_id}"
    store = _PresentationTraceDataStore(hass, key)
    raw: object | None = None
    expected_zone_ids = frozenset(zone_ids)
    try:
        raw = await store.async_load()
        if raw is not None:
            decode_presentation_trace_document(
                raw,
                expected_entry_id=entry_id,
                expected_equipment_group_id=runtime.equipment_group_id,
                expected_zone_ids=expected_zone_ids,
            )
            return PresentationTraceInitializationStatus.LOADED
    except asyncio.CancelledError:
        raise
    except UnsupportedStorageVersionError:
        return PresentationTraceInitializationStatus.UNSUPPORTED
    except (
        KeyError,
        SchemaMigrationError,
        SchemaValidationError,
        TypeError,
        ValueError,
    ):
        if raw is None or not await _async_quarantine(
            hass,
            key=key,
            envelope_version=PRESENTATION_TRACE_STORE_VERSION,
            raw=raw,
            reason_code="invalid_presentation_trace_store",
            remove_primary=store,
            now=_now(now_fn),
        ):
            return PresentationTraceInitializationStatus.FAILED
        status = PresentationTraceInitializationStatus.RECOVERED
    except Exception:
        return PresentationTraceInitializationStatus.FAILED
    else:
        status = PresentationTraceInitializationStatus.CREATED

    document = empty_presentation_trace(
        entry_id=entry_id,
        equipment_group_id=runtime.equipment_group_id,
        zone_ids=zone_ids,
        saved_at_utc=_now(now_fn),
    )
    encoded = dict(
        encode_presentation_trace_document(
            document,
            expected_zone_ids=expected_zone_ids,
        )
    )
    try:
        if not await _async_save_verified(store, encoded):
            return PresentationTraceInitializationStatus.FAILED
    except asyncio.CancelledError:
        raise
    except Exception:
        return PresentationTraceInitializationStatus.FAILED
    return status


@dataclass(frozen=True, slots=True)
class _EncodedCandidates:
    config: dict[str, object]
    options: dict[str, object]
    runtime: dict[str, object]


def _encode_and_verify_candidates(
    candidates: Phase2MigrationDryRun,
) -> _EncodedCandidates:
    config = dict(encode_phase2_equipment_group_document(candidates.config))
    options = dict(encode_phase2_options(candidates.options))
    runtime = dict(encode_phase2_runtime_store_document(candidates.runtime))
    zones = tuple(
        decode_phase2_zone_config(dict(encode_phase2_zone_config(zone)))
        for zone in candidates.zones
    )
    if (
        decode_phase2_equipment_group_document(config) != candidates.config
        or decode_phase2_options(options) != candidates.options
        or decode_phase2_runtime_store_document(runtime) != candidates.runtime
        or zones != candidates.zones
    ):
        raise Phase2MigrationError(
            MigrationFailureCategory.SCHEMA_VALIDATION,
            "migration candidates did not round-trip",
        )
    return _EncodedCandidates(config=config, options=options, runtime=runtime)


async def _async_phase1_runtime_source(
    hass: HomeAssistant,
    *,
    entry: IntelligentClimateConfigEntry,
    configuration: EntryRuntimeConfiguration,
    repairs: RepairsManager,
    saved_at: datetime,
) -> tuple[dict[str, object], bool]:
    key = f"{_RUNTIME_KEY_PREFIX}{entry.entry_id}"
    store = _Phase2RuntimeDataStore(hass, key)
    try:
        current = await store.async_load()
    except _LegacyRuntimeEnvelopeError as legacy:
        if legacy.major_version != 1 or legacy.minor_version not in {1, 2}:
            raise Phase2MigrationError(
                MigrationFailureCategory.STORE_VERSION,
                "unsupported Phase 1 runtime Store envelope",
            ) from None
        raw = legacy.data
    except UnsupportedStorageVersionError as err:
        raise Phase2MigrationError(
            MigrationFailureCategory.STORE_VERSION,
            "future runtime Store must be preserved",
        ) from err
    except asyncio.CancelledError:
        raise
    except Exception as err:
        raise Phase2MigrationError(
            MigrationFailureCategory.STORE_LOAD,
            "runtime Store could not be loaded",
        ) from err
    else:
        if current is not None:
            raise Phase2MigrationError(
                MigrationFailureCategory.STORE_VERSION,
                "Phase 2 runtime Store exists beneath a Phase 1 entry",
            )
        return (
            _empty_phase1_runtime(
                entry_id=entry.entry_id,
                configuration=configuration,
                saved_at=saved_at,
            ),
            False,
        )

    try:
        document = decode_runtime_store_document(raw)
        _validate_phase1_runtime_identity(
            document,
            entry_id=entry.entry_id,
            configuration=configuration,
        )
    except (
        KeyError,
        SchemaMigrationError,
        SchemaValidationError,
        TypeError,
        ValueError,
    ):
        if not await _async_quarantine(
            hass,
            key=key,
            envelope_version=1,
            raw=raw,
            reason_code="invalid_nonauthoritative_store",
            remove_primary=store,
            now=saved_at,
        ):
            raise Phase2MigrationError(
                MigrationFailureCategory.STORE_LOAD,
                "invalid runtime Store could not be quarantined safely",
            ) from None
        repairs.async_report_migration_failure(
            MigrationFailureCategory.STORE_VALIDATION
        )
        return (
            _empty_phase1_runtime(
                entry_id=entry.entry_id,
                configuration=configuration,
                saved_at=saved_at,
            ),
            True,
        )
    return dict(cast(Mapping[str, object], raw)), False


async def _async_require_absent_schedule_store(
    hass: HomeAssistant,
    entry_id: str,
) -> None:
    key = f"{_SCHEDULE_KEY_PREFIX}{entry_id}"
    store: Store[dict[str, Any]] = Store(
        hass,
        1,
        key,
        atomic_writes=True,
        max_readable_version=1,
        minor_version=0,
    )
    try:
        raw = await store.async_load()
    except asyncio.CancelledError:
        raise
    except UnsupportedStorageVersionError as err:
        raise Phase2MigrationError(
            MigrationFailureCategory.STORE_VERSION,
            "future schedule Store must be preserved",
        ) from err
    except Exception as err:
        raise Phase2MigrationError(
            MigrationFailureCategory.STORE_LOAD,
            "schedule Store could not be inspected",
        ) from err
    if raw is not None:
        raise Phase2MigrationError(
            MigrationFailureCategory.STORE_VALIDATION,
            "unexpected pre-Phase-2 schedule Store is preserved",
        )


async def _async_load_or_create_phase2_runtime(
    hass: HomeAssistant,
    *,
    entry_id: str,
    config: Phase2EquipmentGroupDocument,
    options_data: IntegrationOptions,
    zones: tuple[Phase2ZoneConfig, ...],
    repairs: RepairsManager,
    saved_at: datetime,
) -> tuple[Phase2RuntimeStoreDocument, bool]:
    key = f"{_RUNTIME_KEY_PREFIX}{entry_id}"
    store = _Phase2RuntimeDataStore(hass, key)
    raw: object | None = None
    try:
        raw = await store.async_load()
    except _LegacyRuntimeEnvelopeError as legacy:
        if legacy.major_version != 1 or legacy.minor_version not in {1, 2}:
            raise Phase2MigrationError(
                MigrationFailureCategory.STORE_VERSION,
                "unsupported legacy runtime Store envelope",
            ) from None
        raw = legacy.data
        try:
            runtime = _runtime_candidate_from_phase1(
                entry_id=entry_id,
                config=config,
                options_data=options_data,
                zones=zones,
                runtime_data=raw,
                saved_at=saved_at,
            )
        except (
            KeyError,
            SchemaMigrationError,
            SchemaValidationError,
            TypeError,
            ValueError,
        ):
            if not await _async_quarantine(
                hass,
                key=key,
                envelope_version=PHASE2_RUNTIME_STORE_ENVELOPE_VERSION,
                raw=raw,
                reason_code="invalid_nonauthoritative_store",
                remove_primary=store,
                now=saved_at,
            ):
                raise Phase2MigrationError(
                    MigrationFailureCategory.STORE_LOAD,
                    "legacy runtime Store could not be quarantined",
                ) from None
            repairs.async_report_migration_failure(
                MigrationFailureCategory.STORE_VALIDATION
            )
            runtime = _runtime_candidate_from_phase1(
                entry_id=entry_id,
                config=config,
                options_data=options_data,
                zones=zones,
                runtime_data=_empty_phase1_runtime_from_phase2(
                    entry_id=entry_id,
                    config=config,
                    zones=zones,
                    saved_at=saved_at,
                ),
                saved_at=saved_at,
            )
            quarantined = True
        else:
            quarantined = False
        encoded = dict(encode_phase2_runtime_store_document(runtime))
        verified = await _async_save_phase2_runtime(
            hass,
            entry_id=entry_id,
            encoded=encoded,
            expected_group_id=str(config.equipment_group.equipment_group_id),
            expected_zone_ids=frozenset(str(zone.zone.zone_id) for zone in zones),
        )
        return verified, quarantined
    except UnsupportedStorageVersionError as err:
        raise Phase2MigrationError(
            MigrationFailureCategory.STORE_VERSION,
            "future runtime Store must be preserved",
        ) from err
    except asyncio.CancelledError:
        raise
    except Exception as err:
        raise Phase2MigrationError(
            MigrationFailureCategory.STORE_LOAD,
            "runtime Store could not be loaded",
        ) from err

    if raw is None:
        runtime = _runtime_candidate_from_phase1(
            entry_id=entry_id,
            config=config,
            options_data=options_data,
            zones=zones,
            runtime_data=_empty_phase1_runtime_from_phase2(
                entry_id=entry_id,
                config=config,
                zones=zones,
                saved_at=saved_at,
            ),
            saved_at=saved_at,
        )
        encoded = dict(encode_phase2_runtime_store_document(runtime))
        return (
            await _async_save_phase2_runtime(
                hass,
                entry_id=entry_id,
                encoded=encoded,
                expected_group_id=str(config.equipment_group.equipment_group_id),
                expected_zone_ids=frozenset(str(zone.zone.zone_id) for zone in zones),
            ),
            False,
        )
    try:
        runtime = decode_phase2_runtime_store_document(raw)
        _require_migration_safe_runtime(runtime)
    except (
        KeyError,
        SchemaMigrationError,
        SchemaValidationError,
        TypeError,
        ValueError,
    ):
        if not await _async_quarantine(
            hass,
            key=key,
            envelope_version=PHASE2_RUNTIME_STORE_ENVELOPE_VERSION,
            raw=raw,
            reason_code="invalid_phase2_runtime_store",
            remove_primary=store,
            now=saved_at,
        ):
            raise Phase2MigrationError(
                MigrationFailureCategory.STORE_LOAD,
                "invalid Phase 2 runtime Store could not be quarantined",
            ) from None
        repairs.async_report_migration_failure(
            MigrationFailureCategory.STORE_VALIDATION
        )
        runtime = _runtime_candidate_from_phase1(
            entry_id=entry_id,
            config=config,
            options_data=options_data,
            zones=zones,
            runtime_data=_empty_phase1_runtime_from_phase2(
                entry_id=entry_id,
                config=config,
                zones=zones,
                saved_at=saved_at,
            ),
            saved_at=saved_at,
        )
        encoded = dict(encode_phase2_runtime_store_document(runtime))
        return (
            await _async_save_phase2_runtime(
                hass,
                entry_id=entry_id,
                encoded=encoded,
                expected_group_id=str(config.equipment_group.equipment_group_id),
                expected_zone_ids=frozenset(str(zone.zone.zone_id) for zone in zones),
            ),
            True,
        )
    return runtime, False


def _runtime_candidate_from_phase1(
    *,
    entry_id: str,
    config: Phase2EquipmentGroupDocument,
    options_data: IntegrationOptions,
    zones: tuple[Phase2ZoneConfig, ...],
    runtime_data: object,
    saved_at: datetime,
) -> Phase2RuntimeStoreDocument:
    return dry_run_phase2_migration(
        entry_id=entry_id,
        config_data=dict(
            encode_equipment_group_document(
                EquipmentGroupDocument(config.equipment_group)
            )
        ),
        config_version=CONFIG_ENTRY_MAJOR_VERSION,
        config_minor_version=CONFIG_ENTRY_MINOR_VERSION,
        options_data=dict(encode_options(options_data)),
        zone_data=[dict(encode_zone_config(zone.zone)) for zone in zones],
        runtime_data=runtime_data,
        time_zone=config.acknowledged_time_zone,
        saved_at=saved_at,
    ).runtime


async def _async_save_phase2_runtime(
    hass: HomeAssistant,
    *,
    entry_id: str,
    encoded: dict[str, object],
    expected_group_id: str,
    expected_zone_ids: frozenset[str],
) -> Phase2RuntimeStoreDocument:
    store = _Phase2RuntimeDataStore(
        hass,
        f"{_RUNTIME_KEY_PREFIX}{entry_id}",
    )
    try:
        if not await _async_save_verified(store, encoded):
            raise Phase2MigrationError(
                MigrationFailureCategory.STORE_LOAD,
                "Phase 2 runtime Store write could not be verified",
            )
        raw = await _Phase2RuntimeDataStore(
            hass,
            f"{_RUNTIME_KEY_PREFIX}{entry_id}",
        ).async_load()
        if raw != encoded:
            raise Phase2MigrationError(
                MigrationFailureCategory.STORE_LOAD,
                "Phase 2 runtime Store read-back did not match",
            )
        runtime = decode_phase2_runtime_store_document(raw)
    except asyncio.CancelledError:
        raise
    except Phase2MigrationError:
        raise
    except Exception as err:
        raise Phase2MigrationError(
            MigrationFailureCategory.STORE_LOAD,
            "Phase 2 runtime Store write failed",
        ) from err
    _validate_runtime_identity(
        runtime,
        entry_id=entry_id,
        group_id=expected_group_id,
        zone_ids=expected_zone_ids,
        source_ids=None,
    )
    _require_migration_safe_runtime(runtime)
    return runtime


async def _async_quarantine(
    hass: HomeAssistant,
    *,
    key: str,
    envelope_version: int,
    raw: object,
    reason_code: str,
    remove_primary: Store[Any],
    now: datetime,
) -> bool:
    quarantine: Store[dict[str, Any]] = Store(
        hass,
        envelope_version,
        f"{key}{_QUARANTINE_SUFFIX}",
        atomic_writes=True,
    )
    payload = {
        "quarantined_at": now.isoformat(),
        "reason_code": reason_code,
        "data": raw,
    }
    try:
        if not await _async_save_verified(quarantine, payload):
            return False
        await remove_primary.async_remove()
    except asyncio.CancelledError:
        raise
    except Exception:
        return False
    return True


async def _async_save_verified(
    store: Store[Any],
    data: dict[str, Any] | dict[str, object],
) -> bool:
    await store.async_save(data)
    if store.hass.state is CoreState.stopping:
        return False
    return await store.async_load() == data


def _empty_phase1_runtime(
    *,
    entry_id: str,
    configuration: EntryRuntimeConfiguration,
    saved_at: datetime,
) -> dict[str, object]:
    document = RuntimeStoreDocument(
        entry_id=entry_id,
        equipment_group_id=configuration.equipment_group.equipment_group_id,
        saved_at=saved_at,
        last_clean_shutdown=True,
        zones={
            zone.zone_id: RuntimeZoneState(
                last_runtime_state=ControlState.RECONCILING,
                last_live_observation_at=None,
                last_effective_temperature_c=None,
                last_effective_humidity_pct=None,
                last_decision_id=None,
            )
            for zone in configuration.zones
        },
        source_baselines={},
        decisions=(),
        command_journal=(),
    )
    from .models import encode_runtime_store_document

    return dict(encode_runtime_store_document(document))


def _empty_phase1_runtime_from_phase2(
    *,
    entry_id: str,
    config: Phase2EquipmentGroupDocument,
    zones: tuple[Phase2ZoneConfig, ...],
    saved_at: datetime,
) -> dict[str, object]:
    document = RuntimeStoreDocument(
        entry_id=entry_id,
        equipment_group_id=config.equipment_group.equipment_group_id,
        saved_at=saved_at,
        last_clean_shutdown=True,
        zones={
            zone.zone.zone_id: RuntimeZoneState(
                last_runtime_state=ControlState.RECONCILING,
                last_live_observation_at=None,
                last_effective_temperature_c=None,
                last_effective_humidity_pct=None,
                last_decision_id=None,
            )
            for zone in zones
        },
        source_baselines={},
        decisions=(),
        command_journal=(),
    )
    from .models import encode_runtime_store_document

    return dict(encode_runtime_store_document(document))


def _validate_phase1_runtime_identity(
    document: RuntimeStoreDocument,
    *,
    entry_id: str,
    configuration: EntryRuntimeConfiguration,
) -> None:
    if document.entry_id != entry_id:
        raise SchemaValidationError("runtime.entry_id", "does not match config entry")
    if document.equipment_group_id != configuration.equipment_group.equipment_group_id:
        raise SchemaValidationError(
            "runtime.equipment_group_id", "does not match equipment group"
        )
    if set(document.zones) != {zone.zone_id for zone in configuration.zones}:
        raise SchemaValidationError(
            "runtime.zones", "must contain every configured zone exactly once"
        )


def _validate_phase2_graph(
    config: Phase2EquipmentGroupDocument,
    zones: tuple[Phase2ZoneConfig, ...],
) -> None:
    zone_ids = tuple(str(zone.zone.zone_id) for zone in zones)
    if len(zone_ids) != len(set(zone_ids)):
        raise SchemaValidationError("zones", "duplicate zone identity")
    if not config.equipment_group.thermostats:
        if any(not _is_empty_zone_skeleton(zone.zone) for zone in zones):
            raise SchemaValidationError(
                "zones",
                "partially bound legacy configuration is not supported",
            )
        return
    if zones:
        decode_configuration_graph(
            dict(
                encode_equipment_group_document(
                    EquipmentGroupDocument(config.equipment_group)
                )
            ),
            [dict(encode_zone_config(zone.zone)) for zone in zones],
        )


def _is_empty_zone_skeleton(zone: ZoneConfig) -> bool:
    """Return whether a transitional zone has no observation bindings."""
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


def _require_migration_safe_config(config: Phase2EquipmentGroupDocument) -> None:
    if (
        config.automation_enabled
        or config.desired_operating_mode.value != "observe_only"
    ):
        raise SchemaValidationError(
            "config", "migration config must remain Observe Only and disabled"
        )


def _require_migration_safe_runtime(runtime: Phase2RuntimeStoreDocument) -> None:
    intent = runtime.control_intent
    if (
        intent.automation_enabled
        or intent.active_control_armed
        or intent.desired_operating_mode.value != "observe_only"
        or runtime.command_journal
        or runtime.overrides
        or runtime.transition_ledger
        or runtime.occupancy_timers
        or runtime.contact_timers
        or runtime.fan_runtime_budget
        or runtime.failure_counters
    ):
        raise SchemaValidationError(
            "runtime", "migration runtime must remain empty Observe Only state"
        )
    allowed_states = {
        ControlExecutionState.INITIALIZING,
        ControlExecutionState.RECONCILING,
        ControlExecutionState.OBSERVING,
        ControlExecutionState.DEGRADED,
        ControlExecutionState.UNLOADING,
    }
    if any(
        state.control_state not in allowed_states for state in runtime.zones.values()
    ):
        raise SchemaValidationError(
            "runtime.zones", "contains an active-control execution state"
        )


def _validate_runtime_identity(
    runtime: Phase2RuntimeStoreDocument,
    *,
    entry_id: str,
    group_id: str,
    zone_ids: frozenset[str],
    source_ids: frozenset[str] | None,
) -> None:
    if runtime.entry_id != entry_id:
        raise SchemaValidationError("runtime.entry_id", "does not match config entry")
    if str(runtime.equipment_group_id) != group_id:
        raise SchemaValidationError(
            "runtime.equipment_group_id", "does not match equipment group"
        )
    if {str(zone_id) for zone_id in runtime.zones} != set(zone_ids):
        raise SchemaValidationError(
            "runtime.zones", "must contain every configured zone exactly once"
        )
    if source_ids is not None and not {
        str(source_id) for source_id in runtime.source_baselines
    }.issubset(source_ids):
        raise SchemaValidationError(
            "runtime.source_baselines", "contains an unknown source identity"
        )
    if any(
        baseline.last_accepted_at > runtime.saved_at
        for baseline in runtime.source_baselines.values()
    ):
        raise SchemaValidationError(
            "runtime.source_baselines", "contains a future baseline"
        )


def _now(now_fn: NowFunction) -> datetime:
    value = now_fn()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("migration clock must return a timezone-aware datetime")
    return value.astimezone(UTC)
