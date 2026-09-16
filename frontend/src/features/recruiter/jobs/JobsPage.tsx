import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
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

function jobActions(job: JobResponse): { label: string; status: JobStatus }[] {
  switch (job.status) {
    case "DRAFT":
      return [{ label: "Publish", status: "OPEN" }];
    case "OPEN":
      return [
        { label: "Put on hold", status: "ON_HOLD" },
        { label: "Close", status: "CLOSED" },
      ];
    case "ON_HOLD":
      return [
        { label: "Reopen", status: "OPEN" },
        { label: "Close", status: "CLOSED" },
      ];
    default:
      return [];
  }
}

export function JobsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const jobsQuery = useQuery({
    queryKey: JOBS_QUERY_KEY,
    queryFn: () => listJobs(accessToken as string),
    enabled: accessToken !== null,
  });

  const [search, setSearch] = useState("");
  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [location, setLocation] = useState("");
  const [employmentType, setEmploymentType] = useState("Full-time");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);

  const createJobMutation = useMutation({
    mutationFn: () =>
      createJob(
        {
          title,
          department: department || null,
          location: location || null,
          employment_type: employmentType || null,
          description,
        },
        accessToken as string,
      ),
    onSuccess: () => {
      setTitle("");
      setDepartment("");
      setLocation("");
      setDescription("");
      setFormError(null);
      setShowForm(false);
      void queryClient.invalidateQueries({ queryKey: JOBS_QUERY_KEY });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  const statusMutation = useMutation({
    mutationFn: ({ jobId, status }: { jobId: string; status: JobStatus }) =>
      updateJob(jobId, { status }, accessToken as string),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: JOBS_QUERY_KEY }),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createJobMutation.mutate();
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
            <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>
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
                              {jobActions(job).map((action) => (
                                <button
                                  key={action.status}
                                  type="button"
                                  className="btn btn-ghost btn-sm"
                                  disabled={statusMutation.isPending}
                                  onClick={() =>
                                    statusMutation.mutate({ jobId: job.id, status: action.status })
                                  }
                                >
                                  {action.label}
                                </button>
                              ))}
                              {jobActions(job).length === 0 && (
                                <span className="muted">No actions</span>
                              )}
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
            <h2>Create a job</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
          <form onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span>Title</span>
              <input
                required
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                disabled={createJobMutation.isPending}
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Department</span>
                <input
                  value={department}
                  onChange={(e) => setDepartment(e.target.value)}
                  disabled={createJobMutation.isPending}
                />
              </label>

              <label className="field">
                <span>Location</span>
                <input
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                  disabled={createJobMutation.isPending}
                />
              </label>
            </div>

            <label className="field">
              <span>Employment type</span>
              <input
                value={employmentType}
                onChange={(e) => setEmploymentType(e.target.value)}
                disabled={createJobMutation.isPending}
              />
            </label>

            <label className="field">
              <span>Description</span>
              <textarea
                required
                rows={4}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                disabled={createJobMutation.isPending}
              />
            </label>

            {formError && <Alert>{formError}</Alert>}

            <button type="submit" className="btn btn-primary" disabled={createJobMutation.isPending}>
              {createJobMutation.isPending ? "Creating…" : "Create job"}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
