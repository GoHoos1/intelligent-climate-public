export const API_VERSION = 1 as const;

export interface ConfiguredSource {
  entity_id: string;
  enabled: boolean;
}

export interface ReviewedBinding {
  entity_id: string;
  enabled: boolean;
  reviewed: boolean;
}

export interface ZoneConfiguration {
  zone_id: string;
  name: string;
  temperature_sources: ConfiguredSource[];
  humidity_sources: ConfiguredSource[];
  window_door_entity_ids: ReviewedBinding[];
  occupancy_entity_ids: ReviewedBinding[];
  stage_entity_ids: string[];
  fan_entity_ids: ReviewedBinding[];
  [key: string]: unknown;
}

export interface ConfigurationResponse {
  api_version: typeof API_VERSION;
  config: Record<string, unknown>;
  options: Record<string, unknown>;
  active_repairs: string[];
  zones: ZoneConfiguration[];
}

export interface ZoneSnapshot {
  zone_id: string;
  effective_temperature_c: number | null;
  effective_humidity_pct: number | null;
  thermostat_hvac_mode: string | null;
  supported_hvac_modes: string[];
  supports_single_target: boolean;
  supports_target_range: boolean;
  sensor_data_degraded: boolean;
  thermostat_data_degraded: boolean;
}

export interface SnapshotResponse {
  api_version: typeof API_VERSION;
  entry_id: string;
  observation_revision: number;
  calculated_at_utc: string;
  control_state: string;
  reason_code: string | null;
  zones: ZoneSnapshot[];
}

export interface ActivityRecord {
  record_id: string;
  zone_id: string | null;
  timestamp_utc: string;
  activity_type: string;
  reason_code: string;
  severity: string;
  explanation: string;
  detail: Record<string, string | number | boolean | null>;
}

export interface ActivityResponse {
  api_version: typeof API_VERSION;
  total: number;
  offset: number;
  order: "newest" | "oldest";
  records: ActivityRecord[];
}

export interface ShadowReadiness {
  ready: boolean;
  qualification_percent: number;
  valid_evaluation_percent: number;
  elapsed_hours: number;
  evaluated_decisions: number;
  valid_evaluations: number;
  minimum_material_transitions: number;
  blocking_reasons: string[];
  blocking_faults: string[];
}

export interface ShadowHistoryRecord {
  safety_evaluation_id: string;
  evaluated_at_utc: string;
  outcome: string;
  reason_code: string;
  would_command: boolean;
  command: ShadowCommand | null;
}

export interface ShadowCommand {
  kind: string;
  target_c: number | null;
  heat_target_c: number | null;
  cool_target_c: number | null;
  hvac_mode: string | null;
  fan_mode: string | null;
  cause: string;
}

export type ZeroCommandOperatingMode =
  "observe_only" | "manual_control" | "scheduled_shadow";

export interface ShadowStatusResponse {
  api_version: typeof API_VERSION;
  readiness: ShadowReadiness | null;
  history: ShadowHistoryRecord[];
}

export interface ObservationStatusResponse {
  api_version: typeof API_VERSION;
  collection_active: boolean;
  observation_revision: number;
  calculated_at_utc: string;
  usable_temperature_sources: number;
  degraded_zone_count: number;
  presentation_history_hours: number;
  model_ready_history_available: false;
  history_boundary: string;
}

export type TimelineValueKind =
  | "measured"
  | "configured"
  | "calculated"
  | "forecast"
  | "predicted"
  | "planned";

export interface TimelineSample {
  timestamp_utc: string;
  value: number | string;
}

export interface TimelineMissingInterval {
  start_utc: string;
  end_utc: string;
}

export interface TimelineSeries {
  kind: string;
  value_kind: TimelineValueKind;
  unit: string | null;
  source_quality: string;
  coverage_start_utc: string;
  coverage_end_utc: string;
  missing_intervals: TimelineMissingInterval[];
  samples: TimelineSample[];
}

export interface TimelineAnnotation {
  annotation_id: string;
  timestamp_utc: string;
  reason_code: string;
  activity_record_id: string;
}

export interface TodayTimelineResponse {
  api_version: typeof API_VERSION;
  entry_id: string;
  zone_id: string;
  time_zone: string;
  local_date: string;
  day_start_utc: string;
  day_end_utc: string;
  generated_at_utc: string;
  indoor_prediction_available: false;
  capability_statement: string;
  series: TimelineSeries[];
  annotations: TimelineAnnotation[];
}

export interface NarrativeResponse {
  api_version: typeof API_VERSION;
  template_version: number;
  entry_id: string;
  zone_id: string;
  control_state: string;
  reason_code: string;
  temperature_c: number | null;
  hvac_action: string | null;
  scheduled_target_c: number | null;
  effective_target_c: number | null;
  next_transition_utc: string | null;
  source_degraded: boolean;
  context_forecast_available: boolean;
  included_categories: string[];
  rendered: string;
}

export interface EntryDashboardData {
  configuration: ConfigurationResponse;
  snapshot: SnapshotResponse;
  activity: ActivityResponse;
  shadow: ShadowStatusResponse;
  observation: ObservationStatusResponse;
}

export type ScheduleWeekday =
  | "monday"
  | "tuesday"
  | "wednesday"
  | "thursday"
  | "friday"
  | "saturday"
  | "sunday";

export type ScheduleOccupancyLabel =
  "none" | "home" | "away" | "sleep" | "vacation" | "guest" | "custom";

export interface ScheduleTarget {
  kind: "single" | "range";
  target_c: number | null;
  heat_target_c: number | null;
  cool_target_c: number | null;
}

export interface SchedulePeriod {
  period_id: string;
  local_start: string;
  label: string;
  occupancy_label: ScheduleOccupancyLabel;
  target: ScheduleTarget;
  tolerance_c: number;
}

export interface ScheduleProfile {
  profile_id: string;
  name: string;
  enabled: boolean;
  days: Record<ScheduleWeekday, SchedulePeriod[]>;
}

export interface ZoneSchedule {
  zone_id: string;
  enabled: boolean;
  selected_profile_id: string;
  profiles: ScheduleProfile[];
}

export interface ScheduleDocument {
  schedule_schema_version: 1;
  entry_id: string;
  equipment_group_id: string;
  time_zone: string;
  revision: number;
  zones: Record<string, ZoneSchedule>;
  saved_at_utc: string;
}

export interface ScheduleGetResponse {
  api_version: typeof API_VERSION;
  revision: number;
  schedule: ScheduleDocument | null;
}

export interface ScheduleValidationResponse {
  api_version: typeof API_VERSION;
  valid: true;
  revision: number;
}

export interface SchedulePreviewZone {
  zone_id: string;
  profile_id: string;
  period_id: string;
  target: ScheduleTarget;
  next_target: ScheduleTarget | null;
  next_boundary_utc: string;
  next_material_transition_utc: string | null;
  inherited_from_previous_day: boolean;
}

export interface ScheduleDstWarning {
  zone_id: string;
  profile_id: string;
  period_id: string;
  local_date: string;
  local_start: string;
  kind: "gap" | "fold";
  occurs_at_utc: string;
  explanation: string;
}

export interface SchedulePreviewResponse {
  api_version: typeof API_VERSION;
  authoritative: false;
  at_utc: string;
  time_zone: string;
  preview_week_start_local: string;
  zones: SchedulePreviewZone[];
  dst_warnings: ScheduleDstWarning[];
}

export interface ScheduleSaveResponse {
  api_version: typeof API_VERSION;
  revision: number;
  schedule: ScheduleDocument;
}
