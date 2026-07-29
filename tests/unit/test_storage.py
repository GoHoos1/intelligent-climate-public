"""Test debounced nonauthoritative runtime Store behavior."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import UnsupportedStorageVersionError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.storage import Store
from homeassistant.util.file import WriteError

from custom_components.intelligent_climate.activity import ActivityPublisher
from custom_components.intelligent_climate.history import ActivityHistory
from custom_components.intelligent_climate.models import (
    DEFAULT_OPTIONS,
    ActivityReason,
    ActivitySeverity,
    ActivityType,
    ControlState,
    EntryObservationSnapshot,
    EntryRuntimeConfiguration,
    EquipmentGroupConfig,
    EquipmentGroupId,
    EquipmentRelationship,
    EquipmentType,
    ObservationSourceId,
    RuntimeConfigurationState,
    SourceBaseline,
    TemperatureSource,
    ZoneConfig,
    ZoneId,
    encode_runtime_store_document,
)
from custom_components.intelligent_climate.repairs import (
    IssueCode,
    MigrationFailureCategory,
    RepairsManager,
    issue_id,
)
from custom_components.intelligent_climate.storage import (
    STORE_DEBOUNCE_SECONDS,
    STORE_FINAL_SAVE_TIMEOUT_SECONDS,
    STORE_MINOR_VERSION,
    RuntimeStore,
    StoreLoadStatus,
    _async_save_verified,
    _RuntimeDataStore,
)

NOW = datetime(2026, 7, 27, 12, tzinfo=UTC)
GROUP_ID = EquipmentGroupId.parse("b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3")
ZONE_ID = ZoneId.parse("99246285-6f02-4e8a-94ed-bdfd4a5e62c4")
SOURCE_ID = ObservationSourceId.parse("f15f73b1-ea59-4b28-819f-7b99acf065bf")


def _configuration(*, with_zone: bool = False) -> EntryRuntimeConfiguration:
    zones = (
        (
            ZoneConfig(
                zone_id=ZONE_ID,
                name="Zone",
                thermostat_entity_ids=("climate.main",),
                temperature_sources=(
                    TemperatureSource(
                        source_id=SOURCE_ID,
                        entity_id="sensor.temperature",
                        attribute=None,
                        offset_c=0.0,
                        weight=1.0,
                        priority=0,
                        enabled=True,
                    ),
                ),
                humidity_sources=(),
                window_door_entity_ids=(),
                occupancy_entity_ids=(),
                stage_entity_ids=(),
                fan_entity_ids=(),
            ),
        )
        if with_zone
        else ()
    )
    return EntryRuntimeConfiguration(
        equipment_group=EquipmentGroupConfig(
            equipment_group_id=GROUP_ID,
            name="Main",
            equipment_type=EquipmentType.CONVENTIONAL,
            relationship=EquipmentRelationship.SINGLE_SYSTEM,
            thermostats=(),
            shared_policy=None,
        ),
        zones=zones,
        options=DEFAULT_OPTIONS,
        state=(
            RuntimeConfigurationState.CONFIGURED
            if with_zone
            else RuntimeConfigurationState.AWAITING_FIRST_ZONE
        ),
    )


def _coordinator() -> Any:
    return SimpleNamespace(
        data=EntryObservationSnapshot(
            entry_id="entry-1",
            equipment_group_id=GROUP_ID,
            control_state=ControlState.INITIALIZING,
            reconciling=False,
            revision=1,
            thermostats=(),
            zones=(),
            calculated_at=NOW,
        ),
        source_baselines={},
    )


def _fake_store() -> Mock:
    store = Mock()
    store.key = "intelligent_climate.entry-1"
    store.version = 1
    store.minor_version = STORE_MINOR_VERSION
    store.migrated_from = None
    store.migration_payload = None
    store.async_load = AsyncMock(return_value=None)

    async def _save(data: object) -> None:
        store.async_load.return_value = deepcopy(data)

    store.successful_save_side_effect = _save
    store.async_save = AsyncMock(side_effect=_save)
    store.async_remove = AsyncMock()
    return store


def _runtime(
    hass: HomeAssistant,
    fake_store: Mock,
    *,
    with_zone: bool = False,
) -> tuple[RuntimeStore, ActivityPublisher, ActivityHistory]:
    history = ActivityHistory(max_records=500, max_age_days=30)
    repairs = RepairsManager(hass, "entry-1")
    quarantine_store = _fake_store()
    quarantine_store.key = "intelligent_climate.entry-1.quarantine"
    fake_store.hass = hass
    quarantine_store.hass = hass
    with (
        patch(
            "custom_components.intelligent_climate.storage._RuntimeDataStore",
            return_value=fake_store,
        ) as store_class,
        patch(
            "custom_components.intelligent_climate.storage.Store",
            return_value=quarantine_store,
        ) as quarantine_class,
    ):
        runtime = RuntimeStore(
            hass,
            entry_id="entry-1",
            configuration=_configuration(with_zone=with_zone),
            history=history,
            repairs=repairs,
            now_fn=lambda: NOW,
        )
    store_class.assert_called_once_with(
        hass,
        "intelligent_climate.entry-1",
    )
    quarantine_class.assert_called_once_with(
        hass,
        1,
        "intelligent_climate.entry-1.quarantine",
        atomic_writes=True,
    )
    publisher = ActivityPublisher(
        hass,
        entry_id="entry-1",
        equipment_group_id=GROUP_ID,
        history=history,
        now_fn=lambda: NOW,
    )
    repairs.set_activity_reporter(publisher)
    runtime.attach_runtime(cast(Any, _coordinator()), publisher)
    return runtime, publisher, history


def _activity(publisher: ActivityPublisher) -> None:
    publisher.record(
        activity_type=ActivityType.LIFECYCLE,
        reason_code=ActivityReason.SETUP_COMPLETED,
        severity=ActivitySeverity.INFO,
        explanation="Intelligent Climate observation setup completed.",
    )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_store_key_version_atomic_load_and_schema_complete_save(
    hass: HomeAssistant,
) -> None:
    """Store v1 uses the exact key, atomic writes, and an empty journal."""
    fake = _fake_store()
    runtime, publisher, history = _runtime(hass, fake)

    await runtime.async_load()
    _activity(publisher)
    await runtime._async_attempt_save(last_clean_shutdown=False)

    assert runtime.key == "intelligent_climate.entry-1"
    assert runtime.version == 1
    assert runtime.minor_version == STORE_MINOR_VERSION
    assert STORE_FINAL_SAVE_TIMEOUT_SECONDS == 5.0
    assert runtime.loaded is True
    saved = fake.async_save.await_args.args[0]
    assert saved["schema_version"] == 1
    assert saved["entry_id"] == "entry-1"
    assert saved["equipment_group_id"] == str(GROUP_ID)
    assert saved["command_journal"] == []
    assert len(saved["decisions"]) == 1
    assert saved["zones"] == {}
    assert saved["source_baselines"] == {}

    await runtime.async_shutdown()
    publisher.close()
    assert history.listener_count == 0


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_store_envelope_1_1_migrates_to_1_2_without_inner_schema_bump(
    hass: HomeAssistant,
) -> None:
    """The released Store envelope is canonically migrated within Store major 1."""
    runtime, publisher, _history = _runtime(hass, _fake_store())
    document = runtime._document(
        cast(Any, _coordinator()),
        saved_at=NOW,
        last_clean_shutdown=True,
    )
    raw = dict(encode_runtime_store_document(document))
    store = _RuntimeDataStore(hass, "intelligent_climate.migration-test")

    migrated = await store._async_migrate_func(1, 1, raw)

    assert store.version == 1
    assert store.minor_version == 2
    assert store.migrated_from == (1, 1)
    assert migrated["schema_version"] == 1
    assert migrated["command_journal"] == []
    assert migrated == raw
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_verified_save_detects_store_write_error_hidden_by_home_assistant(
    hass: HomeAssistant,
) -> None:
    """Read-back detects a disk failure that Store.async_save logs and swallows."""
    store: Store[dict[str, Any]] = Store(
        hass,
        1,
        "intelligent_climate.write-verification-test",
        atomic_writes=True,
    )
    payload = {"saved_at": NOW.isoformat(), "value": 1}

    with patch.object(
        store,
        "_async_write_data",
        new_callable=AsyncMock,
        side_effect=WriteError("simulated write failure"),
    ):
        assert not await _async_save_verified(store, payload)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_verified_save_does_not_mistake_final_write_queue_for_disk_commit(
    hass: HomeAssistant,
) -> None:
    """Stopping-state data remains deferred and is not read back from memory."""
    store = _fake_store()
    store.hass = hass
    previous_state = hass.state
    hass.set_state(CoreState.stopping)
    try:
        assert (
            await _async_save_verified(
                cast(Store[dict[str, Any]], store),
                {"saved_at": NOW.isoformat()},
            )
            is None
        )
    finally:
        hass.set_state(previous_state)

    store.async_save.assert_awaited_once()
    store.async_load.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_runtime_counts_unverified_store_save_as_write_failure(
    hass: HomeAssistant,
) -> None:
    """A save returning normally without matching persisted data is a failure."""
    store = _fake_store()
    store.async_save = AsyncMock()
    runtime, publisher, _history = _runtime(hass, store)

    assert not await runtime._async_attempt_save(last_clean_shutdown=False)

    assert runtime.consecutive_write_failures == 1
    assert runtime.last_successful_save is None
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_material_activity_uses_30_second_debounce_and_five_minute_cap(
    hass: HomeAssistant,
) -> None:
    """Activity schedules one save no earlier than debounce and by max dirty age."""
    runtime, publisher, _history = _runtime(hass, _fake_store())
    loop_now = hass.loop.time()

    _activity(publisher)

    assert runtime.dirty is True
    assert runtime._save_handle is not None
    assert runtime._save_handle.when() == pytest.approx(
        loop_now + STORE_DEBOUNCE_SECONDS,
        abs=0.2,
    )

    runtime._dirty_since = hass.loop.time() - 299.5
    _activity(publisher)
    assert runtime._save_handle is not None
    assert runtime._save_handle.when() <= hass.loop.time() + 0.6

    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_only_one_writer_task_runs_per_entry(hass: HomeAssistant) -> None:
    """A second timer callback cannot create a concurrent Store writer."""
    fake = _fake_store()
    release = asyncio.Event()

    async def _wait_save(_data: object) -> None:
        await release.wait()
        fake.async_load.return_value = deepcopy(_data)

    fake.async_save.side_effect = _wait_save
    runtime, publisher, _history = _runtime(hass, fake)
    _activity(publisher)

    runtime._start_write_task()
    first_task = runtime.write_task
    runtime._start_write_task()

    assert first_task is not None
    assert runtime.write_task is first_task
    release.set()
    await first_task
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_bounded_retry_failure_threshold_and_single_recovery_transition(
    hass: HomeAssistant,
) -> None:
    """Failures retry with a cap, create Repairs at three, then recover once."""
    fake = _fake_store()
    fake.async_save.side_effect = OSError("private path and exception text")
    runtime, publisher, history = _runtime(hass, fake)
    _activity(publisher)

    for expected in (1, 2, 3):
        assert not await runtime._async_attempt_save(last_clean_shutdown=False)
        assert runtime.consecutive_write_failures == expected
        if runtime._save_handle is not None:
            assert runtime._save_handle.when() - hass.loop.time() <= 120.1
            runtime._save_handle.cancel()
            runtime._save_handle = None

    registry = ir.async_get(hass)
    assert (
        registry.async_get_issue(
            "intelligent_climate",
            issue_id("entry-1", IssueCode.STORE_WRITE_FAILED),
        )
        is not None
    )
    assert (
        sum(
            record.activity_type is ActivityType.STORE_WRITE_FAILED
            for record in history.records
        )
        == 1
    )

    fake.async_save.side_effect = fake.successful_save_side_effect
    assert await runtime._async_attempt_save(last_clean_shutdown=False)
    assert runtime.consecutive_write_failures == 0
    assert runtime.last_successful_save == NOW
    assert (
        registry.async_get_issue(
            "intelligent_climate",
            issue_id("entry-1", IssueCode.STORE_WRITE_FAILED),
        )
        is None
    )
    assert (
        sum(
            record.activity_type is ActivityType.STORE_WRITE_RECOVERED
            for record in history.records
        )
        == 1
    )
    assert all(
        "private path" not in record.explanation
        and "exception text" not in record.explanation
        for record in history.records
    )

    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_final_save_timeout_is_bounded_and_cancels_writer(
    hass: HomeAssistant,
) -> None:
    """A stuck writer cannot block unload or survive the five-second boundary."""
    fake = _fake_store()
    never = asyncio.Event()

    async def _never_save(_data: object) -> None:
        await never.wait()

    fake.async_save.side_effect = _never_save
    runtime, publisher, _history = _runtime(hass, fake)
    _activity(publisher)
    runtime._start_write_task()

    with patch(
        "custom_components.intelligent_climate.storage."
        "STORE_FINAL_SAVE_TIMEOUT_SECONDS",
        0.01,
    ):
        await runtime.async_final_save()

    assert runtime.write_task is None
    assert runtime.consecutive_write_failures == 1
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_invalid_and_failed_store_loads_are_empty_and_nonauthoritative(
    hass: HomeAssistant,
) -> None:
    """Identity mismatches and load errors safely restore an empty history."""
    invalid_fake = _fake_store()
    invalid_runtime, invalid_publisher, invalid_history = _runtime(
        hass,
        invalid_fake,
    )
    document = invalid_runtime._document(
        cast(Any, _coordinator()),
        saved_at=NOW,
        last_clean_shutdown=False,
    )
    raw = dict(encode_runtime_store_document(document))
    raw["entry_id"] = "different-entry"
    invalid_fake.async_load.return_value = raw

    await invalid_runtime.async_load()

    assert invalid_runtime.loaded is True
    assert invalid_runtime.load_status is StoreLoadStatus.QUARANTINED
    assert invalid_runtime.quarantine_present is True
    assert invalid_runtime.requires_repair is True
    invalid_fake.async_remove.assert_awaited_once()
    assert invalid_history.records == ()
    await invalid_runtime.async_shutdown()
    invalid_publisher.close()

    failed_fake = _fake_store()
    failed_fake.async_load.side_effect = OSError("private exception text")
    failed_runtime, failed_publisher, failed_history = _runtime(hass, failed_fake)

    await failed_runtime.async_load()

    assert failed_runtime.loaded is True
    assert failed_runtime.load_status is StoreLoadStatus.FAILED
    assert failed_runtime.read_only is True
    assert failed_history.records == ()
    await failed_runtime.async_shutdown()
    failed_publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_quarantine_is_verified_before_invalid_primary_is_removed(
    hass: HomeAssistant,
) -> None:
    """A silently failed quarantine write cannot destroy the primary payload."""
    primary = _fake_store()
    runtime, publisher, _history = _runtime(hass, primary)
    document = runtime._document(
        cast(Any, _coordinator()),
        saved_at=NOW,
        last_clean_shutdown=False,
    )
    raw = dict(encode_runtime_store_document(document))
    raw["entry_id"] = "different-entry"
    primary.async_load.return_value = raw
    quarantine = cast(Any, runtime)._quarantine_store
    quarantine.async_save = AsyncMock()
    quarantine.async_load = AsyncMock(return_value=None)

    await runtime.async_load()

    assert runtime.load_status is StoreLoadStatus.FAILED
    assert runtime.read_only is True
    assert not cast(Any, runtime).quarantine_present
    primary.async_remove.assert_not_awaited()
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_existing_quarantine_keeps_repair_until_verified_cleanup(
    hass: HomeAssistant,
) -> None:
    """A leftover quarantine remains actionable until a clean save removes it."""
    primary = _fake_store()
    runtime, publisher, _history = _runtime(hass, primary)
    document = runtime._document(
        cast(Any, _coordinator()),
        saved_at=NOW,
        last_clean_shutdown=True,
    )
    primary.async_load.return_value = dict(encode_runtime_store_document(document))
    quarantine = cast(Any, runtime)._quarantine_store
    quarantine.async_load.return_value = {"data": {"invalid": True}}

    await runtime.async_load()

    assert runtime.load_status is StoreLoadStatus.LOADED
    assert runtime.quarantine_present is True
    assert runtime.requires_repair is True
    category = runtime.migration_failure_category
    assert category is MigrationFailureCategory.STORE_VALIDATION
    runtime._repairs.async_report_migration_failure(category)
    registry = ir.async_get(hass)
    migration_issue = issue_id("entry-1", IssueCode.MIGRATION_FAILED)
    assert registry.async_get_issue("intelligent_climate", migration_issue) is not None

    assert await runtime._async_attempt_save(last_clean_shutdown=False)

    assert not cast(Any, runtime).quarantine_present
    assert (
        cast(Any, registry).async_get_issue("intelligent_climate", migration_issue)
        is None
    )
    quarantine.async_remove.assert_awaited_once()
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unreadable_quarantine_does_not_block_valid_primary_recovery(
    hass: HomeAssistant,
) -> None:
    """A quarantine read failure remains actionable while primary data loads."""
    primary = _fake_store()
    runtime, publisher, _history = _runtime(hass, primary)
    document = runtime._document(
        cast(Any, _coordinator()),
        saved_at=NOW,
        last_clean_shutdown=True,
    )
    primary.async_load.return_value = dict(encode_runtime_store_document(document))
    quarantine = cast(Any, runtime)._quarantine_store
    quarantine.async_load.side_effect = OSError("private quarantine path")

    await runtime.async_load()

    assert runtime.load_status is StoreLoadStatus.LOADED
    assert runtime.quarantine_present is True
    assert runtime.requires_repair is True
    assert (
        runtime.migration_failure_category is MigrationFailureCategory.STORE_VALIDATION
    )
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_valid_store_restores_only_configured_comparison_baselines(
    hass: HomeAssistant,
) -> None:
    """Validated baselines restore defensively while live zone values stay unused."""
    fake = _fake_store()
    runtime, publisher, _history = _runtime(hass, fake, with_zone=True)
    document = runtime._document(
        cast(Any, _coordinator()),
        saved_at=NOW,
        last_clean_shutdown=False,
    )
    raw = dict(encode_runtime_store_document(document))
    raw["source_baselines"] = {
        str(SOURCE_ID): {
            "last_accepted_value": 19.5,
            "last_accepted_at": NOW.isoformat(),
        }
    }
    raw["zones"] = {
        str(ZONE_ID): {
            "last_runtime_state": "observing",
            "last_live_observation_at": NOW.isoformat(),
            "last_effective_temperature_c": 999.0,
            "last_effective_humidity_pct": None,
            "last_decision_id": None,
        }
    }
    fake.async_load.return_value = raw

    await runtime.async_load()

    assert runtime.load_status is StoreLoadStatus.LOADED
    assert runtime.previous_clean_shutdown is False
    assert runtime.last_successful_save == NOW
    assert runtime.restored_source_baselines == {SOURCE_ID: SourceBaseline(19.5, NOW)}
    restored = runtime.restored_source_baselines
    restored.clear()
    assert SOURCE_ID in runtime.restored_source_baselines
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "source_baselines",
            {
                "ce30dafc-fadd-4cc4-b261-8a896d5a6d12": {
                    "last_accepted_value": 20.0,
                    "last_accepted_at": NOW.isoformat(),
                }
            },
        ),
        (
            "source_baselines",
            {
                str(SOURCE_ID): {
                    "last_accepted_value": 20.0,
                    "last_accepted_at": "2026-07-27T12:00:01+00:00",
                }
            },
        ),
        (
            "zones",
            {
                "7294e2ec-6f1f-4fbc-9f30-4a44d356cce8": {
                    "last_runtime_state": "observing",
                    "last_live_observation_at": NOW.isoformat(),
                    "last_effective_temperature_c": 20.0,
                    "last_effective_humidity_pct": None,
                    "last_decision_id": None,
                }
            },
        ),
    ],
)
async def test_untrusted_store_identity_or_future_baseline_is_quarantined(
    hass: HomeAssistant,
    field: str,
    value: object,
) -> None:
    """Unknown identities and impossible timestamps never seed runtime state."""
    fake = _fake_store()
    runtime, publisher, history = _runtime(hass, fake, with_zone=True)
    document = runtime._document(
        cast(Any, _coordinator()),
        saved_at=NOW,
        last_clean_shutdown=True,
    )
    raw = dict(encode_runtime_store_document(document))
    raw[field] = value
    fake.async_load.return_value = raw

    await runtime.async_load()

    assert runtime.load_status is StoreLoadStatus.QUARANTINED
    assert runtime.restored_source_baselines == {}
    assert runtime.previous_clean_shutdown is None
    assert history.records == ()
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_store_activity_with_foreign_group_identity_is_quarantined(
    hass: HomeAssistant,
) -> None:
    """A structurally valid activity cannot cross equipment-group boundaries."""
    fake = _fake_store()
    runtime, publisher, history = _runtime(hass, fake, with_zone=True)
    _activity(publisher)
    document = runtime._document(
        cast(Any, _coordinator()),
        saved_at=NOW,
        last_clean_shutdown=True,
    )
    raw = dict(encode_runtime_store_document(document))
    raw["decisions"][0]["equipment_group_id"] = "379faccc-2bbb-456d-a8b9-00610f83ab9f"
    fake.async_load.return_value = raw

    await runtime.async_load()

    assert runtime.load_status is StoreLoadStatus.QUARANTINED
    assert history.records == ()
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unsupported_store_is_preserved_read_only(
    hass: HomeAssistant,
) -> None:
    """A future Store version cannot be overwritten by lifecycle activity."""
    fake = _fake_store()
    fake.async_load.side_effect = UnsupportedStorageVersionError(
        "intelligent_climate.entry-1",
        2,
        1,
    )
    runtime, publisher, _history = _runtime(hass, fake)

    await runtime.async_load()
    _activity(publisher)

    assert runtime.load_status is StoreLoadStatus.UNSUPPORTED
    assert runtime.read_only is True
    assert runtime.dirty is False
    assert runtime._save_handle is None
    assert not await runtime._async_attempt_save(last_clean_shutdown=False)
    fake.async_save.assert_not_awaited()
    fake.async_remove.assert_not_awaited()
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_closed_store_ignores_scheduling_and_unattached_store_cannot_save(
    hass: HomeAssistant,
) -> None:
    """Closing and unattached stores cannot start background persistence."""
    runtime, publisher, _history = _runtime(hass, _fake_store())
    runtime._closing = True

    runtime._mark_dirty()
    runtime._schedule_at(hass.loop.time())
    runtime._start_write_task()

    assert runtime.dirty is True
    assert runtime._save_handle is None
    assert runtime.write_task is None

    runtime._coordinator = None
    assert not await runtime._async_attempt_save(last_clean_shutdown=False)
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_write_reschedules_when_data_remains_dirty(
    hass: HomeAssistant,
) -> None:
    """A completed writer retains one debounce timer when work remains dirty."""
    runtime, publisher, _history = _runtime(hass, _fake_store())
    _activity(publisher)
    runtime._coordinator = None

    await runtime._async_write()

    assert runtime.dirty is True
    assert runtime._save_handle is not None
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_successful_save_without_activity_reporter_clears_failure_state(
    hass: HomeAssistant,
) -> None:
    """A late save can recover safely even if publication is already detached."""
    runtime, publisher, _history = _runtime(hass, _fake_store())
    runtime._consecutive_failures = 1
    runtime._activity = None

    assert await runtime._async_attempt_save(last_clean_shutdown=False)
    assert runtime.consecutive_write_failures == 0

    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_activity_during_save_remains_dirty_and_final_save_retries(
    hass: HomeAssistant,
) -> None:
    """A generation accepted during a save is included by the final second pass."""
    fake = _fake_store()
    runtime, publisher, _history = _runtime(hass, fake)
    _activity(publisher)
    calls = 0

    async def _save_with_new_activity(_data: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            _activity(publisher)
        fake.async_load.return_value = deepcopy(_data)

    fake.async_save.side_effect = _save_with_new_activity

    await runtime.async_final_save()
    await runtime.async_final_save()

    assert fake.async_save.await_count == 2
    assert runtime.dirty is False
    assert runtime.last_successful_save == NOW
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_concurrent_final_saves_share_one_bounded_attempt(
    hass: HomeAssistant,
) -> None:
    """Core shutdown and unload cannot start duplicate final-save writers."""
    fake = _fake_store()
    started = asyncio.Event()
    release = asyncio.Event()

    async def _blocked_save(data: object) -> None:
        started.set()
        await release.wait()
        fake.async_load.return_value = deepcopy(data)

    fake.async_save.side_effect = _blocked_save
    runtime, publisher, _history = _runtime(hass, fake)
    _activity(publisher)

    first = asyncio.create_task(runtime.async_final_save())
    await started.wait()
    second = asyncio.create_task(runtime.async_final_save())
    release.set()
    await asyncio.gather(first, second)

    assert fake.async_save.await_count == 1
    assert runtime.dirty is False
    await runtime.async_shutdown()
    publisher.close()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_final_save_unexpected_failure_and_naive_clock_fail_safely(
    hass: HomeAssistant,
) -> None:
    """Unexpected final-save errors are bounded and naive clocks fail closed."""
    runtime, publisher, _history = _runtime(hass, _fake_store())
    _activity(publisher)

    with patch.object(
        RuntimeStore,
        "_async_attempt_save",
        new_callable=AsyncMock,
        side_effect=ValueError("private exception text"),
    ):
        await runtime.async_final_save()

    assert runtime.consecutive_write_failures == 1
    await runtime.async_shutdown()
    publisher.close()

    naive_runtime, naive_publisher, _naive_history = _runtime(hass, _fake_store())
    naive_runtime._now_fn = lambda: datetime(2026, 7, 27, 12)
    with pytest.raises(ValueError, match="timezone-aware"):
        await naive_runtime._async_attempt_save(last_clean_shutdown=False)
    await naive_runtime.async_shutdown()
    naive_publisher.close()
