import { expect, test, type Page } from "@playwright/test";
import { PNG } from "pngjs";

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

interface Sample {
  timestamp_utc: string;
  value: number;
}

interface BrowserSeries {
  kind: string;
  value_kind: string;
  unit: string | null;
  source_quality: string;
  coverage_start_utc: string;
  coverage_end_utc: string;
  missing_intervals: readonly unknown[];
  samples: readonly {
    timestamp_utc: string;
    value: number | string;
  }[];
}

async function renderTimeline(
  page: Page,
  samples: readonly Sample[],
  extraSeries: readonly BrowserSeries[] = [],
) {
  await page.goto("/browser/fixture.html");
  await page.locator("#timeline").evaluate(
    async (element, payload) => {
      const timelineElement = element as HTMLElement & {
        timeline: unknown;
        updateComplete: Promise<boolean>;
      };
      timelineElement.timeline = {
        api_version: 1,
        entry_id: "entry-browser-regression",
        zone_id: "99246285-6f02-4e8a-94ed-bdfd4a5e62c4",
        time_zone: "America/New_York",
        local_date: "2026-07-31",
        day_start_utc: "2026-07-31T04:00:00+00:00",
        day_end_utc: "2026-08-01T04:00:00+00:00",
        generated_at_utc: payload.values.at(-1)?.timestamp_utc,
        indoor_prediction_available: false,
        capability_statement: "No indoor prediction in Safe Scheduled Control.",
        series: [
          {
            kind: "effective_temperature",
            value_kind: "measured",
            unit: "°C",
            source_quality: "available",
            coverage_start_utc: payload.values[0]?.timestamp_utc,
            coverage_end_utc: payload.values.at(-1)?.timestamp_utc,
            missing_intervals: [],
            samples: payload.values,
          },
          ...payload.extraSeries,
        ],
        annotations: [],
      };
      await timelineElement.updateComplete;
    },
    { values: samples, extraSeries },
  );
  return page.locator("#timeline").locator("svg");
}

test("creates every dynamic chart primitive in the SVG namespace", async ({
  page,
}) => {
  const chart = await renderTimeline(page, [
    { timestamp_utc: "2026-07-31T17:00:00+00:00", value: 24.4 },
    { timestamp_utc: "2026-07-31T17:05:00+00:00", value: 24.4 },
  ]);

  const namespaces = await chart
    .locator("path, circle, line, text")
    .evaluateAll((nodes) =>
      nodes.map((node) => ({
        name: node.localName,
        namespace: node.namespaceURI,
      })),
    );

  expect(namespaces.length).toBeGreaterThan(0);
  expect(namespaces).toEqual(
    namespaces.map(({ name }) => ({ name, namespace: SVG_NAMESPACE })),
  );
  const traceWidth = await chart
    .locator("path.effective_temperature")
    .evaluate((node) => (node as SVGGraphicsElement).getBBox().width);
  expect(traceWidth).toBeGreaterThan(250);
});

test("renders visible pixels for a nearly flat three-sample trace", async ({
  page,
}) => {
  const chart = await renderTimeline(page, [
    { timestamp_utc: "2026-07-31T17:00:00+00:00", value: 24.4 },
    { timestamp_utc: "2026-07-31T17:05:00+00:00", value: 24.41 },
    { timestamp_utc: "2026-07-31T17:10:00+00:00", value: 24.4 },
  ]);

  const image = PNG.sync.read(await chart.screenshot());
  let accentPixels = 0;
  for (let offset = 0; offset < image.data.length; offset += 4) {
    const red = image.data[offset];
    const green = image.data[offset + 1];
    const blue = image.data[offset + 2];
    const alpha = image.data[offset + 3];
    if (red === 0 && green === 90 && blue === 156 && alpha === 255) {
      accentPixels += 1;
    }
  }
  expect(accentPixels).toBeGreaterThan(100);
});

test("renders dense history as clean lines with aligned operation and context lanes", async ({
  page,
}) => {
  const start = Date.parse("2026-07-31T17:00:00+00:00");
  const samples = Array.from({ length: 12 }, (_, index) => ({
    timestamp_utc: new Date(start + index * 5 * 60_000).toISOString(),
    value: 23.5 + index / 100,
  }));
  const end = samples.at(-1)?.timestamp_utc ?? "2026-07-31T17:55:00.000Z";
  const numericSeries = (kind: string, value: number): BrowserSeries => ({
    kind,
    value_kind: "configured",
    unit: "°C",
    source_quality: "available",
    coverage_start_utc: samples[0]?.timestamp_utc ?? end,
    coverage_end_utc: end,
    missing_intervals: [],
    samples: [
      { timestamp_utc: samples[0]?.timestamp_utc ?? end, value },
      { timestamp_utc: end, value },
    ],
  });
  const stateSeries = (
    kind: string,
    values: readonly [string, string][],
  ): BrowserSeries => ({
    kind,
    value_kind: kind === "control_context" ? "calculated" : "measured",
    unit: null,
    source_quality: "available",
    coverage_start_utc: samples[0]?.timestamp_utc ?? end,
    coverage_end_utc: end,
    missing_intervals: [],
    samples: values.map(([timestamp_utc, value]) => ({ timestamp_utc, value })),
  });

  const chart = await renderTimeline(page, samples, [
    numericSeries("scheduled_heat_target", 20.5),
    numericSeries("scheduled_cool_target", 24),
    stateSeries("hvac_action", [
      [samples[0]?.timestamp_utc ?? end, "off"],
      [samples[3]?.timestamp_utc ?? end, "heating"],
      [samples[6]?.timestamp_utc ?? end, "off"],
      [samples[8]?.timestamp_utc ?? end, "cooling"],
      [end, "off"],
    ]),
    stateSeries("fan_action", [
      [samples[0]?.timestamp_utc ?? end, "off"],
      [samples[6]?.timestamp_utc ?? end, "on"],
      [samples[8]?.timestamp_utc ?? end, "off"],
    ]),
    stateSeries("contact_state", [
      [samples[0]?.timestamp_utc ?? end, "closed"],
      [samples[4]?.timestamp_utc ?? end, "open"],
      [samples[8]?.timestamp_utc ?? end, "closed"],
    ]),
    stateSeries("control_context", [
      [samples[0]?.timestamp_utc ?? end, "normal"],
      [samples[5]?.timestamp_utc ?? end, "window_suspended"],
      [samples[8]?.timestamp_utc ?? end, "normal"],
    ]),
  ]);

  await expect(chart.locator("circle.measured-temperature")).toHaveCount(0);
  const timeLabels = await chart.locator(".axis-labels text").allTextContents();
  expect(timeLabels).toEqual(["1:00 PM", "1:15 PM", "1:30 PM", "1:45 PM"]);
  await expect(chart.locator("path.scheduled_heat_target")).toHaveCount(1);
  await expect(chart.locator("path.scheduled_cool_target")).toHaveCount(1);
  const timeline = page.locator("#timeline");
  await expect(timeline.locator(".lane-row")).toHaveCount(6);
  await expect(
    timeline.getByText("Window / door", { exact: true }),
  ).toBeVisible();
  await expect(
    timeline.getByText("Control context", { exact: true }),
  ).toBeVisible();
  const segmentWidths = await timeline
    .locator(".lane-segment")
    .evaluateAll((nodes) =>
      nodes.map((node) => node.getBoundingClientRect().width),
    );
  expect(segmentWidths.every((width) => width > 2)).toBe(true);

  const image = PNG.sync.read(await timeline.screenshot());
  let heatPixels = 0;
  let coolPixels = 0;
  for (let offset = 0; offset < image.data.length; offset += 4) {
    const [red, green, blue, alpha] = image.data.subarray(offset, offset + 4);
    if (red === 239 && green === 108 && blue === 0 && alpha === 255) {
      heatPixels += 1;
    }
    if (red === 25 && green === 118 && blue === 210 && alpha === 255) {
      coolPixels += 1;
    }
  }
  expect(heatPixels).toBeGreaterThan(20);
  expect(coolPixels).toBeGreaterThan(20);
});
