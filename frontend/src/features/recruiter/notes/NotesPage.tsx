import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { EmptyState } from "../../../shared/components/EmptyState";
import { Modal } from "../../../shared/components/Modal";
import { SkeletonList } from "../../../shared/components/Skeleton";
import { Spinner } from "../../../shared/components/Spinner";
import { useToast } from "../../../shared/components/ToastContext";
import type { NoteResponse, NoteVisibility } from "../../../types/note";
import { useAuth } from "../../auth/AuthContext";
import { listCandidates } from "../candidates/api";
import { listJobs } from "../jobs/api";
import { createMyNote, deleteMyNote, listMyNotes, updateMyNote } from "./api";

const NOTES_QUERY_KEY = ["recruiter", "notes", "mine"];

const COLOR_SWATCHES = [
  { value: "", label: "None" },
  { value: "#4f7cff", label: "Blue" },
  { value: "#2fa06a", label: "Green" },
  { value: "#e0a72e", label: "Amber" },
  { value: "#d9534f", label: "Red" },
  { value: "#9b6ad8", label: "Purple" },
];

interface NoteFormState {
  title: string;
  body: string;
  category: string;
  color: string;
  visibility: NoteVisibility;
  candidateId: string;
  jobId: string;
}

const EMPTY_FORM: NoteFormState = {
  title: "",
  body: "",
  category: "",
  color: "",
  visibility: "PRIVATE",
  candidateId: "",
  jobId: "",
};

function noteToFormState(note: NoteResponse): NoteFormState {
  return {
    title: note.title ?? "",
    body: note.body,
    category: note.category ?? "",
    color: note.color ?? "",
    visibility: note.visibility,
    candidateId: note.candidate_id ?? "",
    jobId: note.job_id ?? "",
  };
}

export function NotesPage() {
  const { accessToken, user } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const [search, setSearch] = useState("");
  const [visibilityFilter, setVisibilityFilter] = useState<"" | NoteVisibility>("");
  const [sort, setSort] = useState<"created_at" | "updated_at" | "title">("created_at");
  const [showForm, setShowForm] = useState(false);
  const [editingNote, setEditingNote] = useState<NoteResponse | null>(null);
  const [form, setForm] = useState<NoteFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<NoteResponse | null>(null);

  const notesQuery = useQuery({
    queryKey: [...NOTES_QUERY_KEY, search, visibilityFilter, sort],
    queryFn: () =>
      listMyNotes(token, {
        search: search.trim() || undefined,
        visibility: visibilityFilter || undefined,
        sort,
        order: "desc",
      }),
    enabled: accessToken !== null,
  });

  const candidatesQuery = useQuery({
    queryKey: ["recruiter", "candidates"],
    queryFn: () => listCandidates(token),
    enabled: accessToken !== null && showForm,
  });
  const jobsQuery = useQuery({
    queryKey: ["recruiter", "jobs"],
    queryFn: () => listJobs(token),
    enabled: accessToken !== null && showForm,
  });

  function openCreateForm() {
    setEditingNote(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setShowForm(true);
  }

  function openEditForm(note: NoteResponse) {
    setEditingNote(note);
    setForm(noteToFormState(note));
    setFormError(null);
    setShowForm(true);
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        title: form.title || null,
        body: form.body,
        category: form.category || null,
        color: form.color || null,
        visibility: form.visibility,
        candidate_id: form.candidateId || null,
        job_id: form.jobId || null,
      };
      return editingNote ? updateMyNote(editingNote.id, payload, token) : createMyNote(payload, token);
    },
    onSuccess: () => {
      showToast(editingNote ? "Note updated." : "Note created.", "success");
      setShowForm(false);
      void queryClient.invalidateQueries({ queryKey: NOTES_QUERY_KEY });
    },
    onError: (err) => setFormError(err instanceof ApiError ? err.message : "Unable to reach the server."),
  });

  const deleteMutation = useMutation({
    mutationFn: () => deleteMyNote(pendingDelete!.id, token),
    onSuccess: () => {
      showToast("Note deleted.", "success");
      setPendingDelete(null);
      void queryClient.invalidateQueries({ queryKey: NOTES_QUERY_KEY });
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate();
  }

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Notes</h1>
          <p className="muted">Your personal reminders and shared commentary.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={openCreateForm}>
          + New note
        </button>
      </div>

      <div className="toolbar">
        <input
          className="search-input"
          placeholder="Search notes…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="filter-select"
          value={visibilityFilter}
          onChange={(e) => setVisibilityFilter(e.target.value as "" | NoteVisibility)}
        >
          <option value="">All notes</option>
          <option value="PRIVATE">Private only</option>
          <option value="SHARED">Shared only</option>
        </select>
        <select className="filter-select" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
          <option value="created_at">Newest first</option>
          <option value="updated_at">Recently updated</option>
          <option value="title">Title (A-Z)</option>
        </select>
      </div>

      {notesQuery.isPending && <SkeletonList rows={4} />}
      {notesQuery.isError && (
        <Alert>{notesQuery.error instanceof ApiError ? notesQuery.error.message : "Could not load notes."}</Alert>
      )}

      {notesQuery.isSuccess && notesQuery.data.length === 0 && (
        <EmptyState
          icon="graph"
          title="No notes yet"
          action={
            <button type="button" className="btn btn-primary" onClick={openCreateForm}>
              Write your first note
            </button>
          }
        >
          Personal reminders, candidate follow-ups, and shared team commentary all live here.
        </EmptyState>
      )}

      {notesQuery.isSuccess && notesQuery.data.length > 0 && (
        <div className="card-grid note-grid">
          {notesQuery.data.map((note) => {
            const isOwn = note.author_id === user?.id;
            return (
              <article
                key={note.id}
                className="card note-card"
                style={note.color ? { borderLeft: `4px solid ${note.color}` } : undefined}
              >
                <div className="note-card-head">
                  <span className={`badge ${note.visibility === "PRIVATE" ? "badge-inactive" : "badge-active"}`}>
                    {note.visibility === "PRIVATE" ? "Private" : "Shared"}
                  </span>
                  {note.category && <span className="chip">{note.category}</span>}
                </div>
                <h3 style={{ margin: "0.5rem 0 0.25rem" }}>{note.title || "Untitled note"}</h3>
                <p className="note-card-body">{note.body}</p>
                <div className="note-card-foot">
                  <span className="muted" style={{ fontSize: "0.75rem" }}>
                    {note.author_name} · {new Date(note.updated_at).toLocaleDateString()}
                  </span>
                  {isOwn && (
                    <div className="btn-group">
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => openEditForm(note)}>
                        Edit
                      </button>
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => setPendingDelete(note)}
                      >
                        Delete
                      </button>
                    </div>
                  )}
                </div>
              </article>
            );
          })}
        </div>
      )}

      {showForm && (
        <Modal title={editingNote ? "Edit note" : "New note"} onClose={() => setShowForm(false)} wide>
          <form onSubmit={handleSubmit}>
            <label className="field">
              <span>Title</span>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} disabled={saveMutation.isPending} />
            </label>
            <label className="field">
              <span>Content</span>
              <textarea
                required
                rows={4}
                value={form.body}
                onChange={(e) => setForm({ ...form, body: e.target.value })}
                disabled={saveMutation.isPending}
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Category</span>
                <input
                  value={form.category}
                  onChange={(e) => setForm({ ...form, category: e.target.value })}
                  placeholder="e.g. Interview, Follow-up"
                  disabled={saveMutation.isPending}
                />
              </label>
              <label className="field">
                <span>Color</span>
                <select value={form.color} onChange={(e) => setForm({ ...form, color: e.target.value })} disabled={saveMutation.isPending}>
                  {COLOR_SWATCHES.map((swatch) => (
                    <option key={swatch.value} value={swatch.value}>
                      {swatch.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <div className="field-row">
              <label className="field">
                <span>Related candidate (optional)</span>
                <select
                  value={form.candidateId}
                  onChange={(e) => setForm({ ...form, candidateId: e.target.value })}
                  disabled={saveMutation.isPending || candidatesQuery.isPending}
                >
                  <option value="">None</option>
                  {candidatesQuery.data?.map((candidate) => (
                    <option key={candidate.id} value={candidate.id}>
                      {candidate.full_name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Related job (optional)</span>
                <select
                  value={form.jobId}
                  onChange={(e) => setForm({ ...form, jobId: e.target.value })}
                  disabled={saveMutation.isPending || jobsQuery.isPending}
                >
                  <option value="">None</option>
                  {jobsQuery.data?.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.title}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="field">
              <span>Visibility</span>
              <select
                value={form.visibility}
                onChange={(e) => setForm({ ...form, visibility: e.target.value as NoteVisibility })}
                disabled={saveMutation.isPending}
              >
                <option value="PRIVATE">Private — only you can see this</option>
                <option value="SHARED">Shared — visible to your team</option>
              </select>
            </label>

            {formError && <Alert>{formError}</Alert>}

            <div className="btn-group" style={{ marginTop: "1rem" }}>
              <button type="submit" className="btn btn-primary" disabled={saveMutation.isPending}>
                {saveMutation.isPending ? <Spinner label="Saving…" /> : editingNote ? "Save changes" : "Create note"}
              </button>
              <button type="button" className="btn btn-ghost" onClick={() => setShowForm(false)} disabled={saveMutation.isPending}>
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}

      {pendingDelete && (
        <ConfirmDialog
          title="Delete this note?"
          message="This permanently removes the note. This cannot be undone."
          confirmLabel="Delete note"
          isConfirming={deleteMutation.isPending}
          onCancel={() => setPendingDelete(null)}
          onConfirm={() => deleteMutation.mutate()}
        />
      )}
    </div>
  );
}
