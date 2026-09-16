/** Mirrors backend/app/schemas/note.py. */

export interface NoteResponse {
  id: string;
  application_id: string;
  author_id: string;
  author_name: string;
  body: string;
  created_at: string;
}
