import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { APPLICATION_STATUSES, type ApplicationStatus } from "../../../types/recruitment";
import { useAuth } from "../../auth/AuthContext";
import { listCandidates } from "../candidates/api";
import { listJobs } from "../jobs/api";
import { createApplication, listApplications } from "./api";

const APPLICATIONS_QUERY_KEY = ["recruiter", "applications"];

const TERMINAL_BADGE: Partial<Record<ApplicationStatus, string>> = {
  SELECTED: "badge-active",
  REJECTED: "badge-inactive",
  WITHDRAWN: "badge-inactive",
};

export function ApplicationsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const token = accessToken as string;

  const applicationsQuery = useQuery({
    queryKey: APPLICATIONS_QUERY_KEY,
    queryFn: () => listApplications(token),
    enabled: accessToken !== null,
  });

  const candidatesQuery = useQuery({
    queryKey: ["recruiter", "candidates"],
    queryFn: () => listCandidates(token),
    enabled: accessToken !== null,
  });

  const jobsQuery = useQuery({
    queryKey: ["recruiter", "jobs"],
    queryFn: () => listJobs(token),
    enabled: accessToken !== null,
  });

  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | "">("");
  const [jobFilter, setJobFilter] = useState("");

  const [candidateId, setCandidateId] = useState("");
  const [jobId, setJobId] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const createApplicationMutation = useMutation({
    mutationFn: () => createApplication({ candidate_id: candidateId, job_id: jobId }, token),
    onSuccess: () => {
      setCandidateId("");
      setJobId("");
      setFormError(null);
      void queryClient.invalidateQueries({ queryKey: APPLICATIONS_QUERY_KEY });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createApplicationMutation.mutate();
  }

  const canManageApplications = !(
    applicationsQuery.error instanceof ApiError && applicationsQuery.error.status === 403
  );

  const filteredApplications = useMemo(() => {
    if (!applicationsQuery.data) return [];
    return applicationsQuery.data.filter((application) => {
      if (statusFilter && application.status !== statusFilter) return false;
      if (jobFilter && application.job_id !== jobFilter) return false;
      return true;
    });
  }, [applicationsQuery.data, statusFilter, jobFilter]);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Applications</h1>
          <p className="muted">Every candidate's progress through your hiring pipeline.</p>
        </div>
      </div>

      {applicationsQuery.isPending && <p role="status">Loading applications…</p>}

      {applicationsQuery.isError && !canManageApplications && (
        <Alert>You do not have permission to view applications.</Alert>
      )}
      {applicationsQuery.isError && canManageApplications && (
        <Alert>
          {applicationsQuery.error instanceof ApiError
            ? applicationsQuery.error.message
            : "Could not load applications."}
        </Alert>
      )}

      {applicationsQuery.isSuccess && (
        <section className="stack-lg" style={{ gap: "1rem" }}>
          {applicationsQuery.data.length > 0 && (
            <div className="toolbar">
              <select
                className="filter-select"
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value as ApplicationStatus | "")}
              >
                <option value="">All statuses</option>
                {APPLICATION_STATUSES.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
              <select
                className="filter-select"
                value={jobFilter}
                onChange={(e) => setJobFilter(e.target.value)}
              >
                <option value="">All jobs</option>
                {jobsQuery.data?.map((job) => (
                  <option key={job.id} value={job.id}>
                    {job.title}
                  </option>
                ))}
              </select>
            </div>
          )}

          {applicationsQuery.data.length === 0 ? (
            <p className="muted">No applications yet — link a candidate to a job below.</p>
          ) : filteredApplications.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state-title">No applications match these filters</p>
              <p>Try clearing the status or job filter.</p>
            </div>
          ) : (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Candidate</th>
                    <th>Job</th>
                    <th>Status</th>
                    <th>Applied</th>
                    <th>Resume</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredApplications.map((application) => (
                    <tr
                      key={application.id}
                      className="clickable-row"
                      onClick={() => navigate(`/recruiter/applications/${application.id}`)}
                    >
                      <td>{application.candidate_full_name}</td>
                      <td>{application.job_title}</td>
                      <td>
                        <span
                          className={`badge ${TERMINAL_BADGE[application.status] ?? "badge-active"}`}
                        >
                          {application.status}
                        </span>
                      </td>
                      <td>{new Date(application.applied_at).toLocaleDateString()}</td>
                      <td>{application.resume_id ? "Yes" : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {canManageApplications && (
        <section className="card">
          <h2>Link a candidate to a job</h2>
          <p className="muted">
            Most applications arrive through your career site automatically — use this to add one
            by hand.
          </p>
          <form onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span>Candidate</span>
              <select
                required
                value={candidateId}
                onChange={(e) => setCandidateId(e.target.value)}
                disabled={createApplicationMutation.isPending}
              >
                <option value="" disabled>
                  Select a candidate…
                </option>
                {candidatesQuery.data?.map((candidate) => (
                  <option key={candidate.id} value={candidate.id}>
                    {candidate.full_name} ({candidate.email})
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Job</span>
              <select
                required
                value={jobId}
                onChange={(e) => setJobId(e.target.value)}
                disabled={createApplicationMutation.isPending}
              >
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

            {(candidatesQuery.data?.length ?? 0) === 0 && (
              <p className="field-hint">Add a candidate first from the Candidates page.</p>
            )}
            {(jobsQuery.data?.length ?? 0) === 0 && (
              <p className="field-hint">Create a job first from the Jobs page.</p>
            )}

            {formError && <Alert>{formError}</Alert>}

            <button
              type="submit"
              className="btn btn-primary"
              disabled={createApplicationMutation.isPending || !candidateId || !jobId}
            >
              {createApplicationMutation.isPending ? "Linking…" : "Create application"}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
