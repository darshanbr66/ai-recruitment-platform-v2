import { apiClient } from "../../lib/apiClient";
import type {
  JobApplicationFormValues,
  PublicApplicationResult,
  PublicJobDetail,
  PublicJobSummary,
} from "../../types/careers";
import type {
  AnswerSubmission,
  MonitoringEventCreate,
  PublicInvitationView,
  PublicSubmissionResult,
} from "../../types/assessment";
import type {
  CampusDriveApplicationFormValues,
  PublicCampusDriveApplicationResult,
  PublicCampusDriveResult,
} from "../../types/publicCampusDrive";

export function listOpenJobs(slug: string) {
  return apiClient.get<PublicJobSummary[]>(`/api/v1/public/organizations/${slug}/jobs`);
}

export function getOpenJob(slug: string, jobId: string) {
  return apiClient.get<PublicJobDetail>(`/api/v1/public/organizations/${slug}/jobs/${jobId}`);
}

export function applyToJob(
  slug: string,
  jobId: string,
  values: JobApplicationFormValues,
  resume: File,
) {
  const formData = new FormData();
  formData.append("full_name", values.full_name);
  formData.append("email", values.email);
  if (values.phone) formData.append("phone", values.phone);
  formData.append("resume", resume);

  return apiClient.postForm<PublicApplicationResult>(
    `/api/v1/public/organizations/${slug}/jobs/${jobId}/apply`,
    formData,
  );
}

export function getAssessmentInvitation(token: string) {
  return apiClient.get<PublicInvitationView>(`/api/v1/public/assessment/${token}`);
}

export function startAssessment(token: string) {
  return apiClient.post<PublicInvitationView>(`/api/v1/public/assessment/${token}/start`);
}

export function submitAssessment(token: string, answers: AnswerSubmission[]) {
  return apiClient.post<PublicSubmissionResult>(`/api/v1/public/assessment/${token}/submit`, {
    answers,
  });
}

export function sendMonitoringEvents(token: string, events: MonitoringEventCreate[]) {
  return apiClient.post<void>(`/api/v1/public/assessment/${token}/events`, { events });
}

export function getCampusDriveByToken(token: string) {
  return apiClient.get<PublicCampusDriveResult>(`/api/v1/public/campus-drive/${token}`);
}

export function applyToCampusDrive(
  token: string,
  values: CampusDriveApplicationFormValues,
  resume: File,
) {
  const formData = new FormData();
  formData.append("full_name", values.full_name);
  formData.append("email", values.email);
  if (values.phone) formData.append("phone", values.phone);
  formData.append("resume", resume);

  return apiClient.postForm<PublicCampusDriveApplicationResult>(
    `/api/v1/public/campus-drive/${token}/apply`,
    formData,
  );
}
