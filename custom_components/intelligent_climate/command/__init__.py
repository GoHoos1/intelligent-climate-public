"""Pure command planning and correlation primitives."""

from .correlation import (
    CorrelationClassification,
    CorrelationInput,
    CorrelationPolicy,
    CorrelationReasonCode,
    CorrelationResult,
    ObservedStateChange,
    correlate_state_change,
    semantic_state_matches,
)
from .dependencies import CommandInputProvider, CommandPlanSink, UtcClock

__all__ = [
    "CommandInputProvider",
    "CommandPlanSink",
    "CorrelationClassification",
    "CorrelationInput",
    "CorrelationPolicy",
    "CorrelationReasonCode",
    "CorrelationResult",
    "ObservedStateChange",
    "UtcClock",
    "correlate_state_change",
    "semantic_state_matches",
]
