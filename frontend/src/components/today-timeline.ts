import { LitElement, css, html, nothing, svg, type PropertyValues } from "lit";

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

interface ChartWindow {
  start: number;
  end: number;
}

interface RenderedSeries {
  kind: string;
  valueKind: string;
  label: string;
  className: string;
  path: string;
  points: readonly ChartPoint[];
  latest: number | string;
  latestTimestamp: string;
  sampleCount: number;
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
  hvac_action: "HVAC operation",
  fan_action: "Fan-only circulation",
};

const STATE_LABELS: Record<string, string> = {
  off: "Off",
  idle: "Idle",
  heating: "Heating",
  cooling: "Cooling",
  drying: "Drying",
  fan: "Fan only",
  on: "On",
  not_reported: "Not reported",
  unavailable: "Unavailable",
  unknown: "Unknown (older sample)",
};

const PLOT_TOP = 30;
const PLOT_BOTTOM = 155;
const PLOT_HEIGHT = PLOT_BOTTOM - PLOT_TOP;
const GRID_Y_POSITIONS = [30, 61.25, 92.5, 123.75, 155] as const;
const EARLY_WINDOW_PADDING_MS = 5 * 60 * 1000;
const MINIMUM_EARLY_WINDOW_MS = 15 * 60 * 1000;

function label(kind: string): string {
  return LABELS[kind] ?? kind.replaceAll("_", " ");
}

function stateLabel(value: number | string): string {
  return typeof value === "string"
    ? (STATE_LABELS[value] ?? label(value))
    : String(value);
}

function collapseStateSamples(samples: TimelineSample[]): TimelineSample[] {
  return samples.filter(
    (sample, index) =>
      index === 0 || samples[index - 1]?.value !== sample.value,
  );
}

function derivedAirHandlerState(value: number | string): string {
  switch (value) {
    case "heating":
      return "Running with heating";
    case "cooling":
      return "Running with cooling";
    case "drying":
      return "Running with drying";
    case "fan":
      return "Running fan only";
    case "off":
    case "idle":
      return "Not running";
    default:
      return stateLabel(value);
  }
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
    const chartRange = this.temperatureRange(timeline);
    const chartWindow = this.chartWindow(timeline);
    const rendered = this.renderedSeries(timeline, chartRange, chartWindow);
    const indoorSeries = rendered.find(
      (series) => series.kind === "effective_temperature",
    );
    const collectedSamples = indoorSeries?.sampleCount ?? 0;
    const hasChartHistory = collectedSamples >= 2;
    const stateSeries = timeline.series.filter((series) =>
      ["hvac_action", "fan_action"].includes(series.kind),
    );
    const cursor = this.currentCursor(chartWindow);
    const axisTimes = this.axisTimes(chartWindow, timeline);
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
                    ${collectedSamples} of 2 temperature samples collected. The
                    chart will appear after the next observation.
                  </p>
                  ${this.sampleSummary(indoorSeries)}
                </div>
              </div>`
            : html`<div class="chart-wrap">
                <svg
                  viewBox="0 0 1000 210"
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
                    ${GRID_Y_POSITIONS.map(
                      (y) =>
                        svg`<line x1="80" x2="970" y1=${y} y2=${y}></line>`,
                    )}
                    ${[80, 303, 525, 748, 970].map(
                      (x) =>
                        svg`<line
                          x1=${x}
                          x2=${x}
                          y1=${PLOT_TOP}
                          y2=${PLOT_BOTTOM}
                        ></line>`,
                    )}
                  </g>
                  <g class="y-axis-labels" aria-hidden="true">
                    ${GRID_Y_POSITIONS.map((y, index) => {
                      const [minimum, maximum] = chartRange;
                      const value = maximum - ((maximum - minimum) * index) / 4;
                      return svg`<text x="72" y=${y + 6} text-anchor="end">
                        ${formatTemperature(
                          value,
                          this.temperatureUnit,
                          this.locale,
                        )}
                      </text>`;
                    })}
                  </g>
                  ${rendered.map(
                    (series) =>
                      svg`<g class="series-group ${series.className}">
                        <path
                          class="series ${series.className}"
                          d=${series.path}
                        ></path>
                        ${
                          series.kind === "effective_temperature"
                            ? series.points.map(
                                (point) =>
                                  svg`<circle
                                    class="sample-point measured-temperature"
                                    cx=${point.x}
                                    cy=${point.y}
                                    r="4.5"
                                  ></circle>`,
                              )
                            : nothing
                        }
                      </g>`,
                  )}
                  ${
                    cursor === null
                      ? nothing
                      : svg`<line
                          class="now"
                          x1=${cursor}
                          x2=${cursor}
                          y1=${PLOT_TOP - 5}
                          y2=${PLOT_BOTTOM + 5}
                        ></line>`
                  }
                  ${timeline.annotations.map((annotation) => {
                    const x = this.xPosition(
                      Date.parse(annotation.timestamp_utc),
                      chartWindow,
                    );
                    return svg`<g class="annotation" aria-hidden="true">
                      <circle cx=${x} cy="15" r="6"></circle>
                      <line x1=${x} x2=${x} y1="21" y2=${PLOT_TOP + 6}></line>
                    </g>`;
                  })}
                  <g class="axis-labels" aria-hidden="true">
                    <text x="80" y="198">${axisTimes[0]}</text>
                    <text x="525" y="198" text-anchor="middle">
                      ${axisTimes[1]}
                    </text>
                    <text x="970" y="198" text-anchor="end">
                      ${axisTimes[2]}
                    </text>
                  </g>
                </svg>
                ${this.sampleSummary(indoorSeries)}
              </div>`
      }
      ${
        stateSeries.length === 0
          ? nothing
          : html`<div class="state-bands" aria-label="Equipment state timeline">
              ${stateSeries.map((series) => this.renderStateSeries(series))}
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

  private renderedSeries(
    timeline: TodayTimelineResponse,
    chartRange: readonly [number, number],
    chartWindow: ChartWindow,
  ): RenderedSeries[] {
    const numeric = timeline.series.filter(
      (series) => numericSamples(series).length > 0 && series.unit !== "%",
    );
    return numeric.map((series) => {
      const samples = numericSamples(series);
      const points = samples.map((sample) => ({
        x: this.xPosition(Date.parse(sample.timestamp_utc), chartWindow),
        y: this.yPosition(sample.value, chartRange),
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
        points,
        latest: latest.value,
        latestTimestamp: latest.timestamp_utc,
        sampleCount: samples.length,
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

  private temperatureRange(
    timeline: TodayTimelineResponse,
  ): readonly [number, number] {
    return this.range(
      timeline.series
        .filter((series) => series.unit === "°C")
        .flatMap((series) =>
          numericSamples(series).map((sample) => sample.value),
        ),
    );
  }

  private sampleSummary(
    series: RenderedSeries | undefined,
  ): ReturnType<typeof html> | typeof nothing {
    if (series === undefined) {
      return nothing;
    }
    return html`<p class="sample-summary">
      Latest sample
      ${formatTimestamp(
        series.latestTimestamp,
        this.locale,
        this.timeline?.time_zone,
      )}
      · Source: effective zone temperature
    </p>`;
  }

  private renderStateSeries(series: TimelineSeries): ReturnType<typeof html> {
    const samples = collapseStateSamples(series.samples);
    return html`<div class="state-row">
        <strong>${label(series.kind)}</strong>
        <div>
          ${samples.map(
            (sample) =>
              html`<span class="state-chip">
                ${this.stateTimestamp(sample)}: ${stateLabel(sample.value)}
              </span>`,
          )}
        </div>
      </div>
      ${
        series.kind === "hvac_action"
          ? html`<div class="state-row derived">
              <strong>Air handler <small>derived</small></strong>
              <div>
                ${samples.map(
                  (sample) =>
                    html`<span class="state-chip">
                      ${this.stateTimestamp(sample)}:
                      ${derivedAirHandlerState(sample.value)}
                    </span>`,
                )}
              </div>
            </div>`
          : nothing
      }`;
  }

  private stateTimestamp(sample: TimelineSample): string {
    return formatTimestamp(
      sample.timestamp_utc,
      this.locale,
      this.timeline?.time_zone,
    );
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

  private xPosition(timestamp: number, chartWindow: ChartWindow): number {
    return (
      80 +
      ((timestamp - chartWindow.start) /
        (chartWindow.end - chartWindow.start)) *
        890
    );
  }

  private yPosition(value: number, range: readonly [number, number]): number {
    const [minimum, maximum] = range;
    return (
      PLOT_BOTTOM - ((value - minimum) / (maximum - minimum)) * PLOT_HEIGHT
    );
  }

  private currentCursor(chartWindow: ChartWindow): number | null {
    const now = Date.now();
    if (now < chartWindow.start || now > chartWindow.end) {
      return null;
    }
    return this.xPosition(now, chartWindow);
  }

  private chartWindow(timeline: TodayTimelineResponse): ChartWindow {
    const dayStart = Date.parse(timeline.day_start_utc);
    const dayEnd = Date.parse(timeline.day_end_utc);
    const timestamps = timeline.series
      .filter((series) => series.unit !== "%")
      .flatMap((series) =>
        numericSamples(series).map((sample) =>
          Date.parse(sample.timestamp_utc),
        ),
      )
      .filter((timestamp) => Number.isFinite(timestamp));
    if (timestamps.length === 0) {
      return { start: dayStart, end: dayEnd };
    }

    const first = Math.min(...timestamps);
    const last = Math.max(...timestamps);
    const dayDuration = dayEnd - dayStart;
    const requestedDuration = Math.max(
      MINIMUM_EARLY_WINDOW_MS,
      last - first + EARLY_WINDOW_PADDING_MS * 2,
    );
    const duration = Math.min(dayDuration, requestedDuration);
    const midpoint = (first + last) / 2;
    let start = midpoint - duration / 2;
    let end = midpoint + duration / 2;
    if (start < dayStart) {
      start = dayStart;
      end = dayStart + duration;
    }
    if (end > dayEnd) {
      end = dayEnd;
      start = dayEnd - duration;
    }
    return { start, end };
  }

  private axisTimes(
    chartWindow: ChartWindow,
    timeline: TodayTimelineResponse,
  ): readonly [string, string, string] {
    const formatter = new Intl.DateTimeFormat(this.locale, {
      hour: "numeric",
      minute: "2-digit",
      timeZone: timeline.time_zone,
    });
    return [
      formatter.format(new Date(chartWindow.start)),
      formatter.format(new Date((chartWindow.start + chartWindow.end) / 2)),
      formatter.format(new Date(chartWindow.end)),
    ];
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
      min-block-size: 150px;
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
      stroke: var(--ic-accent, var(--primary-color, #03a9f4));
      stroke-width: 4;
      stroke-linecap: round;
      stroke-linejoin: round;
    }
    .sample-point {
      fill: var(--ic-surface, var(--card-background-color, #ffffff));
      stroke: var(--ic-accent, var(--primary-color, #03a9f4));
      stroke-width: 3;
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
    .y-axis-labels {
      fill: var(--secondary-text-color, #667085);
      font-size: 16px;
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
    .state-row.derived strong small {
      display: block;
      color: var(--secondary-text-color, #667085);
      font-size: 0.68rem;
      font-weight: 500;
    }
    .state-chip {
      display: inline-block;
      margin: 0 6px 6px 0;
      padding: 4px 8px;
      border: 1px solid var(--divider-color, #d8dde3);
      border-radius: 999px;
    }
    .capability,
    .empty,
    .sample-summary {
      color: var(--secondary-text-color, #667085);
      font-size: 0.9rem;
    }
    .sample-summary {
      margin: 8px 0 0;
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
