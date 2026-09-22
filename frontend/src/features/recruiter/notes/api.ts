import { apiClient } from "../../../lib/apiClient";
import type { NoteListQuery, NoteResponse, NoteUpdateRequest, StandaloneNoteCreateRequest } from "../../../types/note";

/** The application detail page's note feed. */
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

/** The standalone Notes workspace (`/recruiter/notes`) — every note visible
 * to the caller (their own private ones + everyone's shared ones). */
export function listMyNotes(accessToken: string, query: NoteListQuery = {}) {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.category) params.set("category", query.category);
  if (query.visibility) params.set("visibility", query.visibility);
  if (query.candidateId) params.set("candidate_id", query.candidateId);
  if (query.jobId) params.set("job_id", query.jobId);
  if (query.sort) params.set("sort", query.sort);
  if (query.order) params.set("order", query.order);
  const search = params.toString();
  return apiClient.get<NoteResponse[]>(`/api/v1/recruiter/notes${search ? `?${search}` : ""}`, accessToken);
}

export function createMyNote(payload: StandaloneNoteCreateRequest, accessToken: string) {
  return apiClient.post<NoteResponse>("/api/v1/recruiter/notes", payload, accessToken);
}

export function updateMyNote(noteId: string, payload: NoteUpdateRequest, accessToken: string) {
  return apiClient.patch<NoteResponse>(`/api/v1/recruiter/notes/${noteId}`, payload, accessToken);
}

export function deleteMyNote(noteId: string, accessToken: string) {
  return apiClient.delete(`/api/v1/recruiter/notes/${noteId}`, accessToken);
}
