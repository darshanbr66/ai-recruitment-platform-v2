import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { APPLICATION_TRANSITIONS, type ApplicationStatus } from "../../../types/recruitment";
import { useAuth } from "../../auth/AuthContext";
import { listCandidates } from "../candidates/api";
import { listJobs } from "../jobs/api";
import { changeApplicationStatus, createApplication, listApplications } from "./api";

const APPLICATIONS_QUERY_KEY = ["recruiter", "applications"];

const TERMINAL_BADGE: Partial<Record<ApplicationStatus, string>> = {
  SELECTED: "badge-active",
  REJECTED: "badge-inactive",
  WITHDRAWN: "badge-inactive",
};

export function ApplicationsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
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

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: ApplicationStatus }) =>
      changeApplicationStatus(id, status, token),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: APPLICATIONS_QUERY_KEY }),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createApplicationMutation.mutate();
  }

  const canManageApplications = !(
    applicationsQuery.error instanceof ApiError && applicationsQuery.error.status === 403
  );

  return (
    <div className="stack-lg">
      <section>
        <h1>Applications</h1>
        <p className="muted">Every candidate's progress through your hiring pipeline.</p>
      </section>

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
        <section>
          {applicationsQuery.data.length === 0 ? (
            <p className="muted">No applications yet — link a candidate to a job below.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Job</th>
                  <th>Status</th>
                  <th>Applied</th>
                  <th>Move to</th>
                </tr>
              </thead>
              <tbody>
                {applicationsQuery.data.map((application) => {
                  const nextStatuses = APPLICATION_TRANSITIONS[application.status];
                  return (
                    <tr key={application.id}>
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
                      <td>
                        {nextStatuses.length === 0 ? (
                          <span className="muted">Final</span>
                        ) : (
                          <select
                            value=""
                            disabled={statusMutation.isPending}
                            onChange={(e) => {
                              const next = e.target.value as ApplicationStatus;
                              if (next) {
                                statusMutation.mutate({ id: application.id, status: next });
                              }
                            }}
                          >
                            <option value="">Change status…</option>
                            {nextStatuses.map((status) => (
                              <option key={status} value={status}>
                                {status}
                              </option>
                            ))}
                          </select>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </section>
      )}

      {canManageApplications && (
        <section className="card">
          <h2>Link a candidate to a job</h2>
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
