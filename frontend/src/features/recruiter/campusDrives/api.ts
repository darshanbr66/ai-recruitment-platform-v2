import { apiClient } from "../../../lib/apiClient";
import type {
  CampusDriveCreateRequest,
  CampusDriveDeleteRequest,
  CampusDriveFunnelCounts,
  CampusDriveResponse,
  CampusDriveUpdateRequest,
} from "../../../types/campusDrive";

export function listCampusDrives(accessToken: string) {
  return apiClient.get<CampusDriveResponse[]>("/api/v1/recruiter/campus-drives", accessToken);
}

export function getCampusDrive(driveId: string, accessToken: string) {
  return apiClient.get<CampusDriveResponse>(`/api/v1/recruiter/campus-drives/${driveId}`, accessToken);
}

export function createCampusDrive(payload: CampusDriveCreateRequest, accessToken: string) {
  return apiClient.post<CampusDriveResponse>("/api/v1/recruiter/campus-drives", payload, accessToken);
}

export function updateCampusDrive(
  driveId: string,
  payload: CampusDriveUpdateRequest,
  accessToken: string,
) {
  return apiClient.patch<CampusDriveResponse>(
    `/api/v1/recruiter/campus-drives/${driveId}`,
    payload,
    accessToken,
  );
}

export function getCampusDriveFunnel(driveId: string, accessToken: string) {
  return apiClient.get<CampusDriveFunnelCounts>(
    `/api/v1/recruiter/campus-drives/${driveId}/funnel`,
    accessToken,
  );
}

export function regenerateCampusDriveLink(driveId: string, accessToken: string) {
  return apiClient.post<CampusDriveResponse>(
    `/api/v1/recruiter/campus-drives/${driveId}/regenerate-link`,
    undefined,
    accessToken,
  );
}

export function deleteCampusDrive(
  driveId: string,
  payload: CampusDriveDeleteRequest,
  accessToken: string,
) {
  return apiClient.post<CampusDriveResponse>(
    `/api/v1/recruiter/campus-drives/${driveId}/delete`,
    payload,
    accessToken,
  );
}
