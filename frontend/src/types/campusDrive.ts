/** Mirrors backend/app/schemas/campus_drive.py. */

export type CampusDriveStatus = "PLANNED" | "ACTIVE" | "CLOSED" | "CANCELLED";

export const CAMPUS_DRIVE_STATUSES: CampusDriveStatus[] = ["PLANNED", "ACTIVE", "CLOSED", "CANCELLED"];

export interface CampusDriveCreateRequest {
  name: string;
  job_id: string;
  college_name: string;
  batch_year?: number | null;
  start_date?: string | null;
  end_date?: string | null;
}

export interface CampusDriveUpdateRequest {
  status?: CampusDriveStatus;
}

export interface CampusDriveResponse {
  id: string;
  name: string;
  job_id: string;
  job_title: string;
  college_name: string;
  batch_year: number | null;
  start_date: string | null;
  end_date: string | null;
  status: CampusDriveStatus;
  application_count: number;
  created_at: string;
}
