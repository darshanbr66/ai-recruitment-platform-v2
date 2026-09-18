import { apiClient } from "../../../lib/apiClient";
import type {
  AssessmentCreateRequest,
  AssessmentDeleteRequest,
  AssessmentInvitationResponse,
  AssessmentResponse,
  AssessmentSummary,
  AssessmentUpdateRequest,
  MonitoringEventResponse,
  ParsedQuestionsResponse,
  RetestRequest,
} from "../../../types/assessment";

export function listAssessments(accessToken: string) {
  return apiClient.get<AssessmentSummary[]>("/api/v1/recruiter/assessments", accessToken);
}

export function parseImportQuestions(file: File, accessToken: string) {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient.postForm<ParsedQuestionsResponse>(
    "/api/v1/recruiter/assessments/parse-questions",
    formData,
    accessToken,
  );
}

export function getAssessment(assessmentId: string, accessToken: string) {
  return apiClient.get<AssessmentResponse>(`/api/v1/recruiter/assessments/${assessmentId}`, accessToken);
}

export function createAssessment(payload: AssessmentCreateRequest, accessToken: string) {
  return apiClient.post<AssessmentResponse>("/api/v1/recruiter/assessments", payload, accessToken);
}

export function updateAssessment(
  assessmentId: string,
  payload: AssessmentUpdateRequest,
  accessToken: string,
) {
  return apiClient.patch<AssessmentResponse>(
    `/api/v1/recruiter/assessments/${assessmentId}`,
    payload,
    accessToken,
  );
}

export function inviteCandidate(
  payload: { assessment_id: string; application_id: string },
  accessToken: string,
) {
  return apiClient.post<AssessmentInvitationResponse>(
    "/api/v1/recruiter/assessments/invite",
    payload,
    accessToken,
  );
}

export function getApplicationAssessment(applicationId: string, accessToken: string) {
  return apiClient.get<AssessmentInvitationResponse | null>(
    `/api/v1/recruiter/applications/${applicationId}/assessment`,
    accessToken,
  );
}

export function listApplicationAssessmentAttempts(applicationId: string, accessToken: string) {
  return apiClient.get<AssessmentInvitationResponse[]>(
    `/api/v1/recruiter/applications/${applicationId}/assessment/attempts`,
    accessToken,
  );
}

export function listApplicationAssessmentEvents(applicationId: string, accessToken: string) {
  return apiClient.get<MonitoringEventResponse[]>(
    `/api/v1/recruiter/applications/${applicationId}/assessment/events`,
    accessToken,
  );
}

export function retestCandidate(payload: RetestRequest, accessToken: string) {
  return apiClient.post<AssessmentInvitationResponse>(
    "/api/v1/recruiter/assessments/retest",
    payload,
    accessToken,
  );
}

export function deleteAssessment(
  assessmentId: string,
  payload: AssessmentDeleteRequest,
  accessToken: string,
) {
  return apiClient.post<AssessmentResponse>(
    `/api/v1/recruiter/assessments/${assessmentId}/delete`,
    payload,
    accessToken,
  );
}
