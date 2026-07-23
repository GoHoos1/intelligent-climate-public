"""Common coordinator-backed entity support for Intelligent Climate."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import IntelligentClimateCoordinator
from .models import ZoneConfig, ZoneObservation


class IntelligentClimateZoneEntity(CoordinatorEntity[IntelligentClimateCoordinator]):
    """Base for one entity owned by an immutable configured zone."""

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        """Store stable configuration and subscribe through CoordinatorEntity."""
        super().__init__(coordinator)
        self.zone = zone

    @property
    def zone_observation(self) -> ZoneObservation | None:
        """Return this zone from the coordinator's current immutable snapshot."""
        return next(
            (
                observation
                for observation in self.coordinator.data.zones
                if observation.zone_id == self.zone.zone_id
            ),
            None,
        )
