import type {
  ActivityResponse,
  ConfigurationResponse,
  NarrativeResponse,
  ObservationStatusResponse,
  ScheduleDocument,
  ScheduleGetResponse,
  SchedulePreviewResponse,
  ScheduleSaveResponse,
  ScheduleValidationResponse,
  ShadowStatusResponse,
  SnapshotResponse,
  TodayTimelineResponse,
} from "../src/types/contracts";

export const ENTRY_ID = "entry-1";
export const ZONE_ID = "99246285-6f02-4e8a-94ed-bdfd4a5e62c4";
export const NOW = "2026-07-31T18:00:00+00:00";

export const configuration: ConfigurationResponse = {
  api_version: 1,
  config: {
    automation_enabled: false,
    acknowledged_time_zone: "America/New_York",
    equipment_group: {
      equipment_group_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    },
  },
  options: {},
  zones: [
    {
      zone_id: ZONE_ID,
      name: "Dining Room",
      temperature_sources: [
        { entity_id: "sensor.dining_room_temperature", enabled: true },
      ],
      humidity_sources: [],
      window_door_entity_ids: [],
      occupancy_entity_ids: [],
      stage_entity_ids: [],
      fan_entity_ids: [],
    },
  ],
  active_repairs: [],
};

export const snapshot: SnapshotResponse = {
  api_version: 1,
  entry_id: ENTRY_ID,
  observation_revision: 8,
  calculated_at_utc: NOW,
  control_state: "observing",
  reason_code: "observe_only",
  zones: [
    {
      zone_id: ZONE_ID,
      effective_temperature_c: 23.7,
      effective_humidity_pct: 50,
      thermostat_hvac_mode: "heat_cool",
      supported_hvac_modes: ["off", "heat", "cool", "heat_cool"],
      supports_single_target: true,
      supports_target_range: true,
      sensor_data_degraded: false,
      thermostat_data_degraded: false,
    },
  ],
};

export const activity: ActivityResponse = {
  api_version: 1,
  total: 2,
  offset: 0,
  order: "newest",
  records: [
    {
      record_id: "record-1",
      zone_id: ZONE_ID,
      timestamp_utc: NOW,
      activity_type: "observation",
      reason_code: "observation_updated",
      severity: "info",
      explanation: "A new valid observation was recorded.",
    },
    {
      record_id: "record-older-repair",
      zone_id: null,
      timestamp_utc: "2026-07-30T18:00:00+00:00",
      activity_type: "repair_issue_created",
      reason_code: "migration_failed",
      severity: "error",
      explanation: "A migration repair was created during an earlier setup.",
    },
  ],
};

export const shadow: ShadowStatusResponse = {
  api_version: 1,
  readiness: {
    ready: false,
    qualification_percent: 42,
    valid_evaluation_percent: 100,
    elapsed_hours: 10,
    evaluated_decisions: 12,
    valid_evaluations: 12,
    minimum_material_transitions: 1,
    blocking_reasons: ["minimum_elapsed_time"],
    blocking_faults: [],
  },
  history: [],
};

export const observation: ObservationStatusResponse = {
  api_version: 1,
  collection_active: true,
  observation_revision: 8,
  calculated_at_utc: NOW,
  usable_temperature_sources: 1,
  degraded_zone_count: 0,
  presentation_history_hours: 48,
  model_ready_history_available: false,
  history_boundary: "Model-ready observation storage begins in Phase 3.",
};

export const timeline: TodayTimelineResponse = {
  api_version: 1,
  entry_id: ENTRY_ID,
  zone_id: ZONE_ID,
  time_zone: "America/New_York",
  local_date: "2026-07-31",
  day_start_utc: "2026-07-31T04:00:00+00:00",
  day_end_utc: "2026-08-01T04:00:00+00:00",
  generated_at_utc: NOW,
  indoor_prediction_available: false,
  capability_statement: "No indoor prediction in Safe Scheduled Control.",
  series: [
    {
      kind: "effective_temperature",
      value_kind: "measured",
      unit: "°C",
      source_quality: "available",
      coverage_start_utc: "2026-07-31T17:00:00+00:00",
      coverage_end_utc: NOW,
      missing_intervals: [],
      samples: [
        { timestamp_utc: "2026-07-31T17:00:00+00:00", value: 23.9 },
        { timestamp_utc: NOW, value: 23.7 },
      ],
    },
    {
      kind: "hvac_action",
      value_kind: "measured",
      unit: null,
      source_quality: "available",
      coverage_start_utc: "2026-07-31T17:00:00+00:00",
      coverage_end_utc: NOW,
      missing_intervals: [],
      samples: [
        { timestamp_utc: "2026-07-31T17:00:00+00:00", value: "idle" },
        { timestamp_utc: NOW, value: "cooling" },
      ],
    },
    {
      kind: "fan_action",
      value_kind: "measured",
      unit: null,
      source_quality: "available",
      coverage_start_utc: "2026-07-31T17:00:00+00:00",
      coverage_end_utc: NOW,
      missing_intervals: [],
      samples: [
        { timestamp_utc: "2026-07-31T17:00:00+00:00", value: "off" },
        { timestamp_utc: NOW, value: "off" },
      ],
    },
  ],
  annotations: [],
};

export const narrative: NarrativeResponse = {
  api_version: 1,
  template_version: 1,
  entry_id: ENTRY_ID,
  zone_id: ZONE_ID,
  control_state: "observing",
  reason_code: "observe_only",
  temperature_c: 23.7,
  hvac_action: "idle",
  scheduled_target_c: null,
  effective_target_c: null,
  next_transition_utc: null,
  source_degraded: false,
  context_forecast_available: false,
  included_categories: ["control", "observation"],
  rendered: "Intelligent Climate is observing only. The zone is 23.7°C.",
};

export const scheduleDocument: ScheduleDocument = {
  schedule_schema_version: 1,
  entry_id: ENTRY_ID,
  equipment_group_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  time_zone: "America/New_York",
  revision: 1,
  zones: {
    [ZONE_ID]: {
      zone_id: ZONE_ID,
      enabled: true,
      selected_profile_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      profiles: [
        {
          profile_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
          name: "Normal",
          enabled: true,
          days: {
            monday: [
              {
                period_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                local_start: "06:30",
                label: "Morning",
                occupancy_label: "home",
                target: {
                  kind: "single",
                  target_c: 21,
                  heat_target_c: null,
                  cool_target_c: null,
                },
                tolerance_c: 0.5,
              },
            ],
            tuesday: [],
            wednesday: [],
            thursday: [],
            friday: [],
            saturday: [],
            sunday: [],
          },
        },
      ],
    },
  },
  saved_at_utc: NOW,
};

export const scheduleGet: ScheduleGetResponse = {
  api_version: 1,
  revision: 1,
  schedule: scheduleDocument,
};

export const scheduleValidation: ScheduleValidationResponse = {
  api_version: 1,
  valid: true,
  revision: 1,
};

export const schedulePreview: SchedulePreviewResponse = {
  api_version: 1,
  authoritative: false,
  at_utc: NOW,
  time_zone: "America/New_York",
  preview_week_start_local: "2026-07-27",
  zones: [
    {
      zone_id: ZONE_ID,
      profile_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
      period_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      target: {
        kind: "single",
        target_c: 21,
        heat_target_c: null,
        cool_target_c: null,
      },
      next_target: null,
      next_boundary_utc: "2026-08-03T10:30:00+00:00",
      next_material_transition_utc: null,
      inherited_from_previous_day: true,
    },
  ],
  dst_warnings: [],
};

export const scheduleSave: ScheduleSaveResponse = {
  api_version: 1,
  revision: 2,
  schedule: { ...scheduleDocument, revision: 2 },
};
