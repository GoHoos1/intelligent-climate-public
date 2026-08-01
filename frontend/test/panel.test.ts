import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";

import "../src/panel/intelligent-climate-panel";
import type { SnapshotResponse } from "../src/types/contracts";
import type { HomeAssistantLike } from "../src/types/home-assistant";
import {
  ENTRY_ID,
  activity,
  configuration,
  narrative,
  observation,
  shadow,
  snapshot,
  timeline,
} from "./fixtures";

function createHass(): {
  hass: HomeAssistantLike;
  cleanup: ReturnType<typeof vi.fn>;
  emitSnapshot: (value: SnapshotResponse) => void;
  setResponse: (type: string, value: unknown) => void;
} {
  const responses: Record<string, unknown> = {
    "intelligent_climate/config/get": configuration,
    "intelligent_climate/snapshot/get": snapshot,
    "intelligent_climate/activity/list": activity,
    "intelligent_climate/shadow/status": shadow,
    "intelligent_climate/observation/status": observation,
    "intelligent_climate/timeline/today": timeline,
    "intelligent_climate/narrative/current": narrative,
  };
  const cleanup = vi.fn();
  let subscription: ((message: unknown) => void) | undefined;
  const callWS: HomeAssistantLike["callWS"] = <T>(
    message: Record<string, unknown>,
  ) => Promise.resolve(responses[String(message["type"])] as T);
  return {
    cleanup,
    emitSnapshot: (value) => subscription?.(value),
    setResponse: (type, value) => {
      responses[type] = value;
    },
    hass: {
      callWS,
      connection: {
        subscribeMessage: (callback) => {
          subscription = callback;
          return Promise.resolve(cleanup);
        },
      },
      locale: { language: "en-US" },
      config: { unit_system: { temperature: "°F" } },
    },
  };
}

async function settle(panel: HTMLElement): Promise<void> {
  for (let index = 0; index < 8; index += 1) {
    await new Promise<void>((resolve) => window.setTimeout(resolve, 0));
    await (panel as HTMLElement & { updateComplete: Promise<boolean> })
      .updateComplete;
    if (panel.shadowRoot?.querySelector(".loading") === null) {
      return;
    }
  }
}

function mount(): {
  panel: HTMLElement;
  cleanup: ReturnType<typeof vi.fn>;
  emitSnapshot: (value: SnapshotResponse) => void;
  setResponse: (type: string, value: unknown) => void;
} {
  const panel = document.createElement("intelligent-climate-panel");
  const { hass, cleanup, emitSnapshot, setResponse } = createHass();
  panel.hass = hass;
  panel.panel = {
    config: {
      api_version: 1,
      frontend_version: "0.0.13",
      entries: [{ entry_id: ENTRY_ID, title: "Main floor" }],
    },
  };
  document.body.append(panel);
  return { panel, cleanup, emitSnapshot, setResponse };
}

afterEach(() => {
  document.body.replaceChildren();
  window.history.replaceState(null, "", "/");
  window.localStorage.clear();
});

describe("Intelligent Climate sidebar", () => {
  it("renders live Observe Only status and the factual Today timeline", async () => {
    const { panel } = mount();
    await settle(panel);
    const root = panel.shadowRoot;
    expect(root?.textContent).toContain("Observe Only");
    expect(root?.textContent).toContain("Automation is off");
    expect(root?.textContent).toContain("Dining Room");
    expect(root?.textContent).toContain("74.7°F");
    expect(root?.querySelector(".narrative")?.textContent).toContain("74.7°F");
    expect(root?.querySelector(".narrative")?.textContent).not.toContain("°C");
    expect(root?.querySelector("ic-today-timeline")).not.toBeNull();
    expect(root?.textContent).toContain("Shadow readiness");
    expect(root?.textContent).toContain(
      "Not started — Scheduled Shadow is not active.",
    );
    expect(root?.textContent).toContain(
      "Ordinary observation history is still being collected.",
    );
    expect(root?.textContent).not.toContain("42%");
  });

  it("shows qualification facts only while Scheduled Shadow is active", async () => {
    const { panel, setResponse } = mount();
    setResponse("intelligent_climate/snapshot/get", {
      ...snapshot,
      control_state: "shadow_qualifying",
    });
    await settle(panel);

    expect(panel.shadowRoot?.textContent).toContain("◌ Qualifying");
    expect(panel.shadowRoot?.textContent).toContain("42%");
    expect(panel.shadowRoot?.textContent).toContain("10.0 / 24 h");
    expect(panel.shadowRoot?.textContent).not.toContain(
      "Scheduled Shadow is not active",
    );
  });

  it("provides keyboard-sized route controls and all Task 22 sections", async () => {
    const { panel } = mount();
    await settle(panel);
    const buttons = [
      ...(panel.shadowRoot?.querySelectorAll(".primary-nav button") ?? []),
    ];
    expect(
      buttons.map((button) => button.textContent.replace(/\s+/g, " ").trim()),
    ).toEqual(["⌂ Overview", "◫ Sensors", "↯ Activity", "⚙ Settings"]);
    (buttons[1] as HTMLButtonElement).click();
    await (panel as HTMLElement & { updateComplete: Promise<boolean> })
      .updateComplete;
    expect(panel.shadowRoot?.textContent).toContain(
      "Current readings and configured sources",
    );
    (buttons[2] as HTMLButtonElement).click();
    await (panel as HTMLElement & { updateComplete: Promise<boolean> })
      .updateComplete;
    expect(panel.shadowRoot?.textContent).toContain("Newest activity first");
    expect(
      panel.shadowRoot?.querySelector(".activity-title strong")?.textContent,
    ).toBe("Observation");
    expect(panel.shadowRoot?.textContent).toContain("Historical record");
    (buttons[3] as HTMLButtonElement).click();
    await (panel as HTMLElement & { updateComplete: Promise<boolean> })
      .updateComplete;
    expect(panel.shadowRoot?.textContent).toContain("Read-only preview");
  });

  it("lets the user override Home Assistant temperature units consistently", async () => {
    const { panel } = mount();
    await settle(panel);
    const settings = panel.shadowRoot?.querySelectorAll(
      ".primary-nav button",
    )[3] as HTMLButtonElement;
    settings.click();
    await (panel as HTMLElement & { updateComplete: Promise<boolean> })
      .updateComplete;
    const select = panel.shadowRoot?.querySelector<HTMLSelectElement>(
      ".setting-select select",
    );
    expect(select).toBeDefined();
    if (select === undefined || select === null) {
      throw new Error("temperature preference selector was not rendered");
    }
    select.value = "celsius";
    select.dispatchEvent(new Event("change"));
    await (panel as HTMLElement & { updateComplete: Promise<boolean> })
      .updateComplete;
    const overview = panel.shadowRoot?.querySelectorAll(
      ".primary-nav button",
    )[0] as HTMLButtonElement;
    overview.click();
    await (panel as HTMLElement & { updateComplete: Promise<boolean> })
      .updateComplete;
    expect(
      panel.shadowRoot?.querySelector(".narrative")?.textContent,
    ).toContain("23.7°C");
    expect(
      window.localStorage.getItem("intelligent-climate.temperature-unit"),
    ).toBe("celsius");
  });

  it("passes an automated accessibility scan", async () => {
    const { panel } = mount();
    await settle(panel);
    const root = panel.shadowRoot;
    if (root === null) {
      throw new Error("panel shadow root was not created");
    }
    const result = await axe.run(root, {
      rules: { "color-contrast": { enabled: false } },
    });
    expect(result.violations).toEqual([]);
  });

  it("owns and releases the backend subscription on disconnect", async () => {
    const { panel, cleanup } = mount();
    await settle(panel);
    panel.remove();
    expect(cleanup).toHaveBeenCalledOnce();
  });

  it("refreshes timeline details when a live snapshot revision arrives", async () => {
    const { panel, emitSnapshot, setResponse } = mount();
    await settle(panel);
    setResponse("intelligent_climate/timeline/today", {
      ...timeline,
      series: timeline.series.map((series) =>
        series.kind === "hvac_action"
          ? {
              ...series,
              samples: [
                ...series.samples,
                {
                  timestamp_utc: "2026-07-31T18:05:00+00:00",
                  value: "heating",
                },
              ],
            }
          : series,
      ),
    });
    emitSnapshot({ ...snapshot, observation_revision: 9 });
    await settle(panel);
    const timelineElement =
      panel.shadowRoot?.querySelector("ic-today-timeline");
    await (
      timelineElement as HTMLElement & { updateComplete: Promise<boolean> }
    ).updateComplete;
    expect(timelineElement?.shadowRoot?.textContent).toContain(
      "Running with heating",
    );
  });
});
