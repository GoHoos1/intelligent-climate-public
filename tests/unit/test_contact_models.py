"""Task 12 pure contact binding and lifecycle tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from custom_components.intelligent_climate.contact import (
    ContactInput,
    ContactLifecycleState,
    ContactReasonCode,
    evaluate_contact,
)
from custom_components.intelligent_climate.models import (
    ContactBinding,
    ContactBindingId,
    ContactKind,
    ContactScope,
    ContactUnavailablePolicy,
    EquipmentGroupId,
    SchemaValidationError,
    ZoneId,
    decode_contact_binding,
    encode_contact_binding,
)

NOW = datetime(2026, 7, 30, 18, tzinfo=UTC)


def _binding(**changes: object) -> ContactBinding:
    value = ContactBinding(
        binding_id=ContactBindingId(UUID(int=1)),
        entity_id="binary_sensor.dining_window",
        kind=ContactKind.WINDOW,
        scope=ContactScope.ZONE,
        zone_id=ZoneId(UUID(int=2)),
        equipment_group_id=EquipmentGroupId(UUID(int=3)),
        open_debounce_seconds=30,
        grace_seconds=120,
        minimum_open_seconds=120,
        close_debounce_seconds=30,
        resume_delay_seconds=300,
        unavailable_policy=ContactUnavailablePolicy.TREAT_OPEN,
        notification_after_seconds=900,
        reminder_interval_seconds=3600,
        reviewed=True,
        enabled=True,
    )
    return value.__class__(
        **{field: getattr(value, field) for field in value.__dataclass_fields__}
        | changes
    )


def test_contact_binding_round_trips_without_runtime_activation() -> None:
    binding = _binding()
    assert decode_contact_binding(encode_contact_binding(binding)) == binding


@pytest.mark.parametrize(
    ("is_open", "age", "previous", "state", "suppressed"),
    [
        (True, 0, None, ContactLifecycleState.OPEN_DEBOUNCE, False),
        (True, 30, None, ContactLifecycleState.GRACE, False),
        (True, 149, None, ContactLifecycleState.GRACE, False),
        (True, 150, None, ContactLifecycleState.SUSPENDED, True),
        (
            False,
            0,
            ContactLifecycleState.SUSPENDED,
            ContactLifecycleState.CLOSE_DEBOUNCE,
            True,
        ),
        (
            False,
            30,
            ContactLifecycleState.SUSPENDED,
            ContactLifecycleState.RESUME_DELAY,
            True,
        ),
        (
            False,
            330,
            ContactLifecycleState.SUSPENDED,
            ContactLifecycleState.CLOSED,
            False,
        ),
    ],
)
def test_contact_state_machine_obeys_debounce_grace_and_resume(
    is_open: bool,
    age: int,
    previous: ContactLifecycleState | None,
    state: ContactLifecycleState,
    suppressed: bool,
) -> None:
    result = evaluate_contact(
        _binding(),
        inputs=ContactInput(NOW, is_open, NOW - timedelta(seconds=age), previous),
    )
    assert result.state is state
    assert result.comfort_suppressed is suppressed


def test_unavailable_treat_open_fails_closed_without_a_command() -> None:
    result = evaluate_contact(_binding(), inputs=ContactInput(NOW, None, None))
    assert result.state is ContactLifecycleState.SUSPENDED
    assert result.reason_code is ContactReasonCode.CONTACT_UNAVAILABLE_TREATED_OPEN
    assert result.comfort_suppressed


def test_unavailable_ignore_is_degraded_not_suspended() -> None:
    result = evaluate_contact(
        _binding(unavailable_policy=ContactUnavailablePolicy.IGNORE_AND_DEGRADE),
        inputs=ContactInput(NOW, None, None),
    )
    assert result.state is ContactLifecycleState.DEGRADED
    assert result.degraded
    assert not result.comfort_suppressed


def test_reopening_during_resume_returns_directly_to_suspension() -> None:
    result = evaluate_contact(
        _binding(),
        inputs=ContactInput(
            NOW,
            True,
            NOW,
            ContactLifecycleState.RESUME_DELAY,
        ),
    )
    assert result.state is ContactLifecycleState.SUSPENDED
    assert result.comfort_suppressed


@pytest.mark.parametrize(
    "changes",
    [
        {"entity_id": "sensor.not_contact"},
        {"enabled": True, "reviewed": False},
        {"scope": ContactScope.EQUIPMENT_GROUP, "zone_id": ZoneId(UUID(int=2))},
        {"notification_after_seconds": 0},
        {"reminder_interval_seconds": 0},
    ],
)
def test_contact_configuration_rejects_unsafe_or_malformed_values(
    changes: dict[str, object],
) -> None:
    with pytest.raises(SchemaValidationError):
        encode_contact_binding(_binding(**changes))


def test_future_observed_timestamp_fails_closed() -> None:
    with pytest.raises(SchemaValidationError, match="future"):
        evaluate_contact(
            _binding(),
            inputs=ContactInput(NOW, True, NOW + timedelta(seconds=1)),
        )
