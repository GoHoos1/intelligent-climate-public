"""Privacy-preserving config-entry diagnostics."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections import Counter
from datetime import datetime
from typing import Any

from homeassistant.components.climate.const import ClimateEntityFeature
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant
from homeassistant.util.dt import utcnow

from . import _decode_runtime_configuration
from .const import DOMAIN, INTEGRATION_VERSION
from .coordinator import IntelligentClimateCoordinator
from .models import (
    ActivityRecord,
    EntryObservationSnapshot,
    EntryRuntimeConfiguration,
    ExclusionReason,
    HumiditySource,
    IntegrationOptions,
    SchemaValidationError,
    SourceAggregationResult,
    SourceObservation,
    SourceQuality,
    TemperatureSource,
    ThermostatRuntimeSnapshot,
    ZoneConfig,
    ZoneObservation,
)
from .repairs import active_issue_codes
from .type_aliases import IntelligentClimateConfigEntry
from .validation import EntityValidationError

DIAGNOSTICS_SCHEMA_VERSION = 1
_PSEUDONYM_HEX_LENGTH = 12
_REPORT_SALT_BYTES = 32

_DEFENSIVE_REDACTION_KEYS = frozenset(
    {
        "access_token",
        "account_id",
        "address",
        "api_key",
        "area_id",
        "attributes",
        "authorization",
        "client_secret",
        "context_id",
        "cookie",
        "coordinates",
        "device_id",
        "email",
        "entity_id",
        "entry_id",
        "latitude",
        "longitude",
        "name",
        "password",
        "path",
        "private_key",
        "refresh_token",
        "token",
        "title",
        "unique_id",
        "url",
        "user_id",
        "username",
        "webhook_id",
    }
)

type DiagnosticDict = dict[str, Any]
type ConfiguredSource = TemperatureSource | HumiditySource


class _ReportPseudonymizer:
    """Create bounded report-local references without retaining raw values."""

    __slots__ = ("_cache", "_salt")

    def __init__(self, salt: bytes | None = None) -> None:
        """Initialize one report scope with an injectable random salt."""
        report_salt = _new_report_salt() if salt is None else salt
        if len(report_salt) < 16:
            raise ValueError("diagnostic report salt must contain at least 16 bytes")
        self._salt = report_salt
        self._cache: dict[tuple[str, str], str] = {}

    def entity(self, value: str) -> str:
        """Pseudonymize any configured Home Assistant entity reference."""
        return self._reference("entity", value)

    def name(self, value: str) -> str:
        """Pseudonymize a user-assigned display name."""
        return self._reference("name", value)

    def _reference(self, reference_type: str, value: str) -> str:
        if not value:
            raise ValueError("sensitive diagnostic reference must not be empty")
        cache_key = (reference_type, value)
        if cached := self._cache.get(cache_key):
            return cached
        digest = hmac.new(
            self._salt,
            f"{reference_type}\0{value}".encode(),
            hashlib.sha256,
        ).hexdigest()[:_PSEUDONYM_HEX_LENGTH]
        result = f"{reference_type}_{digest}"
        self._cache[cache_key] = result
        return result


def _new_report_salt() -> bytes:
    """Return fresh randomness for one independently generated report."""
    return secrets.token_bytes(_REPORT_SALT_BYTES)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
) -> dict[str, Any]:
    """Return one JSON-safe, explicitly allowlisted config-entry report."""
    pseudonyms = _ReportPseudonymizer()
    runtime = _runtime(entry)
    configuration, decode_error = _configuration(hass, entry, runtime)
    repairs = {
        "active_issue_codes": [
            code.value for code in active_issue_codes(hass, entry.entry_id)
        ]
    }

    report: DiagnosticDict = {
        "diagnostics_schema_version": DIAGNOSTICS_SCHEMA_VERSION,
        "integration": {
            "domain": DOMAIN,
            "version": INTEGRATION_VERSION,
            "config_entry_version": entry.version,
            "config_entry_minor_version": entry.minor_version,
        },
        "configuration": _configuration_projection(
            entry,
            configuration,
            decode_error,
            pseudonyms,
        ),
        "runtime": _runtime_projection(runtime, pseudonyms, repairs),
    }
    return async_redact_data(report, _DEFENSIVE_REDACTION_KEYS)


def _runtime(
    entry: IntelligentClimateConfigEntry,
) -> IntelligentClimateCoordinator | None:
    value = getattr(entry, "runtime_data", None)
    return value if isinstance(value, IntelligentClimateCoordinator) else None


def _configuration(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
    runtime: IntelligentClimateCoordinator | None,
) -> tuple[EntryRuntimeConfiguration | None, str | None]:
    if runtime is not None:
        return runtime.configuration, None
    try:
        return _decode_runtime_configuration(hass, entry), None
    except SchemaValidationError:
        return None, "schema_validation"
    except EntityValidationError:
        return None, "entity_validation"
    except KeyError, TypeError, ValueError:
        return None, "invalid_configuration"


def _configuration_projection(
    entry: IntelligentClimateConfigEntry,
    configuration: EntryRuntimeConfiguration | None,
    decode_error: str | None,
    pseudonyms: _ReportPseudonymizer,
) -> DiagnosticDict:
    decode_status = {
        "status": "decoded" if configuration is not None else "failed",
        "error_category": decode_error,
    }
    entry_title_reference = pseudonyms.name(entry.title) if entry.title else None
    if configuration is None:
        return {
            "decode_status": decode_status,
            "entry_title_reference": entry_title_reference,
            "runtime_configuration_state": None,
            "equipment_group": None,
            "zones": [],
            "options": None,
        }

    group = configuration.equipment_group
    return {
        "decode_status": decode_status,
        "entry_title_reference": entry_title_reference,
        "runtime_configuration_state": configuration.state.value,
        "equipment_group": {
            "equipment_group_id": str(group.equipment_group_id),
            "name_reference": pseudonyms.name(group.name),
            "equipment_type": group.equipment_type.value,
            "relationship": group.relationship.value,
            "shared_policy_configured": group.shared_policy is not None,
            "thermostats": [
                {
                    "entity_reference": pseudonyms.entity(binding.entity_id),
                    "role": binding.role.value,
                }
                for binding in group.thermostats
            ],
        },
        "zones": [
            _zone_configuration_projection(zone, pseudonyms)
            for zone in configuration.zones
        ],
        "options": _options_projection(configuration.options),
    }


def _zone_configuration_projection(
    zone: ZoneConfig,
    pseudonyms: _ReportPseudonymizer,
) -> DiagnosticDict:
    return {
        "zone_id": str(zone.zone_id),
        "name_reference": pseudonyms.name(zone.name),
        "thermostat_entity_references": [
            pseudonyms.entity(entity_id) for entity_id in zone.thermostat_entity_ids
        ],
        "temperature_sources": [
            _configured_source_projection(source, pseudonyms)
            for source in zone.temperature_sources
        ],
        "humidity_sources": [
            _configured_source_projection(source, pseudonyms)
            for source in zone.humidity_sources
        ],
        "auxiliary_entity_references": {
            "window_door": [
                pseudonyms.entity(entity_id)
                for entity_id in zone.window_door_entity_ids
            ],
            "occupancy": [
                pseudonyms.entity(entity_id) for entity_id in zone.occupancy_entity_ids
            ],
            "stage": [
                pseudonyms.entity(entity_id) for entity_id in zone.stage_entity_ids
            ],
            "fan": [pseudonyms.entity(entity_id) for entity_id in zone.fan_entity_ids],
        },
    }


def _configured_source_projection(
    source: ConfiguredSource,
    pseudonyms: _ReportPseudonymizer,
) -> DiagnosticDict:
    calibration_key = (
        "calibration_offset_c"
        if isinstance(source, TemperatureSource)
        else "calibration_offset_pct"
    )
    calibration = (
        source.offset_c if isinstance(source, TemperatureSource) else source.offset_pct
    )
    return {
        "source_id": str(source.source_id),
        "entity_reference": pseudonyms.entity(source.entity_id),
        "binding_kind": _binding_kind(source),
        calibration_key: calibration,
        "weight": source.weight,
        "priority": source.priority,
        "enabled": source.enabled,
    }


def _binding_kind(source: ConfiguredSource) -> str:
    if source.attribute is None:
        return "sensor_state"
    if source.attribute == "current_temperature":
        return "climate_current_temperature"
    if source.attribute == "current_humidity":
        return "climate_current_humidity"
    return "unsupported_attribute"


def _options_projection(options: IntegrationOptions) -> DiagnosticDict:
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
    }


def _runtime_projection(
    runtime: IntelligentClimateCoordinator | None,
    pseudonyms: _ReportPseudonymizer,
    repairs: DiagnosticDict,
) -> DiagnosticDict:
    if runtime is None or not isinstance(runtime.data, EntryObservationSnapshot):
        return {
            "available": False,
            "repairs": repairs,
            "activity": None,
            "store": None,
        }

    snapshot = runtime.data
    zones_by_id = {zone.zone_id: zone for zone in runtime.configuration.zones}
    activity_records = runtime.history.bounded_records(now=utcnow())
    runtime_store = runtime.runtime_store
    return {
        "available": True,
        "repairs": repairs,
        "activity": {
            "history_record_count": len(activity_records),
            "configured_max_records": (
                runtime.configuration.options.history_max_records
            ),
            "effective_max_records": runtime.history.max_records,
            "configured_max_age_days": (
                runtime.configuration.options.history_max_age_days
            ),
            "history": [_activity_projection(record) for record in activity_records],
        },
        "store": (
            None
            if runtime_store is None
            else {
                "version": runtime_store.version,
                "minor_version": runtime_store.minor_version,
                "loaded": runtime_store.loaded,
                "load_status": runtime_store.load_status.value,
                "read_only": runtime_store.read_only,
                "quarantine_present": runtime_store.quarantine_present,
                "previous_clean_shutdown": runtime_store.previous_clean_shutdown,
                "restored_source_baseline_count": len(
                    runtime_store.restored_source_baselines
                ),
                "dirty": runtime_store.dirty,
                "consecutive_write_failure_count": (
                    runtime_store.consecutive_write_failures
                ),
                "last_successful_save_timestamp": _optional_timestamp(
                    runtime_store.last_successful_save
                ),
            }
        ),
        "revision": snapshot.revision,
        "control_state": snapshot.control_state.value,
        "reconciling": snapshot.reconciling,
        "calculated_at": _timestamp(snapshot.calculated_at),
        "runtime_configuration_state": runtime.configuration.state.value,
        "configured_zone_count": len(runtime.configuration.zones),
        "thermostat_count": len(snapshot.thermostats),
        "thermostats": [
            _thermostat_projection(thermostat, pseudonyms)
            for thermostat in snapshot.thermostats
        ],
        "zones": [
            _zone_runtime_projection(
                zones_by_id[zone.zone_id],
                zone,
                pseudonyms,
            )
            for zone in snapshot.zones
            if zone.zone_id in zones_by_id
        ],
    }


def _activity_projection(record: ActivityRecord) -> DiagnosticDict:
    """Return the explicit privacy-bounded activity diagnostic allowlist."""
    return {
        "record_id": str(record.record_id),
        "timestamp": _timestamp(record.timestamp),
        "equipment_group_id": str(record.equipment_group_id),
        "zone_id": None if record.zone_id is None else str(record.zone_id),
        "activity_type": record.activity_type.value,
        "reason_code": record.reason_code.value,
        "severity": record.severity.value,
        "explanation": record.explanation,
        "detail": dict(record.detail),
    }


def _thermostat_projection(
    thermostat: ThermostatRuntimeSnapshot,
    pseudonyms: _ReportPseudonymizer,
) -> DiagnosticDict:
    state = thermostat.state
    discovery = thermostat.capability_discovery
    capabilities = discovery.capabilities
    capability_projection: DiagnosticDict | None = None
    if capabilities is not None:
        features = capabilities.supported_features
        capability_projection = {
            "hvac_modes": sorted(mode.value for mode in capabilities.hvac_modes),
            "target_temperature_supported": capabilities.target_temperature,
            "target_temperature_range_supported": (
                capabilities.target_temperature_range
            ),
            "fan_mode_supported": bool(features & ClimateEntityFeature.FAN_MODE),
            "preset_mode_supported": bool(features & ClimateEntityFeature.PRESET_MODE),
            "turn_on_supported": bool(features & ClimateEntityFeature.TURN_ON),
            "turn_off_supported": bool(features & ClimateEntityFeature.TURN_OFF),
            "current_temperature_available": (
                capabilities.current_temperature_available
            ),
            "current_humidity_available": capabilities.current_humidity_available,
            "auxiliary_heat_observable": capabilities.auxiliary_heat_observable,
            "stage_observable": capabilities.stage_observable,
            "discovered_at": _timestamp(capabilities.discovered_at),
        }
    return {
        "entity_reference": pseudonyms.entity(thermostat.entity_id),
        "available": state.available,
        "capability_discovery_status": discovery.status.value,
        "capabilities": capability_projection,
        "observed_hvac_mode": (
            None if state.hvac_mode is None else state.hvac_mode.value
        ),
        "observed_hvac_action": (
            None if state.hvac_action is None else state.hvac_action.value
        ),
        "current_temperature_c": state.current_temperature_c,
        "current_humidity_pct": state.current_humidity_pct,
        "target_temperature_c": state.target_temperature_c,
        "target_low_c": state.target_low_c,
        "target_high_c": state.target_high_c,
        "auxiliary_heat_state": state.auxiliary_heat_state.value,
        "last_changed": _optional_timestamp(state.last_changed),
        "last_updated": _optional_timestamp(state.last_updated),
    }


def _zone_runtime_projection(
    configuration: ZoneConfig,
    observation: ZoneObservation,
    pseudonyms: _ReportPseudonymizer,
) -> DiagnosticDict:
    return {
        "zone_id": str(observation.zone_id),
        "name_reference": pseudonyms.name(configuration.name),
        "sensor_data_degraded": observation.sensor_data_degraded,
        "thermostat_data_degraded": observation.thermostat_data_degraded,
        "calculated_at": _timestamp(observation.calculated_at),
        "effective_temperature_c": observation.effective_temperature_c,
        "effective_humidity_pct": observation.effective_humidity_pct,
        "temperature": _source_group_projection(
            configuration.temperature_sources,
            observation.temperature_observations,
            observation.temperature_aggregation,
            pseudonyms,
        ),
        "humidity": (
            None
            if observation.humidity_aggregation is None
            else _source_group_projection(
                configuration.humidity_sources,
                observation.humidity_observations,
                observation.humidity_aggregation,
                pseudonyms,
            )
        ),
    }


def _source_group_projection(
    configured_sources: tuple[ConfiguredSource, ...],
    observations: tuple[SourceObservation[float], ...],
    aggregation: SourceAggregationResult,
    pseudonyms: _ReportPseudonymizer,
) -> DiagnosticDict:
    final_observations = {item.source_id: item for item in observations}
    final_observations.update(
        {item.source_id: item for item in aggregation.excluded_observations}
    )
    quality_counts = Counter(item.quality for item in final_observations.values())
    reason_counts = Counter(
        item.exclusion_reason
        for item in final_observations.values()
        if item.exclusion_reason is not None
    )
    contributing = set(aggregation.contributing_source_ids)
    return {
        "total_configured_sources": len(configured_sources),
        "enabled_sources": sum(source.enabled for source in configured_sources),
        "valid_sources": len(aggregation.valid_source_ids),
        "contributing_sources": len(aggregation.contributing_source_ids),
        "excluded_sources": len(aggregation.excluded_observations),
        "quality_counts": {
            quality.value: quality_counts[quality] for quality in SourceQuality
        },
        "exclusion_reason_counts": {
            reason.value: reason_counts[reason] for reason in ExclusionReason
        },
        "aggregation_status": aggregation.status.value,
        "aggregation_reasons": [reason.value for reason in aggregation.reasons],
        "effective_value_available": aggregation.effective_value is not None,
        "sources": [
            _source_runtime_projection(
                source,
                final_observations.get(source.source_id),
                source.source_id in contributing,
                source.source_id == aggregation.fallback_source_id,
                pseudonyms,
            )
            for source in configured_sources
        ],
    }


def _source_runtime_projection(
    source: ConfiguredSource,
    observation: SourceObservation[float] | None,
    contributing: bool,
    fallback: bool,
    pseudonyms: _ReportPseudonymizer,
) -> DiagnosticDict:
    return {
        "source_id": str(source.source_id),
        "entity_reference": pseudonyms.entity(source.entity_id),
        "binding_kind": _binding_kind(source),
        "enabled": source.enabled,
        "quality": None if observation is None else observation.quality.value,
        "exclusion_reason": (
            None
            if observation is None or observation.exclusion_reason is None
            else observation.exclusion_reason.value
        ),
        "contributing": contributing,
        "fallback": fallback,
        "source_last_reported": (
            None
            if observation is None
            else _optional_timestamp(observation.source_last_reported)
        ),
        "observed_at": (
            None if observation is None else _timestamp(observation.observed_at)
        ),
        "restored": None if observation is None else observation.restored,
    }


def _timestamp(value: datetime) -> str:
    return value.isoformat()


def _optional_timestamp(value: datetime | None) -> str | None:
    return None if value is None else _timestamp(value)
