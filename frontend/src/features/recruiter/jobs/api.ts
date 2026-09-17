import { apiClient } from "../../../lib/apiClient";
import type {
  JobCreateRequest,
  JobDeleteRequest,
  JobResponse,
  JobUpdateRequest,
} from "../../../types/recruitment";

export function listJobs(accessToken: string) {
  return apiClient.get<JobResponse[]>("/api/v1/recruiter/jobs", accessToken);
}

export function createJob(payload: JobCreateRequest, accessToken: string) {
  return apiClient.post<JobResponse>("/api/v1/recruiter/jobs", payload, accessToken);
}

export function updateJob(jobId: string, payload: JobUpdateRequest, accessToken: string) {
  return apiClient.patch<JobResponse>(`/api/v1/recruiter/jobs/${jobId}`, payload, accessToken);
}

export function deleteJob(jobId: string, payload: JobDeleteRequest, accessToken: string) {
  return apiClient.post<JobResponse>(`/api/v1/recruiter/jobs/${jobId}/delete`, payload, accessToken);
}
