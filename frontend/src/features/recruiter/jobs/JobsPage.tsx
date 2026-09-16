import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import type { JobStatus } from "../../../types/recruitment";
import { useAuth } from "../../auth/AuthContext";
import { createJob, listJobs, updateJob } from "./api";

const JOBS_QUERY_KEY = ["recruiter", "jobs"];

const STATUS_BADGE_CLASS: Record<JobStatus, string> = {
  DRAFT: "badge-inactive",
  OPEN: "badge-active",
  ON_HOLD: "badge-inactive",
  CLOSED: "badge-inactive",
  WITHDRAWN: "badge-inactive",
};

export function JobsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const jobsQuery = useQuery({
    queryKey: JOBS_QUERY_KEY,
    queryFn: () => listJobs(accessToken as string),
    enabled: accessToken !== null,
  });

  const [title, setTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [location, setLocation] = useState("");
  const [employmentType, setEmploymentType] = useState("Full-time");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

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

  return (
    <div className="stack-lg">
      <section>
        <h1>Jobs</h1>
        <p className="muted">Open requisitions across your organization.</p>
      </section>

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
        <section>
          {jobsQuery.data.length === 0 ? (
            <p className="muted">No jobs yet — create the first one below.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Department</th>
                  <th>Location</th>
                  <th>Openings</th>
                  <th>Status</th>
                  {canManageJobs && <th>Move to</th>}
                </tr>
              </thead>
              <tbody>
                {jobsQuery.data.map((job) => (
                  <tr key={job.id}>
                    <td>{job.title}</td>
                    <td>{job.department ?? "—"}</td>
                    <td>{job.location ?? "—"}</td>
                    <td>{job.openings_count}</td>
                    <td>
                      <span className={`badge ${STATUS_BADGE_CLASS[job.status]}`}>{job.status}</span>
                    </td>
                    {canManageJobs && (
                      <td>
                        <select
                          value=""
                          disabled={statusMutation.isPending}
                          onChange={(e) => {
                            const nextStatus = e.target.value as JobStatus;
                            if (nextStatus) {
                              statusMutation.mutate({ jobId: job.id, status: nextStatus });
                            }
                          }}
                        >
                          <option value="">Change status…</option>
                          {(["DRAFT", "OPEN", "ON_HOLD", "CLOSED", "WITHDRAWN"] as JobStatus[])
                            .filter((status) => status !== job.status)
                            .map((status) => (
                              <option key={status} value={status}>
                                {status}
                              </option>
                            ))}
                        </select>
                      </td>
                    )}
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {canManageJobs && (
        <section className="card">
          <h2>Create a job</h2>
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
