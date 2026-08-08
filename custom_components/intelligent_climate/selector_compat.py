"""Compatibility helpers for supported Home Assistant selector APIs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from homeassistant.helpers.selector import EntityFilterSelectorConfig

if TYPE_CHECKING:
    from homeassistant.helpers.selector import EntityWithDeviceFilterSelectorConfig


def entity_filter_selector_config(
    *,
    domain: str | Iterable[str],
    device_class: str | Iterable[str] | None = None,
) -> EntityWithDeviceFilterSelectorConfig:
    """Build an entity filter supported by HA 2026.7 and typed by current HA."""
    normalized_domain = domain if isinstance(domain, str) else list(domain)
    config = EntityFilterSelectorConfig(domain=normalized_domain)
    if device_class is not None:
        config["device_class"] = (
            device_class if isinstance(device_class, str) else list(device_class)
        )
    return cast("EntityWithDeviceFilterSelectorConfig", config)
