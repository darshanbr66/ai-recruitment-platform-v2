import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import type { CampusDriveStatus } from "../../../types/campusDrive";
import { useAuth } from "../../auth/AuthContext";
import { listJobs } from "../jobs/api";
import { createCampusDrive, listCampusDrives } from "./api";

const DRIVES_QUERY_KEY = ["recruiter", "campus-drives"];

const STATUS_BADGE: Record<CampusDriveStatus, string> = {
  PLANNED: "badge-inactive",
  ACTIVE: "badge-active",
  CLOSED: "badge-inactive",
  CANCELLED: "badge-danger",
};

export function CampusDrivesPage() {
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const drivesQuery = useQuery({
    queryKey: DRIVES_QUERY_KEY,
    queryFn: () => listCampusDrives(token),
    enabled: accessToken !== null,
  });

  const jobsQuery = useQuery({
    queryKey: ["recruiter", "jobs"],
    queryFn: () => listJobs(token),
    enabled: accessToken !== null,
  });

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState("");
  const [jobId, setJobId] = useState("");
  const [collegeName, setCollegeName] = useState("");
  const [batchYear, setBatchYear] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createCampusDrive(
        {
          name,
          job_id: jobId,
          college_name: collegeName,
          batch_year: batchYear ? Number(batchYear) : null,
        },
        token,
      ),
    onSuccess: () => {
      setName("");
      setJobId("");
      setCollegeName("");
      setBatchYear("");
      setFormError(null);
      setShowForm(false);
      void queryClient.invalidateQueries({ queryKey: DRIVES_QUERY_KEY });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  const canManage = !(drivesQuery.error instanceof ApiError && drivesQuery.error.status === 403);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Campus Drives</h1>
          <p className="muted">Recruiting events tied to a specific job and college.</p>
        </div>
        {canManage && (
          <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>
            + New drive
          </button>
        )}
      </div>

      {drivesQuery.isPending && <p role="status">Loading campus drives…</p>}
      {drivesQuery.isError && !canManage && (
        <Alert>You do not have permission to view campus drives.</Alert>
      )}

      {drivesQuery.isSuccess &&
        (drivesQuery.data.length === 0 ? (
          <div className="empty-state">
            <p className="empty-state-title">No campus drives yet</p>
            <p>Create one to start mass hiring for a specific job and college.</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Drive</th>
                  <th>Job</th>
                  <th>College</th>
                  <th>Batch</th>
                  <th>Status</th>
                  <th>Applications</th>
                </tr>
              </thead>
              <tbody>
                {drivesQuery.data.map((drive) => (
                  <tr
                    key={drive.id}
                    className="clickable-row"
                    onClick={() => navigate(`/recruiter/campus-drives/${drive.id}`)}
                  >
                    <td>{drive.name}</td>
                    <td>{drive.job_title}</td>
                    <td>{drive.college_name}</td>
                    <td>{drive.batch_year ?? "—"}</td>
                    <td>
                      <span className={`badge ${STATUS_BADGE[drive.status]}`}>{drive.status}</span>
                    </td>
                    <td>{drive.application_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}

      {showForm && (
        <section className="card">
          <div className="page-header">
            <h2>Create a campus drive</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
          <form onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span>Drive name</span>
              <input required value={name} onChange={(e) => setName(e.target.value)} />
            </label>
            <label className="field">
              <span>Job</span>
              <select required value={jobId} onChange={(e) => setJobId(e.target.value)}>
                <option value="" disabled>
                  Select a job…
                </option>
                {jobsQuery.data?.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                ))}
              </select>
            </label>
            <div className="field-row">
              <label className="field">
                <span>College</span>
                <input
                  required
                  value={collegeName}
                  onChange={(e) => setCollegeName(e.target.value)}
                />
              </label>
              <label className="field">
                <span>Batch year</span>
                <input
                  type="number"
                  value={batchYear}
                  onChange={(e) => setBatchYear(e.target.value)}
                />
              </label>
            </div>

            {(jobsQuery.data?.length ?? 0) === 0 && (
              <p className="field-hint">Create a job first from the Jobs page.</p>
            )}

            {formError && <Alert>{formError}</Alert>}

            <button type="submit" className="btn btn-primary" disabled={createMutation.isPending || !jobId}>
              {createMutation.isPending ? "Creating…" : "Create drive"}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
