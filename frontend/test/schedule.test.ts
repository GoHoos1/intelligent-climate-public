import { afterEach, describe, expect, it, vi } from "vitest";

import "../src/components/schedule-editor";
import {
  createEmptyScheduleDraft,
  prepareScheduleWrite,
} from "../src/schedule/draft";
import type { ScheduleDocument } from "../src/types/contracts";
import {
  ENTRY_ID,
  NOW,
  ZONE_ID,
  configuration,
  scheduleDocument,
  schedulePreview,
} from "./fixtures";

afterEach(() => document.body.replaceChildren());

async function renderEditor(
  documentValue: ScheduleDocument = structuredClone(scheduleDocument),
) {
  const editor = document.createElement("ic-schedule-editor");
  editor.document = documentValue;
  editor.zones = configuration.zones;
  editor.preview = schedulePreview;
  editor.temperatureUnit = "°F";
  editor.locale = "en-US";
  document.body.append(editor);
  await editor.updateComplete;
  return editor;
}

describe("Task 23 schedule editor", () => {
  it("creates a valid disabled revision-zero draft for every configured zone", () => {
    const random = vi
      .spyOn(globalThis.crypto, "randomUUID")
      .mockReturnValue("dddddddd-dddd-4ddd-8ddd-dddddddddddd");
    const draft = createEmptyScheduleDraft(
      ENTRY_ID,
      configuration,
      new Date(NOW),
    );

    expect(draft.revision).toBe(0);
    expect(draft.time_zone).toBe("America/New_York");
    expect(draft.equipment_group_id).toBe(
      "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    );
    expect(Object.values(draft.zones)).toHaveLength(1);
    expect(Object.values(draft.zones)[0]?.enabled).toBe(false);
    expect(Object.values(draft.zones)[0]?.profiles[0]?.days.sunday).toEqual([]);
    random.mockRestore();
  });

  it("updates only write metadata when preparing validation and save", () => {
    const prepared = prepareScheduleWrite(
      scheduleDocument,
      new Date("2026-08-01T12:00:00Z"),
    );
    expect(prepared.saved_at_utc).toBe("2026-08-01T12:00:00.000Z");
    expect(prepared.revision).toBe(scheduleDocument.revision);
    expect(scheduleDocument.saved_at_utc).toBe(NOW);
  });

  it("fails closed when schedule identity metadata is unavailable", () => {
    expect(() =>
      createEmptyScheduleDraft(ENTRY_ID, {
        ...configuration,
        config: { ...configuration.config, equipment_group: null },
      }),
    ).toThrow("config.equipment_group is unavailable");
    expect(() =>
      createEmptyScheduleDraft(ENTRY_ID, {
        ...configuration,
        config: {
          ...configuration.config,
          equipment_group: {},
        },
      }),
    ).toThrow("equipment_group_id is unavailable");
    expect(() =>
      createEmptyScheduleDraft(ENTRY_ID, {
        ...configuration,
        config: {
          ...configuration.config,
          acknowledged_time_zone: "",
        },
      }),
    ).toThrow("acknowledged_time_zone is unavailable");
  });

  it("renders all seven days, inheritance, preview, and DST-safe status", async () => {
    const editor = await renderEditor();
    expect(editor.shadowRoot?.querySelectorAll(".day-column")).toHaveLength(7);
    expect(editor.shadowRoot?.textContent.replaceAll(/\s+/g, " ")).toContain(
      "previous period remains active",
    );
    expect(editor.shadowRoot?.textContent).toContain("Current target");
    expect(editor.shadowRoot?.textContent).toContain("69.8°F");
    expect(editor.shadowRoot?.textContent).toContain(
      "No scheduled boundary crosses a DST gap",
    );
  });

  it("adds, duplicates, deletes, copies, and templates periods with new IDs", async () => {
    const ids = [
      "10000000-0000-4000-8000-000000000001",
      "10000000-0000-4000-8000-000000000002",
      "10000000-0000-4000-8000-000000000003",
      "10000000-0000-4000-8000-000000000004",
      "10000000-0000-4000-8000-000000000005",
      "10000000-0000-4000-8000-000000000006",
      "10000000-0000-4000-8000-000000000007",
      "10000000-0000-4000-8000-000000000008",
      "10000000-0000-4000-8000-000000000009",
      "10000000-0000-4000-8000-000000000010",
      "10000000-0000-4000-8000-000000000011",
      "10000000-0000-4000-8000-000000000012",
      "10000000-0000-4000-8000-000000000013",
      "10000000-0000-4000-8000-000000000014",
      "10000000-0000-4000-8000-000000000015",
      "10000000-0000-4000-8000-000000000016",
      "10000000-0000-4000-8000-000000000017",
      "10000000-0000-4000-8000-000000000018",
      "10000000-0000-4000-8000-000000000019",
      "10000000-0000-4000-8000-000000000020",
    ];
    vi.spyOn(globalThis.crypto, "randomUUID").mockImplementation(
      () =>
        (ids.shift() ??
          "10000000-0000-4000-8000-000000000099") as `${string}-${string}-${string}-${string}-${string}`,
    );
    const editor = await renderEditor();
    const changes: ScheduleDocument[] = [];
    editor.addEventListener("schedule-change", (event) => {
      const detail = (event as CustomEvent<{ document: ScheduleDocument }>)
        .detail;
      changes.push(detail.document);
      editor.document = detail.document;
    });

    editor.shadowRoot
      ?.querySelector<HTMLButtonElement>(
        'button[aria-label="Add Tuesday period"]',
      )
      ?.click();
    await editor.updateComplete;
    expect(
      changes.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.tuesday,
    ).toHaveLength(1);

    editor.shadowRoot
      ?.querySelector<HTMLButtonElement>(
        'button[aria-label="Duplicate Tuesday period 1"]',
      )
      ?.click();
    await editor.updateComplete;
    const duplicated =
      changes.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.tuesday ?? [];
    expect(new Set(duplicated.map((period) => period.period_id)).size).toBe(2);

    editor.shadowRoot
      ?.querySelector<HTMLButtonElement>(
        'button[aria-label="Delete Tuesday period 1"]',
      )
      ?.click();
    await editor.updateComplete;
    expect(
      changes.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.tuesday,
    ).toHaveLength(1);

    const mobileDay = editor.shadowRoot?.querySelector<HTMLSelectElement>(
      ".mobile-day-picker select",
    );
    if (mobileDay === null || mobileDay === undefined)
      throw new Error("day selector missing");
    mobileDay.value = "monday";
    mobileDay.dispatchEvent(new Event("change"));
    await editor.updateComplete;
    const sundayCopy = [
      ...(editor.shadowRoot?.querySelectorAll<HTMLInputElement>(
        ".copy-days input",
      ) ?? []),
    ].at(-1);
    sundayCopy?.click();
    await editor.updateComplete;
    editor.shadowRoot
      ?.querySelector<HTMLButtonElement>(".copy-tool > button")
      ?.click();
    await editor.updateComplete;
    const copied = changes.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.sunday[0];
    expect(copied?.label).toBe("Morning");
    expect(copied?.period_id).not.toBe(
      scheduleDocument.zones[ZONE_ID]?.profiles[0]?.days.monday[0]?.period_id,
    );

    const weekdayTemplate = [
      ...(editor.shadowRoot?.querySelectorAll<HTMLButtonElement>(
        ".template-tools button",
      ) ?? []),
    ][0];
    weekdayTemplate?.click();
    await editor.updateComplete;
    expect(
      changes.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.friday,
    ).toHaveLength(4);
  });

  it("emits preview and save requests without making control calls", async () => {
    const editor = await renderEditor();
    const preview = vi.fn();
    const save = vi.fn();
    editor.addEventListener("schedule-preview", preview);
    editor.addEventListener("schedule-save", save);
    const buttons = [
      ...(editor.shadowRoot?.querySelectorAll<HTMLButtonElement>(
        ".save-bar button",
      ) ?? []),
    ];
    buttons[0]?.click();
    editor.dirty = true;
    await editor.updateComplete;
    buttons[1]?.click();
    expect(preview).toHaveBeenCalledOnce();
    expect(save).toHaveBeenCalledOnce();
  });
});
