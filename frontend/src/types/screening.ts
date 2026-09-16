/** Mirrors backend/app/schemas/screening.py. */

export type ScreeningStatus = "PENDING" | "COMPLETED" | "FAILED";

export interface ScreeningRunResponse {
  id: string;
  application_id: string;
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
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}
