import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { useToast } from "../../../shared/components/ToastContext";
import type { JobResponse, JobStatus } from "../../../types/recruitment";
import { useAuth } from "../../auth/AuthContext";
import { createJob, listJobs, updateJob } from "./api";

const JOBS_QUERY_KEY = ["recruiter", "jobs"];

const STATUS_BADGE_CLASS: Record<JobStatus, string> = {
  DRAFT: "badge-inactive",
  OPEN: "badge-active",
  ON_HOLD: "badge-warn",
  CLOSED: "badge-inactive",
  WITHDRAWN: "badge-inactive",
};

function jobActions(job: JobResponse): { label: string; status: JobStatus; confirm?: boolean }[] {
  switch (job.status) {
    case "DRAFT":
      return [{ label: "Publish", status: "OPEN" }];
    case "OPEN":
      return [
        { label: "Put on hold", status: "ON_HOLD" },
        { label: "Close", status: "CLOSED", confirm: true },
      ];
    case "ON_HOLD":
      return [
        { label: "Reopen", status: "OPEN" },
        { label: "Close", status: "CLOSED", confirm: true },
      ];
    case "CLOSED":
      return [{ label: "Reopen", status: "OPEN" }];
    default:
      return [];
  }
}

interface JobFormState {
  title: string;
  department: string;
  location: string;
  employmentType: string;
  openingsCount: string;
  description: string;
}

const EMPTY_FORM: JobFormState = {
  title: "",
  department: "",
  location: "",
  employmentType: "Full-time",
  openingsCount: "1",
  description: "",
};

function jobToFormState(job: JobResponse): JobFormState {
  return {
    title: job.title,
    department: job.department ?? "",
    location: job.location ?? "",
    employmentType: job.employment_type ?? "",
    openingsCount: String(job.openings_count),
    description: job.description,
  };
}

export function JobsPage() {
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const jobsQuery = useQuery({
    queryKey: JOBS_QUERY_KEY,
    queryFn: () => listJobs(token),
    enabled: accessToken !== null,
  });

  const [search, setSearch] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [editingJob, setEditingJob] = useState<JobResponse | null>(null);
  const [form, setForm] = useState<JobFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [openingsError, setOpeningsError] = useState<string | null>(null);
  const [pendingClose, setPendingClose] = useState<JobResponse | null>(null);

  function openCreateForm() {
    setEditingJob(null);
    setForm(EMPTY_FORM);
    setFormError(null);
    setOpeningsError(null);
    setShowForm(true);
  }

  function openEditForm(job: JobResponse) {
    setEditingJob(job);
    setForm(jobToFormState(job));
    setFormError(null);
    setOpeningsError(null);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
    setEditingJob(null);
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        title: form.title,
        department: form.department || null,
        location: form.location || null,
        employment_type: form.employmentType || null,
        description: form.description,
        openings_count: Number(form.openingsCount),
      };
      return editingJob
        ? updateJob(editingJob.id, payload, token)
        : createJob(payload, token);
    },
    onSuccess: () => {
      showToast(editingJob ? "Job updated." : "Job created.", "success");
      closeForm();
      void queryClient.invalidateQueries({ queryKey: JOBS_QUERY_KEY });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: JobStatus; label: string }) =>
      updateJob(jobId, { status }, token),
    onSuccess: (_data, variables) => {
      showToast(`${variables.label} — done.`, "success");
      setPendingClose(null);
      void queryClient.invalidateQueries({ queryKey: JOBS_QUERY_KEY });
    },
  });

  function validateOpenings(value: string): boolean {
    const num = Number(value);
    if (!Number.isInteger(num) || num < 1) {
      setOpeningsError("Number of openings must be a positive whole number.");
      return false;
    }
    setOpeningsError(null);
    return true;
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!validateOpenings(form.openingsCount)) return;
    saveMutation.mutate();
  }

  function handleAction(job: JobResponse, action: { label: string; status: JobStatus; confirm?: boolean }) {
    if (action.confirm) {
      setPendingClose(job);
    } else {
      statusMutation.mutate({ jobId: job.id, status: action.status, label: action.label });
    }
  }

  const canManageJobs = !(jobsQuery.error instanceof ApiError && jobsQuery.error.status === 403);

  const filteredJobs = useMemo(() => {
    if (!jobsQuery.data) return [];
    const term = search.trim().toLowerCase();
    if (!term) return jobsQuery.data;
    return jobsQuery.data.filter(
      (job) =>
        job.title.toLowerCase().includes(term) ||
        (job.department ?? "").toLowerCase().includes(term) ||
        (job.location ?? "").toLowerCase().includes(term),
    );
  }, [jobsQuery.data, search]);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Jobs</h1>
          <p className="muted">Open requisitions across your organization.</p>
        </div>
        {canManageJobs && (
          <div className="page-header-actions">
            <button type="button" className="btn btn-primary" onClick={openCreateForm}>
              + New job
            </button>
          </div>
        )}
      </div>

      {jobsQuery.isPending && <p role="status">Loading jobs…</p>}

      {jobsQuery.isError && !canManageJobs && (
        <Alert>You do not have permission to view jobs.</Alert>
      )}
      {jobsQuery.isError && canManageJobs && (
        <Alert>
          {jobsQuery.error instanceof ApiError ? jobsQuery.error.message : "Could not load jobs."}
        </Alert>
      )}

      {jobsQuery.isSuccess && (
        <section className="stack-lg" style={{ gap: "1rem" }}>
          {jobsQuery.data.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state-title">No jobs yet</p>
              <p>Create your first requisition to start hiring.</p>
            </div>
          ) : (
            <>
              <div className="toolbar">
                <input
                  className="search-input"
                  placeholder="Search by title, department, or location…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Title</th>
                      <th>Department</th>
                      <th>Location</th>
                      <th>Openings</th>
                      <th>Status</th>
                      {canManageJobs && <th>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredJobs.map((job) => (
                      <tr key={job.id}>
                        <td>{job.title}</td>
                        <td>{job.department ?? "—"}</td>
                        <td>{job.location ?? "—"}</td>
                        <td>{job.openings_count}</td>
                        <td>
                          <span className={`badge ${STATUS_BADGE_CLASS[job.status]}`}>
                            {job.status}
                          </span>
                        </td>
                        {canManageJobs && (
                          <td>
                            <div className="btn-group">
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => openEditForm(job)}
                              >
                                Edit
                              </button>
                              {jobActions(job).map((action) => (
                                <button
                                  key={action.status}
                                  type="button"
                                  className="btn btn-ghost btn-sm"
                                  disabled={statusMutation.isPending}
                                  onClick={() => handleAction(job, action)}
                                >
                                  {action.label}
                                </button>
                              ))}
                            </div>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {canManageJobs && showForm && (
        <section className="card">
          <div className="page-header">
            <h2>{editingJob ? `Edit ${editingJob.title}` : "Create a job"}</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={closeForm}>
              Cancel
            </button>
          </div>
          <form onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span>Title</span>
              <input
                required
                value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })}
                disabled={saveMutation.isPending}
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Department</span>
                <input
                  value={form.department}
                  onChange={(e) => setForm({ ...form, department: e.target.value })}
                  disabled={saveMutation.isPending}
                />
              </label>

              <label className="field">
                <span>Location</span>
                <input
                  value={form.location}
                  onChange={(e) => setForm({ ...form, location: e.target.value })}
                  disabled={saveMutation.isPending}
                />
              </label>
            </div>

            <div className="field-row">
              <label className="field">
                <span>Employment type</span>
                <input
                  value={form.employmentType}
                  onChange={(e) => setForm({ ...form, employmentType: e.target.value })}
                  disabled={saveMutation.isPending}
                />
              </label>

              <label className="field">
                <span>Number of openings</span>
                <input
                  type="number"
                  min={1}
                  step={1}
                  required
                  value={form.openingsCount}
                  onChange={(e) => {
                    setForm({ ...form, openingsCount: e.target.value });
                    if (openingsError) validateOpenings(e.target.value);
                  }}
                  onBlur={(e) => validateOpenings(e.target.value)}
                  disabled={saveMutation.isPending}
                  aria-invalid={openingsError ? "true" : undefined}
                />
                {openingsError ? (
                  <span className="field-hint" style={{ color: "var(--color-danger)" }}>
                    {openingsError}
                  </span>
                ) : (
                  <span className="field-hint">How many positions are you hiring for this role?</span>
                )}
              </label>
            </div>

            <label className="field">
              <span>Description</span>
              <textarea
                required
                rows={4}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                disabled={saveMutation.isPending}
              />
            </label>

            {formError && <Alert>{formError}</Alert>}

            <button type="submit" className="btn btn-primary" disabled={saveMutation.isPending}>
              {saveMutation.isPending
                ? editingJob
                  ? "Saving…"
                  : "Creating…"
                : editingJob
                  ? "Save changes"
                  : "Create job"}
            </button>
          </form>
        </section>
      )}

      {pendingClose && (
        <ConfirmDialog
          title="Close this job?"
          message={`This closes "${pendingClose.title}". It stays in your job history and any existing applications are unaffected — you can reopen it at any time.`}
          confirmLabel="Close job"
          isConfirming={statusMutation.isPending}
          onCancel={() => setPendingClose(null)}
          onConfirm={() =>
            statusMutation.mutate({ jobId: pendingClose.id, status: "CLOSED", label: "Close" })
          }
        />
      )}
    </div>
  );
}
