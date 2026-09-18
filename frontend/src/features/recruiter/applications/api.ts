import { apiClient } from "../../../lib/apiClient";
import type {
  ApplicationCreateRequest,
  ApplicationDeleteRequest,
  ApplicationResponse,
  ApplicationStatus,
  SendInterviewEmailRequest,
  SendInterviewEmailResult,
} from "../../../types/recruitment";

export function listApplications(accessToken: string) {
  return apiClient.get<ApplicationResponse[]>("/api/v1/recruiter/applications", accessToken);
}

export function listApplicationsForCandidate(candidateId: string, accessToken: string) {
  return apiClient.get<ApplicationResponse[]>(
    `/api/v1/recruiter/applications?candidate_id=${candidateId}`,
    accessToken,
  );
}

export function listApplicationsForDrive(driveId: string, accessToken: string) {
  return apiClient.get<ApplicationResponse[]>(
    `/api/v1/recruiter/applications?campus_drive_id=${driveId}`,
    accessToken,
  );
}

export function getApplication(applicationId: string, accessToken: string) {
  return apiClient.get<ApplicationResponse>(
    `/api/v1/recruiter/applications/${applicationId}`,
    accessToken,
  );
}

export function createApplication(payload: ApplicationCreateRequest, accessToken: string) {
  return apiClient.post<ApplicationResponse>("/api/v1/recruiter/applications", payload, accessToken);
}

export function changeApplicationStatus(
  applicationId: string,
  toStatus: ApplicationStatus,
  accessToken: string,
) {
  return apiClient.post<ApplicationResponse>(
    `/api/v1/recruiter/applications/${applicationId}/status`,
    { to_status: toStatus },
    accessToken,
  );
}

export function sendInterviewEmail(
  applicationId: string,
  payload: SendInterviewEmailRequest,
  accessToken: string,
) {
  return apiClient.post<SendInterviewEmailResult>(
    `/api/v1/recruiter/applications/${applicationId}/send-interview-email`,
    payload,
    accessToken,
  );
}

export function downloadResume(applicationId: string, accessToken: string) {
  return apiClient.getBlob(
    `/api/v1/recruiter/applications/${applicationId}/resume`,
    accessToken,
  );
}

export function deleteApplication(
  applicationId: string,
  payload: ApplicationDeleteRequest,
  accessToken: string,
) {
  return apiClient.post<ApplicationResponse>(
    `/api/v1/recruiter/applications/${applicationId}/delete`,
    payload,
    accessToken,
  );
}
