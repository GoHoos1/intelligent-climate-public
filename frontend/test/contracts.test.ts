import { describe, expect, it } from "vitest";

import {
  FrontendContractError,
  validateActivity,
  validateConfiguration,
  validateNarrative,
  validateObservationStatus,
  validateScheduleGet,
  validateSchedulePreview,
  validateScheduleSave,
  validateScheduleValidation,
  validateShadowStatus,
  validateSnapshot,
  validateTodayTimeline,
} from "../src/api/validate";
import {
  activity,
  configuration,
  narrative,
  observation,
  shadow,
  scheduleGet,
  scheduleDocument,
  schedulePreview,
  scheduleSave,
  scheduleValidation,
  snapshot,
  timeline,
} from "./fixtures";

describe("frontend schema contracts", () => {
  it("accepts every canonical Task 20 read payload", () => {
    expect(validateConfiguration(configuration)).toEqual(configuration);
    expect(validateSnapshot(snapshot)).toEqual(snapshot);
    expect(validateActivity(activity)).toEqual(activity);
    expect(validateShadowStatus(shadow)).toEqual(shadow);
    expect(validateObservationStatus(observation)).toEqual(observation);
    expect(validateTodayTimeline(timeline)).toEqual(timeline);
    expect(validateNarrative(narrative)).toEqual(narrative);
    expect(validateScheduleGet(scheduleGet)).toEqual(scheduleGet);
    expect(validateScheduleValidation(scheduleValidation)).toEqual(
      scheduleValidation,
    );
    expect(validateSchedulePreview(schedulePreview)).toEqual(schedulePreview);
    expect(validateScheduleSave(scheduleSave)).toEqual(scheduleSave);
  });

  it("fails closed on malformed schedule documents and preview authority", () => {
    expect(() =>
      validateScheduleGet({
        ...scheduleGet,
        schedule: { ...scheduleGet.schedule, schedule_schema_version: 2 },
      }),
    ).toThrow("schedule_schema_version");
    const incompleteDays = structuredClone(scheduleDocument);
    const zone = Object.values(incompleteDays.zones)[0];
    const profile = zone?.profiles[0];
    if (profile === undefined) throw new Error("fixture profile is missing");
    profile.days = {
      monday: [],
    } as never;
    expect(() =>
      validateScheduleGet({ ...scheduleGet, schedule: incompleteDays }),
    ).toThrow("tuesday");
    expect(() =>
      validateSchedulePreview({ ...schedulePreview, authoritative: true }),
    ).toThrow("nonauthoritative");
    expect(() =>
      validateSchedulePreview({
        ...schedulePreview,
        dst_warnings: [
          {
            zone_id: "zone",
            profile_id: "profile",
            period_id: "period",
            local_date: "2026-03-08",
            local_start: "2:30",
            kind: "gap",
            occurs_at_utc: "2026-03-08T07:00:00Z",
            explanation: "Shifted once.",
          },
        ],
      }),
    ).toThrow("HH:MM");
  });

  it("fails closed on version drift and malformed primitives", () => {
    expect(() => validateSnapshot({ ...snapshot, api_version: 2 })).toThrow(
      FrontendContractError,
    );
    expect(() =>
      validateSnapshot({
        ...snapshot,
        zones: [{ ...snapshot.zones[0], effective_temperature_c: Number.NaN }],
      }),
    ).toThrow("finite number");
    expect(() =>
      validateActivity({ ...activity, records: "not-a-list" }),
    ).toThrow("expected array");
    expect(() =>
      validateActivity({
        ...activity,
        records: [
          {
            ...activity.records[0],
            detail: { entity_id: "climate.private" },
          },
        ],
      }),
    ).toThrow("unexpected detail field");
    expect(() =>
      validateActivity({
        ...activity,
        records: [
          { ...activity.records[0], detail: { new_quality: ["valid"] } },
        ],
      }),
    ).toThrow("expected scalar detail");
    expect(() =>
      validateActivity({
        ...activity,
        records: [
          {
            ...activity.records[0],
            detail: { new_target_temperature_c: Number.NaN },
          },
        ],
      }),
    ).toThrow("expected finite detail");
    expect(() => validateActivity({ ...activity, order: "sideways" })).toThrow(
      "expected newest or oldest",
    );
    expect(
      validateActivity({
        ...activity,
        records: [
          {
            ...activity.records[0],
            detail: {
              previous_target_temperature_c: null,
              new_target_temperature_c: 22,
              new_state: true,
            },
          },
        ],
      }).records[0]?.detail,
    ).toEqual({
      previous_target_temperature_c: null,
      new_target_temperature_c: 22,
      new_state: true,
    });
    expect(() => validateSnapshot(null)).toThrow("expected object");
    expect(() =>
      validateSnapshot({ ...snapshot, observation_revision: -1 }),
    ).toThrow("non-negative integer");
    expect(() =>
      validateSnapshot({ ...snapshot, calculated_at_utc: "not-a-date" }),
    ).toThrow("ISO timestamp");
    expect(() =>
      validateSnapshot({
        ...snapshot,
        zones: [{ ...snapshot.zones[0], sensor_data_degraded: "no" }],
      }),
    ).toThrow("expected boolean");
    expect(() =>
      validateSnapshot({
        ...snapshot,
        zones: [{ ...snapshot.zones[0], supported_hvac_modes: "heat" }],
      }),
    ).toThrow("expected array");
    expect(() =>
      validateSnapshot({
        ...snapshot,
        zones: [{ ...snapshot.zones[0], supports_target_range: "yes" }],
      }),
    ).toThrow("expected boolean");
    expect(() =>
      validateConfiguration({
        ...configuration,
        zones: [{ ...configuration.zones[0], temperature_sources: null }],
      }),
    ).toThrow("expected array");
  });

  it("rejects false Phase 2 prediction and model-readiness claims", () => {
    expect(() =>
      validateObservationStatus({
        ...observation,
        model_ready_history_available: true,
      }),
    ).toThrow("must not claim model-ready history");
    expect(() =>
      validateTodayTimeline({ ...timeline, indoor_prediction_available: true }),
    ).toThrow("must not claim indoor prediction");
    expect(() =>
      validateTodayTimeline({
        ...timeline,
        series: [{ ...timeline.series[0], value_kind: "predicted" }],
      }),
    ).toThrow("future Phase 3/4 series");
  });

  it("accepts nullable readiness and complete history/detail records", () => {
    expect(
      validateShadowStatus({ ...shadow, readiness: null }).readiness,
    ).toBeNull();
    expect(
      validateShadowStatus({
        ...shadow,
        history: [
          {
            safety_evaluation_id: "evaluation-1",
            evaluated_at_utc: "2026-07-31T18:00:00Z",
            outcome: "recorded",
            reason_code: "shadow_recorded",
            would_command: true,
            command: {
              kind: "climate_target",
              target_c: 25,
              heat_target_c: null,
              cool_target_c: null,
              hvac_mode: "cool",
              fan_mode: null,
              cause: "schedule",
            },
          },
        ],
      }).history,
    ).toHaveLength(1);

    const detailedTimeline = {
      ...timeline,
      series: [
        {
          ...timeline.series[0],
          unit: null,
          missing_intervals: [
            {
              start_utc: "2026-07-31T17:10:00Z",
              end_utc: "2026-07-31T17:40:00Z",
            },
          ],
          samples: [
            { timestamp_utc: "2026-07-31T17:00:00Z", value: "cooling" },
          ],
        },
      ],
      annotations: [
        {
          annotation_id: "annotation-1",
          timestamp_utc: "2026-07-31T17:00:00Z",
          reason_code: "observation_updated",
          activity_record_id: "record-1",
        },
      ],
    };
    expect(validateTodayTimeline(detailedTimeline).annotations).toHaveLength(1);
    expect(
      validateNarrative({
        ...narrative,
        hvac_action: null,
        scheduled_target_c: 22,
        effective_target_c: 23,
        next_transition_utc: "2026-07-31T20:00:00Z",
      }).next_transition_utc,
    ).toBe("2026-07-31T20:00:00Z");
  });

  it("rejects malformed detailed timeline and narrative values", () => {
    expect(() =>
      validateTodayTimeline({
        ...timeline,
        series: [{ ...timeline.series[0], value_kind: "invented" }],
      }),
    ).toThrow("unsupported provenance");
    expect(() =>
      validateTodayTimeline({
        ...timeline,
        series: [
          {
            ...timeline.series[0],
            samples: [{ timestamp_utc: "2026-07-31T18:00:00Z", value: false }],
          },
        ],
      }),
    ).toThrow("finite number or text");
    expect(() => validateNarrative({ ...narrative, rendered: "" })).toThrow(
      "non-empty string",
    );
  });
});
