"""Suppressed-only operating-mode action tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest
from homeassistant.core import Context, HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.intelligent_climate.const import (
    ACTION_SET_OPERATING_MODE,
    DOMAIN,
)
from custom_components.intelligent_climate.models import (
    EquipmentGroupConfig,
    EquipmentGroupId,
    EquipmentRelationship,
    EquipmentType,
    OperatingMode,
    Phase2EquipmentGroupDocument,
    ThermostatBinding,
    ThermostatRole,
    encode_phase2_equipment_group_document,
)
from custom_components.intelligent_climate.services import (
    async_register_services,
    async_set_operating_mode,
)

THERMOSTAT = "climate.main"


def _config() -> Phase2EquipmentGroupDocument:
    return Phase2EquipmentGroupDocument(
        equipment_group=EquipmentGroupConfig(
            equipment_group_id=EquipmentGroupId.parse(
                "b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3"
            ),
            name="Main",
            equipment_type=EquipmentType.AIR_SOURCE_HEAT_PUMP,
            relationship=EquipmentRelationship.SINGLE_SYSTEM,
            thermostats=(ThermostatBinding(THERMOSTAT, ThermostatRole.PRIMARY),),
            shared_policy=None,
        ),
        automation_enabled=False,
        desired_operating_mode=OperatingMode.OBSERVE_ONLY,
        command_authority_entity_ids=(THERMOSTAT,),
        authority_review_required=False,
        acknowledged_time_zone="America/New_York",
    )


def _call(
    hass: HomeAssistant,
    mode: OperatingMode,
    *,
    user_id: str = "admin",
) -> ServiceCall:
    return ServiceCall(
        hass,
        DOMAIN,
        ACTION_SET_OPERATING_MODE,
        {"entry_id": "entry-1", "mode": mode.value},
        context=Context(user_id=user_id),
    )


def _entry(
    hass: HomeAssistant,
    *,
    schedule_available: bool = True,
) -> tuple[MockConfigEntry, SimpleNamespace]:
    config = _config()
    activity = SimpleNamespace(record=Mock())
    runtime = SimpleNamespace(
        migration=SimpleNamespace(
            config=config,
            runtime=SimpleNamespace(control_intent=SimpleNamespace()),
        ),
        schedule_store=SimpleNamespace(
            document=(
                SimpleNamespace(zones={"zone": SimpleNamespace(enabled=True)})
                if schedule_available
                else None
            )
        ),
        set_operating_mode=Mock(),
    )
    coordinator = SimpleNamespace(
        phase2_runtime=runtime,
        activity=activity,
        data=SimpleNamespace(calculated_at=None),
        runtime_store=None,
        async_request_refresh=AsyncMock(),
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry-1",
        data=dict(encode_phase2_equipment_group_document(config)),
        version=2,
        minor_version=0,
    )
    entry.add_to_hass(hass)
    entry.runtime_data = coordinator
    return entry, activity


async def test_admin_starts_shadow_without_reloading_the_sidebar_entry(
    hass: HomeAssistant,
) -> None:
    """Starting Shadow changes intent only; no service-call adapter exists."""
    entry, activity = _entry(hass)
    with (
        patch.object(
            hass.auth,
            "async_get_user",
            AsyncMock(return_value=SimpleNamespace(is_admin=True)),
        ),
    ):
        await async_set_operating_mode(
            hass,
            _call(hass, OperatingMode.SCHEDULED_SHADOW),
        )

    assert entry.data["automation_enabled"] is True
    assert entry.data["desired_operating_mode"] == "scheduled_shadow"
    coordinator = entry.runtime_data
    coordinator.phase2_runtime.set_operating_mode.assert_called_once()
    coordinator.async_request_refresh.assert_awaited_once()
    activity.record.assert_called_once()
    assert activity.record.call_args.kwargs["detail"] == {
        "previous_state": "observe_only",
        "new_state": "scheduled_shadow",
    }


async def test_zero_command_action_registration_is_exact_and_idempotent(
    hass: HomeAssistant,
) -> None:
    """The integration owns one action surface and no physical action names."""
    async_register_services(hass)
    async_register_services(hass)

    assert set(hass.services.async_services()[DOMAIN]) == {ACTION_SET_OPERATING_MODE}


async def test_shadow_requires_saved_enabled_schedule(hass: HomeAssistant) -> None:
    _entry(hass, schedule_available=False)
    with (
        patch.object(
            hass.auth,
            "async_get_user",
            AsyncMock(return_value=SimpleNamespace(is_admin=True)),
        ),
        pytest.raises(ServiceValidationError, match="valid schedule"),
    ):
        await async_set_operating_mode(
            hass,
            _call(hass, OperatingMode.SCHEDULED_SHADOW),
        )


async def test_mode_change_requires_administrator_and_rejects_active_control(
    hass: HomeAssistant,
) -> None:
    _entry(hass)
    with (
        patch.object(
            hass.auth,
            "async_get_user",
            AsyncMock(return_value=SimpleNamespace(is_admin=False)),
        ),
        pytest.raises(ServiceValidationError, match="Administrator"),
    ):
        await async_set_operating_mode(
            hass,
            _call(hass, OperatingMode.MANUAL_CONTROL, user_id="ordinary"),
        )

    with (
        patch.object(
            hass.auth,
            "async_get_user",
            AsyncMock(return_value=SimpleNamespace(is_admin=True)),
        ),
        pytest.raises(ServiceValidationError, match="cannot arm"),
    ):
        await async_set_operating_mode(
            hass,
            _call(hass, OperatingMode.SCHEDULED_CONTROL),
        )
