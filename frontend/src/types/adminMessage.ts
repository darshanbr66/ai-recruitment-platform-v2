/** Mirrors backend/app/schemas/admin_message.py — "Talk to Admin", the
 * internal thread between a staff member and their organization's admins.
 * Every endpoint behind these types is tenant-scoped server-side. */

export interface AdminMessageResponse {
  id: string;
  conversation_id: string;
  body: string;
  /** Which side wrote it — the recipient is always the other side. */
  from_admin: boolean;
  sender_user_id: string | null;
  sender_name: string | null;
  created_at: string;
  read_at: string | null;
}

/** A row in the admin inbox. */
export interface AdminConversationSummary {
  id: string;
  employee_user_id: string;
  employee_name: string;
  employee_email: string;
  last_message_at: string | null;
  last_message_preview: string | null;
  last_message_from_admin: boolean | null;
  unread_count: number;
}

/** `id` is null for a staff member who hasn't written yet — the
 * conversation is created by their first message. */
export interface AdminConversationDetail {
  id: string | null;
  employee_user_id: string;
  employee_name: string;
  employee_email: string;
  messages: AdminMessageResponse[];
}

export interface AdminMessageUnreadCount {
  unread: number;
}

export interface AdminMessageReadResult {
  updated: number;
}
