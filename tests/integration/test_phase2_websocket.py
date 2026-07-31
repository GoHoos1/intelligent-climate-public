"""Task 20 versioned WebSocket registration and read-boundary tests."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.typing import WebSocketGenerator

from custom_components.intelligent_climate.const import DOMAIN
from custom_components.intelligent_climate.models import ControlState
from custom_components.intelligent_climate.websocket import (
    API_VERSION,
    async_register_websocket_api,
)


async def test_websocket_api_registers_once_and_rejects_unloaded_entry(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    async_register_websocket_api(hass)
    async_register_websocket_api(hass)
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "intelligent_climate/snapshot/get",
            "api_version": API_VERSION,
            "entry_id": "missing",
        }
    )
    response = await client.receive_json()

    assert not response["success"]
    assert response["error"]["code"] == "entry_not_loaded"
    assert hass.data[DOMAIN]["websocket_api_registered"] is True


async def test_snapshot_read_returns_versioned_observation_without_control(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    async_register_websocket_api(hass)
    now = datetime(2026, 7, 31, 18, tzinfo=UTC)
    observation = SimpleNamespace(
        entry_id="entry-1",
        revision=9,
        calculated_at=now,
        control_state=ControlState.OBSERVING,
        zones=(),
    )
    coordinator = SimpleNamespace(data=observation, phase2_runtime=None)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry-1",
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    entry.runtime_data = coordinator
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "intelligent_climate/snapshot/get",
            "api_version": API_VERSION,
            "entry_id": "entry-1",
        }
    )
    response = await client.receive_json()

    assert response["success"]
    assert response["result"] == {
        "api_version": API_VERSION,
        "entry_id": "entry-1",
        "observation_revision": 9,
        "calculated_at_utc": now.isoformat(),
        "control_state": "observing",
        "reason_code": None,
        "zones": [],
    }


async def test_websocket_api_rejects_unknown_frontend_version(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    async_register_websocket_api(hass)
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {
            "type": "intelligent_climate/observation/status",
            "api_version": 2,
            "entry_id": "missing",
        }
    )
    response = await client.receive_json()
    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"
