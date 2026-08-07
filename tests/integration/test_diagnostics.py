"""Test genuine Home Assistant config-entry diagnostics."""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import timedelta
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.climate import (
    ATTR_CURRENT_HUMIDITY,
    ATTR_CURRENT_TEMPERATURE,
    ATTR_HVAC_ACTION,
    ATTR_HVAC_MODES,
)
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigEntry, ConfigSubentryDataWithId
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    ATTR_RESTORED,
    ATTR_SUPPORTED_FEATURES,
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    PERCENTAGE,
    UnitOfTemperature,
)
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.util.dt import utcnow
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.intelligent_climate.const import (
    DOMAIN,
    SUBENTRY_TYPE_ZONE,
)
from custom_components.intelligent_climate.diagnostics import (
    async_get_config_entry_diagnostics,
)
from custom_components.intelligent_climate.models import (
    DEFAULT_OPTIONS,
    RuntimeConfigurationState,
    encode_options,
)
from custom_components.intelligent_climate.repairs import (
    IssueCode,
    MigrationFailureCategory,
    RepairsManager,
    issue_id,
)
from custom_components.intelligent_climate.type_aliases import (
    IntelligentClimateConfigEntry,
)

GROUP_ID = "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
ZONE_IDS = (
    "99246285-6f02-4e8a-94ed-bdfd4a5e62c4",
    "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8",
)
SOURCE_IDS = (
    "f15f73b1-ea59-4b28-819f-7b99acf065bf",
    "ce30dafc-fadd-4cc4-b261-8a896d5a6d12",
    "4d61f93e-a98a-4ce1-bd4a-58b571bdd115",
    "9de4c51b-36ec-4a14-90d9-1df6f51539d0",
)
ENTRY_ID = "01JPRIVATECONFIGENTRY000000"
ENTRY_UNIQUE_ID = "private-config-entry-unique-id"
ENTRY_TITLE = "Private Main Floor"
GROUP_NAME = "Sensitive Equipment Group"
ZONE_NAME = "Private Dining Room"
THERMOSTAT = "climate.private_thermostat"
TEMPERATURE_SENSORS = (
    "sensor.private_temperature",
    "sensor.second_private_temperature",
    "sensor.third_private_temperature",
)
HUMIDITY_SENSOR = "sensor.private_humidity"
OTHER_ENTITY_IDS = (
    "binary_sensor.private_window",
    "person.private_account",
    "binary_sensor.private_stage",
    "fan.private_circulator",
)

SENSITIVE_VALUES = (
    ENTRY_ID,
    ENTRY_UNIQUE_ID,
    ENTRY_TITLE,
    GROUP_NAME,
    ZONE_NAME,
    THERMOSTAT,
    *TEMPERATURE_SENSORS,
    HUMIDITY_SENSOR,
    *OTHER_ENTITY_IDS,
    "private-device-registry-id",
    "private-entity-registry-id",
    "private-area-id",
    "01JPRIVATECONTEXT000000000",
    "private-home-assistant-user-id",
    "private-external-account-id",
    "private@example.com",
    "private-user",
    "private-password",
    "private-api-key",
    "private-authentication-token",
    "private-refresh-token",
    "private-access-token",
    "private-client-secret",
    "private-cookie",
    "Bearer private-authorization",
    "37.123456",
    "-78.654321",
    "123 Private Street",
    "https://private.example.invalid/account",
    "private-webhook-id",
    "-----BEGIN PRIVATE KEY-----",
    "arbitrary-private-provider-attribute",
    "C:\\private\\homeassistant\\configuration.yaml",
    "private-repository-credential",
)


def _parent_data(
    *,
    thermostat: str | None = THERMOSTAT,
    name: str = GROUP_NAME,
) -> dict[str, object]:
    return {
        "equipment_group": {
            "equipment_group_id": GROUP_ID,
            "name": name,
            "equipment_type": "air_source_heat_pump",
            "relationship": "single_system",
            "thermostats": (
                []
                if thermostat is None
                else [{"entity_id": thermostat, "role": "primary"}]
            ),
            "shared_policy": None,
        }
    }


def _temperature_source(
    index: int,
    *,
    entity_id: str | None = None,
    attribute: str | None = None,
    enabled: bool = True,
) -> dict[str, object]:
    return {
        "source_id": SOURCE_IDS[index],
        "entity_id": entity_id or TEMPERATURE_SENSORS[index],
        "attribute": attribute,
        "offset_c": 0.25 + index,
        "weight": 1.5 + index,
        "priority": index,
        "enabled": enabled,
    }


def _zone_data(
    *,
    name: str = ZONE_NAME,
    sources: list[dict[str, object]] | None = None,
    humidity: bool = True,
    empty: bool = False,
) -> dict[str, object]:
    if sources is None:
        sources = [
            _temperature_source(0),
            _temperature_source(
                1,
                entity_id=THERMOSTAT,
                attribute=ATTR_CURRENT_TEMPERATURE,
            ),
        ]
    return {
        "data_version": 1,
        "zone_id": ZONE_IDS[0],
        "name": name,
        "thermostat_entity_ids": [] if empty else [THERMOSTAT],
        "temperature_sources": [] if empty else sources,
        "humidity_sources": (
            []
            if empty or not humidity
            else [
                {
                    "source_id": SOURCE_IDS[2],
                    "entity_id": HUMIDITY_SENSOR,
                    "attribute": None,
                    "offset_pct": -0.5,
                    "weight": 2.0,
                    "priority": 1,
                    "enabled": True,
                }
            ]
        ),
        "window_door_entity_ids": [] if empty else [OTHER_ENTITY_IDS[0]],
        "occupancy_entity_ids": [] if empty else [OTHER_ENTITY_IDS[1]],
        "stage_entity_ids": [] if empty else [OTHER_ENTITY_IDS[2]],
        "fan_entity_ids": [] if empty else [OTHER_ENTITY_IDS[3]],
    }


def _subentry(
    data: dict[str, object] | None = None,
) -> ConfigSubentryDataWithId:
    zone = _zone_data() if data is None else data
    return ConfigSubentryDataWithId(
        data=zone,
        subentry_id="private-zone-subentry-id",
        subentry_type=SUBENTRY_TYPE_ZONE,
        title=str(zone["name"]),
        unique_id=str(zone["zone_id"]),
    )


def _entry(
    *,
    data: dict[str, object] | None = None,
    zones: list[ConfigSubentryDataWithId] | None = None,
    observation_enabled: bool = True,
    source_stale_after_seconds: int = 1800,
    title: str = ENTRY_TITLE,
    thermostat: str = THERMOSTAT,
) -> MockConfigEntry:
    parent = _parent_data(thermostat=thermostat) if data is None else data
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=ENTRY_ID,
        unique_id=ENTRY_UNIQUE_ID,
        title=title,
        data=parent,
        options=dict(
            encode_options(
                replace(
                    DEFAULT_OPTIONS,
                    observation_enabled=observation_enabled,
                    source_stale_after_seconds=source_stale_after_seconds,
                    startup_reconciliation_seconds=60,
                    min_valid_temperature_sources=1,
                )
            )
        ),
        subentries_data=[_subentry()] if zones is None else zones,
        version=1,
        minor_version=0,
    )


def _sensitive_attributes() -> dict[str, object]:
    return {
        "device_id": "private-device-registry-id",
        "entity_registry_id": "private-entity-registry-id",
        "area_id": "private-area-id",
        "context_id": "01JPRIVATECONTEXT000000000",
        "user_id": "private-home-assistant-user-id",
        "external_account_id": "private-external-account-id",
        "email": "private@example.com",
        "username": "private-user",
        "password": "private-password",
        "api_key": "private-api-key",
        "authentication_token": "private-authentication-token",
        "refresh_token": "private-refresh-token",
        "access_token": "private-access-token",
        "client_secret": "private-client-secret",
        "cookie": "private-cookie",
        "authorization": "Bearer private-authorization",
        "latitude": "37.123456",
        "longitude": "-78.654321",
        "street_address": "123 Private Street",
        "url": "https://private.example.invalid/account",
        "webhook_id": "private-webhook-id",
        "private_key": "-----BEGIN PRIVATE KEY-----",
        "provider_private": "arbitrary-private-provider-attribute",
        "filesystem_path": "C:\\private\\homeassistant\\configuration.yaml",
        "repository_credential": "private-repository-credential",
    }


def _set_thermostat(
    hass: HomeAssistant,
    *,
    current_temperature: float = 20.6,
) -> None:
    attributes: dict[str, object] = {
        ATTR_HVAC_MODES: [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL],
        ATTR_SUPPORTED_FEATURES: int(ClimateEntityFeature.TARGET_TEMPERATURE),
        ATTR_CURRENT_TEMPERATURE: current_temperature,
        ATTR_CURRENT_HUMIDITY: 49.0,
        ATTR_HVAC_ACTION: HVACAction.HEATING,
        ATTR_TEMPERATURE: 21.5,
        **_sensitive_attributes(),
    }
    hass.states.async_set(
        THERMOSTAT,
        HVACMode.HEAT,
        attributes,
        context=Context(
            id="01JPRIVATECONTEXT000000000",
            user_id="private-home-assistant-user-id",
        ),
    )


def _set_temperature_sensor(
    hass: HomeAssistant,
    entity_id: str,
    value: float | str,
    *,
    timestamp_offset: timedelta = timedelta(),
    restored: bool = False,
) -> None:
    attributes: dict[str, object] = {
        ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
        ATTR_UNIT_OF_MEASUREMENT: UnitOfTemperature.CELSIUS,
        **_sensitive_attributes(),
    }
    if restored:
        attributes[ATTR_RESTORED] = True
    timestamp = utcnow() + timestamp_offset
    hass.states.async_set(
        entity_id,
        str(value),
        attributes,
        timestamp=timestamp.timestamp(),
        context=Context(
            id="01JPRIVATECONTEXT000000000",
            user_id="private-home-assistant-user-id",
        ),
    )


def _set_humidity_sensor(hass: HomeAssistant, value: float = 49.0) -> None:
    hass.states.async_set(
        HUMIDITY_SENSOR,
        str(value),
        {
            ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY,
            ATTR_UNIT_OF_MEASUREMENT: PERCENTAGE,
            **_sensitive_attributes(),
        },
    )


def _set_valid_states(hass: HomeAssistant) -> None:
    _set_thermostat(hass)
    _set_temperature_sensor(hass, TEMPERATURE_SENSORS[0], 20.4)
    _set_humidity_sensor(hass)


async def _setup(
    hass: HomeAssistant,
    entry: MockConfigEntry,
) -> IntelligentClimateConfigEntry:
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    typed = cast(IntelligentClimateConfigEntry, entry)
    if typed.runtime_data.data.reconciling:
        # The helper compares this timestamp with wall-clock time at invocation.
        async_fire_time_changed(
            hass,
            utcnow() + timedelta(seconds=61),
        )
        await hass.async_block_till_done()
    return typed


async def _report(
    hass: HomeAssistant,
    entry: MockConfigEntry | ConfigEntry,
) -> dict[str, Any]:
    return await async_get_config_entry_diagnostics(
        hass,
        cast(IntelligentClimateConfigEntry, entry),
    )


def _serialized(report: dict[str, Any]) -> str:
    return json.dumps(report, sort_keys=True)


def _all_mapping_keys(value: object) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(str(key))
            keys.update(_all_mapping_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_all_mapping_keys(item))
    return keys


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_loaded_diagnostics_are_allowlisted_deterministic_and_json_safe(
    hass: HomeAssistant,
) -> None:
    """A real loaded entry exposes useful state without private input values."""
    _set_valid_states(hass)
    entry = await _setup(hass, _entry())
    coordinator = entry.runtime_data
    snapshot = coordinator.data
    timers = (
        coordinator._cancel_debounce,
        coordinator._cancel_reconciliation,
        coordinator._cancel_watchdog,
        coordinator._cancel_state_change_subscription,
        coordinator._cancel_state_report_subscription,
    )
    baselines = dict(coordinator._source_baselines)
    pending_jumps = dict(coordinator._pending_temperature_jumps)
    history_records = coordinator.history.records
    runtime_store = coordinator.runtime_store
    assert runtime_store is not None
    store_state = (
        runtime_store.loaded,
        runtime_store.dirty,
        runtime_store.consecutive_write_failures,
        runtime_store.last_successful_save,
        runtime_store._save_handle,
        runtime_store.write_task,
        runtime_store.load_status,
    )
    known_salt = b"known-report-salt-material-000001"

    with (
        patch(
            "custom_components.intelligent_climate.diagnostics._new_report_salt",
            return_value=known_salt,
        ),
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
        ) as service_call,
        patch.object(hass.config_entries, "async_schedule_reload") as reload,
        patch("builtins.open", side_effect=AssertionError("filesystem access")),
        patch("socket.create_connection", side_effect=AssertionError("network access")),
    ):
        report = await _report(hass, entry)
        repeated = await _report(hass, entry)

    assert report == repeated
    json.dumps(report)
    assert list(report) == [
        "diagnostics_schema_version",
        "integration",
        "configuration",
        "runtime",
    ]
    assert report["diagnostics_schema_version"] == 1
    assert report["integration"] == {
        "domain": DOMAIN,
        "version": "0.0.19",
        "config_entry_version": 2,
        "config_entry_minor_version": 0,
    }

    configuration = report["configuration"]
    assert configuration["decode_status"] == {
        "status": "decoded",
        "error_category": None,
    }
    assert configuration["runtime_configuration_state"] == "configured"
    group = configuration["equipment_group"]
    assert group["equipment_group_id"] == GROUP_ID
    assert group["equipment_type"] == "air_source_heat_pump"
    assert group["relationship"] == "single_system"
    assert group["shared_policy_configured"] is False
    assert re.fullmatch(r"name_[0-9a-f]{12}", group["name_reference"])
    assert configuration["entry_title_reference"] != group["name_reference"]
    zone_configuration = configuration["zones"][0]
    assert zone_configuration["zone_id"] == ZONE_IDS[0]
    assert re.fullmatch(
        r"name_[0-9a-f]{12}",
        zone_configuration["name_reference"],
    )
    assert [row["source_id"] for row in zone_configuration["temperature_sources"]] == [
        SOURCE_IDS[0],
        SOURCE_IDS[1],
    ]
    assert zone_configuration["temperature_sources"][0] == {
        "source_id": SOURCE_IDS[0],
        "entity_reference": zone_configuration["temperature_sources"][0][
            "entity_reference"
        ],
        "binding_kind": "sensor_state",
        "calibration_offset_c": 0.25,
        "weight": 1.5,
        "priority": 0,
        "enabled": True,
    }
    assert zone_configuration["humidity_sources"][0]["source_id"] == SOURCE_IDS[2]
    assert zone_configuration["humidity_sources"][0]["calibration_offset_pct"] == -0.5
    assert configuration["options"] == {
        "observation_enabled": True,
        "temperature_strategy": "median",
        "humidity_strategy": "median",
        "min_valid_temperature_sources": 1,
        "min_valid_humidity_sources": 1,
        "source_stale_after_seconds": 1800,
        "startup_reconciliation_seconds": 60,
        "jump_limit_c_per_5_minutes": 2.8,
        "outlier_floor_c": 1.7,
        "indoor_temperature_min_c": 1.7,
        "indoor_temperature_max_c": 43.3,
        "history_max_records": 500,
        "history_max_age_days": 30,
    }

    runtime = report["runtime"]
    assert runtime["available"] is True
    assert runtime["repairs"] == {"active_issue_codes": []}
    assert runtime["store"] == {
        "version": 2,
        "minor_version": 0,
        "loaded": True,
        "load_status": store_state[6].value,
        "read_only": False,
        "quarantine_present": False,
        "previous_clean_shutdown": True,
        "restored_source_baseline_count": 0,
        "dirty": True,
        "consecutive_write_failure_count": 0,
        "last_successful_save_timestamp": (
            None if store_state[3] is None else store_state[3].isoformat()
        ),
    }
    assert runtime["activity"]["configured_max_records"] == 500
    assert runtime["activity"]["effective_max_records"] == 500
    assert runtime["activity"]["configured_max_age_days"] == 30
    assert runtime["activity"]["history_record_count"] == len(
        runtime["activity"]["history"]
    )
    assert {record["activity_type"] for record in runtime["activity"]["history"]} >= {
        "lifecycle",
        "runtime_state_changed",
    }
    assert runtime["revision"] == snapshot.revision
    assert runtime["control_state"] == "observing"
    assert runtime["reconciling"] is False
    assert runtime["runtime_configuration_state"] == "configured"
    assert runtime["configured_zone_count"] == 1
    assert runtime["thermostat_count"] == 1
    thermostat = runtime["thermostats"][0]
    assert thermostat["available"] is True
    assert thermostat["capability_discovery_status"] == "complete"
    assert thermostat["observed_hvac_mode"] == "heat"
    assert thermostat["observed_hvac_action"] == "heating"
    assert thermostat["current_temperature_c"] == 20.6
    assert thermostat["current_humidity_pct"] == 49.0
    assert thermostat["target_temperature_c"] == 21.5
    assert thermostat["target_low_c"] is None
    assert thermostat["target_high_c"] is None
    assert thermostat["auxiliary_heat_state"] == "not_observable"
    assert thermostat["capabilities"] == {
        "hvac_modes": ["cool", "heat", "off"],
        "target_temperature_supported": True,
        "target_temperature_range_supported": False,
        "fan_mode_supported": False,
        "preset_mode_supported": False,
        "turn_on_supported": False,
        "turn_off_supported": False,
        "current_temperature_available": True,
        "current_humidity_available": True,
        "auxiliary_heat_observable": False,
        "stage_observable": False,
        "discovered_at": thermostat["capabilities"]["discovered_at"],
    }
    zone = runtime["zones"][0]
    assert zone["zone_id"] == ZONE_IDS[0]
    assert zone["effective_temperature_c"] == 21.2
    assert zone["effective_humidity_pct"] == 48.5
    temperature = zone["temperature"]
    assert temperature["total_configured_sources"] == 2
    assert temperature["enabled_sources"] == 2
    assert temperature["valid_sources"] == 2
    assert temperature["contributing_sources"] == 2
    assert temperature["excluded_sources"] == 0
    assert temperature["quality_counts"]["valid"] == 2
    assert sum(temperature["exclusion_reason_counts"].values()) == 0
    assert temperature["aggregation_status"] == "healthy"
    assert temperature["aggregation_reasons"] == []
    assert temperature["effective_value_available"] is True
    assert [row["source_id"] for row in temperature["sources"]] == [
        SOURCE_IDS[0],
        SOURCE_IDS[1],
    ]
    assert zone["humidity"]["quality_counts"]["valid"] == 1
    assert zone["humidity"]["effective_value_available"] is True

    thermostat_reference = group["thermostats"][0]["entity_reference"]
    assert thermostat_reference == zone_configuration["thermostat_entity_references"][0]
    assert (
        thermostat_reference
        == zone_configuration["temperature_sources"][1]["entity_reference"]
    )
    assert thermostat_reference == thermostat["entity_reference"]
    assert thermostat_reference == temperature["sources"][1]["entity_reference"]
    assert thermostat_reference != temperature["sources"][0]["entity_reference"]
    assert re.fullmatch(r"entity_[0-9a-f]{12}", thermostat_reference)
    assert known_salt.decode() not in _serialized(report)

    serialized = _serialized(report)
    for forbidden in SENSITIVE_VALUES:
        assert forbidden not in serialized
    assert "raw_value" not in _all_mapping_keys(report)
    assert "attributes" not in _all_mapping_keys(report)
    assert "<state" not in serialized.casefold()

    assert coordinator.data is snapshot
    assert coordinator.data.revision == snapshot.revision
    assert timers == (
        coordinator._cancel_debounce,
        coordinator._cancel_reconciliation,
        coordinator._cancel_watchdog,
        coordinator._cancel_state_change_subscription,
        coordinator._cancel_state_report_subscription,
    )
    assert coordinator._source_baselines == baselines
    assert coordinator._pending_temperature_jumps == pending_jumps
    assert coordinator.history.records is history_records
    assert store_state == (
        runtime_store.loaded,
        runtime_store.dirty,
        runtime_store.consecutive_write_failures,
        runtime_store.last_successful_save,
        runtime_store._save_handle,
        runtime_store.write_task,
        runtime_store.load_status,
    )
    service_call.assert_not_awaited()
    reload.assert_not_called()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_independent_reports_receive_independent_pseudonyms(
    hass: HomeAssistant,
) -> None:
    """Fresh report randomness changes every sensitive reference."""
    _set_valid_states(hass)
    entry = await _setup(hass, _entry())

    first = await _report(hass, entry)
    second = await _report(hass, entry)

    first_reference = first["runtime"]["thermostats"][0]["entity_reference"]
    second_reference = second["runtime"]["thermostats"][0]["entity_reference"]
    assert first_reference != second_reference
    assert (
        first["configuration"]["equipment_group"]["name_reference"]
        != second["configuration"]["equipment_group"]["name_reference"]
    )


@pytest.mark.parametrize(
    ("entry", "expected_state"),
    [
        (
            _entry(zones=[]),
            RuntimeConfigurationState.AWAITING_FIRST_ZONE.value,
        ),
        (
            _entry(
                data=_parent_data(thermostat=None),
                zones=[_subentry(_zone_data(empty=True))],
            ),
            RuntimeConfigurationState.TRANSITIONAL_EMPTY_SKELETON.value,
        ),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unloaded_lifecycle_configurations_are_safely_decoded(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    expected_state: str,
) -> None:
    """Awaiting-first-zone and transitional entries need no runtime object."""
    entry.add_to_hass(hass)

    report = await _report(hass, entry)

    assert report["configuration"]["decode_status"]["status"] == "decoded"
    assert report["configuration"]["runtime_configuration_state"] == expected_state
    assert report["runtime"] == {
        "available": False,
        "repairs": {"active_issue_codes": []},
        "activity": None,
        "store": None,
    }
    for forbidden in SENSITIVE_VALUES:
        assert forbidden not in _serialized(report)


@pytest.mark.parametrize(
    ("entry", "category"),
    [
        (
            _entry(
                data={
                    "password": "private-password",
                    "url": "https://private.example.invalid/account",
                    "coordinates": [37.123456, -78.654321],
                },
                zones=[],
                title="private-password",
            ),
            "schema_validation",
        ),
        (
            _entry(
                data=_parent_data(thermostat="sensor.private_temperature"),
                zones=[],
                thermostat="sensor.private_temperature",
            ),
            "entity_validation",
        ),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_persisted_configuration_returns_bounded_decode_status(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    category: str,
) -> None:
    """Malformed input never escapes through an exception string or raw data."""
    entry.add_to_hass(hass)

    report = await _report(hass, entry)

    assert report["configuration"]["decode_status"] == {
        "status": "failed",
        "error_category": category,
    }
    assert report["configuration"]["runtime_configuration_state"] is None
    assert report["configuration"]["equipment_group"] is None
    assert report["configuration"]["zones"] == []
    assert report["configuration"]["options"] is None
    assert report["runtime"] == {
        "available": False,
        "repairs": {"active_issue_codes": []},
        "activity": None,
        "store": None,
    }
    serialized = _serialized(report)
    assert "traceback" not in serialized.casefold()
    assert "private-password" not in serialized
    assert "https://private.example.invalid/account" not in serialized
    assert "sensor.private_temperature" not in serialized


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unexpected_boundary_value_error_uses_generic_decode_category(
    hass: HomeAssistant,
) -> None:
    """Unexpected decoder value errors cannot echo their sensitive message."""
    entry = _entry(zones=[])
    entry.add_to_hass(hass)

    with patch(
        "custom_components.intelligent_climate.diagnostics."
        "_decode_runtime_configuration",
        side_effect=TypeError("private-password"),
    ):
        report = await _report(hass, entry)

    assert report["configuration"]["decode_status"] == {
        "status": "failed",
        "error_category": "invalid_configuration",
    }
    assert "private-password" not in _serialized(report)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_empty_entry_title_is_omitted_without_breaking_failed_decode(
    hass: HomeAssistant,
) -> None:
    """An empty Home Assistant title is not a reason to lose safe diagnostics."""
    entry = _entry(data={}, zones=[], title="")
    entry.add_to_hass(hass)

    report = await _report(hass, entry)

    assert report["configuration"]["decode_status"]["status"] == "failed"
    assert report["configuration"]["entry_title_reference"] is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_disabled_observation_diagnostics_are_loaded_and_bounded(
    hass: HomeAssistant,
) -> None:
    """Disabled observation reports configuration without inventing observations."""
    entry = await _setup(hass, _entry(observation_enabled=False))

    report = await _report(hass, entry)

    assert report["runtime"]["available"] is True
    assert report["runtime"]["control_state"] == "disabled"
    assert report["runtime"]["reconciling"] is False
    temperature = report["runtime"]["zones"][0]["temperature"]
    assert temperature["aggregation_status"] == "unavailable"
    assert temperature["quality_counts"]["valid"] == 0
    assert all(row["quality"] is None for row in temperature["sources"])
    assert entry.runtime_data._cancel_state_change_subscription is None
    assert entry.runtime_data._cancel_state_report_subscription is None
    assert entry.runtime_data._cancel_reconciliation is None
    assert entry.runtime_data._cancel_watchdog is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_missing_source_is_unavailable_without_raw_entity_id(
    hass: HomeAssistant,
) -> None:
    """Startup ordering gaps remain useful and privacy-preserving."""
    _set_thermostat(hass)
    _set_humidity_sensor(hass)
    entry = await _setup(hass, _entry())

    report = await _report(hass, entry)

    row = report["runtime"]["zones"][0]["temperature"]["sources"][0]
    assert row["quality"] == "unavailable"
    assert row["exclusion_reason"] == "unavailable"
    assert row["source_last_reported"] is None
    assert TEMPERATURE_SENSORS[0] not in _serialized(report)


@pytest.mark.parametrize(
    ("value", "timestamp_offset", "restored", "quality"),
    [
        (20.4, timedelta(minutes=-31), False, "stale"),
        (20.4, timedelta(), True, "restored_not_confirmed"),
        (100.0, timedelta(), False, "implausible"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_source_health_quality_is_represented_without_raw_values(
    hass: HomeAssistant,
    value: float,
    timestamp_offset: timedelta,
    restored: bool,
    quality: str,
) -> None:
    """Stale, restored, and implausible source health survives projection."""
    _set_thermostat(hass)
    _set_temperature_sensor(
        hass,
        TEMPERATURE_SENSORS[0],
        value,
        timestamp_offset=timestamp_offset,
        restored=restored,
    )
    _set_humidity_sensor(hass)
    entry = await _setup(hass, _entry())

    report = await _report(hass, entry)
    temperature = report["runtime"]["zones"][0]["temperature"]
    row = temperature["sources"][0]

    assert row["quality"] == quality
    assert row["exclusion_reason"] == quality
    assert temperature["quality_counts"][quality] == 1
    assert temperature["exclusion_reason_counts"][quality] == 1
    assert "raw_value" not in _all_mapping_keys(report)


@pytest.mark.parametrize(
    ("values", "expected_quality", "expected_reason"),
    [
        ((10.0, 30.0), "contradictory", "two_source_contradiction"),
        ((20.0, 20.1, 30.0), "outlier", "outlier_excluded"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_cross_source_exclusion_summaries_are_accurate(
    hass: HomeAssistant,
    values: tuple[float, ...],
    expected_quality: str,
    expected_reason: str,
) -> None:
    """Contradiction and outlier summaries use final aggregation qualities."""
    sources = [
        _temperature_source(index, entity_id=TEMPERATURE_SENSORS[index])
        for index in range(len(values))
    ]
    zone = _zone_data(sources=sources, humidity=False)
    _set_thermostat(hass)
    for entity_id, value in zip(
        TEMPERATURE_SENSORS[: len(values)],
        values,
        strict=True,
    ):
        _set_temperature_sensor(hass, entity_id, value)
    entry = await _setup(hass, _entry(zones=[_subentry(zone)]))

    report = await _report(hass, entry)
    temperature = report["runtime"]["zones"][0]["temperature"]

    assert temperature["quality_counts"][expected_quality] >= 1
    assert temperature["exclusion_reason_counts"][expected_quality] >= 1
    assert expected_reason in temperature["aggregation_reasons"]
    assert any(row["quality"] == expected_quality for row in temperature["sources"])
    assert [row["source_id"] for row in temperature["sources"]] == list(
        SOURCE_IDS[: len(values)]
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_jump_rejection_is_reported_after_live_source_change(
    hass: HomeAssistant,
) -> None:
    """A pending suspicious jump remains excluded in downloadable diagnostics."""
    _set_thermostat(hass)
    _set_temperature_sensor(hass, TEMPERATURE_SENSORS[0], 20.0)
    _set_humidity_sensor(hass)
    entry = await _setup(
        hass,
        _entry(
            zones=[
                _subentry(
                    _zone_data(
                        sources=[_temperature_source(0)],
                        humidity=False,
                    )
                )
            ]
        ),
    )

    _set_temperature_sensor(hass, TEMPERATURE_SENSORS[0], 30.0)
    await hass.async_block_till_done()
    async_fire_time_changed(
        hass,
        entry.runtime_data.data.calculated_at + timedelta(seconds=1),
    )
    await hass.async_block_till_done()
    report = await _report(hass, entry)
    row = report["runtime"]["zones"][0]["temperature"]["sources"][0]

    assert row["quality"] == "jump_rejected"
    assert row["exclusion_reason"] == "jump_rejected"
    assert (
        report["runtime"]["zones"][0]["temperature"]["quality_counts"]["jump_rejected"]
        == 1
    )
    assert entry.runtime_data._pending_temperature_jumps


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_repairs_projection_is_sorted_private_read_only_and_json_safe(
    hass: HomeAssistant,
) -> None:
    """Diagnostics expose only active codes and never mutate the issue registry."""
    _set_valid_states(hass)
    entry = await _setup(hass, _entry())
    manager = entry.runtime_data.issue_manager
    manager.async_report_migration_failure(MigrationFailureCategory.SCHEMA_VALIDATION)
    manager.async_report_command_boundary_violation()
    registry = ir.async_get(hass)
    before = dict(registry.issues)

    report = await _report(hass, entry)

    assert report["diagnostics_schema_version"] == 1
    assert report["runtime"]["repairs"] == {
        "active_issue_codes": [
            "command_boundary_violation",
            "migration_failed",
        ]
    }
    assert registry.issues == before
    serialized = _serialized(report)
    assert ENTRY_ID not in serialized
    assert issue_id(ENTRY_ID, IssueCode.MIGRATION_FAILED) not in serialized
    assert issue_id(ENTRY_ID, IssueCode.COMMAND_BOUNDARY_VIOLATION) not in serialized
    assert "unexpected_control_intent" not in serialized
    json.loads(serialized)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_repairs_projection_survives_absent_runtime_and_failed_decode(
    hass: HomeAssistant,
) -> None:
    """Issue-code diagnostics do not require runtime data or valid configuration."""
    entry = _entry(data={"malformed_private_document": "never-copy"})
    manager = RepairsManager(hass, ENTRY_ID)
    manager.async_report_migration_failure(MigrationFailureCategory.SCHEMA_VALIDATION)

    report = await _report(hass, entry)

    assert report["configuration"]["decode_status"] == {
        "status": "failed",
        "error_category": "schema_validation",
    }
    assert report["runtime"] == {
        "available": False,
        "repairs": {"active_issue_codes": ["migration_failed"]},
        "activity": None,
        "store": None,
    }
    assert "never-copy" not in _serialized(report)
