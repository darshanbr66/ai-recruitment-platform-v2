/** Mirrors backend/app/schemas/sigvi.py. */

export const SIGVI_MAX_MESSAGE_CHARS = 1000;
/** Turns of history sent with each message (the backend uses at most 8). */
export const SIGVI_HISTORY_TURNS = 8;

export type SigviRole = "user" | "assistant";

export interface SigviHistoryMessage {
  role: SigviRole;
  content: string;
}

export interface SigviChatRequest {
  message: string;
  conversation_id?: string;
  history: SigviHistoryMessage[];
  organization_slug?: string;
}

export interface SigviSource {
  id: string;
  title: string;
  type: "knowledge" | "job";
  url: string | null;
}

export interface SigviJobCard {
  id: string;
  title: string;
  department: string | null;
  location: string | null;
  employment_type: string | null;
  summary: string | null;
  organization_slug: string;
  view_path: string;
  apply_path: string;
}

export interface SigviChatResponse {
  conversation_id: string;
  message: string;
  sources: SigviSource[];
  jobs: SigviJobCard[];
}
