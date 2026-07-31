"""Task 13 pure occupancy policy and resolver tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import pytest

from custom_components.intelligent_climate.models import (
    OccupancyBindingId,
    OccupancyBuiltInKind,
    OccupancyModeDefinition,
    OccupancyModeId,
    OccupancyPolicy,
    OccupancySourceBinding,
    OccupancySourceCategory,
    OccupancyUnavailableFallback,
    SchemaValidationError,
    decode_occupancy_policy,
    encode_occupancy_policy,
)
from custom_components.intelligent_climate.occupancy import (
    OccupancyCandidate,
    OccupancyCandidateKind,
    OccupancyReasonCode,
    OccupancyResolutionInput,
    resolve_occupancy,
)

NOW = datetime(2026, 7, 30, 18, tzinfo=UTC)
HOME = OccupancyModeId(UUID(int=1))
AWAY = OccupancyModeId(UUID(int=2))
SLEEP = OccupancyModeId(UUID(int=3))
BINDING = OccupancyBindingId(UUID(int=4))


def _policy(**changes: Any) -> OccupancyPolicy:
    value = OccupancyPolicy(
        sources=(
            OccupancySourceBinding(
                BINDING,
                "binary_sensor.household_present",
                OccupancySourceCategory.BINARY_SENSOR,
                (("on", HOME), ("off", AWAY)),
                enabled=True,
                reviewed=True,
            ),
        ),
        modes=(
            OccupancyModeDefinition(HOME, "Home", OccupancyBuiltInKind.HOME, ()),
            OccupancyModeDefinition(AWAY, "Away", OccupancyBuiltInKind.AWAY, ()),
            OccupancyModeDefinition(SLEEP, "Sleep", OccupancyBuiltInKind.SLEEP, ()),
        ),
        priority_order=(SLEEP, HOME, AWAY),
        arrival_delay_seconds=120,
        departure_delay_seconds=600,
        unavailable_fallback=OccupancyUnavailableFallback.HOME,
    )
    return replace(value, **changes)


def _candidate(
    mode: OccupancyModeId,
    kind: OccupancyCandidateKind,
    age: int,
    available: bool = True,
) -> OccupancyCandidate:
    return OccupancyCandidate(
        BINDING, mode, kind, available, NOW - timedelta(seconds=age)
    )


def test_manual_selection_outranks_automatic_candidates_until_expiry() -> None:
    result = resolve_occupancy(
        _policy(),
        inputs=OccupancyResolutionInput(
            NOW,
            HOME,
            SLEEP,
            NOW + timedelta(minutes=5),
            (_candidate(AWAY, OccupancyCandidateKind.DEPARTURE, 1000),),
        ),
    )
    assert result.mode_id is SLEEP
    assert result.reason_code is OccupancyReasonCode.MANUAL_SELECTION


def test_policy_round_trips_with_stable_ids_and_private_source_projection() -> None:
    policy = _policy()
    assert decode_occupancy_policy(encode_occupancy_policy(policy)) == policy


def test_policy_codec_rejects_unknown_or_nonfinite_configuration() -> None:
    encoded = encode_occupancy_policy(_policy())
    encoded["unexpected"] = True
    with pytest.raises(SchemaValidationError):
        decode_occupancy_policy(encoded)
    encoded = encode_occupancy_policy(_policy())
    encoded["arrival_delay_seconds"] = True
    with pytest.raises(SchemaValidationError):
        decode_occupancy_policy(encoded)


@pytest.mark.parametrize(
    ("candidate", "reason", "mode"),
    [
        (
            _candidate(HOME, OccupancyCandidateKind.ARRIVAL, 119),
            OccupancyReasonCode.ARRIVAL_DELAY,
            AWAY,
        ),
        (
            _candidate(HOME, OccupancyCandidateKind.ARRIVAL, 120),
            OccupancyReasonCode.AUTOMATIC_PRIORITY,
            HOME,
        ),
        (
            _candidate(AWAY, OccupancyCandidateKind.DEPARTURE, 599),
            OccupancyReasonCode.DEPARTURE_DELAY,
            HOME,
        ),
        (
            _candidate(AWAY, OccupancyCandidateKind.DEPARTURE, 600),
            OccupancyReasonCode.AUTOMATIC_PRIORITY,
            AWAY,
        ),
    ],
)
def test_arrival_and_departure_delays_are_exact_and_deterministic(
    candidate: OccupancyCandidate, reason: OccupancyReasonCode, mode: OccupancyModeId
) -> None:
    result = resolve_occupancy(
        _policy(),
        inputs=OccupancyResolutionInput(
            NOW,
            AWAY if candidate.kind is OccupancyCandidateKind.ARRIVAL else HOME,
            candidates=(candidate,),
        ),
    )
    assert result.mode_id is mode
    assert result.reason_code is reason


def test_priority_selects_the_highest_configured_accepted_mode() -> None:
    result = resolve_occupancy(
        _policy(),
        inputs=OccupancyResolutionInput(
            NOW,
            AWAY,
            candidates=(
                _candidate(HOME, OccupancyCandidateKind.ARRIVAL, 120),
                _candidate(SLEEP, OccupancyCandidateKind.ARRIVAL, 120),
            ),
        ),
    )
    assert result.mode_id is SLEEP


def test_unavailable_source_cannot_force_away_and_uses_home_fallback() -> None:
    result = resolve_occupancy(
        _policy(),
        inputs=OccupancyResolutionInput(
            NOW,
            AWAY,
            candidates=(
                _candidate(AWAY, OccupancyCandidateKind.DEPARTURE, 1000, False),
            ),
        ),
    )
    assert result.mode_id is HOME
    assert result.reason_code is OccupancyReasonCode.UNAVAILABLE_HOME_FALLBACK


@pytest.mark.parametrize(
    "policy",
    [
        _policy(priority_order=(HOME, AWAY)),
        _policy(sources=(replace(_policy().sources[0], enabled=True, reviewed=False),)),
        _policy(arrival_delay_seconds=-1),
    ],
)
def test_malformed_policy_is_rejected_before_resolution(
    policy: OccupancyPolicy,
) -> None:
    with pytest.raises(SchemaValidationError):
        resolve_occupancy(policy, inputs=OccupancyResolutionInput(NOW, HOME))


def test_unknown_or_future_candidate_fails_closed() -> None:
    with pytest.raises(SchemaValidationError):
        resolve_occupancy(
            _policy(),
            inputs=OccupancyResolutionInput(
                NOW,
                HOME,
                candidates=(
                    replace(
                        _candidate(HOME, OccupancyCandidateKind.ARRIVAL, 0),
                        binding_id=OccupancyBindingId(UUID(int=99)),
                    ),
                ),
            ),
        )
    with pytest.raises(SchemaValidationError, match="future"):
        resolve_occupancy(
            _policy(),
            inputs=OccupancyResolutionInput(
                NOW,
                HOME,
                candidates=(
                    replace(
                        _candidate(HOME, OccupancyCandidateKind.ARRIVAL, 0),
                        observed_since_utc=NOW + timedelta(seconds=1),
                    ),
                ),
            ),
        )
