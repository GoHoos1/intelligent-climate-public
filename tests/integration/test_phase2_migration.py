"""Test the crash-safe Phase 1 to Phase 2 migration transaction."""

from __future__ import annotations

import asyncio
import json
from copy import deepcopy
from dataclasses import replace
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest

pytest.importorskip("homeassistant", reason="CI installs Home Assistant 2026.7.")
pytest.importorskip(
    "pytest_homeassistant_custom_component",
    reason="CI installs the Home Assistant custom-component test harness.",
)

from homeassistant import config_entries
from homeassistant.config_entries import ConfigSubentryDataWithId
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate import (
    async_migrate_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.intelligent_climate.const import DOMAIN, SUBENTRY_TYPE_ZONE
from custom_components.intelligent_climate.migration import (
    PresentationTraceInitializationStatus,
    _Phase2RuntimeDataStore,
    _PresentationTraceDataStore,
    async_initialize_presentation_trace,
)
from custom_components.intelligent_climate.models import (
    PHASE2_CONFIG_MAJOR_VERSION,
    PHASE2_CONFIG_MINOR_VERSION,
    PHASE2_RUNTIME_STORE_SCHEMA_VERSION,
    PHASE2_ZONE_DATA_VERSION,
    PRESENTATION_TRACE_SCHEMA_VERSION,
    ControlExecutionState,
    ControlState,
    OperatingMode,
    decode_phase2_equipment_group_document,
    decode_phase2_options,
    decode_phase2_runtime_store_document,
    decode_phase2_zone_config,
    decode_presentation_trace_document,
    encode_phase2_runtime_store_document,
)
from custom_components.intelligent_climate.repairs import (
    IssueCode,
    MigrationFailureCategory,
    issue_id,
)

ROOT = Path(__file__).parents[2]
FIXTURE = ROOT / "tests" / "fixtures" / "phase_1_0_0_8_baseline.json"


def _baseline() -> dict[str, Any]:
    return cast(
        dict[str, Any],
        json.loads(FIXTURE.read_text(encoding="utf-8")),
    )


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    source = _baseline()
    config = source["config_entry"]
    zone = source["zone_subentry"]
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id=source["runtime_store"]["data"]["entry_id"],
        data=deepcopy(config["data"]),
        options=deepcopy(source["options"]),
        subentries_data=[
            ConfigSubentryDataWithId(
                data=deepcopy(zone),
                subentry_id="zone-subentry-1",
                subentry_type=SUBENTRY_TYPE_ZONE,
                title=zone["name"],
                unique_id=zone["zone_id"],
            )
        ],
        version=config["version"],
        minor_version=config["minor_version"],
        state=config_entries.ConfigEntryState.SETUP_IN_PROGRESS,
    )
    entry.add_to_hass(hass)
    return entry


async def _save_phase1_runtime(
    hass: HomeAssistant,
    *,
    data: object | None = None,
) -> None:
    source = _baseline()
    store: Store[dict[str, Any]] = Store(
        hass,
        source["runtime_store"]["envelope_version"],
        f"intelligent_climate.{source['runtime_store']['data']['entry_id']}",
        atomic_writes=True,
        minor_version=source["runtime_store"]["envelope_minor_version"],
    )
    await store.async_save(
        deepcopy(source["runtime_store"]["data"]) if data is None else cast(Any, data)
    )


def _set_live_states(hass: HomeAssistant) -> None:
    hass.states.async_set(
        "climate.dining_room",
        "heat",
        {
            "current_temperature": 21.0,
            "current_humidity": 50,
        },
    )


async def _stored_phase2_runtime(hass: HomeAssistant, entry_id: str) -> dict[str, Any]:
    raw = await _Phase2RuntimeDataStore(
        hass,
        f"intelligent_climate.{entry_id}",
    ).async_load()
    assert raw is not None
    return raw


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_accepted_0_0_8_migrates_to_observe_only_without_service_call(
    hass: HomeAssistant,
) -> None:
    """The accepted baseline commits all authoritative documents before setup."""
    _set_live_states(hass)
    entry = _entry(hass)
    await _save_phase1_runtime(hass)

    with (
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
        ) as service_call,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
    ):
        assert await async_migrate_entry(hass, entry)
        assert not hasattr(entry, "runtime_data")
        assert await async_setup_entry(hass, entry)

    assert (entry.version, entry.minor_version) == (
        PHASE2_CONFIG_MAJOR_VERSION,
        PHASE2_CONFIG_MINOR_VERSION,
    )
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
    zone = decode_phase2_zone_config(entry.subentries["zone-subentry-1"].data)
    runtime_raw = await _stored_phase2_runtime(hass, entry.entry_id)
    runtime = decode_phase2_runtime_store_document(runtime_raw)

    assert config.automation_enabled is False
    assert config.desired_operating_mode is OperatingMode.OBSERVE_ONLY
    assert options.observation.observation_enabled is True
    assert zone.zone.name == "Dining Room"
    assert zone.contact_bindings == ()
    assert entry.subentries["zone-subentry-1"].data["data_version"] == (
        PHASE2_ZONE_DATA_VERSION
    )
    assert runtime_raw["schema_version"] == PHASE2_RUNTIME_STORE_SCHEMA_VERSION
    assert runtime.control_intent.automation_enabled is False
    assert runtime.control_intent.active_control_armed is False
    assert runtime.control_intent.desired_operating_mode is OperatingMode.OBSERVE_ONLY
    assert runtime.command_journal == ()
    assert entry.runtime_data.data.control_state in {
        ControlState.RECONCILING,
        ControlState.OBSERVING,
    }
    service_call.assert_not_awaited()

    presentation_raw = await _PresentationTraceDataStore(
        hass,
        f"intelligent_climate.presentation.{entry.entry_id}",
    ).async_load()
    assert presentation_raw is not None
    assert presentation_raw["presentation_schema_version"] == (
        PRESENTATION_TRACE_SCHEMA_VERSION
    )
    presentation = decode_presentation_trace_document(
        presentation_raw,
        expected_entry_id=entry.entry_id,
        expected_equipment_group_id=runtime.equipment_group_id,
        expected_zone_ids=frozenset(runtime.zones),
    )
    assert all(not points for points in presentation.samples_by_zone.values())
    assert presentation.annotations == ()

    schedule: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"intelligent_climate.schedule.{entry.entry_id}",
        atomic_writes=True,
        minor_version=0,
    )
    assert await schedule.async_load() is None
    assert await async_unload_entry(hass, entry)
    assert (await _stored_phase2_runtime(hass, entry.entry_id))["schema_version"] == 2


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_failed_runtime_commit_resumes_from_safe_version2_config(
    hass: HomeAssistant,
) -> None:
    """A failure after config commit cannot start runtime and is retryable."""
    _set_live_states(hass)
    entry = _entry(hass)
    await _save_phase1_runtime(hass)

    with (
        patch(
            "custom_components.intelligent_climate.migration._async_save_verified",
            new_callable=AsyncMock,
            return_value=False,
        ),
        patch(
            "custom_components.intelligent_climate.coordinator."
            "IntelligentClimateCoordinator.async_start",
            new_callable=AsyncMock,
        ) as start,
    ):
        assert not await async_migrate_entry(hass, entry)
    start.assert_not_awaited()
    assert entry.version == PHASE2_CONFIG_MAJOR_VERSION
    assert entry.data["automation_enabled"] is False
    assert entry.data["desired_operating_mode"] == OperatingMode.OBSERVE_ONLY.value
    assert entry.subentries["zone-subentry-1"].data["data_version"] == 2
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN,
            issue_id(entry.entry_id, IssueCode.MIGRATION_FAILED),
        )
        is not None
    )

    with (
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
        ) as service_call,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
    ):
        assert await async_setup_entry(hass, entry)
    runtime = decode_phase2_runtime_store_document(
        await _stored_phase2_runtime(hass, entry.entry_id)
    )
    assert runtime.control_intent.active_control_armed is False
    assert runtime.command_journal == ()
    service_call.assert_not_awaited()
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_failed_zone_commit_resumes_mixed_zone_versions_before_setup(
    hass: HomeAssistant,
) -> None:
    """A parent-v2/zone-v1 interruption is completed before coordinator start."""
    _set_live_states(hass)
    entry = _entry(hass)
    await _save_phase1_runtime(hass)

    with patch.object(
        hass.config_entries,
        "async_update_subentry",
        return_value=False,
    ):
        assert not await async_migrate_entry(hass, entry)
    assert entry.version == PHASE2_CONFIG_MAJOR_VERSION
    assert entry.subentries["zone-subentry-1"].data["data_version"] == 1

    with (
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
        ) as service_call,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
    ):
        assert await async_setup_entry(hass, entry)
    assert entry.subentries["zone-subentry-1"].data["data_version"] == 2
    service_call.assert_not_awaited()
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_phase1_runtime_is_quarantined_before_empty_safe_migration(
    hass: HomeAssistant,
) -> None:
    """Invalid nonauthoritative history is preserved and never hydrated."""
    _set_live_states(hass)
    entry = _entry(hass)
    invalid = deepcopy(_baseline()["runtime_store"]["data"])
    invalid["entry_id"] = "wrong-entry"
    await _save_phase1_runtime(hass, data=invalid)

    with (
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
        ) as service_call,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
    ):
        assert await async_migrate_entry(hass, entry)
        assert await async_setup_entry(hass, entry)

    quarantine: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"intelligent_climate.{entry.entry_id}.quarantine",
        atomic_writes=True,
    )
    quarantined = await quarantine.async_load()
    assert quarantined is not None
    assert quarantined["reason_code"] == "invalid_nonauthoritative_store"
    assert quarantined["data"]["entry_id"] == "wrong-entry"
    runtime = decode_phase2_runtime_store_document(
        await _stored_phase2_runtime(hass, entry.entry_id)
    )
    assert runtime.source_baselines == {}
    assert runtime.decisions == ()
    assert runtime.command_journal == ()
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN,
            issue_id(entry.entry_id, IssueCode.MIGRATION_FAILED),
        )
        is not None
    )
    service_call.assert_not_awaited()
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_future_runtime_store_is_preserved_and_blocks_config_commit(
    hass: HomeAssistant,
) -> None:
    """A future authoritative envelope is never overwritten or downgraded."""
    entry = _entry(hass)
    future_payload = {"schema_version": 99, "future": True}
    future: Store[dict[str, Any]] = Store(
        hass,
        3,
        f"intelligent_climate.{entry.entry_id}",
        atomic_writes=True,
        minor_version=0,
    )
    await future.async_save(future_payload)

    assert not await async_migrate_entry(hass, entry)

    assert (entry.version, entry.minor_version) == (1, 1)
    assert await future.async_load() == future_payload
    assert not hasattr(entry, "runtime_data")


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unexpected_schedule_store_is_preserved_and_blocks_migration(
    hass: HomeAssistant,
) -> None:
    """No pre-Phase-2 schedule can be silently trusted or replaced."""
    entry = _entry(hass)
    await _save_phase1_runtime(hass)
    schedule_payload = {"schedule_schema_version": 1, "unexpected": True}
    schedule: Store[dict[str, Any]] = Store(
        hass,
        1,
        f"intelligent_climate.schedule.{entry.entry_id}",
        atomic_writes=True,
        minor_version=0,
    )
    await schedule.async_save(schedule_payload)

    assert not await async_migrate_entry(hass, entry)

    assert entry.version == 1
    assert await schedule.async_load() == schedule_payload


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_presentation_initialization_failure_never_rolls_back_observation(
    hass: HomeAssistant,
) -> None:
    """Auxiliary chart persistence can fail without blocking Observe Only."""
    _set_live_states(hass)
    entry = _entry(hass)
    await _save_phase1_runtime(hass)
    assert await async_migrate_entry(hass, entry)

    from custom_components.intelligent_climate import migration

    real_save = migration._async_save_verified

    async def _fail_presentation(store: Store[Any], data: dict[str, Any]) -> bool:
        if isinstance(store, _PresentationTraceDataStore):
            return False
        return await real_save(store, data)

    with (
        patch(
            "custom_components.intelligent_climate.migration._async_save_verified",
            side_effect=_fail_presentation,
        ),
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
        ) as service_call,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
    ):
        assert await async_setup_entry(hass, entry)

    assert entry.runtime_data.data.control_state in {
        ControlState.RECONCILING,
        ControlState.OBSERVING,
    }
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN,
            issue_id(entry.entry_id, IssueCode.MIGRATION_FAILED),
        )
        is not None
    )
    service_call.assert_not_awaited()
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_interrupted_v2_entry_quarantines_invalid_legacy_runtime(
    hass: HomeAssistant,
) -> None:
    """Setup recovers a parent-v2/runtime-v1 interruption without control."""
    _set_live_states(hass)
    entry = _entry(hass)
    await _save_phase1_runtime(hass)
    assert await async_migrate_entry(hass, entry)

    invalid_legacy = deepcopy(_baseline()["runtime_store"]["data"])
    invalid_legacy["entry_id"] = "wrong-entry"
    await _save_phase1_runtime(hass, data=invalid_legacy)

    with (
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
        ) as service_call,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
    ):
        assert await async_setup_entry(hass, entry)

    runtime = decode_phase2_runtime_store_document(
        await _stored_phase2_runtime(hass, entry.entry_id)
    )
    assert runtime.control_intent.active_control_armed is False
    assert runtime.command_journal == ()
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN,
            issue_id(entry.entry_id, IssueCode.MIGRATION_FAILED),
        )
        is not None
    )
    service_call.assert_not_awaited()
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_phase2_runtime_is_replaced_with_empty_safe_state(
    hass: HomeAssistant,
) -> None:
    """Setup rejects persisted active intent and rebuilds Observe Only state."""
    _set_live_states(hass)
    entry = _entry(hass)
    await _save_phase1_runtime(hass)
    assert await async_migrate_entry(hass, entry)
    raw = await _stored_phase2_runtime(hass, entry.entry_id)
    intent = cast(dict[str, Any], raw["control_intent"])
    intent["active_control_armed"] = True
    await _Phase2RuntimeDataStore(
        hass,
        f"intelligent_climate.{entry.entry_id}",
    ).async_save(raw)

    with (
        patch(
            "homeassistant.core.ServiceRegistry.async_call",
            new_callable=AsyncMock,
        ) as service_call,
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            new_callable=AsyncMock,
        ),
    ):
        assert await async_setup_entry(hass, entry)

    recovered = decode_phase2_runtime_store_document(
        await _stored_phase2_runtime(hass, entry.entry_id)
    )
    assert recovered.control_intent.active_control_armed is False
    assert recovered.control_intent.desired_operating_mode is OperatingMode.OBSERVE_ONLY
    assert recovered.command_journal == ()
    service_call.assert_not_awaited()
    assert await async_unload_entry(hass, entry)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_presentation_trace_load_recovery_and_future_version_boundaries(
    hass: HomeAssistant,
) -> None:
    """Auxiliary traces load, recover, skip, and preserve future envelopes."""
    entry = _entry(hass)
    await _save_phase1_runtime(hass)
    assert await async_migrate_entry(hass, entry)
    runtime = decode_phase2_runtime_store_document(
        await _stored_phase2_runtime(hass, entry.entry_id)
    )

    assert (
        await async_initialize_presentation_trace(
            hass,
            entry_id=entry.entry_id,
            runtime=runtime,
        )
        is PresentationTraceInitializationStatus.CREATED
    )
    assert (
        await async_initialize_presentation_trace(
            hass,
            entry_id=entry.entry_id,
            runtime=runtime,
        )
        is PresentationTraceInitializationStatus.LOADED
    )

    presentation_key = f"intelligent_climate.presentation.{entry.entry_id}"
    await _PresentationTraceDataStore(hass, presentation_key).async_save(
        {"presentation_schema_version": 1, "invalid": True}
    )
    assert (
        await async_initialize_presentation_trace(
            hass,
            entry_id=entry.entry_id,
            runtime=runtime,
        )
        is PresentationTraceInitializationStatus.RECOVERED
    )

    empty_runtime = replace(runtime, zones=MappingProxyType({}))
    assert (
        await async_initialize_presentation_trace(
            hass,
            entry_id="empty-presentation",
            runtime=empty_runtime,
        )
        is PresentationTraceInitializationStatus.SKIPPED_NO_ZONES
    )

    future_entry_id = "future-presentation"
    future_store: Store[dict[str, Any]] = Store(
        hass,
        2,
        f"intelligent_climate.presentation.{future_entry_id}",
        atomic_writes=True,
    )
    future_payload = {"future": True}
    await future_store.async_save(future_payload)
    assert (
        await async_initialize_presentation_trace(
            hass,
            entry_id=future_entry_id,
            runtime=replace(runtime, entry_id=future_entry_id),
        )
        is PresentationTraceInitializationStatus.UNSUPPORTED
    )
    assert await future_store.async_load() == future_payload


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_migration_safety_validators_reject_active_or_mismatched_state(
    hass: HomeAssistant,
) -> None:
    """Hand-constructed runtime state cannot bypass Task 8 safety gates."""
    entry = _entry(hass)
    await _save_phase1_runtime(hass)
    assert await async_migrate_entry(hass, entry)
    runtime = decode_phase2_runtime_store_document(
        await _stored_phase2_runtime(hass, entry.entry_id)
    )
    config = decode_phase2_equipment_group_document(entry.data)

    from custom_components.intelligent_climate import migration
    from custom_components.intelligent_climate.models import SchemaValidationError

    with pytest.raises(SchemaValidationError, match="Observe Only"):
        migration._require_migration_safe_config(
            replace(config, automation_enabled=True)
        )

    zone_id, zone_state = next(iter(runtime.zones.items()))
    active_runtime = replace(
        runtime,
        zones=MappingProxyType(
            {
                zone_id: replace(
                    zone_state,
                    control_state=ControlExecutionState.MANUAL_IDLE,
                )
            }
        ),
    )
    with pytest.raises(SchemaValidationError, match="active-control"):
        migration._require_migration_safe_runtime(active_runtime)

    with pytest.raises(SchemaValidationError, match="entry_id"):
        migration._validate_runtime_identity(
            runtime,
            entry_id="wrong-entry",
            group_id=str(runtime.equipment_group_id),
            zone_ids=frozenset(str(item) for item in runtime.zones),
            source_ids=None,
        )
    with pytest.raises(ValueError, match="timezone-aware"):
        migration._now(lambda: datetime(2026, 7, 30))

    encoded = dict(encode_phase2_runtime_store_document(runtime))
    encoded["command_journal"] = [{"unsafe": True}]
    unsafe = decode_phase2_runtime_store_document(encoded)
    with pytest.raises(SchemaValidationError, match="empty Observe Only"):
        migration._require_migration_safe_runtime(unsafe)
    assert (
        migration.Phase2MigrationError(
            MigrationFailureCategory.STORE_LOAD,
            "bounded",
        ).category
        is MigrationFailureCategory.STORE_LOAD
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_presentation_trace_cancellation_and_io_failures_are_bounded(
    hass: HomeAssistant,
) -> None:
    """Cancellation propagates while ordinary auxiliary I/O failures do not."""
    entry = _entry(hass)
    await _save_phase1_runtime(hass)
    assert await async_migrate_entry(hass, entry)
    runtime = decode_phase2_runtime_store_document(
        await _stored_phase2_runtime(hass, entry.entry_id)
    )

    with (
        patch.object(
            _PresentationTraceDataStore,
            "async_load",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_initialize_presentation_trace(
            hass,
            entry_id=entry.entry_id,
            runtime=runtime,
        )

    with patch.object(
        _PresentationTraceDataStore,
        "async_load",
        new_callable=AsyncMock,
        side_effect=OSError,
    ):
        assert (
            await async_initialize_presentation_trace(
                hass,
                entry_id=entry.entry_id,
                runtime=runtime,
            )
            is PresentationTraceInitializationStatus.FAILED
        )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_runtime_preflight_cancellation_and_store_failures_fail_closed(
    hass: HomeAssistant,
) -> None:
    """Authoritative preflight propagates cancellation and bounds I/O errors."""
    entry = _entry(hass)

    with (
        patch.object(
            _Phase2RuntimeDataStore,
            "async_load",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await async_migrate_entry(hass, entry)

    with patch.object(
        _Phase2RuntimeDataStore,
        "async_load",
        new_callable=AsyncMock,
        side_effect=OSError,
    ):
        assert not await async_migrate_entry(hass, entry)
    assert entry.version == 1

    phase2_payload = {"schema_version": 2, "existing": True}
    with patch.object(
        _Phase2RuntimeDataStore,
        "async_load",
        new_callable=AsyncMock,
        return_value=phase2_payload,
    ):
        assert not await async_migrate_entry(hass, entry)
    assert entry.version == 1


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_schedule_preflight_and_quarantine_io_boundaries(
    hass: HomeAssistant,
) -> None:
    """Future schedules and unverified quarantines are never overwritten."""
    from custom_components.intelligent_climate import migration

    future_entry_id = "future-schedule"
    future_store: Store[dict[str, Any]] = Store(
        hass,
        2,
        f"intelligent_climate.schedule.{future_entry_id}",
        atomic_writes=True,
    )
    future_payload = {"future": True}
    await future_store.async_save(future_payload)
    with pytest.raises(
        migration.Phase2MigrationError,
        match="future schedule",
    ) as raised:
        await migration._async_require_absent_schedule_store(
            hass,
            future_entry_id,
        )
    assert raised.value.category is MigrationFailureCategory.STORE_VERSION
    assert await future_store.async_load() == future_payload

    with (
        patch.object(
            Store,
            "async_load",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await migration._async_require_absent_schedule_store(
            hass,
            "cancelled-schedule",
        )
    with (
        patch.object(
            Store,
            "async_load",
            new_callable=AsyncMock,
            side_effect=OSError,
        ),
        pytest.raises(
            migration.Phase2MigrationError,
            match="could not be inspected",
        ),
    ):
        await migration._async_require_absent_schedule_store(
            hass,
            "failed-schedule",
        )

    primary: Store[dict[str, Any]] = Store(
        hass,
        1,
        "intelligent_climate.quarantine-source",
        atomic_writes=True,
    )
    with patch(
        "custom_components.intelligent_climate.migration._async_save_verified",
        new_callable=AsyncMock,
        return_value=False,
    ):
        assert not await migration._async_quarantine(
            hass,
            key="intelligent_climate.quarantine-source",
            envelope_version=1,
            raw={"invalid": True},
            reason_code="invalid",
            remove_primary=primary,
            now=datetime.now().astimezone(),
        )
    with (
        patch(
            "custom_components.intelligent_climate.migration._async_save_verified",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await migration._async_quarantine(
            hass,
            key="intelligent_climate.quarantine-cancelled",
            envelope_version=1,
            raw={"invalid": True},
            reason_code="invalid",
            remove_primary=primary,
            now=datetime.now().astimezone(),
        )
    with patch(
        "custom_components.intelligent_climate.migration._async_save_verified",
        new_callable=AsyncMock,
        side_effect=OSError,
    ):
        assert not await migration._async_quarantine(
            hass,
            key="intelligent_climate.quarantine-failed",
            envelope_version=1,
            raw={"invalid": True},
            reason_code="invalid",
            remove_primary=primary,
            now=datetime.now().astimezone(),
        )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_runtime_write_verification_and_identity_failures_are_bounded(
    hass: HomeAssistant,
) -> None:
    """Read-back and identity failures never publish an unsafe runtime."""
    entry = _entry(hass)
    await _save_phase1_runtime(hass)
    assert await async_migrate_entry(hass, entry)
    raw = await _stored_phase2_runtime(hass, entry.entry_id)
    runtime = decode_phase2_runtime_store_document(raw)

    from custom_components.intelligent_climate import migration
    from custom_components.intelligent_climate.models import SchemaValidationError

    expected_zones = frozenset(str(item) for item in runtime.zones)
    with (
        patch(
            "custom_components.intelligent_climate.migration._async_save_verified",
            new_callable=AsyncMock,
            return_value=True,
        ),
        patch.object(
            _Phase2RuntimeDataStore,
            "async_load",
            new_callable=AsyncMock,
            return_value={"different": True},
        ),
        pytest.raises(migration.Phase2MigrationError, match="did not match"),
    ):
        await migration._async_save_phase2_runtime(
            hass,
            entry_id=entry.entry_id,
            encoded=raw,
            expected_group_id=str(runtime.equipment_group_id),
            expected_zone_ids=expected_zones,
        )
    with (
        patch(
            "custom_components.intelligent_climate.migration._async_save_verified",
            new_callable=AsyncMock,
            side_effect=OSError,
        ),
        pytest.raises(migration.Phase2MigrationError, match="write failed"),
    ):
        await migration._async_save_phase2_runtime(
            hass,
            entry_id=entry.entry_id,
            encoded=raw,
            expected_group_id=str(runtime.equipment_group_id),
            expected_zone_ids=expected_zones,
        )
    with (
        patch(
            "custom_components.intelligent_climate.migration._async_save_verified",
            new_callable=AsyncMock,
            side_effect=asyncio.CancelledError,
        ),
        pytest.raises(asyncio.CancelledError),
    ):
        await migration._async_save_phase2_runtime(
            hass,
            entry_id=entry.entry_id,
            encoded=raw,
            expected_group_id=str(runtime.equipment_group_id),
            expected_zone_ids=expected_zones,
        )

    with pytest.raises(SchemaValidationError, match="equipment_group_id"):
        migration._validate_runtime_identity(
            runtime,
            entry_id=runtime.entry_id,
            group_id="wrong-group",
            zone_ids=expected_zones,
            source_ids=None,
        )
    with pytest.raises(SchemaValidationError, match="every configured zone"):
        migration._validate_runtime_identity(
            runtime,
            entry_id=runtime.entry_id,
            group_id=str(runtime.equipment_group_id),
            zone_ids=frozenset(),
            source_ids=None,
        )
    with pytest.raises(SchemaValidationError, match="unknown source"):
        migration._validate_runtime_identity(
            runtime,
            entry_id=runtime.entry_id,
            group_id=str(runtime.equipment_group_id),
            zone_ids=expected_zones,
            source_ids=frozenset(),
        )
    with pytest.raises(SchemaValidationError, match="future baseline"):
        migration._validate_runtime_identity(
            replace(
                runtime,
                saved_at=datetime(2000, 1, 1).astimezone(),
            ),
            entry_id=runtime.entry_id,
            group_id=str(runtime.equipment_group_id),
            zone_ids=expected_zones,
            source_ids=frozenset(str(item) for item in runtime.source_baselines),
        )

    with patch(
        "custom_components.intelligent_climate.migration._async_save_verified",
        new_callable=AsyncMock,
        side_effect=OSError,
    ):
        assert (
            await async_initialize_presentation_trace(
                hass,
                entry_id="presentation-save-failure",
                runtime=replace(runtime, entry_id="presentation-save-failure"),
            )
            is PresentationTraceInitializationStatus.FAILED
        )
