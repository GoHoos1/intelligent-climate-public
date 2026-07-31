import {
  API_VERSION,
  type ActivityRecord,
  type ActivityResponse,
  type ConfigurationResponse,
  type NarrativeResponse,
  type ObservationStatusResponse,
  type ShadowReadiness,
  type ShadowStatusResponse,
  type SnapshotResponse,
  type TimelineAnnotation,
  type TimelineMissingInterval,
  type TimelineSample,
  type TimelineSeries,
  type TimelineValueKind,
  type TodayTimelineResponse,
  type ZoneConfiguration,
  type ZoneSnapshot,
} from "../types/contracts";

export class FrontendContractError extends Error {
  public constructor(path: string, message: string) {
    super(`${path}: ${message}`);
    this.name = "FrontendContractError";
  }
}

type JsonObject = Record<string, unknown>;

const VALUE_KINDS = new Set<TimelineValueKind>([
  "measured",
  "configured",
  "calculated",
  "forecast",
  "predicted",
  "planned",
]);

function object(value: unknown, path: string): JsonObject {
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    throw new FrontendContractError(path, "expected object");
  }
  return value as JsonObject;
}

function array(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) {
    throw new FrontendContractError(path, "expected array");
  }
  return value;
}

function string(value: unknown, path: string): string {
  if (typeof value !== "string" || value.length === 0) {
    throw new FrontendContractError(path, "expected non-empty string");
  }
  return value;
}

function optionalString(value: unknown, path: string): string | null {
  return value === null ? null : string(value, path);
}

function boolean(value: unknown, path: string): boolean {
  if (typeof value !== "boolean") {
    throw new FrontendContractError(path, "expected boolean");
  }
  return value;
}

function number(value: unknown, path: string): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new FrontendContractError(path, "expected finite number");
  }
  return value;
}

function nonNegativeInteger(value: unknown, path: string): number {
  const result = number(value, path);
  if (!Number.isInteger(result) || result < 0) {
    throw new FrontendContractError(path, "expected non-negative integer");
  }
  return result;
}

function nullableNumber(value: unknown, path: string): number | null {
  return value === null ? null : number(value, path);
}

function timestamp(value: unknown, path: string): string {
  const result = string(value, path);
  if (!Number.isFinite(Date.parse(result))) {
    throw new FrontendContractError(path, "expected ISO timestamp");
  }
  return result;
}

function version(root: JsonObject, path: string): void {
  if (root["api_version"] !== API_VERSION) {
    throw new FrontendContractError(
      `${path}.api_version`,
      `expected ${String(API_VERSION)}`,
    );
  }
}

function strings(value: unknown, path: string): string[] {
  return array(value, path).map((item, index) =>
    string(item, `${path}[${String(index)}]`),
  );
}

function zoneConfiguration(value: unknown, path: string): ZoneConfiguration {
  const root = object(value, path);
  return {
    ...root,
    zone_id: string(root["zone_id"], `${path}.zone_id`),
    name: string(root["name"], `${path}.name`),
    temperature_sources: array(
      root["temperature_sources"],
      `${path}.temperature_sources`,
    ),
    humidity_sources: array(
      root["humidity_sources"],
      `${path}.humidity_sources`,
    ),
    window_door_entity_ids: array(
      root["window_door_entity_ids"],
      `${path}.window_door_entity_ids`,
    ),
    occupancy_entity_ids: array(
      root["occupancy_entity_ids"],
      `${path}.occupancy_entity_ids`,
    ),
    fan_entity_ids: array(root["fan_entity_ids"], `${path}.fan_entity_ids`),
  };
}

export function validateConfiguration(value: unknown): ConfigurationResponse {
  const root = object(value, "config");
  version(root, "config");
  return {
    api_version: API_VERSION,
    config: object(root["config"], "config.config"),
    options: object(root["options"], "config.options"),
    zones: array(root["zones"], "config.zones").map((item, index) =>
      zoneConfiguration(item, `config.zones[${String(index)}]`),
    ),
  };
}

function zoneSnapshot(value: unknown, path: string): ZoneSnapshot {
  const root = object(value, path);
  return {
    zone_id: string(root["zone_id"], `${path}.zone_id`),
    effective_temperature_c: nullableNumber(
      root["effective_temperature_c"],
      `${path}.effective_temperature_c`,
    ),
    effective_humidity_pct: nullableNumber(
      root["effective_humidity_pct"],
      `${path}.effective_humidity_pct`,
    ),
    sensor_data_degraded: boolean(
      root["sensor_data_degraded"],
      `${path}.sensor_data_degraded`,
    ),
    thermostat_data_degraded: boolean(
      root["thermostat_data_degraded"],
      `${path}.thermostat_data_degraded`,
    ),
  };
}

export function validateSnapshot(value: unknown): SnapshotResponse {
  const root = object(value, "snapshot");
  version(root, "snapshot");
  return {
    api_version: API_VERSION,
    entry_id: string(root["entry_id"], "snapshot.entry_id"),
    observation_revision: nonNegativeInteger(
      root["observation_revision"],
      "snapshot.observation_revision",
    ),
    calculated_at_utc: timestamp(
      root["calculated_at_utc"],
      "snapshot.calculated_at_utc",
    ),
    control_state: string(root["control_state"], "snapshot.control_state"),
    reason_code: optionalString(root["reason_code"], "snapshot.reason_code"),
    zones: array(root["zones"], "snapshot.zones").map((item, index) =>
      zoneSnapshot(item, `snapshot.zones[${String(index)}]`),
    ),
  };
}

function activityRecord(value: unknown, path: string): ActivityRecord {
  const root = object(value, path);
  return {
    record_id: string(root["record_id"], `${path}.record_id`),
    zone_id: optionalString(root["zone_id"], `${path}.zone_id`),
    timestamp_utc: timestamp(root["timestamp_utc"], `${path}.timestamp_utc`),
    activity_type: string(root["activity_type"], `${path}.activity_type`),
    reason_code: string(root["reason_code"], `${path}.reason_code`),
    severity: string(root["severity"], `${path}.severity`),
    explanation: string(root["explanation"], `${path}.explanation`),
  };
}

export function validateActivity(value: unknown): ActivityResponse {
  const root = object(value, "activity");
  version(root, "activity");
  return {
    api_version: API_VERSION,
    total: nonNegativeInteger(root["total"], "activity.total"),
    offset: nonNegativeInteger(root["offset"], "activity.offset"),
    records: array(root["records"], "activity.records").map((item, index) =>
      activityRecord(item, `activity.records[${String(index)}]`),
    ),
  };
}

function readiness(value: unknown, path: string): ShadowReadiness {
  const root = object(value, path);
  return {
    ready: boolean(root["ready"], `${path}.ready`),
    qualification_percent: number(
      root["qualification_percent"],
      `${path}.qualification_percent`,
    ),
    valid_evaluation_percent: number(
      root["valid_evaluation_percent"],
      `${path}.valid_evaluation_percent`,
    ),
    elapsed_hours: number(root["elapsed_hours"], `${path}.elapsed_hours`),
    evaluated_decisions: nonNegativeInteger(
      root["evaluated_decisions"],
      `${path}.evaluated_decisions`,
    ),
    valid_evaluations: nonNegativeInteger(
      root["valid_evaluations"],
      `${path}.valid_evaluations`,
    ),
    minimum_material_transitions: nonNegativeInteger(
      root["minimum_material_transitions"],
      `${path}.minimum_material_transitions`,
    ),
    blocking_reasons: strings(
      root["blocking_reasons"],
      `${path}.blocking_reasons`,
    ),
    blocking_faults: strings(
      root["blocking_faults"],
      `${path}.blocking_faults`,
    ),
  };
}

export function validateShadowStatus(value: unknown): ShadowStatusResponse {
  const root = object(value, "shadow");
  version(root, "shadow");
  return {
    api_version: API_VERSION,
    readiness:
      root["readiness"] === null
        ? null
        : readiness(root["readiness"], "shadow.readiness"),
    history: array(root["history"], "shadow.history").map((item, index) => {
      const path = `shadow.history[${String(index)}]`;
      const record = object(item, path);
      return {
        safety_evaluation_id: string(
          record["safety_evaluation_id"],
          `${path}.safety_evaluation_id`,
        ),
        evaluated_at_utc: timestamp(
          record["evaluated_at_utc"],
          `${path}.evaluated_at_utc`,
        ),
        outcome: string(record["outcome"], `${path}.outcome`),
        reason_code: string(record["reason_code"], `${path}.reason_code`),
        would_command: boolean(
          record["would_command"],
          `${path}.would_command`,
        ),
      };
    }),
  };
}

export function validateObservationStatus(
  value: unknown,
): ObservationStatusResponse {
  const root = object(value, "observation");
  version(root, "observation");
  if (root["model_ready_history_available"] !== false) {
    throw new FrontendContractError(
      "observation.model_ready_history_available",
      "Phase 2 must not claim model-ready history",
    );
  }
  return {
    api_version: API_VERSION,
    collection_active: boolean(
      root["collection_active"],
      "observation.collection_active",
    ),
    observation_revision: nonNegativeInteger(
      root["observation_revision"],
      "observation.observation_revision",
    ),
    calculated_at_utc: timestamp(
      root["calculated_at_utc"],
      "observation.calculated_at_utc",
    ),
    usable_temperature_sources: nonNegativeInteger(
      root["usable_temperature_sources"],
      "observation.usable_temperature_sources",
    ),
    degraded_zone_count: nonNegativeInteger(
      root["degraded_zone_count"],
      "observation.degraded_zone_count",
    ),
    presentation_history_hours: nonNegativeInteger(
      root["presentation_history_hours"],
      "observation.presentation_history_hours",
    ),
    model_ready_history_available: false,
    history_boundary: string(
      root["history_boundary"],
      "observation.history_boundary",
    ),
  };
}

function missingInterval(
  value: unknown,
  path: string,
): TimelineMissingInterval {
  const root = object(value, path);
  return {
    start_utc: timestamp(root["start_utc"], `${path}.start_utc`),
    end_utc: timestamp(root["end_utc"], `${path}.end_utc`),
  };
}

function timelineSample(value: unknown, path: string): TimelineSample {
  const root = object(value, path);
  const sampleValue = root["value"];
  if (
    (typeof sampleValue !== "string" || sampleValue.length === 0) &&
    (typeof sampleValue !== "number" || !Number.isFinite(sampleValue))
  ) {
    throw new FrontendContractError(
      `${path}.value`,
      "expected finite number or text",
    );
  }
  return {
    timestamp_utc: timestamp(root["timestamp_utc"], `${path}.timestamp_utc`),
    value: sampleValue,
  };
}

function timelineSeries(value: unknown, path: string): TimelineSeries {
  const root = object(value, path);
  const kind = string(root["value_kind"], `${path}.value_kind`);
  if (!VALUE_KINDS.has(kind as TimelineValueKind)) {
    throw new FrontendContractError(
      `${path}.value_kind`,
      "unsupported provenance",
    );
  }
  if (kind === "predicted" || kind === "planned") {
    throw new FrontendContractError(
      `${path}.value_kind`,
      "future Phase 3/4 series are not accepted by the Phase 2 panel",
    );
  }
  return {
    kind: string(root["kind"], `${path}.kind`),
    value_kind: kind as TimelineValueKind,
    unit: optionalString(root["unit"], `${path}.unit`),
    source_quality: string(root["source_quality"], `${path}.source_quality`),
    coverage_start_utc: timestamp(
      root["coverage_start_utc"],
      `${path}.coverage_start_utc`,
    ),
    coverage_end_utc: timestamp(
      root["coverage_end_utc"],
      `${path}.coverage_end_utc`,
    ),
    missing_intervals: array(
      root["missing_intervals"],
      `${path}.missing_intervals`,
    ).map((item, index) =>
      missingInterval(item, `${path}.missing_intervals[${String(index)}]`),
    ),
    samples: array(root["samples"], `${path}.samples`).map((item, index) =>
      timelineSample(item, `${path}.samples[${String(index)}]`),
    ),
  };
}

function annotation(value: unknown, path: string): TimelineAnnotation {
  const root = object(value, path);
  return {
    annotation_id: string(root["annotation_id"], `${path}.annotation_id`),
    timestamp_utc: timestamp(root["timestamp_utc"], `${path}.timestamp_utc`),
    reason_code: string(root["reason_code"], `${path}.reason_code`),
    activity_record_id: string(
      root["activity_record_id"],
      `${path}.activity_record_id`,
    ),
  };
}

export function validateTodayTimeline(value: unknown): TodayTimelineResponse {
  const root = object(value, "timeline");
  version(root, "timeline");
  if (root["indoor_prediction_available"] !== false) {
    throw new FrontendContractError(
      "timeline.indoor_prediction_available",
      "Phase 2 must not claim indoor prediction",
    );
  }
  return {
    api_version: API_VERSION,
    entry_id: string(root["entry_id"], "timeline.entry_id"),
    zone_id: string(root["zone_id"], "timeline.zone_id"),
    time_zone: string(root["time_zone"], "timeline.time_zone"),
    local_date: string(root["local_date"], "timeline.local_date"),
    day_start_utc: timestamp(root["day_start_utc"], "timeline.day_start_utc"),
    day_end_utc: timestamp(root["day_end_utc"], "timeline.day_end_utc"),
    generated_at_utc: timestamp(
      root["generated_at_utc"],
      "timeline.generated_at_utc",
    ),
    indoor_prediction_available: false,
    capability_statement: string(
      root["capability_statement"],
      "timeline.capability_statement",
    ),
    series: array(root["series"], "timeline.series").map((item, index) =>
      timelineSeries(item, `timeline.series[${String(index)}]`),
    ),
    annotations: array(root["annotations"], "timeline.annotations").map(
      (item, index) =>
        annotation(item, `timeline.annotations[${String(index)}]`),
    ),
  };
}

export function validateNarrative(value: unknown): NarrativeResponse {
  const root = object(value, "narrative");
  version(root, "narrative");
  return {
    api_version: API_VERSION,
    template_version: nonNegativeInteger(
      root["template_version"],
      "narrative.template_version",
    ),
    entry_id: string(root["entry_id"], "narrative.entry_id"),
    zone_id: string(root["zone_id"], "narrative.zone_id"),
    control_state: string(root["control_state"], "narrative.control_state"),
    reason_code: string(root["reason_code"], "narrative.reason_code"),
    temperature_c: nullableNumber(
      root["temperature_c"],
      "narrative.temperature_c",
    ),
    hvac_action: optionalString(root["hvac_action"], "narrative.hvac_action"),
    scheduled_target_c: nullableNumber(
      root["scheduled_target_c"],
      "narrative.scheduled_target_c",
    ),
    effective_target_c: nullableNumber(
      root["effective_target_c"],
      "narrative.effective_target_c",
    ),
    next_transition_utc:
      root["next_transition_utc"] === null
        ? null
        : timestamp(
            root["next_transition_utc"],
            "narrative.next_transition_utc",
          ),
    source_degraded: boolean(
      root["source_degraded"],
      "narrative.source_degraded",
    ),
    context_forecast_available: boolean(
      root["context_forecast_available"],
      "narrative.context_forecast_available",
    ),
    included_categories: strings(
      root["included_categories"],
      "narrative.included_categories",
    ),
    rendered: string(root["rendered"], "narrative.rendered"),
  };
}
