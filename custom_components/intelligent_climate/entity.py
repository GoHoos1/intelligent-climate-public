"""Common coordinator-backed entity support for Intelligent Climate."""

from __future__ import annotations

from typing import cast

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, NAME
from .coordinator import IntelligentClimateCoordinator
from .models import ZoneConfig, ZoneObservation

_GROUP_MODEL = "Equipment group"
_ZONE_MODEL = "Climate zone"


def build_zone_device_info(
    coordinator: IntelligentClimateCoordinator,
    zone: ZoneConfig,
) -> DeviceInfo:
    """Build child-device information across supported Home Assistant versions."""
    group = coordinator.configuration.equipment_group
    group_identifier = (DOMAIN, str(group.equipment_group_id))
    group_device = None
    if (
        coordinator.hass.config_entries.async_get_entry(coordinator.entry.entry_id)
        is not None
    ):
        group_device = dr.async_get(coordinator.hass).async_get_or_create(
            config_entry_id=coordinator.entry.entry_id,
            identifiers={group_identifier},
            manufacturer=NAME,
            model=_GROUP_MODEL,
            name=group.name,
        )
    device_info = DeviceInfo(
        identifiers={(DOMAIN, str(zone.zone_id))},
        manufacturer=NAME,
        model=_ZONE_MODEL,
        name=zone.name,
    )
    if "via_device_id" in DeviceInfo.__annotations__ and group_device is not None:
        device_info["via_device_id"] = group_device.id
    else:
        cast(dict[str, object], device_info)["via_device"] = group_identifier
    return device_info


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
