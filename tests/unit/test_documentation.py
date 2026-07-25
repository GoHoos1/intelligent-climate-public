"""Test user-facing release documentation structure."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
README = (ROOT / "README.md").read_text(encoding="utf-8")
CHANGELOG = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")


def _heading_position(document: str, heading: str) -> int:
    position = document.find(f"## {heading}")
    assert position >= 0, f"missing heading: {heading}"
    return position


def test_readme_recent_changes_is_near_top_and_links_full_changelog() -> None:
    """Recent releases are concise and visible before installation."""
    recent = _heading_position(README, "Recent changes")

    assert recent < _heading_position(README, "Installation with HACS")
    assert recent < len(README) // 4
    recent_body = README[
        recent : _heading_position(README, "What Intelligent Climate does today")
    ]
    assert "**0.0.3**" in recent_body
    assert "**0.0.2**" in recent_body
    assert "**0.0.1**" in recent_body
    assert "[View the full changelog](CHANGELOG.md)" in recent_body


def test_readme_prioritizes_user_guidance_before_architecture() -> None:
    """Installation, use, privacy, and troubleshooting precede internals."""
    architecture = _heading_position(README, "Technical architecture")
    ordered_user_sections = (
        "What Intelligent Climate does today",
        "What it deliberately does not do",
        "Installation with HACS",
        "Initial setup",
        "Adding and reconfiguring zones",
        "Understanding the read-only zone climate entity",
        "Source health and availability",
        "Downloading diagnostics",
        "Troubleshooting",
        "Privacy and local-first behavior",
    )

    positions = tuple(
        _heading_position(README, heading) for heading in ordered_user_sections
    )
    assert positions == tuple(sorted(positions))
    assert all(position < architecture for position in positions)
    assert "observation-only" in README[:architecture].casefold()
    assert "original thermostat" in README[:architecture].casefold()


def test_readme_has_complete_requested_section_order() -> None:
    """The full README follows the approved user-first outline."""
    headings = re.findall(r"^## (.+)$", README, flags=re.MULTILINE)

    assert headings == [
        "Current release and maturity",
        "Recent changes",
        "What Intelligent Climate does today",
        "What it deliberately does not do",
        "Installation with HACS",
        "Initial setup",
        "Adding and reconfiguring zones",
        "Understanding the read-only zone climate entity",
        "Source health and availability",
        "Downloading diagnostics",
        "Troubleshooting",
        "Privacy and local-first behavior",
        "Current roadmap and Phase 1 status",
        "Documentation",
        "Technical architecture",
        "Development and validation",
        "License",
    ]


def test_changelog_contains_versioned_release_sections() -> None:
    """Release history is versioned without inventing release tags."""
    headings = re.findall(r"^## (.+)$", CHANGELOG, flags=re.MULTILINE)

    assert headings == [
        "Unreleased",
        "0.0.3 - 2026-07-24",
        "0.0.2 - 2026-07-24",
        "0.0.1 - 2026-07-24",
        "0.0.0 - 2026-07-23",
    ]
    assert "public release tag exists" in CHANGELOG
    assert "Repairs" in CHANGELOG
    assert "physical" in CHANGELOG
