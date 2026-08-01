"""Freeze the accepted 0.0.8 baseline before Phase 2 behavior is added."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any, cast

from homeassistant.const import Platform

from custom_components.intelligent_climate.const import (
    INTEGRATION_VERSION,
    PLATFORMS,
)
from custom_components.intelligent_climate.models import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
    RUNTIME_STORE_SCHEMA_VERSION,
    ZONE_DATA_VERSION,
    OperatingMode,
    decode_equipment_group_document,
    decode_options,
    decode_runtime_store_document,
    decode_zone_config,
    encode_equipment_group_document,
    encode_options,
    encode_runtime_store_document,
    encode_zone_config,
)
from custom_components.intelligent_climate.storage import (
    STORE_MINOR_VERSION,
    STORE_VERSION,
)

ROOT = Path(__file__).parents[2]
INTEGRATION_DIR = ROOT / "custom_components" / "intelligent_climate"
FIXTURE_PATH = ROOT / "tests" / "fixtures" / "phase_1_0_0_8_baseline.json"
ACCEPTANCE_PATH = ROOT / "docs" / "phase-1-acceptance.md"
PHASE_2_DESIGN_PATH = ROOT / "docs" / "phase-2-requirements-and-technical-design.md"


def _fixture() -> dict[str, Any]:
    """Load the immutable accepted-baseline fixture."""
    return cast(
        dict[str, Any],
        json.loads(FIXTURE_PATH.read_text(encoding="utf-8")),
    )


def _attribute_path(node: ast.AST) -> tuple[str, ...]:
    """Return a dotted attribute path for a simple expression."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return tuple(reversed(parts))


def _service_call_paths(path: Path) -> list[str]:
    """Return direct Home Assistant service-call expressions in one module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        ".".join(_attribute_path(node.func))
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _attribute_path(node.func)[-2:] == ("services", "async_call")
    ]


def test_accepted_release_evidence_is_frozen() -> None:
    """The fixture records the exact accepted Phase 1 release evidence."""
    release = _fixture()["release"]
    acceptance = ACCEPTANCE_PATH.read_text(encoding="utf-8")

    assert release == {
        "version": "0.0.8",
        "accepted_commit": "803ad044da81494c7034e5e9ae52b898cd347b07",
        "accepted_at": "2026-07-29",
        "acceptance_criteria_passed": 35,
        "automated_tests_passed": 817,
        "statement_coverage_pct": 97.88,
        "branch_coverage_pct": 95.21,
    }
    assert "**Release:** 0.0.8" in acceptance
    assert "**Result:** All 35 Phase 1 acceptance criteria passed" in acceptance
    assert acceptance.count("| P1-AC-") == 35
    assert release["version"] == "0.0.8"
    assert INTEGRATION_VERSION == "0.0.11"


def test_accepted_config_zone_options_and_store_round_trip() -> None:
    """Every persisted 0.0.8 document remains a valid migration input."""
    baseline = _fixture()
    config = baseline["config_entry"]
    zone = baseline["zone_subentry"]
    options = baseline["options"]
    store = baseline["runtime_store"]

    assert (
        dict(
            encode_equipment_group_document(
                decode_equipment_group_document(
                    config["data"],
                    version=config["version"],
                    minor_version=config["minor_version"],
                )
            )
        )
        == config["data"]
    )
    assert dict(encode_zone_config(decode_zone_config(zone))) == zone
    assert dict(encode_options(decode_options(options))) == options
    assert (
        dict(
            encode_runtime_store_document(decode_runtime_store_document(store["data"]))
        )
        == store["data"]
    )


def test_accepted_schema_and_platform_versions_are_frozen() -> None:
    """Task 1 cannot silently advance a persisted or platform contract."""
    baseline = _fixture()

    assert (CONFIG_ENTRY_MAJOR_VERSION, CONFIG_ENTRY_MINOR_VERSION) == (1, 1)
    assert ZONE_DATA_VERSION == 1
    assert RUNTIME_STORE_SCHEMA_VERSION == 1
    assert (STORE_VERSION, STORE_MINOR_VERSION) == (1, 2)
    assert (
        baseline["runtime_store"]["envelope_version"],
        baseline["runtime_store"]["envelope_minor_version"],
    ) == (STORE_VERSION, STORE_MINOR_VERSION)
    assert [platform.value for platform in PLATFORMS] == baseline["runtime_contract"][
        "forwarded_platforms"
    ]
    assert set(PLATFORMS) == {
        Platform.BINARY_SENSOR,
        Platform.CLIMATE,
        Platform.EVENT,
        Platform.SENSOR,
        Platform.SWITCH,
    }


def test_phase_1_modes_remain_the_frozen_prefix_of_phase_2_vocabulary() -> None:
    """Task 2 may extend vocabulary without changing accepted Phase 1 values."""
    baseline = _fixture()

    phase_1_modes = baseline["runtime_contract"]["operating_modes"]

    assert [mode.value for mode in OperatingMode][: len(phase_1_modes)] == phase_1_modes
    schedule_package = INTEGRATION_DIR / "schedule"
    assert {path.name for path in schedule_package.glob("*.py")} == {
        "__init__.py",
        "evaluate.py",
        "time.py",
        "transitions.py",
    }
    override_package = INTEGRATION_DIR / "override"
    assert {path.name for path in override_package.glob("*.py")} == {
        "__init__.py",
        "expiration.py",
        "state_machine.py",
    }
    command_package = INTEGRATION_DIR / "command"
    assert {path.name for path in command_package.glob("*.py")} == {
        "__init__.py",
        "correlation.py",
        "dependencies.py",
    }
    shadow_package = INTEGRATION_DIR / "shadow"
    assert {path.name for path in shadow_package.glob("*.py")} == {
        "__init__.py",
        "history.py",
        "qualification.py",
        "sink.py",
    }
    assert not (INTEGRATION_DIR / "environment").exists()
    frontend_package = ROOT / "frontend"
    assert frontend_package.is_dir()
    assert {path.name for path in frontend_package.iterdir()} >= {
        "package.json",
        "package-lock.json",
        "src",
        "test",
        "tsconfig.json",
        "vitest.config.ts",
    }
    assert not (INTEGRATION_DIR / "actions.py").exists()
    assert (INTEGRATION_DIR / "frontend.py").is_file()
    assert {
        "manual_control.py",
        "narrative.py",
        "presentation_trace.py",
        "runtime.py",
        "timeline.py",
        "websocket.py",
    } <= {path.name for path in INTEGRATION_DIR.glob("*.py")}


def test_task_01_forbids_any_physical_adapter_or_service_call() -> None:
    """No physical command path may appear before its approved backlog task."""
    assert not (INTEGRATION_DIR / "control" / "command_adapter.py").exists()
    offenders = {
        str(path.relative_to(ROOT)): _service_call_paths(path)
        for path in INTEGRATION_DIR.rglob("*.py")
        if _service_call_paths(path)
    }

    assert offenders == {}


def test_phase_2_design_is_present_and_preserves_task_gates() -> None:
    """The approved design is the in-repository contract for later slices."""
    design = PHASE_2_DESIGN_PATH.read_text(encoding="utf-8")
    governance = ROOT / "docs" / "governance"

    assert "## Phase 2 Requirements Review and Technical Design" in design
    assert "**Design status:** Approved implementation baseline" in design
    assert (governance / "master-specifications.txt").is_file()
    assert (governance / "nonnegotiable-requirements.txt").is_file()
    assert (governance / "architecture-decisions.txt").is_file()
    assert "| 1 | Freeze 0.0.8 baseline fixtures" in design
    assert "| 2 | Add Phase 2 typed IDs/enums/control reason" in design
    assert "| 28 | Add active adapter in isolation" in design
    assert "The Phase 7 Simulation Lab is not a Phase 2 operating stage." in design
    assert "Use psychrometric comfort" in design
