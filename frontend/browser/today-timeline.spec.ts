import { expect, test, type Page } from "@playwright/test";
import { PNG } from "pngjs";

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

interface Sample {
  timestamp_utc: string;
  value: number;
}

async function renderTimeline(page: Page, samples: readonly Sample[]) {
  await page.goto("/browser/fixture.html");
  await page.locator("#timeline").evaluate(async (element, values) => {
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
      generated_at_utc: values.at(-1)?.timestamp_utc,
      indoor_prediction_available: false,
      capability_statement: "No indoor prediction in Safe Scheduled Control.",
      series: [
        {
          kind: "effective_temperature",
          value_kind: "measured",
          unit: "°C",
          source_quality: "available",
          coverage_start_utc: values[0]?.timestamp_utc,
          coverage_end_utc: values.at(-1)?.timestamp_utc,
          missing_intervals: [],
          samples: values,
        },
      ],
      annotations: [],
    };
    await timelineElement.updateComplete;
  }, samples);
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
