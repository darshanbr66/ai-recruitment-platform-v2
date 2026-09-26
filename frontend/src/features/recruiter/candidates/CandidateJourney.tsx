import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { EmptyState } from "../../../shared/components/EmptyState";
import { SkeletonLines } from "../../../shared/components/Skeleton";
import { Spinner } from "../../../shared/components/Spinner";
import { useToast } from "../../../shared/components/ToastContext";
import { humanizeStatus, statusTone, toneBadgeClass } from "../../../shared/lib/statusTone";
import type { CandidateApplicationHistory } from "../../../types/recruitment";
import { useAuth } from "../../auth/AuthContext";
import { listJobs } from "../jobs/api";
import { getCandidateHistory, matchCandidateToJob } from "./api";

/** Roles holding `application.create` (backend RBAC is authoritative; this
 * only avoids showing a form the server would refuse). */
const MATCHING_ROLES = ["ORG_ADMIN", "RECRUITER"];

const TIMELINE_LABELS: Record<string, string> = {
  CANDIDATE_CREATED: "Candidate added",
  CANDIDATE_REGISTERED: "Applied through the careers site",
  CANDIDATE_EMAIL_VERIFIED: "Email verified",
  CANDIDATE_UPDATED: "Profile updated",
  CANDIDATE_MATCHED_TO_JOB: "Matched to a job by HR",
  DUPLICATE_APPLICATION_BLOCKED: "Repeat application blocked",
  APPLICATION_CREATED: "Application created",
  APPLICATION_STATUS_CHANGED: "Status changed",
  AI_SCREENING_COMPLETED: "AI screening: match",
  AI_SCREENED_OUT: "AI screening: screened out",
  AI_SCREENING_FAILED: "AI screening unavailable",
  AI_SCREENING_OVERRIDDEN: "AI decision overridden by HR",
  CANDIDATE_WELCOME_EMAIL_SENT: "Welcome email sent",
  CANDIDATE_WELCOME_EMAIL_FAILED: "Welcome email failed",
};

const MATCHABLE_JOB_STATUSES = ["OPEN", "DRAFT", "ON_HOLD"];

function ApplicationHistoryItem({ entry }: { entry: CandidateApplicationHistory }) {
  const latest = entry.screenings[0] ?? null;
  return (
    <li className="journey-item">
      <div className="journey-item-head">
        <Link to={`/recruiter/applications/${entry.application_id}`}>{entry.job_title}</Link>
        <span className={`chip ${entry.is_original ? "chip-original" : ""}`}>
          {entry.is_original ? "Original application" : humanizeStatus(entry.source)}
        </span>
        <span className={toneBadgeClass(statusTone(entry.status))}>{humanizeStatus(entry.status)}</span>
      </div>
      <p className="muted journey-meta">
        {new Date(entry.applied_at).toLocaleDateString()} · {entry.screenings.length} screening{" "}
        {entry.screenings.length === 1 ? "run" : "runs"}
        {entry.deleted_at && " · archived"}
      </p>
      {latest?.status === "COMPLETED" && (
        <div className="journey-screening">
          <p>
            <span className={`badge ${latest.decision === "NOT_MATCH" ? "badge-warn" : "badge-active"}`}>
              {latest.decision === "NOT_MATCH" ? "AI: not a match" : "AI: match"}
            </span>{" "}
            <span className="muted">
              {latest.requested_by_user_id === null ? "automatic at submission" : "run by a recruiter"} ·{" "}
              {new Date(latest.created_at).toLocaleString()}
            </span>
          </p>
          {latest.summary && <p>{latest.summary}</p>}
          {(latest.missing_requirements?.length ?? 0) > 0 && (
            <p className="muted">
              <strong>Not evidenced:</strong> {latest.missing_requirements?.join(", ")}
            </p>
          )}
        </div>
      )}
      {latest?.status === "FAILED" && <p className="muted">Latest AI screening could not be completed.</p>}
    </li>
  );
}

/**
 * The HR view of one candidate's journey: original application, HR job
 * matches (with the form to add one), screening history per role, and the
 * candidate-related audit trail. AI output here is internal decision
 * support — HR has final authority.
 */
export function CandidateJourney({ candidateId }: { candidateId: string }) {
  const { accessToken, user } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const canMatch = user?.roles.some((role) => MATCHING_ROLES.includes(role)) ?? false;

  const [jobId, setJobId] = useState("");
  const [reason, setReason] = useState("");

  const historyQuery = useQuery({
    queryKey: ["recruiter", "candidates", candidateId, "history"],
    queryFn: () => getCandidateHistory(candidateId, token),
    enabled: accessToken !== null,
  });
  const jobsQuery = useQuery({
    queryKey: ["recruiter", "jobs"],
    queryFn: () => listJobs(token),
    enabled: accessToken !== null && canMatch,
  });

  const matchMutation = useMutation({
    mutationFn: () => matchCandidateToJob(candidateId, { job_id: jobId, reason: reason.trim() || null }, token),
    onSuccess: (application) => {
      showToast(`Matched to ${application.job_title}.`, "success");
      setJobId("");
      setReason("");
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "candidates", candidateId] });
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "applications"] });
    },
    onError: (err) => {
      showToast(err instanceof ApiError ? err.message : "Could not match the candidate.", "error");
    },
  });

  const history = historyQuery.data;
  const associatedJobIds = new Set(history?.applications.map((a) => a.job_id) ?? []);
  const matchableJobs = (jobsQuery.data ?? []).filter(
    (job) => MATCHABLE_JOB_STATUSES.includes(job.status) && !associatedJobIds.has(job.id) && !job.deleted_at,
  );

  function handleMatch(event: FormEvent) {
    event.preventDefault();
    if (jobId) matchMutation.mutate();
  }

  return (
    <>
      <section className="card" aria-labelledby="journey-title">
        <h2 id="journey-title">Roles &amp; AI screening</h2>
        <p className="muted journey-note">
          AI screening is advisory. HR can override any AI decision and match this candidate to any
          role.
        </p>
        {historyQuery.isPending && <SkeletonLines count={3} />}
        {historyQuery.isError && <Alert>Could not load this candidate's screening history.</Alert>}
        {history &&
          (history.applications.length === 0 ? (
            <EmptyState icon="applications" title="No roles yet" compact>
              This candidate isn't associated with any role yet.
            </EmptyState>
          ) : (
            <ul className="journey-list">
              {history.applications.map((entry) => (
                <ApplicationHistoryItem key={entry.application_id} entry={entry} />
              ))}
            </ul>
          ))}

        {canMatch && (
          <form className="journey-match" onSubmit={handleMatch}>
            <h3>Match to another job</h3>
            <div className="field-row">
              <label className="field">
                <span>Job</span>
                <select required value={jobId} onChange={(e) => setJobId(e.target.value)} disabled={matchMutation.isPending}>
                  <option value="">Select a job…</option>
                  {matchableJobs.map((job) => (
                    <option key={job.id} value={job.id}>
                      {job.title}
                      {job.status !== "OPEN" ? ` (${humanizeStatus(job.status)})` : ""}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Reason (optional)</span>
                <input
                  maxLength={1000}
                  value={reason}
                  onChange={(e) => setReason(e.target.value)}
                  placeholder="Why this role fits"
                  disabled={matchMutation.isPending}
                />
              </label>
            </div>
            <button type="submit" className="btn btn-primary btn-sm" disabled={!jobId || matchMutation.isPending}>
              {matchMutation.isPending ? <Spinner label="Matching…" /> : "Match candidate"}
            </button>
          </form>
        )}
      </section>

      <section className="card" aria-labelledby="timeline-title">
        <h2 id="timeline-title">Activity</h2>
        {history && history.timeline.length === 0 && <p className="muted">No activity recorded yet.</p>}
        {history && history.timeline.length > 0 && (
          <ol className="journey-timeline">
            {history.timeline.map((entry) => (
              <li key={entry.id}>
                <strong>{TIMELINE_LABELS[entry.action] ?? humanizeStatus(entry.action)}</strong>
                {entry.description && <span> — {entry.description}</span>}
                {entry.reason && <span className="muted"> Reason: {entry.reason}</span>}
                <span className="muted journey-meta">
                  {entry.actor_name ?? "System"} · {new Date(entry.created_at).toLocaleString()}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </>
  );
}
