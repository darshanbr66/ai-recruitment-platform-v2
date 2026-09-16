import { apiClient } from "../../../lib/apiClient";
import type { CandidateCreateRequest, CandidateResponse } from "../../../types/recruitment";

export function listCandidates(accessToken: string) {
  return apiClient.get<CandidateResponse[]>("/api/v1/recruiter/candidates", accessToken);
}

export function createCandidate(payload: CandidateCreateRequest, accessToken: string) {
  return apiClient.post<CandidateResponse>("/api/v1/recruiter/candidates", payload, accessToken);
}

export function getCandidate(candidateId: string, accessToken: string) {
  return apiClient.get<CandidateResponse>(`/api/v1/recruiter/candidates/${candidateId}`, accessToken);
}
