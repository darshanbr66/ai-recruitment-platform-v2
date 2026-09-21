import { apiClient } from "../../../lib/apiClient";
import type {
  NotificationAcknowledgeResult,
  NotificationResponse,
} from "../../../types/notification";

/** The signed-in user's own unread notifications, newest first. */
export function listUnreadNotifications(accessToken: string) {
  return apiClient.get<NotificationResponse[]>("/api/v1/recruiter/notifications", accessToken);
}

/** Marks them read so they are never delivered again. Safe to repeat. */
export function acknowledgeNotifications(ids: string[], accessToken: string) {
  return apiClient.post<NotificationAcknowledgeResult>(
    "/api/v1/recruiter/notifications/read",
    { ids },
    accessToken,
  );
}
