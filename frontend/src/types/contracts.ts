export const API_VERSION = 1 as const;

export interface ZoneConfiguration {
  zone_id: string;
  name: string;
  temperature_sources: unknown[];
  humidity_sources: unknown[];
  window_door_entity_ids: unknown[];
  occupancy_entity_ids: unknown[];
  fan_entity_ids: unknown[];
  [key: string]: unknown;
}

export interface ConfigurationResponse {
  api_version: typeof API_VERSION;
  config: Record<string, unknown>;
  options: Record<string, unknown>;
  zones: ZoneConfiguration[];
}

export interface ZoneSnapshot {
  zone_id: string;
  effective_temperature_c: number | null;
  effective_humidity_pct: number | null;
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
}

export interface ActivityResponse {
  api_version: typeof API_VERSION;
  total: number;
  offset: number;
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
}

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
