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
  description_visible: boolean;
  status: JobStatus;
  openings_count: number;
  created_by: string;
  deleted_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobDeleteRequest {
  reason: string;
}

export interface JobCreateRequest {
  title: string;
  department?: string | null;
  location?: string | null;
  employment_type?: string | null;
  description: string;
  description_visible?: boolean;
  openings_count?: number;
}

export interface JobUpdateRequest {
  title?: string;
  department?: string | null;
  location?: string | null;
  employment_type?: string | null;
  description?: string;
  description_visible?: boolean;
  openings_count?: number;
  status?: JobStatus;
}

export type CandidateSource = "PORTAL" | "RECRUITER_ADDED" | "CAMPUS_IMPORT" | "REFERRAL" | "OTHER";

export type CandidateType = "FRESHER" | "EXPERIENCED";

export interface CandidateResponse {
  id: string;
  organization_id: string;
  email: string;
  full_name: string;
  phone: string | null;
  location: string | null;
  current_title: string | null;
  current_company: string | null;
  preferred_location: string | null;
  years_experience: number | null;
  candidate_type: CandidateType | null;
  notice_period_days: number | null;
  immediate_joiner: boolean | null;
  qualification: string | null;
  linkedin_url: string | null;
  github_url: string | null;
  source: CandidateSource;
  is_active: boolean;
  deleted_at: string | null;
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
  | "HIRED";

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
  "HIRED",
];

/** Mirrors app/workflows/application_workflow.py's TRANSITIONS table. */
export const APPLICATION_TRANSITIONS: Record<ApplicationStatus, ApplicationStatus[]> = {
  APPLIED: ["UNDER_REVIEW", "REJECTED"],
  UNDER_REVIEW: ["SCREENING", "REJECTED"],
  SCREENING: ["ASSESSMENT_INVITED", "SHORTLISTED", "REJECTED"],
  ASSESSMENT_INVITED: ["ASSESSMENT_STARTED", "REJECTED"],
  ASSESSMENT_STARTED: ["ASSESSMENT_COMPLETED", "REJECTED"],
  ASSESSMENT_COMPLETED: ["SHORTLISTED", "REJECTED"],
  SHORTLISTED: ["INTERVIEW", "REJECTED"],
  INTERVIEW: ["SELECTED", "REJECTED"],
  SELECTED: ["HIRED"],
  REJECTED: [],
  HIRED: [],
};

export interface ApplicationResponse {
  id: string;
  organization_id: string;
  candidate_id: string;
  candidate_full_name: string;
  candidate_email: string;
  candidate_phone: string | null;
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
  deleted_at: string | null;
}

export interface ApplicationCreateRequest {
  candidate_id: string;
  job_id: string;
}

export interface ApplicationDeleteRequest {
  reason: string;
}

