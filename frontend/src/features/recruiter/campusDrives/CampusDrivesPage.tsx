import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { useToast } from "../../../shared/components/ToastContext";
import type { CampusDriveStatus } from "../../../types/campusDrive";
import { useAuth } from "../../auth/AuthContext";
import { listAssessments } from "../assessments/api";
import { listJobs } from "../jobs/api";
import { createCampusDrive, listCampusDrives } from "./api";

const DRIVES_QUERY_KEY = ["recruiter", "campus-drives"];

const STATUS_BADGE: Record<CampusDriveStatus, string> = {
  DRAFT: "badge-inactive",
  ACTIVE: "badge-active",
  PAUSED: "badge-warn",
  CLOSED: "badge-inactive",
};

interface DriveFormState {
  name: string;
  collegeName: string;
  jobSource: "existing" | "new";
  jobId: string;
  newJobTitle: string;
  newJobDescription: string;
  description: string;
  registrationDeadline: string;
  defaultAssessmentId: string;
}

const EMPTY_FORM: DriveFormState = {
  name: "",
  collegeName: "",
  jobSource: "existing",
  jobId: "",
  newJobTitle: "",
  newJobDescription: "",
  description: "",
  registrationDeadline: "",
  defaultAssessmentId: "",
};

export function CampusDrivesPage() {
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { showToast } = useToast();

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

  const assessmentsQuery = useQuery({
    queryKey: ["recruiter", "assessments"],
    queryFn: () => listAssessments(token),
    enabled: accessToken !== null,
  });

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<DriveFormState>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [createdLink, setCreatedLink] = useState<{ name: string; link: string } | null>(null);

  function openCreateForm() {
    setForm(EMPTY_FORM);
    setFormError(null);
    setShowForm(true);
  }

  function closeForm() {
    setShowForm(false);
  }

  const createMutation = useMutation({
    mutationFn: () =>
      createCampusDrive(
        {
          name: form.name,
          college_name: form.collegeName,
          job_id: form.jobSource === "existing" ? form.jobId : null,
          new_job_title: form.jobSource === "new" ? form.newJobTitle : null,
          new_job_description: form.jobSource === "new" ? form.newJobDescription : null,
          description: form.description || null,
          registration_deadline: form.registrationDeadline || null,
          default_assessment_id: form.defaultAssessmentId || null,
        },
        token,
      ),
    onSuccess: (drive) => {
      showToast("Campus drive created.", "success");
      setFormError(null);
      setShowForm(false);
      if (drive.application_link) {
        setCreatedLink({ name: drive.name, link: drive.application_link });
      }
      void queryClient.invalidateQueries({ queryKey: DRIVES_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "jobs"] });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  async function copyLink(link: string) {
    try {
      await navigator.clipboard.writeText(link);
      showToast("Link copied to clipboard.", "success");
    } catch {
      showToast("Could not copy the link automatically — copy it manually.", "error");
    }
  }

  const canManage = !(drivesQuery.error instanceof ApiError && drivesQuery.error.status === 403);
  const isFormValid =
    form.name.trim() !== "" &&
    form.collegeName.trim() !== "" &&
    (form.jobSource === "existing"
      ? form.jobId !== ""
      : form.newJobTitle.trim() !== "" && form.newJobDescription.trim() !== "");

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Campus Drives</h1>
          <p className="muted">Mass hiring events tied to a job and a college, with their own public link.</p>
        </div>
        {canManage && (
          <button type="button" className="btn btn-primary" onClick={openCreateForm}>
            + New drive
          </button>
        )}
      </div>

      {createdLink && (
        <section className="card stack-sm" role="status">
          <p>
            <strong>{createdLink.name}</strong> is ready. Share this link with candidates — it won't
            be shown again (you can always generate a new one from the drive page):
          </p>
          <div className="link-copy-row">
            <code className="link-copy-value">{createdLink.link}</code>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => copyLink(createdLink.link)}>
              Copy link
            </button>
            <a className="btn btn-ghost btn-sm" href={createdLink.link} target="_blank" rel="noreferrer">
              Open link
            </a>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            style={{ alignSelf: "flex-start" }}
            onClick={() => setCreatedLink(null)}
          >
            Dismiss
          </button>
        </section>
      )}

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
            <button type="button" className="btn btn-ghost btn-sm" onClick={closeForm}>
              Cancel
            </button>
          </div>
          <form onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span>Drive name</span>
              <input
                required
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                disabled={createMutation.isPending}
              />
            </label>

            <label className="field">
              <span>College / institution</span>
              <input
                required
                value={form.collegeName}
                onChange={(e) => setForm({ ...form, collegeName: e.target.value })}
                disabled={createMutation.isPending}
              />
            </label>

            <fieldset className="field">
              <legend>Job for this drive</legend>
              <div className="segmented-control">
                <button
                  type="button"
                  className={`btn btn-sm ${form.jobSource === "existing" ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setForm({ ...form, jobSource: "existing" })}
                  disabled={createMutation.isPending}
                >
                  Use existing job
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${form.jobSource === "new" ? "btn-primary" : "btn-ghost"}`}
                  onClick={() => setForm({ ...form, jobSource: "new" })}
                  disabled={createMutation.isPending}
                >
                  + Add new job
                </button>
              </div>

              {form.jobSource === "existing" ? (
                <label className="field">
                  <span>Job</span>
                  <select
                    required
                    value={form.jobId}
                    onChange={(e) => setForm({ ...form, jobId: e.target.value })}
                    disabled={createMutation.isPending}
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
                  {(jobsQuery.data?.length ?? 0) === 0 && (
                    <span className="field-hint">No jobs yet — switch to "+ Add new job" instead.</span>
                  )}
                </label>
              ) : (
                <>
                  <label className="field">
                    <span>New job title</span>
                    <input
                      required
                      value={form.newJobTitle}
                      onChange={(e) => setForm({ ...form, newJobTitle: e.target.value })}
                      disabled={createMutation.isPending}
                    />
                  </label>
                  <label className="field">
                    <span>New job description</span>
                    <textarea
                      required
                      rows={3}
                      value={form.newJobDescription}
                      onChange={(e) => setForm({ ...form, newJobDescription: e.target.value })}
                      disabled={createMutation.isPending}
                    />
                  </label>
                </>
              )}
            </fieldset>

            <label className="field">
              <span>Description</span>
              <textarea
                rows={3}
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                disabled={createMutation.isPending}
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Registration deadline</span>
                <input
                  type="date"
                  value={form.registrationDeadline}
                  onChange={(e) => setForm({ ...form, registrationDeadline: e.target.value })}
                  disabled={createMutation.isPending}
                />
              </label>

              <label className="field">
                <span>Assessment (optional)</span>
                <select
                  value={form.defaultAssessmentId}
                  onChange={(e) => setForm({ ...form, defaultAssessmentId: e.target.value })}
                  disabled={createMutation.isPending}
                >
                  <option value="">No assessment</option>
                  {assessmentsQuery.data?.map((assessment) => (
                    <option key={assessment.id} value={assessment.id}>
                      {assessment.title}
                    </option>
                  ))}
                </select>
                <span className="field-hint">
                  If set, candidates are automatically invited to take it after applying.
                </span>
              </label>
            </div>

            {formError && <Alert>{formError}</Alert>}

            <button
              type="submit"
              className="btn btn-primary"
              disabled={createMutation.isPending || !isFormValid}
            >
              {createMutation.isPending ? "Creating…" : "Create drive"}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
