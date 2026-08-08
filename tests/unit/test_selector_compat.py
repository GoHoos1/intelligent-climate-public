"""Tests for Home Assistant selector type compatibility."""

from __future__ import annotations

import ast
from pathlib import Path

from custom_components.intelligent_climate.selector_compat import (
    entity_filter_selector_config,
)

ROOT = Path(__file__).resolve().parents[2]


def test_entity_filter_helper_preserves_supported_selector_shape() -> None:
    """Test the compatibility helper emits ordinary selector dictionaries."""
    assert entity_filter_selector_config(domain="climate") == {"domain": "climate"}
    assert entity_filter_selector_config(
        domain=("sensor", "binary_sensor"),
        device_class=("temperature", "humidity"),
    ) == {
        "domain": ["sensor", "binary_sensor"],
        "device_class": ["temperature", "humidity"],
    }


def test_new_selector_type_is_never_imported_at_runtime() -> None:
    """Test the post-2026.7 type remains confined to TYPE_CHECKING."""
    source = (
        ROOT / "custom_components/intelligent_climate/selector_compat.py"
    ).read_text()
    module = ast.parse(source)
    runtime_imports = [
        alias.name
        for node in module.body
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]
    assert "EntityWithDeviceFilterSelectorConfig" not in runtime_imports
