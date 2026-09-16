/** Mirrors backend/app/schemas/assessment.py and public_assessment.py. */

export type QuestionType = "MCQ_SINGLE" | "MCQ_MULTI";
export type InvitationStatus = "SENT" | "STARTED" | "SUBMITTED" | "EXPIRED" | "CANCELLED";

export interface QuestionOptionCreate {
  label: string;
  is_correct: boolean;
}

export interface QuestionCreate {
  prompt: string;
  type: QuestionType;
  points: number;
  options: QuestionOptionCreate[];
}

export interface AssessmentCreateRequest {
  title: string;
  instructions: string;
  duration_minutes: number;
  pass_score: number;
  questions: QuestionCreate[];
}

export interface QuestionOptionResponse {
  id: string;
  label: string;
  is_correct: boolean;
}

export interface QuestionResponse {
  id: string;
  prompt: string;
  type: QuestionType;
  points: number;
  options: QuestionOptionResponse[];
}

export interface AssessmentResponse {
  id: string;
  title: string;
  instructions: string;
  duration_minutes: number;
  pass_score: number;
  created_at: string;
  questions: QuestionResponse[];
}

export interface AssessmentSummary {
  id: string;
  title: string;
  duration_minutes: number;
  pass_score: number;
  question_count: number;
  created_at: string;
}

export interface AssessmentResultResponse {
  score: number;
  max_score: number;
  percentage: number;
  passed: boolean;
  evaluated_at: string;
}

export interface AssessmentInvitationResponse {
  id: string;
  assessment_id: string;
  assessment_title: string;
  application_id: string;
  candidate_full_name: string;
  status: InvitationStatus;
  expires_at: string;
  started_at: string | null;
  submitted_at: string | null;
  result: AssessmentResultResponse | null;
  invitation_link: string | null;
}

// --- Public (candidate-facing, token-based) ---

export interface PublicQuestionOption {
  id: string;
  label: string;
}

export interface PublicQuestion {
  id: string;
  prompt: string;
  type: QuestionType;
  points: number;
  options: PublicQuestionOption[];
}

export interface PublicInvitationView {
  status: InvitationStatus;
  assessment_title: string;
  instructions: string;
  duration_minutes: number;
  job_title: string;
  organization_name: string;
  expires_at: string;
  started_at: string | null;
  questions: PublicQuestion[];
}

export interface AnswerSubmission {
  question_id: string;
  selected_option_ids: string[];
}

export interface PublicSubmissionResult {
  score: number;
  max_score: number;
  percentage: number;
  passed: boolean;
}
