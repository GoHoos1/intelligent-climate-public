"""Versioned, permission-aware Phase 2 backend WebSocket API."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback

from .const import DOMAIN
from .models import (
    ZoneId,
    decode_schedule_document,
    encode_phase2_equipment_group_document,
    encode_phase2_options,
    encode_phase2_zone_config,
    encode_schedule_document,
)
from .models.schedule import TargetSpec
from .models.shadow import ShadowReadinessEntitySnapshot
from .narrative import (
    build_current_narrative_facts,
    narrative_to_json,
)
from .schedule.evaluate import ScheduleEvaluationError, evaluate_schedule
from .schedule_storage import (
    ScheduleRevisionConflictError,
    ScheduleStoreError,
)
from .timeline import build_today_timeline, timeline_to_json

API_VERSION = 1
_ENTRY = vol.Required("entry_id")
_ZONE = vol.Required("zone_id")
_BASE: dict[str | vol.Marker, Any] = {
    vol.Required("api_version"): vol.In([API_VERSION])
}

if TYPE_CHECKING:
    from .coordinator import IntelligentClimateCoordinator
    from .runtime import Phase2CoordinatorRuntime


def async_register_websocket_api(hass: HomeAssistant) -> None:
    """Register the stable API once for all config entries."""
    data = hass.data.setdefault(DOMAIN, {})
    if data.get("websocket_api_registered"):
        return
    for handler in (
        websocket_config_get,
        websocket_snapshot_get,
        websocket_subscribe,
        websocket_schedule_get,
        websocket_schedule_validate,
        websocket_schedule_save,
        websocket_schedule_preview,
        websocket_activity_list,
        websocket_shadow_status,
        websocket_observation_status,
        websocket_timeline_today,
        websocket_narrative_current,
    ):
        websocket_api.async_register_command(hass, handler)
    data["websocket_api_registered"] = True


@websocket_api.websocket_command(
    {vol.Required("type"): "intelligent_climate/config/get", **_BASE, _ENTRY: str}
)
@websocket_api.async_response
async def websocket_config_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the canonical validated Phase 2 configuration projection."""
    coordinator = _coordinator(hass, msg, connection)
    if coordinator is None:
        return
    runtime = _runtime(coordinator, msg, connection)
    if runtime is None:
        return
    migration = runtime.migration
    connection.send_result(
        msg["id"],
        {
            "api_version": API_VERSION,
            "config": dict(encode_phase2_equipment_group_document(migration.config)),
            "options": dict(encode_phase2_options(migration.options)),
            "zones": [
                dict(encode_phase2_zone_config(item)) for item in migration.zones
            ],
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "intelligent_climate/snapshot/get", **_BASE, _ENTRY: str}
)
@websocket_api.async_response
async def websocket_snapshot_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return one current observation and policy projection."""
    coordinator = _coordinator(hass, msg, connection)
    if coordinator is None:
        return
    connection.send_result(msg["id"], _snapshot_json(coordinator))


@websocket_api.websocket_command(
    {vol.Required("type"): "intelligent_climate/subscribe", **_BASE, _ENTRY: str}
)
@websocket_api.async_response
async def websocket_subscribe(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Subscribe to canonical snapshot replacements with owned cleanup."""
    coordinator = _coordinator(hass, msg, connection)
    if coordinator is None:
        return

    @callback
    def _updated() -> None:
        connection.send_event(msg["id"], _snapshot_json(coordinator))

    connection.subscriptions[msg["id"]] = coordinator.async_add_listener(_updated)
    connection.send_result(msg["id"], {"api_version": API_VERSION, "subscribed": True})


@websocket_api.websocket_command(
    {vol.Required("type"): "intelligent_climate/schedule/get", **_BASE, _ENTRY: str}
)
@websocket_api.async_response
async def websocket_schedule_get(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the current authoritative schedule or empty revision zero."""
    runtime = _runtime_from_message(hass, msg, connection)
    if runtime is None:
        return
    document = runtime.schedule_store.document
    connection.send_result(
        msg["id"],
        {
            "api_version": API_VERSION,
            "revision": runtime.schedule_store.revision,
            "schedule": (
                None
                if document is None
                else dict(
                    encode_schedule_document(
                        document,
                        validation_context=runtime.schedule_validation_context,
                    )
                )
            ),
        },
    )


_SCHEDULE_INPUT: dict[str | vol.Marker, Any] = {
    **_BASE,
    _ENTRY: str,
    vol.Required("schedule"): dict,
}


@websocket_api.websocket_command(
    {vol.Required("type"): "intelligent_climate/schedule/validate", **_SCHEDULE_INPUT}
)
@websocket_api.async_response
async def websocket_schedule_validate(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Validate a complete unsaved draft using the authoritative backend."""
    runtime = _runtime_from_message(hass, msg, connection)
    if runtime is None:
        return
    try:
        document = decode_schedule_document(
            msg["schedule"],
            validation_context=runtime.schedule_validation_context,
        )
    except (KeyError, TypeError, ValueError) as err:
        connection.send_error(msg["id"], "invalid_schedule", str(err))
        return
    connection.send_result(
        msg["id"],
        {
            "api_version": API_VERSION,
            "valid": True,
            "revision": document.revision,
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "intelligent_climate/schedule/save",
        **_SCHEDULE_INPUT,
        vol.Required("expected_revision"): vol.All(int, vol.Range(min=0)),
    }
)
@websocket_api.require_admin
@websocket_api.async_response
async def websocket_schedule_save(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Atomically save one validated schedule with optimistic concurrency."""
    runtime = _runtime_from_message(hass, msg, connection)
    if runtime is None:
        return
    try:
        document = decode_schedule_document(
            msg["schedule"],
            validation_context=runtime.schedule_validation_context,
        )
        saved = await runtime.schedule_store.async_save(
            document,
            expected_revision=msg["expected_revision"],
        )
    except ScheduleRevisionConflictError as err:
        connection.send_error(
            msg["id"],
            "revision_conflict",
            f"Current schedule revision is {err.actual_revision}",
        )
        return
    except (KeyError, TypeError, ValueError, ScheduleStoreError) as err:
        connection.send_error(msg["id"], "schedule_save_failed", str(err))
        return
    runtime.async_schedule_updated()
    connection.send_result(
        msg["id"],
        {
            "api_version": API_VERSION,
            "revision": saved.revision,
            "schedule": dict(
                encode_schedule_document(
                    saved,
                    validation_context=runtime.schedule_validation_context,
                )
            ),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "intelligent_climate/schedule/preview",
        **_SCHEDULE_INPUT,
        vol.Optional("at_utc"): str,
    }
)
@websocket_api.async_response
async def websocket_schedule_preview(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return an unsaved deterministic preview; never publish it to runtime."""
    runtime = _runtime_from_message(hass, msg, connection)
    if runtime is None:
        return
    try:
        document = decode_schedule_document(
            msg["schedule"],
            validation_context=runtime.schedule_validation_context,
        )
        at = _parse_datetime(msg.get("at_utc"))
        previews = [
            evaluate_schedule(document, zone_id=zone_id, at=at)
            for zone_id in sorted(document.zones, key=str)
            if document.zones[zone_id].enabled
        ]
    except (KeyError, TypeError, ValueError, ScheduleEvaluationError) as err:
        connection.send_error(msg["id"], "preview_failed", str(err))
        return
    connection.send_result(
        msg["id"],
        {
            "api_version": API_VERSION,
            "authoritative": False,
            "at_utc": at.isoformat(),
            "zones": [
                {
                    "zone_id": str(item.zone_id),
                    "profile_id": str(item.profile_id),
                    "period_id": str(item.base_period_id),
                    "target": _target_json(item.base_target),
                    "next_boundary_utc": item.next_boundary_utc.isoformat(),
                    "next_material_transition_utc": (
                        None
                        if item.next_material_transition_utc is None
                        else item.next_material_transition_utc.isoformat()
                    ),
                }
                for item in previews
            ],
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "intelligent_climate/activity/list",
        **_BASE,
        _ENTRY: str,
        vol.Optional("offset", default=0): vol.All(int, vol.Range(min=0)),
        vol.Optional("limit", default=100): vol.All(int, vol.Range(min=1, max=200)),
    }
)
@websocket_api.async_response
async def websocket_activity_list(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return one bounded page of chronological privacy-safe activity."""
    coordinator = _coordinator(hass, msg, connection)
    if coordinator is None:
        return
    records = coordinator.history.records
    offset = msg["offset"]
    selected = records[offset : offset + msg["limit"]]
    connection.send_result(
        msg["id"],
        {
            "api_version": API_VERSION,
            "total": len(records),
            "offset": offset,
            "records": [
                {
                    "record_id": str(item.record_id),
                    "zone_id": None if item.zone_id is None else str(item.zone_id),
                    "timestamp_utc": item.timestamp.isoformat(),
                    "activity_type": item.activity_type.value,
                    "reason_code": item.reason_code.value,
                    "severity": item.severity.value,
                    "explanation": item.explanation,
                }
                for item in selected
            ],
        },
    )


@websocket_api.websocket_command(
    {vol.Required("type"): "intelligent_climate/shadow/status", **_BASE, _ENTRY: str}
)
@websocket_api.async_response
async def websocket_shadow_status(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return current qualification plus bounded would-command history."""
    runtime = _runtime_from_message(hass, msg, connection)
    if runtime is None:
        return
    readiness = runtime.snapshot.shadow_readiness if runtime.snapshot else None
    connection.send_result(
        msg["id"],
        {
            "api_version": API_VERSION,
            "readiness": _readiness_json(readiness),
            "history": [
                {
                    "safety_evaluation_id": str(item.safety_evaluation_id),
                    "evaluated_at_utc": item.evaluated_at_utc.isoformat(),
                    "outcome": item.outcome.value,
                    "reason_code": item.reason_code.value,
                    "would_command": item.would_command is not None,
                }
                for item in runtime.shadow_sink.history
            ],
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "intelligent_climate/observation/status",
        **_BASE,
        _ENTRY: str,
    }
)
@websocket_api.async_response
async def websocket_observation_status(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Report collection status without claiming Phase 3 model readiness."""
    coordinator = _coordinator(hass, msg, connection)
    if coordinator is None:
        return
    snapshot = coordinator.data
    connection.send_result(
        msg["id"],
        {
            "api_version": API_VERSION,
            "collection_active": not coordinator._shutdown,
            "observation_revision": snapshot.revision,
            "calculated_at_utc": snapshot.calculated_at.isoformat(),
            "usable_temperature_sources": sum(
                len(zone.valid_temperature_source_ids) for zone in snapshot.zones
            ),
            "degraded_zone_count": sum(
                zone.sensor_data_degraded or zone.thermostat_data_degraded
                for zone in snapshot.zones
            ),
            "presentation_history_hours": 48,
            "model_ready_history_available": False,
            "history_boundary": (
                "Presentation history is nonauthoritative; model-ready observation "
                "storage begins in Phase 3."
            ),
        },
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): "intelligent_climate/timeline/today",
        **_BASE,
        _ENTRY: str,
        _ZONE: str,
        vol.Optional("local_date"): str,
    }
)
@websocket_api.async_response
async def websocket_timeline_today(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return the canonical local-day factual timeline."""
    coordinator = _coordinator(hass, msg, connection)
    if coordinator is None:
        return
    runtime = _runtime(coordinator, msg, connection)
    if runtime is None:
        return
    try:
        zone_id = ZoneId.parse(msg["zone_id"])
        now = coordinator.data.calculated_at
        selected_date = (
            now.astimezone(
                ZoneInfo(runtime.schedule_validation_context.time_zone)
            ).date()
            if "local_date" not in msg
            else date.fromisoformat(msg["local_date"])
        )
        timeline = build_today_timeline(
            runtime.presentation_trace.document,
            zone_id=zone_id,
            time_zone=runtime.schedule_validation_context.time_zone,
            local_date=selected_date,
            generated_at_utc=now,
        )
    except (TypeError, ValueError) as err:
        connection.send_error(msg["id"], "timeline_failed", str(err))
        return
    connection.send_result(msg["id"], timeline_to_json(timeline))


@websocket_api.websocket_command(
    {
        vol.Required("type"): "intelligent_climate/narrative/current",
        **_BASE,
        _ENTRY: str,
        _ZONE: str,
    }
)
@websocket_api.async_response
async def websocket_narrative_current(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Return a deterministic current fact packet and local rendering."""
    coordinator = _coordinator(hass, msg, connection)
    if coordinator is None:
        return
    runtime = _runtime(coordinator, msg, connection)
    if runtime is None or runtime.snapshot is None:
        connection.send_error(msg["id"], "not_ready", "Policy snapshot is not ready")
        return
    try:
        facts = build_current_narrative_facts(
            coordinator.data,
            runtime.snapshot,
            zone_id=ZoneId.parse(msg["zone_id"]),
        )
    except ValueError as err:
        connection.send_error(msg["id"], "narrative_failed", str(err))
        return
    connection.send_result(msg["id"], narrative_to_json(facts))


def _coordinator(
    hass: HomeAssistant,
    msg: dict[str, Any],
    connection: websocket_api.ActiveConnection,
) -> IntelligentClimateCoordinator | None:
    entry = hass.config_entries.async_get_entry(msg["entry_id"])
    coordinator = None if entry is None else getattr(entry, "runtime_data", None)
    if coordinator is None:
        connection.send_error(msg["id"], "entry_not_loaded", "Entry is not loaded")
    return coordinator


def _runtime(
    coordinator: IntelligentClimateCoordinator,
    msg: dict[str, Any],
    connection: websocket_api.ActiveConnection,
) -> Phase2CoordinatorRuntime | None:
    runtime = coordinator.phase2_runtime
    if runtime is None:
        connection.send_error(msg["id"], "phase2_not_ready", "Phase 2 is not ready")
    return runtime


def _runtime_from_message(
    hass: HomeAssistant,
    msg: dict[str, Any],
    connection: websocket_api.ActiveConnection,
) -> Phase2CoordinatorRuntime | None:
    coordinator = _coordinator(hass, msg, connection)
    return None if coordinator is None else _runtime(coordinator, msg, connection)


def _snapshot_json(
    coordinator: IntelligentClimateCoordinator,
) -> dict[str, object]:
    observation = coordinator.data
    policy = (
        None
        if coordinator.phase2_runtime is None
        else coordinator.phase2_runtime.snapshot
    )
    return {
        "api_version": API_VERSION,
        "entry_id": observation.entry_id,
        "observation_revision": observation.revision,
        "calculated_at_utc": observation.calculated_at.isoformat(),
        "control_state": (
            observation.control_state.value
            if policy is None
            else policy.control_state.value
        ),
        "reason_code": None if policy is None else policy.reason_code.value,
        "zones": [
            {
                "zone_id": str(item.zone_id),
                "effective_temperature_c": item.effective_temperature_c,
                "effective_humidity_pct": item.effective_humidity_pct,
                "sensor_data_degraded": item.sensor_data_degraded,
                "thermostat_data_degraded": item.thermostat_data_degraded,
            }
            for item in observation.zones
        ],
    }


def _target_json(value: TargetSpec) -> dict[str, object]:
    return {
        "kind": value.kind.value,
        "target_c": value.target_c,
        "heat_target_c": value.heat_target_c,
        "cool_target_c": value.cool_target_c,
    }


def _readiness_json(
    value: ShadowReadinessEntitySnapshot | None,
) -> dict[str, object] | None:
    if value is None:
        return None
    return {
        "ready": value.ready,
        "qualification_percent": value.qualification_percent,
        "valid_evaluation_percent": value.valid_evaluation_percent,
        "elapsed_hours": value.elapsed_hours,
        "evaluated_decisions": value.evaluated_decisions,
        "valid_evaluations": value.valid_evaluations,
        "minimum_material_transitions": value.minimum_material_transitions,
        "blocking_reasons": [item.value for item in value.blocking_reasons],
        "blocking_faults": [item.value for item in value.blocking_faults],
    }


def _parse_datetime(value: object) -> datetime:
    if value is None:
        return datetime.now(UTC)
    if not isinstance(value, str):
        raise ValueError("at_utc must be an ISO timestamp")
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("at_utc must be timezone-aware")
    return parsed.astimezone(UTC)
