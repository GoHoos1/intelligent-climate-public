import { afterEach, describe, expect, it, vi } from "vitest";

import "../src/components/schedule-editor";
import {
  createEmptyScheduleDraft,
  prepareScheduleWrite,
} from "../src/schedule/draft";
import type { ScheduleDocument, ZoneSnapshot } from "../src/types/contracts";
import {
  ENTRY_ID,
  NOW,
  ZONE_ID,
  configuration,
  scheduleDocument,
  schedulePreview,
  snapshot,
} from "./fixtures";

afterEach(() => document.body.replaceChildren());

async function renderEditor(
  documentValue: ScheduleDocument = structuredClone(scheduleDocument),
  zoneSnapshots: ZoneSnapshot[] = structuredClone(snapshot.zones),
) {
  const editor = document.createElement("ic-schedule-editor");
  editor.document = documentValue;
  editor.zones = configuration.zones;
  editor.zoneSnapshots = zoneSnapshots;
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
    expect(editor.shadowRoot?.textContent).toContain("Schedule profile");
    expect(editor.shadowRoot?.textContent).toContain(
      "A profile is a complete weekly schedule",
    );
    expect(editor.shadowRoot?.textContent.replaceAll(/\s+/g, " ")).toContain(
      "Current thermostat mode Heat/Cool",
    );
    expect(editor.shadowRoot?.textContent).toContain(
      "single target is ambiguous in this mode",
    );
    expect(editor.shadowRoot?.textContent).toContain(
      "The schedule never changes HVAC mode automatically",
    );
    expect(
      editor.shadowRoot?.querySelector(
        "select[aria-describedby='profile-help']",
      ),
    ).toBeNull();
  });

  it("defaults capable zones to ranges and flags mode-incompatible targets", async () => {
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
      changes.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.tuesday[0]?.target,
    ).toMatchObject({
      kind: "range",
      heat_target_c: 20.6,
      cool_target_c: 23.9,
    });

    const fixtureSnapshot = snapshot.zones[0];
    if (fixtureSnapshot === undefined) throw new Error("zone snapshot missing");
    const heatOnly = await renderEditor(structuredClone(scheduleDocument), [
      {
        ...structuredClone(fixtureSnapshot),
        thermostat_hvac_mode: "heat",
        supported_hvac_modes: ["off", "heat"],
        supports_target_range: false,
      },
    ]);
    const heatChanges: ScheduleDocument[] = [];
    heatOnly.addEventListener("schedule-change", (event) => {
      heatChanges.push(
        (event as CustomEvent<{ document: ScheduleDocument }>).detail.document,
      );
    });
    heatOnly.shadowRoot
      ?.querySelector<HTMLButtonElement>(
        'button[aria-label="Add Tuesday period"]',
      )
      ?.click();
    expect(
      heatChanges.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.tuesday[0]?.target
        .kind,
    ).toBe("single");
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
    expect(
      changes.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.friday[0]?.target,
    ).toMatchObject({
      kind: "range",
      heat_target_c: 20.6,
      cool_target_c: 23.9,
    });
  });

  it("copies any desktop day to multiple destinations", async () => {
    const editor = await renderEditor();
    const changes: ScheduleDocument[] = [];
    editor.addEventListener("schedule-change", (event) => {
      const detail = (event as CustomEvent<{ document: ScheduleDocument }>)
        .detail;
      changes.push(detail.document);
      editor.document = detail.document;
    });

    editor.shadowRoot
      ?.querySelector<HTMLButtonElement>('button[aria-label="Copy Monday"]')
      ?.click();
    await editor.updateComplete;
    const destinations = [
      ...(editor.shadowRoot?.querySelectorAll<HTMLInputElement>(
        ".copy-days input",
      ) ?? []),
    ];
    destinations[0]?.click();
    destinations.at(-1)?.click();
    await editor.updateComplete;
    editor.shadowRoot
      ?.querySelector<HTMLButtonElement>(".copy-tool > button")
      ?.click();
    await editor.updateComplete;

    expect(
      changes.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.tuesday[0]?.label,
    ).toBe("Morning");
    expect(
      changes.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.sunday[0]?.label,
    ).toBe("Morning");
  });

  it("clears a whole day only after explaining inherited settings", async () => {
    const editor = await renderEditor();
    const changes: ScheduleDocument[] = [];
    editor.addEventListener("schedule-change", (event) => {
      const detail = (event as CustomEvent<{ document: ScheduleDocument }>)
        .detail;
      changes.push(detail.document);
      editor.document = detail.document;
    });

    editor.shadowRoot
      ?.querySelector<HTMLButtonElement>('button[aria-label="Clear Monday"]')
      ?.click();
    await editor.updateComplete;
    expect(editor.shadowRoot?.textContent.replaceAll(/\s+/g, " ")).toContain(
      "final settings from the prior configured day will continue",
    );
    expect(changes).toHaveLength(0);

    editor.shadowRoot
      ?.querySelector<HTMLButtonElement>(".clear-confirmation button.danger")
      ?.click();
    await editor.updateComplete;
    expect(changes.at(-1)?.zones[ZONE_ID]?.profiles[0]?.days.monday).toEqual(
      [],
    );
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
