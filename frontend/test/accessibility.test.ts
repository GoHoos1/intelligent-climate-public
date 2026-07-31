import { describe, expect, it } from "vitest";

import {
  formatTemperature,
  formatTimestamp,
  statusSemantics,
} from "../src/accessibility/semantics";

describe("accessibility and locale primitives", () => {
  it("gives every state a text label and non-color icon", () => {
    for (const state of [
      "observing",
      "manual_idle",
      "shadow_qualifying",
      "shadow_ready",
      "safe_fallback",
      "emergency_paused",
      "unknown_state",
    ]) {
      const semantics = statusSemantics(state);
      expect(semantics.label.length).toBeGreaterThan(0);
      expect(semantics.icon.length).toBeGreaterThan(0);
    }
    expect(statusSemantics("observing").automationOff).toBe(true);
  });

  it("formats temperature in the HA unit without inventing zero", () => {
    expect(formatTemperature(0, "°F", "en-US")).toBe("32°F");
    expect(formatTemperature(23.7, "°C", "en-US")).toBe("23.7°C");
    expect(formatTemperature(null, "°F", "en-US")).toBe("Unavailable");
  });

  it("formats UTC instants in the requested time zone", () => {
    expect(
      formatTimestamp("2026-07-31T18:00:00Z", "en-US", "America/New_York"),
    ).toContain("2:00 PM");
  });
});
