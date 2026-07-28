"""Test manifest and HACS repository invariants."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from custom_components.intelligent_climate.const import DOMAIN, INTEGRATION_VERSION
from custom_components.intelligent_climate.models import ActivityType

ROOT = Path(__file__).parents[2]
CUSTOM_COMPONENTS_DIR = ROOT / "custom_components"
INTEGRATION_DIR = ROOT / "custom_components" / DOMAIN
HACS_REQUIRED_MANIFEST_FIELDS = {
    "codeowners",
    "documentation",
    "domain",
    "issue_tracker",
    "name",
    "version",
}


def test_exactly_one_custom_integration_exists() -> None:
    """Test the repository contains one HACS-manageable integration."""
    integrations = [
        path.name
        for path in CUSTOM_COMPONENTS_DIR.iterdir()
        if path.is_dir() and not path.name.startswith("__")
    ]

    assert integrations == [DOMAIN]


def test_integration_directory_matches_manifest_domain() -> None:
    """Test the HACS integration directory matches manifest domain."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())

    assert isinstance(manifest, dict)
    assert INTEGRATION_DIR.name == manifest["domain"]


def test_manifest_matches_foundation_scope() -> None:
    """Test manifest metadata does not claim unimplemented features."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())

    assert isinstance(manifest, dict)
    assert manifest["domain"] == DOMAIN
    assert manifest["name"] == "Intelligent Climate"
    assert manifest["version"] == INTEGRATION_VERSION
    assert manifest["codeowners"] == ["@GoHoos1"]
    assert manifest["config_flow"] is True
    assert manifest["dependencies"] == []
    assert manifest["documentation"] == (
        "https://github.com/GoHoos1/intelligent-climate-public"
    )
    assert manifest["integration_type"] == "hub"
    assert manifest["iot_class"] == "calculated"
    assert (
        manifest["issue_tracker"]
        == "https://github.com/GoHoos1/intelligent-climate-public/issues"
    )
    assert manifest["requirements"] == []


def test_manifest_and_package_versions_match_diagnostics_release() -> None:
    """Test both release metadata files identify version 0.0.5."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())
    package = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert manifest["version"] == INTEGRATION_VERSION == "0.0.5"
    assert package["project"]["version"] == INTEGRATION_VERSION


def test_manifest_contains_hacs_required_fields() -> None:
    """Test HACS-required integration manifest fields are present."""
    manifest = json.loads((INTEGRATION_DIR / "manifest.json").read_text())

    assert isinstance(manifest, dict)
    assert manifest.keys() >= HACS_REQUIRED_MANIFEST_FIELDS


def test_task_14_entity_and_event_translations_are_complete() -> None:
    """English translations cover both entities and every activity event type."""
    translations = json.loads(
        (INTEGRATION_DIR / "translations" / "en.json").read_text()
    )

    assert translations["entity"]["sensor"]["latest_activity"]["name"] == (
        "Latest activity"
    )
    event_translation = translations["entity"]["event"]["activity"]
    assert event_translation["name"] == "Activity"
    assert set(event_translation["state"]) == {
        activity_type.value for activity_type in ActivityType
    }


def test_hacs_manifest_declares_integration_name() -> None:
    """Test HACS metadata declares only the integration package."""
    hacs_manifest = json.loads((ROOT / "hacs.json").read_text())

    assert isinstance(hacs_manifest, dict)
    assert set(hacs_manifest) == {"name"}
    assert hacs_manifest["name"] == "Intelligent Climate"
    assert "render_readme" not in hacs_manifest
