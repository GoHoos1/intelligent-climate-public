"""Test the isolated authoritative Schedule Store added by Phase 2 Task 6."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.exceptions import UnsupportedStorageVersionError

from custom_components.intelligent_climate.models import (
    SCHEDULE_SCHEMA_VERSION,
    WEEKDAYS,
    EquipmentGroupId,
    LocalTime,
    ScheduleDocument,
    ScheduleOccupancyLabel,
    SchedulePeriod,
    SchedulePeriodId,
    ScheduleProfileId,
    ScheduleValidationContext,
    ScheduleZoneConstraints,
    SchemaValidationError,
    TargetKind,
    TargetSpec,
    Weekday,
    WeeklyScheduleProfile,
    ZoneId,
    ZoneScheduleSet,
    decode_schedule_document,
    encode_schedule_document,
)
from custom_components.intelligent_climate.schedule_storage import (
    SCHEDULE_STORE_MINOR_VERSION,
    SCHEDULE_STORE_VERSION,
    ScheduleRevisionConflictError,
    ScheduleStore,
    ScheduleStoreLoadStatus,
    ScheduleStoreNotLoadedError,
    ScheduleStoreReadOnlyError,
    ScheduleStoreWriteError,
    _async_save_verified,
    _ScheduleDataStore,
)

ROOT = Path(__file__).parents[2]
INTEGRATION_DIR = ROOT / "custom_components" / "intelligent_climate"

NOW = datetime(2026, 7, 30, 17, 30, tzinfo=UTC)
SAVED_AT = datetime(2026, 7, 30, 16, tzinfo=UTC)
GROUP_ID = EquipmentGroupId.parse("30000000-0000-4000-8000-000000000001")
ZONE_ID = ZoneId.parse("10000000-0000-4000-8000-000000000001")
PROFILE_ID = ScheduleProfileId.parse("20000000-0000-4000-8000-000000000001")
PERIOD_ID = SchedulePeriodId.parse("40000000-0000-4000-8000-000000000001")


def _context() -> ScheduleValidationContext:
    return ScheduleValidationContext(
        entry_id="entry-1",
        equipment_group_id=GROUP_ID,
        time_zone="America/New_York",
        zone_constraints={
            ZONE_ID: ScheduleZoneConstraints(
                zone_id=ZONE_ID,
                supports_single_target=True,
                supports_target_range=True,
                single_target_min_c=10.0,
                single_target_max_c=30.0,
                heat_target_min_c=10.0,
                heat_target_max_c=25.0,
                cool_target_min_c=18.0,
                cool_target_max_c=30.0,
                minimum_heat_cool_separation_c=1.5,
            )
        },
    )


def _document(
    *,
    revision: int = 0,
    saved_at: datetime = SAVED_AT,
    target_c: float = 21.0,
) -> ScheduleDocument:
    period = SchedulePeriod(
        period_id=PERIOD_ID,
        local_start=LocalTime.parse("06:30"),
        label="Morning",
        occupancy_label=ScheduleOccupancyLabel.HOME,
        target=TargetSpec(
            kind=TargetKind.SINGLE,
            target_c=target_c,
            heat_target_c=None,
            cool_target_c=None,
        ),
        tolerance_c=0.3,
    )
    profile = WeeklyScheduleProfile(
        profile_id=PROFILE_ID,
        name="Normal",
        enabled=True,
        days={
            weekday: (period,) if weekday is Weekday.MONDAY else ()
            for weekday in WEEKDAYS
        },
    )
    zone = ZoneScheduleSet(
        zone_id=ZONE_ID,
        enabled=True,
        selected_profile_id=PROFILE_ID,
        profiles=(profile,),
    )
    return ScheduleDocument(
        schedule_schema_version=SCHEDULE_SCHEMA_VERSION,
        entry_id="entry-1",
        equipment_group_id=GROUP_ID,
        time_zone="America/New_York",
        revision=revision,
        zones={ZONE_ID: zone},
        saved_at_utc=saved_at,
    )


def _fake_store(
    hass: HomeAssistant,
    key: str,
) -> Any:
    store = SimpleNamespace(
        hass=hass,
        key=key,
        async_load=AsyncMock(return_value=None),
        async_save=AsyncMock(),
        async_remove=AsyncMock(),
    )

    async def _successful_save(data: object) -> None:
        store.async_load.return_value = deepcopy(data)

    store.async_save.side_effect = _successful_save
    return store


def _store(
    hass: HomeAssistant,
    *,
    primary: Any | None = None,
    quarantine: Any | None = None,
    now: datetime = NOW,
) -> tuple[ScheduleStore, Any, Any]:
    primary = primary or _fake_store(
        hass,
        "intelligent_climate.schedule.entry-1",
    )
    quarantine = quarantine or _fake_store(
        hass,
        "intelligent_climate.schedule.entry-1.quarantine",
    )
    with (
        patch(
            "custom_components.intelligent_climate.schedule_storage._ScheduleDataStore",
            return_value=primary,
        ),
        patch(
            "custom_components.intelligent_climate.schedule_storage.Store",
            return_value=quarantine,
        ),
    ):
        result = ScheduleStore(
            hass,
            entry_id="entry-1",
            validation_context=_context(),
            now_fn=lambda: now,
        )
    return result, primary, quarantine


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_store_contract_and_missing_load_are_exact_and_idempotent(
    hass: HomeAssistant,
) -> None:
    """The absent Store is writable revision zero and does not create data."""
    with (
        patch(
            "custom_components.intelligent_climate.schedule_storage._ScheduleDataStore"
        ) as primary_class,
        patch(
            "custom_components.intelligent_climate.schedule_storage.Store"
        ) as quarantine_class,
    ):
        primary = _fake_store(
            hass,
            "intelligent_climate.schedule.entry-1",
        )
        quarantine = _fake_store(
            hass,
            "intelligent_climate.schedule.entry-1.quarantine",
        )
        primary_class.return_value = primary
        quarantine_class.return_value = quarantine
        store = ScheduleStore(
            hass,
            entry_id="entry-1",
            validation_context=_context(),
            now_fn=lambda: NOW,
        )

    first = await store.async_load()
    second = await store.async_load()

    primary_class.assert_called_once_with(
        hass,
        "intelligent_climate.schedule.entry-1",
    )
    quarantine_class.assert_called_once_with(
        hass,
        1,
        "intelligent_climate.schedule.entry-1.quarantine",
        atomic_writes=True,
    )
    assert store.key == "intelligent_climate.schedule.entry-1"
    assert (store.version, store.minor_version) == (1, 0)
    assert (SCHEDULE_STORE_VERSION, SCHEDULE_STORE_MINOR_VERSION) == (1, 0)
    assert store.loaded is True
    assert store.load_status is ScheduleStoreLoadStatus.MISSING
    assert store.revision == 0
    assert store.document is None
    assert first == second
    assert first.status is ScheduleStoreLoadStatus.MISSING
    assert first.document is None
    assert first.read_only is False
    assert first.quarantine_present is False
    primary.async_load.assert_awaited_once()
    quarantine.async_load.assert_awaited_once()
    primary.async_save.assert_not_awaited()


def test_real_store_envelope_requests_atomic_exact_version(
    hass: HomeAssistant,
) -> None:
    """The concrete Home Assistant Store carries the exact v1.0 contract."""
    store = _ScheduleDataStore(
        hass,
        "intelligent_climate.schedule.envelope-test",
    )

    assert store.version == SCHEDULE_STORE_VERSION
    assert store.minor_version == SCHEDULE_STORE_MINOR_VERSION
    assert store.key == "intelligent_climate.schedule.envelope-test"


def test_validation_context_identity_must_match_store_entry(
    hass: HomeAssistant,
) -> None:
    """A Store cannot validate one entry while writing another entry's key."""
    with pytest.raises(ValueError, match="entry_id must match"):
        ScheduleStore(
            hass,
            entry_id="other-entry",
            validation_context=_context(),
        )


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_initial_save_is_validated_incremented_verified_then_published(
    hass: HomeAssistant,
) -> None:
    """Revision zero is an unsaved draft; the first persisted revision is one."""
    store, primary, _quarantine = _store(hass)
    await store.async_load()
    draft = _document()

    canonical = await store.async_save(draft, expected_revision=0)

    assert draft.revision == 0
    assert draft.saved_at_utc == SAVED_AT
    assert canonical is not draft
    assert canonical.revision == 1
    assert canonical.saved_at_utc == NOW
    assert store.document is canonical
    assert store.revision == 1
    assert store.load_status is ScheduleStoreLoadStatus.LOADED
    saved = primary.async_save.await_args.args[0]
    assert decode_schedule_document(saved, validation_context=_context()) == canonical
    assert saved == dict(
        encode_schedule_document(canonical, validation_context=_context())
    )
    with pytest.raises(FrozenInstanceError):
        canonical.revision = 9  # type: ignore[misc]


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_valid_persisted_document_loads_as_the_canonical_revision(
    hass: HomeAssistant,
) -> None:
    """A strict positive persisted revision round-trips unchanged."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    existing = _document(revision=7)
    primary.async_load.return_value = dict(
        encode_schedule_document(existing, validation_context=_context())
    )
    store, _primary, _quarantine = _store(hass, primary=primary)

    result = await store.async_load()

    assert result.status is ScheduleStoreLoadStatus.LOADED
    assert result.document == existing
    assert store.document == existing
    assert store.revision == 7
    assert store.read_only is False


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_save_requires_load_and_exact_draft_revision(
    hass: HomeAssistant,
) -> None:
    """Callers cannot bypass startup recovery or submit ambiguous revisions."""
    store, primary, _quarantine = _store(hass)

    with pytest.raises(ScheduleStoreNotLoadedError):
        await store.async_save(_document(), expected_revision=0)

    await store.async_load()
    with pytest.raises(
        SchemaValidationError,
        match="draft revision must match expected_revision",
    ):
        await store.async_save(_document(revision=1), expected_revision=0)
    primary.async_save.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_stale_and_malformed_expected_revisions_are_rejected_before_write(
    hass: HomeAssistant,
) -> None:
    """Optimistic compare-and-swap rejects stale editors and malformed input."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    existing = _document(revision=3)
    primary.async_load.return_value = dict(
        encode_schedule_document(existing, validation_context=_context())
    )
    store, _primary, _quarantine = _store(hass, primary=primary)
    await store.async_load()
    primary.async_save.reset_mock()

    with pytest.raises(ScheduleRevisionConflictError) as conflict:
        await store.async_save(_document(revision=2), expected_revision=2)
    assert conflict.value.expected_revision == 2
    assert conflict.value.actual_revision == 3
    assert "expected 2, current revision is 3" in str(conflict.value)

    for invalid in (True, -1, 1.5):
        with pytest.raises(ValueError, match="nonnegative integer"):
            await store.async_save(
                existing,
                expected_revision=cast(Any, invalid),
            )
    primary.async_save.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_complete_document_validation_precedes_persistence(
    hass: HomeAssistant,
) -> None:
    """An invalid complete draft is rejected as a whole with revision unchanged."""
    store, primary, _quarantine = _store(hass)
    await store.async_load()
    invalid = replace(_document(), entry_id="foreign-entry")

    with pytest.raises(SchemaValidationError, match="does not match"):
        await store.async_save(invalid, expected_revision=0)

    assert store.revision == 0
    assert store.document is None
    primary.async_save.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_hand_built_invalid_draft_fields_are_not_hidden_by_canonicalization(
    hass: HomeAssistant,
) -> None:
    """Store-owned revision/timestamp replacement cannot mask an invalid draft."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    existing = _document(revision=1)
    primary.async_load.return_value = dict(
        encode_schedule_document(existing, validation_context=_context())
    )
    store, _primary, _quarantine = _store(hass, primary=primary)
    await store.async_load()
    invalid_revision = replace(existing, revision=cast(Any, True))
    invalid_timestamp = replace(existing, saved_at_utc=cast(Any, "not-a-datetime"))

    with pytest.raises(SchemaValidationError, match="revision"):
        await store.async_save(invalid_revision, expected_revision=1)
    with pytest.raises(SchemaValidationError, match="saved_at_utc"):
        await store.async_save(invalid_timestamp, expected_revision=1)

    primary.async_save.assert_not_awaited()
    assert store.document == existing


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_concurrent_compare_and_swap_allows_only_one_revision_winner(
    hass: HomeAssistant,
) -> None:
    """The entry-scoped lock makes concurrent saves true compare-and-swap."""
    store, primary, _quarantine = _store(hass)
    await store.async_load()
    entered = asyncio.Event()
    release = asyncio.Event()

    async def _blocked_save(data: object) -> None:
        entered.set()
        await release.wait()
        primary.async_load.return_value = deepcopy(data)

    primary.async_save.side_effect = _blocked_save
    first = asyncio.create_task(
        store.async_save(_document(target_c=20.0), expected_revision=0)
    )
    await entered.wait()
    second = asyncio.create_task(
        store.async_save(_document(target_c=22.0), expected_revision=0)
    )
    release.set()

    first_result = await first
    with pytest.raises(ScheduleRevisionConflictError):
        await second

    assert first_result.revision == 1
    assert (
        first_result.zones[ZONE_ID].profiles[0].days[Weekday.MONDAY][0].target.target_c
        == 20.0
    )
    assert primary.async_save.await_count == 1


@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize("silent_failure", [False, True])
async def test_failed_write_keeps_prior_canonical_document(
    hass: HomeAssistant,
    silent_failure: bool,
) -> None:
    """Exceptions and unverified writes never publish a browser draft."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    existing = _document(revision=4, target_c=20.0)
    existing_raw = dict(
        encode_schedule_document(existing, validation_context=_context())
    )
    primary.async_load.return_value = existing_raw
    store, _primary, _quarantine = _store(hass, primary=primary)
    await store.async_load()
    if silent_failure:
        primary.async_save.side_effect = None
    else:
        primary.async_save.side_effect = OSError("private path and exception text")

    with pytest.raises(ScheduleStoreWriteError):
        await store.async_save(
            _document(revision=4, target_c=23.0),
            expected_revision=4,
        )

    assert store.document == existing
    assert store.revision == 4
    assert store.load_status is ScheduleStoreLoadStatus.LOADED


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_stopping_home_assistant_rejects_write_before_store_mutation(
    hass: HomeAssistant,
) -> None:
    """A stopping lifecycle cannot accept an unverifiable schedule mutation."""
    store, primary, _quarantine = _store(hass)
    await store.async_load()
    prior_state = hass.state
    hass.set_state(CoreState.stopping)
    try:
        with pytest.raises(ScheduleStoreWriteError, match="stopping"):
            await store.async_save(_document(), expected_revision=0)
    finally:
        hass.set_state(prior_state)

    primary.async_save.assert_not_awaited()
    assert store.document is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_semantically_invalid_store_is_verified_in_quarantine_first(
    hass: HomeAssistant,
) -> None:
    """Invalid authoritative data is copied durably before primary removal."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    invalid = dict(
        encode_schedule_document(_document(revision=1), validation_context=_context())
    )
    invalid["entry_id"] = "foreign-entry"
    primary.async_load.return_value = invalid
    store, _primary, quarantine = _store(hass, primary=primary)

    result = await store.async_load()

    assert result.status is ScheduleStoreLoadStatus.QUARANTINED
    assert result.document is None
    assert result.read_only is False
    assert result.quarantine_present is True
    saved_quarantine = quarantine.async_save.await_args.args[0]
    assert saved_quarantine["reason_code"] == ("invalid_authoritative_schedule_store")
    assert saved_quarantine["quarantined_at"] == NOW.isoformat()
    assert saved_quarantine["data"] == invalid
    primary.async_remove.assert_awaited_once()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_persisted_revision_zero_is_invalid_and_quarantined(
    hass: HomeAssistant,
) -> None:
    """Revision zero is reserved for unsaved drafts and is never canonical."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    primary.async_load.return_value = dict(
        encode_schedule_document(_document(), validation_context=_context())
    )
    store, _primary, _quarantine = _store(hass, primary=primary)

    await store.async_load()

    assert store.load_status is ScheduleStoreLoadStatus.QUARANTINED
    assert store.document is None
    primary.async_remove.assert_awaited_once()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unverified_quarantine_preserves_primary_read_only(
    hass: HomeAssistant,
) -> None:
    """A failed quarantine copy cannot destroy the only invalid payload."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    invalid = {"schedule_schema_version": 1, "invalid": True}
    primary.async_load.return_value = invalid
    quarantine = _fake_store(
        hass,
        "intelligent_climate.schedule.entry-1.quarantine",
    )
    quarantine.async_save.side_effect = None
    store, _primary, _quarantine = _store(
        hass,
        primary=primary,
        quarantine=quarantine,
    )

    result = await store.async_load()

    assert result.status is ScheduleStoreLoadStatus.FAILED
    assert result.read_only is True
    assert result.quarantine_present is False
    primary.async_remove.assert_not_awaited()
    with pytest.raises(ScheduleStoreReadOnlyError):
        await store.async_save(_document(), expected_revision=0)


@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize("future_inner", [False, True])
async def test_future_envelope_or_inner_schema_is_preserved_read_only(
    hass: HomeAssistant,
    future_inner: bool,
) -> None:
    """Future data is neither downgraded, quarantined, nor overwritten."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    if future_inner:
        raw = dict(
            encode_schedule_document(
                _document(revision=1),
                validation_context=_context(),
            )
        )
        raw["schedule_schema_version"] = SCHEDULE_SCHEMA_VERSION + 1
        primary.async_load.return_value = raw
    else:
        primary.async_load.side_effect = UnsupportedStorageVersionError(
            "intelligent_climate.schedule.entry-1",
            2,
            0,
        )
    store, _primary, quarantine = _store(hass, primary=primary)

    result = await store.async_load()

    assert result.status is ScheduleStoreLoadStatus.UNSUPPORTED
    assert result.document is None
    assert result.read_only is True
    assert result.quarantine_present is False
    primary.async_remove.assert_not_awaited()
    quarantine.async_save.assert_not_awaited()
    with pytest.raises(ScheduleStoreReadOnlyError):
        await store.async_save(_document(), expected_revision=0)


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_unreadable_primary_is_preserved_failed_and_read_only(
    hass: HomeAssistant,
) -> None:
    """Unexpected read failure cannot be mistaken for an empty writable Store."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    primary.async_load.side_effect = OSError("private path and exception text")
    store, _primary, _quarantine = _store(hass, primary=primary)

    result = await store.async_load()

    assert result.status is ScheduleStoreLoadStatus.FAILED
    assert result.read_only is True
    assert result.document is None


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_schema_error_raised_by_store_load_with_no_payload_fails_closed(
    hass: HomeAssistant,
) -> None:
    """A schema-classified read error with no raw payload cannot be quarantined."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    primary.async_load.side_effect = SchemaValidationError(
        "schedule Store",
        "could not decode payload",
    )
    store, _primary, _quarantine = _store(hass, primary=primary)

    result = await store.async_load()

    assert result.status is ScheduleStoreLoadStatus.FAILED
    assert result.read_only is True
    primary.async_remove.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_existing_or_unreadable_quarantine_keeps_missing_store_actionable(
    hass: HomeAssistant,
) -> None:
    """Missing primary plus known quarantine remains a quarantined load result."""
    for unreadable in (False, True):
        primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
        quarantine = _fake_store(
            hass,
            "intelligent_climate.schedule.entry-1.quarantine",
        )
        if unreadable:
            quarantine.async_load.side_effect = OSError("private quarantine path")
        else:
            quarantine.async_load.return_value = {"data": {"invalid": True}}
        store, _primary, _quarantine = _store(
            hass,
            primary=primary,
            quarantine=quarantine,
        )

        result = await store.async_load()

        assert result.status is ScheduleStoreLoadStatus.QUARANTINED
        assert result.quarantine_present is True
        assert result.read_only is False


@pytest.mark.usefixtures("enable_custom_integrations")
@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_verified_save_replaces_quarantine_only_after_canonical_commit(
    hass: HomeAssistant,
    cleanup_fails: bool,
) -> None:
    """A valid save becomes canonical even if stale quarantine cleanup fails."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    quarantine = _fake_store(
        hass,
        "intelligent_climate.schedule.entry-1.quarantine",
    )
    quarantine.async_load.return_value = {"data": {"invalid": True}}
    if cleanup_fails:
        quarantine.async_remove.side_effect = OSError("private cleanup path")
    store, _primary, _quarantine = _store(
        hass,
        primary=primary,
        quarantine=quarantine,
    )
    await store.async_load()

    canonical = await store.async_save(_document(), expected_revision=0)

    assert canonical.revision == 1
    assert store.document is canonical
    assert store.load_status is ScheduleStoreLoadStatus.LOADED
    assert store.quarantine_present is cleanup_fails
    quarantine.async_remove.assert_awaited_once()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_cancellation_propagates_without_quarantining(
    hass: HomeAssistant,
) -> None:
    """Cancellation is lifecycle control, not corrupt persisted data."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    primary.async_load.side_effect = asyncio.CancelledError
    store, _primary, quarantine = _store(hass, primary=primary)

    with pytest.raises(asyncio.CancelledError):
        await store.async_load()

    assert store.loaded is False
    assert store.load_status is ScheduleStoreLoadStatus.NOT_LOADED
    quarantine.async_save.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_save_and_quarantine_cancellation_propagate(
    hass: HomeAssistant,
) -> None:
    """Cancellation is never converted into a write or quarantine failure."""
    quarantine_load = _fake_store(
        hass,
        "intelligent_climate.schedule.entry-1.quarantine",
    )
    quarantine_load.async_load.side_effect = asyncio.CancelledError
    loading_store, _primary, _quarantine = _store(
        hass,
        quarantine=quarantine_load,
    )
    with pytest.raises(asyncio.CancelledError):
        await loading_store.async_load()

    store, primary, _quarantine = _store(hass)
    await store.async_load()
    primary.async_save.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await store.async_save(_document(), expected_revision=0)
    assert store.document is None

    invalid_primary = _fake_store(
        hass,
        "intelligent_climate.schedule.entry-1",
    )
    invalid_primary.async_load.return_value = []
    quarantine = _fake_store(
        hass,
        "intelligent_climate.schedule.entry-1.quarantine",
    )
    quarantine.async_save.side_effect = asyncio.CancelledError
    quarantining_store, _primary, _quarantine = _store(
        hass,
        primary=invalid_primary,
        quarantine=quarantine,
    )
    with pytest.raises(asyncio.CancelledError):
        await quarantining_store.async_load()
    invalid_primary.async_remove.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_cleanup_cancellation_propagates_after_canonical_commit(
    hass: HomeAssistant,
) -> None:
    """Cancellation during stale-quarantine cleanup does not undo the save."""
    primary = _fake_store(hass, "intelligent_climate.schedule.entry-1")
    quarantine = _fake_store(
        hass,
        "intelligent_climate.schedule.entry-1.quarantine",
    )
    quarantine.async_load.return_value = {"data": {"invalid": True}}
    quarantine.async_remove.side_effect = asyncio.CancelledError
    store, _primary, _quarantine = _store(
        hass,
        primary=primary,
        quarantine=quarantine,
    )
    await store.async_load()

    with pytest.raises(asyncio.CancelledError):
        await store.async_save(_document(), expected_revision=0)

    assert store.document is not None
    assert store.revision == 1
    assert store.quarantine_present is True


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_verified_write_detects_stopping_race(
    hass: HomeAssistant,
) -> None:
    """A lifecycle transition during the atomic write cannot verify success."""
    store = _fake_store(hass, "intelligent_climate.schedule.race-test")
    prior_state = hass.state

    async def _stop_during_save(_data: object) -> None:
        hass.set_state(CoreState.stopping)

    store.async_save.side_effect = _stop_during_save
    try:
        assert not await _async_save_verified(
            cast(Any, store),
            {"schedule_schema_version": 1},
        )
    finally:
        hass.set_state(prior_state)
    store.async_load.assert_not_awaited()


@pytest.mark.usefixtures("enable_custom_integrations")
async def test_naive_clock_is_rejected_without_persistence(
    hass: HomeAssistant,
) -> None:
    """The canonical saved-at instant can never lose timezone information."""
    store, primary, _quarantine = _store(
        hass,
        now=datetime(2026, 7, 30, 17, 30),
    )
    await store.async_load()

    with pytest.raises(ValueError, match="timezone-aware"):
        await store.async_save(_document(), expected_revision=0)

    primary.async_save.assert_not_awaited()


def test_schedule_store_task_19_wiring_has_no_control_surface() -> None:
    """Task 19 may compose the Store, but persistence still cannot control."""
    source = (INTEGRATION_DIR / "schedule_storage.py").read_text(encoding="utf-8")
    prohibited = {
        "services.async_call",
        "async_track",
        "call_at",
        "call_later",
        "Coordinator",
        "CommandSink",
        "command_adapter",
        "RepairsManager",
        "ActivityPublisher",
        "config_entries.async_update_entry",
    }

    assert all(term not in source for term in prohibited)
    assert "from .schedule_storage import ScheduleStore" in (
        INTEGRATION_DIR / "__init__.py"
    ).read_text(encoding="utf-8")
    for runtime_path in (
        INTEGRATION_DIR / "coordinator.py",
        INTEGRATION_DIR / "storage.py",
    ):
        assert "schedule_storage" not in runtime_path.read_text(encoding="utf-8")
