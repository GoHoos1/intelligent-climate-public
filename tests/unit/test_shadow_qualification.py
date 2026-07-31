"""Test Task 18 restart-safe Shadow qualification and readiness snapshots."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, cast

import pytest

from custom_components.intelligent_climate.models.identifiers import ZoneId
from custom_components.intelligent_climate.models.phase2_schema import (
    Phase2ShadowQualification,
)
from custom_components.intelligent_climate.models.schema import SchemaValidationError
from custom_components.intelligent_climate.models.shadow import (
    ShadowBlockingFault,
    ShadowReadinessReason,
)
from custom_components.intelligent_climate.shadow.qualification import (
    empty_shadow_qualification,
    evaluate_shadow_readiness,
    record_shadow_evaluation,
    reset_shadow_qualification,
    validate_shadow_qualification,
)

NOW = datetime(2026, 7, 31, 16, 0, tzinfo=UTC)
ZONE_A = ZoneId.parse("11111111-1111-4111-8111-111111111111")
ZONE_B = ZoneId.parse("22222222-2222-4222-8222-222222222222")
ZONES = (ZONE_A, ZONE_B)


def _state(
    *,
    started: datetime | None = NOW - timedelta(hours=24),
    evaluated: int = 20,
    valid: int = 19,
    transitions_a: int = 2,
    transitions_b: int = 2,
    faults: tuple[str, ...] = (),
) -> Phase2ShadowQualification:
    return Phase2ShadowQualification(
        started_at_utc=started,
        evaluated_decisions=evaluated,
        valid_evaluations=valid,
        material_transitions_by_zone=MappingProxyType(
            {ZONE_A: transitions_a, ZONE_B: transitions_b}
        ),
        blocking_fault_codes=faults,
    )


def test_empty_qualification_is_immutable_and_not_started() -> None:
    state = empty_shadow_qualification(ZONES)
    readiness = evaluate_shadow_readiness(
        state,
        all_zone_ids=ZONES,
        enabled_zone_ids=ZONES,
        now_utc=NOW,
    )

    assert state.started_at_utc is None
    assert dict(state.material_transitions_by_zone) == {ZONE_A: 0, ZONE_B: 0}
    assert readiness.ready is False
    assert readiness.qualification_percent == 0.0
    assert readiness.blocking_reasons == (
        ShadowReadinessReason.NOT_STARTED,
        ShadowReadinessReason.DURATION,
        ShadowReadinessReason.DECISION_COUNT,
        ShadowReadinessReason.VALID_RATIO,
        ShadowReadinessReason.MATERIAL_TRANSITIONS,
    )
    with pytest.raises(TypeError):
        cast(dict[ZoneId, int], state.material_transitions_by_zone)[ZONE_A] = 1


def test_exact_all_requirement_boundaries_are_ready() -> None:
    readiness = evaluate_shadow_readiness(
        _state(),
        all_zone_ids=ZONES,
        enabled_zone_ids=ZONES,
        now_utc=NOW,
    )

    assert readiness.ready
    assert readiness.qualification_percent == 100.0
    assert readiness.valid_evaluation_percent == 95.0
    assert readiness.elapsed_hours == 24.0
    assert readiness.minimum_material_transitions == 2
    assert readiness.blocking_reasons == ()


@pytest.mark.parametrize(
    ("state", "now", "reason"),
    [
        (
            _state(started=NOW - timedelta(seconds=86399)),
            NOW,
            ShadowReadinessReason.DURATION,
        ),
        (_state(evaluated=19, valid=19), NOW, ShadowReadinessReason.DECISION_COUNT),
        (_state(valid=18), NOW, ShadowReadinessReason.VALID_RATIO),
        (_state(transitions_b=1), NOW, ShadowReadinessReason.MATERIAL_TRANSITIONS),
        (
            _state(faults=(ShadowBlockingFault.SENSOR.value,)),
            NOW,
            ShadowReadinessReason.BLOCKING_FAULT,
        ),
    ],
)
def test_each_requirement_blocks_independently(
    state: Phase2ShadowQualification,
    now: datetime,
    reason: ShadowReadinessReason,
) -> None:
    result = evaluate_shadow_readiness(
        state,
        all_zone_ids=ZONES,
        enabled_zone_ids=ZONES,
        now_utc=now,
    )
    assert not result.ready
    assert reason in result.blocking_reasons
    assert result.qualification_percent < 100.0


def test_only_enabled_zones_govern_transition_readiness() -> None:
    result = evaluate_shadow_readiness(
        _state(transitions_b=0),
        all_zone_ids=ZONES,
        enabled_zone_ids=(ZONE_A,),
        now_utc=NOW,
    )
    assert result.ready
    assert result.minimum_material_transitions == 2


def test_recording_starts_continuity_and_updates_counts_transition_and_faults() -> None:
    state = empty_shadow_qualification(ZONES)
    state = record_shadow_evaluation(
        state,
        all_zone_ids=ZONES,
        evaluated_at_utc=NOW,
        valid=True,
        material_transition_zone_id=ZONE_A,
        active_faults=(ShadowBlockingFault.SENSOR, ShadowBlockingFault.SENSOR),
    )

    assert state.started_at_utc == NOW
    assert state.evaluated_decisions == 1
    assert state.valid_evaluations == 1
    assert state.material_transitions_by_zone[ZONE_A] == 1
    assert state.blocking_fault_codes == (ShadowBlockingFault.SENSOR.value,)

    state = record_shadow_evaluation(
        state,
        all_zone_ids=ZONES,
        evaluated_at_utc=NOW + timedelta(minutes=1),
        valid=False,
        material_transition_zone_id=None,
        active_faults=(),
    )
    assert state.evaluated_decisions == 2
    assert state.valid_evaluations == 1
    assert state.blocking_fault_codes == (ShadowBlockingFault.SAFETY_EVALUATION.value,)


def test_later_valid_evaluation_clears_resolved_fault_snapshot() -> None:
    state = record_shadow_evaluation(
        _state(faults=(ShadowBlockingFault.SENSOR.value,)),
        all_zone_ids=ZONES,
        evaluated_at_utc=NOW,
        valid=True,
        material_transition_zone_id=None,
        active_faults=(),
    )
    assert state.blocking_fault_codes == ()


def test_reset_clears_all_accumulated_evidence() -> None:
    reset = reset_shadow_qualification(_state(), all_zone_ids=ZONES)
    assert reset == empty_shadow_qualification(ZONES)


@pytest.mark.parametrize(
    ("state", "zones", "match"),
    [
        (cast(Any, object()), ZONES, "qualification record"),
        (_state(valid=21), ZONES, "cannot exceed"),
        (replace(_state(), evaluated_decisions=-1), ZONES, "nonnegative"),
        (
            replace(
                _state(), material_transitions_by_zone=MappingProxyType({ZONE_A: 2})
            ),
            ZONES,
            "every runtime zone",
        ),
        (
            _state(faults=(ShadowBlockingFault.SENSOR.value,) * 2),
            ZONES,
            "canonically ordered",
        ),
        (_state(faults=("unsupported",)), ZONES, "unsupported fault"),
        (
            replace(_state(), blocking_fault_codes=cast(Any, ["sensor"])),
            ZONES,
            "immutable fault sequence",
        ),
        (
            replace(_state(), started_at_utc=NOW.replace(tzinfo=None)),
            ZONES,
            "timezone-aware",
        ),
    ],
)
def test_qualification_validation_fails_closed(
    state: object,
    zones: tuple[ZoneId, ...],
    match: str,
) -> None:
    with pytest.raises(SchemaValidationError, match=match):
        validate_shadow_qualification(cast(Any, state), all_zone_ids=zones)


@pytest.mark.parametrize(
    "zone_ids",
    [
        cast(Any, [ZONE_A]),
        cast(Any, (ZONE_A, "bad")),
        (ZONE_A, ZONE_A),
    ],
)
def test_zone_identity_inputs_are_strict(zone_ids: object) -> None:
    with pytest.raises(SchemaValidationError):
        empty_shadow_qualification(cast(Any, zone_ids))


@pytest.mark.parametrize(
    "changes",
    [
        {"evaluated_at_utc": NOW.replace(tzinfo=None)},
        {"evaluated_at_utc": NOW.astimezone(timezone(timedelta(hours=-4)))},
        {"evaluated_at_utc": NOW - timedelta(days=2)},
        {"valid": cast(Any, 1)},
        {"material_transition_zone_id": ZoneId.new()},
        {"active_faults": cast(Any, ("sensor",))},
    ],
)
def test_record_input_validation_is_fail_closed(changes: dict[str, object]) -> None:
    values: dict[str, object] = {
        "all_zone_ids": ZONES,
        "evaluated_at_utc": NOW,
        "valid": True,
        "material_transition_zone_id": None,
        "active_faults": (),
    }
    values.update(changes)
    with pytest.raises(SchemaValidationError):
        record_shadow_evaluation(_state(started=NOW), **cast(Any, values))


@pytest.mark.parametrize(
    "enabled",
    [(), (ZoneId.new(),), cast(Any, [ZONE_A]), (ZONE_A, ZONE_A)],
)
def test_readiness_requires_valid_enabled_zone_subset(enabled: object) -> None:
    with pytest.raises(SchemaValidationError):
        evaluate_shadow_readiness(
            _state(),
            all_zone_ids=ZONES,
            enabled_zone_ids=cast(Any, enabled),
            now_utc=NOW,
        )


def test_readiness_rejects_clock_before_start_and_non_utc() -> None:
    for now in (
        NOW - timedelta(days=2),
        NOW.replace(tzinfo=None),
        NOW.astimezone(timezone(timedelta(hours=-4))),
    ):
        with pytest.raises(SchemaValidationError):
            evaluate_shadow_readiness(
                _state(started=NOW),
                all_zone_ids=ZONES,
                enabled_zone_ids=ZONES,
                now_utc=now,
            )
