import type {
  ConfigurationResponse,
  ScheduleDocument,
  ScheduleProfile,
  ScheduleWeekday,
} from "../types/contracts";
import { createUuid } from "../util/uuid";

const WEEKDAYS: readonly ScheduleWeekday[] = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

export function createEmptyScheduleDraft(
  entryId: string,
  configuration: ConfigurationResponse,
  now = new Date(),
): ScheduleDocument {
  const equipmentGroup = record(
    configuration.config["equipment_group"],
    "config.equipment_group",
  );
  const equipmentGroupId = requiredString(
    equipmentGroup["equipment_group_id"],
    "config.equipment_group.equipment_group_id",
  );
  const timeZone = requiredString(
    configuration.config["acknowledged_time_zone"],
    "config.acknowledged_time_zone",
  );
  const zones: ScheduleDocument["zones"] = {};
  for (const zone of configuration.zones) {
    const profileId = createUuid();
    zones[zone.zone_id] = {
      zone_id: zone.zone_id,
      enabled: false,
      selected_profile_id: profileId,
      profiles: [emptyProfile(profileId)],
    };
  }
  return {
    schedule_schema_version: 1,
    entry_id: entryId,
    equipment_group_id: equipmentGroupId,
    time_zone: timeZone,
    revision: 0,
    zones,
    saved_at_utc: now.toISOString(),
  };
}

export function prepareScheduleWrite(
  document: ScheduleDocument,
  now = new Date(),
): ScheduleDocument {
  return { ...structuredClone(document), saved_at_utc: now.toISOString() };
}

function emptyProfile(profileId: string): ScheduleProfile {
  const days = {} as ScheduleProfile["days"];
  for (const weekday of WEEKDAYS) {
    days[weekday] = [];
  }
  return {
    profile_id: profileId,
    name: "Normal",
    enabled: true,
    days,
  };
}

function record(value: unknown, path: string): Record<string, unknown> {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new Error(`${path} is unavailable`);
  }
  return value as Record<string, unknown>;
}

function requiredString(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new Error(`${path} is unavailable`);
  }
  return value;
}
