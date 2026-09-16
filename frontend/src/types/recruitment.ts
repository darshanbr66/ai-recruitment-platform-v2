/**
 * Mirrors backend/app/schemas/{job,candidate,application}.py (Phase 3).
 */

export type JobStatus = "DRAFT" | "OPEN" | "ON_HOLD" | "CLOSED" | "WITHDRAWN";

export const JOB_STATUSES: JobStatus[] = ["DRAFT", "OPEN", "ON_HOLD", "CLOSED", "WITHDRAWN"];

export interface JobResponse {
  id: string;
  organization_id: string;
  title: string;
  department: string | null;
  location: string | null;
  employment_type: string | null;
  description: string;
  status: JobStatus;
  openings_count: number;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface JobCreateRequest {
  title: string;
  department?: string | null;
  location?: string | null;
  employment_type?: string | null;
  description: string;
  openings_count?: number;
}

export interface JobUpdateRequest {
  status?: JobStatus;
}

export type CandidateSource = "PORTAL" | "RECRUITER_ADDED" | "CAMPUS_IMPORT" | "REFERRAL" | "OTHER";

export interface CandidateResponse {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  phone: string | null;
  location: string | null;
  current_title: string | null;
  years_experience: number | null;
  source: CandidateSource;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface CandidateCreateRequest {
  email: string;
  full_name: string;
  phone?: string | null;
  location?: string | null;
  current_title?: string | null;
  years_experience?: number | null;
}

export type ApplicationStatus =
  | "APPLIED"
  | "UNDER_REVIEW"
  | "SCREENING"
  | "ASSESSMENT_INVITED"
  | "ASSESSMENT_STARTED"
  | "ASSESSMENT_COMPLETED"
  | "SHORTLISTED"
  | "INTERVIEW"
  | "SELECTED"
  | "REJECTED"
  | "WITHDRAWN";

export const APPLICATION_STATUSES: ApplicationStatus[] = [
  "APPLIED",
  "UNDER_REVIEW",
  "SCREENING",
  "ASSESSMENT_INVITED",
  "ASSESSMENT_STARTED",
  "ASSESSMENT_COMPLETED",
  "SHORTLISTED",
  "INTERVIEW",
  "SELECTED",
  "REJECTED",
  "WITHDRAWN",
];

/** Mirrors app/workflows/application_workflow.py's TRANSITIONS table. */
export const APPLICATION_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  APPLIED: ["UNDER_REVIEW", "WITHDRAWN"],
  UNDER_REVIEW: ["SCREENING", "REJECTED", "WITHDRAWN"],
  SCREENING: ["ASSESSMENT_INVITED", "SHORTLISTED", "REJECTED", "WITHDRAWN"],
  ASSESSMENT_INVITED: ["ASSESSMENT_STARTED", "REJECTED", "WITHDRAWN"],
  ASSESSMENT_STARTED: ["ASSESSMENT_COMPLETED", "WITHDRAWN"],
  ASSESSMENT_COMPLETED: ["SHORTLISTED", "REJECTED"],
  SHORTLISTED: ["INTERVIEW", "REJECTED", "WITHDRAWN"],
  INTERVIEW: ["SELECTED", "REJECTED", "WITHDRAWN"],
  SELECTED: [],
  REJECTED: [],
  WITHDRAWN: [],
};

export interface ApplicationResponse {
  id: string;
  organization_id: string;
  candidate_id: string;
  candidate_full_name: string;
  job_id: string;
  job_title: string;
  campus_drive_id: string | null;
  status: ApplicationStatus;
  source: string;
  applied_at: string;
  created_at: string;
  updated_at: string;
  resume_id: string | null;
  resume_filename: string | null;
}

export interface ApplicationCreateRequest {
  candidate_id: string;
  job_id: string;
}
