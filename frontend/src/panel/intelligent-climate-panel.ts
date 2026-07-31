import {
  LitElement,
  css,
  html,
  nothing,
  type PropertyValues,
  type TemplateResult,
} from "lit";

import {
  formatTemperature,
  formatTimestamp,
  humanizeCode,
  statusSemantics,
} from "../accessibility/semantics";
import { IntelligentClimateClient } from "../api/client";
import { FrontendContractError } from "../api/validate";
import "../components/today-timeline";
import {
  readTemperatureUnitPreference,
  resolveTemperatureUnit,
  type TemperatureUnitPreference,
  writeTemperatureUnitPreference,
} from "../preferences/temperature-unit";
import { intelligentClimateTheme } from "../styles/theme";
import type {
  ActivityRecord,
  ConfiguredSource,
  EntryDashboardData,
  NarrativeResponse,
  SnapshotResponse,
  TodayTimelineResponse,
  ReviewedBinding,
  ZoneConfiguration,
  ZoneSnapshot,
} from "../types/contracts";
import type {
  HomeAssistantLike,
  HomeAssistantPanelInfo,
  IntelligentClimatePanelEntry,
} from "../types/home-assistant";

type PanelRoute = "overview" | "sensors" | "activity" | "settings";

const ROUTES: readonly {
  id: PanelRoute;
  label: string;
  icon: string;
}[] = [
  { id: "overview", label: "Overview", icon: "⌂" },
  { id: "sensors", label: "Sensors", icon: "◫" },
  { id: "activity", label: "Activity", icon: "↯" },
  { id: "settings", label: "Settings", icon: "⚙" },
];

function isPanelRoute(value: string): value is PanelRoute {
  return ROUTES.some((route) => route.id === value);
}

export class IntelligentClimatePanel extends LitElement {
  public static override properties = {
    hass: { attribute: false },
    panel: { attribute: false },
    route: { attribute: false },
    narrow: { type: Boolean },
    activeRoute: { state: true },
    selectedEntryId: { state: true },
    selectedZoneId: { state: true },
    data: { state: true },
    timeline: { state: true },
    narrative: { state: true },
    loading: { state: true },
    errorMessage: { state: true },
    activityFilter: { state: true },
    temperatureUnitPreference: { state: true },
    activityLoadingOlder: { state: true },
  };

  declare public hass: HomeAssistantLike;
  declare public panel: HomeAssistantPanelInfo;
  public route: { path?: string } | undefined;
  public narrow = false;

  protected activeRoute: PanelRoute = "overview";
  protected selectedEntryId = "";
  protected selectedZoneId = "";
  protected data: EntryDashboardData | undefined;
  protected timeline: TodayTimelineResponse | undefined;
  protected narrative: NarrativeResponse | undefined;
  protected loading = true;
  protected errorMessage = "";
  protected activityFilter = "all";
  protected temperatureUnitPreference: TemperatureUnitPreference =
    readTemperatureUnitPreference();
  protected activityLoadingOlder = false;

  private client: IntelligentClimateClient | undefined;
  private unsubscribe: (() => void) | undefined;
  private loadGeneration = 0;

  public override disconnectedCallback(): void {
    this.loadGeneration += 1;
    this.unsubscribe?.();
    this.unsubscribe = undefined;
    super.disconnectedCallback();
  }

  protected override willUpdate(changed: PropertyValues<this>): void {
    if (changed.has("route")) {
      const path = this.route?.path?.split("/").find(Boolean);
      if (path !== undefined && isPanelRoute(path)) {
        this.activeRoute = path;
      }
    }
  }

  protected override updated(changed: PropertyValues<this>): void {
    if (
      (changed.has("hass") || changed.has("panel")) &&
      this.client === undefined
    ) {
      void this.initialize();
    }
  }

  protected override render() {
    const entries = this.entries();
    return html`
      <div class="app-shell">
        <header class="topbar">
          <div class="brand">
            <span class="brand-mark" aria-hidden="true">IC</span>
            <div>
              <h1>Intelligent Climate</h1>
              <p>See what your home is doing—and why.</p>
            </div>
          </div>
          ${
            entries.length > 1
              ? html`<label class="entry-picker">
                  <span>Equipment group</span>
                  <select
                    .value=${this.selectedEntryId}
                    @change=${this.entryChanged}
                  >
                    ${entries.map(
                      (entry) =>
                        html`<option value=${entry.entry_id}>
                          ${entry.title}
                        </option>`,
                    )}
                  </select>
                </label>`
              : html`<div class="entry-name">
                  ${entries[0]?.title ?? "Climate"}
                </div>`
          }
        </header>

        <nav class="primary-nav" aria-label="Intelligent Climate sections">
          ${ROUTES.map(
            (route) =>
              html`<button
                type="button"
                class=${this.activeRoute === route.id ? "active" : ""}
                aria-current=${this.activeRoute === route.id ? "page" : nothing}
                @click=${() => this.navigate(route.id)}
              >
                <span aria-hidden="true">${route.icon}</span>
                ${route.label}
              </button>`,
          )}
        </nav>

        <main id="main-content" tabindex="-1">
          ${
            this.loading
              ? this.renderLoading()
              : this.errorMessage.length > 0
                ? this.renderError()
                : this.renderRoute()
          }
        </main>
      </div>
    `;
  }

  private renderLoading(): TemplateResult {
    return html`<div class="loading" role="status" aria-live="polite">
      <div class="spinner" aria-hidden="true"></div>
      <strong>Loading your climate picture…</strong>
      <span>Connecting to the local Intelligent Climate data.</span>
    </div>`;
  }

  private renderError(): TemplateResult {
    return html`<section class="error-card" role="alert">
      <span class="error-icon" aria-hidden="true">!</span>
      <div>
        <h2>We couldn’t load Intelligent Climate</h2>
        <p>${this.errorMessage}</p>
        <button type="button" class="primary-button" @click=${this.retry}>
          Try again
        </button>
      </div>
    </section>`;
  }

  private renderRoute(): TemplateResult {
    switch (this.activeRoute) {
      case "overview":
        return this.renderOverview();
      case "sensors":
        return this.renderSensors();
      case "activity":
        return this.renderActivity();
      case "settings":
        return this.renderSettings();
    }
  }

  private renderOverview(): TemplateResult {
    const data = this.requireData();
    const status = statusSemantics(data.snapshot.control_state);
    const readiness = data.shadow.readiness;
    const selectedZone = this.selectedZone();
    return html`
      <section
        class="status-hero tone-${status.tone}"
        aria-labelledby="status-title"
      >
        <div class="status-copy">
          <span class="eyebrow">Current operating status</span>
          <h2 id="status-title">
            <span aria-hidden="true">${status.icon}</span> ${status.label}
          </h2>
          <p>
            ${
              status.automationOff
                ? "Automation is off. Sensors, thermostat state, weather context, activity, and history remain available."
                : "The safety path is evaluating current conditions. This read-only preview does not control your equipment."
            }
          </p>
          <div class="status-meta">
            <span>Revision ${data.snapshot.observation_revision}</span>
            <span>Updated ${this.time(data.snapshot.calculated_at_utc)}</span>
            <span
              >${data.snapshot.reason_code === null ? "No current alert" : humanizeCode(data.snapshot.reason_code)}</span
            >
          </div>
        </div>
        <div class="hero-orbit" aria-hidden="true">
          <div class="orbit-ring"></div>
          <div class="orbit-value">${data.snapshot.zones.length}</div>
          <div class="orbit-label">
            ${data.snapshot.zones.length === 1 ? "zone" : "zones"}
          </div>
        </div>
      </section>

      <section class="metric-grid" aria-label="Climate summary">
        <article class="metric-card">
          <span class="metric-icon temp" aria-hidden="true">◒</span>
          <div>
            <span>Selected zone</span
            ><strong>${selectedZone?.name ?? "Unavailable"}</strong>
          </div>
          <b
            >${this.temperature(this.selectedZoneSnapshot()?.effective_temperature_c ?? null)}</b
          >
        </article>
        <article class="metric-card">
          <span class="metric-icon humidity" aria-hidden="true">◇</span>
          <div>
            <span>Humidity</span
            ><strong
              >${this.selectedZone()?.humidity_sources.some((source) => source.enabled) === true ? "Measured" : "Not configured"}</strong
            >
          </div>
          <b
            >${this.humidity(this.selectedZoneSnapshot()?.effective_humidity_pct ?? null, this.selectedZone()?.humidity_sources.some((source) => source.enabled) === true)}</b
          >
        </article>
        <article class="metric-card">
          <span class="metric-icon source" aria-hidden="true">✓</span>
          <div>
            <span>Usable sources</span
            ><strong
              >${data.observation.degraded_zone_count === 0 ? "Healthy" : "Attention"}</strong
            >
          </div>
          <b>${data.observation.usable_temperature_sources}</b>
        </article>
        <article class="metric-card">
          <span class="metric-icon history" aria-hidden="true">↺</span>
          <div>
            <span>Local timeline</span><strong>Recent climate history</strong>
          </div>
          <b>${data.observation.presentation_history_hours}h</b>
        </article>
      </section>

      ${this.renderZoneSelector(data.configuration.zones)}

      <div class="overview-grid">
        <section class="card narrative-card" aria-labelledby="now-heading">
          <div class="card-heading">
            <div>
              <span class="eyebrow">Right now</span>
              <h2 id="now-heading">What Intelligent Climate sees</h2>
            </div>
            <button
              type="button"
              class="icon-button"
              aria-label="Refresh climate details"
              @click=${this.refreshDetails}
            >
              ↻
            </button>
          </div>
          ${
            this.narrative === undefined
              ? html`<p class="muted">
                  A current explanation is not available yet.
                </p>`
              : html`<p class="narrative">${this.renderNarrative()}</p>`
          }
        </section>

        <section
          class="card readiness-card"
          aria-labelledby="readiness-heading"
        >
          <div class="card-heading">
            <div>
              <span class="eyebrow">Safe Scheduled Control</span>
              <h2 id="readiness-heading">Shadow readiness</h2>
            </div>
            <span
              class="readiness-state ${readiness?.ready === true ? "ready" : "waiting"}"
            >
              ${readiness?.ready === true ? "✓ Ready" : "◌ Observing"}
            </span>
          </div>
          ${
            readiness === null
              ? html`<p class="muted">
                  Shadow qualification has not started. Observe Only remains
                  fully available.
                </p>`
              : html`<div class="progress-row">
                    <div class="progress-label">
                      <span>Qualification</span
                      ><strong
                        >${Math.round(readiness.qualification_percent)}%</strong
                      >
                    </div>
                    <div
                      class="progress"
                      role="progressbar"
                      aria-label="Shadow qualification"
                      aria-valuemin="0"
                      aria-valuemax="100"
                      aria-valuenow=${readiness.qualification_percent}
                    >
                      <span
                        style=${`width: ${String(Math.min(100, Math.max(0, readiness.qualification_percent)))}%`}
                      ></span>
                    </div>
                  </div>
                  <dl class="readiness-facts">
                    <div>
                      <dt>Elapsed</dt>
                      <dd>${readiness.elapsed_hours.toFixed(1)} / 24 h</dd>
                    </div>
                    <div>
                      <dt>Decisions</dt>
                      <dd>${readiness.evaluated_decisions} / 20</dd>
                    </div>
                    <div>
                      <dt>Valid</dt>
                      <dd>${readiness.valid_evaluation_percent.toFixed(0)}%</dd>
                    </div>
                    <div>
                      <dt>Transitions</dt>
                      <dd>${readiness.minimum_material_transitions} / 2</dd>
                    </div>
                  </dl>
                  ${
                    readiness.blocking_reasons.length === 0
                      ? nothing
                      : html`<p class="blocking">
                          <strong>Still needed:</strong>
                          ${readiness.blocking_reasons.map((reason) => reason.replaceAll("_", " ")).join(", ")}
                        </p>`
                  }
                  ${
                    readiness.blocking_faults.length === 0
                      ? nothing
                      : html`<p class="fault">
                          <strong>Blocking fault:</strong>
                          ${readiness.blocking_faults.join(", ")}
                        </p>`
                  }`
          }
        </section>
      </div>

      <section class="card timeline-card" aria-labelledby="timeline-heading">
        <div class="card-heading">
          <div>
            <span class="eyebrow">Local day</span>
            <h2 id="timeline-heading">Today</h2>
          </div>
          <span class="provenance-note"
            >Measured · Configured · Calculated</span
          >
        </div>
        <ic-today-timeline
          .timeline=${this.timeline}
          .locale=${this.locale()}
          .temperatureUnit=${this.temperatureUnit()}
        ></ic-today-timeline>
      </section>

      <section class="card activity-preview" aria-labelledby="recent-heading">
        <div class="card-heading">
          <div>
            <span class="eyebrow">Only meaningful changes are recorded</span>
            <h2 id="recent-heading">Recent activity</h2>
          </div>
          <button
            type="button"
            class="text-button"
            @click=${() => this.navigate("activity")}
          >
            View all activity →
          </button>
        </div>
        ${this.renderActivityRecords(data.activity.records.slice(0, 5))}
      </section>
    `;
  }

  private renderZoneSelector(
    zones: ZoneConfiguration[],
  ): TemplateResult | typeof nothing {
    if (zones.length < 2) {
      return nothing;
    }
    return html`<div
      class="zone-tabs"
      role="tablist"
      aria-label="Climate zones"
    >
      ${zones.map(
        (zone) =>
          html`<button
            type="button"
            role="tab"
            aria-selected=${this.selectedZoneId === zone.zone_id}
            class=${this.selectedZoneId === zone.zone_id ? "active" : ""}
            @click=${() => this.selectZone(zone.zone_id)}
          >
            ${zone.name}
          </button>`,
      )}
    </div>`;
  }

  private renderSensors(): TemplateResult {
    const data = this.requireData();
    return html`
      <section class="page-heading">
        <div>
          <span class="eyebrow">Current readings and configured sources</span>
          <h2>Sensors</h2>
        </div>
        <p>
          See which sources each zone uses and whether current readings are
          available. Missing values are never shown as zero.
        </p>
      </section>
      <section class="sensor-summary">
        <article class="summary-tile">
          <strong>${data.observation.usable_temperature_sources}</strong
          ><span>usable temperature sources</span>
        </article>
        <article class="summary-tile">
          <strong>${data.observation.degraded_zone_count}</strong
          ><span>zones needing attention</span>
        </article>
        <article class="summary-tile">
          <strong
            >${data.observation.collection_active ? "Active" : "Stopped"}</strong
          ><span>observation collection</span>
        </article>
      </section>
      <div class="zone-health-grid">
        ${data.configuration.zones.map((zone) => {
          const snapshot = data.snapshot.zones.find(
            (item) => item.zone_id === zone.zone_id,
          );
          const degraded =
            snapshot?.sensor_data_degraded === true ||
            snapshot?.thermostat_data_degraded === true;
          return html`<article class="card zone-health-card">
            <div class="card-heading">
              <div>
                <span class="eyebrow">Zone</span>
                <h3>${zone.name}</h3>
              </div>
              <span class="health-pill ${degraded ? "warning" : "healthy"}"
                >${degraded ? "⚠ Review" : "✓ Healthy"}</span
              >
            </div>
            <div class="sensor-reading">
              <strong
                >${this.temperature(snapshot?.effective_temperature_c ?? null)}</strong
              >
              <span
                >${this.humidity(
                  snapshot?.effective_humidity_pct ?? null,
                  zone.humidity_sources.some((source) => source.enabled),
                )}
                humidity</span
              >
            </div>
            <dl class="source-counts">
              <div>
                <dt>Temperature</dt>
                <dd>${this.enabledSourceCount(zone.temperature_sources)}</dd>
              </div>
              <div>
                <dt>Humidity</dt>
                <dd>${this.enabledSourceCount(zone.humidity_sources)}</dd>
              </div>
              <div>
                <dt>Contacts</dt>
                <dd>
                  ${this.enabledBindingCount(zone.window_door_entity_ids)}
                </dd>
              </div>
              <div>
                <dt>Occupancy</dt>
                <dd>${this.enabledBindingCount(zone.occupancy_entity_ids)}</dd>
              </div>
              <div>
                <dt>HVAC stage</dt>
                <dd>${zone.stage_entity_ids.length}</dd>
              </div>
              <div>
                <dt>Fan</dt>
                <dd>${this.enabledBindingCount(zone.fan_entity_ids)}</dd>
              </div>
            </dl>
            ${snapshot?.sensor_data_degraded === true ? html`<p class="warning-copy">Temperature source data is degraded.</p>` : nothing}
            ${snapshot?.thermostat_data_degraded === true ? html`<p class="warning-copy">Thermostat observation data is degraded.</p>` : nothing}
            ${this.enabledSourceCount(zone.humidity_sources) === 0 ? html`<p class="muted">Humidity is not configured for this zone. Reconfigure the zone to select a humidity sensor or thermostat.</p>` : nothing}
          </article>`;
        })}
      </div>
      <section class="boundary-note">
        <span aria-hidden="true">ⓘ</span>
        <div>
          <strong>History availability</strong>
          <p>${data.observation.history_boundary}</p>
        </div>
      </section>
    `;
  }

  private renderActivity(): TemplateResult {
    const data = this.requireData();
    const records = data.activity.records.filter(
      (record) =>
        this.activityFilter === "all" ||
        record.severity === this.activityFilter,
    );
    return html`
      <section class="page-heading with-action">
        <div>
          <span class="eyebrow">Newest activity first</span>
          <h2>Activity</h2>
          <p>
            Decisions, observations, transitions, warnings, and lifecycle
            events.
          </p>
        </div>
        <label class="filter"
          ><span>Show</span
          ><select .value=${this.activityFilter} @change=${this.filterChanged}>
            <option value="all">All activity</option>
            <option value="warning">Warnings</option>
            <option value="error">Errors</option>
            <option value="info">Information</option>
          </select></label
        >
      </section>
      <section class="card activity-card">
        <p class="record-count">
          Showing ${records.length} of ${data.activity.total} retained records
        </p>
        ${this.renderActivityRecords(records)}
        ${
          data.activity.records.length < data.activity.total
            ? html`<button
                type="button"
                class="load-more"
                ?disabled=${this.activityLoadingOlder}
                @click=${this.loadOlderActivity}
              >
                ${this.activityLoadingOlder ? "Loading…" : "Load older activity"}
              </button>`
            : nothing
        }
      </section>
    `;
  }

  private renderActivityRecords(records: ActivityRecord[]): TemplateResult {
    if (records.length === 0) {
      return html`<div class="empty-state" role="status">
        No matching material activity is available.
      </div>`;
    }
    return html`<ol class="activity-list">
      ${records.map((record) => {
        const zone = this.data?.configuration.zones.find(
          (item) => item.zone_id === record.zone_id,
        );
        return html`<li>
          <span
            class="activity-marker severity-${record.severity}"
            aria-hidden="true"
          ></span>
          <div class="activity-body">
            <div class="activity-title">
              <strong>${humanizeCode(record.activity_type)}</strong
              ><time datetime=${record.timestamp_utc}
                >${this.time(record.timestamp_utc)}</time
              >
            </div>
            <p>${record.explanation}</p>
            <div class="activity-meta">
              <span>${humanizeCode(record.reason_code)}</span
              >${zone === undefined ? nothing : html`<span>${zone.name}</span>`}<span>${record.severity}</span>${this.repairRecordStatus(record)}
            </div>
          </div>
        </li>`;
      })}
    </ol>`;
  }

  private renderSettings(): TemplateResult {
    const data = this.requireData();
    const automationEnabled =
      data.configuration.config["automation_enabled"] === true;
    const safety = data.configuration.options["safety_limits"];
    return html`
      <section class="page-heading">
        <div>
          <span class="eyebrow">Configuration & system health</span>
          <h2>Settings</h2>
        </div>
        <p>
          Manage how information is displayed, review system health, and open
          Home Assistant’s source configuration.
        </p>
      </section>
      <div class="settings-grid">
        <section class="card setting-card">
          <span class="setting-icon" aria-hidden="true">°</span>
          <div>
            <h3>Temperature display</h3>
            <label class="setting-select">
              <span>Use temperatures in</span>
              <select
                .value=${this.temperatureUnitPreference}
                @change=${this.temperatureUnitChanged}
              >
                <option value="home_assistant">Follow Home Assistant</option>
                <option value="fahrenheit">Fahrenheit (°F)</option>
                <option value="celsius">Celsius (°C)</option>
              </select>
            </label>
            <p>
              Applies to temperatures, targets, explanations, and the Today
              timeline in this browser.
            </p>
          </div>
        </section>
        <section class="card setting-card">
          <span class="setting-icon" aria-hidden="true">◉</span>
          <div>
            <h3>Automation</h3>
            <p class="setting-value">
              ${automationEnabled ? "Configured" : "Off"}
            </p>
            <p>
              Observation, activity, and sensor health remain active when
              automation is off.
            </p>
          </div>
        </section>
        <section class="card setting-card">
          <span class="setting-icon" aria-hidden="true">⌁</span>
          <div>
            <h3>Safety limits</h3>
            <p class="setting-value">
              ${typeof safety === "object" && safety !== null ? "Loaded and enforced" : "Unavailable"}
            </p>
            <p>
              Backend validation remains authoritative. The frontend cannot
              lower a gate.
            </p>
          </div>
        </section>
        <section class="card setting-card">
          <span class="setting-icon" aria-hidden="true">↺</span>
          <div>
            <h3>History</h3>
            <p class="setting-value">
              ${data.observation.presentation_history_hours} hours local
            </p>
            <p>
              The Today trace is nonauthoritative presentation data, not
              training data.
            </p>
          </div>
        </section>
        <section class="card setting-card">
          <span class="setting-icon" aria-hidden="true">⚠</span>
          <div>
            <h3>Repairs</h3>
            <p class="setting-value">
              ${data.configuration.active_repairs.length === 0 ? "No active repairs" : `${String(data.configuration.active_repairs.length)} need attention`}
            </p>
            <p>
              Activity retains historical repair events. Only items currently
              listed here are active now.
            </p>
          </div>
        </section>
      </div>
      <section class="card links-card">
        <h3>Home Assistant tools</h3>
        <div class="settings-links">
          <a href="/config/integrations/integration/intelligent_climate"
            ><span aria-hidden="true">⚙</span>
            <div>
              <strong>Integration configuration</strong
              ><small
                >Select humidity, contact, occupancy, stage, fan, and
                temperature sources by reconfiguring a zone</small
              >
            </div>
            <span aria-hidden="true">→</span></a
          >
          <a href="/config/repairs"
            ><span aria-hidden="true">⚠</span>
            <div>
              <strong>Repairs</strong
              ><small>Review issues requiring attention</small>
            </div>
            <span aria-hidden="true">→</span></a
          >
          <a href="/developer-tools/yaml"
            ><span aria-hidden="true">⇩</span>
            <div>
              <strong>Diagnostics</strong
              ><small>Download from the integration device page</small>
            </div>
            <span aria-hidden="true">→</span></a
          >
        </div>
      </section>
      <section class="boundary-note">
        <span aria-hidden="true">🛡</span>
        <div>
          <strong>Read-only preview</strong>
          <p>
            Observe Only and Shadow information is available here. This release
            cannot send commands to your thermostat or fans.
          </p>
        </div>
      </section>
      <details class="card diagnostics-details">
        <summary>Technical diagnostics</summary>
        <p>
          Frontend ${this.panel.config.frontend_version}; API
          v${this.panel.config.api_version}. Invalid or mismatched data is not
          displayed.
        </p>
      </details>
    `;
  }

  private entries(): IntelligentClimatePanelEntry[] {
    return this.panel.config.entries;
  }

  private requireData(): EntryDashboardData {
    if (this.data === undefined) {
      throw new Error("panel data is not loaded");
    }
    return this.data;
  }

  private selectedZone(): ZoneConfiguration | undefined {
    return this.data?.configuration.zones.find(
      (zone) => zone.zone_id === this.selectedZoneId,
    );
  }

  private selectedZoneSnapshot(): ZoneSnapshot | undefined {
    return this.data?.snapshot.zones.find(
      (zone) => zone.zone_id === this.selectedZoneId,
    );
  }

  private locale(): string {
    return this.hass.locale.language;
  }

  private temperatureUnit(): "°C" | "°F" {
    return resolveTemperatureUnit(
      this.temperatureUnitPreference,
      this.hass.config.unit_system.temperature,
    );
  }

  private temperature(value: number | null): string {
    return formatTemperature(value, this.temperatureUnit(), this.locale());
  }

  private humidity(value: number | null, configured = true): string {
    if (!configured) {
      return "Not configured";
    }
    return value === null
      ? "Unavailable"
      : `${new Intl.NumberFormat(this.locale(), { maximumFractionDigits: 1 }).format(value)}%`;
  }

  private time(value: string): string {
    return formatTimestamp(value, this.locale(), this.timeline?.time_zone);
  }

  private enabledSourceCount(sources: ConfiguredSource[]): number {
    return sources.filter((source) => source.enabled).length;
  }

  private enabledBindingCount(bindings: ReviewedBinding[]): number {
    return bindings.filter((binding) => binding.enabled && binding.reviewed)
      .length;
  }

  private renderNarrative(): string {
    const facts = this.narrative;
    if (facts === undefined) {
      return "A current explanation is not available yet.";
    }
    const control: Record<string, string> = {
      observing: "Intelligent Climate is observing only.",
      manual_idle: "Manual Control is selected and automation is off.",
      shadow_qualifying:
        "Scheduled Shadow is evaluating conditions without sending commands.",
      shadow_ready:
        "Scheduled Shadow is ready and is still not sending commands.",
      safe_fallback: "Automatic control is suppressed by Safe Fallback.",
      emergency_paused: "Control is paused.",
      degraded: "Observation is continuing with degraded data.",
      reconciling: "Live state is being checked after startup.",
    };
    const sentences = [
      control[facts.control_state] ??
        `Current status: ${humanizeCode(facts.control_state)}.`,
    ];
    const target = facts.effective_target_c ?? facts.scheduled_target_c;
    if (target !== null) {
      const transition =
        facts.next_transition_utc === null
          ? ""
          : ` until ${this.time(facts.next_transition_utc)}`;
      sentences.push(
        `The current target is ${this.temperature(target)}${transition}.`,
      );
    }
    if (facts.temperature_c !== null) {
      const action =
        facts.hvac_action === null
          ? ""
          : `, and the thermostat reports ${facts.hvac_action}`;
      sentences.push(
        `The zone is ${this.temperature(facts.temperature_c)}${action}.`,
      );
    }
    if (facts.source_degraded) {
      sentences.push("Some current sensor data needs attention.");
    }
    return sentences.join(" ");
  }

  private repairRecordStatus(
    record: ActivityRecord,
  ): TemplateResult | typeof nothing {
    if (!record.activity_type.startsWith("repair_issue_")) {
      return nothing;
    }
    const active =
      this.data?.configuration.active_repairs.includes(record.reason_code) ===
      true;
    return html`<span class=${active ? "repair-active" : "repair-history"}
      >${active ? "Active repair" : "Historical record"}</span
    >`;
  }

  private async initialize(): Promise<void> {
    if (this.panel.config.api_version !== 1) {
      this.loading = false;
      this.errorMessage = `This panel expects API version 1, but received ${String(this.panel.config.api_version)}.`;
      return;
    }
    const first = this.entries()[0];
    if (first === undefined) {
      this.loading = false;
      this.errorMessage =
        "No loaded Intelligent Climate equipment group is available.";
      return;
    }
    this.selectedEntryId = first.entry_id;
    await this.loadEntry(first.entry_id);
  }

  private async loadEntry(entryId: string): Promise<void> {
    const generation = ++this.loadGeneration;
    this.unsubscribe?.();
    this.unsubscribe = undefined;
    this.loading = true;
    this.errorMessage = "";
    this.data = undefined;
    this.timeline = undefined;
    this.narrative = undefined;
    const client = new IntelligentClimateClient(this.hass, entryId);
    this.client = client;
    try {
      const data = await client.dashboardData();
      if (generation !== this.loadGeneration) {
        return;
      }
      this.data = data;
      const firstZone = data.configuration.zones[0];
      this.selectedZoneId = firstZone?.zone_id ?? "";
      if (this.selectedZoneId.length > 0) {
        await this.loadZoneDetails(generation);
      }
      if (generation !== this.loadGeneration) {
        return;
      }
      this.unsubscribe = await client.subscribe((snapshot) => {
        this.applySnapshot(snapshot);
      });
    } catch (error: unknown) {
      if (generation !== this.loadGeneration) {
        return;
      }
      this.errorMessage = this.describeError(error);
    } finally {
      if (generation === this.loadGeneration) {
        this.loading = false;
      }
    }
  }

  private async loadZoneDetails(generation: number): Promise<void> {
    if (this.client === undefined || this.selectedZoneId.length === 0) {
      return;
    }
    const [timeline, narrative] = await Promise.allSettled([
      this.client.todayTimeline(this.selectedZoneId),
      this.client.narrative(this.selectedZoneId),
    ]);
    if (generation !== this.loadGeneration) {
      return;
    }
    this.timeline =
      timeline.status === "fulfilled" ? timeline.value : undefined;
    this.narrative =
      narrative.status === "fulfilled" ? narrative.value : undefined;
  }

  private applySnapshot(snapshot: SnapshotResponse): void {
    if (this.data === undefined || snapshot.entry_id !== this.selectedEntryId) {
      return;
    }
    this.data = { ...this.data, snapshot };
  }

  private describeError(error: unknown): string {
    if (error instanceof FrontendContractError) {
      return `The backend returned data this frontend cannot safely display (${error.message}). Reload the integration or update the candidate.`;
    }
    if (error instanceof Error) {
      return error.message;
    }
    return "An unknown local data error occurred.";
  }

  private navigate(route: PanelRoute): void {
    this.activeRoute = route;
    window.history.replaceState(null, "", `/intelligent-climate/${route}`);
    this.shadowRoot?.querySelector<HTMLElement>("#main-content")?.focus();
  }

  private entryChanged = (event: Event): void => {
    const target = event.currentTarget;
    if (!(target instanceof HTMLSelectElement)) {
      return;
    }
    this.selectedEntryId = target.value;
    void this.loadEntry(target.value);
  };

  private filterChanged = (event: Event): void => {
    const target = event.currentTarget;
    if (target instanceof HTMLSelectElement) {
      this.activityFilter = target.value;
    }
  };

  private temperatureUnitChanged = (event: Event): void => {
    const target = event.currentTarget;
    if (!(target instanceof HTMLSelectElement)) {
      return;
    }
    const value = target.value;
    if (
      value !== "home_assistant" &&
      value !== "fahrenheit" &&
      value !== "celsius"
    ) {
      return;
    }
    this.temperatureUnitPreference = value;
    writeTemperatureUnitPreference(value);
  };

  private loadOlderActivity = async (): Promise<void> => {
    if (
      this.client === undefined ||
      this.data === undefined ||
      this.activityLoadingOlder
    ) {
      return;
    }
    const currentData = this.data;
    const generation = this.loadGeneration;
    this.activityLoadingOlder = true;
    try {
      const page = await this.client.activity(
        currentData.activity.records.length,
        100,
        "newest",
      );
      if (generation !== this.loadGeneration) {
        return;
      }
      const existing = new Set(
        currentData.activity.records.map((record) => record.record_id),
      );
      const records = [
        ...currentData.activity.records,
        ...page.records.filter((record) => !existing.has(record.record_id)),
      ];
      this.data = {
        ...currentData,
        activity: { ...page, offset: 0, records },
      };
    } catch (error: unknown) {
      this.errorMessage = this.describeError(error);
    } finally {
      this.activityLoadingOlder = false;
    }
  };

  private selectZone(zoneId: string): void {
    this.selectedZoneId = zoneId;
    void this.loadZoneDetails(this.loadGeneration);
  }

  private refreshDetails = (): void => {
    void this.loadZoneDetails(this.loadGeneration);
  };

  private retry = (): void => {
    if (this.selectedEntryId.length > 0) {
      void this.loadEntry(this.selectedEntryId);
    } else {
      void this.initialize();
    }
  };

  public static override styles = [
    intelligentClimateTheme,
    css`
      :host {
        display: block;
        min-block-size: 100%;
      }
      .app-shell {
        min-block-size: 100vh;
        background:
          radial-gradient(
            circle at 80% 0%,
            color-mix(in srgb, var(--ic-accent) 10%, transparent),
            transparent 30%
          ),
          var(--lovelace-background, var(--primary-background-color));
      }
      .topbar {
        min-block-size: 86px;
        padding: 14px clamp(16px, 4vw, 48px);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        background: color-mix(in srgb, var(--ic-surface) 92%, transparent);
        border-block-end: 1px solid var(--ic-border);
        backdrop-filter: blur(18px);
      }
      .brand {
        display: flex;
        align-items: center;
        gap: 14px;
      }
      .brand-mark {
        inline-size: 46px;
        block-size: 46px;
        display: grid;
        place-items: center;
        border-radius: 15px;
        background: linear-gradient(
          145deg,
          var(--ic-accent),
          color-mix(in srgb, var(--ic-accent) 55%, #6c5ce7)
        );
        color: white;
        font-weight: 800;
        letter-spacing: -0.04em;
        box-shadow: 0 8px 22px
          color-mix(in srgb, var(--ic-accent) 30%, transparent);
      }
      h1,
      h2,
      h3,
      p {
        margin-block: 0;
      }
      h1 {
        font-size: clamp(1.1rem, 2vw, 1.35rem);
        letter-spacing: -0.025em;
      }
      .brand p,
      .page-heading p {
        color: var(--secondary-text-color);
        font-size: 0.82rem;
        margin-block-start: 3px;
      }
      .entry-picker {
        display: grid;
        gap: 3px;
        font-size: 0.72rem;
        color: var(--secondary-text-color);
      }
      select {
        min-inline-size: 180px;
        border: 1px solid var(--ic-border);
        border-radius: 12px;
        background: var(--ic-surface);
        padding-inline: 12px 36px;
      }
      .entry-name {
        padding: 10px 14px;
        border-radius: 12px;
        background: var(--ic-surface-muted);
        font-weight: 600;
      }
      .primary-nav {
        position: sticky;
        inset-block-start: 0;
        z-index: 4;
        min-block-size: 62px;
        display: flex;
        justify-content: center;
        gap: 4px;
        padding: 8px 16px;
        background: color-mix(in srgb, var(--ic-surface) 94%, transparent);
        border-block-end: 1px solid var(--ic-border);
        backdrop-filter: blur(16px);
      }
      .primary-nav button {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        min-inline-size: 116px;
        border: 0;
        border-radius: 12px;
        background: transparent;
        cursor: pointer;
        font-weight: 600;
        color: var(--secondary-text-color);
      }
      .primary-nav button.active {
        background: color-mix(in srgb, var(--ic-accent) 12%, transparent);
        color: var(--primary-text-color);
        box-shadow: inset 0 -2px var(--ic-accent);
      }
      main {
        max-inline-size: 1480px;
        margin-inline: auto;
        padding: clamp(18px, 3.5vw, 46px);
      }
      .loading {
        min-block-size: 60vh;
        display: grid;
        place-items: center;
        align-content: center;
        gap: 12px;
        color: var(--secondary-text-color);
        text-align: center;
      }
      .loading strong {
        color: var(--primary-text-color);
        font-size: 1.1rem;
      }
      .spinner {
        inline-size: 46px;
        block-size: 46px;
        border-radius: 50%;
        border: 4px solid var(--ic-border);
        border-block-start-color: var(--ic-accent);
        animation: spin 1s linear infinite;
      }
      @keyframes spin {
        to {
          transform: rotate(360deg);
        }
      }
      .error-card {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 20px;
        max-inline-size: 720px;
        margin: 80px auto;
        padding: 30px;
        border: 1px solid
          color-mix(in srgb, var(--error-color, #d93025) 35%, transparent);
        border-radius: var(--ic-radius);
        background: var(--ic-surface);
        box-shadow: var(--ic-shadow);
      }
      .error-icon {
        inline-size: 48px;
        block-size: 48px;
        border-radius: 50%;
        display: grid;
        place-items: center;
        background: color-mix(
          in srgb,
          var(--error-color, #d93025) 15%,
          transparent
        );
        color: var(--error-color, #d93025);
        font-weight: 900;
        font-size: 1.4rem;
      }
      .error-card p {
        margin-block: 8px 20px;
        color: var(--secondary-text-color);
      }
      .primary-button,
      .text-button,
      .icon-button {
        border: 0;
        cursor: pointer;
      }
      .primary-button {
        padding-inline: 18px;
        border-radius: 12px;
        background: var(--ic-accent);
        color: white;
        font-weight: 700;
      }
      .status-hero {
        position: relative;
        overflow: hidden;
        min-block-size: 250px;
        display: grid;
        grid-template-columns: 1fr auto;
        align-items: center;
        gap: 30px;
        padding: clamp(26px, 5vw, 58px);
        border-radius: 28px;
        color: white;
        background: linear-gradient(
          125deg,
          #1c516a 0%,
          #147aa0 52%,
          #0b96ad 100%
        );
        box-shadow: 0 22px 50px rgb(0 78 105 / 20%);
      }
      .status-hero.tone-warning {
        background: linear-gradient(125deg, #5b3b12, #a26011, #c17d18);
      }
      .status-hero.tone-critical {
        background: linear-gradient(125deg, #651f26, #a52d37, #c64545);
      }
      .status-hero.tone-positive {
        background: linear-gradient(125deg, #154f44, #187761, #249a79);
      }
      .status-hero::before {
        content: "";
        position: absolute;
        inset: -60% -10% auto 50%;
        inline-size: 600px;
        block-size: 600px;
        border: 1px solid rgb(255 255 255 / 18%);
        border-radius: 50%;
      }
      .status-copy {
        position: relative;
        z-index: 1;
        max-inline-size: 760px;
      }
      .eyebrow {
        display: block;
        margin-block-end: 7px;
        font-size: 0.72rem;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.13em;
        color: var(--secondary-text-color);
      }
      .status-hero .eyebrow {
        color: rgb(255 255 255 / 72%);
      }
      .status-hero h2 {
        font-size: clamp(1.8rem, 4vw, 3.4rem);
        letter-spacing: -0.055em;
        line-height: 1;
      }
      .status-hero p {
        max-inline-size: 690px;
        margin-block: 18px 22px;
        line-height: 1.55;
        color: rgb(255 255 255 / 85%);
      }
      .status-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 8px;
      }
      .status-meta span {
        padding: 6px 10px;
        border-radius: 999px;
        background: rgb(255 255 255 / 12%);
        font-size: 0.75rem;
      }
      .hero-orbit {
        position: relative;
        z-index: 1;
        inline-size: 150px;
        block-size: 150px;
        display: grid;
        place-items: center;
        align-content: center;
        border-radius: 50%;
        background: rgb(255 255 255 / 10%);
        border: 1px solid rgb(255 255 255 / 22%);
      }
      .orbit-ring {
        position: absolute;
        inset: 12px;
        border: 2px dashed rgb(255 255 255 / 35%);
        border-radius: 50%;
      }
      .orbit-value {
        font-size: 2.8rem;
        font-weight: 800;
        line-height: 1;
      }
      .orbit-label {
        font-size: 0.78rem;
        opacity: 0.8;
      }
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        gap: 14px;
        margin-block: 18px 28px;
      }
      .metric-card {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 12px;
        min-block-size: 96px;
        padding: 16px;
        border: 1px solid var(--ic-border);
        border-radius: 17px;
        background: var(--ic-surface);
        box-shadow: 0 5px 18px rgb(0 0 0 / 5%);
      }
      .metric-icon {
        inline-size: 42px;
        block-size: 42px;
        display: grid;
        place-items: center;
        border-radius: 13px;
        background: color-mix(in srgb, var(--ic-accent) 12%, transparent);
        color: var(--ic-accent);
        font-weight: 800;
      }
      .metric-icon.humidity {
        color: #5b6ee1;
        background: rgb(91 110 225 / 12%);
      }
      .metric-icon.source {
        color: #18815f;
        background: rgb(24 129 95 / 12%);
      }
      .metric-icon.history {
        color: #ad6a13;
        background: rgb(173 106 19 / 12%);
      }
      .metric-card div span {
        display: block;
        color: var(--secondary-text-color);
        font-size: 0.72rem;
      }
      .metric-card div strong {
        display: block;
        margin-block-start: 4px;
        font-size: 0.87rem;
      }
      .metric-card b {
        font-size: 1.25rem;
      }
      .zone-tabs {
        display: flex;
        gap: 8px;
        margin-block-end: 18px;
        overflow-x: auto;
      }
      .zone-tabs button {
        padding-inline: 18px;
        border: 1px solid var(--ic-border);
        border-radius: 999px;
        background: var(--ic-surface);
        cursor: pointer;
        white-space: nowrap;
      }
      .zone-tabs button.active {
        color: white;
        border-color: var(--ic-accent);
        background: var(--ic-accent);
        font-weight: 700;
      }
      .overview-grid {
        display: grid;
        grid-template-columns: minmax(0, 1.25fr) minmax(320px, 0.75fr);
        gap: 18px;
      }
      .card {
        padding: clamp(20px, 3vw, 30px);
        border: 1px solid var(--ic-border);
        border-radius: var(--ic-radius);
        background: var(--ic-surface);
        box-shadow: var(--ic-shadow);
      }
      .card-heading {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 18px;
        margin-block-end: 18px;
      }
      .card-heading h2 {
        font-size: 1.18rem;
        letter-spacing: -0.02em;
      }
      .card-heading h3 {
        font-size: 1.05rem;
      }
      .icon-button {
        inline-size: 44px;
        border-radius: 12px;
        background: var(--ic-surface-muted);
        font-size: 1.2rem;
      }
      .narrative {
        font-size: clamp(1.05rem, 1.8vw, 1.35rem);
        line-height: 1.65;
        letter-spacing: -0.015em;
      }
      .fact-chips {
        display: flex;
        flex-wrap: wrap;
        gap: 7px;
        margin-block-start: 20px;
      }
      .fact-chips span,
      .activity-meta span {
        padding: 5px 9px;
        border: 1px solid var(--ic-border);
        border-radius: 999px;
        color: var(--secondary-text-color);
        font-size: 0.7rem;
        text-transform: capitalize;
      }
      .muted {
        color: var(--secondary-text-color);
        line-height: 1.5;
      }
      .readiness-state,
      .health-pill {
        padding: 7px 10px;
        border-radius: 999px;
        font-size: 0.72rem;
        font-weight: 800;
        white-space: nowrap;
      }
      .readiness-state.waiting {
        color: #a35e0b;
        background: rgb(210 125 16 / 13%);
      }
      .readiness-state.ready,
      .health-pill.healthy {
        color: #137255;
        background: rgb(24 129 95 / 13%);
      }
      .health-pill.warning {
        color: #a35e0b;
        background: rgb(210 125 16 / 13%);
      }
      .progress-label {
        display: flex;
        justify-content: space-between;
        font-size: 0.82rem;
      }
      .progress {
        overflow: hidden;
        block-size: 9px;
        margin-block: 8px 20px;
        border-radius: 999px;
        background: var(--ic-surface-muted);
      }
      .progress span {
        display: block;
        block-size: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, var(--ic-accent), #2ec39b);
      }
      .readiness-facts,
      .source-counts {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 10px;
        margin: 0;
      }
      .readiness-facts div,
      .source-counts div {
        padding: 12px;
        border-radius: 12px;
        background: var(--ic-surface-muted);
      }
      dt {
        color: var(--secondary-text-color);
        font-size: 0.7rem;
      }
      dd {
        margin: 4px 0 0;
        font-weight: 700;
      }
      .blocking,
      .fault {
        margin-block-start: 14px;
        font-size: 0.78rem;
        color: var(--secondary-text-color);
      }
      .fault {
        color: var(--error-color, #d93025);
      }
      .timeline-card,
      .activity-preview {
        margin-block-start: 18px;
      }
      .provenance-note {
        color: var(--secondary-text-color);
        font-size: 0.76rem;
      }
      .text-button {
        padding-inline: 12px;
        border-radius: 10px;
        background: transparent;
        color: var(--ic-accent);
        font-weight: 700;
      }
      .page-heading {
        display: flex;
        align-items: end;
        justify-content: space-between;
        gap: 24px;
        margin-block: 8px 28px;
      }
      .page-heading h2 {
        font-size: clamp(1.8rem, 4vw, 2.8rem);
        letter-spacing: -0.05em;
      }
      .page-heading p {
        max-inline-size: 630px;
        line-height: 1.5;
      }
      .sensor-summary {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 14px;
        margin-block-end: 18px;
      }
      .summary-tile {
        display: grid;
        gap: 4px;
        padding: 20px;
        border-radius: 16px;
        background: var(--ic-surface-muted);
      }
      .summary-tile strong {
        font-size: 1.55rem;
      }
      .summary-tile span {
        color: var(--secondary-text-color);
        font-size: 0.8rem;
      }
      .zone-health-grid,
      .settings-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 18px;
      }
      .sensor-reading {
        display: flex;
        align-items: baseline;
        gap: 12px;
        margin-block: 10px 18px;
      }
      .sensor-reading strong {
        font-size: 2rem;
        letter-spacing: -0.04em;
      }
      .sensor-reading span {
        color: var(--secondary-text-color);
      }
      .source-counts {
        grid-template-columns: repeat(5, 1fr);
      }
      .source-counts div {
        text-align: center;
        padding: 10px 5px;
      }
      .warning-copy {
        margin-block-start: 12px;
        color: #a35e0b;
        font-size: 0.8rem;
      }
      .boundary-note {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 14px;
        margin-block-start: 18px;
        padding: 18px 20px;
        border: 1px solid
          color-mix(in srgb, var(--ic-accent) 24%, var(--ic-border));
        border-radius: 15px;
        background: color-mix(in srgb, var(--ic-accent) 7%, var(--ic-surface));
      }
      .boundary-note > span {
        font-size: 1.35rem;
      }
      .boundary-note p {
        margin-block-start: 4px;
        color: var(--secondary-text-color);
        font-size: 0.82rem;
        line-height: 1.45;
      }
      .filter {
        display: grid;
        gap: 4px;
        color: var(--secondary-text-color);
        font-size: 0.72rem;
      }
      .record-count {
        margin-block-end: 20px;
        color: var(--secondary-text-color);
        font-size: 0.78rem;
      }
      .activity-list {
        list-style: none;
        margin: 0;
        padding: 0;
      }
      .load-more {
        min-block-size: 44px;
        display: block;
        margin: 18px auto 0;
        padding-inline: 18px;
        border: 1px solid var(--ic-border);
        border-radius: 12px;
        background: var(--ic-surface-muted);
        color: var(--primary-text-color);
        font: inherit;
        font-weight: 650;
        cursor: pointer;
      }
      .load-more:disabled {
        cursor: wait;
        opacity: 0.65;
      }
      .activity-list li {
        display: grid;
        grid-template-columns: 16px 1fr;
        gap: 12px;
        position: relative;
        padding-block: 2px 22px;
      }
      .activity-list li:not(:last-child)::before {
        content: "";
        position: absolute;
        inset-inline-start: 6px;
        inset-block: 16px 0;
        inline-size: 2px;
        background: var(--ic-border);
      }
      .activity-marker {
        position: relative;
        z-index: 1;
        inline-size: 14px;
        block-size: 14px;
        margin-block-start: 4px;
        border: 3px solid var(--ic-surface);
        border-radius: 50%;
        background: var(--ic-accent);
        box-shadow: 0 0 0 1px var(--ic-accent);
      }
      .activity-marker.severity-warning {
        background: #d17c0d;
        box-shadow: 0 0 0 1px #d17c0d;
      }
      .activity-marker.severity-error {
        background: var(--error-color, #d93025);
        box-shadow: 0 0 0 1px var(--error-color, #d93025);
      }
      .activity-title {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        text-transform: capitalize;
      }
      .activity-title time {
        color: var(--secondary-text-color);
        font-size: 0.76rem;
        white-space: nowrap;
      }
      .activity-body p {
        margin-block: 6px 10px;
        color: var(--secondary-text-color);
        font-size: 0.85rem;
        line-height: 1.5;
      }
      .activity-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
      }
      .repair-active,
      .repair-history {
        border-radius: 999px;
        padding: 2px 8px;
        font-weight: 650;
      }
      .repair-active {
        background: color-mix(in srgb, var(--error-color) 14%, transparent);
        color: var(--error-color);
      }
      .repair-history {
        background: var(--ic-surface-muted);
      }
      .empty-state {
        min-block-size: 180px;
        display: grid;
        place-items: center;
        color: var(--secondary-text-color);
        text-align: center;
      }
      .setting-card {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 16px;
      }
      .setting-icon {
        inline-size: 44px;
        block-size: 44px;
        display: grid;
        place-items: center;
        border-radius: 13px;
        background: color-mix(in srgb, var(--ic-accent) 12%, transparent);
        color: var(--ic-accent);
        font-size: 1.2rem;
      }
      .setting-card h3 {
        font-size: 1rem;
      }
      .setting-card p {
        margin-block-start: 7px;
        color: var(--secondary-text-color);
        font-size: 0.82rem;
        line-height: 1.45;
      }
      .setting-card .setting-value {
        color: var(--primary-text-color);
        font-weight: 700;
      }
      .setting-select {
        display: grid;
        gap: 6px;
        margin-block: 8px;
        color: var(--secondary-text-color);
        font-size: 0.82rem;
      }
      .setting-select select {
        inline-size: 100%;
      }
      .diagnostics-details {
        margin-block-start: 18px;
      }
      .diagnostics-details p {
        color: var(--secondary-text-color);
        padding-block-start: 10px;
      }
      .links-card {
        margin-block-start: 18px;
      }
      .settings-links {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        margin-block-start: 16px;
      }
      .settings-links a {
        display: grid;
        grid-template-columns: auto 1fr auto;
        align-items: center;
        gap: 12px;
        padding: 14px;
        border: 1px solid var(--ic-border);
        border-radius: 13px;
        color: inherit;
        text-decoration: none;
      }
      .settings-links a:hover {
        border-color: var(--ic-accent);
        background: color-mix(in srgb, var(--ic-accent) 5%, transparent);
      }
      .settings-links small {
        display: block;
        margin-block-start: 3px;
        color: var(--secondary-text-color);
      }
      @media (max-width: 980px) {
        .metric-grid {
          grid-template-columns: repeat(2, 1fr);
        }
        .overview-grid {
          grid-template-columns: 1fr;
        }
        .source-counts {
          grid-template-columns: repeat(3, 1fr);
        }
        .settings-links {
          grid-template-columns: 1fr;
        }
      }
      @media (max-width: 700px) {
        .topbar {
          align-items: flex-start;
        }
        .brand p {
          display: none;
        }
        .entry-name {
          display: none;
        }
        .primary-nav {
          justify-content: stretch;
          overflow-x: auto;
        }
        .primary-nav button {
          min-inline-size: 88px;
          flex: 1;
          flex-direction: column;
          gap: 2px;
          font-size: 0.72rem;
        }
        main {
          padding: 16px;
        }
        .status-hero {
          grid-template-columns: 1fr;
          min-block-size: auto;
          border-radius: 22px;
        }
        .hero-orbit {
          display: none;
        }
        .status-hero h2 {
          font-size: 2rem;
        }
        .metric-grid,
        .sensor-summary,
        .zone-health-grid,
        .settings-grid {
          grid-template-columns: 1fr;
        }
        .metric-card {
          min-block-size: 82px;
        }
        .page-heading,
        .page-heading.with-action {
          align-items: stretch;
          flex-direction: column;
        }
        .source-counts {
          grid-template-columns: repeat(2, 1fr);
        }
        .card {
          padding: 20px;
        }
        .activity-title {
          flex-direction: column;
          gap: 3px;
        }
      }
      @media (max-width: 380px) {
        .topbar {
          padding-inline: 12px;
        }
        .brand-mark {
          inline-size: 40px;
          block-size: 40px;
        }
        .brand h1 {
          font-size: 1rem;
        }
        .entry-picker select {
          min-inline-size: 130px;
          max-inline-size: 150px;
        }
        .metric-card {
          grid-template-columns: auto 1fr;
        }
        .metric-card b {
          grid-column: 2;
        }
      }
    `,
  ];
}

if (!customElements.get("intelligent-climate-panel")) {
  customElements.define("intelligent-climate-panel", IntelligentClimatePanel);
}

declare global {
  interface HTMLElementTagNameMap {
    "intelligent-climate-panel": IntelligentClimatePanel;
  }
}
