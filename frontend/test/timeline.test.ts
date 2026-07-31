import { describe, expect, it } from "vitest";

import "../src/components/today-timeline";
import { timeline } from "./fixtures";

describe("accessible Today timeline", () => {
  it("renders provenance with non-color line styles and a data table", async () => {
    const element = document.createElement("ic-today-timeline");
    element.timeline = timeline;
    element.locale = "en-US";
    element.temperatureUnit = "°F";
    document.body.append(element);
    await element.updateComplete;
    const root = element.shadowRoot;
    expect(root?.querySelector("path.series.measured")).not.toBeNull();
    expect(root?.textContent).toContain("Indoor temperature");
    expect(root?.textContent).toContain("measured");
    expect(root?.textContent).toContain("74.7°F");
    expect(root?.querySelector("table caption")?.textContent).toContain(
      "Latest factual value",
    );
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
    expect(element.shadowRoot?.querySelector("svg")).toBeNull();
    element.remove();
  });
});
