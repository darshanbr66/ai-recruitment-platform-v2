import type { CSSProperties } from "react";

/** "Riya Recruiter" -> "RR", "Madonna" -> "M", "" -> "?". */
export function initials(name: string | null | undefined): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  const first = parts[0][0];
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase();
}

// A deliberately small palette: brand blue, info cyan, success green,
// the human amber, and neutral. Tones are semantic-adjacent, not a rainbow.
const TONES = [
  { bg: "var(--color-primary-soft)", fg: "var(--color-primary)" },
  { bg: "var(--color-info-bg)", fg: "var(--color-info-text)" },
  { bg: "var(--color-active-bg)", fg: "var(--color-active-text)" },
  { bg: "var(--color-accent-soft)", fg: "var(--color-accent-text)" },
  { bg: "var(--color-inactive-bg)", fg: "var(--color-inactive-text)" },
] as const;

/** A stable tone per name, so a person keeps the same avatar colour on every
 * page and every visit. */
export function avatarStyle(name: string | null | undefined): CSSProperties {
  const key = (name ?? "").trim().toLowerCase();
  let hash = 0;
  for (let i = 0; i < key.length; i++) hash = (hash * 31 + key.charCodeAt(i)) >>> 0;
  const tone = TONES[hash % TONES.length];
  return { "--avatar-bg": tone.bg, "--avatar-fg": tone.fg } as CSSProperties;
}
