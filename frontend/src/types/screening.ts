/** Mirrors backend/app/schemas/screening.py. */

export type ScreeningStatus = "PENDING" | "COMPLETED" | "FAILED";

export type ScreeningDecision = "MATCH" | "NOT_MATCH";

export interface ScreeningRunResponse {
  id: string;
  application_id: string;
  /** null = the automatic run at application submission. */
  requested_by_user_id: string | null;
  status: ScreeningStatus;
  provider: string;
  model: string;
  overall_score: number | null;
  recommendation: string | null;
  summary: string | null;
  matching_skills: string[] | null;
  missing_skills: string[] | null;
  strengths: string[] | null;
  concerns: string[] | null;
  experience_assessment: string | null;
  education_assessment: string | null;
  decision: ScreeningDecision | null;
  matched_requirements: string[] | null;
  missing_requirements: string[] | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}
