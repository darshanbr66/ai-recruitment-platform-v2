/**
 * One tone per application stage, used everywhere a stage appears (badges,
 * pipeline bars, timelines), so a status never changes colour between pages.
 * Colour follows meaning: progress is blue, a positive outcome green, a
 * negative one red, and the final human success — hired — the warm accent.
 */
export type Tone = "neutral" | "info" | "brand" | "success" | "danger" | "accent" | "warn";

const TONES: Record<string, Tone> = {
  APPLIED: "neutral",
  UNDER_REVIEW: "info",
  SCREENING: "info",
  ASSESSMENT_INVITED: "brand",
  ASSESSMENT_STARTED: "brand",
  ASSESSMENT_COMPLETED: "brand",
  SHORTLISTED: "brand",
  INTERVIEW: "brand",
  SELECTED: "success",
  REJECTED: "danger",
  HIRED: "accent",
};

export function statusTone(status: string): Tone {
  return TONES[status] ?? "neutral";
}

const BADGE_CLASS: Record<Tone, string> = {
  neutral: "badge-inactive",
  info: "badge-info",
  brand: "badge-info",
  success: "badge-active",
  danger: "badge-danger",
  accent: "badge-accent",
  warn: "badge-warn",
};

export function toneBadgeClass(tone: Tone): string {
  return `badge ${BADGE_CLASS[tone]}`;
}

const TONE_COLOR: Record<Tone, string> = {
  neutral: "var(--color-text-muted)",
  info: "var(--kind-job)",
  brand: "var(--color-primary)",
  success: "var(--color-active-text)",
  danger: "var(--color-danger)",
  accent: "var(--color-accent)",
  warn: "var(--color-warn-text)",
};

/** A CSS colour for fills (bars, dots) — theme-aware through the tokens. */
export function toneColor(tone: Tone): string {
  return TONE_COLOR[tone];
}

/** "UNDER_REVIEW" -> "Under review". */
export function humanizeStatus(status: string): string {
  const text = status.replace(/_/g, " ").toLowerCase();
  return text.charAt(0).toUpperCase() + text.slice(1);
}
