"""Immutable source-health evaluation state."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .identifiers import ObservationSourceId
from .observation import SourceObservation
from .schema import SourceBaseline


@dataclass(frozen=True, slots=True)
class PendingJumpCandidate:
    """A rejected temperature range awaiting a confirming live reading."""

    source_id: ObservationSourceId
    candidate_value: float
    first_seen_at: datetime


@dataclass(frozen=True, slots=True)
class SourceHealthEvaluation:
    """One health decision and the immutable state for the next evaluation."""

    observation: SourceObservation[float]
    next_baseline: SourceBaseline | None
    pending_jump: PendingJumpCandidate | None
