"""Pure correlated thermostat fan-mode restoration policy."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from ..models.fan import (
    FanBindingKind,
    FanControlBinding,
    FanPolicy,
    validate_fan_policy,
)
from ..models.schema import SchemaValidationError


class FanRestoreReasonCode(StrEnum):
    """Privacy-safe result of restoration eligibility."""

    ELIGIBLE = "eligible"
    NOT_THERMOSTAT_FAN_MODE = "not_thermostat_fan_mode"
    NO_PRIOR_MODE = "no_prior_mode"
    CORRELATION_MISMATCH = "correlation_mismatch"
    CURRENT_MODE_MISMATCH = "current_mode_mismatch"
    EXTERNAL_CHANGE = "external_change"


@dataclass(frozen=True, slots=True)
class FanRestoreEvidence:
    """All evidence required before a later layer may plan a restore."""

    policy: FanPolicy
    prior_mode: str | None
    current_mode: str | None
    correlation_matches: bool
    external_change_observed: bool


@dataclass(frozen=True, slots=True)
class FanRestoreDecision:
    """An inert restore eligibility result, never a command."""

    eligible: bool
    reason_code: FanRestoreReasonCode
    restore_mode: str | None


def evaluate_fan_restore(evidence: FanRestoreEvidence) -> FanRestoreDecision:
    """Allow restore only while exact correlated circulation state remains."""
    validate_fan_policy(evidence.policy)
    binding = evidence.policy.control_binding
    _validate_evidence(binding, evidence)
    if binding.kind is not FanBindingKind.THERMOSTAT_FAN_MODE:
        return _decision(FanRestoreReasonCode.NOT_THERMOSTAT_FAN_MODE)
    if evidence.prior_mode is None:
        return _decision(FanRestoreReasonCode.NO_PRIOR_MODE)
    if evidence.external_change_observed:
        return _decision(FanRestoreReasonCode.EXTERNAL_CHANGE)
    if not evidence.correlation_matches:
        return _decision(FanRestoreReasonCode.CORRELATION_MISMATCH)
    if evidence.current_mode != binding.circulation_mode:
        return _decision(FanRestoreReasonCode.CURRENT_MODE_MISMATCH)
    return FanRestoreDecision(
        eligible=True,
        reason_code=FanRestoreReasonCode.ELIGIBLE,
        restore_mode=evidence.prior_mode,
    )


def _validate_evidence(
    binding: FanControlBinding, evidence: FanRestoreEvidence
) -> None:
    if not isinstance(evidence.correlation_matches, bool):
        raise SchemaValidationError("correlation_matches", "must be a boolean")
    if not isinstance(evidence.external_change_observed, bool):
        raise SchemaValidationError("external_change_observed", "must be a boolean")
    for path, value in (
        ("prior_mode", evidence.prior_mode),
        ("current_mode", evidence.current_mode),
    ):
        if value is not None and (
            not isinstance(value, str) or not value or len(value) > 64
        ):
            raise SchemaValidationError(path, "must be a bounded mode or null")
    if binding.kind is FanBindingKind.THERMOSTAT_FAN_MODE:
        if evidence.prior_mode is not None and (
            evidence.prior_mode not in binding.supported_modes
            or evidence.prior_mode == binding.circulation_mode
        ):
            raise SchemaValidationError(
                "prior_mode", "must be a mapped non-circulation supported mode"
            )
        if evidence.current_mode is not None and (
            evidence.current_mode not in binding.supported_modes
        ):
            raise SchemaValidationError(
                "current_mode", "must be a mapped supported mode"
            )


def _decision(reason: FanRestoreReasonCode) -> FanRestoreDecision:
    return FanRestoreDecision(False, reason, None)
