"""Shared strict config-entry typing without runtime import cycles."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    from .coordinator import IntelligentClimateCoordinator

type IntelligentClimateConfigEntry = ConfigEntry[IntelligentClimateCoordinator]
