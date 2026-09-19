import { apiClient } from "../../../lib/apiClient";
import type {
  EmailComposeRequest,
  EmailComposeResponse,
  GeneralEmailDraft,
  GeneralEmailPreview,
  GeneralEmailSendResult,
} from "../../../types/email";

/** General (non-application) email. The SMTP account is server-side only —
 * nothing here can choose or see it. */

export function composeGeneralEmail(payload: EmailComposeRequest, accessToken: string) {
  return apiClient.post<EmailComposeResponse>("/api/v1/recruiter/email/compose", payload, accessToken);
}

export function previewGeneralEmail(draft: GeneralEmailDraft, accessToken: string) {
  return apiClient.post<GeneralEmailPreview>("/api/v1/recruiter/email/preview", draft, accessToken);
}

/** The only call that sends a general email — always an explicit user action. */
export function sendGeneralEmail(draft: GeneralEmailDraft, accessToken: string) {
  return apiClient.post<GeneralEmailSendResult>("/api/v1/recruiter/email/send", draft, accessToken);
}
