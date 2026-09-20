import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { Modal } from "../../../shared/components/Modal";
import { EmptyState } from "../../../shared/components/EmptyState";
import { SkeletonTable } from "../../../shared/components/Skeleton";
import { statusTone, toneBadgeClass } from "../../../shared/lib/statusTone";
import { Spinner } from "../../../shared/components/Spinner";
import { useToast } from "../../../shared/components/ToastContext";
import type { ApplicationResponse } from "../../../types/recruitment";
import { APPLICATION_STATUSES, type ApplicationStatus } from "../../../types/recruitment";
import { useAuth } from "../../auth/AuthContext";
import { listCandidates } from "../candidates/api";
import { listJobs } from "../jobs/api";
import { createApplication, deleteApplication, listApplications } from "./api";

const APPLICATIONS_QUERY_KEY = ["recruiter", "applications"];

export function ApplicationsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const token = accessToken as string;
  const { showToast } = useToast();
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch] = useState("");

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
  const [pendingDelete, setPendingDelete] = useState<ApplicationResponse | null>(null);
  const [deleteReason, setDeleteReason] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const createApplicationMutation = useMutation({
    mutationFn: () => createApplication({ candidate_id: candidateId, job_id: jobId }, token),
    onSuccess: () => {
      showToast("Application created.", "success");
      setCandidateId("");
      setJobId("");
      setFormError(null);
      setShowForm(false);
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

  function closeForm() {
    if (createApplicationMutation.isPending) return;
    setShowForm(false);
  }

  const deleteMutation = useMutation({
    mutationFn: () => deleteApplication(pendingDelete!.id, { reason: deleteReason.trim() }, token),
    onSuccess: () => {
      showToast(`Application for ${pendingDelete?.candidate_full_name} was deleted.`, "success");
      setPendingDelete(null);
      setDeleteReason("");
      setDeleteError(null);
      void queryClient.invalidateQueries({ queryKey: APPLICATIONS_QUERY_KEY });
    },
    onError: (err) => {
      setDeleteError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function openDeleteModal(application: ApplicationResponse) {
    setPendingDelete(application);
    setDeleteReason("");
    setDeleteError(null);
  }

  function closeDeleteModal() {
    if (deleteMutation.isPending) return;
    setPendingDelete(null);
    setDeleteReason("");
    setDeleteError(null);
  }

  function handleDeleteSubmit(event: FormEvent) {
    event.preventDefault();
    if (deleteReason.trim().length === 0) {
      setDeleteError("A reason for deletion is required.");
      return;
    }
    deleteMutation.mutate();
  }

  const canManageApplications = !(
    applicationsQuery.error instanceof ApiError && applicationsQuery.error.status === 403
  );

  const filteredApplications = useMemo(() => {
    if (!applicationsQuery.data) return [];
    const term = search.trim().toLowerCase();
    return applicationsQuery.data.filter((application) => {
      if (statusFilter && application.status !== statusFilter) return false;
      if (jobFilter && application.job_id !== jobFilter) return false;
      if (
        term &&
        !application.candidate_full_name.toLowerCase().includes(term) &&
        !application.job_title.toLowerCase().includes(term)
      ) {
        return false;
      }
      return true;
    });
  }, [applicationsQuery.data, statusFilter, jobFilter, search]);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Applications</h1>
          <p className="muted">Every candidate's progress through your hiring pipeline.</p>
        </div>
        {canManageApplications && (
          <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>
            + Link candidate to job
          </button>
        )}
      </div>

      {applicationsQuery.isPending && <SkeletonTable columns={7} />}

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
              <input
                className="search-input"
                placeholder="Search by candidate or job…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
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
            <EmptyState icon="inbox" title="No applications yet">
              Use "+ Link candidate to job" above to add one, or wait for candidates to apply.
            </EmptyState>
          ) : filteredApplications.length === 0 ? (
            <EmptyState icon="search" title="No applications match these filters">
              Try clearing the search, status, or job filter.
            </EmptyState>
          ) : (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Candidate</th>
                    <th>Job</th>
                    <th>Status</th>
                    <th>Source</th>
                    <th>Applied</th>
                    <th>Resume</th>
                    {canManageApplications && <th>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {filteredApplications.map((application, index) => (
                    <tr
                      key={application.id}
                      className="clickable-row"
                      onClick={() => navigate(`/recruiter/applications/${application.id}`)}
                    >
                      <td>{index + 1}</td>
                      <td>{application.candidate_full_name}</td>
                      <td>{application.job_title}</td>
                      <td>
                        <span className={toneBadgeClass(statusTone(application.status))}>
                          {application.status}
                        </span>
                      </td>
                      <td>
                        <span className="badge badge-inactive">{application.source}</span>
                      </td>
                      <td>{new Date(application.applied_at).toLocaleDateString()}</td>
                      <td>{application.resume_id ? "Yes" : "—"}</td>
                      {canManageApplications && (
                        <td onClick={(e) => e.stopPropagation()}>
                          <button
                            type="button"
                            className="btn btn-danger btn-sm"
                            onClick={() => openDeleteModal(application)}
                          >
                            Delete
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {canManageApplications && showForm && (
        <Modal title="Link a candidate to a job" onClose={closeForm}>
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

            <div className="btn-group" style={{ marginTop: "1rem" }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={createApplicationMutation.isPending || !candidateId || !jobId}
              >
                {createApplicationMutation.isPending ? (
                  <Spinner label="Linking…" />
                ) : (
                  "Create application"
                )}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={closeForm}
                disabled={createApplicationMutation.isPending}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}

      {pendingDelete && (
        <Modal title="Delete application" onClose={closeDeleteModal}>
          <form onSubmit={handleDeleteSubmit}>
            <p>
              <strong>Candidate:</strong> {pendingDelete.candidate_full_name}
              <br />
              <strong>Job:</strong> {pendingDelete.job_title}
            </p>
            <p className="muted">
              This removes this application from your active pipeline. Its status history and any
              assessment attempts are preserved, and this action is recorded in Activities.
            </p>
            <label className="field">
              <span>Reason for deletion</span>
              <textarea
                required
                rows={3}
                value={deleteReason}
                onChange={(e) => {
                  setDeleteReason(e.target.value);
                  if (deleteError) setDeleteError(null);
                }}
                disabled={deleteMutation.isPending}
                placeholder="e.g. Duplicate application"
              />
            </label>

            {deleteError && <Alert>{deleteError}</Alert>}

            <div className="btn-group" style={{ marginTop: "1rem" }}>
              <button type="submit" className="btn btn-danger" disabled={deleteMutation.isPending}>
                {deleteMutation.isPending ? <Spinner label="Deleting…" /> : "Delete application"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={closeDeleteModal}
                disabled={deleteMutation.isPending}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
