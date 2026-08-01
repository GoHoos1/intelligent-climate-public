"""Constants for Intelligent Climate."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "intelligent_climate"
NAME = "Intelligent Climate"
INTEGRATION_VERSION = "0.0.13"

PLATFORMS = (
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.EVENT,
    Platform.SENSOR,
    Platform.SWITCH,
)

EVENT_ACTIVITY = "intelligent_climate_activity"

CONF_EQUIPMENT_GROUP_NAME = "equipment_group_name"
CONF_EQUIPMENT_TYPE = "equipment_type"
CONF_EQUIPMENT_RELATIONSHIP = "equipment_relationship"
CONF_THERMOSTAT_ENTITY_ID = "thermostat_entity_id"
CONF_THERMOSTAT_ENTITY_IDS = "thermostat_entity_ids"
CONF_ZONE_THERMOSTAT_ENTITY_IDS = "zone_thermostat_entity_ids"
CONF_TEMPERATURE_SOURCES = "temperature_sources"
CONF_HUMIDITY_SOURCES = "humidity_sources"
CONF_WINDOW_DOOR_ENTITY_IDS = "window_door_entity_ids"
CONF_OCCUPANCY_ENTITY_IDS = "occupancy_entity_ids"
CONF_STAGE_ENTITY_IDS = "stage_entity_ids"
CONF_FAN_ENTITY_IDS = "fan_entity_ids"
CONF_ZONE_NAME = "zone_name"
CONF_SOURCE_ENABLED = "source_enabled"
CONF_SOURCE_OFFSET_C = "source_offset_c"
CONF_SOURCE_OFFSET_PCT = "source_offset_pct"
CONF_SOURCE_PRIORITY = "source_priority"
CONF_SOURCE_WEIGHT = "source_weight"

SUBENTRY_TYPE_ZONE = "zone"

CONFIG_SCHEMA_VERSION = 1

STATE_CHANGE_DEBOUNCE_SECONDS = 0.1
