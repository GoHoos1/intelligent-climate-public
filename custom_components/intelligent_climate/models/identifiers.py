"""Stable identifiers for future equipment groups and zones."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class EquipmentGroupId:
    """Stable identifier for one physical HVAC equipment group."""

    value: UUID

    @classmethod
    def new(cls) -> EquipmentGroupId:
        """Create a new equipment-group identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> EquipmentGroupId:
        """Parse and validate an equipment-group identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ZoneId:
    """Stable identifier for one future climate zone."""

    value: UUID

    @classmethod
    def new(cls) -> ZoneId:
        """Create a new zone identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> ZoneId:
        """Parse and validate a zone identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ObservationSourceId:
    """Stable identifier for one configured observation source."""

    value: UUID

    @classmethod
    def new(cls) -> ObservationSourceId:
        """Create a new observation-source identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> ObservationSourceId:
        """Parse and validate an observation-source identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)
