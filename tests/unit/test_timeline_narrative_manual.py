"""Task 20 timeline, narrative, and typed manual-action contracts."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from types import MappingProxyType, SimpleNamespace
from typing import Any, cast
from uuid import uuid4

import pytest

from custom_components.intelligent_climate.manual_control import (
    ManualActionKind,
    ManualControlAction,
    evaluate_manual_control_action,
)
from custom_components.intelligent_climate.models import (
    DEFAULT_PHASE2_SAFETY_LIMITS,
    ControlExecutionState,
    ControlReason,
    EquipmentGroupId,
    PresentationFanAction,
    PresentationHvacAction,
    PresentationPointKind,
    PresentationQualityFlag,
    PresentationTraceDocument,
    PresentationTracePoint,
    TargetKind,
    TargetSpec,
    ZoneId,
)
from custom_components.intelligent_climate.models.frontend import (
    CurrentNarrativeFacts,
    TimelineMissingInterval,
    TimelineSample,
    TimelineSeries,
    TimelineSeriesKind,
    TimelineValueKind,
    TodayTimeline,
)
from custom_components.intelligent_climate.models.modes import OperatingMode
from custom_components.intelligent_climate.narrative import (
    build_current_narrative_facts,
    narrative_to_json,
    render_current_narrative,
)
from custom_components.intelligent_climate.timeline import (
    build_today_timeline,
    timeline_to_json,
)

ENTRY_ID = "entry-1"
GROUP_ID = EquipmentGroupId.parse("b7ea11b6-6ff6-49de-934e-a9be3a1ce5a3")
ZONE_ID = ZoneId.parse("99246285-6f02-4e8a-94ed-bdfd4a5e62c4")
NOW = datetime(2026, 7, 27, 16, tzinfo=UTC)
DEFAULT_SCHEDULED_TARGET = TargetSpec(TargetKind.SINGLE, 21.0, None, None)
DEFAULT_EFFECTIVE_TARGET = TargetSpec(TargetKind.SINGLE, 22.0, None, None)


def _point(
    timestamp: datetime,
    *,
    temperature: float | None = 21.0,
    scheduled: TargetSpec | None = DEFAULT_SCHEDULED_TARGET,
    effective: TargetSpec | None = DEFAULT_EFFECTIVE_TARGET,
) -> PresentationTracePoint:
    return PresentationTracePoint(
        point_id=uuid4(),
        zone_id=ZONE_ID,
        timestamp_utc=timestamp,
        kind=PresentationPointKind.MATERIAL_CHANGE,
        effective_temperature_c=temperature,
        effective_humidity_pct=45.0,
        outdoor_temperature_c=30.0,
        scheduled_target=scheduled,
        effective_target=effective,
        hvac_action=PresentationHvacAction.COOLING,
        fan_action=PresentationFanAction.ON,
        quality_flags=(
            PresentationQualityFlag.TEMPERATURE_VALID,
            PresentationQualityFlag.THERMOSTAT_VALID,
        ),
        annotation_ids=(),
    )


def _document(*points: PresentationTracePoint) -> PresentationTraceDocument:
    return PresentationTraceDocument(
        entry_id=ENTRY_ID,
        equipment_group_id=GROUP_ID,
        saved_at_utc=max((item.timestamp_utc for item in points), default=NOW),
        samples_by_zone=MappingProxyType({ZONE_ID: tuple(points)}),
        annotations=(),
    )


@pytest.mark.parametrize(
    ("local_date", "hours"),
    [(date(2026, 3, 8), 23), (date(2026, 11, 1), 25)],
)
def test_today_timeline_uses_actual_dst_day_duration(
    local_date: date, hours: int
) -> None:
    timeline = build_today_timeline(
        _document(),
        zone_id=ZONE_ID,
        time_zone="America/New_York",
        local_date=local_date,
        generated_at_utc=NOW,
    )
    assert (
        timeline.day_end_utc - timeline.day_start_utc
    ).total_seconds() == hours * 3600


def test_timeline_labels_provenance_omits_unavailable_and_reports_gaps() -> None:
    first = _point(NOW - timedelta(minutes=30), temperature=None)
    second = _point(NOW, temperature=22.0)
    timeline = build_today_timeline(
        _document(first, second),
        zone_id=ZONE_ID,
        time_zone="America/New_York",
        local_date=NOW.astimezone().date(),
        generated_at_utc=NOW,
    )
    by_kind = {item.kind: item for item in timeline.series}
    temperature = by_kind[TimelineSeriesKind.EFFECTIVE_TEMPERATURE]
    assert temperature.value_kind is TimelineValueKind.MEASURED
    assert [sample.value for sample in temperature.samples] == [22.0]
    humidity = by_kind[TimelineSeriesKind.EFFECTIVE_HUMIDITY]
    assert len(humidity.missing_intervals) == 1
    assert all(
        item.value_kind not in {TimelineValueKind.PREDICTED, TimelineValueKind.PLANNED}
        for item in timeline.series
    )
    payload = timeline_to_json(timeline)
    assert payload["indoor_prediction_available"] is False
    capability = payload["capability_statement"]
    assert isinstance(capability, str)
    assert "No indoor prediction" in capability


def test_range_targets_become_distinct_configured_and_calculated_series() -> None:
    target = TargetSpec(TargetKind.RANGE, None, 19.0, 24.0)
    timeline = build_today_timeline(
        _document(_point(NOW, scheduled=target, effective=target)),
        zone_id=ZONE_ID,
        time_zone="America/New_York",
        local_date=NOW.astimezone().date(),
        generated_at_utc=NOW,
    )
    kinds = {item.kind for item in timeline.series}
    assert TimelineSeriesKind.SCHEDULED_HEAT_TARGET in kinds
    assert TimelineSeriesKind.SCHEDULED_COOL_TARGET in kinds
    assert TimelineSeriesKind.EFFECTIVE_HEAT_TARGET in kinds
    assert TimelineSeriesKind.EFFECTIVE_COOL_TARGET in kinds
    assert TimelineSeriesKind.SCHEDULED_TARGET not in kinds


def test_frontend_series_rejects_predicted_or_empty_placeholder() -> None:
    with pytest.raises(ValueError, match="predicted or planned"):
        TimelineSeries(
            kind=TimelineSeriesKind.EFFECTIVE_TEMPERATURE,
            value_kind=TimelineValueKind.PREDICTED,
            unit="°C",
            source_quality="available",
            coverage_start_utc=NOW,
            coverage_end_utc=NOW,
            missing_intervals=(),
            samples=(),
        )


@pytest.mark.parametrize(
    ("factory", "message"),
    [
        (lambda: TimelineSample(NOW.replace(tzinfo=None), 1.0), "timezone-aware"),
        (lambda: TimelineSample(NOW, float("inf")), "finite"),
        (lambda: TimelineSample(NOW, ""), "must not be empty"),
        (lambda: TimelineSample(NOW, True), "finite numeric or text"),
        (
            lambda: TimelineMissingInterval(NOW, NOW),
            "positive duration",
        ),
    ],
)
def test_frontend_samples_and_gaps_fail_closed(
    factory: Callable[[], object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        factory()


def test_frontend_timeline_metadata_fails_closed() -> None:
    sample = TimelineSample(NOW, 1.0)
    with pytest.raises(ValueError, match="empty timeline"):
        TimelineSeries(
            TimelineSeriesKind.EFFECTIVE_TEMPERATURE,
            TimelineValueKind.MEASURED,
            "°C",
            "available",
            NOW,
            NOW,
            (),
            (),
        )
    with pytest.raises(ValueError, match="explicit coverage"):
        TimelineSeries(
            TimelineSeriesKind.EFFECTIVE_TEMPERATURE,
            TimelineValueKind.MEASURED,
            "°C",
            "available",
            None,
            NOW,
            (),
            (sample,),
        )
    with pytest.raises(ValueError, match="reversed"):
        TimelineSeries(
            TimelineSeriesKind.EFFECTIVE_TEMPERATURE,
            TimelineValueKind.MEASURED,
            "°C",
            "available",
            NOW,
            NOW - timedelta(seconds=1),
            (),
            (sample,),
        )
    with pytest.raises(ValueError, match="source_quality"):
        TimelineSeries(
            TimelineSeriesKind.EFFECTIVE_TEMPERATURE,
            TimelineValueKind.MEASURED,
            "°C",
            "",
            NOW,
            NOW,
            (),
            (sample,),
        )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"api_version": 2}, "unsupported"),
        ({"day_end_utc": NOW}, "reversed"),
        ({"day_end_utc": NOW + timedelta(hours=22)}, "23, 24, or 25"),
        ({"indoor_prediction_available": True}, "no indoor prediction"),
    ],
)
def test_today_timeline_contract_rejects_false_capabilities(
    changes: dict[str, object], message: str
) -> None:
    values = {
        "api_version": 1,
        "entry_id": ENTRY_ID,
        "zone_id": ZONE_ID,
        "time_zone": "UTC",
        "local_date": "2026-07-27",
        "day_start_utc": NOW,
        "day_end_utc": NOW + timedelta(hours=24),
        "generated_at_utc": NOW,
        "series": (),
        "annotations": (),
    }
    values.update(changes)
    with pytest.raises(ValueError, match=message):
        TodayTimeline(**values)  # type: ignore[arg-type]


def _facts(**changes: object) -> CurrentNarrativeFacts:
    values = {
        "api_version": 1,
        "entry_id": ENTRY_ID,
        "zone_id": ZONE_ID,
        "control_state": ControlExecutionState.SHADOW_QUALIFYING.value,
        "reason_code": ControlReason.SHADOW_QUALIFYING.value,
        "temperature_c": 22.0,
        "hvac_action": "cooling",
        "scheduled_target_c": 21.0,
        "effective_target_c": 22.0,
        "next_transition_utc": NOW + timedelta(hours=1),
        "source_degraded": False,
        "context_forecast_available": True,
        "included_categories": ("control", "observation", "context_forecast"),
    }
    values.update(changes)
    return CurrentNarrativeFacts(**values)  # type: ignore[arg-type]


def test_narrative_uses_only_packet_facts_and_labels_forecast_context() -> None:
    rendered = render_current_narrative(_facts())
    assert "22.0°C" in rendered
    assert "reports cooling" in rendered
    assert "does not affect Safe Scheduled Control" in rendered
    assert "because" not in rendered
    payload = narrative_to_json(_facts())
    assert payload["template_version"] == 1
    assert payload["included_categories"] == [
        "control",
        "observation",
        "context_forecast",
    ]


def test_narrative_fact_builder_uses_only_matching_snapshot_values() -> None:
    zone = SimpleNamespace(
        zone_id=ZONE_ID,
        thermostat_states=(),
        effective_temperature_c=20.5,
        sensor_data_degraded=True,
        thermostat_data_degraded=False,
    )
    policy_zone = SimpleNamespace(
        scheduled_target=DEFAULT_SCHEDULED_TARGET,
        effective_target=DEFAULT_EFFECTIVE_TARGET,
        next_transition_utc=NOW + timedelta(hours=1),
    )
    observation = SimpleNamespace(entry_id=ENTRY_ID, revision=3, zones=(zone,))
    policy = SimpleNamespace(
        entry_id=ENTRY_ID,
        observation_revision=3,
        control_state=ControlExecutionState.SHADOW_QUALIFYING,
        reason_code=ControlReason.SHADOW_QUALIFYING,
        zone=lambda selected: policy_zone if selected == ZONE_ID else None,
    )
    facts = build_current_narrative_facts(
        observation,  # type: ignore[arg-type]
        policy,  # type: ignore[arg-type]
        zone_id=ZONE_ID,
        context_forecast_available=True,
    )
    assert facts.temperature_c == 20.5
    assert facts.source_degraded
    assert facts.included_categories == (
        "control",
        "observation",
        "schedule",
        "effective_target",
        "source_quality",
        "context_forecast",
    )
    for invalid in (
        SimpleNamespace(entry_id="other", revision=3, zones=(zone,)),
        SimpleNamespace(entry_id=ENTRY_ID, revision=4, zones=(zone,)),
        SimpleNamespace(entry_id=ENTRY_ID, revision=3, zones=()),
    ):
        with pytest.raises(ValueError):
            build_current_narrative_facts(
                invalid,  # type: ignore[arg-type]
                policy,  # type: ignore[arg-type]
                zone_id=ZONE_ID,
            )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"api_version": 2}, "unsupported"),
        ({"temperature_c": float("nan")}, "finite"),
        ({"included_categories": ("control", "control")}, "unique"),
    ],
)
def test_narrative_fact_packet_fails_closed(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _facts(**changes)


@pytest.mark.parametrize(
    "state",
    [
        ControlExecutionState.OBSERVING.value,
        ControlExecutionState.MANUAL_IDLE.value,
        ControlExecutionState.SHADOW_READY.value,
        ControlExecutionState.SAFE_FALLBACK.value,
        ControlExecutionState.EMERGENCY_PAUSED.value,
        ControlExecutionState.DEGRADED.value,
        ControlExecutionState.RECONCILING.value,
        "window_suspended",
    ],
)
def test_narrative_control_templates_are_deterministic(state: str) -> None:
    first = render_current_narrative(_facts(control_state=state))
    second = render_current_narrative(_facts(control_state=state))
    assert first == second


def _action(
    kind: ManualActionKind = ManualActionKind.SET_TARGET,
    **changes: object,
) -> ManualControlAction:
    values = {
        "kind": kind,
        "entry_id": ENTRY_ID,
        "zone_id": ZONE_ID,
        "observed_revision": 7,
        "user_context_id": "context-1",
        "created_at_utc": NOW,
        "target_c": 21.0 if kind is ManualActionKind.SET_TARGET else None,
        "hvac_mode": "heat" if kind is ManualActionKind.SET_HVAC_MODE else None,
        "fan_mode": "auto" if kind is ManualActionKind.SET_FAN_MODE else None,
    }
    values.update(changes)
    return ManualControlAction(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "kind",
    list(ManualActionKind),
)
def test_typed_manual_action_accepts_only_fresh_explicit_current_user_intent(
    kind: ManualActionKind,
) -> None:
    decision = evaluate_manual_control_action(
        _action(kind),
        operating_mode=OperatingMode.MANUAL_CONTROL,
        control_state=ControlExecutionState.MANUAL_IDLE,
        current_revision=7,
        now_utc=NOW + timedelta(seconds=30),
        safety_limits=DEFAULT_PHASE2_SAFETY_LIMITS,
        supported_hvac_modes=("heat",),
        supported_fan_modes=("auto",),
    )
    assert decision.accepted_for_future_planning
    assert decision.reason_code == "validated_explicit_user_action"


@pytest.mark.parametrize(
    ("changes", "reason"),
    [
        ({"created_at_utc": NOW - timedelta(seconds=31)}, "fresh_intent_required"),
        ({"observed_revision": 6}, "current_revision_required"),
        ({"target_c": 40.0}, "target_outside_limits"),
    ],
)
def test_manual_action_rejections_are_reason_coded(
    changes: dict[str, object], reason: str
) -> None:
    action = _action(**cast(Any, changes))
    decision = evaluate_manual_control_action(
        action,
        operating_mode=OperatingMode.MANUAL_CONTROL,
        control_state=ControlExecutionState.MANUAL_IDLE,
        current_revision=7,
        now_utc=NOW,
        safety_limits=DEFAULT_PHASE2_SAFETY_LIMITS,
        supported_hvac_modes=("heat",),
        supported_fan_modes=("auto",),
    )
    assert not decision.accepted_for_future_planning
    assert decision.reason_code == reason


def test_manual_action_is_not_a_command_or_service_payload() -> None:
    action = _action()
    assert not hasattr(action, "domain")
    assert not hasattr(action, "service")
    assert not hasattr(action, "service_data")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"entry_id": ""}, "authenticated user"),
        ({"observed_revision": 0}, "positive"),
        ({"created_at_utc": NOW.replace(tzinfo=None)}, "timezone-aware"),
        ({"target_c": None}, "do not match"),
        ({"target_c": float("inf")}, "finite"),
    ],
)
def test_manual_action_shape_fails_closed(
    changes: dict[str, object], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        _action(**cast(Any, changes))


@pytest.mark.parametrize(
    ("action", "reason"),
    [
        (
            _action(ManualActionKind.SET_HVAC_MODE, hvac_mode="cool"),
            "unsupported_hvac_mode",
        ),
        (_action(ManualActionKind.SET_FAN_MODE, fan_mode="on"), "unsupported_fan_mode"),
    ],
)
def test_manual_capability_rejections_are_explicit(
    action: ManualControlAction, reason: str
) -> None:
    decision = evaluate_manual_control_action(
        action,
        operating_mode=OperatingMode.MANUAL_CONTROL,
        control_state=ControlExecutionState.MANUAL_IDLE,
        current_revision=7,
        now_utc=NOW,
        safety_limits=DEFAULT_PHASE2_SAFETY_LIMITS,
        supported_hvac_modes=("heat",),
        supported_fan_modes=("auto",),
    )
    assert decision.reason_code == reason
