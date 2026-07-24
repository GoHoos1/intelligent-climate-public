"""Test pure Task 8 source freshness and health evaluation."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime, timedelta, timezone
from math import inf, nan
from pathlib import Path

import pytest

from custom_components.intelligent_climate.health import (
    HUMIDITY_PLAUSIBLE_MAX,
    HUMIDITY_PLAUSIBLE_MIN,
    JUMP_CONFIRMATION_DELAY_SECONDS,
    evaluate_humidity_health,
    evaluate_temperature_health,
)
from custom_components.intelligent_climate.models import (
    ExclusionReason,
    ObservationSourceId,
    PendingJumpCandidate,
    SourceBaseline,
    SourceHealthEvaluation,
    SourceObservation,
    SourceQuality,
)

SOURCE_ID = ObservationSourceId.parse("f15f73b1-ea59-4b28-819f-7b99acf065bf")
OTHER_SOURCE_ID = ObservationSourceId.parse("0b6fc506-0833-458d-a139-16d917a27443")
NOW = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
BASELINE_TIME = NOW - timedelta(minutes=5)
BASELINE = SourceBaseline(20.0, BASELINE_TIME)
DEFAULTS = {
    "stale_after_seconds": 300,
    "plausible_min_c": 0.0,
    "plausible_max_c": 50.0,
    "jump_limit_c_per_5_minutes": 3.0,
}


def _observation(
    value: float | None = 20.0,
    *,
    raw_value: object = "20.0",
    observed_at: datetime = NOW,
    source_last_reported: datetime | None = NOW,
    quality: SourceQuality = SourceQuality.VALID,
    restored: bool = False,
    source_id: ObservationSourceId = SOURCE_ID,
) -> SourceObservation[float]:
    reason = None if quality is SourceQuality.VALID else ExclusionReason(quality.value)
    return SourceObservation(
        source_id=source_id,
        raw_value=raw_value,
        normalized_value=value,
        observed_at=observed_at,
        source_last_reported=source_last_reported,
        quality=quality,
        exclusion_reason=reason,
        restored=restored,
    )


def _temperature(
    observation: SourceObservation[float],
    *,
    baseline: SourceBaseline | None = BASELINE,
    pending_jump: PendingJumpCandidate | None = None,
    **overrides: float | int,
) -> SourceHealthEvaluation:
    policy = DEFAULTS | overrides
    return evaluate_temperature_health(
        observation,
        baseline=baseline,
        pending_jump=pending_jump,
        stale_after_seconds=int(policy["stale_after_seconds"]),
        plausible_min_c=float(policy["plausible_min_c"]),
        plausible_max_c=float(policy["plausible_max_c"]),
        jump_limit_c_per_5_minutes=float(policy["jump_limit_c_per_5_minutes"]),
    )


def _assert_excluded(
    result: SourceHealthEvaluation,
    quality: SourceQuality,
    original: SourceObservation[float],
) -> None:
    output = result.observation
    assert output is not original
    assert output.source_id is original.source_id
    assert output.raw_value is original.raw_value
    assert output.observed_at is original.observed_at
    assert output.source_last_reported is original.source_last_reported
    assert output.restored is original.restored
    assert output.normalized_value is None
    assert output.quality is quality
    assert output.exclusion_reason is ExclusionReason(quality.value)


def test_health_models_are_frozen_slotted_and_exported() -> None:
    """Test Task 8 state is immutable and has no instance dictionaries."""
    candidate = PendingJumpCandidate(SOURCE_ID, 27.0, NOW)
    result = SourceHealthEvaluation(_observation(), BASELINE, candidate)

    assert not hasattr(candidate, "__dict__")
    assert not hasattr(result, "__dict__")
    with pytest.raises(FrozenInstanceError):
        candidate.candidate_value = 28.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.pending_jump = None  # type: ignore[misc]


def test_health_evaluation_does_not_mutate_inputs() -> None:
    """Test accepted and rejected paths leave every supplied object unchanged."""
    observation = _observation(24.0, raw_value={"nested": [1, 2]})
    candidate = PendingJumpCandidate(SOURCE_ID, 23.0, NOW - timedelta(seconds=10))
    before = (observation, BASELINE, candidate)

    result = _temperature(observation, pending_jump=candidate)

    assert before == (observation, BASELINE, candidate)
    assert result.next_baseline is BASELINE
    assert observation.normalized_value == 24.0
    _assert_excluded(result, SourceQuality.JUMP_REJECTED, observation)


def test_health_module_contains_no_clock_read() -> None:
    """Test deterministic health code has no current-clock API call."""
    source = (
        Path(__file__).parents[2]
        / "custom_components"
        / "intelligent_climate"
        / "health.py"
    ).read_text()

    assert "datetime.now" not in source
    assert "datetime.utcnow" not in source
    assert "dt_util.now" not in source
    assert "dt_util.utcnow" not in source
    assert "time.time" not in source


@pytest.mark.parametrize(
    ("field", "observation"),
    [
        ("observation.observed_at", _observation(observed_at=NOW.replace(tzinfo=None))),
        (
            "observation.source_last_reported",
            _observation(source_last_reported=NOW.replace(tzinfo=None)),
        ),
    ],
)
def test_naive_observation_timestamps_are_rejected(
    field: str,
    observation: SourceObservation[float],
) -> None:
    """Test caller timestamps must be timezone-aware."""
    with pytest.raises(ValueError, match=field.replace(".", r"\.")):
        _temperature(observation)


@pytest.mark.parametrize(
    ("observation", "message"),
    [
        (_observation(None), "normalized value"),
        (_observation(source_last_reported=None), "source_last_reported"),
        (_observation(nan), "must be finite"),
        (_observation(inf), "must be finite"),
    ],
)
def test_malformed_valid_observations_are_rejected(
    observation: SourceObservation[float],
    message: str,
) -> None:
    """Test malformed Task 7 valid records are programming errors."""
    with pytest.raises(ValueError, match=message):
        _temperature(observation)


def test_nonfinite_value_is_rejected_even_on_malformed_exclusion() -> None:
    """Test no nonfinite normalized value may enter Task 8."""
    observation = _observation(inf, quality=SourceQuality.NON_FINITE)

    with pytest.raises(ValueError, match="normalized value must be finite"):
        _temperature(observation)


@pytest.mark.parametrize("threshold", [-1, -100])
def test_negative_freshness_is_rejected(threshold: int) -> None:
    """Test freshness policy cannot be negative."""
    with pytest.raises(ValueError, match="stale_after_seconds"):
        _temperature(_observation(), stale_after_seconds=threshold)
    with pytest.raises(ValueError, match="stale_after_seconds"):
        evaluate_humidity_health(
            _observation(),
            stale_after_seconds=threshold,
        )


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"plausible_min_c": nan}, "plausible_min_c"),
        ({"plausible_min_c": -inf}, "plausible_min_c"),
        ({"plausible_max_c": inf}, "plausible_max_c"),
        (
            {"plausible_min_c": 30.0, "plausible_max_c": 20.0},
            "must not exceed",
        ),
        ({"jump_limit_c_per_5_minutes": nan}, "jump_limit"),
        ({"jump_limit_c_per_5_minutes": inf}, "jump_limit"),
        ({"jump_limit_c_per_5_minutes": 0.0}, "jump_limit"),
        ({"jump_limit_c_per_5_minutes": -1.0}, "jump_limit"),
    ],
)
def test_invalid_temperature_policy_is_rejected(
    overrides: dict[str, float],
    message: str,
) -> None:
    """Test temperature policy invariants fail deterministically."""
    policy = DEFAULTS | overrides
    with pytest.raises(ValueError, match=message):
        evaluate_temperature_health(
            _observation(),
            baseline=BASELINE,
            pending_jump=None,
            stale_after_seconds=int(policy["stale_after_seconds"]),
            plausible_min_c=float(policy["plausible_min_c"]),
            plausible_max_c=float(policy["plausible_max_c"]),
            jump_limit_c_per_5_minutes=float(policy["jump_limit_c_per_5_minutes"]),
        )


@pytest.mark.parametrize(
    ("baseline", "message"),
    [
        (SourceBaseline(nan, NOW), "last_accepted_value"),
        (SourceBaseline(inf, NOW), "last_accepted_value"),
        (SourceBaseline(20.0, NOW.replace(tzinfo=None)), "last_accepted_at"),
    ],
)
def test_malformed_baseline_is_rejected(
    baseline: SourceBaseline,
    message: str,
) -> None:
    """Test accepted baseline invariants are enforced."""
    with pytest.raises(ValueError, match=message):
        _temperature(_observation(), baseline=baseline)
    with pytest.raises(ValueError, match=message):
        evaluate_humidity_health(
            _observation(),
            stale_after_seconds=300,
            baseline=baseline,
        )


@pytest.mark.parametrize(
    ("candidate", "message"),
    [
        (
            PendingJumpCandidate(OTHER_SOURCE_ID, 27.0, NOW),
            "source_id",
        ),
        (
            PendingJumpCandidate(SOURCE_ID, nan, NOW),
            "candidate_value",
        ),
        (
            PendingJumpCandidate(SOURCE_ID, inf, NOW),
            "candidate_value",
        ),
        (
            PendingJumpCandidate(SOURCE_ID, 27.0, NOW.replace(tzinfo=None)),
            "first_seen_at",
        ),
    ],
)
def test_malformed_pending_candidate_is_rejected(
    candidate: PendingJumpCandidate,
    message: str,
) -> None:
    """Test pending jump state belongs to this source and is well formed."""
    with pytest.raises(ValueError, match=message):
        _temperature(_observation(), pending_jump=candidate)


@pytest.mark.parametrize(
    "quality",
    [
        SourceQuality.UNAVAILABLE,
        SourceQuality.UNKNOWN,
        SourceQuality.NON_NUMERIC,
        SourceQuality.NON_FINITE,
        SourceQuality.UNIT_UNSUPPORTED,
    ],
)
def test_task_7_exclusions_pass_through_and_clear_pending(
    quality: SourceQuality,
) -> None:
    """Test original Task 7 exclusions win over all Task 8 checks."""
    observation = _observation(
        None,
        raw_value=quality.value,
        source_last_reported=None,
        quality=quality,
        restored=True,
    )
    candidate = PendingJumpCandidate(SOURCE_ID, 28.0, NOW)

    result = _temperature(observation, pending_jump=candidate)

    assert result.observation is observation
    assert result.next_baseline is BASELINE
    assert result.pending_jump is None
    assert result.observation.normalized_value is None
    assert result.observation.exclusion_reason is ExclusionReason(quality.value)


def test_task_7_humidity_exclusion_passes_through_and_preserves_baseline() -> None:
    """Test humidity also preserves an existing Task 7 exclusion exactly."""
    observation = _observation(
        None,
        source_last_reported=None,
        quality=SourceQuality.UNAVAILABLE,
    )

    result = evaluate_humidity_health(
        observation,
        stale_after_seconds=300,
        baseline=BASELINE,
    )

    assert result == SourceHealthEvaluation(observation, BASELINE, None)
    assert result.observation is observation


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        (-1000.0, False),
        (-0.000001, False),
        (0.0, True),
        (20.123456789, True),
        (50.0, True),
        (50.000001, False),
        (1000.0, False),
    ],
)
def test_temperature_plausibility_bounds_are_inclusive_and_unrounded(
    value: float,
    accepted: bool,
) -> None:
    """Test configured Celsius bounds reject without clamp or rounding."""
    observation = _observation(value, raw_value=value)

    result = _temperature(observation, baseline=None)

    if accepted:
        assert result.observation is observation
        assert result.observation.normalized_value == value
        assert result.next_baseline == SourceBaseline(value, NOW)
    else:
        _assert_excluded(result, SourceQuality.IMPLAUSIBLE, observation)
        assert result.next_baseline is None
    assert result.pending_jump is None


def test_implausible_temperature_preserves_existing_baseline_and_recovers() -> None:
    """Test an extreme value cannot poison the next plausible evaluation."""
    bad = _temperature(
        _observation(500.0, raw_value=500.0),
        pending_jump=PendingJumpCandidate(SOURCE_ID, 30.0, NOW),
    )
    recovered = _temperature(_observation(20.5))

    assert bad.next_baseline is BASELINE
    assert bad.pending_jump is None
    assert recovered.observation.quality is SourceQuality.VALID
    assert recovered.next_baseline == SourceBaseline(20.5, NOW)


@pytest.mark.parametrize(
    ("value", "accepted"),
    [
        (-0.000001, False),
        (0.0, True),
        (45.123456, True),
        (100.0, True),
        (100.000001, False),
    ],
)
def test_humidity_uses_fixed_inclusive_physical_bounds(
    value: float,
    accepted: bool,
) -> None:
    """Test humidity remains percentage points and has no jump rule."""
    observation = _observation(value, raw_value=value)

    result = evaluate_humidity_health(
        observation,
        stale_after_seconds=300,
        baseline=BASELINE,
    )

    assert (HUMIDITY_PLAUSIBLE_MIN, HUMIDITY_PLAUSIBLE_MAX) == (0.0, 100.0)
    if accepted:
        assert result.observation is observation
        assert result.next_baseline == SourceBaseline(value, NOW)
    else:
        _assert_excluded(result, SourceQuality.IMPLAUSIBLE, observation)
        assert result.next_baseline is BASELINE
    assert result.pending_jump is None


def test_humidity_has_no_rate_limit_and_first_value_establishes_baseline() -> None:
    """Test any fresh plausible humidity change is accepted directly."""
    first = evaluate_humidity_health(
        _observation(1.0),
        stale_after_seconds=300,
    )
    jumped = evaluate_humidity_health(
        _observation(99.0, source_last_reported=NOW + timedelta(seconds=1)),
        stale_after_seconds=300,
        baseline=first.next_baseline,
    )

    assert first.next_baseline == SourceBaseline(1.0, NOW)
    assert jumped.observation.quality is SourceQuality.VALID
    assert jumped.next_baseline == SourceBaseline(
        99.0,
        NOW + timedelta(seconds=1),
    )


def test_restored_value_is_rejected_even_when_equal_to_baseline_then_recovers() -> None:
    """Test only a later non-restored live observation may update the baseline."""
    restored = _observation(
        20.0,
        raw_value="20 restored",
        restored=True,
    )
    candidate = PendingJumpCandidate(SOURCE_ID, 28.0, NOW)

    rejected = _temperature(restored, pending_jump=candidate)
    live = _temperature(_observation(20.0, raw_value="20 live"))

    _assert_excluded(rejected, SourceQuality.RESTORED_NOT_CONFIRMED, restored)
    assert rejected.observation.restored is True
    assert rejected.next_baseline is BASELINE
    assert rejected.pending_jump is None
    assert live.observation.quality is SourceQuality.VALID
    assert live.next_baseline == SourceBaseline(20.0, NOW)


@pytest.mark.parametrize(
    ("age", "expected"),
    [
        (timedelta(seconds=299), SourceQuality.VALID),
        (timedelta(seconds=300), SourceQuality.VALID),
        (timedelta(seconds=300, microseconds=1), SourceQuality.STALE),
        (timedelta(seconds=900), SourceQuality.STALE),
        (timedelta(seconds=-60), SourceQuality.VALID),
    ],
)
def test_freshness_boundary_and_future_timestamp(
    age: timedelta,
    expected: SourceQuality,
) -> None:
    """Test only age strictly beyond the threshold is stale."""
    source_last_reported = NOW - age
    observation = _observation(
        20.0,
        source_last_reported=source_last_reported,
    )

    result = _temperature(observation, baseline=None)

    assert result.observation.quality is expected
    if expected is SourceQuality.VALID:
        assert result.next_baseline == SourceBaseline(20.0, source_last_reported)
    else:
        _assert_excluded(result, SourceQuality.STALE, observation)
        assert result.next_baseline is None


def test_stale_value_clears_pending_preserves_baseline_and_recovers() -> None:
    """Test a stale exclusion cannot replace or leak the accepted value."""
    observation = _observation(
        28.0,
        raw_value="stale 28",
        source_last_reported=NOW - timedelta(seconds=301),
    )
    pending = PendingJumpCandidate(SOURCE_ID, 28.0, NOW - timedelta(minutes=2))

    stale = _temperature(observation, pending_jump=pending)
    fresh = _temperature(_observation(20.5))

    _assert_excluded(stale, SourceQuality.STALE, observation)
    assert stale.observation.normalized_value is None
    assert stale.next_baseline is BASELINE
    assert stale.pending_jump is None
    assert fresh.observation.quality is SourceQuality.VALID


def test_first_healthy_temperature_establishes_source_timestamp_baseline() -> None:
    """Test first acceptance uses source update time, not evaluation time."""
    updated = NOW - timedelta(seconds=5)
    observation = _observation(21.25, source_last_reported=updated)

    result = _temperature(observation, baseline=None)

    assert result.observation is observation
    assert result.next_baseline == SourceBaseline(21.25, updated)
    assert result.pending_jump is None


@pytest.mark.parametrize("value", [17.0, 20.0, 23.0])
def test_normal_change_and_exact_rate_boundary_are_accepted(value: float) -> None:
    """Test positive, negative, unchanged, and inclusive allowed changes."""
    result = _temperature(_observation(value))

    assert result.observation.quality is SourceQuality.VALID
    assert result.next_baseline == SourceBaseline(value, NOW)
    assert result.pending_jump is None


@pytest.mark.parametrize("value", [16.999999, 23.000001])
def test_value_just_beyond_rate_boundary_creates_candidate(value: float) -> None:
    """Test a first excessive jump is excluded without clamping."""
    observation = _observation(value, raw_value=value)

    result = _temperature(observation)

    _assert_excluded(result, SourceQuality.JUMP_REJECTED, observation)
    assert result.next_baseline is BASELINE
    assert result.pending_jump == PendingJumpCandidate(SOURCE_ID, value, NOW)


def test_early_consistent_candidate_remains_rejected_and_keeps_first_time() -> None:
    """Test a consistent range cannot confirm before 30 seconds."""
    first_time = NOW - timedelta(seconds=10)
    candidate = PendingJumpCandidate(SOURCE_ID, 27.0, first_time)
    observation = _observation(27.05)

    result = _temperature(observation, pending_jump=candidate)

    _assert_excluded(result, SourceQuality.JUMP_REJECTED, observation)
    assert result.next_baseline is BASELINE
    assert result.pending_jump is candidate
    assert result.pending_jump.first_seen_at is first_time


@pytest.mark.parametrize("delay_seconds", [30, 31, 300])
def test_consistent_candidate_at_or_after_30_seconds_confirms(
    delay_seconds: int,
) -> None:
    """Test a second consistent reading accepts the current candidate range."""
    candidate = PendingJumpCandidate(
        SOURCE_ID,
        27.0,
        NOW - timedelta(seconds=delay_seconds),
    )
    allowed = 3.0 * delay_seconds / 300
    observation = _observation(27.0 + allowed)

    result = _temperature(observation, pending_jump=candidate)

    assert result.observation is observation
    assert result.observation.quality is SourceQuality.VALID
    assert result.next_baseline == SourceBaseline(27.0 + allowed, NOW)
    assert result.pending_jump is None


def test_inconsistent_candidate_restarts_confirmation_period() -> None:
    """Test a value outside old and candidate ranges becomes the new candidate."""
    original = PendingJumpCandidate(
        SOURCE_ID,
        27.0,
        NOW - timedelta(seconds=40),
    )
    changed = _temperature(
        _observation(32.0),
        pending_jump=original,
    )
    too_early = _temperature(
        _observation(
            32.05,
            observed_at=NOW + timedelta(seconds=29),
            source_last_reported=NOW + timedelta(seconds=29),
        ),
        pending_jump=changed.pending_jump,
    )
    confirmed = _temperature(
        _observation(
            32.1,
            observed_at=NOW + timedelta(seconds=30),
            source_last_reported=NOW + timedelta(seconds=30),
        ),
        pending_jump=changed.pending_jump,
    )

    assert changed.pending_jump == PendingJumpCandidate(SOURCE_ID, 32.0, NOW)
    assert too_early.observation.quality is SourceQuality.JUMP_REJECTED
    assert too_early.pending_jump is changed.pending_jump
    assert confirmed.observation.quality is SourceQuality.VALID
    assert confirmed.next_baseline == SourceBaseline(
        32.1,
        NOW + timedelta(seconds=30),
    )


def test_return_to_baseline_range_accepts_and_clears_candidate() -> None:
    """Test a rejected jump can recover through the original accepted range."""
    candidate = PendingJumpCandidate(
        SOURCE_ID,
        28.0,
        NOW - timedelta(seconds=10),
    )
    observation = _observation(22.5)

    result = _temperature(observation, pending_jump=candidate)

    assert result.observation is observation
    assert result.next_baseline == SourceBaseline(22.5, NOW)
    assert result.pending_jump is None


@pytest.mark.parametrize(
    ("value", "quality"),
    [
        (20.0, SourceQuality.VALID),
        (20.000001, SourceQuality.JUMP_REJECTED),
    ],
)
def test_zero_elapsed_time_accepts_only_unchanged_value(
    value: float,
    quality: SourceQuality,
) -> None:
    """Test zero elapsed time permits zero temperature change."""
    baseline = SourceBaseline(20.0, NOW)

    result = _temperature(_observation(value), baseline=baseline)

    assert result.observation.quality is quality


def test_timezone_offsets_compare_by_instant_for_baseline_and_candidate() -> None:
    """Test aware datetimes with different offsets compare correctly."""
    eastern = timezone(timedelta(hours=-4))
    baseline = SourceBaseline(
        20.0,
        datetime(2026, 7, 23, 7, 55, tzinfo=eastern),
    )
    candidate = PendingJumpCandidate(
        SOURCE_ID,
        27.0,
        datetime(2026, 7, 23, 7, 59, 30, tzinfo=eastern),
    )
    observation = _observation(
        27.2,
        source_last_reported=datetime(2026, 7, 23, 12, 0, tzinfo=UTC),
    )

    result = _temperature(
        observation,
        baseline=baseline,
        pending_jump=candidate,
    )

    assert result.observation.quality is SourceQuality.VALID
    assert result.next_baseline == SourceBaseline(27.2, NOW)


@pytest.mark.parametrize(
    "initial_quality",
    [SourceQuality.UNAVAILABLE, SourceQuality.UNKNOWN],
)
def test_task_7_invalid_to_live_valid_recovery(
    initial_quality: SourceQuality,
) -> None:
    """Test missing/sentinel state does not poison later live input."""
    invalid = _temperature(
        _observation(
            None,
            quality=initial_quality,
            source_last_reported=None,
        ),
    )
    recovered = _temperature(_observation(20.5), baseline=invalid.next_baseline)

    assert invalid.next_baseline is BASELINE
    assert recovered.observation.quality is SourceQuality.VALID
    assert recovered.next_baseline == SourceBaseline(20.5, NOW)


def test_task_8_only_produces_approved_health_qualities() -> None:
    """Test Task 9 outlier and contradiction reasons remain dormant."""
    results = [
        _temperature(_observation(-1.0), baseline=None),
        _temperature(_observation(20.0, restored=True), baseline=None),
        _temperature(
            _observation(
                20.0,
                source_last_reported=NOW - timedelta(seconds=301),
            ),
            baseline=None,
        ),
        _temperature(_observation(30.0)),
    ]

    assert {result.observation.quality for result in results} == {
        SourceQuality.IMPLAUSIBLE,
        SourceQuality.RESTORED_NOT_CONFIRMED,
        SourceQuality.STALE,
        SourceQuality.JUMP_REJECTED,
    }
    assert all(
        result.observation.quality
        not in {SourceQuality.OUTLIER, SourceQuality.CONTRADICTORY}
        for result in results
    )


def test_jump_confirmation_delay_is_fixed_documented_policy() -> None:
    """Test Task 8 adds no user option for the confirmation interval."""
    assert JUMP_CONFIRMATION_DELAY_SECONDS == 30
