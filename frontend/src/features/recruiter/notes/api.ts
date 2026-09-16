import { apiClient } from "../../../lib/apiClient";
import type { NoteResponse } from "../../../types/note";

export function listNotes(applicationId: string, accessToken: string) {
  return apiClient.get<NoteResponse[]>(
    `/api/v1/recruiter/applications/${applicationId}/notes`,
    accessToken,
  );
}

export function createNote(applicationId: string, body: string, accessToken: string) {
  return apiClient.post<NoteResponse>(
    `/api/v1/recruiter/applications/${applicationId}/notes`,
    { body },
    accessToken,
  );
}
