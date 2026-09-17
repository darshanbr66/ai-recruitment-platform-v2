/** Mirrors backend/app/schemas/campus_drive.py. */

export type CampusDriveStatus = "DRAFT" | "ACTIVE" | "PAUSED" | "CLOSED";

export const CAMPUS_DRIVE_STATUSES: CampusDriveStatus[] = ["DRAFT", "ACTIVE", "PAUSED", "CLOSED"];

/** Either `job_id` (use an existing job) or both `new_job_title` and
 * `new_job_description` (create one inline) must be supplied — never both,
 * never neither. Enforced again server-side. */
export interface CampusDriveCreateRequest {
  name: string;
  college_name: string;
  job_id?: string | null;
  new_job_title?: string | null;
  new_job_description?: string | null;
  description?: string | null;
  batch_year?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  registration_deadline?: string | null;
  default_assessment_id?: string | null;
}

export interface CampusDriveUpdateRequest {
  name?: string;
  college_name?: string;
  description?: string | null;
  batch_year?: number | null;
  start_date?: string | null;
  end_date?: string | null;
  registration_deadline?: string | null;
  default_assessment_id?: string | null;
  status?: CampusDriveStatus;
}

export interface CampusDriveResponse {
  id: string;
  name: string;
  job_id: string;
  job_title: string;
  college_name: string;
  description: string | null;
  batch_year: number | null;
  start_date: string | null;
  end_date: string | null;
  registration_deadline: string | null;
  default_assessment_id: string | null;
  default_assessment_title: string | null;
  status: CampusDriveStatus;
  application_count: number;
  deleted_at: string | null;
  created_at: string;
  /** Only populated once, on create/regenerate — never re-sent by list/get. */
  application_link: string | null;
}

export interface CampusDriveDeleteRequest {
  reason: string;
}

export interface CampusDriveFunnelCounts {
  registered: number;
  screening: number;
  assessment_invited: number;
  assessment_completed: number;
  assessment_passed: number;
  assessment_failed: number;
  shortlisted: number;
  interview: number;
  selected: number;
  rejected: number;
  withdrawn: number;
}
