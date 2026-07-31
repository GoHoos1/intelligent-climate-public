"""Pure contact-binding records for Phase 2 Task 12."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .identifiers import ContactBindingId, EquipmentGroupId, ZoneId
from .schema import SchemaValidationError


class ContactKind(StrEnum):
    """Physical class of the contact, used only for policy defaults."""

    WINDOW = "window"
    EXTERIOR_DOOR = "exterior_door"


class ContactScope(StrEnum):
    """Scope at which a qualifying contact suppresses comfort automation."""

    ZONE = "zone"
    EQUIPMENT_GROUP = "equipment_group"


class ContactUnavailablePolicy(StrEnum):
    """Fail-closed handling of a contact that cannot be observed."""

    TREAT_OPEN = "treat_open"
    IGNORE_AND_DEGRADE = "ignore_and_degrade"


@dataclass(frozen=True, slots=True)
class ContactBinding:
    """One strict, inert contact policy owned by a zone or equipment group."""

    binding_id: ContactBindingId
    entity_id: str
    kind: ContactKind
    scope: ContactScope
    zone_id: ZoneId | None
    equipment_group_id: EquipmentGroupId
    open_debounce_seconds: int
    grace_seconds: int
    minimum_open_seconds: int
    close_debounce_seconds: int
    resume_delay_seconds: int
    unavailable_policy: ContactUnavailablePolicy
    notification_after_seconds: int
    reminder_interval_seconds: int | None
    suspend_shared_group: bool = False
    enabled: bool = False
    reviewed: bool = False


def validate_contact_binding(binding: ContactBinding) -> None:
    """Reject malformed or unsafe configuration before it reaches evaluation."""
    if not isinstance(binding.binding_id, ContactBindingId):
        raise SchemaValidationError("binding_id", "must be a contact binding ID")
    if not isinstance(binding.equipment_group_id, EquipmentGroupId):
        raise SchemaValidationError(
            "equipment_group_id", "must be an equipment group ID"
        )
    if not isinstance(binding.entity_id, str) or not binding.entity_id.startswith(
        "binary_sensor."
    ):
        raise SchemaValidationError("entity_id", "must be a binary_sensor entity ID")
    if not isinstance(binding.kind, ContactKind):
        raise SchemaValidationError("kind", "must be a supported contact kind")
    if not isinstance(binding.scope, ContactScope):
        raise SchemaValidationError("scope", "must be a supported contact scope")
    if binding.scope is ContactScope.ZONE and not isinstance(binding.zone_id, ZoneId):
        raise SchemaValidationError("zone_id", "is required for zone scope")
    if binding.scope is ContactScope.EQUIPMENT_GROUP and binding.zone_id is not None:
        raise SchemaValidationError(
            "zone_id", "must be absent for equipment group scope"
        )
    if not isinstance(binding.unavailable_policy, ContactUnavailablePolicy):
        raise SchemaValidationError("unavailable_policy", "is unsupported")
    if not isinstance(binding.enabled, bool) or not isinstance(binding.reviewed, bool):
        raise SchemaValidationError("enabled", "and reviewed must be booleans")
    if binding.enabled and not binding.reviewed:
        raise SchemaValidationError("enabled", "cannot be true before review")
    if not isinstance(binding.suspend_shared_group, bool):
        raise SchemaValidationError("suspend_shared_group", "must be a boolean")
    values = {
        "open_debounce_seconds": binding.open_debounce_seconds,
        "grace_seconds": binding.grace_seconds,
        "minimum_open_seconds": binding.minimum_open_seconds,
        "close_debounce_seconds": binding.close_debounce_seconds,
        "resume_delay_seconds": binding.resume_delay_seconds,
        "notification_after_seconds": binding.notification_after_seconds,
    }
    for path, value in values.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise SchemaValidationError(path, "must be a nonnegative whole number")
    if binding.notification_after_seconds <= 0:
        raise SchemaValidationError("notification_after_seconds", "must be positive")
    if binding.reminder_interval_seconds is not None and (
        not isinstance(binding.reminder_interval_seconds, int)
        or isinstance(binding.reminder_interval_seconds, bool)
        or binding.reminder_interval_seconds <= 0
    ):
        raise SchemaValidationError(
            "reminder_interval_seconds", "must be positive or null"
        )


def encode_contact_binding(binding: ContactBinding) -> dict[str, object]:
    """Encode a validated contact configuration without runtime activation."""
    validate_contact_binding(binding)
    return {
        "binding_id": str(binding.binding_id),
        "entity_id": binding.entity_id,
        "kind": binding.kind.value,
        "scope": binding.scope.value,
        "zone_id": None if binding.zone_id is None else str(binding.zone_id),
        "equipment_group_id": str(binding.equipment_group_id),
        "open_debounce_seconds": binding.open_debounce_seconds,
        "grace_seconds": binding.grace_seconds,
        "minimum_open_seconds": binding.minimum_open_seconds,
        "close_debounce_seconds": binding.close_debounce_seconds,
        "resume_delay_seconds": binding.resume_delay_seconds,
        "unavailable_policy": binding.unavailable_policy.value,
        "notification_after_seconds": binding.notification_after_seconds,
        "reminder_interval_seconds": binding.reminder_interval_seconds,
        "suspend_shared_group": binding.suspend_shared_group,
        "enabled": binding.enabled,
        "reviewed": binding.reviewed,
    }


def decode_contact_binding(value: object) -> ContactBinding:
    """Strictly decode one contact binding from JSON-compatible data."""
    if not isinstance(value, dict):
        raise SchemaValidationError("contact_binding", "must be an object")
    expected = set(encode_contact_binding(_sample_binding()).keys())
    if set(value) != expected:
        raise SchemaValidationError(
            "contact_binding", "contains missing or unknown fields"
        )
    try:
        binding = ContactBinding(
            binding_id=ContactBindingId.parse(
                _string(value["binding_id"], "binding_id")
            ),
            entity_id=_string(value["entity_id"], "entity_id"),
            kind=ContactKind(_string(value["kind"], "kind")),
            scope=ContactScope(_string(value["scope"], "scope")),
            zone_id=(
                None
                if value["zone_id"] is None
                else ZoneId.parse(_string(value["zone_id"], "zone_id"))
            ),
            equipment_group_id=EquipmentGroupId.parse(
                _string(value["equipment_group_id"], "equipment_group_id")
            ),
            open_debounce_seconds=_integer(
                value["open_debounce_seconds"], "open_debounce_seconds"
            ),
            grace_seconds=_integer(value["grace_seconds"], "grace_seconds"),
            minimum_open_seconds=_integer(
                value["minimum_open_seconds"], "minimum_open_seconds"
            ),
            close_debounce_seconds=_integer(
                value["close_debounce_seconds"], "close_debounce_seconds"
            ),
            resume_delay_seconds=_integer(
                value["resume_delay_seconds"], "resume_delay_seconds"
            ),
            unavailable_policy=ContactUnavailablePolicy(
                _string(value["unavailable_policy"], "unavailable_policy")
            ),
            notification_after_seconds=_integer(
                value["notification_after_seconds"], "notification_after_seconds"
            ),
            reminder_interval_seconds=(
                None
                if value["reminder_interval_seconds"] is None
                else _integer(
                    value["reminder_interval_seconds"], "reminder_interval_seconds"
                )
            ),
            suspend_shared_group=_boolean(
                value["suspend_shared_group"], "suspend_shared_group"
            ),
            enabled=_boolean(value["enabled"], "enabled"),
            reviewed=_boolean(value["reviewed"], "reviewed"),
        )
    except (TypeError, ValueError) as err:
        raise SchemaValidationError(
            "contact_binding", "contains an invalid value"
        ) from err
    validate_contact_binding(binding)
    return binding


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


def _sample_binding() -> ContactBinding:
    """Return a private shape-only instance; never expose it as configuration."""
    from uuid import UUID

    return ContactBinding(
        ContactBindingId(UUID(int=1)),
        "binary_sensor.contact",
        ContactKind.WINDOW,
        ContactScope.EQUIPMENT_GROUP,
        None,
        EquipmentGroupId(UUID(int=2)),
        0,
        0,
        0,
        0,
        0,
        ContactUnavailablePolicy.TREAT_OPEN,
        1,
        None,
    )
