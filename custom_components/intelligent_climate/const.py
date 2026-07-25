"""Constants for Intelligent Climate."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "intelligent_climate"
NAME = "Intelligent Climate"
INTEGRATION_VERSION = "0.0.3"

PLATFORMS = (Platform.CLIMATE,)

CONF_EQUIPMENT_GROUP_NAME = "equipment_group_name"
CONF_EQUIPMENT_TYPE = "equipment_type"
CONF_THERMOSTAT_ENTITY_ID = "thermostat_entity_id"
CONF_TEMPERATURE_SOURCES = "temperature_sources"
CONF_ZONE_NAME = "zone_name"

SUBENTRY_TYPE_ZONE = "zone"

CONFIG_SCHEMA_VERSION = 1

STATE_CHANGE_DEBOUNCE_SECONDS = 0.1
