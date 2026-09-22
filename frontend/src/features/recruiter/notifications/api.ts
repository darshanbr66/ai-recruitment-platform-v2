import { apiClient } from "../../../lib/apiClient";
import type {
  AnnouncementCreateRequest,
  AnnouncementResult,
  DirectMessageCreateRequest,
  NotificationAcknowledgeResult,
  NotificationResponse,
  UnreadCountResponse,
} from "../../../types/notification";

/** The signed-in user's own unread notifications, newest first — feeds the
 * toast stream only. The Notification Center uses `listAllNotifications`. */
export function listUnreadNotifications(accessToken: string) {
  return apiClient.get<NotificationResponse[]>("/api/v1/recruiter/notifications", accessToken);
}

/** The Notification Center's full, paginated history — never auto-consumed
 * just by being listed. */
export function listAllNotifications(
  accessToken: string,
  options: { unreadOnly?: boolean; limit?: number; offset?: number } = {},
) {
  const params = new URLSearchParams();
  if (options.unreadOnly) params.set("unread_only", "true");
  if (options.limit) params.set("limit", String(options.limit));
  if (options.offset) params.set("offset", String(options.offset));
  const query = params.toString();
  return apiClient.get<NotificationResponse[]>(
    `/api/v1/recruiter/notifications/all${query ? `?${query}` : ""}`,
    accessToken,
  );
}

export function getUnreadCount(accessToken: string) {
  return apiClient.get<UnreadCountResponse>("/api/v1/recruiter/notifications/unread-count", accessToken);
}

/** Marks them read so they are never delivered again. Safe to repeat. */
export function acknowledgeNotifications(ids: string[], accessToken: string) {
  return apiClient.post<NotificationAcknowledgeResult>(
    "/api/v1/recruiter/notifications/read",
    { ids },
    accessToken,
  );
}

export function acknowledgeAllNotifications(accessToken: string) {
  return apiClient.post<NotificationAcknowledgeResult>(
    "/api/v1/recruiter/notifications/read-all",
    undefined,
    accessToken,
  );
}

export function sendAnnouncement(payload: AnnouncementCreateRequest, accessToken: string) {
  return apiClient.post<AnnouncementResult>("/api/v1/recruiter/notifications/announce", payload, accessToken);
}

export function sendDirectMessage(payload: DirectMessageCreateRequest, accessToken: string) {
  return apiClient.post<NotificationResponse>("/api/v1/recruiter/notifications/send", payload, accessToken);
}
