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
        thermostats=(),
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


async def test_snapshot_reports_only_aggregate_zone_mode_capabilities(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Mode guidance exposes safe facts without thermostat identity."""
    async_register_websocket_api(hass)
    now = datetime(2026, 7, 31, 18, tzinfo=UTC)
    mode = SimpleNamespace(value="heat_cool")
    state = SimpleNamespace(
        entity_id="climate.private_name",
        available=True,
        hvac_mode=mode,
    )
    capabilities = SimpleNamespace(
        hvac_modes=(
            SimpleNamespace(value="off"),
            SimpleNamespace(value="heat"),
            SimpleNamespace(value="cool"),
            mode,
        ),
        target_temperature=True,
        target_temperature_range=True,
    )
    thermostat = SimpleNamespace(
        entity_id=state.entity_id,
        state=state,
        capability_discovery=SimpleNamespace(capabilities=capabilities),
    )
    zone = SimpleNamespace(
        zone_id="99246285-6f02-4e8a-94ed-bdfd4a5e62c4",
        effective_temperature_c=23.7,
        effective_humidity_pct=50.0,
        thermostat_states=(state,),
        sensor_data_degraded=False,
        thermostat_data_degraded=False,
    )
    observation = SimpleNamespace(
        entry_id="entry-mode",
        revision=10,
        calculated_at=now,
        control_state=ControlState.OBSERVING,
        thermostats=(thermostat,),
        zones=(zone,),
    )
    coordinator = SimpleNamespace(data=observation, phase2_runtime=None)
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry-mode",
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    entry.runtime_data = coordinator
    client = await hass_ws_client(hass)

    await client.send_json_auto_id(
        {
            "type": "intelligent_climate/snapshot/get",
            "api_version": API_VERSION,
            "entry_id": entry.entry_id,
        }
    )
    response = await client.receive_json()

    assert response["success"]
    result = response["result"]["zones"][0]
    assert result["thermostat_hvac_mode"] == "heat_cool"
    assert result["supported_hvac_modes"] == ["cool", "heat", "heat_cool", "off"]
    assert result["supports_single_target"] is True
    assert result["supports_target_range"] is True
    assert "climate.private_name" not in str(response["result"])


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


async def test_activity_defaults_newest_first_and_can_request_oldest(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Presentation order changes without mutating chronological storage."""
    async_register_websocket_api(hass)
    earlier = datetime(2026, 7, 31, 17, tzinfo=UTC)
    later = datetime(2026, 7, 31, 18, tzinfo=UTC)

    def record(record_id: str, timestamp: datetime) -> SimpleNamespace:
        return SimpleNamespace(
            record_id=record_id,
            zone_id=None,
            timestamp=timestamp,
            activity_type=SimpleNamespace(value="observation"),
            reason_code=SimpleNamespace(value="observation_updated"),
            severity=SimpleNamespace(value="info"),
            explanation=record_id,
            detail={
                "previous_state": "reconciling",
                "new_state": "observing",
                "source_id": "private-internal-source-id",
            },
        )

    stored = (record("earlier", earlier), record("later", later))
    coordinator = SimpleNamespace(history=SimpleNamespace(records=stored))
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="entry-activity",
        state=ConfigEntryState.LOADED,
    )
    entry.add_to_hass(hass)
    entry.runtime_data = coordinator
    client = await hass_ws_client(hass)

    for order, expected in (
        (None, ["later", "earlier"]),
        ("oldest", ["earlier", "later"]),
    ):
        message: dict[str, object] = {
            "type": "intelligent_climate/activity/list",
            "api_version": API_VERSION,
            "entry_id": entry.entry_id,
        }
        if order is not None:
            message["order"] = order
        await client.send_json_auto_id(message)
        response = await client.receive_json()
        assert response["success"]
        assert [item["record_id"] for item in response["result"]["records"]] == expected
        assert response["result"]["records"][0]["detail"] == {
            "previous_state": "reconciling",
            "new_state": "observing",
        }

    assert coordinator.history.records == stored
