import { describe, expect, it, vi } from "vitest";

import { IntelligentClimateClient } from "../src/api/client";
import type { HomeAssistantLike } from "../src/types/home-assistant";
import {
  ENTRY_ID,
  activity,
  configuration,
  observation,
  shadow,
  scheduleDocument,
  scheduleGet,
  schedulePreview,
  scheduleSave,
  scheduleValidation,
  snapshot,
  narrative,
  timeline,
} from "./fixtures";

function createHass(): {
  hass: HomeAssistantLike;
  callWSMock: ReturnType<typeof vi.fn>;
  callServiceMock: ReturnType<typeof vi.fn>;
} {
  const responses: Record<string, unknown> = {
    "intelligent_climate/config/get": configuration,
    "intelligent_climate/snapshot/get": snapshot,
    "intelligent_climate/activity/list": activity,
    "intelligent_climate/shadow/status": shadow,
    "intelligent_climate/observation/status": observation,
    "intelligent_climate/timeline/today": timeline,
    "intelligent_climate/narrative/current": narrative,
    "intelligent_climate/schedule/get": scheduleGet,
    "intelligent_climate/schedule/validate": scheduleValidation,
    "intelligent_climate/schedule/preview": schedulePreview,
    "intelligent_climate/schedule/save": scheduleSave,
  };
  const callWSMock = vi.fn((message: Record<string, unknown>) =>
    Promise.resolve(responses[String(message["type"])]),
  );
  const callWS: HomeAssistantLike["callWS"] = <T>(
    message: Record<string, unknown>,
  ) => callWSMock(message) as Promise<T>;
  const callServiceMock = vi.fn(() => Promise.resolve());
  return {
    callWSMock,
    callServiceMock,
    hass: {
      callWS,
      callService: callServiceMock,
      connection: { subscribeMessage: () => Promise.resolve(vi.fn()) },
      locale: { language: "en-US" },
      config: { unit_system: { temperature: "°F" } },
    },
  };
}

describe("IntelligentClimateClient", () => {
  it("adds the fixed version and entry to every read", async () => {
    const { hass, callWSMock } = createHass();
    const result = await new IntelligentClimateClient(
      hass,
      ENTRY_ID,
    ).dashboardData();
    expect(result.snapshot).toEqual(snapshot);
    expect(callWSMock).toHaveBeenCalledTimes(5);
    expect(callWSMock).toHaveBeenCalledWith(
      expect.objectContaining({ api_version: 1, entry_id: ENTRY_ID }),
    );
  });

  it("validates subscription events and returns owned cleanup", async () => {
    const { hass } = createHass();
    const cleanup = vi.fn();
    let send: ((message: unknown) => void) | undefined;
    hass.connection.subscribeMessage = (callback) => {
      send = callback;
      return Promise.resolve(cleanup);
    };
    const listener = vi.fn();
    const unsubscribe = await new IntelligentClimateClient(
      hass,
      ENTRY_ID,
    ).subscribe(listener);
    send?.(snapshot);
    expect(listener).toHaveBeenCalledWith(snapshot);
    unsubscribe();
    expect(cleanup).toHaveBeenCalledOnce();
  });

  it("loads zone detail and forwards bounded activity pagination", async () => {
    const { hass, callWSMock } = createHass();
    const client = new IntelligentClimateClient(hass, ENTRY_ID);
    expect(await client.todayTimeline("zone-1")).toEqual(timeline);
    expect(await client.narrative("zone-1")).toEqual(narrative);
    expect(await client.activity(10, 25)).toEqual(activity);
    expect(callWSMock).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "intelligent_climate/activity/list",
        offset: 10,
        limit: 25,
        order: "newest",
      }),
    );
  });

  it("rejects malformed subscription events before notifying the panel", async () => {
    const { hass } = createHass();
    let send: ((message: unknown) => void) | undefined;
    hass.connection.subscribeMessage = (callback) => {
      send = callback;
      return Promise.resolve(vi.fn());
    };
    const listener = vi.fn();
    await new IntelligentClimateClient(hass, ENTRY_ID).subscribe(listener);
    expect(() => send?.({ ...snapshot, api_version: 2 })).toThrow(
      "snapshot.api_version",
    );
    expect(listener).not.toHaveBeenCalled();
  });

  it("rejects an empty entry identifier", () => {
    expect(() => new IntelligentClimateClient(createHass().hass, "")).toThrow(
      "entryId is required",
    );
  });

  it("validates, previews, and saves complete schedules with revision evidence", async () => {
    const { hass, callWSMock } = createHass();
    const client = new IntelligentClimateClient(hass, ENTRY_ID);

    expect(await client.schedule()).toEqual(scheduleGet);
    expect(await client.validateSchedule(scheduleDocument)).toEqual(
      scheduleValidation,
    );
    expect(
      await client.previewSchedule(scheduleDocument, "2026-07-31T18:00:00Z"),
    ).toEqual(schedulePreview);
    expect(await client.saveSchedule(scheduleDocument, 1)).toEqual(
      scheduleSave,
    );
    expect(callWSMock).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "intelligent_climate/schedule/save",
        expected_revision: 1,
        schedule: scheduleDocument,
      }),
    );
  });

  it("uses the explicit zero-command service for operating-mode changes", async () => {
    const { hass, callServiceMock } = createHass();
    await new IntelligentClimateClient(hass, ENTRY_ID).setOperatingMode(
      "scheduled_shadow",
    );
    expect(callServiceMock).toHaveBeenCalledWith(
      "intelligent_climate",
      "set_operating_mode",
      { entry_id: ENTRY_ID, mode: "scheduled_shadow" },
    );
  });
});
