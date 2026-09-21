import type { IconName } from "../../shared/components/Icon";

/** Starting points drawn from what the site actually offers. The label is sent
 * verbatim as the visitor's message. */
export const SIGVI_SUGGESTIONS: { label: string; icon: IconName }[] = [
  { label: "Show me current openings", icon: "jobs" },
  { label: "How do I apply?", icon: "applications" },
  { label: "How does the hiring process work?", icon: "graph" },
  { label: "Tell me about SIGVITAS", icon: "sparkles" },
  { label: "How does the assessment work?", icon: "assessments" },
];

/** What Sigvi can help with, as shown on the welcome screen. */
export const SIGVI_CAPABILITIES = [
  "Current job openings",
  "How to apply",
  "The hiring process",
  "Campus opportunities",
  "Assessments",
  "SIGVITAS and career questions",
  "General questions",
];
