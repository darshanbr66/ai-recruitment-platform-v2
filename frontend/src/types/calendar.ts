/** Mirrors backend/app/schemas/calendar_event.py. */

export type CalendarEventType =
  | "INTERVIEW"
  | "HR_MEETING"
  | "TEAM_MEETING"
  | "ASSESSMENT_DEADLINE"
  | "FOLLOW_UP"
  | "RECRUITMENT_EVENT"
  | "CAMPUS_EVENT"
  | "GENERAL_REMINDER";

/** One selectable attendee, from GET /recruiter/calendar/attendee-options —
 * the caller's own organization only. */
export interface CalendarAttendeeOption {
  id: string;
  full_name: string;
  email: string;
}

export type CalendarEventStatus = "SCHEDULED" | "COMPLETED" | "CANCELLED";

export interface CalendarEventResponse {
  id: string;
  title: string;
  description: string | null;
  event_type: CalendarEventType;
  status: CalendarEventStatus;
  start_at: string;
  end_at: string;
  all_day: boolean;
  timezone: string;
  organizer_id: string;
  organizer_name: string;
  candidate_id: string | null;
  job_id: string | null;
  application_id: string | null;
  reminder_minutes_before: number | null;
  reminder_fired_at: string | null;
  attendee_ids: string[];
  created_at: string;
  updated_at: string;
}

export interface CalendarEventCreateRequest {
  title: string;
  description?: string | null;
  event_type: CalendarEventType;
  start_at: string;
  end_at: string;
  all_day?: boolean;
  timezone: string;
  candidate_id?: string | null;
  job_id?: string | null;
  application_id?: string | null;
  reminder_minutes_before?: number | null;
  attendee_ids?: string[];
}

export interface CalendarEventUpdateRequest {
  title?: string;
  description?: string | null;
  event_type?: CalendarEventType;
  status?: CalendarEventStatus;
  start_at?: string;
  end_at?: string;
  all_day?: boolean;
  timezone?: string;
  candidate_id?: string | null;
  job_id?: string | null;
  application_id?: string | null;
  reminder_minutes_before?: number | null;
  attendee_ids?: string[];
}
