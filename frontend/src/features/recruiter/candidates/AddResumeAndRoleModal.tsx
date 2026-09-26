import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { Modal } from "../../../shared/components/Modal";
import { Spinner } from "../../../shared/components/Spinner";
import { useToast } from "../../../shared/components/ToastContext";
import { useAuth } from "../../auth/AuthContext";
import { listJobs } from "../jobs/api";
import { addApplicationWithResume } from "./api";

/** A candidate can be put forward for a role that isn't advertised yet or is
 * paused — the same set the HR job-match flow offers. */
const SELECTABLE_JOB_STATUSES = ["OPEN", "DRAFT", "ON_HOLD"];

/**
 * HR attaching a resume and an applying role to a candidate who already
 * exists. This creates the application in the normal pipeline (source
 * RECRUITER_ADDED) and runs the existing AI resume-vs-JD screening, so the
 * result is indistinguishable from any other application downstream.
 *
 * It never creates a candidate: the caller already has one. The AI outcome
 * is advisory — HR stays the decision maker — so the toast reports what
 * screening said without dressing it up as a verdict.
 */
export function AddResumeAndRoleModal({
  candidateId,
  candidateName,
  onClose,
}: {
  candidateId: string;
  candidateName: string;
  onClose: () => void;
}) {
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [jobId, setJobId] = useState("");
  const [resume, setResume] = useState<File | null>(null);
  const [runScreening, setRunScreening] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const jobsQuery = useQuery({
    queryKey: ["recruiter", "jobs"],
    queryFn: () => listJobs(token),
    enabled: accessToken !== null,
  });

  const selectableJobs = (jobsQuery.data ?? []).filter(
    (job) => SELECTABLE_JOB_STATUSES.includes(job.status) && !job.deleted_at,
  );

  const mutation = useMutation({
    mutationFn: () =>
      addApplicationWithResume(candidateId, { jobId, resume: resume as File, runScreening }, token),
    onSuccess: (result) => {
      const role = result.application.job_title;
      const screened = result.screening?.recommendation ?? result.screening?.decision ?? null;
      showToast(
        result.attached_to_existing
          ? `Resume added to ${candidateName}'s ${role} application.${screened ? ` AI screening: ${screened}.` : ""}`
          : `${candidateName} added to ${role}.${screened ? ` AI screening: ${screened}.` : ""}`,
        "success",
      );
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "candidates", candidateId] });
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "applications"] });
      onClose();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!jobId) {
      setError("Select the role this candidate is applying for.");
      return;
    }
    if (!resume) {
      setError("Attach the candidate's resume.");
      return;
    }
    mutation.mutate();
  }

  return (
    <Modal title="Add resume & role" onClose={mutation.isPending ? () => {} : onClose}>
      <form onSubmit={handleSubmit}>
        <p>
          <strong>Candidate:</strong> {candidateName}
        </p>

        <label className="field">
          <span>Applying role</span>
          <select
            required
            value={jobId}
            onChange={(e) => {
              setJobId(e.target.value);
              if (error) setError(null);
            }}
            disabled={mutation.isPending || jobsQuery.isPending}
          >
            <option value="">
              {jobsQuery.isPending ? "Loading roles…" : "Select a role…"}
            </option>
            {selectableJobs.map((job) => (
              <option key={job.id} value={job.id}>
                {job.title}
                {job.department ? ` — ${job.department}` : ""}
              </option>
            ))}
          </select>
        </label>
        {jobsQuery.isSuccess && selectableJobs.length === 0 && (
          <Alert>Create a job first — there is no open role to apply this candidate to.</Alert>
        )}

        <label className="field">
          <span>Add resume</span>
          <input
            type="file"
            required
            accept=".pdf,.doc,.docx,.txt"
            onChange={(e) => {
              setResume(e.target.files?.[0] ?? null);
              if (error) setError(null);
            }}
            disabled={mutation.isPending}
          />
        </label>

        <label className="field checkbox-row">
          <input
            type="checkbox"
            checked={runScreening}
            onChange={(e) => setRunScreening(e.target.checked)}
            disabled={mutation.isPending}
          />
          <span>Run AI screening against this role</span>
        </label>
        <p className="muted" style={{ marginTop: "-0.5rem", fontSize: "0.82rem" }}>
          AI screening is advisory. You can review and override the result on the application.
        </p>

        {error && <Alert>{error}</Alert>}

        <div className="btn-group" style={{ marginTop: "1rem" }}>
          <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
            {mutation.isPending ? <Spinner label="Adding…" /> : "Add application"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
