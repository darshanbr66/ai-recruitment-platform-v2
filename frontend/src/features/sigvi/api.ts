import { apiClient } from "../../lib/apiClient";
import type { SigviChatRequest, SigviChatResponse } from "../../types/sigvi";

/** The browser only ever talks to our backend; the AI provider and its key
 * stay server-side. */
export function sendChatMessage(request: SigviChatRequest) {
  return apiClient.post<SigviChatResponse>("/api/v1/public/ai/chat", request);
}
