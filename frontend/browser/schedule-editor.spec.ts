import { expect, test, type Page } from "@playwright/test";

async function renderEditor(page: Page) {
  await page.goto("/browser/schedule-fixture.html");
  const editor = page.locator("#editor");
  await editor.evaluate(async (element) => {
    const value = element as HTMLElement & {
      document: unknown;
      zones: unknown;
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
