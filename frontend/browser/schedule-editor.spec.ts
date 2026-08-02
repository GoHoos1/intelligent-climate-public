import { expect, test, type Page } from "@playwright/test";

interface BrowserScheduleDocument {
  zones: Record<
    string,
    {
      profiles: {
        days: Record<string, { label?: string }[]>;
      }[];
    }
  >;
}

async function renderEditor(page: Page) {
  await page.goto("/browser/schedule-fixture.html");
  const editor = page.locator("#editor");
  await editor.evaluate(async (element) => {
    const value = element as HTMLElement & {
      document: unknown;
      zones: unknown;
      zoneSnapshots: unknown;
      temperatureUnit: string;
      locale: string;
      updateComplete: Promise<boolean>;
    };
    const zoneId = "11111111-1111-4111-8111-111111111111";
    const profileId = "22222222-2222-4222-8222-222222222222";
    value.document = {
      schedule_schema_version: 1,
      entry_id: "entry-browser",
      equipment_group_id: "33333333-3333-4333-8333-333333333333",
      time_zone: "America/New_York",
      revision: 1,
      zones: {
        [zoneId]: {
          zone_id: zoneId,
          enabled: true,
          selected_profile_id: profileId,
          profiles: [
            {
              profile_id: profileId,
              name: "Normal",
              enabled: true,
              days: {
                monday: [
                  {
                    period_id: "44444444-4444-4444-8444-444444444444",
                    local_start: "06:30",
                    label: "Morning",
                    occupancy_label: "home",
                    target: {
                      kind: "single",
                      target_c: 21,
                      heat_target_c: null,
                      cool_target_c: null,
                    },
                    tolerance_c: 0.5,
                  },
                ],
                tuesday: [],
                wednesday: [],
                thursday: [],
                friday: [],
                saturday: [],
                sunday: [],
              },
            },
          ],
        },
      },
      saved_at_utc: "2026-08-01T12:00:00Z",
    };
    value.zones = [{ zone_id: zoneId, name: "Dining Room" }];
    value.zoneSnapshots = [
      {
        zone_id: zoneId,
        effective_temperature_c: 22,
        effective_humidity_pct: 50,
        thermostat_hvac_mode: "heat_cool",
        supported_hvac_modes: ["off", "heat", "cool", "heat_cool"],
        supports_single_target: true,
        supports_target_range: true,
        sensor_data_degraded: false,
        thermostat_data_degraded: false,
      },
    ];
    value.temperatureUnit = "°F";
    value.locale = "en-US";
    await value.updateComplete;
  });
  return editor;
}

test("renders the synchronized seven-day desktop editor", async ({ page }) => {
  const editor = await renderEditor(page);
  await expect(editor.locator(".day-column")).toHaveCount(7);
  await expect(editor.getByLabel("Label").first()).toHaveValue("Morning");
  await expect(editor.getByLabel("Target (°F)").first()).toHaveValue("69.8");
  const minimumButtonHeight = await editor
    .locator("button")
    .evaluateAll((nodes) =>
      Math.min(...nodes.map((node) => node.getBoundingClientRect().height)),
    );
  expect(minimumButtonHeight).toBeGreaterThanOrEqual(36);
});

test("uses one-day-at-a-time editing at a 320-pixel viewport", async ({
  page,
}) => {
  await page.setViewportSize({ width: 320, height: 900 });
  const editor = await renderEditor(page);
  await expect(editor.locator(".mobile-day-picker")).toBeVisible();
  await expect(editor.locator(".day-column:visible")).toHaveCount(1);
  await expect(
    editor.getByRole("button", { name: "Add Monday period" }),
  ).toBeVisible();
  const bodyWidth = await page.evaluate(
    () => document.documentElement.scrollWidth,
  );
  expect(bodyWidth).toBeLessThanOrEqual(320);
});

test("shows mode guidance and defaults capable thermostats to ranges", async ({
  page,
}) => {
  const editor = await renderEditor(page);
  await expect(editor.locator(".mode-guidance")).toContainText(
    "Current thermostat mode",
  );
  await expect(editor.locator(".mode-guidance")).toContainText("Heat/Cool");
  await expect(editor.locator(".mode-warning").first()).toContainText(
    "Single target cannot be used for Scheduled Control",
  );
  await editor.evaluate((element) => {
    element.addEventListener("schedule-change", (event) => {
      (
        globalThis as typeof globalThis & { scheduleChange?: unknown }
      ).scheduleChange = (event as CustomEvent).detail;
    });
  });
  await editor.getByRole("button", { name: "Add Tuesday period" }).click();
  const kind = await page.evaluate(() => {
    const detail = (
      globalThis as typeof globalThis & {
        scheduleChange?: {
          document: {
            zones: Record<
              string,
              {
                profiles: {
                  days: { tuesday: { target: { kind: string } }[] };
                }[];
              }
            >;
          };
        };
      }
    ).scheduleChange;
    return detail?.document.zones["11111111-1111-4111-8111-111111111111"]
      ?.profiles[0]?.days.tuesday[0]?.target.kind;
  });
  expect(kind).toBe("range");
});

test("adds periods on plain HTTP when randomUUID is unavailable", async ({
  page,
}) => {
  await page.addInitScript(() => {
    Object.defineProperty(globalThis.crypto, "randomUUID", {
      configurable: true,
      value: undefined,
    });
  });
  const editor = await renderEditor(page);
  await editor.evaluate((element) => {
    element.addEventListener("schedule-change", (event) => {
      const detail = (event as CustomEvent).detail as { document: unknown };
      (
        globalThis as typeof globalThis & { scheduleChange?: unknown }
      ).scheduleChange = detail.document;
    });
  });

  await editor.getByRole("button", { name: "Add Tuesday period" }).click();
  const periodId = await page.evaluate(() => {
    const changed = (
      globalThis as typeof globalThis & {
        scheduleChange?: {
          zones: Record<
            string,
            {
              profiles: {
                days: { tuesday: { period_id: string }[] };
              }[];
            }
          >;
        };
      }
    ).scheduleChange;
    const zone = changed?.zones["11111111-1111-4111-8111-111111111111"];
    return zone?.profiles[0]?.days.tuesday[0]?.period_id;
  });

  expect(periodId).toMatch(
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
  );
});

test("copies to multiple days and explains whole-day clearing", async ({
  page,
}) => {
  const editor = await renderEditor(page);
  await editor.evaluate((element) => {
    const value = element as HTMLElement & {
      document: unknown;
    };
    element.addEventListener("schedule-change", (event) => {
      value.document = (
        event as CustomEvent<{ document: unknown }>
      ).detail.document;
    });
  });

  await editor.getByRole("button", { name: "Copy Monday" }).click();
  await editor.getByLabel("Copy Monday to Tuesday").check();
  await editor.getByLabel("Copy Monday to Sunday").check();
  await editor.getByRole("button", { name: "Copy to selected days" }).click();
  const copiedLabels = await editor.evaluate((element) => {
    const document = (
      element as HTMLElement & { document: BrowserScheduleDocument }
    ).document;
    const zone = document.zones["11111111-1111-4111-8111-111111111111"];
    const profile = zone?.profiles[0];
    if (profile === undefined) throw new Error("schedule profile missing");
    return [
      profile.days["tuesday"]?.[0]?.label,
      profile.days["sunday"]?.[0]?.label,
    ];
  });
  expect(copiedLabels).toEqual(["Morning", "Morning"]);

  await editor.getByRole("button", { name: "Clear Monday" }).click();
  await expect(
    editor.getByText(/prior configured day will continue/),
  ).toBeVisible();
  await editor.getByRole("button", { name: "Confirm clear Monday" }).click();
  const mondayPeriods = await editor.evaluate((element) => {
    const document = (
      element as HTMLElement & { document: BrowserScheduleDocument }
    ).document;
    const zone = document.zones["11111111-1111-4111-8111-111111111111"];
    const profile = zone?.profiles[0];
    if (profile === undefined) throw new Error("schedule profile missing");
    return profile.days["monday"]?.length;
  });
  expect(mondayPeriods).toBe(0);
});
