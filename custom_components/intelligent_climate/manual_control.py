"""Typed, physically inert Manual Control action boundary for Phase 2 Task 20."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from math import isfinite

from .control.precedence import (
    ManualIntentDecision,
    ManualIntentRequest,
    ManualIntentSource,
    evaluate_manual_intent_authority,
)
from .models.control import ControlExecutionState
from .models.identifiers import ZoneId
from .models.modes import OperatingMode
from .models.phase2_schema import Phase2SafetyLimits

MANUAL_INTENT_MAX_AGE = timedelta(seconds=30)


class ManualActionKind(StrEnum):
    """Allowlisted explicit-user action shapes; these are not service names."""

    SET_TARGET = "set_target"
    SET_HVAC_MODE = "set_hvac_mode"
    SET_FAN_MODE = "set_fan_mode"


@dataclass(frozen=True, slots=True)
class ManualControlAction:
    """Fresh typed UI action with no executable Home Assistant payload."""

    kind: ManualActionKind
    entry_id: str
    zone_id: ZoneId
    observed_revision: int
    user_context_id: str
    created_at_utc: datetime
    target_c: float | None = None
    hvac_mode: str | None = None
    fan_mode: str | None = None

    def __post_init__(self) -> None:
        if not self.entry_id or not self.user_context_id:
            raise ValueError("entry and authenticated user context are required")
        if self.observed_revision < 1:
            raise ValueError("observed_revision must be positive")
        _utc(self.created_at_utc)
        fields = (
            self.target_c is not None,
            self.hvac_mode is not None,
            self.fan_mode is not None,
        )
        expected = {
            ManualActionKind.SET_TARGET: (True, False, False),
            ManualActionKind.SET_HVAC_MODE: (False, True, False),
            ManualActionKind.SET_FAN_MODE: (False, False, True),
        }[self.kind]
        if fields != expected:
            raise ValueError("manual action fields do not match action kind")
        if self.target_c is not None and (
            isinstance(self.target_c, bool) or not isfinite(self.target_c)
        ):
            raise ValueError("manual target must be finite")
        for name, value in (("hvac_mode", self.hvac_mode), ("fan_mode", self.fan_mode)):
            if value is not None and (not value.strip() or len(value) > 64):
                raise ValueError(f"{name} must be bounded nonempty text")


@dataclass(frozen=True, slots=True)
class ManualActionDecision:
    """Inert validation result that cannot authorize physical dispatch."""

    accepted_for_future_planning: bool
    authority: ManualIntentDecision
    reason_code: str


def evaluate_manual_control_action(
    action: ManualControlAction,
    *,
    operating_mode: OperatingMode,
    control_state: ControlExecutionState,
    current_revision: int,
    now_utc: datetime,
    safety_limits: Phase2SafetyLimits,
    supported_hvac_modes: tuple[str, ...],
    supported_fan_modes: tuple[str, ...],
) -> ManualActionDecision:
    """Validate freshness, user authority, revision, limits, and capabilities."""
    now = _utc(now_utc)
    fresh = (
        action.created_at_utc <= now <= action.created_at_utc + MANUAL_INTENT_MAX_AGE
    )
    authority = evaluate_manual_intent_authority(
        ManualIntentRequest(
            operating_mode=operating_mode,
            control_state=control_state,
            source=ManualIntentSource.EXPLICIT_USER,
            authenticated_user=bool(action.user_context_id),
            fresh=fresh,
            observed_revision_matches=action.observed_revision == current_revision,
        )
    )
    if not authority.authorized:
        return ManualActionDecision(False, authority, authority.code.value)
    reason = _value_rejection(
        action,
        safety_limits=safety_limits,
        supported_hvac_modes=supported_hvac_modes,
        supported_fan_modes=supported_fan_modes,
    )
    if reason is not None:
        return ManualActionDecision(False, authority, reason)
    return ManualActionDecision(True, authority, "validated_explicit_user_action")


def _value_rejection(
    action: ManualControlAction,
    *,
    safety_limits: Phase2SafetyLimits,
    supported_hvac_modes: tuple[str, ...],
    supported_fan_modes: tuple[str, ...],
) -> str | None:
    if action.kind is ManualActionKind.SET_TARGET:
        assert action.target_c is not None
        minimum = min(
            safety_limits.minimum_heating_target_c,
            safety_limits.minimum_cooling_target_c,
        )
        maximum = max(
            safety_limits.maximum_heating_target_c,
            safety_limits.maximum_cooling_target_c,
        )
        return (
            None if minimum <= action.target_c <= maximum else "target_outside_limits"
        )
    if action.kind is ManualActionKind.SET_HVAC_MODE:
        return (
            None
            if action.hvac_mode in supported_hvac_modes
            else "unsupported_hvac_mode"
        )
    return None if action.fan_mode in supported_fan_modes else "unsupported_fan_mode"


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("manual action timestamp must be timezone-aware")
    return value.astimezone(UTC)
