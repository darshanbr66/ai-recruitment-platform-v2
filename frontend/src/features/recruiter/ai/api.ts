import { apiClient } from "../../../lib/apiClient";
import type {
  InternalAIQueryRequest,
  InternalAIQueryResponse,
  JobMatchRequest,
  MatchRequest,
  MatchResponse,
} from "../../../types/internalAi";

export function queryInternalAi(payload: InternalAIQueryRequest, accessToken: string) {
  return apiClient.post<InternalAIQueryResponse>("/api/v1/recruiter/ai/query", payload, accessToken);
}

export function computeMatch(payload: MatchRequest, accessToken: string) {
  return apiClient.post<MatchResponse>("/api/v1/recruiter/ai/match", payload, accessToken);
}

export function computeJobMatches(payload: JobMatchRequest, accessToken: string) {
  return apiClient.post<MatchResponse[]>("/api/v1/recruiter/ai/match/job", payload, accessToken);
}

export function getLatestMatch(candidateId: string, jobId: string, accessToken: string) {
  return apiClient.get<MatchResponse | null>(
    `/api/v1/recruiter/ai/match/${candidateId}/${jobId}`,
    accessToken,
  );
}
