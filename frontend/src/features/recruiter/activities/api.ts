import { apiClient } from "../../../lib/apiClient";
import type { ActivityResponse } from "../../../types/activity";

export interface ActivityFilters {
  search?: string;
  action?: string;
  entity_type?: string;
}

export function listActivities(filters: ActivityFilters, accessToken: string) {
  const params = new URLSearchParams();
  if (filters.search) params.set("search", filters.search);
  if (filters.action) params.set("action", filters.action);
  if (filters.entity_type) params.set("entity_type", filters.entity_type);
  const query = params.toString();
  return apiClient.get<ActivityResponse[]>(
    `/api/v1/recruiter/activities${query ? `?${query}` : ""}`,
    accessToken,
  );
}
