"""Pure Shadow sink, history, and qualification primitives."""

from .history import (
    append_shadow_history,
    decode_shadow_history,
    encode_shadow_history,
    shadow_history_record,
)
from .qualification import (
    empty_shadow_qualification,
    evaluate_shadow_readiness,
    record_shadow_evaluation,
    reset_shadow_qualification,
)
from .sink import ShadowCommandSink

__all__ = [
    "ShadowCommandSink",
    "append_shadow_history",
    "decode_shadow_history",
    "empty_shadow_qualification",
    "encode_shadow_history",
    "evaluate_shadow_readiness",
    "record_shadow_evaluation",
    "reset_shadow_qualification",
    "shadow_history_record",
]
