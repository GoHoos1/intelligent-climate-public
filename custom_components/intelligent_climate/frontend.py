"""Supported static-asset and sidebar-panel lifecycle for Package G."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Final, TypedDict

from homeassistant.components import frontend, panel_custom
from homeassistant.components.http import StaticPathConfig
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .websocket import API_VERSION

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

FRONTEND_VERSION: Final = "0.0.11"
PANEL_URL_PATH: Final = "intelligent-climate"
PANEL_COMPONENT_NAME: Final = "intelligent-climate-panel"
PANEL_STATIC_URL: Final = "/intelligent_climate_frontend/intelligent-climate-panel.js"
PANEL_ASSET_PATH: Final = (
    Path(__file__).parent / "frontend_dist" / "intelligent-climate-panel.js"
)

_STATIC_REGISTERED: Final = "frontend_static_registered"
_LOADED_ENTRIES: Final = "frontend_loaded_entries"
_PANEL_SIGNATURE: Final = "frontend_panel_signature"


class PanelEntry(TypedDict):
    """Minimal user-visible entry choice passed to the local panel."""

    entry_id: str
    title: str


async def async_setup_frontend(hass: HomeAssistant) -> None:
    """Register the immutable bundled module path exactly once."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get(_STATIC_REGISTERED):
        return
    if not PANEL_ASSET_PATH.is_file():
        raise HomeAssistantError("Intelligent Climate frontend asset is missing")
    await hass.http.async_register_static_paths(
        [StaticPathConfig(PANEL_STATIC_URL, str(PANEL_ASSET_PATH), True)]
    )
    data[_STATIC_REGISTERED] = True


async def async_register_frontend_entry(
    hass: HomeAssistant,
    *,
    entry_id: str,
    title: str,
) -> None:
    """Expose one loaded entry and refresh the single shared panel."""
    data = hass.data.setdefault(DOMAIN, {})
    entries = _loaded_entries(data)
    entries[entry_id] = title
    await _async_refresh_panel(hass, data, entries)


async def async_unregister_frontend_entry(
    hass: HomeAssistant,
    *,
    entry_id: str,
) -> None:
    """Remove one unloaded entry and clean up the panel after the last."""
    data = hass.data.setdefault(DOMAIN, {})
    entries = _loaded_entries(data)
    entries.pop(entry_id, None)
    await _async_refresh_panel(hass, data, entries)


def _loaded_entries(data: dict[str, object]) -> dict[str, str]:
    value = data.setdefault(_LOADED_ENTRIES, {})
    if not isinstance(value, dict):
        raise HomeAssistantError("Invalid Intelligent Climate frontend runtime state")
    if not all(
        isinstance(key, str) and isinstance(title, str) for key, title in value.items()
    ):
        raise HomeAssistantError("Invalid Intelligent Climate frontend entry state")
    return value


async def _async_refresh_panel(
    hass: HomeAssistant,
    data: dict[str, object],
    entries: dict[str, str],
) -> None:
    signature = tuple(sorted(entries.items()))
    if data.get(_PANEL_SIGNATURE) == signature:
        return
    frontend.async_remove_panel(hass, PANEL_URL_PATH, warn_if_unknown=False)
    data.pop(_PANEL_SIGNATURE, None)
    if not signature:
        return
    panel_entries: list[PanelEntry] = [
        {"entry_id": entry_id, "title": title} for entry_id, title in signature
    ]
    await panel_custom.async_register_panel(
        hass,
        frontend_url_path=PANEL_URL_PATH,
        webcomponent_name=PANEL_COMPONENT_NAME,
        sidebar_title="Intelligent Climate",
        sidebar_icon="mdi:home-thermometer-outline",
        module_url=f"{PANEL_STATIC_URL}?v={FRONTEND_VERSION}",
        config={
            "api_version": API_VERSION,
            "frontend_version": FRONTEND_VERSION,
            "entries": panel_entries,
        },
        require_admin=False,
        config_panel_domain=DOMAIN,
    )
    data[_PANEL_SIGNATURE] = signature
