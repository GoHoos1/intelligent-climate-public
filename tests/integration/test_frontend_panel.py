"""Task 22 supported sidebar lifecycle and bundled-asset tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.components import frontend
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.intelligent_climate import frontend as frontend_module
from custom_components.intelligent_climate.const import DOMAIN
from custom_components.intelligent_climate.frontend import (
    FRONTEND_VERSION,
    PANEL_ASSET_PATH,
    PANEL_STATIC_URL,
    PANEL_URL_PATH,
    async_register_frontend_entry,
    async_setup_frontend,
    async_unregister_frontend_entry,
)
from custom_components.intelligent_climate.websocket import API_VERSION


async def test_frontend_static_asset_registers_once(hass: HomeAssistant) -> None:
    """The immutable built asset uses the supported HTTP static-path API."""
    register = AsyncMock()
    object.__setattr__(
        hass,
        "http",
        SimpleNamespace(async_register_static_paths=register),
    )

    await async_setup_frontend(hass)
    await async_setup_frontend(hass)

    assert PANEL_ASSET_PATH.is_file()
    assert PANEL_ASSET_PATH.stat().st_size > 1_000
    register.assert_awaited_once()
    await_args = register.await_args
    assert await_args is not None
    path = await_args.args[0][0]
    assert path.url_path == PANEL_STATIC_URL
    assert path.path == str(PANEL_ASSET_PATH)
    assert path.cache_headers is True


async def test_frontend_static_asset_must_exist(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A broken package fails setup instead of registering a dead panel URL."""
    monkeypatch.setattr(frontend_module, "PANEL_ASSET_PATH", tmp_path / "missing.js")

    with pytest.raises(HomeAssistantError, match="frontend asset is missing"):
        await async_setup_frontend(hass)


async def test_panel_tracks_loaded_entries_and_cleans_up(hass: HomeAssistant) -> None:
    """One shared panel updates for loaded entries and disappears after final unload."""
    await async_register_frontend_entry(hass, entry_id="entry-b", title="Upstairs")
    await async_register_frontend_entry(hass, entry_id="entry-a", title="Main floor")

    panel = hass.data[frontend.DATA_PANELS][PANEL_URL_PATH]
    assert panel.sidebar_title == "Intelligent Climate"
    assert panel.sidebar_icon == "mdi:home-thermometer-outline"
    assert panel.require_admin is False
    assert panel.config == {
        "api_version": API_VERSION,
        "frontend_version": FRONTEND_VERSION,
        "entries": [
            {"entry_id": "entry-a", "title": "Main floor"},
            {"entry_id": "entry-b", "title": "Upstairs"},
        ],
        "_panel_custom": {
            "name": "intelligent-climate-panel",
            "embed_iframe": False,
            "trust_external": False,
            "module_url": f"{PANEL_STATIC_URL}?v={FRONTEND_VERSION}",
        },
    }

    await async_unregister_frontend_entry(hass, entry_id="entry-a")
    remaining = hass.data[frontend.DATA_PANELS][PANEL_URL_PATH]
    assert remaining.config is not None
    assert remaining.config["entries"] == [{"entry_id": "entry-b", "title": "Upstairs"}]

    await async_unregister_frontend_entry(hass, entry_id="entry-b")
    assert PANEL_URL_PATH not in hass.data[frontend.DATA_PANELS]


async def test_panel_registration_is_semantic_noop_for_same_entry(
    hass: HomeAssistant,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Equivalent setup callbacks do not churn the Home Assistant panel registry."""
    remove = Mock()
    monkeypatch.setattr(frontend, "async_remove_panel", remove)
    entry = SimpleNamespace(entry_id="entry-a", title="Main floor")

    await async_register_frontend_entry(
        hass,
        entry_id=entry.entry_id,
        title=entry.title,
    )
    await async_register_frontend_entry(
        hass,
        entry_id=entry.entry_id,
        title=entry.title,
    )

    remove.assert_called_once()


async def test_frontend_runtime_state_rejects_corruption(hass: HomeAssistant) -> None:
    """Hand-constructed invalid entry state fails closed."""
    hass.data.setdefault(DOMAIN, {})["frontend_loaded_entries"] = {1: "invalid"}

    with pytest.raises(
        HomeAssistantError,
        match="Invalid Intelligent Climate frontend entry state",
    ):
        await async_register_frontend_entry(hass, entry_id="entry-a", title="Main")


async def test_frontend_runtime_state_rejects_non_mapping(
    hass: HomeAssistant,
) -> None:
    """A corrupted entry collection fails before panel mutation."""
    hass.data.setdefault(DOMAIN, {})["frontend_loaded_entries"] = "invalid"

    with pytest.raises(
        HomeAssistantError,
        match="Invalid Intelligent Climate frontend runtime state",
    ):
        await async_register_frontend_entry(hass, entry_id="entry-a", title="Main")
