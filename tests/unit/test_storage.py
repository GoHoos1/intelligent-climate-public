"""Test debounced nonauthoritative runtime Store behavior."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

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
    RuntimeConfigurationState,
    encode_runtime_store_document,
)
from custom_components.intelligent_climate.repairs import (
    IssueCode,
    RepairsManager,
    issue_id,
)
from custom_components.intelligent_climate.storage import (
    STORE_DEBOUNCE_SECONDS,
    STORE_FINAL_SAVE_TIMEOUT_SECONDS,
    RuntimeStore,
)

NOW = datetime(2026, 7, 27, 12, tzinfo=UTC)
GROUP_ID = EquipmentGroupId.parse("b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3")


def _configuration() -> EntryRuntimeConfiguration:
    return EntryRuntimeConfiguration(
        equipment_group=EquipmentGroupConfig(
            equipment_group_id=GROUP_ID,
            name="Main",
            equipment_type=EquipmentType.CONVENTIONAL,
            relationship=EquipmentRelationship.SINGLE_SYSTEM,
            thermostats=(),
            shared_policy=None,
        ),
        zones=(),
        options=DEFAULT_OPTIONS,
        state=RuntimeConfigurationState.AWAITING_FIRST_ZONE,
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
    store.async_load = AsyncMock(return_value=None)
    store.async_save = AsyncMock()
    return store


def _runtime(
    hass: HomeAssistant,
    fake_store: Mock,
) -> tuple[RuntimeStore, ActivityPublisher, ActivityHistory]:
    history = ActivityHistory(max_records=500, max_age_days=30)
    repairs = RepairsManager(hass, "entry-1")
    with patch(
        "custom_components.intelligent_climate.storage.Store",
        return_value=fake_store,
    ) as store_class:
        runtime = RuntimeStore(
            hass,
            entry_id="entry-1",
            configuration=_configuration(),
            history=history,
            repairs=repairs,
            now_fn=lambda: NOW,
        )
    store_class.assert_called_once_with(
        hass,
        1,
        "intelligent_climate.entry-1",
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

    fake.async_save.side_effect = None
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
    assert invalid_history.records == ()
    await invalid_runtime.async_shutdown()
    invalid_publisher.close()

    failed_fake = _fake_store()
    failed_fake.async_load.side_effect = OSError("private exception text")
    failed_runtime, failed_publisher, failed_history = _runtime(hass, failed_fake)

    await failed_runtime.async_load()

    assert failed_runtime.loaded is True
    assert failed_history.records == ()
    await failed_runtime.async_shutdown()
    failed_publisher.close()


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

    fake.async_save.side_effect = _save_with_new_activity

    await runtime.async_final_save()

    assert fake.async_save.await_count == 2
    assert runtime.dirty is False
    assert runtime.last_successful_save == NOW
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
