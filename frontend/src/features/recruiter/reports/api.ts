import { apiClient } from "../../../lib/apiClient";
import type { ReportOverview } from "../../../types/report";

export function getReportOverview(accessToken: string) {
  return apiClient.get<ReportOverview>("/api/v1/recruiter/reports/overview", accessToken);
}
