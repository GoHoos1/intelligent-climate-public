"""Deterministic contact debounce/suspension state calculation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from ..models.contact import (
    ContactBinding,
    ContactUnavailablePolicy,
    validate_contact_binding,
)
from ..models.schema import SchemaValidationError


class ContactLifecycleState(StrEnum):
    """The documented inert contact lifecycle."""

    CLOSED = "closed"
    OPEN_DEBOUNCE = "open_debounce"
    GRACE = "grace"
    SUSPENDED = "suspended"
    CLOSE_DEBOUNCE = "close_debounce"
    RESUME_DELAY = "resume_delay"
    DEGRADED = "degraded"


class ContactReasonCode(StrEnum):
    """Privacy-bounded explanation for contact processing."""

    CLOSED = "closed"
    OPEN_DEBOUNCING = "open_debouncing"
    GRACE_ACTIVE = "grace_active"
    CONTACT_SUSPENDED = "contact_suspended"
    CLOSE_DEBOUNCING = "close_debouncing"
    RESUME_DELAY_ACTIVE = "resume_delay_active"
    CONTACT_UNAVAILABLE_TREATED_OPEN = "contact_unavailable_treated_open"
    CONTACT_UNAVAILABLE_DEGRADED = "contact_unavailable_degraded"
    BINDING_DISABLED = "binding_disabled"


@dataclass(frozen=True, slots=True)
class ContactInput:
    """All caller-supplied facts needed for one deterministic evaluation."""

    at_utc: datetime
    is_open: bool | None
    observed_since_utc: datetime | None
    previous_state: ContactLifecycleState | None = None


@dataclass(frozen=True, slots=True)
class ContactEvaluation:
    """One physically inert policy result; it never requests an HVAC action."""

    state: ContactLifecycleState
    reason_code: ContactReasonCode
    comfort_suppressed: bool
    degraded: bool
    next_evaluation_at_utc: datetime | None


def evaluate_contact(
    binding: ContactBinding, *, inputs: ContactInput
) -> ContactEvaluation:
    """Resolve debounce/grace/resume using caller timestamps only."""
    validate_contact_binding(binding)
    at = _utc(inputs.at_utc, "at_utc")
    if not binding.enabled:
        return _result(ContactLifecycleState.CLOSED, ContactReasonCode.BINDING_DISABLED)
    if inputs.is_open is None:
        if binding.unavailable_policy is ContactUnavailablePolicy.IGNORE_AND_DEGRADE:
            return _result(
                ContactLifecycleState.DEGRADED,
                ContactReasonCode.CONTACT_UNAVAILABLE_DEGRADED,
                degraded=True,
            )
        return _result(
            ContactLifecycleState.SUSPENDED,
            ContactReasonCode.CONTACT_UNAVAILABLE_TREATED_OPEN,
            suppressed=True,
        )
    since = _utc(inputs.observed_since_utc, "observed_since_utc")
    if since > at:
        raise SchemaValidationError("observed_since_utc", "must not be in the future")
    if inputs.is_open:
        return _open_result(binding, at, since, inputs.previous_state)
    return _closed_result(binding, at, since, inputs.previous_state)


def _open_result(
    binding: ContactBinding,
    at: datetime,
    since: datetime,
    previous: ContactLifecycleState | None,
) -> ContactEvaluation:
    if previous in {
        ContactLifecycleState.SUSPENDED,
        ContactLifecycleState.CLOSE_DEBOUNCE,
        ContactLifecycleState.RESUME_DELAY,
    }:
        return _result(
            ContactLifecycleState.SUSPENDED,
            ContactReasonCode.CONTACT_SUSPENDED,
            suppressed=True,
        )
    elapsed = at - since
    debounce = timedelta(seconds=binding.open_debounce_seconds)
    minimum = timedelta(seconds=binding.minimum_open_seconds)
    grace = timedelta(seconds=binding.grace_seconds)
    if elapsed < debounce:
        return _result(
            ContactLifecycleState.OPEN_DEBOUNCE,
            ContactReasonCode.OPEN_DEBOUNCING,
            next_at=since + debounce,
        )
    qualifying = max(minimum, debounce + grace)
    if elapsed < qualifying:
        return _result(
            ContactLifecycleState.GRACE,
            ContactReasonCode.GRACE_ACTIVE,
            next_at=since + qualifying,
        )
    return _result(
        ContactLifecycleState.SUSPENDED,
        ContactReasonCode.CONTACT_SUSPENDED,
        suppressed=True,
    )


def _closed_result(
    binding: ContactBinding,
    at: datetime,
    since: datetime,
    previous: ContactLifecycleState | None,
) -> ContactEvaluation:
    if previous not in {
        ContactLifecycleState.SUSPENDED,
        ContactLifecycleState.CLOSE_DEBOUNCE,
        ContactLifecycleState.RESUME_DELAY,
    }:
        return _result(ContactLifecycleState.CLOSED, ContactReasonCode.CLOSED)
    elapsed = at - since
    debounce = timedelta(seconds=binding.close_debounce_seconds)
    if elapsed < debounce:
        return _result(
            ContactLifecycleState.CLOSE_DEBOUNCE,
            ContactReasonCode.CLOSE_DEBOUNCING,
            suppressed=True,
            next_at=since + debounce,
        )
    resume = timedelta(seconds=binding.resume_delay_seconds)
    if elapsed < debounce + resume:
        return _result(
            ContactLifecycleState.RESUME_DELAY,
            ContactReasonCode.RESUME_DELAY_ACTIVE,
            suppressed=True,
            next_at=since + debounce + resume,
        )
    return _result(ContactLifecycleState.CLOSED, ContactReasonCode.CLOSED)


def _result(
    state: ContactLifecycleState,
    reason: ContactReasonCode,
    *,
    suppressed: bool = False,
    degraded: bool = False,
    next_at: datetime | None = None,
) -> ContactEvaluation:
    return ContactEvaluation(state, reason, suppressed, degraded, next_at)


def _utc(value: datetime | None, path: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise SchemaValidationError(path, "must be an aware datetime")
    return value.astimezone(UTC)
