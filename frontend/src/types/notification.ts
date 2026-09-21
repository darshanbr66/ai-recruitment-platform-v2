/** Mirrors backend/app/schemas/notification.py. */

export type NotificationType = "ASSESSMENT_STARTED" | "ASSESSMENT_SUBMITTED";

export interface NotificationResponse {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  created_at: string;
  read_at: string | null;
}

export interface NotificationAcknowledgeResult {
  updated: number;
}
