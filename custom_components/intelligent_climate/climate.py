"""Read-only virtual climate entities for Intelligent Climate zones."""

from __future__ import annotations

import math
from typing import Any, override

from homeassistant.components.climate import ClimateEntity
from homeassistant.components.climate.const import (
    ClimateEntityFeature,
    ClimateEntityStateAttribute,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigSubentry
from homeassistant.const import PRECISION_TENTHS, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.temperature import display_temp

from .const import DOMAIN, NAME, SUBENTRY_TYPE_ZONE
from .coordinator import IntelligentClimateCoordinator
from .entity import IntelligentClimateZoneEntity
from .models import NormalizedClimateState, RuntimeConfigurationState, ZoneConfig
from .type_aliases import IntelligentClimateConfigEntry

_TARGET_AGREEMENT_C = 0.1
_FLOAT_TOLERANCE = 1e-9
_ZONE_MODEL = "Climate zone"
_GROUP_MODEL = "Equipment group"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IntelligentClimateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up exactly one read-only climate entity per configured zone."""
    coordinator = entry.runtime_data
    subentries = _zone_subentries_by_id(entry)
    matched_subentries: list[tuple[ZoneConfig, ConfigSubentry]] = []
    configured_zones = (
        coordinator.configuration.zones
        if coordinator.configuration.state is RuntimeConfigurationState.CONFIGURED
        else ()
    )
    for zone in configured_zones:
        matches = subentries.get(str(zone.zone_id), ())
        if len(matches) != 1:
            raise ConfigEntryError(
                f"Zone {zone.zone_id} must match exactly one config subentry"
            )
        matched_subentries.append((zone, matches[0]))

    equipment_group = coordinator.configuration.equipment_group
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, str(equipment_group.equipment_group_id))},
        manufacturer=NAME,
        model=_GROUP_MODEL,
        name=equipment_group.name,
    )

    for zone, subentry in matched_subentries:
        async_add_entities(
            [IntelligentClimateZoneClimateEntity(coordinator, zone)],
            config_subentry_id=subentry.subentry_id,
        )


def _zone_subentries_by_id(
    entry: IntelligentClimateConfigEntry,
) -> dict[str, list[ConfigSubentry]]:
    """Index zone subentries by their already validated stable zone ID."""
    result: dict[str, list[ConfigSubentry]] = {}
    for subentry in entry.subentries.values():
        if subentry.subentry_type != SUBENTRY_TYPE_ZONE:
            continue
        if subentry.unique_id is None:
            raise ConfigEntryError("Zone config subentry is missing its stable ID")
        result.setdefault(subentry.unique_id, []).append(subentry)
    return result


class IntelligentClimateZoneClimateEntity(
    IntelligentClimateZoneEntity,
    ClimateEntity,
):
    """Present one zone's coordinator snapshot without writable capabilities."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_precision = PRECISION_TENTHS
    _attr_supported_features = ClimateEntityFeature(0)
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: IntelligentClimateCoordinator,
        zone: ZoneConfig,
    ) -> None:
        """Initialize stable identity and virtual zone device information."""
        super().__init__(coordinator, zone)
        equipment_group = coordinator.configuration.equipment_group
        self._attr_unique_id = f"{zone.zone_id}:zone"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(zone.zone_id))},
            manufacturer=NAME,
            model=_ZONE_MODEL,
            name=zone.name,
            via_device=(DOMAIN, str(equipment_group.equipment_group_id)),
        )

    @property
    @override
    def available(self) -> bool:
        """Return strict current observation availability."""
        observation = self.zone_observation
        return (
            super().available
            and observation is not None
            and not self.coordinator.data.reconciling
            and self.coordinator.configuration.options.observation_enabled
            and observation.effective_temperature_c is not None
            and any(state.available for state in observation.thermostat_states)
        )

    @property
    @override
    def current_temperature(self) -> float | None:
        """Return current effective Celsius temperature without display conversion."""
        if (observation := self.zone_observation) is None:
            return None
        return observation.effective_temperature_c

    @property
    @override
    def current_humidity(self) -> float | None:
        """Return effective humidity only for a configured humidity surface."""
        if not self.zone.humidity_sources:
            return None
        if (observation := self.zone_observation) is None:
            return None
        return observation.effective_humidity_pct

    @property
    @override
    def hvac_mode(self) -> HVACMode | None:
        """Return the common mode among currently available thermostats."""
        states = self._available_thermostat_states
        if not states:
            return None
        return _common_value(tuple(state.hvac_mode for state in states))

    @property
    @override
    def hvac_modes(self) -> list[HVACMode]:
        """Expose only the current observed mode for service validation."""
        return [mode] if (mode := self.hvac_mode) is not None else []

    @property
    @override
    def hvac_action(self) -> HVACAction | None:
        """Return the common action among currently available thermostats."""
        states = self._available_thermostat_states
        if not states:
            return None
        return _common_value(tuple(state.hvac_action for state in states))

    @property
    def _available_thermostat_states(self) -> tuple[NormalizedClimateState, ...]:
        observation = self.zone_observation
        if observation is None:
            return ()
        return tuple(
            state for state in observation.thermostat_states if state.available
        )

    @property
    @override
    def target_temperature(self) -> float | None:
        """Return an agreed single observed Celsius target."""
        single, _ = self._observed_target
        return single

    @property
    @override
    def target_temperature_low(self) -> float | None:
        """Return the agreed observed Celsius range low endpoint."""
        _, target_range = self._observed_target
        return None if target_range is None else target_range[0]

    @property
    @override
    def target_temperature_high(self) -> float | None:
        """Return the agreed observed Celsius range high endpoint."""
        _, target_range = self._observed_target
        return None if target_range is None else target_range[1]

    @property
    def _observed_target(self) -> tuple[float | None, tuple[float, float] | None]:
        observation = self.zone_observation
        if observation is None or not observation.thermostat_states:
            return (None, None)
        states = observation.thermostat_states
        if any(not state.available for state in states):
            return (None, None)

        single_values = tuple(state.target_temperature_c for state in states)
        if (
            all(_is_finite(value) for value in single_values)
            and all(
                state.target_low_c is None and state.target_high_c is None
                for state in states
            )
            and _values_agree(single_values)
        ):
            single = single_values[0]
            if single is not None:
                return (single, None)

        low_values = tuple(state.target_low_c for state in states)
        high_values = tuple(state.target_high_c for state in states)
        if (
            all(state.target_temperature_c is None for state in states)
            and all(_is_finite(value) for value in low_values)
            and all(_is_finite(value) for value in high_values)
            and all(
                low <= high
                for low, high in zip(low_values, high_values, strict=True)
                if low is not None and high is not None
            )
            and _values_agree(low_values)
            and _values_agree(high_values)
        ):
            low = low_values[0]
            high = high_values[0]
            if low is not None and high is not None:
                return (None, (low, high))
        return (None, None)

    @property
    @override
    def extra_state_attributes(self) -> dict[str, float] | None:
        """Serialize one bounded observed target with standard climate keys."""
        single, target_range = self._observed_target
        if single is not None:
            return {
                ClimateEntityStateAttribute.TEMPERATURE.value: (
                    self._display_temperature(single)
                )
            }
        if target_range is not None:
            low, high = target_range
            return {
                ClimateEntityStateAttribute.TARGET_TEMP_LOW.value: (
                    self._display_temperature(low)
                ),
                ClimateEntityStateAttribute.TARGET_TEMP_HIGH.value: (
                    self._display_temperature(high)
                ),
            }
        return None

    def _display_temperature(self, value: float) -> float:
        """Convert an observed Celsius target through Home Assistant display rules."""
        displayed = display_temp(
            self.hass,
            value,
            UnitOfTemperature.CELSIUS,
            self.precision,
        )
        assert displayed is not None
        return displayed

    @override
    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Reject mutation of an observation-only entity."""
        raise self._unsupported_control_error()

    @override
    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Reject mutation of an observation-only entity."""
        raise self._unsupported_control_error()

    @override
    async def async_set_humidity(self, humidity: int) -> None:
        """Reject mutation of an observation-only entity."""
        raise self._unsupported_control_error()

    @override
    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Reject mutation of an observation-only entity."""
        raise self._unsupported_control_error()

    @override
    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Reject mutation of an observation-only entity."""
        raise self._unsupported_control_error()

    @override
    async def async_set_swing_mode(self, swing_mode: str) -> None:
        """Reject mutation of an observation-only entity."""
        raise self._unsupported_control_error()

    @override
    async def async_set_swing_horizontal_mode(
        self,
        swing_horizontal_mode: str,
    ) -> None:
        """Reject mutation of an observation-only entity."""
        raise self._unsupported_control_error()

    @override
    async def async_turn_on(self) -> None:
        """Reject mutation of an observation-only entity."""
        raise self._unsupported_control_error()

    @override
    async def async_turn_off(self) -> None:
        """Reject mutation of an observation-only entity."""
        raise self._unsupported_control_error()

    @override
    async def async_toggle(self) -> None:
        """Reject mutation of an observation-only entity."""
        raise self._unsupported_control_error()

    def _unsupported_control_error(self) -> ServiceValidationError:
        """Record one payload-free attempt and build the translated rejection."""
        self.coordinator.async_record_unsupported_control_attempt(self.zone.zone_id)
        return ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="observation_only",
        )


def _common_value[ValueT](
    values: tuple[ValueT | None, ...],
) -> ValueT | None:
    """Return one non-missing common value or fail closed."""
    if not values or any(value is None for value in values):
        return None
    first = values[0]
    return first if all(value == first for value in values[1:]) else None


def _is_finite(value: float | None) -> bool:
    return value is not None and math.isfinite(value)


def _values_agree(values: tuple[float | None, ...]) -> bool:
    finite_values = tuple(value for value in values if value is not None)
    return (
        len(finite_values) == len(values)
        and max(finite_values) - min(finite_values)
        <= _TARGET_AGREEMENT_C + _FLOAT_TOLERANCE
    )
