import { apiClient } from "../../../lib/apiClient";
import type {
  ApplicationCreateRequest,
  ApplicationDeleteRequest,
  ApplicationResponse,
  ApplicationStatus,
} from "../../../types/recruitment";
import type {
  EmailComposeRequest,
  EmailComposeResponse,
  EmailDraft,
  EmailPreview,
  EmailSendResult,
  EmailTemplate,
} from "../../../types/email";

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

export function listEmailTemplates(accessToken: string) {
  return apiClient.get<EmailTemplate[]>("/api/v1/recruiter/email-templates", accessToken);
}

export function composeEmail(
  applicationId: string,
  payload: EmailComposeRequest,
  accessToken: string,
) {
  return apiClient.post<EmailComposeResponse>(
    `/api/v1/recruiter/applications/${applicationId}/email/compose`,
    payload,
    accessToken,
  );
}

export function previewEmail(applicationId: string, draft: EmailDraft, accessToken: string) {
  return apiClient.post<EmailPreview>(
    `/api/v1/recruiter/applications/${applicationId}/email/preview`,
    draft,
    accessToken,
  );
}

/** The only call that emails a candidate — always an explicit user action. */
export function sendEmail(applicationId: string, draft: EmailDraft, accessToken: string) {
  return apiClient.post<EmailSendResult>(
    `/api/v1/recruiter/applications/${applicationId}/email/send`,
    draft,
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
