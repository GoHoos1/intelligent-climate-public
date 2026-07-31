"""Immutable manual-override cancellation, extension, and expiration semantics."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import UTC, datetime

from ..models.override import (
    ControlledValues,
    ManualOverride,
    OverrideEndReason,
    OverrideExpirationPolicy,
    OverrideReasonCode,
    OverrideState,
    validate_controlled_values,
)
from .expiration import ExpirationCalculation


@dataclass(frozen=True, slots=True)
class OverrideTransition:
    """One pure lifecycle result with a privacy-safe reason."""

    override: ManualOverride
    previous_state: OverrideState
    reason_code: OverrideReasonCode
    explanation: str
    changed: bool


def evaluate_override_lifecycle(
    value: ManualOverride,
    *,
    at_utc: datetime,
) -> OverrideTransition:
    """Enter EXPIRING exactly at or after a resolved automatic deadline."""
    at = _utc(at_utc)
    if value.state is not OverrideState.ACTIVE:
        return _transition(value, value, OverrideReasonCode.ACTIVE, changed=False)
    if value.expires_at_utc is None or at < value.expires_at_utc:
        return _transition(value, value, OverrideReasonCode.ACTIVE, changed=False)
    updated = replace(
        value,
        state=OverrideState.EXPIRING,
        last_updated_at_utc=at,
    )
    return _transition(
        value,
        updated,
        OverrideReasonCode.EXPIRATION_DUE,
        changed=True,
    )


def cancel_override(
    value: ManualOverride,
    *,
    at_utc: datetime,
) -> OverrideTransition:
    """End an active or expiring override without any command side effect."""
    at = _utc(at_utc)
    _require_mutable(value, at)
    updated = replace(
        value,
        state=OverrideState.ENDED,
        last_updated_at_utc=at,
        ended_at_utc=at,
        end_reason=OverrideEndReason.MANUALLY_CANCELLED,
    )
    return _transition(
        value,
        updated,
        OverrideReasonCode.MANUALLY_CANCELLED,
        changed=True,
    )


def extend_override(
    value: ManualOverride,
    *,
    at_utc: datetime,
    expiration_policy: OverrideExpirationPolicy,
    expiration: ExpirationCalculation,
    requested_values: ControlledValues | None = None,
) -> OverrideTransition:
    """Replace expiration deterministically while preserving stable identity."""
    at = _utc(at_utc)
    _require_mutable(value, at)
    replacement_values = requested_values or value.requested_values
    validate_controlled_values(value.controlled_fields, replacement_values)
    if expiration.expires_at_utc is not None:
        deadline = _utc(expiration.expires_at_utc)
        if deadline < at:
            raise ValueError("extended expiration cannot precede extension time")
    updated = replace(
        value,
        requested_values=replacement_values,
        last_updated_at_utc=at,
        expiration_policy=expiration_policy,
        expires_at_utc=expiration.expires_at_utc,
        anchor_transition_key=expiration.anchor_transition_key,
        state=OverrideState.ACTIVE,
        ended_at_utc=None,
        end_reason=None,
    )
    return _transition(
        value,
        updated,
        OverrideReasonCode.EXTENDED,
        changed=updated != value,
    )


def complete_override(
    value: ManualOverride,
    *,
    at_utc: datetime,
    end_reason: OverrideEndReason,
) -> OverrideTransition:
    """End only an EXPIRING override after a caller-owned reconciliation."""
    at = _utc(at_utc)
    if value.state is not OverrideState.EXPIRING:
        raise ValueError("only an expiring override can be completed")
    if end_reason is OverrideEndReason.MANUALLY_CANCELLED:
        raise ValueError("manual cancellation must use cancel_override")
    if at < value.last_updated_at_utc:
        raise ValueError("completion time cannot move backward")
    updated = replace(
        value,
        state=OverrideState.ENDED,
        last_updated_at_utc=at,
        ended_at_utc=at,
        end_reason=end_reason,
    )
    return _transition(
        value,
        updated,
        OverrideReasonCode.ENDED,
        changed=True,
    )


def _require_mutable(value: ManualOverride, at: datetime) -> None:
    if value.state is OverrideState.ENDED:
        raise ValueError("ended override cannot be changed")
    if at < value.last_updated_at_utc:
        raise ValueError("override update time cannot move backward")


def _transition(
    previous: ManualOverride,
    current: ManualOverride,
    reason: OverrideReasonCode,
    *,
    changed: bool,
) -> OverrideTransition:
    explanations = {
        OverrideReasonCode.ACTIVE: "The manual override remains active.",
        OverrideReasonCode.EXTENDED: "The manual override expiration was replaced.",
        OverrideReasonCode.MANUALLY_CANCELLED: (
            "The manual override was manually cancelled."
        ),
        OverrideReasonCode.EXPIRATION_DUE: (
            "The manual override reached its expiration boundary."
        ),
        OverrideReasonCode.ENDED: (
            "The manual override ended after caller-owned reconciliation."
        ),
    }
    return OverrideTransition(
        override=current,
        previous_state=previous.state,
        reason_code=reason,
        explanation=explanations[reason],
        changed=changed,
    )


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("time must be timezone-aware")
    if value.utcoffset() != UTC.utcoffset(value):
        raise ValueError("time must be expressed in UTC")
    return value
