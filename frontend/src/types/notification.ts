/** Mirrors backend/app/schemas/notification.py. */

export type NotificationType =
  | "ASSESSMENT_STARTED"
  | "ASSESSMENT_SUBMITTED"
  | "ANNOUNCEMENT"
  | "DIRECT_MESSAGE"
  | "CALENDAR_REMINDER";

export interface NotificationResponse {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  created_at: string;
  read_at: string | null;
  sender_id: string | null;
  sender_name: string | null;
  related_entity_type: string | null;
  related_entity_id: string | null;
}

export interface NotificationAcknowledgeResult {
  updated: number;
}

export interface UnreadCountResponse {
  unread: number;
}

export type AnnouncementTarget = "EVERYONE" | "DEPARTMENT" | "EMPLOYEES";

export interface AnnouncementCreateRequest {
  title: string;
  message: string;
  target: AnnouncementTarget;
  department_id?: string | null;
  user_ids?: string[];
}

export interface AnnouncementResult {
  recipients_notified: number;
}

export interface DirectMessageCreateRequest {
  recipient_user_id: string;
  title: string;
  message: string;
}
