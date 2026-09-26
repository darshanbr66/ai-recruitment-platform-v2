import { apiClient } from "../../../lib/apiClient";
import type {
  AdminConversationDetail,
  AdminConversationSummary,
  AdminMessageReadResult,
  AdminMessageResponse,
  AdminMessageUnreadCount,
} from "../../../types/adminMessage";

const BASE = "/api/v1/recruiter/admin-messages";

/** Unread for whichever side the caller is on — admin replies they haven't
 * read, or staff messages no admin has read. Backs the nav badge. */
export function getAdminMessageUnreadCount(accessToken: string) {
  return apiClient.get<AdminMessageUnreadCount>(`${BASE}/unread-count`, accessToken);
}

/** The caller's own thread with the admins. No conversation id is sent or
 * accepted, so a staff member can only ever reach their own. */
export function getMyAdminConversation(accessToken: string) {
  return apiClient.get<AdminConversationDetail>(`${BASE}/mine`, accessToken);
}

export function sendMessageToAdmins(body: string, accessToken: string) {
  return apiClient.post<AdminMessageResponse>(`${BASE}/mine`, { body }, accessToken);
}

export function markMyAdminConversationRead(accessToken: string) {
  return apiClient.post<AdminMessageReadResult>(`${BASE}/mine/read`, undefined, accessToken);
}

/** The admin inbox — the caller's organization only, enforced server-side. */
export function listAdminConversations(accessToken: string) {
  return apiClient.get<AdminConversationSummary[]>(`${BASE}/conversations`, accessToken);
}

export function getAdminConversation(conversationId: string, accessToken: string) {
  return apiClient.get<AdminConversationDetail>(
    `${BASE}/conversations/${conversationId}`,
    accessToken,
  );
}

export function replyToAdminConversation(
  conversationId: string,
  body: string,
  accessToken: string,
) {
  return apiClient.post<AdminMessageResponse>(
    `${BASE}/conversations/${conversationId}/messages`,
    { body },
    accessToken,
  );
}

export function markAdminConversationRead(conversationId: string, accessToken: string) {
  return apiClient.post<AdminMessageReadResult>(
    `${BASE}/conversations/${conversationId}/read`,
    undefined,
    accessToken,
  );
}
