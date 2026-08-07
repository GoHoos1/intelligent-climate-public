import { describe, expect, it } from "vitest";

import "../src/components/today-timeline";
import { NOW, timeline } from "./fixtures";

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

describe("accessible Today timeline", () => {
  it("renders provenance with non-color line styles and a data table", async () => {
    const element = document.createElement("ic-today-timeline");
    element.timeline = timeline;
    element.locale = "en-US";
    element.temperatureUnit = "°F";
    document.body.append(element);
    await element.updateComplete;
    const root = element.shadowRoot;
    const measuredPath = root?.querySelector("path.series.measured");
    expect(measuredPath).not.toBeNull();
    expect(measuredPath?.getAttribute("d")).toMatch(/^M .+ L /);
    expect(root?.querySelectorAll("circle.measured-temperature")).toHaveLength(
      2,
    );
    expect(
      [...(root?.querySelectorAll("path, circle, line, text") ?? [])].every(
        (node) => node.namespaceURI === SVG_NAMESPACE,
      ),
    ).toBe(true);
    expect(root?.textContent).toContain("Indoor temperature");
    expect(root?.textContent).toContain("measured");
    expect(root?.textContent).toContain("74.7°F");
    expect(root?.querySelectorAll(".y-axis-labels text")).toHaveLength(5);
    expect(
      root?.querySelectorAll(".axis-labels text").length,
    ).toBeGreaterThanOrEqual(4);
    expect(root?.textContent).toContain("Source: effective zone temperature");
    expect(root?.textContent).toContain("Heating");
    expect(root?.textContent).toContain("Cooling");
    expect(root?.textContent).toContain("Air handler");
    expect(root?.textContent).toContain(
      "Derived from actual thermostat operation",
    );
    expect(root?.textContent).toContain("Fan only");
    expect(root?.querySelectorAll(".lane-row")).toHaveLength(4);
    expect(root?.querySelector("table caption")?.textContent).toContain(
      "Latest factual value",
    );
    element.remove();
  });

  it("shows scheduled heat and cool steps with aligned context lanes", async () => {
    const element = document.createElement("ic-today-timeline");
    const samples = [
      { timestamp_utc: "2026-07-31T17:00:00+00:00", value: 20.5 },
      { timestamp_utc: "2026-07-31T18:00:00+00:00", value: 20.5 },
    ];
    element.timeline = {
      ...timeline,
      series: [
        ...timeline.series,
        {
          kind: "scheduled_heat_target",
          value_kind: "configured",
          unit: "°C",
          source_quality: "available",
          coverage_start_utc: samples[0]?.timestamp_utc ?? NOW,
          coverage_end_utc: samples[1]?.timestamp_utc ?? NOW,
          missing_intervals: [],
          samples,
        },
        {
          kind: "scheduled_cool_target",
          value_kind: "configured",
          unit: "°C",
          source_quality: "available",
          coverage_start_utc: samples[0]?.timestamp_utc ?? NOW,
          coverage_end_utc: samples[1]?.timestamp_utc ?? NOW,
          missing_intervals: [],
          samples: samples.map((sample) => ({ ...sample, value: 24 })),
        },
        {
          kind: "effective_heat_target",
          value_kind: "calculated",
          unit: "°C",
          source_quality: "available",
          coverage_start_utc: samples[0]?.timestamp_utc ?? NOW,
          coverage_end_utc: samples[1]?.timestamp_utc ?? NOW,
          missing_intervals: [],
          samples,
        },
        {
          kind: "effective_cool_target",
          value_kind: "calculated",
          unit: "°C",
          source_quality: "available",
          coverage_start_utc: samples[0]?.timestamp_utc ?? NOW,
          coverage_end_utc: samples[1]?.timestamp_utc ?? NOW,
          missing_intervals: [],
          samples: samples.map((sample, index) => ({
            ...sample,
            value: index === 0 ? 24 : 23.5,
          })),
        },
        {
          kind: "contact_state",
          value_kind: "measured",
          unit: null,
          source_quality: "available",
          coverage_start_utc: "2026-07-31T17:00:00+00:00",
          coverage_end_utc: NOW,
          missing_intervals: [],
          samples: [
            { timestamp_utc: "2026-07-31T17:00:00+00:00", value: "closed" },
            { timestamp_utc: "2026-07-31T17:30:00+00:00", value: "open" },
            { timestamp_utc: NOW, value: "open" },
          ],
        },
        {
          kind: "control_context",
          value_kind: "calculated",
          unit: null,
          source_quality: "available",
          coverage_start_utc: "2026-07-31T17:00:00+00:00",
          coverage_end_utc: NOW,
          missing_intervals: [],
          samples: [
            { timestamp_utc: "2026-07-31T17:00:00+00:00", value: "normal" },
            {
              timestamp_utc: "2026-07-31T17:35:00+00:00",
              value: "window_suspended",
            },
            { timestamp_utc: NOW, value: "window_suspended" },
          ],
        },
      ],
    };
    document.body.append(element);
    await element.updateComplete;

    const root = element.shadowRoot;
    expect(root?.querySelector("path.scheduled_heat_target")).not.toBeNull();
    expect(root?.querySelector("path.scheduled_cool_target")).not.toBeNull();
    expect(root?.querySelector("path.effective_heat_target")).toBeNull();
    expect(root?.querySelector("path.effective_cool_target")).not.toBeNull();
    expect(root?.textContent).toContain("Window / door");
    expect(root?.textContent).toContain("Control context");
    expect(root?.querySelectorAll(".lane-segment.contact.open")).toHaveLength(
      1,
    );
    expect(
      root?.querySelectorAll(".lane-segment.context.window_suspended"),
    ).toHaveLength(1);
    element.remove();
  });

  it("omits dots from dense history while preserving the measured line", async () => {
    const element = document.createElement("ic-today-timeline");
    element.timeline = {
      ...timeline,
      series: timeline.series.map((series) =>
        series.kind === "effective_temperature"
          ? {
              ...series,
              samples: Array.from({ length: 24 }, (_, index) => ({
                timestamp_utc: new Date(
                  Date.parse("2026-07-31T16:00:00+00:00") + index * 5 * 60_000,
                ).toISOString(),
                value: 23.5 + index / 100,
              })),
            }
          : series,
      ),
    };
    document.body.append(element);
    await element.updateComplete;

    expect(
      element.shadowRoot?.querySelector("path.effective_temperature"),
    ).not.toBeNull();
    expect(
      element.shadowRoot?.querySelectorAll("circle.measured-temperature"),
    ).toHaveLength(0);
    element.remove();
  });

  it("keeps a flat three-sample five-minute trace visible", async () => {
    const element = document.createElement("ic-today-timeline");
    element.timeline = {
      ...timeline,
      series: timeline.series.map((series) =>
        series.kind === "effective_temperature"
          ? {
              ...series,
              samples: [
                {
                  timestamp_utc: "2026-07-31T17:00:00+00:00",
                  value: 24.4,
                },
                {
                  timestamp_utc: "2026-07-31T17:05:00+00:00",
                  value: 24.4,
                },
                {
                  timestamp_utc: "2026-07-31T17:10:00+00:00",
                  value: 24.4,
                },
              ],
            }
          : series,
      ),
    };
    document.body.append(element);
    await element.updateComplete;

    const root = element.shadowRoot;
    const path = root?.querySelector("path.effective_temperature");
    const pathData = path?.getAttribute("d") ?? "";
    expect(pathData.match(/ L /g)).toHaveLength(2);
    expect(pathData).toBe("M 302.50 92.50 L 525.00 92.50 L 747.50 92.50");
    expect(root?.querySelectorAll("circle.measured-temperature")).toHaveLength(
      3,
    );
    expect(root?.querySelector("svg")?.getAttribute("viewBox")).toBe(
      "0 0 1000 210",
    );
    expect(root?.querySelector(".axis-labels")?.textContent).toContain(
      "1:05 PM",
    );
    element.remove();
  });

  it("uses clock-aligned ticks without turning the latest sample into a tick", async () => {
    const element = document.createElement("ic-today-timeline");
    element.timeline = {
      ...timeline,
      generated_at_utc: "2026-07-31T19:50:00+00:00",
      series: timeline.series.map((series) =>
        series.kind === "effective_temperature"
          ? {
              ...series,
              samples: [
                {
                  timestamp_utc: "2026-07-31T04:00:00+00:00",
                  value: 23.9,
                },
                {
                  timestamp_utc: "2026-07-31T19:50:00+00:00",
                  value: 23.7,
                },
              ],
            }
          : series,
      ),
    };
    document.body.append(element);
    await element.updateComplete;

    const labels = [
      ...(element.shadowRoot?.querySelectorAll(".axis-labels text") ?? []),
    ].map((node) => node.textContent.trim());
    expect(labels).toEqual([
      "12 AM",
      "2 AM",
      "4 AM",
      "6 AM",
      "8 AM",
      "10 AM",
      "12 PM",
      "2 PM",
    ]);
    expect(labels).not.toContain("3:50 PM");
    element.remove();
  });

  it.each([
    {
      name: "spring-forward",
      start: "2026-03-08T05:00:00+00:00",
      end: "2026-03-09T04:00:00+00:00",
      missing: "2 AM",
    },
    {
      name: "fall-back",
      start: "2026-11-01T04:00:00+00:00",
      end: "2026-11-02T05:00:00+00:00",
      missing: null,
    },
  ])(
    "keeps clock ticks aligned on a $name day",
    async ({ start, end, missing }) => {
      const element = document.createElement("ic-today-timeline");
      element.timeline = {
        ...timeline,
        day_start_utc: start,
        day_end_utc: end,
        series: timeline.series.map((series) =>
          series.kind === "effective_temperature"
            ? {
                ...series,
                samples: [
                  { timestamp_utc: start, value: 23.9 },
                  {
                    timestamp_utc: new Date(
                      Date.parse(end) - 60_000,
                    ).toISOString(),
                    value: 23.7,
                  },
                ],
              }
            : series,
        ),
      };
      document.body.append(element);
      await element.updateComplete;

      const labels = [
        ...(element.shadowRoot?.querySelectorAll(".axis-labels text") ?? []),
      ].map((node) => node.textContent.trim());
      expect(labels[0]).toBe("12 AM");
      expect(labels.at(-1)).toBe("10 PM");
      expect(labels.every((value) => !value.includes(":"))).toBe(true);
      if (missing !== null) expect(labels).not.toContain(missing);
      element.remove();
    },
  );

  it("keeps a flat two-sample five-minute trace visibly separated", async () => {
    const element = document.createElement("ic-today-timeline");
    element.timeline = {
      ...timeline,
      series: timeline.series.map((series) =>
        series.kind === "effective_temperature"
          ? {
              ...series,
              samples: [
                {
                  timestamp_utc: "2026-07-31T17:00:00+00:00",
                  value: 24.4,
                },
                {
                  timestamp_utc: "2026-07-31T17:05:00+00:00",
                  value: 24.4,
                },
              ],
            }
          : series,
      ),
    };
    document.body.append(element);
    await element.updateComplete;

    const pathData =
      element.shadowRoot
        ?.querySelector("path.effective_temperature")
        ?.getAttribute("d") ?? "";
    expect(pathData).toBe("M 376.67 92.50 L 673.33 92.50");
    expect(
      element.shadowRoot?.querySelectorAll("circle.measured-temperature"),
    ).toHaveLength(2);
    element.remove();
  });

  it("states that data is unavailable instead of drawing zero", async () => {
    const element = document.createElement("ic-today-timeline");
    document.body.append(element);
    await element.updateComplete;
    expect(element.shadowRoot?.textContent).toContain("not available yet");
    expect(element.shadowRoot?.querySelector("svg")).toBeNull();
    element.remove();
  });

  it("uses a compact collecting state until two observations exist", async () => {
    const element = document.createElement("ic-today-timeline");
    element.timeline = {
      ...timeline,
      series: timeline.series.map((series) => ({
        ...series,
        samples: series.samples.slice(0, 1),
      })),
    };
    document.body.append(element);
    await element.updateComplete;
    expect(element.shadowRoot?.textContent).toContain(
      "Collecting climate history",
    );
    expect(element.shadowRoot?.textContent).toContain(
      "1 of 2 temperature samples collected",
    );
    expect(element.shadowRoot?.textContent).toContain(
      "Source: effective zone temperature",
    );
    expect(element.shadowRoot?.querySelector("svg")).toBeNull();
    element.remove();
  });
});
