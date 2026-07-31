"""Pure occupancy binding, policy, and effect records for Phase 2 Task 13."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .identifiers import OccupancyBindingId, OccupancyModeId, ScheduleProfileId, ZoneId
from .schema import SchemaValidationError


class OccupancyBuiltInKind(StrEnum):
    """Supported built-in occupancy modes; CUSTOM remains privacy-neutral."""

    HOME = "home"
    AWAY = "away"
    SLEEP = "sleep"
    VACATION = "vacation"
    GUEST = "guest"
    CUSTOM = "custom"


class OccupancyEffectKind(StrEnum):
    """Permitted zone effects, still inert until later command planning."""

    NONE = "none"
    SELECT_PROFILE = "select_profile"
    TARGET_OFFSET = "target_offset"


class OccupancyUnavailableFallback(StrEnum):
    """Safe resolution when automatic occupancy sources are unavailable."""

    HOME = "home"
    LAST_CONFIRMED = "last_confirmed"


class OccupancySourceCategory(StrEnum):
    """Privacy-bounded class of source, never a person or device name."""

    PERSON = "person"
    DEVICE_TRACKER = "device_tracker"
    PRESENCE_SENSOR = "presence_sensor"
    ALARM_PANEL = "alarm_panel"
    INPUT_HELPER = "input_helper"
    BED_OCCUPANCY = "bed_occupancy"
    ROOM_OCCUPANCY = "room_occupancy"
    BINARY_SENSOR = "binary_sensor"


@dataclass(frozen=True, slots=True)
class OccupancySourceBinding:
    """One reviewed source with a strict raw-state to typed-mode mapping."""

    binding_id: OccupancyBindingId
    entity_id: str
    category: OccupancySourceCategory
    mode_by_state: tuple[tuple[str, OccupancyModeId], ...]
    enabled: bool = False
    reviewed: bool = False


@dataclass(frozen=True, slots=True)
class OccupancyEffect:
    """A bounded desired effect for one zone, with no physical authority."""

    kind: OccupancyEffectKind
    profile_id: ScheduleProfileId | None = None
    heat_offset_c: float | None = None
    cool_offset_c: float | None = None


@dataclass(frozen=True, slots=True)
class OccupancyModeDefinition:
    """One stable named mode and its configured zone-local effects."""

    mode_id: OccupancyModeId
    name: str
    kind: OccupancyBuiltInKind
    zone_effects: tuple[tuple[ZoneId, OccupancyEffect], ...]


@dataclass(frozen=True, slots=True)
class OccupancyPolicy:
    """All pure configuration for deterministic occupancy resolution."""

    sources: tuple[OccupancySourceBinding, ...]
    modes: tuple[OccupancyModeDefinition, ...]
    priority_order: tuple[OccupancyModeId, ...]
    arrival_delay_seconds: int
    departure_delay_seconds: int
    unavailable_fallback: OccupancyUnavailableFallback


def validate_occupancy_policy(policy: OccupancyPolicy) -> None:
    """Validate identity, review gate, mappings, modes, and bounded effects."""
    if not isinstance(policy.unavailable_fallback, OccupancyUnavailableFallback):
        raise SchemaValidationError("unavailable_fallback", "is unsupported")
    for path, value in (
        ("arrival_delay_seconds", policy.arrival_delay_seconds),
        ("departure_delay_seconds", policy.departure_delay_seconds),
    ):
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SchemaValidationError(path, "must be a nonnegative whole number")
    source_ids: set[OccupancyBindingId] = set()
    entities: set[str] = set()
    mode_ids: set[OccupancyModeId] = set()
    for index, source in enumerate(policy.sources):
        if not isinstance(source.binding_id, OccupancyBindingId):
            raise SchemaValidationError(f"sources[{index}].binding_id", "is invalid")
        if source.binding_id in source_ids:
            raise SchemaValidationError("sources", "binding IDs must be unique")
        source_ids.add(source.binding_id)
        if not isinstance(source.entity_id, str) or "." not in source.entity_id:
            raise SchemaValidationError(
                f"sources[{index}].entity_id", "must be an entity ID"
            )
        if source.entity_id in entities:
            raise SchemaValidationError("sources", "entity IDs must be unique")
        entities.add(source.entity_id)
        if not isinstance(source.category, OccupancySourceCategory):
            raise SchemaValidationError(f"sources[{index}].category", "is unsupported")
        if not isinstance(source.enabled, bool) or not isinstance(
            source.reviewed, bool
        ):
            raise SchemaValidationError(
                f"sources[{index}]", "review flags must be booleans"
            )
        if source.enabled and not source.reviewed:
            raise SchemaValidationError(
                f"sources[{index}].enabled", "cannot be true before review"
            )
        states = [state for state, _ in source.mode_by_state]
        if not states or any(
            not isinstance(state, str) or not state or len(state) > 64
            for state in states
        ):
            raise SchemaValidationError(
                f"sources[{index}].mode_by_state",
                "states must be bounded nonempty strings",
            )
        if len(set(states)) != len(states) or any(
            not isinstance(mode, OccupancyModeId) for _, mode in source.mode_by_state
        ):
            raise SchemaValidationError(
                f"sources[{index}].mode_by_state", "must be unique valid mappings"
            )
    for index, mode in enumerate(policy.modes):
        if not isinstance(mode.mode_id, OccupancyModeId) or mode.mode_id in mode_ids:
            raise SchemaValidationError("modes", "mode IDs must be valid and unique")
        mode_ids.add(mode.mode_id)
        if (
            not isinstance(mode.name, str)
            or not mode.name.strip()
            or len(mode.name) > 64
        ):
            raise SchemaValidationError(
                f"modes[{index}].name", "must be a bounded nonempty label"
            )
        if not isinstance(mode.kind, OccupancyBuiltInKind):
            raise SchemaValidationError(f"modes[{index}].kind", "is unsupported")
        zone_ids = [zone_id for zone_id, _ in mode.zone_effects]
        if len(set(zone_ids)) != len(zone_ids) or any(
            not isinstance(zone_id, ZoneId) for zone_id in zone_ids
        ):
            raise SchemaValidationError(
                f"modes[{index}].zone_effects", "zone IDs must be unique"
            )
        for zone_index, (_, effect) in enumerate(mode.zone_effects):
            _validate_effect(effect, f"modes[{index}].zone_effects[{zone_index}]")
    if set(policy.priority_order) != mode_ids or len(policy.priority_order) != len(
        mode_ids
    ):
        raise SchemaValidationError(
            "priority_order", "must contain every mode exactly once"
        )
    mapped = {
        mode_id for source in policy.sources for _, mode_id in source.mode_by_state
    }
    if not mapped <= mode_ids:
        raise SchemaValidationError(
            "sources.mode_by_state", "references an unknown mode"
        )


def _validate_effect(effect: OccupancyEffect, path: str) -> None:
    if not isinstance(effect.kind, OccupancyEffectKind):
        raise SchemaValidationError(f"{path}.kind", "is unsupported")
    offsets = (effect.heat_offset_c, effect.cool_offset_c)
    if any(
        value is not None
        and (
            not isinstance(value, int | float)
            or isinstance(value, bool)
            or not isfinite(value)
        )
        for value in offsets
    ):
        raise SchemaValidationError(path, "offsets must be finite numbers")
    if effect.kind is OccupancyEffectKind.NONE and any(
        value is not None for value in (effect.profile_id, *offsets)
    ):
        raise SchemaValidationError(path, "none effect cannot contain values")
    if effect.kind is OccupancyEffectKind.SELECT_PROFILE and (
        not isinstance(effect.profile_id, ScheduleProfileId)
        or any(value is not None for value in offsets)
    ):
        raise SchemaValidationError(path, "profile effect requires only a profile ID")
    if effect.kind is OccupancyEffectKind.TARGET_OFFSET and (
        effect.profile_id is not None or offsets == (None, None)
    ):
        raise SchemaValidationError(path, "offset effect requires at least one offset")


def encode_occupancy_policy(policy: OccupancyPolicy) -> dict[str, object]:
    """Encode a strict policy for an authorized future configuration surface."""
    validate_occupancy_policy(policy)
    return {
        "sources": [
            {
                "binding_id": str(source.binding_id),
                "entity_id": source.entity_id,
                "category": source.category.value,
                "mode_by_state": [
                    {"state": state, "mode_id": str(mode_id)}
                    for state, mode_id in source.mode_by_state
                ],
                "enabled": source.enabled,
                "reviewed": source.reviewed,
            }
            for source in policy.sources
        ],
        "modes": [
            {
                "mode_id": str(mode.mode_id),
                "name": mode.name,
                "kind": mode.kind.value,
                "zone_effects": [
                    {
                        "zone_id": str(zone_id),
                        "kind": effect.kind.value,
                        "profile_id": (
                            None
                            if effect.profile_id is None
                            else str(effect.profile_id)
                        ),
                        "heat_offset_c": effect.heat_offset_c,
                        "cool_offset_c": effect.cool_offset_c,
                    }
                    for zone_id, effect in mode.zone_effects
                ],
            }
            for mode in policy.modes
        ],
        "priority_order": [str(mode_id) for mode_id in policy.priority_order],
        "arrival_delay_seconds": policy.arrival_delay_seconds,
        "departure_delay_seconds": policy.departure_delay_seconds,
        "unavailable_fallback": policy.unavailable_fallback.value,
    }


def decode_occupancy_policy(value: object) -> OccupancyPolicy:
    """Decode one exact policy shape and reject unknown/malformed input."""
    if not isinstance(value, dict) or set(value) != {
        "sources",
        "modes",
        "priority_order",
        "arrival_delay_seconds",
        "departure_delay_seconds",
        "unavailable_fallback",
    }:
        raise SchemaValidationError("occupancy_policy", "must be an exact object")
    try:
        sources = tuple(
            _decode_source(item, index)
            for index, item in enumerate(_list(value["sources"], "sources"))
        )
        modes = tuple(
            _decode_mode(item, index)
            for index, item in enumerate(_list(value["modes"], "modes"))
        )
        priority = tuple(
            OccupancyModeId.parse(_string(item, f"priority_order[{index}]"))
            for index, item in enumerate(
                _list(value["priority_order"], "priority_order")
            )
        )
        policy = OccupancyPolicy(
            sources=sources,
            modes=modes,
            priority_order=priority,
            arrival_delay_seconds=_integer(
                value["arrival_delay_seconds"], "arrival_delay_seconds"
            ),
            departure_delay_seconds=_integer(
                value["departure_delay_seconds"], "departure_delay_seconds"
            ),
            unavailable_fallback=OccupancyUnavailableFallback(
                _string(value["unavailable_fallback"], "unavailable_fallback")
            ),
        )
    except (TypeError, ValueError) as err:
        raise SchemaValidationError(
            "occupancy_policy", "contains an invalid value"
        ) from err
    validate_occupancy_policy(policy)
    return policy


def _decode_source(value: object, index: int) -> OccupancySourceBinding:
    root = _object(value, f"sources[{index}]")
    if set(root) != {
        "binding_id",
        "entity_id",
        "category",
        "mode_by_state",
        "enabled",
        "reviewed",
    }:
        raise SchemaValidationError(
            f"sources[{index}]", "contains missing or unknown fields"
        )
    rows = _list(root["mode_by_state"], f"sources[{index}].mode_by_state")
    mappings = tuple(
        (
            _string(
                _object(item, f"sources[{index}].mode_by_state[{map_index}]").get(
                    "state"
                ),
                f"sources[{index}].mode_by_state[{map_index}].state",
            ),
            OccupancyModeId.parse(
                _string(
                    _object(item, f"sources[{index}].mode_by_state[{map_index}]").get(
                        "mode_id"
                    ),
                    f"sources[{index}].mode_by_state[{map_index}].mode_id",
                )
            ),
        )
        for map_index, item in enumerate(rows)
        if set(_object(item, f"sources[{index}].mode_by_state[{map_index}]"))
        == {"state", "mode_id"}
    )
    if len(mappings) != len(rows):
        raise SchemaValidationError(
            f"sources[{index}].mode_by_state", "contains unknown fields"
        )
    return OccupancySourceBinding(
        OccupancyBindingId.parse(
            _string(root["binding_id"], f"sources[{index}].binding_id")
        ),
        _string(root["entity_id"], f"sources[{index}].entity_id"),
        OccupancySourceCategory(
            _string(root["category"], f"sources[{index}].category")
        ),
        mappings,
        _boolean(root["enabled"], f"sources[{index}].enabled"),
        _boolean(root["reviewed"], f"sources[{index}].reviewed"),
    )


def _decode_mode(value: object, index: int) -> OccupancyModeDefinition:
    root = _object(value, f"modes[{index}]")
    if set(root) != {"mode_id", "name", "kind", "zone_effects"}:
        raise SchemaValidationError(
            f"modes[{index}]", "contains missing or unknown fields"
        )
    effects: list[tuple[ZoneId, OccupancyEffect]] = []
    for effect_index, item in enumerate(
        _list(root["zone_effects"], f"modes[{index}].zone_effects")
    ):
        effect = _object(item, f"modes[{index}].zone_effects[{effect_index}]")
        if set(effect) != {
            "zone_id",
            "kind",
            "profile_id",
            "heat_offset_c",
            "cool_offset_c",
        }:
            raise SchemaValidationError(
                f"modes[{index}].zone_effects[{effect_index}]",
                "contains missing or unknown fields",
            )
        effects.append(
            (
                ZoneId.parse(_string(effect["zone_id"], "zone_id")),
                OccupancyEffect(
                    OccupancyEffectKind(_string(effect["kind"], "kind")),
                    None
                    if effect["profile_id"] is None
                    else ScheduleProfileId.parse(
                        _string(effect["profile_id"], "profile_id")
                    ),
                    _number_or_none(effect["heat_offset_c"], "heat_offset_c"),
                    _number_or_none(effect["cool_offset_c"], "cool_offset_c"),
                ),
            )
        )
    return OccupancyModeDefinition(
        OccupancyModeId.parse(_string(root["mode_id"], f"modes[{index}].mode_id")),
        _string(root["name"], f"modes[{index}].name"),
        OccupancyBuiltInKind(_string(root["kind"], f"modes[{index}].kind")),
        tuple(effects),
    )


def _object(value: object, path: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SchemaValidationError(path, "must be an object")
    return value


def _list(value: object, path: str) -> list[object]:
    if not isinstance(value, list):
        raise SchemaValidationError(path, "must be a list")
    return value


def _string(value: object, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise SchemaValidationError(path, "must be a nonempty string")
    return value


def _integer(value: object, path: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError(path, "must be a whole number")
    return value


def _boolean(value: object, path: str) -> bool:
    if not isinstance(value, bool):
        raise SchemaValidationError(path, "must be a boolean")
    return value


def _number_or_none(value: object, path: str) -> float | None:
    if value is None:
        return None
    if (
        not isinstance(value, int | float)
        or isinstance(value, bool)
        or not isfinite(value)
    ):
        raise SchemaValidationError(path, "must be a finite number or null")
    return float(value)
