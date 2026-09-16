import { apiClient } from "../../../lib/apiClient";
import type {
  ApplicationCreateRequest,
  ApplicationResponse,
  ApplicationStatus,
} from "../../../types/recruitment";

export function listApplications(accessToken: string) {
  return apiClient.get<ApplicationResponse[]>("/api/v1/recruiter/applications", accessToken);
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
