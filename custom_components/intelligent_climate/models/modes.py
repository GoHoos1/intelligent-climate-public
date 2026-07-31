"""User-selected operating-mode terminology."""

from __future__ import annotations

from enum import StrEnum


class OperatingMode(StrEnum):
    """Persistent user intent, separate from current control execution state."""

    DISABLED = "disabled"
    OBSERVE_ONLY = "observe_only"
    MANUAL_CONTROL = "manual_control"
    SCHEDULED_SHADOW = "scheduled_shadow"
    SCHEDULED_CONTROL = "scheduled_control"


def parse_operating_mode(value: str) -> OperatingMode:
    """Parse and validate an operating-mode string."""
    return OperatingMode(value)
