"""Pure cancellation, extension, and exact-boundary override tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest

from custom_components.intelligent_climate.models.identifiers import (
    EquipmentGroupId,
    OverrideId,
    ZoneId,
)
from custom_components.intelligent_climate.models.override import (
    ControlledField,
    ControlledValues,
    ManualOverride,
    OverrideEndReason,
    OverrideExpirationKind,
    OverrideExpirationPolicy,
    OverrideReasonCode,
    OverrideSource,
    OverrideState,
)
from custom_components.intelligent_climate.override.expiration import (
    ExpirationCalculation,
    ExpirationReasonCode,
)
from custom_components.intelligent_climate.override.state_machine import (
    cancel_override,
    complete_override,
    evaluate_override_lifecycle,
    extend_override,
)

START = datetime(2026, 7, 30, 12, tzinfo=UTC)
DEADLINE = START + timedelta(hours=1)


def _override(**changes: Any) -> ManualOverride:
    value = ManualOverride(
        override_id=OverrideId.parse("50000000-0000-4000-8000-000000000001"),
        entry_id="entry-1",
        equipment_group_id=EquipmentGroupId.parse(
            "30000000-0000-4000-8000-000000000001"
        ),
        zone_id=ZoneId.parse("10000000-0000-4000-8000-000000000001"),
        controlled_fields=frozenset({ControlledField.TARGET}),
        source=OverrideSource.PHYSICAL_OR_EXTERNAL,
        source_context_id=None,
        requested_values=ControlledValues(target_c=21.0),
        started_at_utc=START,
        last_updated_at_utc=START,
        expiration_policy=OverrideExpirationPolicy(
            OverrideExpirationKind.DURATION,
            duration_seconds=3600,
        ),
        expires_at_utc=DEADLINE,
        anchor_transition_key=None,
        state=OverrideState.ACTIVE,
    )
    return replace(value, **changes)


def test_before_expiration_remains_active_without_mutation() -> None:
    value = _override()
    result = evaluate_override_lifecycle(
        value,
        at_utc=DEADLINE - timedelta(microseconds=1),
    )

    assert result.override is value
    assert result.changed is False
    assert result.reason_code is OverrideReasonCode.ACTIVE


def test_exact_expiration_boundary_enters_expiring_once() -> None:
    value = _override()
    result = evaluate_override_lifecycle(value, at_utc=DEADLINE)
    repeated = evaluate_override_lifecycle(result.override, at_utc=DEADLINE)

    assert result.previous_state is OverrideState.ACTIVE
    assert result.override.state is OverrideState.EXPIRING
    assert result.changed is True
    assert result.reason_code is OverrideReasonCode.EXPIRATION_DUE
    assert repeated.override == result.override
    assert repeated.changed is False


def test_unresolved_and_manual_expiration_never_auto_expires() -> None:
    value = _override(
        expiration_policy=OverrideExpirationPolicy(
            OverrideExpirationKind.MANUAL_CANCELLATION
        ),
        expires_at_utc=None,
    )

    result = evaluate_override_lifecycle(
        value,
        at_utc=START + timedelta(days=365),
    )

    assert result.override is value
    assert result.override.state is OverrideState.ACTIVE


def test_manual_cancellation_ends_without_changing_stable_identity() -> None:
    value = _override()
    at = START + timedelta(minutes=10)

    result = cancel_override(value, at_utc=at)

    assert result.override.override_id == value.override_id
    assert result.override.started_at_utc == value.started_at_utc
    assert result.override.state is OverrideState.ENDED
    assert result.override.ended_at_utc == at
    assert result.override.end_reason is OverrideEndReason.MANUALLY_CANCELLED
    assert result.reason_code is OverrideReasonCode.MANUALLY_CANCELLED


def test_extension_replaces_policy_deadline_and_optional_value() -> None:
    value = _override()
    at = START + timedelta(minutes=10)
    deadline = at + timedelta(hours=2)
    policy = OverrideExpirationPolicy(
        OverrideExpirationKind.DURATION,
        duration_seconds=7200,
    )
    calculation = ExpirationCalculation(
        expires_at_utc=deadline,
        anchor_transition_key=None,
        reason_code=ExpirationReasonCode.DURATION_ELAPSED,
        explanation="fixed",
    )

    result = extend_override(
        value,
        at_utc=at,
        expiration_policy=policy,
        expiration=calculation,
        requested_values=ControlledValues(target_c=22.0),
    )

    assert result.override.override_id == value.override_id
    assert result.override.started_at_utc == value.started_at_utc
    assert result.override.last_updated_at_utc == at
    assert result.override.expires_at_utc == deadline
    assert result.override.requested_values.target_c == 22.0
    assert result.override.state is OverrideState.ACTIVE
    assert result.reason_code is OverrideReasonCode.EXTENDED


def test_extension_can_reactivate_expiring_override() -> None:
    expiring = replace(
        _override(),
        state=OverrideState.EXPIRING,
        last_updated_at_utc=DEADLINE,
    )
    calculation = ExpirationCalculation(
        expires_at_utc=DEADLINE + timedelta(hours=1),
        anchor_transition_key="new-transition",
        reason_code=ExpirationReasonCode.NEXT_MATERIAL_SCHEDULE_TRANSITION,
        explanation="fixed",
    )

    result = extend_override(
        expiring,
        at_utc=DEADLINE,
        expiration_policy=OverrideExpirationPolicy(
            OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
        ),
        expiration=calculation,
    )

    assert result.override.state is OverrideState.ACTIVE
    assert result.override.anchor_transition_key == "new-transition"


def test_completion_requires_expiring_and_records_caller_reason() -> None:
    expiring = evaluate_override_lifecycle(_override(), at_utc=DEADLINE).override

    result = complete_override(
        expiring,
        at_utc=DEADLINE + timedelta(seconds=1),
        end_reason=OverrideEndReason.RECONCILED,
    )

    assert result.override.state is OverrideState.ENDED
    assert result.override.end_reason is OverrideEndReason.RECONCILED
    assert result.reason_code is OverrideReasonCode.ENDED


@pytest.mark.parametrize(
    ("operation", "message"),
    [
        (
            lambda value: cancel_override(
                replace(
                    value,
                    state=OverrideState.ENDED,
                    ended_at_utc=DEADLINE,
                    end_reason=OverrideEndReason.EXPIRED,
                ),
                at_utc=DEADLINE,
            ),
            "ended override",
        ),
        (
            lambda value: cancel_override(
                value,
                at_utc=START - timedelta(seconds=1),
            ),
            "move backward",
        ),
        (
            lambda value: extend_override(
                value,
                at_utc=START,
                expiration_policy=value.expiration_policy,
                expiration=ExpirationCalculation(
                    expires_at_utc=START - timedelta(seconds=1),
                    anchor_transition_key=None,
                    reason_code=ExpirationReasonCode.DURATION_ELAPSED,
                    explanation="fixed",
                ),
            ),
            "cannot precede",
        ),
        (
            lambda value: complete_override(
                value,
                at_utc=START,
                end_reason=OverrideEndReason.EXPIRED,
            ),
            "only an expiring",
        ),
        (
            lambda value: evaluate_override_lifecycle(
                value,
                at_utc=datetime(2026, 7, 30, 8, tzinfo=timezone(timedelta(hours=-4))),
            ),
            "expressed in UTC",
        ),
    ],
)
def test_invalid_lifecycle_inputs_fail_closed(
    operation: Callable[[ManualOverride], object],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        operation(_override())


def test_extension_without_deadline_covers_unresolved_policy_branch() -> None:
    value = _override()
    calculation = ExpirationCalculation(
        expires_at_utc=None,
        anchor_transition_key=None,
        reason_code=ExpirationReasonCode.NO_MATERIAL_SCHEDULE_TRANSITION,
        explanation="fixed",
    )

    result = extend_override(
        value,
        at_utc=START,
        expiration_policy=OverrideExpirationPolicy(
            OverrideExpirationKind.NEXT_MATERIAL_SCHEDULE_TRANSITION
        ),
        expiration=calculation,
    )

    assert result.override.expires_at_utc is None


def test_completion_rejects_manual_reason_and_backward_time() -> None:
    expiring = _override(
        state=OverrideState.EXPIRING,
        last_updated_at_utc=DEADLINE,
    )
    with pytest.raises(ValueError, match="cancel_override"):
        complete_override(
            expiring,
            at_utc=DEADLINE,
            end_reason=OverrideEndReason.MANUALLY_CANCELLED,
        )
    with pytest.raises(ValueError, match="move backward"):
        complete_override(
            expiring,
            at_utc=DEADLINE - timedelta(seconds=1),
            end_reason=OverrideEndReason.EXPIRED,
        )


def test_lifecycle_rejects_naive_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_override_lifecycle(
            _override(),
            at_utc=datetime(2026, 7, 30, 12),
        )
