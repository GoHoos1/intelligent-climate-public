"""Test genuine Home Assistant Repairs integration and lifecycle."""

from __future__ import annotations

import json
from dataclasses import replace
from datetime import timedelta
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate import async_setup_entry, async_unload_entry
from custom_components.intelligent_climate.const import (
    DOMAIN,
    PLATFORMS,
    SUBENTRY_TYPE_ZONE,
)
from custom_components.intelligent_climate.control import (
    ObservationIntent,
    ObserveOnlyCommandSink,
)
from custom_components.intelligent_climate.repairs import (
    IssueCode,
    MigrationFailureCategory,
    RepairsManager,
    issue_id,
)

GROUP_ID = "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
ZONE_ID = "99246285-6f02-4e8a-94ed-bdfd4a5e62c4"
SOURCE_IDS = (
    "f15f73b1-ea59-4b28-819f-7b99acf065bf",
    "ce30dafc-fadd-4cc4-b261-8a896d5a6d12",
)
ENTRY_ID = "01JPRIVATECONFIGENTRY000000"
THERMOSTAT = "climate.private_thermostat"
SENSORS = ("sensor.private_temperature", "sensor.second_private_temperature")


def _parent_data(thermostat: str = THERMOSTAT) -> dict[str, object]:
    return {
        "equipment_group": {
            "equipment_group_id": GROUP_ID,
            "name": "Private equipment group",
            "equipment_type": "conventional",
            "relationship": "single_system",
            "thermostats": [{"entity_id": thermostat, "role": "primary"}],
            "shared_policy": None,
        }
    }


def _source(index: int, entity_id: str) -> dict[str, object]:
    return {
        "source_id": SOURCE_IDS[index],
        "entity_id": entity_id,
        "attribute": None,
        "offset_c": 0.0,
        "weight": 1.0,
        "priority": 0,
        "enabled": True,
    }


def _zone_data(
    *,
    sources: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "data_version": 1,
        "zone_id": ZONE_ID,
        "name": "Private zone",
        "thermostat_entity_ids": [THERMOSTAT],
        "temperature_sources": (
            [_source(0, SENSORS[0])] if sources is None else sources
        ),
        "humidity_sources": [],
        "window_door_entity_ids": [],
        "occupancy_entity_ids": [],
        "stage_entity_ids": [],
        "fan_entity_ids": [],
    }


def _subentry(data: dict[str, object]) -> ConfigSubentryDataWithId:
    return config_entries.ConfigSubentryDataWithId(
        data=data,
        subentry_id="zone-subentry-1",
        subentry_type=SUBENTRY_TYPE_ZONE,
        title=str(data["name"]),
        unique_id=str(data["zone_id"]),
    )


def _entry(
    *,
    entry_id: str = ENTRY_ID,
    version: int = 1,
    data: dict[str, object] | None = None,
    zone_data: dict[str, object] | None = None,
    observation_enabled: bool = True,
) -> MockConfigEntry:
    options: dict[str, object] = {}
    if not observation_enabled:
        from custom_components.intelligent_climate.models import (
            DEFAULT_OPTIONS,
            encode_options,
        )

        options = dict(
            encode_options(replace(DEFAULT_OPTIONS, observation_enabled=False))
        )
    zone = _zone_data() if zone_data is None else zone_data
    return MockConfigEntry(
        domain=DOMAIN,
        entry_id=entry_id,
        data=_parent_data() if data is None else data,
        options=options,
        subentries_data=[_subentry(zone)],
        version=version,
        minor_version=0,
        state=config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    )


def _set_valid_states(hass: HomeAssistant) -> None:
    hass.states.async_set(THERMOSTAT, "heat")
    for index, entity_id in enumerate(SENSORS):
        hass.states.async_set(
            entity_id,
            str(20 + index),
            {
                ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE,
                "unit_of_measurement": UnitOfTemperature.CELSIUS,
            },
        )


def _issue(
    hass: HomeAssistant,
    entry_id: str,
    code: IssueCode,
) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue(DOMAIN, issue_id(entry_id, code))


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with patch.object(
        hass.config_entries,
        "async_forward_entry_setups",
        new_callable=AsyncMock,
    ) as forward:
        assert await async_setup_entry(hass, entry)
    forward.assert_awaited_once_with(entry, PLATFORMS)


async def _unload(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        new_callable=AsyncMock,
        return_value=True,
    ):
        assert await async_unload_entry(hass, entry)


async def _finish_reconciliation(entry: MockConfigEntry) -> None:
    coordinator = entry.runtime_data
    await coordinator._async_reconciliation_complete(
        coordinator.data.calculated_at
        + timedelta(
            seconds=coordinator.configuration.options.startup_reconciliation_seconds
        ),
        generation=coordinator._reconciliation_generation,
    )


async def _publish_entity_change(
    entry: MockConfigEntry,
    *entity_ids: str,
) -> None:
    coordinator = entry.runtime_data
    for entity_id in entity_ids:
        coordinator._collect_entity_event(entity_id)
    await coordinator._async_debounce_elapsed(
        coordinator.data.calculated_at + timedelta(seconds=1),
        generation=coordinator._debounce_generation,
    )


def test_registry_creation_is_idempotent_and_absent_delete_is_harmless(
    hass: HomeAssistant,
) -> None:
    """Manager helpers use genuine registry idempotence."""
    manager = RepairsManager(hass, ENTRY_ID)
    manager.async_delete_issue(IssueCode.MIGRATION_FAILED)
    manager.async_report_migration_failure(MigrationFailureCategory.SCHEMA_MIGRATION)
    first = _issue(hass, ENTRY_ID, IssueCode.MIGRATION_FAILED)
    manager.async_report_migration_failure(MigrationFailureCategory.SCHEMA_MIGRATION)

    assert _issue(hass, ENTRY_ID, IssueCode.MIGRATION_FAILED) is first
    manager.async_delete_issue(IssueCode.MIGRATION_FAILED)
    manager.async_delete_issue(IssueCode.MIGRATION_FAILED)
    assert _issue(hass, ENTRY_ID, IssueCode.MIGRATION_FAILED) is None


def test_manager_rejects_empty_entry_scope(hass: HomeAssistant) -> None:
    """A manager cannot exist without a deterministic entry scope."""
    with pytest.raises(ValueError, match="config-entry ID must not be empty"):
        RepairsManager(hass, "")


def test_no_zone_issue_is_idempotent_and_clears_when_a_zone_exists(
    hass: HomeAssistant,
) -> None:
    """Final-zone removal stays actionable until a zone is configured."""
    manager = RepairsManager(hass, ENTRY_ID)

    manager.async_sync_zone_presence(has_zones=False)
    first = _issue(hass, ENTRY_ID, IssueCode.NO_ZONES_CONFIGURED)
    assert first is not None
    assert first.data == {"issue_code": "no_zones_configured"}

    manager.async_sync_zone_presence(has_zones=False)
    assert _issue(hass, ENTRY_ID, IssueCode.NO_ZONES_CONFIGURED) is first

    manager.async_sync_zone_presence(has_zones=True)
    assert _issue(hass, ENTRY_ID, IssueCode.NO_ZONES_CONFIGURED) is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_missing_entities_wait_for_guard_aggregate_and_recover(
    hass: HomeAssistant,
) -> None:
    """Missing references create one issue only after reconciliation."""
    entry = _entry(
        zone_data=_zone_data(sources=[_source(0, SENSORS[0]), _source(1, SENSORS[1])])
    )
    await _setup(hass, entry)

    assert entry.runtime_data.data.reconciling is True
    assert _issue(hass, ENTRY_ID, IssueCode.MISSING_ENTITY) is None

    await _finish_reconciliation(entry)
    issue = _issue(hass, ENTRY_ID, IssueCode.MISSING_ENTITY)
    assert issue is not None
    assert issue.data == {
        "issue_code": "missing_entity",
        "affected_reference_count": 3,
    }
    assert (
        len(
            [
                item
                for item in ir.async_get(hass).issues.values()
                if item.domain == DOMAIN and item.translation_key == "missing_entity"
            ]
        )
        == 1
    )

    _set_valid_states(hass)
    await _publish_entity_change(entry, THERMOSTAT, *SENSORS)
    assert _issue(hass, ENTRY_ID, IssueCode.MISSING_ENTITY) is None
    await _unload(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unknown_unavailable_and_disabled_observation_are_not_missing(
    hass: HomeAssistant,
) -> None:
    """Existing transient states and disabled evaluation create no issues."""
    hass.states.async_set(THERMOSTAT, STATE_UNKNOWN)
    hass.states.async_set(
        SENSORS[0],
        STATE_UNAVAILABLE,
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    )
    entry = _entry()
    await _setup(hass, entry)
    await _finish_reconciliation(entry)
    assert _issue(hass, ENTRY_ID, IssueCode.MISSING_ENTITY) is None
    assert _issue(hass, ENTRY_ID, IssueCode.INCOMPATIBLE_ENTITY) is None
    await _unload(hass, entry)

    disabled = _entry(entry_id="disabled-entry", observation_enabled=False)
    await _setup(hass, disabled)
    disabled.runtime_data.issue_manager.async_sync_entity_conditions(
        disabled.runtime_data.configuration
    )
    assert _issue(hass, "disabled-entry", IssueCode.MISSING_ENTITY) is None
    assert _issue(hass, "disabled-entry", IssueCode.INCOMPATIBLE_ENTITY) is None
    await _unload(hass, disabled)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_incompatible_sensor_is_reported_and_valid_binding_clears(
    hass: HomeAssistant,
) -> None:
    """A definitive device-class conflict is actionable and recoverable."""
    hass.states.async_set(THERMOSTAT, "heat")
    hass.states.async_set(
        SENSORS[0],
        "50",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.HUMIDITY},
    )
    entry = _entry()
    await _setup(hass, entry)
    assert _issue(hass, ENTRY_ID, IssueCode.INCOMPATIBLE_ENTITY) is None

    await _finish_reconciliation(entry)
    issue = _issue(hass, ENTRY_ID, IssueCode.INCOMPATIBLE_ENTITY)
    assert issue is not None
    assert issue.data == {
        "issue_code": "incompatible_entity",
        "affected_reference_count": 1,
    }

    hass.states.async_set(
        SENSORS[0],
        "20",
        {ATTR_DEVICE_CLASS: SensorDeviceClass.TEMPERATURE},
    )
    await _publish_entity_change(entry, SENSORS[0])
    assert _issue(hass, ENTRY_ID, IssueCode.INCOMPATIBLE_ENTITY) is None
    await _unload(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_missing_optional_climate_attribute_is_not_incompatible(
    hass: HomeAssistant,
) -> None:
    """Temporary absence of current_temperature is observation quality only."""
    hass.states.async_set(THERMOSTAT, "heat")
    climate_source = {
        **_source(0, THERMOSTAT),
        "attribute": "current_temperature",
    }
    zone = _zone_data(sources=[climate_source])
    zone["humidity_sources"] = [
        {
            "source_id": SOURCE_IDS[1],
            "entity_id": THERMOSTAT,
            "attribute": "current_humidity",
            "offset_pct": 0.0,
            "weight": 1.0,
            "priority": 0,
            "enabled": True,
        }
    ]
    entry = _entry(zone_data=zone)
    await _setup(hass, entry)
    await _finish_reconciliation(entry)

    assert _issue(hass, ENTRY_ID, IssueCode.MISSING_ENTITY) is None
    assert _issue(hass, ENTRY_ID, IssueCode.INCOMPATIBLE_ENTITY) is None
    await _unload(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_disabled_source_is_not_reported_missing(
    hass: HomeAssistant,
) -> None:
    """A deliberately disabled source is outside the Repairs evaluation set."""
    _set_valid_states(hass)
    disabled_source = _source(1, "sensor.deliberately_disabled")
    disabled_source["enabled"] = False
    entry = _entry(
        zone_data=_zone_data(sources=[_source(0, SENSORS[0]), disabled_source])
    )
    await _setup(hass, entry)
    await _finish_reconciliation(entry)

    assert _issue(hass, ENTRY_ID, IssueCode.MISSING_ENTITY) is None
    await _unload(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_migration_failure_is_bounded_then_clean_setup_clears(
    hass: HomeAssistant,
) -> None:
    """Failed persisted migration creates no runtime residue or side effects."""
    malformed: dict[str, object] = {
        "equipment_group": {
            **_parent_data()["equipment_group"],  # type: ignore[dict-item]
            "private_malformed_value": "do-not-copy",
        }
    }
    failed = _entry(version=2, data=malformed)
    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ) as forward,
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
        ) as service,
        pytest.raises(ConfigEntryError),
    ):
        await async_setup_entry(hass, failed)

    issue = _issue(hass, ENTRY_ID, IssueCode.MIGRATION_FAILED)
    assert issue is not None
    assert issue.data == {
        "issue_code": "migration_failed",
        "failure_category": "schema_migration",
    }
    assert "do-not-copy" not in json.dumps(issue.to_json())
    assert not hasattr(failed, "runtime_data")
    forward.assert_not_awaited()
    service.assert_not_awaited()

    _set_valid_states(hass)
    recovered = _entry()
    await _setup(hass, recovered)
    assert _issue(hass, ENTRY_ID, IssueCode.MIGRATION_FAILED) is None
    await _unload(hass, recovered)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unexpected_decode_value_error_reports_bounded_migration_issue(
    hass: HomeAssistant,
) -> None:
    """Unexpected decode boundary values still fail closed with a category."""
    entry = _entry()
    with (
        patch(
            "custom_components.intelligent_climate._decode_runtime_configuration",
            side_effect=ValueError("private decode detail"),
        ),
        pytest.raises(ConfigEntryError),
    ):
        await async_setup_entry(hass, entry)

    issue = _issue(hass, ENTRY_ID, IssueCode.MIGRATION_FAILED)
    assert issue is not None
    assert issue.data == {
        "issue_code": "migration_failed",
        "failure_category": "schema_validation",
    }
    assert "private decode detail" not in json.dumps(issue.to_json())


@pytest.mark.parametrize(
    "failure",
    [
        ConfigEntryNotReady("not ready"),
        ValueError("private runtime detail"),
    ],
)
@pytest.mark.usefixtures("enable_custom_integrations")
async def test_runtime_validation_failure_reports_issue_and_shuts_down(
    hass: HomeAssistant,
    failure: Exception,
) -> None:
    """Known first-refresh failures create a bounded issue before setup aborts."""
    _set_valid_states(hass)
    entry = _entry()
    with (
        patch(
            "custom_components.intelligent_climate.coordinator."
            "IntelligentClimateCoordinator.async_start",
            new_callable=AsyncMock,
            side_effect=failure,
        ),
        pytest.raises(ConfigEntryError),
    ):
        await async_setup_entry(hass, entry)

    issue = _issue(hass, ENTRY_ID, IssueCode.MIGRATION_FAILED)
    assert issue is not None
    assert issue.data == {
        "issue_code": "migration_failed",
        "failure_category": "runtime_validation",
    }
    assert not hasattr(entry, "runtime_data")


def test_store_write_hook_threshold_recovery_and_no_filesystem(
    hass: HomeAssistant,
) -> None:
    """The future Store hook reports counts without implementing Store I/O."""
    manager = RepairsManager(hass, ENTRY_ID)
    with patch("pathlib.Path.open") as path_open:
        manager.async_notify_store_write_failures(1)
        manager.async_notify_store_write_failures(2)
        assert _issue(hass, ENTRY_ID, IssueCode.STORE_WRITE_FAILED) is None

        manager.async_notify_store_write_failures(3)
        first = _issue(hass, ENTRY_ID, IssueCode.STORE_WRITE_FAILED)
        assert first is not None
        manager.async_notify_store_write_failures(7)
        assert _issue(hass, ENTRY_ID, IssueCode.STORE_WRITE_FAILED) is first
        manager.async_notify_store_write_failures(0)
        assert _issue(hass, ENTRY_ID, IssueCode.STORE_WRITE_FAILED) is None
    path_open.assert_not_called()


def test_store_write_hook_rejects_invalid_counts(hass: HomeAssistant) -> None:
    """The consecutive-failure boundary is strictly typed."""
    manager = RepairsManager(hass, ENTRY_ID)
    with pytest.raises(ValueError):
        manager.async_notify_store_write_failures(-1)
    with pytest.raises(ValueError):
        manager.async_notify_store_write_failures(True)


async def test_command_boundary_violation_is_suppressed_private_and_clearable(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A physical intent creates a payload-free issue and no service call."""
    manager = RepairsManager(hass, ENTRY_ID)
    sink = ObserveOnlyCommandSink(manager)
    payload = "set climate.private_thermostat to 99"
    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        new_callable=AsyncMock,
    ) as service:
        result = await sink.async_record_intent(
            ObservationIntent(source="private-decision-engine", description=payload)
        )

    assert result.status == "suppressed_observe_only"
    issue = _issue(hass, ENTRY_ID, IssueCode.COMMAND_BOUNDARY_VIOLATION)
    assert issue is not None
    serialized = json.dumps(issue.to_json())
    assert payload not in serialized
    assert "private-decision-engine" not in serialized
    assert payload not in caplog.text
    assert "reason_code=command_boundary_violation" in caplog.text
    service.assert_not_awaited()

    manager.async_prepare_clean_setup()
    assert _issue(hass, ENTRY_ID, IssueCode.COMMAND_BOUNDARY_VIOLATION) is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_runtime_command_sink_event_persists_unload_and_clears_next_setup(
    hass: HomeAssistant,
) -> None:
    """The coordinator-owned sink follows the documented event clear policy."""
    _set_valid_states(hass)
    entry = _entry()
    await _setup(hass, entry)
    with patch(
        "homeassistant.core.ServiceRegistry.async_call",
        new_callable=AsyncMock,
    ) as service:
        result = await entry.runtime_data.command_sink.async_record_intent(
            ObservationIntent("runtime", "unexpected nonempty intent")
        )
    assert result.status == "suppressed_observe_only"
    assert _issue(hass, ENTRY_ID, IssueCode.COMMAND_BOUNDARY_VIOLATION)
    service.assert_not_awaited()

    await _unload(hass, entry)
    assert _issue(hass, ENTRY_ID, IssueCode.COMMAND_BOUNDARY_VIOLATION)

    recovered = _entry()
    await _setup(hass, recovered)
    assert _issue(hass, ENTRY_ID, IssueCode.COMMAND_BOUNDARY_VIOLATION) is None
    await _unload(hass, recovered)


async def test_empty_command_intent_is_suppressed_without_violation(
    hass: HomeAssistant,
) -> None:
    """An empty boundary record is not a physical-command violation."""
    manager = RepairsManager(hass, ENTRY_ID)
    sink = ObserveOnlyCommandSink(manager)

    result = await sink.async_record_intent(ObservationIntent("", ""))
    assert result.status == "suppressed_observe_only"
    assert _issue(hass, ENTRY_ID, IssueCode.COMMAND_BOUNDARY_VIOLATION) is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_multiple_entries_are_independent_and_unload_keeps_event_issue(
    hass: HomeAssistant,
) -> None:
    """Entry scopes do not collide and unload does not erase persistent events."""
    _set_valid_states(hass)
    first = _entry(entry_id="entry-one")
    second = _entry(entry_id="entry-two")
    await _setup(hass, first)
    await _setup(hass, second)
    first.runtime_data.issue_manager.async_report_command_boundary_violation()
    second.runtime_data.issue_manager.async_report_command_boundary_violation()

    await _unload(hass, first)
    assert _issue(hass, "entry-one", IssueCode.COMMAND_BOUNDARY_VIOLATION)
    assert _issue(hass, "entry-two", IssueCode.COMMAND_BOUNDARY_VIOLATION)
    await _unload(hass, second)


def test_all_registry_entries_match_documented_issue_policy(
    hass: HomeAssistant,
) -> None:
    """Genuine issue entries are errors, non-fixable, and correctly persistent."""
    manager = RepairsManager(hass, ENTRY_ID)
    manager._async_sync_counted_issue(IssueCode.MISSING_ENTITY, 1)
    manager._async_sync_counted_issue(IssueCode.INCOMPATIBLE_ENTITY, 1)
    manager.async_sync_zone_presence(has_zones=False)
    manager.async_report_migration_failure(MigrationFailureCategory.SCHEMA_VALIDATION)
    manager.async_notify_store_write_failures(3)
    manager.async_report_command_boundary_violation()

    assert manager.active_issue_codes == tuple(sorted(IssueCode, key=str))
    for code in IssueCode:
        issue = _issue(hass, ENTRY_ID, code)
        assert issue is not None
        assert issue.severity is ir.IssueSeverity.ERROR
        assert issue.is_fixable is False
        assert issue.is_persistent is (
            code
            in {
                IssueCode.MIGRATION_FAILED,
                IssueCode.STORE_WRITE_FAILED,
                IssueCode.COMMAND_BOUNDARY_VIOLATION,
            }
        )
        assert issue.translation_key == code.value
        assert issue.translation_placeholders is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_every_issue_translation_resolves_without_fix_flow(
    hass: HomeAssistant,
) -> None:
    """Home Assistant loads each actionable English issue title and description."""
    translations = await async_get_translations(
        hass,
        "en",
        "issues",
        integrations={DOMAIN},
    )
    for code in IssueCode:
        prefix = f"component.{DOMAIN}.issues.{code.value}"
        assert translations[f"{prefix}.title"]
        assert translations[f"{prefix}.description"]
