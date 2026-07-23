"""Operating-mode terminology for the foundation slice."""

from __future__ import annotations

from enum import StrEnum


class OperatingMode(StrEnum):
    """Operating modes available in the repository foundation."""

    DISABLED = "disabled"
    OBSERVE_ONLY = "observe_only"


def parse_operating_mode(value: str) -> OperatingMode:
    """Parse and validate an operating-mode string."""
    return OperatingMode(value)
