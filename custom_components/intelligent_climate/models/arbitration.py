"""Pure shared-equipment arbitration records for Phase 2 Task 14."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite

from .identifiers import EquipmentGroupId, ZoneId
from .schema import EquipmentRelationship, SchemaValidationError


class ZoneDemandDirection(StrEnum):
    """One zone's normalized comfort demand."""

    HEAT = "heat"
    COOL = "cool"
    SATISFIED = "satisfied"
    SUPPRESSED = "suppressed"


class DemandSuppression(StrEnum):
    """Why a zone cannot participate in shared arbitration."""

    NONE = "none"
    OVERRIDDEN = "overridden"
    CONTACT_SUSPENDED = "contact_suspended"
    INVALID = "invalid"


class EquipmentDirection(StrEnum):
    """Observed equipment direction without command semantics."""

    IDLE = "idle"
    HEAT = "heat"
    COOL = "cool"
    UNKNOWN = "unknown"


class RelatedThermostatDisposition(StrEnum):
    """Normalized related-thermostat observation used by the arbiter."""

    NEUTRAL = "neutral"
    HEAT = "heat"
    COOL = "cool"
    UNCERTAIN = "uncertain"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class SharedEquipmentArbitrationPolicy:
    """Reviewed Phase 2 authority and priority configuration."""

    equipment_group_id: EquipmentGroupId
    relationship: EquipmentRelationship
    configured_thermostat_entity_ids: tuple[str, ...]
    command_authority_entity_ids: tuple[str, ...]
    zone_priority_order: tuple[ZoneId, ...]
    authority_reviewed: bool


@dataclass(frozen=True, slots=True)
class ZoneDemand:
    """One complete zone demand after override/contact/occupancy evaluation."""

    zone_id: ZoneId
    direction: ZoneDemandDirection
    deviation_c: float
    requested_target_c: float | None
    suppression: DemandSuppression = DemandSuppression.NONE
    emergency_protection: bool = False


@dataclass(frozen=True, slots=True)
class RelatedThermostatObservation:
    """A privacy-bounded observation of a configured thermostat."""

    entity_id: str
    disposition: RelatedThermostatDisposition
    origin_certain: bool


def validate_shared_arbitration_policy(
    policy: SharedEquipmentArbitrationPolicy,
) -> None:
    """Reject malformed policy values without granting authority."""
    if not isinstance(policy.equipment_group_id, EquipmentGroupId):
        raise SchemaValidationError(
            "equipment_group_id", "must be an equipment group ID"
        )
    if not isinstance(policy.relationship, EquipmentRelationship):
        raise SchemaValidationError("relationship", "is unsupported")
    if not isinstance(policy.authority_reviewed, bool):
        raise SchemaValidationError("authority_reviewed", "must be a boolean")
    _validate_entity_ids(
        policy.configured_thermostat_entity_ids,
        "configured_thermostat_entity_ids",
        allow_empty=False,
    )
    _validate_entity_ids(
        policy.command_authority_entity_ids,
        "command_authority_entity_ids",
        allow_empty=True,
    )
    if not set(policy.command_authority_entity_ids) <= set(
        policy.configured_thermostat_entity_ids
    ):
        raise SchemaValidationError(
            "command_authority_entity_ids",
            "must reference configured thermostats only",
        )
    if not policy.zone_priority_order:
        raise SchemaValidationError("zone_priority_order", "must not be empty")
    if any(not isinstance(item, ZoneId) for item in policy.zone_priority_order):
        raise SchemaValidationError("zone_priority_order", "must contain zone IDs only")
    if len(set(policy.zone_priority_order)) != len(policy.zone_priority_order):
        raise SchemaValidationError(
            "zone_priority_order", "must not contain duplicate zone IDs"
        )


def validate_zone_demands(
    policy: SharedEquipmentArbitrationPolicy,
    demands: tuple[ZoneDemand, ...],
) -> None:
    """Validate one complete, uniquely owned demand set."""
    if not isinstance(demands, tuple):
        raise SchemaValidationError("demands", "must be a tuple")
    zone_ids = [item.zone_id for item in demands]
    if any(not isinstance(item, ZoneId) for item in zone_ids):
        raise SchemaValidationError("demands", "must contain valid zone IDs")
    if len(set(zone_ids)) != len(zone_ids):
        raise SchemaValidationError("demands", "must contain each zone once")
    if set(zone_ids) != set(policy.zone_priority_order):
        raise SchemaValidationError(
            "demands", "must contain every configured priority zone exactly once"
        )
    for index, demand in enumerate(demands):
        path = f"demands[{index}]"
        if not isinstance(demand.direction, ZoneDemandDirection):
            raise SchemaValidationError(f"{path}.direction", "is unsupported")
        if not isinstance(demand.suppression, DemandSuppression):
            raise SchemaValidationError(f"{path}.suppression", "is unsupported")
        if not isinstance(demand.emergency_protection, bool):
            raise SchemaValidationError(
                f"{path}.emergency_protection", "must be a boolean"
            )
        if (
            isinstance(demand.deviation_c, bool)
            or not isinstance(demand.deviation_c, int | float)
            or not isfinite(demand.deviation_c)
            or demand.deviation_c < 0
        ):
            raise SchemaValidationError(
                f"{path}.deviation_c", "must be a finite nonnegative number"
            )
        active = demand.direction in {
            ZoneDemandDirection.HEAT,
            ZoneDemandDirection.COOL,
        }
        if active and demand.suppression is not DemandSuppression.NONE:
            raise SchemaValidationError(
                f"{path}.suppression",
                "must be none for heat or cool demand",
            )
        if (
            demand.direction is ZoneDemandDirection.SATISFIED
            and demand.suppression is not DemandSuppression.NONE
        ):
            raise SchemaValidationError(
                f"{path}.suppression",
                "must be none for satisfied demand",
            )
        if (
            demand.direction is ZoneDemandDirection.SUPPRESSED
            and demand.suppression is DemandSuppression.NONE
        ):
            raise SchemaValidationError(
                f"{path}.suppression",
                "must explain suppressed demand",
            )
        if active:
            if (
                isinstance(demand.requested_target_c, bool)
                or not isinstance(demand.requested_target_c, int | float)
                or not isfinite(demand.requested_target_c)
            ):
                raise SchemaValidationError(
                    f"{path}.requested_target_c",
                    "must be a finite target for heat or cool demand",
                )
        elif demand.requested_target_c is not None:
            raise SchemaValidationError(
                f"{path}.requested_target_c",
                "must be null for satisfied or suppressed demand",
            )
        if demand.emergency_protection and not active:
            raise SchemaValidationError(
                f"{path}.emergency_protection",
                "requires heat or cool demand",
            )


def validate_related_observations(
    policy: SharedEquipmentArbitrationPolicy,
    observations: tuple[RelatedThermostatObservation, ...],
) -> None:
    """Reject malformed or foreign related-thermostat evidence."""
    if not isinstance(observations, tuple):
        raise SchemaValidationError("related_observations", "must be a tuple")
    entity_ids = [item.entity_id for item in observations]
    if len(set(entity_ids)) != len(entity_ids):
        raise SchemaValidationError(
            "related_observations", "must contain each thermostat once"
        )
    configured = set(policy.configured_thermostat_entity_ids)
    for index, observation in enumerate(observations):
        path = f"related_observations[{index}]"
        if observation.entity_id not in configured:
            raise SchemaValidationError(
                f"{path}.entity_id", "is not a configured thermostat"
            )
        if not isinstance(observation.disposition, RelatedThermostatDisposition):
            raise SchemaValidationError(f"{path}.disposition", "is unsupported")
        if not isinstance(observation.origin_certain, bool):
            raise SchemaValidationError(f"{path}.origin_certain", "must be a boolean")


def _validate_entity_ids(
    values: tuple[str, ...], path: str, *, allow_empty: bool
) -> None:
    if not isinstance(values, tuple):
        raise SchemaValidationError(path, "must be a tuple")
    if not allow_empty and not values:
        raise SchemaValidationError(path, "must not be empty")
    if any(
        not isinstance(item, str) or not item.startswith("climate.") for item in values
    ):
        raise SchemaValidationError(path, "must contain climate entity IDs")
    if len(set(values)) != len(values):
        raise SchemaValidationError(path, "must not contain duplicate entity IDs")
