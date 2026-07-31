"""Stable identifiers for Intelligent Climate domain objects."""

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


@dataclass(frozen=True, slots=True)
class ScheduleProfileId:
    """Stable identifier for one weekly schedule profile."""

    value: UUID

    @classmethod
    def new(cls) -> ScheduleProfileId:
        """Create a new schedule-profile identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> ScheduleProfileId:
        """Parse and validate a schedule-profile identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class SchedulePeriodId:
    """Stable identifier for one weekly schedule period."""

    value: UUID

    @classmethod
    def new(cls) -> SchedulePeriodId:
        """Create a new schedule-period identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> SchedulePeriodId:
        """Parse and validate a schedule-period identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class OverrideId:
    """Stable identifier for one manual override."""

    value: UUID

    @classmethod
    def new(cls) -> OverrideId:
        """Create a new override identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> OverrideId:
        """Parse and validate an override identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class DecisionId:
    """Stable identifier for one control decision."""

    value: UUID

    @classmethod
    def new(cls) -> DecisionId:
        """Create a new control-decision identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> DecisionId:
        """Parse and validate a control-decision identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class CommandId:
    """Stable identifier for one planned command."""

    value: UUID

    @classmethod
    def new(cls) -> CommandId:
        """Create a new command identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> CommandId:
        """Parse and validate a command identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class CorrelationId:
    """Stable identifier shared by one command and its observations."""

    value: UUID

    @classmethod
    def new(cls) -> CorrelationId:
        """Create a new command-correlation identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> CorrelationId:
        """Parse and validate a command-correlation identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class SafetyEvaluationId:
    """Stable identifier for one complete safety evaluation."""

    value: UUID

    @classmethod
    def new(cls) -> SafetyEvaluationId:
        """Create a new safety-evaluation identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> SafetyEvaluationId:
        """Parse and validate a safety-evaluation identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class ContactBindingId:
    """Stable identifier for one configured window or door binding."""

    value: UUID

    @classmethod
    def new(cls) -> ContactBindingId:
        """Create a new contact-binding identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> ContactBindingId:
        """Parse and validate a contact-binding identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class OccupancyModeId:
    """Stable identifier for one configured occupancy mode."""

    value: UUID

    @classmethod
    def new(cls) -> OccupancyModeId:
        """Create a new occupancy-mode identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> OccupancyModeId:
        """Parse and validate an occupancy-mode identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)


@dataclass(frozen=True, slots=True)
class OccupancyBindingId:
    """Stable identifier for one configured occupancy source binding."""

    value: UUID

    @classmethod
    def new(cls) -> OccupancyBindingId:
        """Create a new occupancy-binding identifier."""
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str) -> OccupancyBindingId:
        """Parse and validate an occupancy-binding identifier."""
        return cls(UUID(value))

    def __str__(self) -> str:
        """Return the canonical identifier string."""
        return str(self.value)
