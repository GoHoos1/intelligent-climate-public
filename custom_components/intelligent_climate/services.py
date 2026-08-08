"""Administrator-only zero-command operating-mode actions."""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import ACTION_SET_OPERATING_MODE, DOMAIN
from .models import (
    ActivityReason,
    ActivitySeverity,
    ActivityType,
    OperatingMode,
    encode_phase2_equipment_group_document,
)

if TYPE_CHECKING:
    from .coordinator import IntelligentClimateCoordinator

_ALLOWED_ZERO_COMMAND_MODES = frozenset(
    {
        OperatingMode.OBSERVE_ONLY,
        OperatingMode.MANUAL_CONTROL,
        OperatingMode.SCHEDULED_SHADOW,
    }
)


def async_register_services(hass: HomeAssistant) -> None:
    """Register the suppressed-only mode action once for all entries."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("services_registered"):
        return

    async def _async_set_operating_mode(call: ServiceCall) -> None:
        await async_set_operating_mode(hass, call)

    hass.services.async_register(
        DOMAIN,
        ACTION_SET_OPERATING_MODE,
        _async_set_operating_mode,
        schema=vol.Schema(
            {
                vol.Required("entry_id"): str,
                vol.Required("mode"): vol.In(
                    [item.value for item in sorted(_ALLOWED_ZERO_COMMAND_MODES)]
                ),
            }
        ),
    )
    data["services_registered"] = True


async def async_set_operating_mode(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Persist one explicit zero-command mode and reload safely."""
    user_id = call.context.user_id
    user = None if user_id is None else await hass.auth.async_get_user(user_id)
    if user is None or not user.is_admin:
        raise ServiceValidationError(
            "Administrator permission is required to change operating mode"
        )

    entry_id = call.data["entry_id"]
    entry = hass.config_entries.async_get_entry(entry_id)
    coordinator: IntelligentClimateCoordinator | None = (
        None if entry is None else getattr(entry, "runtime_data", None)
    )
    if entry is None or coordinator is None or coordinator.phase2_runtime is None:
        raise ServiceValidationError("Intelligent Climate entry is not loaded")

    mode = OperatingMode(call.data["mode"])
    if mode not in _ALLOWED_ZERO_COMMAND_MODES:
        raise ServiceValidationError("This release cannot arm active control")
    runtime = coordinator.phase2_runtime
    current = runtime.migration.config.desired_operating_mode
    if mode is current:
        return
    if mode is OperatingMode.SCHEDULED_SHADOW:
        schedule = runtime.schedule_store.document
        if schedule is None or not any(
            zone.enabled for zone in schedule.zones.values()
        ):
            raise ServiceValidationError(
                "Save and enable a valid schedule before starting Scheduled Shadow"
            )

    updated = replace(
        runtime.migration.config,
        automation_enabled=mode is OperatingMode.SCHEDULED_SHADOW,
        desired_operating_mode=mode,
    )
    coordinator.activity.record(
        activity_type=ActivityType.RUNTIME_STATE_CHANGED,
        reason_code=ActivityReason.CONTROL_STATE_CHANGED,
        severity=ActivitySeverity.INFO,
        explanation=(
            "Scheduled Shadow started; equipment commands remain suppressed."
            if mode is OperatingMode.SCHEDULED_SHADOW
            else (
                "Manual Control selected; this release remains zero-command."
                if mode is OperatingMode.MANUAL_CONTROL
                else "Observe Only selected; automation remains off."
            )
        ),
        detail={"previous_state": current.value, "new_state": mode.value},
    )
    hass.config_entries.async_update_entry(
        entry,
        data=dict(encode_phase2_equipment_group_document(updated)),
    )
    if not await hass.config_entries.async_reload(entry.entry_id):
        raise ServiceValidationError("Operating mode was saved but reload failed")
