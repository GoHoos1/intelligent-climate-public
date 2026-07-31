export type StatusTone =
  "neutral" | "info" | "positive" | "warning" | "critical";

export interface StatusSemantics {
  label: string;
  icon: string;
  tone: StatusTone;
  automationOff: boolean;
}

const STATUS: Record<string, StatusSemantics> = {
  observing: {
    label: "Observe Only",
    icon: "◉",
    tone: "info",
    automationOff: true,
  },
  manual_idle: {
    label: "Manual Control — Automation Off",
    icon: "✋",
    tone: "neutral",
    automationOff: true,
  },
  shadow_qualifying: {
    label: "Shadow Qualifying",
    icon: "◌",
    tone: "info",
    automationOff: false,
  },
  shadow_ready: {
    label: "Shadow Ready",
    icon: "✓",
    tone: "positive",
    automationOff: false,
  },
  scheduled_idle: {
    label: "Scheduled Control",
    icon: "▶",
    tone: "positive",
    automationOff: false,
  },
  manual_override: {
    label: "Override",
    icon: "✋",
    tone: "warning",
    automationOff: false,
  },
  window_suspended: {
    label: "Suspended",
    icon: "▣",
    tone: "warning",
    automationOff: false,
  },
  safe_fallback: {
    label: "Safe Fallback",
    icon: "⚠",
    tone: "warning",
    automationOff: false,
  },
  emergency_protection: {
    label: "Emergency Protection",
    icon: "◆",
    tone: "critical",
    automationOff: false,
  },
  emergency_paused: {
    label: "Paused",
    icon: "Ⅱ",
    tone: "critical",
    automationOff: false,
  },
  degraded: {
    label: "Degraded",
    icon: "⚠",
    tone: "warning",
    automationOff: false,
  },
  reconciling: {
    label: "Reconciling",
    icon: "↻",
    tone: "info",
    automationOff: false,
  },
};

export function statusSemantics(controlState: string): StatusSemantics {
  return (
    STATUS[controlState] ?? {
      label: controlState.replaceAll("_", " "),
      icon: "●",
      tone: "neutral",
      automationOff: false,
    }
  );
}

export function formatTemperature(
  celsius: number | null,
  unit: "°C" | "°F",
  locale: string,
): string {
  if (celsius === null) {
    return "Unavailable";
  }
  const value = unit === "°F" ? (celsius * 9) / 5 + 32 : celsius;
  return `${new Intl.NumberFormat(locale, { maximumFractionDigits: 1 }).format(value)}${unit}`;
}

export function formatTimestamp(
  value: string,
  locale: string,
  timeZone?: string,
): string {
  return new Intl.DateTimeFormat(locale, {
    hour: "numeric",
    minute: "2-digit",
    month: "short",
    day: "numeric",
    ...(timeZone === undefined ? {} : { timeZone }),
  }).format(new Date(value));
}

export function humanizeCode(value: string): string {
  return value
    .split("_")
    .filter((part) => part.length > 0)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
