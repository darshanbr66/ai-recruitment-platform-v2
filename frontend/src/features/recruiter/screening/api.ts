import { apiClient } from "../../../lib/apiClient";
import type { ScreeningRunResponse } from "../../../types/screening";

export function startScreening(applicationId: string, accessToken: string) {
  return apiClient.post<ScreeningRunResponse>(
    `/api/v1/recruiter/applications/${applicationId}/screening`,
    undefined,
    accessToken,
  );
}

export function listScreeningRuns(applicationId: string, accessToken: string) {
  return apiClient.get<ScreeningRunResponse[]>(
    `/api/v1/recruiter/applications/${applicationId}/screening`,
    accessToken,
  );
}
