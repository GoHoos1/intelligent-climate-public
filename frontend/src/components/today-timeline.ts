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

interface TimeTick {
  label: string;
  timestamp: number;
  x: number;
  anchor: "start" | "middle" | "end";
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

interface LaneSegment {
  left: number;
  width: number;
  value: string;
  label: string;
  className: string;
  startsAt: string;
  endsAt: string;
}

interface StateLane {
  label: string;
  detail: string;
  className: string;
  segments: LaneSegment[];
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
  contact_state: "Window / door",
  control_context: "Control context",
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
  open: "Open",
  closed: "Closed",
  normal: "Normal",
  window_suspended: "Paused for open window / door",
  manual_override: "Manual override",
  shared_conflict: "Shared-equipment conflict",
  safe_fallback: "Safe fallback",
  paused: "Paused",
  degraded: "Degraded",
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

function isTextSample(
  sample: TimelineSample,
): sample is TimelineSample & { value: string } {
  return typeof sample.value === "string";
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
    const stateLanes = this.stateLanes(timeline, chartWindow);
    const cursor = this.currentCursor(chartWindow);
    const timeTicks = this.timeTicks(chartWindow, timeline);
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
                    ${timeTicks.map(
                      (tick) =>
                        svg`<line
                          x1=${tick.x}
                          x2=${tick.x}
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
                          series.kind === "effective_temperature" &&
                          series.sampleCount <= 3
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
                    ${timeTicks.map(
                      (tick) =>
                        svg`<text
                          x=${tick.x}
                          y="198"
                          text-anchor=${tick.anchor}
                        >${tick.label}</text>`,
                    )}
                  </g>
                </svg>
                ${this.sampleSummary(indoorSeries)}
              </div>`
      }
      ${
        stateLanes.length === 0
          ? nothing
          : html`<div
              class="state-lanes-scroll"
              aria-label="Equipment and context state timeline"
            >
              <div class="state-lanes">
                ${stateLanes.map((lane) => this.renderStateLane(lane))}
              </div>
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
    const numeric = this.visibleNumericSeries(timeline).filter(
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

  private visibleNumericSeries(
    timeline: TodayTimelineResponse,
  ): TimelineSeries[] {
    const scheduledByEffective: Record<string, string> = {
      effective_target: "scheduled_target",
      effective_heat_target: "scheduled_heat_target",
      effective_cool_target: "scheduled_cool_target",
    };
    return timeline.series.filter((series) => {
      const scheduledKind = scheduledByEffective[series.kind];
      if (scheduledKind === undefined) return true;
      const scheduled = timeline.series.find(
        (candidate) => candidate.kind === scheduledKind,
      );
      return (
        scheduled === undefined || !this.sameNumericSeries(series, scheduled)
      );
    });
  }

  private sameNumericSeries(
    first: TimelineSeries,
    second: TimelineSeries,
  ): boolean {
    const firstSamples = numericSamples(first);
    const secondSamples = numericSamples(second);
    return (
      firstSamples.length === secondSamples.length &&
      firstSamples.every((sample, index) => {
        const other = secondSamples[index];
        return (
          sample.timestamp_utc === other?.timestamp_utc &&
          sample.value === other.value
        );
      })
    );
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

  private stateLanes(
    timeline: TodayTimelineResponse,
    chartWindow: ChartWindow,
  ): StateLane[] {
    const hvac = timeline.series.find(
      (series) => series.kind === "hvac_action",
    );
    const fan = timeline.series.find((series) => series.kind === "fan_action");
    const contacts = timeline.series.find(
      (series) => series.kind === "contact_state",
    );
    const context = timeline.series.find(
      (series) => series.kind === "control_context",
    );
    const result: StateLane[] = [];
    if (hvac !== undefined) {
      result.push(
        this.buildStateLane(
          hvac,
          chartWindow,
          "Heating",
          "Actual thermostat heating operation",
          "heating",
          (value) => value === "heating",
        ),
        this.buildStateLane(
          hvac,
          chartWindow,
          "Cooling",
          "Actual thermostat cooling operation",
          "cooling",
          (value) => value === "cooling",
        ),
        this.buildStateLane(
          hvac,
          chartWindow,
          "Air handler",
          "Derived from actual thermostat operation",
          "air-handler derived",
          (value) => ["heating", "cooling", "drying", "fan"].includes(value),
          derivedAirHandlerState,
        ),
      );
    }
    if (fan !== undefined) {
      result.splice(
        Math.min(2, result.length),
        0,
        this.buildStateLane(
          fan,
          chartWindow,
          "Fan only",
          "Explicit circulation without heating or cooling",
          "fan-only",
          (value) => value === "on",
        ),
      );
    }
    if (
      contacts?.samples.some((sample) => sample.value !== "not_configured") ===
      true
    ) {
      result.push(
        this.buildStateLane(
          contacts,
          chartWindow,
          "Window / door",
          "Any configured contact open or unavailable",
          "contact",
          (value) => value === "open" || value === "unavailable",
        ),
      );
    }
    if (
      context?.samples.some(
        (sample) =>
          sample.value !== "normal" && sample.value !== "not_reported",
      ) === true
    ) {
      result.push(
        this.buildStateLane(
          context,
          chartWindow,
          "Control context",
          "Recorded override, suspension, fallback, or pause",
          "context",
          (value) => value !== "normal" && value !== "not_reported",
        ),
      );
    }
    return result;
  }

  private buildStateLane(
    series: TimelineSeries,
    chartWindow: ChartWindow,
    laneLabel: string,
    detail: string,
    className: string,
    active: (value: string) => boolean,
    valueLabel: (value: string) => string = stateLabel,
  ): StateLane {
    const samples = collapseStateSamples(series.samples).filter(isTextSample);
    const coverageEnd = Math.min(
      chartWindow.end,
      Date.parse(series.coverage_end_utc),
    );
    const segments = samples.flatMap((sample, index) => {
      if (!active(sample.value)) return [];
      const start = Math.max(
        chartWindow.start,
        Date.parse(sample.timestamp_utc),
      );
      const next = samples[index + 1];
      const end = Math.min(
        coverageEnd,
        next === undefined ? coverageEnd : Date.parse(next.timestamp_utc),
      );
      if (end <= start) return [];
      const duration = chartWindow.end - chartWindow.start;
      return [
        {
          left: ((start - chartWindow.start) / duration) * 100,
          width: ((end - start) / duration) * 100,
          value: sample.value,
          label: valueLabel(sample.value),
          className: `${className} ${sample.value}`,
          startsAt: this.stateTimestamp(new Date(start).toISOString()),
          endsAt: this.stateTimestamp(new Date(end).toISOString()),
        },
      ];
    });
    return { label: laneLabel, detail, className, segments };
  }

  private renderStateLane(lane: StateLane): ReturnType<typeof html> {
    return html`<div class="lane-row ${lane.className}">
      <span class="lane-label">
        <strong>${lane.label}</strong>
        <small>${lane.detail}</small>
      </span>
      <div class="lane-track">
        ${lane.segments.map(
          (segment) =>
            html`<span
              class="lane-segment ${segment.className}"
              style=${`inset-inline-start:${String(segment.left)}%;inline-size:${String(segment.width)}%`}
              tabindex="0"
              aria-label=${`${lane.label}: ${segment.label}, ${segment.startsAt} to ${segment.endsAt}`}
              title=${`${segment.label} · ${segment.startsAt}–${segment.endsAt}`}
            ></span>`,
        )}
      </div>
      <span aria-hidden="true"></span>
    </div>`;
  }

  private stateTimestamp(value: string): string {
    return formatTimestamp(value, this.locale, this.timeline?.time_zone);
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

  private timeTicks(
    chartWindow: ChartWindow,
    timeline: TodayTimelineResponse,
  ): TimeTick[] {
    const duration = chartWindow.end - chartWindow.start;
    const intervalMinutes =
      duration <= 30 * 60_000
        ? 5
        : duration <= 90 * 60_000
          ? 15
          : duration <= 3 * 60 * 60_000
            ? 30
            : duration <= 8 * 60 * 60_000
              ? 60
              : 120;
    const partsFormatter = new Intl.DateTimeFormat("en-US", {
      hour: "numeric",
      hourCycle: "h23",
      minute: "2-digit",
      timeZone: timeline.time_zone,
    });
    const hourFormatter = new Intl.DateTimeFormat(this.locale, {
      hour: "numeric",
      timeZone: timeline.time_zone,
    });
    const minuteFormatter = new Intl.DateTimeFormat(this.locale, {
      hour: "numeric",
      minute: "2-digit",
      timeZone: timeline.time_zone,
    });
    const dayStart = Date.parse(timeline.day_start_utc);
    const dayEnd = Date.parse(timeline.day_end_utc);
    const scanStep = Math.min(intervalMinutes, 15) * 60_000;
    const timestamps: number[] = [];
    for (
      let timestamp = dayStart;
      timestamp < dayEnd && timestamp < chartWindow.end;
      timestamp += scanStep
    ) {
      if (timestamp < chartWindow.start) continue;
      const parts = Object.fromEntries(
        partsFormatter
          .formatToParts(new Date(timestamp))
          .filter((part) => part.type === "hour" || part.type === "minute")
          .map((part) => [part.type, Number(part.value)]),
      );
      const hour = parts["hour"];
      const minute = parts["minute"];
      if (hour === undefined || minute === undefined) continue;
      const minutesSinceMidnight = hour * 60 + minute;
      if (minutesSinceMidnight % intervalMinutes === 0) {
        timestamps.push(timestamp);
      }
    }
    return timestamps.map((timestamp, index) => ({
      timestamp,
      x: this.xPosition(timestamp, chartWindow),
      label:
        intervalMinutes < 60
          ? minuteFormatter.format(new Date(timestamp))
          : hourFormatter.format(new Date(timestamp)),
      anchor:
        index === 0 && timestamp === chartWindow.start
          ? "start"
          : index === timestamps.length - 1 && timestamp === chartWindow.end
            ? "end"
            : "middle",
    }));
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
    .swatch.scheduled_heat_target,
    .swatch.effective_heat_target {
      border-block-start-color: var(--warning-color, #d97706);
    }
    .swatch.scheduled_cool_target,
    .swatch.effective_cool_target {
      border-block-start-color: var(--info-color, #1976d2);
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
    .series.scheduled_heat_target {
      stroke: var(--warning-color, #d97706);
    }
    .series.scheduled_cool_target {
      stroke: var(--info-color, #1976d2);
    }
    .series.effective_heat_target {
      stroke: var(--warning-color, #d97706);
    }
    .series.effective_cool_target {
      stroke: var(--info-color, #1976d2);
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
      font-size: 16px;
    }
    .y-axis-labels {
      fill: var(--secondary-text-color, #667085);
      font-size: 16px;
    }
    .state-lanes-scroll {
      overflow-x: auto;
      margin-block: 12px;
    }
    .state-lanes {
      display: grid;
      gap: 6px;
      min-inline-size: 620px;
    }
    .lane-row {
      display: grid;
      grid-template-columns: 80fr 890fr 30fr;
      align-items: center;
      min-block-size: 30px;
    }
    .lane-label {
      display: grid;
      padding-inline-end: 8px;
      font-size: 0.72rem;
      line-height: 1.15;
    }
    .lane-label small {
      display: block;
      color: var(--secondary-text-color, #667085);
      font-size: 0.58rem;
      font-weight: 500;
    }
    .lane-track {
      position: relative;
      block-size: 15px;
      border: 1px solid var(--divider-color, #d8dde3);
      border-radius: 5px;
      background: color-mix(
        in srgb,
        var(--secondary-text-color, #667085) 7%,
        transparent
      );
      overflow: hidden;
    }
    .lane-segment {
      position: absolute;
      inset-block: 0;
      min-inline-size: 2px;
      background: var(--ic-accent, #0288d1);
    }
    .lane-segment:focus-visible {
      outline: 3px solid var(--primary-text-color);
      outline-offset: -3px;
    }
    .lane-segment.heating {
      background: var(--warning-color, #ef6c00);
    }
    .lane-segment.cooling {
      background: var(--info-color, #1976d2);
    }
    .lane-segment.fan-only,
    .lane-segment.fan {
      background: var(--success-color, #2e7d32);
    }
    .lane-segment.air-handler {
      background: repeating-linear-gradient(
        135deg,
        var(--secondary-text-color, #667085),
        var(--secondary-text-color, #667085) 4px,
        transparent 4px,
        transparent 8px
      );
    }
    .lane-segment.contact.open {
      background: var(--warning-color, #ef6c00);
    }
    .lane-segment.contact.unavailable,
    .lane-segment.context.degraded,
    .lane-segment.context.safe_fallback {
      background: repeating-linear-gradient(
        135deg,
        var(--error-color, #c62828),
        var(--error-color, #c62828) 4px,
        transparent 4px,
        transparent 8px
      );
    }
    .lane-segment.context {
      background: var(--warning-color, #ef6c00);
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
