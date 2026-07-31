"""Pure deterministic occupancy-mode resolution with injected deadlines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum

from ..models.identifiers import OccupancyBindingId, OccupancyModeId
from ..models.occupancy import (
    OccupancyBuiltInKind,
    OccupancyPolicy,
    OccupancyUnavailableFallback,
    validate_occupancy_policy,
)
from ..models.schema import SchemaValidationError


class OccupancyCandidateKind(StrEnum):
    """Whether a mapping is an arrival-like or departure-like transition."""

    ARRIVAL = "arrival"
    DEPARTURE = "departure"


class OccupancyReasonCode(StrEnum):
    """Privacy-safe explanation without raw person/device values."""

    MANUAL_SELECTION = "manual_selection"
    AUTOMATIC_PRIORITY = "automatic_priority"
    ARRIVAL_DELAY = "arrival_delay"
    DEPARTURE_DELAY = "departure_delay"
    UNAVAILABLE_HOME_FALLBACK = "unavailable_home_fallback"
    UNAVAILABLE_LAST_CONFIRMED = "unavailable_last_confirmed"
    NO_ACCEPTED_SOURCE = "no_accepted_source"


@dataclass(frozen=True, slots=True)
class OccupancyCandidate:
    """One raw-state-free mapped candidate, supplied by a later runtime layer."""

    binding_id: OccupancyBindingId
    proposed_mode_id: OccupancyModeId
    kind: OccupancyCandidateKind
    available: bool
    observed_since_utc: datetime


@dataclass(frozen=True, slots=True)
class OccupancyResolutionInput:
    """All injected inputs; no source read, timer, or wall-clock access occurs."""

    at_utc: datetime
    last_confirmed_mode_id: OccupancyModeId | None
    manual_mode_id: OccupancyModeId | None = None
    manual_expires_at_utc: datetime | None = None
    candidates: tuple[OccupancyCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class OccupancyDecision:
    """An inert mode decision and next caller deadline, never a command request."""

    mode_id: OccupancyModeId | None
    reason_code: OccupancyReasonCode
    changed: bool
    next_evaluation_at_utc: datetime | None


def resolve_occupancy(
    policy: OccupancyPolicy, *, inputs: OccupancyResolutionInput
) -> OccupancyDecision:
    """Resolve manual, delayed automatic, and unavailable fallback precedence."""
    validate_occupancy_policy(policy)
    at = _utc(inputs.at_utc, "at_utc")
    mode_ids = {mode.mode_id for mode in policy.modes}
    if (
        inputs.last_confirmed_mode_id is not None
        and inputs.last_confirmed_mode_id not in mode_ids
    ):
        raise SchemaValidationError("last_confirmed_mode_id", "is not configured")
    if inputs.manual_mode_id is not None:
        if inputs.manual_mode_id not in mode_ids:
            raise SchemaValidationError("manual_mode_id", "is not configured")
        expiry = (
            _utc(inputs.manual_expires_at_utc, "manual_expires_at_utc")
            if inputs.manual_expires_at_utc is not None
            else None
        )
        if expiry is None or expiry > at:
            return _decision(
                inputs.manual_mode_id,
                OccupancyReasonCode.MANUAL_SELECTION,
                inputs.last_confirmed_mode_id,
                expiry,
            )
    accepted: list[tuple[OccupancyCandidate, datetime]] = []
    pending: list[tuple[OccupancyCandidate, datetime]] = []
    configured_sources = {
        source.binding_id: source for source in policy.sources if source.enabled
    }
    for index, candidate in enumerate(inputs.candidates):
        source = configured_sources.get(candidate.binding_id)
        if source is None:
            raise SchemaValidationError(
                f"candidates[{index}].binding_id", "is unknown or disabled"
            )
        if candidate.proposed_mode_id not in mode_ids or not isinstance(
            candidate.kind, OccupancyCandidateKind
        ):
            raise SchemaValidationError(
                f"candidates[{index}]", "has an unsupported mode or transition kind"
            )
        since = _utc(
            candidate.observed_since_utc, f"candidates[{index}].observed_since_utc"
        )
        if since > at:
            raise SchemaValidationError(
                f"candidates[{index}].observed_since_utc", "must not be in the future"
            )
        if not candidate.available:
            continue
        delay = (
            policy.arrival_delay_seconds
            if candidate.kind is OccupancyCandidateKind.ARRIVAL
            else policy.departure_delay_seconds
        )
        ready = since + timedelta(seconds=delay)
        (accepted if ready <= at else pending).append((candidate, ready))
    if accepted:
        rank = {mode_id: index for index, mode_id in enumerate(policy.priority_order)}
        candidate, _ = min(accepted, key=lambda item: rank[item[0].proposed_mode_id])
        return _decision(
            candidate.proposed_mode_id,
            OccupancyReasonCode.AUTOMATIC_PRIORITY,
            inputs.last_confirmed_mode_id,
            min((deadline for _, deadline in pending), default=None),
        )
    if pending:
        reason = (
            OccupancyReasonCode.ARRIVAL_DELAY
            if any(
                candidate.kind is OccupancyCandidateKind.ARRIVAL
                for candidate, _ in pending
            )
            else OccupancyReasonCode.DEPARTURE_DELAY
        )
        return _decision(
            inputs.last_confirmed_mode_id,
            reason,
            inputs.last_confirmed_mode_id,
            min(deadline for _, deadline in pending),
        )
    if inputs.candidates and not any(item.available for item in inputs.candidates):
        if policy.unavailable_fallback is OccupancyUnavailableFallback.LAST_CONFIRMED:
            return _decision(
                inputs.last_confirmed_mode_id,
                OccupancyReasonCode.UNAVAILABLE_LAST_CONFIRMED,
                inputs.last_confirmed_mode_id,
                None,
            )
        home = next(
            (
                mode.mode_id
                for mode in policy.modes
                if mode.kind is OccupancyBuiltInKind.HOME
            ),
            None,
        )
        return _decision(
            home,
            OccupancyReasonCode.UNAVAILABLE_HOME_FALLBACK,
            inputs.last_confirmed_mode_id,
            None,
        )
    return _decision(
        inputs.last_confirmed_mode_id,
        OccupancyReasonCode.NO_ACCEPTED_SOURCE,
        inputs.last_confirmed_mode_id,
        None,
    )


def _decision(
    mode_id: OccupancyModeId | None,
    reason: OccupancyReasonCode,
    previous: OccupancyModeId | None,
    next_at: datetime | None,
) -> OccupancyDecision:
    return OccupancyDecision(mode_id, reason, mode_id != previous, next_at)


def _utc(value: datetime | None, path: str) -> datetime:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise SchemaValidationError(path, "must be an aware datetime")
    return value.astimezone(UTC)
