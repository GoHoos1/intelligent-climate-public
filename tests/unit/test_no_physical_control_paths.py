"""Protect the Phase 1 observation-only invariant."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).parents[2]
INTEGRATION_DIR = ROOT / "custom_components" / "intelligent_climate"


def _attribute_path(node: ast.AST) -> tuple[str, ...]:
    """Return a dotted attribute path for simple attribute expressions."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return tuple(reversed(parts))


def _find_prohibited_service_call_paths(source: str) -> list[str]:
    """Find direct Home Assistant service-call paths in Python source.

    This repository invariant check is a guardrail. It is not proof of all
    possible control behavior, but it catches direct service-call expressions
    that are out of scope for the observation-only foundation.
    """
    tree = ast.parse(source)
    offenders: list[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_path = _attribute_path(node.func)
            if call_path[-2:] == ("services", "async_call"):
                offenders.append(".".join(call_path))
            elif call_path[-1:] == ("async_call",):
                offenders.append("async_call")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if "services" in module.split("."):
                offenders.extend(
                    f"from {module} import {alias.name}"
                    for alias in node.names
                    if alias.name == "async_call"
                )

    return offenders


def test_ast_guard_detects_hass_services_async_call() -> None:
    """Test the guard detects direct hass service-call expressions."""
    source = (
        "async def bad(hass):\n    await hass.services.async_call('climate', 'off')\n"
    )

    assert _find_prohibited_service_call_paths(source) == ["hass.services.async_call"]


def test_ast_guard_detects_other_object_services_async_call() -> None:
    """Test the guard detects service-call expressions through other objects."""
    source = "async def bad(runtime):\n    await runtime.hass.services.async_call()\n"

    assert _find_prohibited_service_call_paths(source) == [
        "runtime.hass.services.async_call"
    ]


def test_ast_guard_detects_imported_async_call_helper() -> None:
    """Test the guard detects imported service-call helper aliases."""
    source = (
        "from homeassistant.helpers.services import async_call as call_service\n"
        "async def bad():\n"
        "    await call_service()\n"
    )

    assert _find_prohibited_service_call_paths(source) == [
        "from homeassistant.helpers.services import async_call"
    ]


def test_integration_python_contains_no_home_assistant_service_call_path() -> None:
    """Test integration code contains no direct Home Assistant service-call path."""
    offenders = [
        f"{path.relative_to(ROOT)} contains {offender}"
        for path in INTEGRATION_DIR.rglob("*.py")
        for offender in _find_prohibited_service_call_paths(path.read_text())
    ]

    assert offenders == []


def test_zone_flow_has_no_control_or_platform_forwarding_path() -> None:
    """Test Task 5 zone UI work remains configuration-only."""
    source = (INTEGRATION_DIR / "zone_flow.py").read_text()

    assert "services.async_call" not in source
    assert "async_forward_entry_setups" not in source
    assert "async_register" not in source
    assert "ClimateEntity" not in source
    assert "Coordinator" not in source
    assert "Store(" not in source


def test_integration_forwards_only_phase_1_platforms() -> None:
    """Test setup forwards exactly the approved observation-only platforms."""
    setup_source = (INTEGRATION_DIR / "__init__.py").read_text()
    constants_source = (INTEGRATION_DIR / "const.py").read_text()

    assert setup_source.count("async_forward_entry_setups(entry, PLATFORMS)") == 1
    assert setup_source.count("async_unload_platforms(entry, PLATFORMS)") == 1
    for platform in (
        "Platform.BINARY_SENSOR",
        "Platform.CLIMATE",
        "Platform.EVENT",
        "Platform.SENSOR",
        "Platform.SWITCH",
    ):
        assert constants_source.count(platform) == 1


def test_tasks_5_and_6_add_no_runtime_or_registry_mutation_paths() -> None:
    """Test selection/discovery add no runtime observation infrastructure."""
    task_paths = (
        INTEGRATION_DIR / "config_flow.py",
        INTEGRATION_DIR / "zone_flow.py",
        INTEGRATION_DIR / "validation.py",
        INTEGRATION_DIR / "capability.py",
        INTEGRATION_DIR / "models" / "capability.py",
    )
    prohibited = {
        "async_forward_entry_setups",
        "async_track_state_change_event",
        "async_track_entity_registry_updated_event",
        "entity_registry.async_update_entity",
        "device_registry.async_get_or_create",
        "DataUpdateCoordinator",
        "CoordinatorEntity",
        "Store(",
        "async_register",
    }
    offenders = [
        f"{path.relative_to(ROOT)} contains {term}"
        for path in task_paths
        for term in prohibited
        if term in path.read_text()
    ]
    entity_base = re.compile(r"\b(?:ClimateEntity|SensorEntity|BinarySensorEntity)\b")
    offenders.extend(
        f"{path.relative_to(ROOT)} defines an entity platform"
        for path in task_paths
        if entity_base.search(path.read_text())
    )

    assert offenders == []


def test_task_6_capability_discovery_is_a_pure_read_only_boundary() -> None:
    """Test Task 6 adds no orchestration, mutation, persistence, or control path."""
    task_6_paths = (
        INTEGRATION_DIR / "capability.py",
        INTEGRATION_DIR / "models" / "capability.py",
    )
    prohibited = {
        "hass.services.async_call",
        "async_register",
        "async_forward_entry_setups",
        "async_track_state_change_event",
        "async_track_entity_registry_updated_event",
        "entity_registry.async_update_entity",
        "device_registry.async_get_or_create",
        "DataUpdateCoordinator",
        "CoordinatorEntity",
        "Store(",
        "ObservationIntent",
        "CommandSink",
    }
    offenders = [
        f"{path.relative_to(ROOT)} contains {term}"
        for path in task_6_paths
        for term in prohibited
        if term in path.read_text()
    ]

    assert offenders == []


def test_task_6_has_no_direct_capability_control_path() -> None:
    """Capability discovery and later entity surfaces remain observation-only."""
    setup_source = (INTEGRATION_DIR / "__init__.py").read_text()

    assert "discover_thermostat_capabilities" not in setup_source
    assert not any(
        _find_prohibited_service_call_paths((INTEGRATION_DIR / module).read_text())
        for module in ("binary_sensor.py", "switch.py")
    )


def test_task_7_observation_is_a_pure_unwired_boundary() -> None:
    """Test Task 7 adds no orchestration, mutation, persistence, or control path."""
    task_7_paths = (
        INTEGRATION_DIR / "observation.py",
        INTEGRATION_DIR / "models" / "observation.py",
    )
    prohibited = {
        "hass.services.async_call",
        "async_register",
        "async_forward_entry_setups",
        "async_track_state_change_event",
        "async_track_entity_registry_updated_event",
        "async_call_later",
        "async_track_time",
        "entity_registry.async_update_entity",
        "device_registry.async_get_or_create",
        "config_entries.async_update_entry",
        "DataUpdateCoordinator",
        "CoordinatorEntity",
        "Store(",
        "ObservationIntent",
        "CommandSink",
    }
    offenders = [
        f"{path.relative_to(ROOT)} contains {term}"
        for path in task_7_paths
        for term in prohibited
        if term in path.read_text()
    ]

    assert offenders == []


def test_task_7_has_no_setup_shortcut_or_control_entity_path() -> None:
    """Observation helpers and entity platforms have no control shortcut."""
    setup_source = (INTEGRATION_DIR / "__init__.py").read_text()

    assert "observe_temperature_source" not in setup_source
    assert "observe_humidity_source" not in setup_source
    assert not any(
        _find_prohibited_service_call_paths((INTEGRATION_DIR / module).read_text())
        for module in ("binary_sensor.py", "switch.py")
    )


def test_task_8_health_is_a_pure_unwired_boundary() -> None:
    """Test health adds no orchestration, mutation, persistence, or control path."""
    task_8_paths = (
        INTEGRATION_DIR / "health.py",
        INTEGRATION_DIR / "models" / "health.py",
    )
    prohibited = {
        "hass.services.async_call",
        "async_register",
        "async_forward_entry_setups",
        "async_track_state_change_event",
        "async_track_entity_registry_updated_event",
        "async_call_later",
        "async_track_time",
        "async_track_point_in_time",
        "entity_registry.async_update_entity",
        "device_registry.async_get_or_create",
        "config_entries.async_update_entry",
        "DataUpdateCoordinator",
        "CoordinatorEntity",
        "Store(",
        "async_save",
        "datetime.now",
        "datetime.utcnow",
        "ObservationIntent",
        "CommandSink",
    }
    offenders = [
        f"{path.relative_to(ROOT)} contains {term}"
        for path in task_8_paths
        for term in prohibited
        if term in path.read_text()
    ]

    assert offenders == []


def test_task_8_has_no_setup_shortcut_or_control_surface() -> None:
    """Health helpers and health entities remain observation-only."""
    setup_source = (INTEGRATION_DIR / "__init__.py").read_text()

    assert "evaluate_temperature_health" not in setup_source
    assert "evaluate_humidity_health" not in setup_source
    assert not any(
        _find_prohibited_service_call_paths((INTEGRATION_DIR / module).read_text())
        for module in ("binary_sensor.py", "switch.py")
    )


def test_task_9_aggregation_is_a_pure_unwired_boundary() -> None:
    """Test aggregation adds no runtime, mutation, persistence, or control path."""
    task_9_paths = (
        INTEGRATION_DIR / "aggregation.py",
        INTEGRATION_DIR / "models" / "aggregation.py",
    )
    prohibited = {
        "homeassistant",
        "hass.services.async_call",
        "async_register",
        "async_forward_entry_setups",
        "async_track_state_change_event",
        "async_track_entity_registry_updated_event",
        "async_call_later",
        "async_track_time",
        "async_track_point_in_time",
        "hass.states",
        "entity_registry",
        "device_registry",
        "config_entries.async_update_entry",
        "DataUpdateCoordinator",
        "CoordinatorEntity",
        "Store(",
        "async_save",
        "datetime.now",
        "datetime.utcnow",
        "ObservationIntent",
        "CommandSink",
    }
    offenders = [
        f"{path.relative_to(ROOT)} contains {term}"
        for path in task_9_paths
        for term in prohibited
        if term in path.read_text()
    ]

    assert offenders == []


def test_task_9_has_no_setup_shortcut_or_control_surface() -> None:
    """Aggregation helpers and later entity surfaces remain observation-only."""
    setup_source = (INTEGRATION_DIR / "__init__.py").read_text()

    assert "aggregate_temperature_sources" not in setup_source
    assert "aggregate_humidity_sources" not in setup_source
    assert not any(
        _find_prohibited_service_call_paths((INTEGRATION_DIR / module).read_text())
        for module in ("binary_sensor.py", "switch.py")
    )


def test_task_10_coordinator_has_only_approved_observation_surfaces() -> None:
    """Test runtime orchestration cannot reach commands, services, or persistence."""
    task_10_paths = (
        INTEGRATION_DIR / "coordinator.py",
        INTEGRATION_DIR / "climate_state.py",
        INTEGRATION_DIR / "type_aliases.py",
        INTEGRATION_DIR / "models" / "runtime.py",
    )
    prohibited = {
        "hass.services",
        "ObservationIntent",
        "SERVICE_SET_",
        "async_register",
        "async_forward_entry_setups",
        "CoordinatorEntity",
        "ClimateEntity",
        "SensorEntity",
        "BinarySensorEntity",
        "Store(",
        "async_save",
        "entity_registry",
        "device_registry",
        "issue_registry",
        "diagnostics",
        "datetime.now",
        "datetime.utcnow",
        "time.time",
    }
    offenders = [
        f"{path.relative_to(ROOT)} contains {term}"
        for path in task_10_paths
        for term in prohibited
        if term in path.read_text()
    ]

    assert offenders == []


def test_task_10_pipeline_remains_composed_after_task_14_wiring() -> None:
    """Test Task 14 preserves the coordinator's complete observation pipeline."""
    source = (INTEGRATION_DIR / "coordinator.py").read_text()
    required_calls = {
        "discover_thermostat_capabilities(",
        "normalize_climate_state(",
        "observe_temperature_source(",
        "observe_humidity_source(",
        "evaluate_temperature_health(",
        "evaluate_humidity_health(",
        "aggregate_temperature_sources(",
        "aggregate_humidity_sources(",
    }
    assert all(call in source for call in required_calls)


def test_task_10_setup_uses_runtime_data_without_domain_hass_data() -> None:
    """Test the active coordinator is typed on the config entry only."""
    setup_source = (INTEGRATION_DIR / "__init__.py").read_text()
    aliases_source = (INTEGRATION_DIR / "type_aliases.py").read_text()

    assert "entry.runtime_data = coordinator" in setup_source
    assert "hass.data" not in setup_source
    assert "ConfigEntry[IntelligentClimateCoordinator]" in aliases_source


def test_task_11_entity_surface_has_no_out_of_scope_runtime_paths() -> None:
    """Test Task 11 adds only presentation, registry, and translated rejection."""
    task_11_paths = (
        INTEGRATION_DIR / "entity.py",
        INTEGRATION_DIR / "climate.py",
    )
    prohibited = {
        "hass.services",
        "ObservationIntent",
        "CommandSink",
        "ObserveOnlyCommandSink",
        "decision_engine",
        "SERVICE_SET_",
        "async_register",
        "Store(",
        "async_save",
        "diagnostics",
        "async_fire",
        "datetime.now",
        "datetime.utcnow",
        "time.time",
        "async_add_executor_job",
    }
    offenders = [
        f"{path.relative_to(ROOT)} contains {term}"
        for path in task_11_paths
        for term in prohibited
        if term in path.read_text()
    ]

    assert offenders == []


def test_task_11_setters_only_raise_translated_validation_error() -> None:
    """Test every supported async climate mutation is an immediate raise."""
    source = (INTEGRATION_DIR / "climate.py").read_text()
    tree = ast.parse(source)
    climate_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef)
        and node.name == "IntelligentClimateZoneClimateEntity"
    )
    expected = {
        "async_set_hvac_mode",
        "async_set_temperature",
        "async_set_humidity",
        "async_set_fan_mode",
        "async_set_preset_mode",
        "async_set_swing_mode",
        "async_set_swing_horizontal_mode",
        "async_turn_on",
        "async_turn_off",
        "async_toggle",
    }
    setters = {
        node.name: node
        for node in climate_class.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name in expected
    }

    assert set(setters) == expected
    for setter in setters.values():
        executable = [
            statement
            for statement in setter.body
            if not (
                isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
            )
        ]
        assert len(executable) == 1
        assert isinstance(executable[0], ast.Raise)
        raised = executable[0].exc
        assert isinstance(raised, ast.Call)
        assert isinstance(raised.func, ast.Attribute)
        assert raised.func.attr == "_unsupported_control_error"

    helper = next(
        node
        for node in climate_class.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_unsupported_control_error"
    )
    helper_source = ast.unparse(helper)
    assert helper_source.count("async_record_unsupported_control_attempt") == 1
    assert helper_source.count("ServiceValidationError") == 2
    assert "translation_key='observation_only'" in helper_source


def test_task_11_entity_properties_do_not_read_home_assistant_states() -> None:
    """Test presentation code derives only from the coordinator snapshot."""
    source = (INTEGRATION_DIR / "climate.py").read_text()
    tree = ast.parse(source)
    offenders = [
        ".".join(_attribute_path(node))
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and _attribute_path(node)[-2:] == ("hass", "states")
    ]

    assert offenders == []


def test_phase_1_entity_and_support_modules_are_observation_only() -> None:
    """All approved entity, activity, diagnostic, and Store modules exist."""
    assert (INTEGRATION_DIR / "diagnostics.py").is_file()
    assert (INTEGRATION_DIR / "repairs.py").is_file()
    assert (INTEGRATION_DIR / "event.py").is_file()
    assert (INTEGRATION_DIR / "sensor.py").is_file()
    assert (INTEGRATION_DIR / "history.py").is_file()
    assert (INTEGRATION_DIR / "storage.py").is_file()
    assert (INTEGRATION_DIR / "binary_sensor.py").is_file()
    assert (INTEGRATION_DIR / "switch.py").is_file()
    assert not any(
        _find_prohibited_service_call_paths((INTEGRATION_DIR / module).read_text())
        for module in ("binary_sensor.py", "switch.py")
    )


def test_task_13_repairs_adds_no_control_store_polling_or_repair_flow() -> None:
    """Repairs remains a synchronous reporting boundary with no active repair."""
    repairs = (INTEGRATION_DIR / "repairs.py").read_text()
    command_sink = (INTEGRATION_DIR / "control" / "command_sink.py").read_text()
    integration_sources = "\n".join(
        path.read_text() for path in INTEGRATION_DIR.rglob("*.py")
    )
    prohibited = {
        "hass.services",
        "services.async_call",
        "Store(",
        "async_save",
        "async_load",
        "async_add_executor_job",
        "async_track_time_interval",
        "async_track_time_change",
        "asyncio.sleep",
        "time.sleep",
        "RepairsFlow",
        "async_create_fix_flow",
    }

    assert all(term not in repairs for term in prohibited)
    assert "async_report_command_boundary_violation" in command_sink
    assert "async_create_issue(" in repairs
    assert "async_delete_issue(" in repairs
    assert "is_fixable=policy.is_fixable" in repairs
    assert "services.async_call" not in integration_sources


def test_task_14_modules_have_no_physical_control_or_future_feature_path() -> None:
    """Every Task 14 module remains observation-only and narrowly scoped."""
    task_14_paths = (
        INTEGRATION_DIR / "activity.py",
        INTEGRATION_DIR / "history.py",
        INTEGRATION_DIR / "storage.py",
        INTEGRATION_DIR / "event.py",
        INTEGRATION_DIR / "sensor.py",
        INTEGRATION_DIR / "models" / "activity.py",
    )
    prohibited = {
        "hass.services",
        "services.async_call",
        "SERVICE_SET_",
        "ClimateEntity",
        "FanEntity",
        "SwitchEntity",
        "HumidifierEntity",
        "WaterHeaterEntity",
        "weekly_schedule",
        "occupancy",
        "prediction",
        "simulation",
        "manual_override",
        "command_payload",
        "target_entity_id",
        "async_add_executor_job",
    }
    offenders = [
        f"{path.relative_to(ROOT)} contains {term}"
        for path in task_14_paths
        for term in prohibited
        if term in path.read_text()
    ]

    assert offenders == []


def test_task_15_migration_and_recovery_change_no_control_surface() -> None:
    """Lifecycle hardening changes persistence only, never physical behavior."""
    setup = (INTEGRATION_DIR / "__init__.py").read_text()
    storage = (INTEGRATION_DIR / "storage.py").read_text()
    schema = (INTEGRATION_DIR / "models" / "schema.py").read_text()
    constants = (INTEGRATION_DIR / "const.py").read_text()
    combined = "\n".join((setup, storage, schema, constants))

    assert "CONFIG_ENTRY_MINOR_VERSION = 1" in schema
    assert "STORE_VERSION = 1" in storage
    assert "STORE_MINOR_VERSION = 2" in storage
    assert "RUNTIME_STORE_SCHEMA_VERSION = 1" in schema
    for platform in (
        "Platform.BINARY_SENSOR",
        "Platform.CLIMATE",
        "Platform.EVENT",
        "Platform.SENSOR",
        "Platform.SWITCH",
    ):
        assert constants.count(platform) == 1
    assert "async_migrate_entry" in setup
    assert "restored_source_baselines" in setup
    assert "hass.services" not in combined
    assert "services.async_call" not in combined
    assert "SERVICE_SET_" not in combined
    assert "weekly_schedule" not in combined
    assert "manual_override" not in combined
    assert "prediction" not in combined
    assert "simulation" not in combined
