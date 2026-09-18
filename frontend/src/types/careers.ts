/** Mirrors backend/app/schemas/public.py. */

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

export interface JobApplicationFormValues {
  full_name: string;
  email: string;
  phone: string;
}
