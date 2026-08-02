import { LitElement, css, html, nothing, type PropertyValues } from "lit";

import { intelligentClimateTheme } from "../styles/theme";
import type {
  ScheduleDocument,
  SchedulePeriod,
  SchedulePreviewResponse,
  ScheduleProfile,
  ScheduleTarget,
  ScheduleWeekday,
  ZoneConfiguration,
  ZoneSnapshot,
  ZoneSchedule,
} from "../types/contracts";
import { createUuid } from "../util/uuid";

const WEEKDAYS: readonly ScheduleWeekday[] = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];

const DAY_LABELS: Record<ScheduleWeekday, string> = {
  monday: "Monday",
  tuesday: "Tuesday",
  wednesday: "Wednesday",
  thursday: "Thursday",
  friday: "Friday",
  saturday: "Saturday",
  sunday: "Sunday",
};

interface EditorDetail {
  document: ScheduleDocument;
}

interface StarterTargets {
  homeHeatC: number;
  homeCoolC: number;
  awayHeatC: number;
  awayCoolC: number;
  sleepHeatC: number;
  sleepCoolC: number;
}

const DEFAULT_STARTER_TARGETS: StarterTargets = {
  homeHeatC: 20.6,
  homeCoolC: 23.9,
  awayHeatC: 18.9,
  awayCoolC: 26.7,
  sleepHeatC: 19.4,
  sleepCoolC: 23.9,
};

export class ScheduleEditor extends LitElement {
  public static override properties = {
    document: { attribute: false },
    zones: { attribute: false },
    zoneSnapshots: { attribute: false },
    preview: { attribute: false },
    validationMessage: { type: String },
    saving: { type: Boolean },
    dirty: { type: Boolean },
    temperatureUnit: { type: String },
    locale: { type: String },
    selectedZoneId: { state: true },
    selectedProfileId: { state: true },
    mobileDay: { state: true },
    copySource: { state: true },
    copyTargets: { state: true },
    clearPendingDay: { state: true },
    starterTargets: { state: true },
  };

  declare public document: ScheduleDocument;
  declare public zones: ZoneConfiguration[];
  public zoneSnapshots: ZoneSnapshot[] = [];
  declare public preview: SchedulePreviewResponse | undefined;
  public validationMessage = "";
  public saving = false;
  public dirty = false;
  public temperatureUnit: "°C" | "°F" = "°C";
  public locale = "en-US";

  protected selectedZoneId = "";
  protected selectedProfileId = "";
  protected mobileDay: ScheduleWeekday = "monday";
  protected copySource: ScheduleWeekday = "monday";
  protected copyTargets: ScheduleWeekday[] = [];
  protected clearPendingDay: ScheduleWeekday | undefined;
  protected starterTargets: StarterTargets = { ...DEFAULT_STARTER_TARGETS };

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has("document")) {
      const zoneIds = Object.keys(this.document.zones);
      if (!zoneIds.includes(this.selectedZoneId)) {
        this.selectedZoneId = zoneIds[0] ?? "";
      }
      const zone = this.document.zones[this.selectedZoneId];
      if (
        zone !== undefined &&
        !zone.profiles.some(
          (profile) => profile.profile_id === this.selectedProfileId,
        )
      ) {
        this.selectedProfileId = zone.selected_profile_id;
      }
    }
  }

  protected override render() {
    const zone = this.currentZone();
    const profile = this.currentProfile();
    if (zone === undefined || profile === undefined) {
      return html`<p role="status">No schedule zone is available.</p>`;
    }
    return html`
      <section class="editor-toolbar" aria-label="Schedule selection">
        <label>
          <span>Zone</span>
          <select .value=${this.selectedZoneId} @change=${this.zoneChanged}>
            ${Object.keys(this.document.zones).map(
              (zoneId) =>
                html`<option value=${zoneId}>${this.zoneName(zoneId)}</option>`,
            )}
          </select>
        </label>
        ${
          zone.profiles.length === 1
            ? html`<div class="profile-summary">
                <span>Schedule profile</span>
                <strong>${profile.name}</strong>
                <small>
                  A profile is a complete weekly schedule. Additional profiles
                  can later support patterns such as Vacation or Guest.
                </small>
              </div>`
            : html`<label>
                <span>Schedule profile</span>
                <select
                  .value=${this.selectedProfileId}
                  @change=${this.profileChanged}
                  aria-describedby="profile-help"
                >
                  ${zone.profiles.map(
                    (item) =>
                      html`<option value=${item.profile_id}>
                        ${item.name}
                      </option>`,
                  )}
                </select>
                <small id="profile-help">
                  Each profile is a complete weekly schedule for this zone.
                </small>
              </label>`
        }
        <label class="switch-label">
          <input
            type="checkbox"
            .checked=${zone.enabled}
            @change=${this.zoneEnabledChanged}
          />
          <span>Schedule this zone</span>
        </label>
        <label class="switch-label">
          <input
            type="checkbox"
            .checked=${profile.enabled}
            @change=${this.profileEnabledChanged}
          />
          <span>Enable profile</span>
        </label>
      </section>

      ${this.renderModeGuidance()}

      <section class="template-tools" aria-labelledby="template-heading">
        <div class="template-intro">
          <h3 id="template-heading">Starter schedule</h3>
          <p>
            Review these comfort bands before replacing the matching days.
            Heating and cooling targets stay together in one schedule period;
            your thermostat mode determines which side applies.
          </p>
        </div>
        <div class="starter-grid">
          ${this.starterTargetInputs("Home", "homeHeatC", "homeCoolC")}
          ${this.starterTargetInputs("Away", "awayHeatC", "awayCoolC")}
          ${this.starterTargetInputs("Sleep", "sleepHeatC", "sleepCoolC")}
        </div>
        <div class="template-actions">
          <button type="button" @click=${() => this.applyTemplate("weekday")}>
            Apply weekdays
          </button>
          <button type="button" @click=${() => this.applyTemplate("weekend")}>
            Apply weekend
          </button>
        </div>
      </section>

      <label class="mobile-day-picker">
        <span>Day to edit</span>
        <select .value=${this.mobileDay} @change=${this.mobileDayChanged}>
          ${WEEKDAYS.map(
            (day) => html`<option value=${day}>${DAY_LABELS[day]}</option>`,
          )}
        </select>
      </label>

      <section class="week-grid" aria-label="Weekly schedule">
        ${WEEKDAYS.map((day) => this.renderDay(profile, day))}
      </section>

      <section
        class="copy-tool"
        id="copy-day-tool"
        aria-labelledby="copy-heading"
      >
        <div>
          <h3 id="copy-heading">Copy a day</h3>
          <p>
            Choose any source and one or more destinations. Copied periods
            receive new stable identities.
          </p>
        </div>
        <label>
          <span>Copy from</span>
          <select .value=${this.copySource} @change=${this.copySourceChanged}>
            ${WEEKDAYS.map(
              (day) => html`<option value=${day}>${DAY_LABELS[day]}</option>`,
            )}
          </select>
        </label>
        <div class="copy-days">
          ${WEEKDAYS.filter((day) => day !== this.copySource).map(
            (day) =>
              html`<label>
                <input
                  type="checkbox"
                  aria-label=${`Copy ${DAY_LABELS[this.copySource]} to ${DAY_LABELS[day]}`}
                  .checked=${this.copyTargets.includes(day)}
                  @change=${(event: Event) => this.copyTargetChanged(day, event)}
                />
                ${DAY_LABELS[day]}
              </label>`,
          )}
        </div>
        <button
          type="button"
          class="secondary"
          ?disabled=${this.copyTargets.length === 0}
          @click=${this.copyDay}
        >
          Copy to selected days
        </button>
      </section>

      ${this.renderPreview(zone)}

      <section class="save-bar ${this.dirty ? "dirty" : ""}">
        <div>
          <strong
            >${this.dirty ? "Unsaved schedule changes" : "Schedule is saved"}</strong
          >
          <span
            >Revision ${this.document.revision} ·
            ${this.document.time_zone}</span
          >
        </div>
        <button type="button" @click=${this.requestPreview}>Preview</button>
        <button
          type="button"
          class="primary"
          ?disabled=${!this.dirty || this.saving}
          @click=${this.requestSave}
        >
          ${this.saving ? "Saving…" : "Validate & save"}
        </button>
      </section>
      ${
        this.validationMessage.length === 0
          ? nothing
          : html`<div class="validation" role="alert">
              <strong>Schedule needs attention</strong>
              <p>${this.validationMessage}</p>
            </div>`
      }
    `;
  }

  private renderDay(profile: ScheduleProfile, day: ScheduleWeekday) {
    const periods = profile.days[day];
    const hidden = day === this.mobileDay ? "" : "mobile-hidden";
    return html`<article class="day-column ${hidden}">
      <header>
        <div>
          <h3>${DAY_LABELS[day]}</h3>
          <span
            >${periods.length}
            ${periods.length === 1 ? "period" : "periods"}</span
          >
        </div>
        <div class="day-actions">
          <button
            type="button"
            aria-label=${`Copy ${DAY_LABELS[day]}`}
            @click=${() => this.selectCopySource(day)}
          >
            Copy
          </button>
          <button
            type="button"
            class="add"
            aria-label=${`Add ${DAY_LABELS[day]} period`}
            @click=${() => this.addPeriod(day)}
          >
            + Add
          </button>
          <button
            type="button"
            class="danger"
            ?disabled=${periods.length === 0}
            aria-label=${`Clear ${DAY_LABELS[day]}`}
            @click=${() => this.requestClearDay(day)}
          >
            Clear
          </button>
        </div>
      </header>
      ${
        this.clearPendingDay === day
          ? html`<div class="clear-confirmation" role="alert">
              <p>
                Clear every ${DAY_LABELS[day]} period? The final settings from
                the prior configured day will continue until the next period.
              </p>
              <div>
                <button type="button" @click=${this.cancelClearDay}>
                  Cancel
                </button>
                <button
                  type="button"
                  class="danger"
                  aria-label=${`Confirm clear ${DAY_LABELS[day]}`}
                  @click=${() => this.confirmClearDay(day)}
                >
                  Clear ${DAY_LABELS[day]}
                </button>
              </div>
            </div>`
          : nothing
      }
      ${
        periods.length === 0
          ? html`<p class="inheritance">
              ↺ Inherits the most recent period from an earlier day.
            </p>`
          : periods[0]?.local_start === "00:00"
            ? nothing
            : html`<p class="inheritance">
                ↺ Midnight–${periods[0]?.local_start}: previous period remains
                active.
              </p>`
      }
      <ol>
        ${periods.map((period, index) => this.renderPeriod(day, period, index))}
      </ol>
    </article>`;
  }

  private renderPeriod(
    day: ScheduleWeekday,
    period: SchedulePeriod,
    index: number,
  ) {
    const current = this.preview?.zones.some(
      (zone) => zone.period_id === period.period_id,
    );
    const path = `days.${day}[${String(index)}]`;
    const invalid = this.validationMessage.includes(path);
    return html`<li
      class="period ${current ? "current" : ""} ${invalid ? "invalid" : ""}"
    >
      <div class="period-heading">
        <strong
          >${current ? "● Current period" : `Period ${String(index + 1)}`}</strong
        >
        <div>
          <button
            type="button"
            aria-label=${`Duplicate ${DAY_LABELS[day]} period ${String(index + 1)}`}
            @click=${() => this.duplicatePeriod(day, index)}
          >
            Duplicate
          </button>
          <button
            type="button"
            class="danger"
            aria-label=${`Delete ${DAY_LABELS[day]} period ${String(index + 1)}`}
            @click=${() => this.deletePeriod(day, index)}
          >
            Delete
          </button>
        </div>
      </div>
      <div class="field-grid">
        <label>
          <span>Starts</span>
          <input
            type="time"
            .value=${period.local_start}
            @change=${(event: Event) =>
              this.periodTextChanged(day, index, "local_start", event)}
          />
        </label>
        <label>
          <span>Label</span>
          <input
            type="text"
            maxlength="64"
            .value=${period.label}
            @input=${(event: Event) =>
              this.periodTextChanged(day, index, "label", event)}
          />
        </label>
        <label>
          <span>Occupancy label</span>
          <select
            .value=${period.occupancy_label}
            @change=${(event: Event) =>
              this.periodTextChanged(day, index, "occupancy_label", event)}
          >
            ${[
              "none",
              "home",
              "away",
              "sleep",
              "vacation",
              "guest",
              "custom",
            ].map(
              (value) =>
                html`<option value=${value}>${this.titleCase(value)}</option>`,
            )}
          </select>
        </label>
        <label>
          <span>Target type</span>
          <select
            .value=${period.target.kind}
            @change=${(event: Event) => this.targetKindChanged(day, index, event)}
          >
            <option value="single">Single target</option>
            <option value="range">Heat / cool range</option>
          </select>
        </label>
        ${
          period.target.kind === "single"
            ? this.temperatureInput(
                day,
                index,
                "target_c",
                "Target",
                period.target.target_c,
              )
            : html`${this.temperatureInput(day, index, "heat_target_c", "Heat target", period.target.heat_target_c)}
              ${this.temperatureInput(day, index, "cool_target_c", "Cool target", period.target.cool_target_c)}`
        }
        <label>
          <span>Tolerance (${this.temperatureUnit})</span>
          <input
            type="number"
            min=${this.temperatureUnit === "°F" ? "0.2" : "0.1"}
            max=${this.temperatureUnit === "°F" ? "5" : "2.8"}
            step=${this.temperatureUnit === "°F" ? "0.1" : "0.1"}
            .value=${this.formatNumber(this.displayDelta(period.tolerance_c))}
            @change=${(event: Event) => this.toleranceChanged(day, index, event)}
          />
        </label>
      </div>
      ${this.targetModeWarning(period)}
      ${invalid ? html`<p class="field-error">Review this period and the validation summary.</p>` : nothing}
    </li>`;
  }

  private temperatureInput(
    day: ScheduleWeekday,
    index: number,
    field: keyof ScheduleTarget,
    label: string,
    value: number | null,
  ) {
    return html`<label>
      <span>${label} (${this.temperatureUnit})</span>
      <input
        type="number"
        step=${this.temperatureUnit === "°F" ? "0.5" : "0.1"}
        .value=${value === null ? "" : this.formatNumber(this.displayTemperature(value))}
        @change=${(event: Event) => this.targetValueChanged(day, index, field, event)}
      />
    </label>`;
  }

  private renderPreview(zone: ZoneSchedule) {
    const preview = this.preview;
    if (preview === undefined) {
      return html`<section class="preview-card">
        <h3>Authoritative preview</h3>
        <p>
          Preview the unsaved draft to see the current target, next material
          transition, inheritance, and exact DST behavior.
        </p>
      </section>`;
    }
    const item = preview.zones.find(
      (candidate) => candidate.zone_id === zone.zone_id,
    );
    const warnings = preview.dst_warnings.filter(
      (warning) => warning.zone_id === zone.zone_id,
    );
    return html`<section class="preview-card" aria-labelledby="preview-heading">
      <div>
        <h3 id="preview-heading">Authoritative preview</h3>
        <span
          >Week of ${preview.preview_week_start_local} ·
          ${preview.time_zone}</span
        >
      </div>
      ${
        item === undefined
          ? html`<p>
              This zone is disabled, so it has no active scheduled target.
            </p>`
          : html`<dl>
              <div>
                <dt>Current target</dt>
                <dd>${this.targetText(item.target)}</dd>
              </div>
              <div>
                <dt>Next target</dt>
                <dd>
                  ${item.next_target === null ? "No material change" : this.targetText(item.next_target)}
                </dd>
              </div>
              <div>
                <dt>Next transition</dt>
                <dd>
                  ${item.next_material_transition_utc === null ? "None" : this.dateTime(item.next_material_transition_utc)}
                </dd>
              </div>
              <div>
                <dt>Inherited now</dt>
                <dd>
                  ${item.inherited_from_previous_day ? "Yes — from an earlier day" : "No"}
                </dd>
              </div>
            </dl>`
      }
      ${
        warnings.length === 0
          ? html`<p class="no-warning">
              ✓ No scheduled boundary crosses a DST gap or repeated hour in this
              preview week.
            </p>`
          : html`<ul class="dst-warnings">
              ${warnings.map(
                (warning) =>
                  html`<li>
                    <strong
                      >${warning.kind === "gap" ? "Spring-forward gap" : "Repeated-hour fold"}</strong
                    >
                    <span>${warning.explanation}</span>
                  </li>`,
              )}
            </ul>`
      }
      <p class="preview-boundary">
        Preview is unsaved and nonauthoritative for control.
      </p>
    </section>`;
  }

  private currentZone(): ZoneSchedule | undefined {
    return this.document.zones[this.selectedZoneId];
  }

  private currentProfile(): ScheduleProfile | undefined {
    const zone = this.currentZone();
    return zone?.profiles.find(
      (profile) => profile.profile_id === this.selectedProfileId,
    );
  }

  private updateDocument(mutator: (document: ScheduleDocument) => void): void {
    const document = structuredClone(this.document);
    mutator(document);
    this.dispatchEvent(
      new CustomEvent<EditorDetail>("schedule-change", {
        detail: { document },
        bubbles: true,
        composed: true,
      }),
    );
  }

  private updateProfile(mutator: (profile: ScheduleProfile) => void): void {
    const zoneId = this.selectedZoneId;
    const profileId = this.selectedProfileId;
    this.updateDocument((document) => {
      const profile = document.zones[zoneId]?.profiles.find(
        (item) => item.profile_id === profileId,
      );
      if (profile !== undefined) {
        mutator(profile);
      }
    });
  }

  private zoneChanged = (event: Event): void => {
    const target = event.currentTarget;
    if (!(target instanceof HTMLSelectElement)) return;
    this.selectedZoneId = target.value;
    const zone = this.currentZone();
    this.selectedProfileId = zone?.selected_profile_id ?? "";
  };

  private profileChanged = (event: Event): void => {
    const target = event.currentTarget;
    if (!(target instanceof HTMLSelectElement)) return;
    this.selectedProfileId = target.value;
    const zoneId = this.selectedZoneId;
    this.updateDocument((document) => {
      const zone = document.zones[zoneId];
      if (zone !== undefined) zone.selected_profile_id = target.value;
    });
  };

  private zoneEnabledChanged = (event: Event): void => {
    const target = event.currentTarget;
    if (!(target instanceof HTMLInputElement)) return;
    const zoneId = this.selectedZoneId;
    this.updateDocument((document) => {
      const zone = document.zones[zoneId];
      if (zone !== undefined) zone.enabled = target.checked;
    });
  };

  private profileEnabledChanged = (event: Event): void => {
    const target = event.currentTarget;
    if (target instanceof HTMLInputElement) {
      this.updateProfile((profile) => (profile.enabled = target.checked));
    }
  };

  private mobileDayChanged = (event: Event): void => {
    const target = event.currentTarget;
    if (target instanceof HTMLSelectElement) {
      this.mobileDay = target.value as ScheduleWeekday;
      this.copySource = this.mobileDay;
      this.copyTargets = this.copyTargets.filter(
        (day) => day !== this.copySource,
      );
    }
  };

  private addPeriod(day: ScheduleWeekday): void {
    this.updateProfile((profile) => {
      const periods = profile.days[day];
      periods.push(this.newPeriod(this.nextAvailableTime(periods)));
      periods.sort((left, right) =>
        left.local_start.localeCompare(right.local_start),
      );
    });
  }

  private duplicatePeriod(day: ScheduleWeekday, index: number): void {
    this.updateProfile((profile) => {
      const source = profile.days[day][index];
      if (source === undefined) return;
      profile.days[day].push({
        ...structuredClone(source),
        period_id: this.uuid(),
        local_start: this.nextAvailableTime(
          profile.days[day],
          source.local_start,
        ),
      });
      profile.days[day].sort((left, right) =>
        left.local_start.localeCompare(right.local_start),
      );
    });
  }

  private deletePeriod(day: ScheduleWeekday, index: number): void {
    this.updateProfile((profile) => profile.days[day].splice(index, 1));
  }

  private requestClearDay(day: ScheduleWeekday): void {
    this.clearPendingDay = day;
  }

  private cancelClearDay = (): void => {
    this.clearPendingDay = undefined;
  };

  private confirmClearDay(day: ScheduleWeekday): void {
    this.updateProfile((profile) => {
      profile.days[day] = [];
    });
    this.clearPendingDay = undefined;
  }

  private periodTextChanged(
    day: ScheduleWeekday,
    index: number,
    field: "local_start" | "label" | "occupancy_label",
    event: Event,
  ): void {
    const target = event.currentTarget;
    if (!(
      target instanceof HTMLInputElement || target instanceof HTMLSelectElement
    ))
      return;
    this.updateProfile((profile) => {
      const period = profile.days[day][index];
      if (period === undefined) return;
      if (field === "occupancy_label") {
        period.occupancy_label =
          target.value as SchedulePeriod["occupancy_label"];
      } else {
        period[field] = target.value;
      }
      profile.days[day].sort((left, right) =>
        left.local_start.localeCompare(right.local_start),
      );
    });
  }

  private targetKindChanged(
    day: ScheduleWeekday,
    index: number,
    event: Event,
  ): void {
    const target = event.currentTarget;
    if (!(target instanceof HTMLSelectElement)) return;
    this.updateProfile((profile) => {
      const period = profile.days[day][index];
      if (period === undefined) return;
      period.target =
        target.value === "range"
          ? {
              kind: "range",
              target_c: null,
              heat_target_c: 20,
              cool_target_c: 24,
            }
          : {
              kind: "single",
              target_c: 22,
              heat_target_c: null,
              cool_target_c: null,
            };
    });
  }

  private targetValueChanged(
    day: ScheduleWeekday,
    index: number,
    field: keyof ScheduleTarget,
    event: Event,
  ): void {
    const target = event.currentTarget;
    if (!(target instanceof HTMLInputElement) || target.value.length === 0)
      return;
    const value = Number(target.value);
    if (!Number.isFinite(value)) return;
    this.updateProfile((profile) => {
      const period = profile.days[day][index];
      if (period !== undefined && field !== "kind") {
        period.target[field] = this.celsiusTemperature(value);
      }
    });
  }

  private toleranceChanged(
    day: ScheduleWeekday,
    index: number,
    event: Event,
  ): void {
    const target = event.currentTarget;
    if (!(target instanceof HTMLInputElement)) return;
    const value = Number(target.value);
    if (!Number.isFinite(value)) return;
    this.updateProfile((profile) => {
      const period = profile.days[day][index];
      if (period !== undefined) period.tolerance_c = this.celsiusDelta(value);
    });
  }

  private copyTargetChanged(day: ScheduleWeekday, event: Event): void {
    const target = event.currentTarget;
    if (!(target instanceof HTMLInputElement)) return;
    this.copyTargets = target.checked
      ? [...this.copyTargets, day]
      : this.copyTargets.filter((item) => item !== day);
  }

  private copySourceChanged = (event: Event): void => {
    const target = event.currentTarget;
    if (!(target instanceof HTMLSelectElement)) return;
    this.copySource = target.value as ScheduleWeekday;
    this.copyTargets = this.copyTargets.filter(
      (day) => day !== this.copySource,
    );
  };

  private selectCopySource(day: ScheduleWeekday): void {
    this.copySource = day;
    this.copyTargets = this.copyTargets.filter((target) => target !== day);
    const tool = this.renderRoot.querySelector<HTMLElement>("#copy-day-tool");
    if (tool !== null && typeof tool.scrollIntoView === "function") {
      tool.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }

  private copyDay = (): void => {
    const sourceDay = this.copySource;
    const targets = [...this.copyTargets];
    this.updateProfile((profile) => {
      const source = profile.days[sourceDay];
      for (const day of targets) {
        profile.days[day] = source.map((period) => ({
          ...structuredClone(period),
          period_id: this.uuid(),
        }));
      }
    });
    this.copyTargets = [];
  };

  private applyTemplate(kind: "weekday" | "weekend"): void {
    const days = kind === "weekday" ? WEEKDAYS.slice(0, 5) : WEEKDAYS.slice(5);
    const starts: readonly [
      string,
      string,
      keyof StarterTargets,
      keyof StarterTargets,
    ][] =
      kind === "weekday"
        ? ([
            ["06:30", "Morning", "homeHeatC", "homeCoolC"],
            ["08:30", "Away", "awayHeatC", "awayCoolC"],
            ["17:30", "Evening", "homeHeatC", "homeCoolC"],
            ["22:30", "Sleep", "sleepHeatC", "sleepCoolC"],
          ] as const)
        : ([
            ["08:00", "Morning", "homeHeatC", "homeCoolC"],
            ["23:00", "Sleep", "sleepHeatC", "sleepCoolC"],
          ] as const);
    this.updateProfile((profile) => {
      for (const day of days) {
        profile.days[day] = starts.map(([time, label, heatKey, coolKey]) => ({
          ...this.newPeriod(time),
          label,
          occupancy_label:
            label === "Sleep" ? "sleep" : label === "Away" ? "away" : "home",
          target: {
            kind: "range",
            target_c: null,
            heat_target_c: this.starterTargets[heatKey],
            cool_target_c: this.starterTargets[coolKey],
          },
        }));
      }
    });
  }

  private starterTargetInputs(
    label: string,
    heatKey: keyof StarterTargets,
    coolKey: keyof StarterTargets,
  ) {
    return html`<fieldset>
      <legend>${label}</legend>
      ${this.starterTemperatureInput("Heat", heatKey)}
      ${this.starterTemperatureInput("Cool", coolKey)}
    </fieldset>`;
  }

  private starterTemperatureInput(label: string, key: keyof StarterTargets) {
    return html`<label>
      <span>${label} (${this.temperatureUnit})</span>
      <input
        type="number"
        step=${this.temperatureUnit === "°F" ? "0.5" : "0.1"}
        .value=${this.formatNumber(
          this.displayTemperature(this.starterTargets[key]),
        )}
        @change=${(event: Event) => this.starterTargetChanged(key, event)}
      />
    </label>`;
  }

  private starterTargetChanged(key: keyof StarterTargets, event: Event): void {
    const target = event.currentTarget;
    if (!(target instanceof HTMLInputElement)) return;
    const value = Number(target.value);
    if (!Number.isFinite(value)) return;
    this.starterTargets = {
      ...this.starterTargets,
      [key]: this.celsiusTemperature(value),
    };
  }

  private requestPreview = (): void => {
    this.dispatchEvent(
      new CustomEvent("schedule-preview", { bubbles: true, composed: true }),
    );
  };

  private requestSave = (): void => {
    this.dispatchEvent(
      new CustomEvent("schedule-save", { bubbles: true, composed: true }),
    );
  };

  private newPeriod(localStart: string): SchedulePeriod {
    return {
      period_id: this.uuid(),
      local_start: localStart,
      label: "",
      occupancy_label: "none",
      target: this.defaultTarget(),
      tolerance_c: 0.5,
    };
  }

  private nextAvailableTime(
    periods: SchedulePeriod[],
    after = "05:30",
  ): string {
    const used = new Set(periods.map((period) => period.local_start));
    let minutes = this.timeMinutes(after) + 30;
    for (let attempts = 0; attempts < 48; attempts += 1) {
      minutes %= 24 * 60;
      const candidate = `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(minutes % 60).padStart(2, "0")}`;
      if (!used.has(candidate)) return candidate;
      minutes += 30;
    }
    return "00:00";
  }

  private timeMinutes(value: string): number {
    const [hour = "0", minute = "0"] = value.split(":");
    return Number(hour) * 60 + Number(minute);
  }

  private uuid(): string {
    return createUuid();
  }

  private zoneName(zoneId: string): string {
    return this.zones.find((zone) => zone.zone_id === zoneId)?.name ?? zoneId;
  }

  private currentZoneSnapshot(): ZoneSnapshot | undefined {
    return this.zoneSnapshots.find(
      (snapshot) => snapshot.zone_id === this.selectedZoneId,
    );
  }

  private defaultTarget(): ScheduleTarget {
    const snapshot = this.currentZoneSnapshot();
    const rangeCapable = snapshot?.supports_target_range === true;
    return rangeCapable
      ? {
          kind: "range",
          target_c: null,
          heat_target_c: this.starterTargets.homeHeatC,
          cool_target_c: this.starterTargets.homeCoolC,
        }
      : {
          kind: "single",
          target_c: 22,
          heat_target_c: null,
          cool_target_c: null,
        };
  }

  private renderModeGuidance() {
    const snapshot = this.currentZoneSnapshot();
    const mode = snapshot?.thermostat_hvac_mode;
    const label =
      mode === null || mode === undefined
        ? "Unavailable"
        : this.modeLabel(mode);
    let guidance: string;
    if (mode === "heat_cool" || mode === "auto") {
      guidance =
        "Use heat / cool ranges. A single target is ambiguous in this mode and Scheduled Control will remain blocked for that period.";
    } else if (mode === "heat") {
      guidance =
        "A single target is interpreted as heating. A heat / cool range requires Heat/Cool or Auto mode before Scheduled Control can use it.";
    } else if (mode === "cool") {
      guidance =
        "A single target is interpreted as cooling. A heat / cool range requires Heat/Cool or Auto mode before Scheduled Control can use it.";
    } else if (mode === "off") {
      guidance =
        "Schedules remain editable, but Scheduled Control is blocked while the thermostat is Off.";
    } else {
      guidance =
        "Schedules remain editable, but Scheduled Control is blocked until the thermostat reports an unambiguous Heat, Cool, or Heat/Cool mode.";
    }
    return html`<section
      class="mode-guidance"
      aria-labelledby="mode-guidance-heading"
    >
      <div>
        <span>Current thermostat mode</span>
        <strong id="mode-guidance-heading">${label}</strong>
      </div>
      <p>${guidance}</p>
      <small>The schedule never changes HVAC mode automatically.</small>
    </section>`;
  }

  private targetModeWarning(period: SchedulePeriod) {
    const snapshot = this.currentZoneSnapshot();
    const mode = snapshot?.thermostat_hvac_mode;
    const targetSupported =
      period.target.kind === "single"
        ? snapshot?.supports_single_target === true
        : snapshot?.supports_target_range === true;
    if (!targetSupported) {
      const targetLabel =
        period.target.kind === "single"
          ? "Single targets are"
          : "Heat / cool ranges are";
      return html`<p class="mode-warning" role="status">
        ${targetLabel} not supported by the current command-authority
        thermostat. This period remains visible, but it cannot be used for
        Scheduled Control.
      </p>`;
    }
    const compatible =
      (period.target.kind === "single" &&
        (mode === "heat" || mode === "cool")) ||
      (period.target.kind === "range" &&
        (mode === "heat_cool" || mode === "auto"));
    if (compatible) return nothing;
    const targetLabel =
      period.target.kind === "single" ? "Single target" : "Heat / cool range";
    const modeLabel =
      mode === null || mode === undefined
        ? "an unavailable mode"
        : this.modeLabel(mode);
    return html`<p class="mode-warning" role="status">
      ${targetLabel} cannot be used for Scheduled Control while the thermostat
      reports ${modeLabel}. It remains saved and visible; control will fail
      closed.
    </p>`;
  }

  private modeLabel(mode: string): string {
    if (mode === "heat_cool") return "Heat/Cool";
    if (mode === "auto") return "Auto";
    return this.titleCase(mode);
  }

  private displayTemperature(celsius: number): number {
    return this.temperatureUnit === "°F" ? (celsius * 9) / 5 + 32 : celsius;
  }

  private celsiusTemperature(value: number): number {
    return this.temperatureUnit === "°F" ? ((value - 32) * 5) / 9 : value;
  }

  private displayDelta(celsius: number): number {
    return this.temperatureUnit === "°F" ? (celsius * 9) / 5 : celsius;
  }

  private celsiusDelta(value: number): number {
    return this.temperatureUnit === "°F" ? (value * 5) / 9 : value;
  }

  private formatNumber(value: number): string {
    return String(Math.round(value * 10) / 10);
  }

  private targetText(target: ScheduleTarget): string {
    if (target.kind === "single" && target.target_c !== null) {
      return `${this.formatNumber(this.displayTemperature(target.target_c))}${this.temperatureUnit}`;
    }
    if (target.heat_target_c !== null && target.cool_target_c !== null) {
      return `${this.formatNumber(this.displayTemperature(target.heat_target_c))}–${this.formatNumber(this.displayTemperature(target.cool_target_c))}${this.temperatureUnit}`;
    }
    return "Unavailable";
  }

  private dateTime(value: string): string {
    return new Intl.DateTimeFormat(this.locale, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: this.document.time_zone,
    }).format(new Date(value));
  }

  private titleCase(value: string): string {
    return value.charAt(0).toUpperCase() + value.slice(1);
  }

  public static override styles = [
    intelligentClimateTheme,
    css`
      :host {
        display: block;
      }
      button,
      input,
      select {
        min-block-size: 44px;
        font: inherit;
      }
      button {
        border: 1px solid var(--ic-border);
        border-radius: 10px;
        background: var(--ic-surface);
        color: var(--primary-text-color);
        padding: 8px 12px;
        cursor: pointer;
      }
      button:hover {
        border-color: var(--ic-accent);
      }
      button:focus-visible,
      input:focus-visible,
      select:focus-visible {
        outline: 3px solid color-mix(in srgb, var(--ic-accent) 45%, transparent);
        outline-offset: 2px;
      }
      button.primary {
        background: var(--ic-accent);
        color: white;
        border-color: var(--ic-accent);
        font-weight: 700;
      }
      button.danger {
        color: var(--error-color, #c62828);
      }
      button:disabled {
        opacity: 0.55;
        cursor: not-allowed;
      }
      label {
        display: grid;
        gap: 5px;
        font-size: 0.84rem;
        font-weight: 650;
      }
      input,
      select {
        box-sizing: border-box;
        inline-size: 100%;
        padding: 8px 10px;
        border: 1px solid var(--ic-border);
        border-radius: 9px;
        background: var(--ic-surface);
        color: var(--primary-text-color);
      }
      .editor-toolbar {
        display: grid;
        grid-template-columns: minmax(160px, 1fr) minmax(160px, 1fr) auto auto;
        gap: 16px;
        align-items: end;
        margin-block-end: 18px;
      }
      .switch-label {
        display: flex;
        align-items: center;
        gap: 8px;
        min-block-size: 44px;
      }
      .switch-label input {
        inline-size: 20px;
        min-block-size: 20px;
      }
      .profile-summary {
        display: grid;
        gap: 5px;
      }
      .profile-summary > span,
      .profile-summary small,
      label small {
        color: var(--secondary-text-color);
        font-size: 0.76rem;
        line-height: 1.35;
      }
      .template-tools,
      .mode-guidance,
      .copy-tool,
      .preview-card,
      .save-bar {
        border: 1px solid var(--ic-border);
        border-radius: 16px;
        background: var(--ic-surface);
        padding: 16px;
        margin-block: 16px;
      }
      .mode-guidance {
        display: grid;
        grid-template-columns: minmax(150px, auto) 1fr;
        gap: 8px 20px;
        border: 1px solid var(--ic-border);
        border-inline-start: 4px solid var(--info-color, #039be5);
        border-radius: 12px;
        background: var(--ic-surface);
        padding: 14px 16px;
      }
      .mode-guidance div {
        display: grid;
      }
      .mode-guidance span,
      .mode-guidance small {
        color: var(--secondary-text-color);
        font-size: 0.78rem;
      }
      .mode-guidance small {
        grid-column: 1 / -1;
      }
      .mode-warning {
        margin-block-start: 10px;
        border-inline-start: 3px solid var(--warning-color, #f9a825);
        padding-inline-start: 10px;
        font-size: 0.82rem;
      }
      .template-tools {
        display: grid;
        grid-template-columns: minmax(220px, 1fr) minmax(360px, 2fr) auto;
        align-items: end;
        gap: 16px;
      }
      .starter-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
      }
      .starter-grid fieldset {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 8px;
        min-inline-size: 0;
        margin: 0;
        padding: 8px;
        border: 1px solid var(--ic-border);
        border-radius: 10px;
      }
      .starter-grid legend {
        padding-inline: 4px;
        font-size: 0.8rem;
        font-weight: 700;
      }
      .template-actions {
        display: grid;
        gap: 8px;
      }
      h3,
      p {
        margin-block: 0;
      }
      p {
        color: var(--secondary-text-color);
        line-height: 1.5;
      }
      .mobile-day-picker {
        display: none;
      }
      .week-grid {
        display: grid;
        grid-template-columns: repeat(7, minmax(215px, 1fr));
        gap: 12px;
        overflow-x: auto;
        padding-block: 4px 12px;
        scroll-snap-type: inline proximity;
      }
      .day-column {
        border: 1px solid var(--ic-border);
        border-radius: 14px;
        background: color-mix(in srgb, var(--ic-surface) 96%, var(--ic-accent));
        padding: 12px;
        scroll-snap-align: start;
      }
      .day-column > header {
        display: flex;
        justify-content: space-between;
        gap: 8px;
        align-items: start;
      }
      .day-actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: end;
        gap: 4px;
      }
      .day-actions button {
        min-block-size: 36px;
        padding: 5px 7px;
        font-size: 0.72rem;
      }
      .clear-confirmation {
        margin-block-start: 10px;
        padding: 10px;
        border: 1px solid var(--warning-color, #f9a825);
        border-radius: 10px;
        background: color-mix(
          in srgb,
          var(--warning-color, #f9a825) 9%,
          transparent
        );
      }
      .clear-confirmation div {
        display: flex;
        justify-content: end;
        gap: 8px;
        margin-block-start: 8px;
      }
      .day-column header span {
        color: var(--secondary-text-color);
        font-size: 0.8rem;
      }
      .day-column ol {
        list-style: none;
        padding: 0;
        margin: 10px 0 0;
        display: grid;
        gap: 10px;
      }
      .inheritance {
        font-size: 0.78rem;
        padding: 8px;
        margin-block-start: 10px;
        border-radius: 8px;
        background: color-mix(in srgb, var(--ic-accent) 8%, transparent);
      }
      .period {
        border: 1px solid var(--ic-border);
        border-radius: 12px;
        background: var(--primary-background-color);
        padding: 10px;
      }
      .period.current {
        border-color: var(--ic-accent);
        box-shadow: inset 3px 0 var(--ic-accent);
      }
      .period.invalid {
        border-color: var(--error-color, #c62828);
      }
      .period-heading {
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 6px;
        margin-block-end: 10px;
      }
      .period-heading div {
        display: flex;
        gap: 4px;
      }
      .period-heading button {
        min-block-size: 36px;
        padding: 5px 7px;
        font-size: 0.72rem;
      }
      .field-grid {
        display: grid;
        gap: 9px;
      }
      .field-error {
        color: var(--error-color, #c62828);
        font-size: 0.78rem;
        margin-block-start: 8px;
      }
      .copy-tool {
        display: grid;
        grid-template-columns: minmax(180px, 1fr) minmax(150px, 0.6fr) 2fr auto;
        align-items: center;
        gap: 16px;
      }
      .copy-days {
        display: flex;
        flex-wrap: wrap;
        gap: 8px 16px;
      }
      .copy-days label {
        display: flex;
        align-items: center;
        gap: 6px;
      }
      .copy-days input {
        inline-size: 18px;
        min-block-size: 18px;
      }
      .preview-card > div:first-child {
        display: flex;
        justify-content: space-between;
        gap: 12px;
      }
      .preview-card dl {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 10px;
      }
      .preview-card dl div {
        padding: 10px;
        border-radius: 10px;
        background: var(--primary-background-color);
      }
      .preview-card dt {
        color: var(--secondary-text-color);
        font-size: 0.78rem;
      }
      .preview-card dd {
        margin: 4px 0 0;
        font-weight: 700;
      }
      .dst-warnings {
        padding-inline-start: 20px;
      }
      .dst-warnings li {
        margin-block: 8px;
      }
      .dst-warnings span {
        display: block;
        color: var(--secondary-text-color);
      }
      .no-warning {
        margin-block: 12px;
      }
      .preview-boundary {
        font-size: 0.78rem;
      }
      .save-bar {
        position: sticky;
        inset-block-end: 12px;
        display: grid;
        grid-template-columns: 1fr auto auto;
        gap: 10px;
        align-items: center;
        box-shadow: var(--ha-card-box-shadow, 0 8px 24px rgba(0, 0, 0, 0.12));
        z-index: 2;
      }
      .save-bar.dirty {
        border-color: var(--warning-color, #f9a825);
      }
      .save-bar div {
        display: grid;
      }
      .save-bar span {
        color: var(--secondary-text-color);
        font-size: 0.8rem;
      }
      .validation {
        border: 2px solid var(--error-color, #c62828);
        border-radius: 12px;
        padding: 14px;
        color: var(--error-color, #c62828);
      }
      .validation p {
        color: inherit;
      }
      @media (max-width: 900px) {
        .editor-toolbar {
          grid-template-columns: 1fr 1fr;
        }
        .template-tools {
          grid-template-columns: 1fr;
          align-items: stretch;
        }
        .starter-grid {
          grid-template-columns: repeat(3, minmax(0, 1fr));
        }
        .mobile-day-picker {
          display: grid;
          margin-block: 14px;
        }
        .week-grid {
          display: block;
          overflow: visible;
        }
        .day-column.mobile-hidden {
          display: none;
        }
        .copy-tool {
          grid-template-columns: 1fr;
        }
        .preview-card dl {
          grid-template-columns: 1fr 1fr;
        }
      }
      @media (max-width: 480px) {
        .editor-toolbar {
          grid-template-columns: 1fr;
        }
        .template-actions button {
          inline-size: 100%;
        }
        .starter-grid {
          grid-template-columns: 1fr;
        }
        .preview-card dl {
          grid-template-columns: 1fr;
        }
        .save-bar {
          grid-template-columns: 1fr 1fr;
        }
        .save-bar div {
          grid-column: 1 / -1;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        * {
          scroll-behavior: auto !important;
        }
      }
    `,
  ];
}

customElements.define("ic-schedule-editor", ScheduleEditor);

declare global {
  interface HTMLElementTagNameMap {
    "ic-schedule-editor": ScheduleEditor;
  }
}
