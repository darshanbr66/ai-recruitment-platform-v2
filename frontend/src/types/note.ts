/** Mirrors backend/app/schemas/note.py. */

export type NoteVisibility = "PRIVATE" | "SHARED";

export interface NoteResponse {
  id: string;
  application_id: string | null;
  candidate_id: string | null;
  job_id: string | null;
  author_id: string;
  author_name: string;
  title: string | null;
  body: string;
  category: string | null;
  color: string | null;
  visibility: NoteVisibility;
  created_at: string;
  updated_at: string;
}

export interface StandaloneNoteCreateRequest {
  body: string;
  title?: string | null;
  category?: string | null;
  color?: string | null;
  visibility?: NoteVisibility;
  application_id?: string | null;
  candidate_id?: string | null;
  job_id?: string | null;
}

export interface NoteUpdateRequest {
  body?: string;
  title?: string | null;
  category?: string | null;
  color?: string | null;
  visibility?: NoteVisibility;
  application_id?: string | null;
  candidate_id?: string | null;
  job_id?: string | null;
}

export interface NoteListQuery {
  search?: string;
  category?: string;
  visibility?: NoteVisibility;
  candidateId?: string;
  jobId?: string;
  sort?: "created_at" | "updated_at" | "title";
  order?: "asc" | "desc";
}
