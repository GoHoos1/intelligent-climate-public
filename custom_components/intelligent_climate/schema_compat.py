"""Version-aware configuration codecs during the Phase 2 transition."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace

from .models import (
    CONFIG_ENTRY_MAJOR_VERSION,
    CONFIG_ENTRY_MINOR_VERSION,
    PHASE2_CONFIG_MAJOR_VERSION,
    PHASE2_CONFIG_MINOR_VERSION,
    PHASE2_ZONE_DATA_VERSION,
    ZONE_DATA_VERSION,
    EquipmentGroupConfig,
    EquipmentGroupDocument,
    EquipmentRelationship,
    IntegrationOptions,
    OperatingMode,
    Phase2BindingCandidate,
    Phase2EquipmentGroupDocument,
    Phase2IntegrationOptions,
    Phase2ZoneConfig,
    SchemaMigrationError,
    SchemaValidationError,
    ThermostatRole,
    ZoneConfig,
    decode_equipment_group_document,
    decode_options,
    decode_phase2_equipment_group_document,
    decode_phase2_options,
    decode_phase2_zone_config,
    decode_zone_config,
    encode_equipment_group_document,
    encode_options,
    encode_phase2_equipment_group_document,
    encode_phase2_options,
    encode_phase2_zone_config,
    encode_zone_config,
)


def is_phase2_config_version(version: int, minor_version: int) -> bool:
    """Return whether a config entry uses the exact Phase 2 schema."""
    return (version, minor_version) == (
        PHASE2_CONFIG_MAJOR_VERSION,
        PHASE2_CONFIG_MINOR_VERSION,
    )


def decode_active_equipment_group(
    value: object,
    *,
    version: int,
    minor_version: int,
) -> EquipmentGroupConfig:
    """Decode a supported Phase 1 or Phase 2 equipment-group document."""
    if is_phase2_config_version(version, minor_version):
        return decode_phase2_equipment_group_document(
            value,
            version=version,
            minor_version=minor_version,
        ).equipment_group
    return decode_equipment_group_document(
        value,
        version=version,
        minor_version=minor_version,
    ).equipment_group


def decode_active_observation_options(
    value: object,
    *,
    version: int,
    minor_version: int,
) -> IntegrationOptions:
    """Decode the observation settings embedded in either config generation."""
    if is_phase2_config_version(version, minor_version):
        return decode_phase2_options(
            value,
            version=version,
            minor_version=minor_version,
        ).observation
    return decode_options(
        value,
        version=version,
        minor_version=minor_version,
    )


def decode_active_zone(value: object) -> ZoneConfig:
    """Decode a supported Phase 1 or Phase 2 zone document."""
    if (
        isinstance(value, Mapping)
        and value.get("data_version") == PHASE2_ZONE_DATA_VERSION
    ):
        return decode_phase2_zone_config(value).zone
    return decode_zone_config(value)


def encode_active_equipment_group(
    group: EquipmentGroupConfig,
    *,
    version: int,
    minor_version: int,
    current_data: object | None,
    time_zone: str,
) -> dict[str, object]:
    """Encode a group while preserving Phase 2 safety and authority state."""
    if is_phase2_config_version(version, minor_version):
        document = (
            _new_phase2_group(group, time_zone=time_zone)
            if current_data is None
            else replace(
                decode_phase2_equipment_group_document(
                    current_data,
                    version=version,
                    minor_version=minor_version,
                ),
                equipment_group=group,
            )
        )
        return dict(encode_phase2_equipment_group_document(document))
    if (version, minor_version) != (
        CONFIG_ENTRY_MAJOR_VERSION,
        CONFIG_ENTRY_MINOR_VERSION,
    ) and not (
        version == CONFIG_ENTRY_MAJOR_VERSION
        and 0 <= minor_version <= CONFIG_ENTRY_MINOR_VERSION
    ):
        raise SchemaMigrationError("version", "unsupported config-entry version")
    return dict(
        encode_equipment_group_document(EquipmentGroupDocument(equipment_group=group))
    )


def encode_active_observation_options(
    options: IntegrationOptions,
    *,
    version: int,
    minor_version: int,
    current_data: object | None,
) -> dict[str, object]:
    """Encode observation options without resetting Phase 2 safety policies."""
    if is_phase2_config_version(version, minor_version):
        if current_data is None:
            from .models import (
                DEFAULT_PHASE2_COMMAND_TIMING,
                DEFAULT_PHASE2_SAFETY_LIMITS,
            )

            document = Phase2IntegrationOptions(
                observation=options,
                safety_limits=DEFAULT_PHASE2_SAFETY_LIMITS,
                command_timing=DEFAULT_PHASE2_COMMAND_TIMING,
            )
        else:
            document = replace(
                decode_phase2_options(
                    current_data,
                    version=version,
                    minor_version=minor_version,
                ),
                observation=options,
            )
        return dict(encode_phase2_options(document))
    return dict(encode_options(options))


def encode_active_zone(
    zone: ZoneConfig,
    *,
    target_data_version: int,
    current_data: object | None,
) -> dict[str, object]:
    """Encode a zone while preserving reviewed Phase 2 behavior bindings."""
    if target_data_version == PHASE2_ZONE_DATA_VERSION:
        document = (
            _migrate_zone(zone)
            if current_data is None
            or not (
                isinstance(current_data, Mapping)
                and current_data.get("data_version") == PHASE2_ZONE_DATA_VERSION
            )
            else replace(decode_phase2_zone_config(current_data), zone=zone)
        )
        return dict(encode_phase2_zone_config(document))
    if target_data_version != ZONE_DATA_VERSION:
        raise SchemaMigrationError("data_version", "unsupported zone data version")
    return dict(encode_zone_config(zone))


def encode_reviewed_active_zone(
    zone: ZoneConfig,
    *,
    target_data_version: int,
    current_data: object | None,
    reviewed_fields: frozenset[str],
) -> dict[str, object]:
    """Encode an interactively reviewed zone and enable selected candidates."""
    if target_data_version != PHASE2_ZONE_DATA_VERSION:
        return encode_active_zone(
            zone,
            target_data_version=target_data_version,
            current_data=current_data,
        )
    document = (
        _migrate_zone(zone)
        if current_data is None
        or not (
            isinstance(current_data, Mapping)
            and current_data.get("data_version") == PHASE2_ZONE_DATA_VERSION
        )
        else replace(decode_phase2_zone_config(current_data), zone=zone)
    )

    def reviewed(entity_ids: tuple[str, ...]) -> tuple[Phase2BindingCandidate, ...]:
        return tuple(
            Phase2BindingCandidate(entity_id=item, enabled=True, reviewed=True)
            for item in entity_ids
        )

    document = replace(
        document,
        zone=zone,
        contact_bindings=(
            reviewed(zone.window_door_entity_ids)
            if "window_door_entity_ids" in reviewed_fields
            else document.contact_bindings
        ),
        occupancy_bindings=(
            reviewed(zone.occupancy_entity_ids)
            if "occupancy_entity_ids" in reviewed_fields
            else document.occupancy_bindings
        ),
        fan_bindings=(
            reviewed(zone.fan_entity_ids)
            if "fan_entity_ids" in reviewed_fields
            else document.fan_bindings
        ),
    )
    return dict(encode_phase2_zone_config(document))


def migrate_zone_document(value: object) -> Phase2ZoneConfig:
    """Return one strict Phase 2 zone, accepting a Phase 1 source document."""
    if (
        isinstance(value, Mapping)
        and value.get("data_version") == PHASE2_ZONE_DATA_VERSION
    ):
        return decode_phase2_zone_config(value)
    return _migrate_zone(decode_zone_config(value))


def _new_phase2_group(
    group: EquipmentGroupConfig,
    *,
    time_zone: str,
) -> Phase2EquipmentGroupDocument:
    if group.relationship is EquipmentRelationship.SHARED_ZONED:
        authorities = tuple(
            binding.entity_id
            for binding in group.thermostats
            if binding.role is ThermostatRole.PRIMARY
        )
        authority_review_required = True
    else:
        authorities = tuple(binding.entity_id for binding in group.thermostats)
        authority_review_required = not authorities
    return Phase2EquipmentGroupDocument(
        equipment_group=group,
        automation_enabled=False,
        desired_operating_mode=OperatingMode.OBSERVE_ONLY,
        command_authority_entity_ids=authorities,
        authority_review_required=authority_review_required,
        acknowledged_time_zone=time_zone,
    )


def _migrate_zone(zone: ZoneConfig) -> Phase2ZoneConfig:
    candidate = Phase2ZoneConfig(
        zone=zone,
        contact_bindings=tuple(
            Phase2BindingCandidate(entity_id=item, enabled=False, reviewed=False)
            for item in zone.window_door_entity_ids
        ),
        occupancy_bindings=tuple(
            Phase2BindingCandidate(entity_id=item, enabled=False, reviewed=False)
            for item in zone.occupancy_entity_ids
        ),
        fan_bindings=tuple(
            Phase2BindingCandidate(entity_id=item, enabled=False, reviewed=False)
            for item in zone.fan_entity_ids
        ),
    )
    encoded = dict(encode_phase2_zone_config(candidate))
    decoded = decode_phase2_zone_config(encoded)
    if decoded != candidate:
        raise SchemaValidationError("zone", "Phase 2 zone must round-trip")
    return decoded
