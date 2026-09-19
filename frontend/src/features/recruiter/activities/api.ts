import { apiClient } from "../../../lib/apiClient";
import type {
  ActivityCount,
  ActivityDeleteResult,
  ActivityResponse,
} from "../../../types/activity";

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

export function deleteActivity(activityId: string, accessToken: string) {
  return apiClient.delete(`/api/v1/recruiter/activities/${activityId}`, accessToken);
}

/** The organization's total entry count — what "Delete all" would remove. */
export function countActivities(accessToken: string) {
  return apiClient.get<ActivityCount>("/api/v1/recruiter/activities/count", accessToken);
}

/** Deletes the selected entries in one request; `deleted` is the number of
 * rows actually removed (ids already gone are not counted). */
export function deleteSelectedActivities(activityIds: string[], accessToken: string) {
  return apiClient.delete<ActivityDeleteResult>(
    "/api/v1/recruiter/activities/bulk",
    accessToken,
    { activity_ids: activityIds },
  );
}

/** Deletes every entry of the caller's own organization. */
export function deleteAllActivities(accessToken: string) {
  return apiClient.delete<ActivityDeleteResult>("/api/v1/recruiter/activities/all", accessToken, {
    confirm: true,
  });
}
