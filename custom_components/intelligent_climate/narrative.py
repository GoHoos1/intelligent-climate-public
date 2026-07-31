"""Deterministic, fact-bounded current-status narrative for Phase 2."""

from __future__ import annotations

from .models.frontend import FRONTEND_API_VERSION, CurrentNarrativeFacts
from .models.identifiers import ZoneId
from .models.policy_runtime import Phase2PolicySnapshot
from .models.runtime import EntryObservationSnapshot
from .models.schedule import TargetKind, TargetSpec

NARRATIVE_TEMPLATE_VERSION = 1


def build_current_narrative_facts(
    observation: EntryObservationSnapshot,
    policy: Phase2PolicySnapshot,
    *,
    zone_id: ZoneId,
    context_forecast_available: bool = False,
) -> CurrentNarrativeFacts:
    """Project only facts present in the immutable live snapshots."""
    if observation.entry_id != policy.entry_id:
        raise ValueError("observation and policy entries must match")
    if observation.revision != policy.observation_revision:
        raise ValueError("observation and policy revisions must match")
    zone = next((item for item in observation.zones if item.zone_id == zone_id), None)
    policy_zone = policy.zone(zone_id)
    if zone is None or policy_zone is None:
        raise ValueError("zone is not present in current snapshots")
    thermostat = zone.thermostat_states[0] if zone.thermostat_states else None
    categories = ["control", "observation"]
    if policy_zone.scheduled_target is not None:
        categories.append("schedule")
    if policy_zone.effective_target != policy_zone.scheduled_target:
        categories.append("effective_target")
    if zone.sensor_data_degraded or zone.thermostat_data_degraded:
        categories.append("source_quality")
    if context_forecast_available:
        categories.append("context_forecast")
    return CurrentNarrativeFacts(
        api_version=FRONTEND_API_VERSION,
        entry_id=observation.entry_id,
        zone_id=zone_id,
        control_state=policy.control_state.value,
        reason_code=policy.reason_code.value,
        temperature_c=zone.effective_temperature_c,
        hvac_action=(
            None
            if thermostat is None or thermostat.hvac_action is None
            else thermostat.hvac_action.value
        ),
        scheduled_target_c=_single_target(policy_zone.scheduled_target),
        effective_target_c=_single_target(policy_zone.effective_target),
        next_transition_utc=policy_zone.next_transition_utc,
        source_degraded=(zone.sensor_data_degraded or zone.thermostat_data_degraded),
        context_forecast_available=context_forecast_available,
        included_categories=tuple(categories),
    )


def render_current_narrative(facts: CurrentNarrativeFacts) -> str:
    """Render fixed templates without inference, mutation, or command authority."""
    sentences = [_control_sentence(facts)]
    target = facts.effective_target_c or facts.scheduled_target_c
    if target is not None:
        if facts.next_transition_utc is None:
            sentences.append(f"The current target is {target:.1f}°C.")
        else:
            sentences.append(
                f"The current target is {target:.1f}°C until the next "
                f"transition at {facts.next_transition_utc.isoformat()}."
            )
    if facts.temperature_c is not None:
        sentence = f"The zone is {facts.temperature_c:.1f}°C"
        if facts.hvac_action is not None:
            sentence += f" and the thermostat reports {facts.hvac_action}"
        sentences.append(sentence + ".")
    if facts.source_degraded:
        sentences.append("Some current observation data is degraded.")
    if facts.context_forecast_available:
        sentences.append(
            "Outdoor forecast is shown for context and does not affect "
            "Safe Scheduled Control."
        )
    return " ".join(sentences)


def narrative_to_json(facts: CurrentNarrativeFacts) -> dict[str, object]:
    """Return the typed fact packet and its deterministic local rendering."""
    return {
        "api_version": facts.api_version,
        "template_version": NARRATIVE_TEMPLATE_VERSION,
        "entry_id": facts.entry_id,
        "zone_id": str(facts.zone_id),
        "control_state": facts.control_state,
        "reason_code": facts.reason_code,
        "temperature_c": facts.temperature_c,
        "hvac_action": facts.hvac_action,
        "scheduled_target_c": facts.scheduled_target_c,
        "effective_target_c": facts.effective_target_c,
        "next_transition_utc": (
            None
            if facts.next_transition_utc is None
            else facts.next_transition_utc.isoformat()
        ),
        "source_degraded": facts.source_degraded,
        "context_forecast_available": facts.context_forecast_available,
        "included_categories": list(facts.included_categories),
        "rendered": render_current_narrative(facts),
    }


def _single_target(value: TargetSpec | None) -> float | None:
    if value is None or value.kind is not TargetKind.SINGLE:
        return None
    return value.target_c


def _control_sentence(facts: CurrentNarrativeFacts) -> str:
    labels = {
        "observing": "Intelligent Climate is observing only.",
        "manual_idle": "Manual Control is selected and automation is off.",
        "shadow_qualifying": "Scheduled Shadow is qualifying without commands.",
        "shadow_ready": "Scheduled Shadow is ready and still sends no commands.",
        "safe_fallback": "Automatic control is suppressed by Safe Fallback.",
        "emergency_paused": "Control is paused and no automatic command is sent.",
        "degraded": "Observation continues with degraded data.",
        "reconciling": "Live state is being reconciled without commands.",
    }
    return labels.get(
        facts.control_state,
        f"Current control state is {facts.control_state.replace('_', ' ')}.",
    )
