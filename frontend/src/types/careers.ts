/** Mirrors backend/app/schemas/public.py. */

import type { CandidateType } from "./recruitment";

export interface PublicOrganizationSummary {
  name: string;
  slug: string;
}

export interface PublicJobSummary {
  id: string;
  title: string;
  department: string | null;
  location: string | null;
  employment_type: string | null;
  openings_count: number;
  created_at: string;
}

export interface PublicJobDetail extends PublicJobSummary {
  /** null when the recruiter has hidden the JD from the public page. */
  description: string | null;
  organization: PublicOrganizationSummary;
}

export interface PublicApplicationResult {
  id: string;
  job_title: string;
  candidate_email: string;
  status: string;
  submitted_at: string;
}

/** All text inputs are kept as strings (the form's own state); `applyToJob`
 * decides what is sent — experience/availability fields only for
 * EXPERIENCED candidates, and never an empty value. */
export interface JobApplicationFormValues {
  full_name: string;
  email: string;
  phone: string;
  candidate_type: CandidateType;
  years_experience: string;
  notice_period_days: string;
  immediate_joiner: boolean;
  current_title: string;
  current_company: string;
  current_location: string;
  preferred_location: string;
  qualification: string;
  linkedin_url: string;
  github_url: string;
}
