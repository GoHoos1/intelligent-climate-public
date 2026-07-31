import { LitElement, css, html, nothing, type PropertyValues } from "lit";

import { formatTemperature, formatTimestamp } from "../accessibility/semantics";
import type {
  TimelineSample,
  TimelineSeries,
  TodayTimelineResponse,
} from "../types/contracts";

interface ChartPoint {
  x: number;
  y: number;
}

interface RenderedSeries {
  kind: string;
  valueKind: string;
  label: string;
  className: string;
  path: string;
  latest: number | string;
  coverage: string;
  gaps: number;
}

const LABELS: Record<string, string> = {
  effective_temperature: "Indoor temperature",
  effective_humidity: "Indoor humidity",
  outdoor_temperature: "Outdoor temperature",
  scheduled_target: "Scheduled target",
  scheduled_heat_target: "Scheduled heat target",
  scheduled_cool_target: "Scheduled cool target",
  effective_target: "Effective target",
  effective_heat_target: "Effective heat target",
  effective_cool_target: "Effective cool target",
  hvac_action: "HVAC action",
  fan_action: "Fan action",
};

function label(kind: string): string {
  return LABELS[kind] ?? kind.replaceAll("_", " ");
}

function numericSamples(
  series: TimelineSeries,
): (TimelineSample & { value: number })[] {
  return series.samples.filter(
    (sample): sample is TimelineSample & { value: number } =>
      typeof sample.value === "number",
  );
}

function pathFor(points: ChartPoint[], stepped: boolean): string {
  if (points.length === 0) {
    return "";
  }
  const first = points[0];
  if (first === undefined) {
    return "";
  }
  let path = `M ${first.x.toFixed(2)} ${first.y.toFixed(2)}`;
  for (const point of points.slice(1)) {
    path += stepped
      ? ` H ${point.x.toFixed(2)} V ${point.y.toFixed(2)}`
      : ` L ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
  }
  return path;
}

export class IntelligentClimateTodayTimeline extends LitElement {
  public static override properties = {
    timeline: { attribute: false },
    locale: { type: String },
    temperatureUnit: { type: String, attribute: "temperature-unit" },
  };

  declare public timeline: TodayTimelineResponse | undefined;
  public locale = "en-US";
  public temperatureUnit: "°C" | "°F" = "°C";

  protected override updated(changed: PropertyValues<this>): void {
    if (changed.has("timeline")) {
      this.setAttribute(
        "aria-label",
        this.timeline === undefined
          ? "Today climate timeline unavailable"
          : `Today climate timeline for ${this.timeline.local_date}`,
      );
    }
  }

  protected override render() {
    if (this.timeline === undefined) {
      return html`<div class="empty" role="status">
        Today’s timeline is not available yet. Observation continues normally.
      </div>`;
    }
    const timeline = this.timeline;
    const rendered = this.renderedSeries(timeline);
    const hasChartHistory = timeline.series.some(
      (series) => series.unit !== "%" && numericSamples(series).length >= 2,
    );
    const stateSeries = timeline.series.filter((series) =>
      ["hvac_action", "fan_action"].includes(series.kind),
    );
    const cursor = this.currentCursor(timeline);
    return html`
      <div class="legend" aria-label="Timeline legend">
        ${rendered.map(
          (series) =>
            html`<span class="legend-item">
              <span
                class="swatch ${series.className}"
                aria-hidden="true"
              ></span>
              ${series.label}
              <small>${series.valueKind}</small>
            </span>`,
        )}
      </div>
      ${
        rendered.length === 0
          ? html`<div class="empty" role="status">
              No numeric observations yet.
            </div>`
          : !hasChartHistory
            ? html`<div class="empty collecting" role="status">
                <div>
                  <strong>Collecting climate history</strong>
                  <p>
                    The first useful chart will appear after at least two
                    observations. Current readings are already available above.
                  </p>
                </div>
              </div>`
            : html`<div class="chart-wrap">
                <svg
                  viewBox="0 0 1000 300"
                  role="img"
                  aria-labelledby="timeline-title timeline-description"
                >
                  <title id="timeline-title">
                    Today climate observations and targets
                  </title>
                  <desc id="timeline-description">
                    Solid lines are measured. Dashed lines are configured.
                    Dotted lines are calculated. Exact values follow in the
                    accessible table.
                  </desc>
                  <g class="grid" aria-hidden="true">
                    ${[40, 95, 150, 205, 260].map(
                      (y) =>
                        html`<line x1="55" x2="970" y1=${y} y2=${y}></line>`,
                    )}
                    ${[55, 284, 513, 742, 970].map(
                      (x) =>
                        html`<line x1=${x} x2=${x} y1="40" y2="260"></line>`,
                    )}
                  </g>
                  ${rendered.map(
                    (series) =>
                      html`<path
                        class="series ${series.className}"
                        d=${series.path}
                        vector-effect="non-scaling-stroke"
                      ></path>`,
                  )}
                  ${
                    cursor === null
                      ? nothing
                      : html`<line
                          class="now"
                          x1=${cursor}
                          x2=${cursor}
                          y1="35"
                          y2="265"
                          vector-effect="non-scaling-stroke"
                        ></line>`
                  }
                  ${timeline.annotations.map((annotation) => {
                    const x = this.xPosition(
                      Date.parse(annotation.timestamp_utc),
                      timeline,
                    );
                    return html`<g class="annotation" aria-hidden="true">
                      <circle cx=${x} cy="28" r="6"></circle>
                      <line x1=${x} x2=${x} y1="34" y2="46"></line>
                    </g>`;
                  })}
                  <g class="axis-labels" aria-hidden="true">
                    <text x="55" y="288">12 AM</text>
                    <text x="513" y="288" text-anchor="middle">12 PM</text>
                    <text x="970" y="288" text-anchor="end">12 AM</text>
                  </g>
                </svg>
              </div>`
      }
      ${
        stateSeries.length === 0
          ? nothing
          : html`<div class="state-bands" aria-label="Equipment state timeline">
              ${stateSeries.map(
                (series) =>
                  html`<div class="state-row">
                    <strong>${label(series.kind)}</strong>
                    <div>
                      ${series.samples.map(
                        (sample) =>
                          html`<span class="state-chip">
                            ${formatTimestamp(
                              sample.timestamp_utc,
                              this.locale,
                              this.timeline?.time_zone,
                            )}:
                            ${String(sample.value)}
                          </span>`,
                      )}
                    </div>
                  </div>`,
              )}
            </div>`
      }
      <p class="capability">${timeline.capability_statement}</p>
      <details>
        <summary>Accessible timeline data</summary>
        <div class="table-scroll">
          <table>
            <caption>
              Latest factual value and coverage for each available series
            </caption>
            <thead>
              <tr>
                <th scope="col">Series</th>
                <th scope="col">Provenance</th>
                <th scope="col">Latest</th>
                <th scope="col">Coverage</th>
                <th scope="col">Gaps</th>
              </tr>
            </thead>
            <tbody>
              ${rendered.map(
                (series) =>
                  html`<tr>
                    <th scope="row">${series.label}</th>
                    <td>${series.valueKind}</td>
                    <td>${this.latestValue(series)}</td>
                    <td>${series.coverage}</td>
                    <td>${series.gaps}</td>
                  </tr>`,
              )}
            </tbody>
          </table>
        </div>
      </details>
    `;
  }

  private renderedSeries(timeline: TodayTimelineResponse): RenderedSeries[] {
    const numeric = timeline.series.filter(
      (series) => numericSamples(series).length > 0 && series.unit !== "%",
    );
    const indoorValues = numeric
      .filter((series) => series.kind !== "outdoor_temperature")
      .flatMap((series) =>
        numericSamples(series).map((sample) => sample.value),
      );
    const outdoorValues = numeric
      .filter((series) => series.kind === "outdoor_temperature")
      .flatMap((series) =>
        numericSamples(series).map((sample) => sample.value),
      );
    const indoorRange = this.range(indoorValues);
    const outdoorRange = this.range(outdoorValues);
    return numeric.map((series) => {
      const samples = numericSamples(series);
      const range =
        series.kind === "outdoor_temperature" ? outdoorRange : indoorRange;
      const points = samples.map((sample) => ({
        x: this.xPosition(Date.parse(sample.timestamp_utc), timeline),
        y: this.yPosition(sample.value, range),
      }));
      const latest = samples.at(-1);
      if (latest === undefined) {
        throw new Error("validated timeline series unexpectedly empty");
      }
      return {
        kind: series.kind,
        valueKind: series.value_kind,
        label: label(series.kind),
        className: `${series.value_kind} ${series.kind}`,
        path: pathFor(points, series.value_kind !== "measured"),
        latest: latest.value,
        coverage: `${formatTimestamp(
          series.coverage_start_utc,
          this.locale,
          timeline.time_zone,
        )} – ${formatTimestamp(
          series.coverage_end_utc,
          this.locale,
          timeline.time_zone,
        )}`,
        gaps: series.missing_intervals.length,
      };
    });
  }

  private range(values: number[]): readonly [number, number] {
    if (values.length === 0) {
      return [0, 1];
    }
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const padding = Math.max((maximum - minimum) * 0.15, 0.5);
    return [minimum - padding, maximum + padding];
  }

  private xPosition(
    timestamp: number,
    timeline: TodayTimelineResponse,
  ): number {
    const start = Date.parse(timeline.day_start_utc);
    const end = Date.parse(timeline.day_end_utc);
    return 55 + ((timestamp - start) / (end - start)) * 915;
  }

  private yPosition(value: number, range: readonly [number, number]): number {
    const [minimum, maximum] = range;
    return 260 - ((value - minimum) / (maximum - minimum)) * 220;
  }

  private currentCursor(timeline: TodayTimelineResponse): number | null {
    const now = Date.now();
    if (
      now < Date.parse(timeline.day_start_utc) ||
      now > Date.parse(timeline.day_end_utc)
    ) {
      return null;
    }
    return this.xPosition(now, timeline);
  }

  private latestValue(series: RenderedSeries): string {
    if (typeof series.latest !== "number") {
      return series.latest;
    }
    return formatTemperature(series.latest, this.temperatureUnit, this.locale);
  }

  public static override styles = css`
    :host {
      display: block;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 18px;
      margin-block: 4px 16px;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 7px;
      font-size: 0.84rem;
    }
    .legend-item small {
      color: var(--secondary-text-color);
      text-transform: capitalize;
    }
    .swatch {
      inline-size: 28px;
      border-block-start: 3px solid var(--ic-accent);
    }
    .swatch.configured {
      border-block-start-style: dashed;
    }
    .swatch.calculated {
      border-block-start-style: dotted;
    }
    .chart-wrap {
      overflow: hidden;
      min-block-size: 220px;
    }
    svg {
      display: block;
      inline-size: 100%;
      min-inline-size: 620px;
      block-size: auto;
    }
    .grid line {
      stroke: var(--divider-color, #d8dde3);
      stroke-width: 1;
    }
    .series {
      fill: none;
      stroke: var(--ic-accent);
      stroke-width: 3;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .series.configured {
      stroke-dasharray: 14 8;
      stroke: var(--warning-color, #d97706);
    }
    .series.calculated {
      stroke-dasharray: 3 7;
      stroke: var(--success-color, #1f9d68);
    }
    .series.outdoor_temperature {
      stroke: var(--secondary-text-color, #667085);
      stroke-dasharray: 18 7;
      stroke-width: 2;
    }
    .now {
      stroke: var(--error-color, #d93025);
      stroke-width: 2;
    }
    .annotation circle,
    .annotation line {
      fill: var(--warning-color, #d97706);
      stroke: var(--warning-color, #d97706);
    }
    .axis-labels {
      fill: var(--secondary-text-color, #667085);
      font-size: 24px;
    }
    .state-bands {
      display: grid;
      gap: 8px;
      margin-block: 12px;
    }
    .state-row {
      display: grid;
      grid-template-columns: minmax(100px, 150px) 1fr;
      gap: 10px;
      align-items: start;
      font-size: 0.82rem;
    }
    .state-chip {
      display: inline-block;
      margin: 0 6px 6px 0;
      padding: 4px 8px;
      border: 1px solid var(--divider-color, #d8dde3);
      border-radius: 999px;
    }
    .capability,
    .empty {
      color: var(--secondary-text-color, #667085);
      font-size: 0.9rem;
    }
    .empty {
      min-block-size: 180px;
      display: grid;
      place-items: center;
      border: 1px dashed var(--divider-color, #d8dde3);
      border-radius: 14px;
      text-align: center;
      padding: 24px;
    }
    .empty.collecting {
      min-block-size: 96px;
    }
    .empty.collecting p {
      margin: 6px 0 0;
    }
    summary {
      min-block-size: 44px;
      display: flex;
      align-items: center;
      cursor: pointer;
      font-weight: 600;
    }
    .table-scroll {
      overflow-x: auto;
    }
    table {
      inline-size: 100%;
      border-collapse: collapse;
      font-size: 0.84rem;
    }
    caption {
      text-align: start;
      color: var(--secondary-text-color, #667085);
      margin-block-end: 8px;
    }
    th,
    td {
      padding: 10px;
      border-block-end: 1px solid var(--divider-color, #d8dde3);
      text-align: start;
      white-space: nowrap;
    }
    @media (max-width: 700px) {
      .chart-wrap {
        overflow-x: auto;
      }
      .state-row {
        grid-template-columns: 1fr;
      }
    }
  `;
}

if (!customElements.get("ic-today-timeline")) {
  customElements.define("ic-today-timeline", IntelligentClimateTodayTimeline);
}

declare global {
  interface HTMLElementTagNameMap {
    "ic-today-timeline": IntelligentClimateTodayTimeline;
  }
}
