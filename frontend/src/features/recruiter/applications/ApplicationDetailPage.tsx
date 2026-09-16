import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { triggerBlobDownload } from "../../../lib/downloadBlob";
import { Alert } from "../../../shared/components/Alert";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { APPLICATION_TRANSITIONS, type ApplicationStatus } from "../../../types/recruitment";
import { useAuth } from "../../auth/AuthContext";
import {
  getApplicationAssessment,
  inviteCandidate,
  listAssessments,
} from "../assessments/api";
import { createNote, listNotes } from "../notes/api";
import { listScreeningRuns, startScreening } from "../screening/api";
import { changeApplicationStatus, downloadResume, getApplication } from "./api";

const TERMINAL_BADGE: Partial<Record<ApplicationStatus, string>> = {
  SELECTED: "badge-active",
  REJECTED: "badge-inactive",
  WITHDRAWN: "badge-inactive",
};

const RECOMMENDATION_BADGE: Record<string, string> = {
  STRONG_MATCH: "badge-active",
  POSSIBLE_MATCH: "badge-active",
  WEAK_MATCH: "badge-warn",
  NOT_A_MATCH: "badge-danger",
};

const STATUSES_REQUIRING_CONFIRMATION: ApplicationStatus[] = ["REJECTED", "WITHDRAWN"];

export function ApplicationDetailPage() {
  const { applicationId = "" } = useParams<{ applicationId: string }>();
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();

  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [noteBody, setNoteBody] = useState("");
  const [selectedAssessmentId, setSelectedAssessmentId] = useState("");
  const [pendingStatus, setPendingStatus] = useState<ApplicationStatus | null>(null);

  const applicationQuery = useQuery({
    queryKey: ["recruiter", "applications", applicationId],
    queryFn: () => getApplication(applicationId, token),
    enabled: accessToken !== null,
  });

  const screeningQuery = useQuery({
    queryKey: ["recruiter", "screening", applicationId],
    queryFn: () => listScreeningRuns(applicationId, token),
    enabled: accessToken !== null,
  });

  const assessmentInvitationQuery = useQuery({
    queryKey: ["recruiter", "assessment-invitation", applicationId],
    queryFn: () => getApplicationAssessment(applicationId, token),
    enabled: accessToken !== null,
  });

  const assessmentsQuery = useQuery({
    queryKey: ["recruiter", "assessments"],
    queryFn: () => listAssessments(token),
    enabled: accessToken !== null,
  });

  const notesQuery = useQuery({
    queryKey: ["recruiter", "notes", applicationId],
    queryFn: () => listNotes(applicationId, token),
    enabled: accessToken !== null,
  });

  const statusMutation = useMutation({
    mutationFn: (status: ApplicationStatus) => changeApplicationStatus(applicationId, status, token),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "applications", applicationId] });
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "applications"] });
    },
  });

  const screeningMutation = useMutation({
    mutationFn: () => startScreening(applicationId, token),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "screening", applicationId] });
    },
  });

  const inviteMutation = useMutation({
    mutationFn: () => inviteCandidate({ assessment_id: selectedAssessmentId, application_id: applicationId }, token),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "assessment-invitation", applicationId] });
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "applications", applicationId] });
    },
  });

  const noteMutation = useMutation({
    mutationFn: () => createNote(applicationId, noteBody, token),
    onSuccess: () => {
      setNoteBody("");
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "notes", applicationId] });
    },
  });

  async function handleDownload() {
    if (!applicationQuery.data) return;
    setDownloadError(null);
    setDownloading(true);
    try {
      const { blob, filename } = await downloadResume(applicationId, token);
      triggerBlobDownload(blob, filename ?? applicationQuery.data.resume_filename ?? "resume");
    } catch (err) {
      setDownloadError(err instanceof ApiError ? err.message : "Could not download the resume.");
    } finally {
      setDownloading(false);
    }
  }

  function handleNoteSubmit(event: FormEvent) {
    event.preventDefault();
    if (noteBody.trim()) noteMutation.mutate();
  }

  if (applicationQuery.isPending) {
    return <p role="status">Loading application…</p>;
  }
  if (applicationQuery.isError || !applicationQuery.data) {
    return (
      <Alert>
        {applicationQuery.error instanceof ApiError
          ? applicationQuery.error.message
          : "Application not found."}
      </Alert>
    );
  }

  const application = applicationQuery.data;
  const nextStatuses = APPLICATION_TRANSITIONS[application.status];
  const latestScreening = screeningQuery.data?.[0] ?? null;

  return (
    <div className="stack-lg">
      <p>
        <Link to="/recruiter/applications">&larr; Back to applications</Link>
      </p>

      <div className="page-header">
        <div>
          <h1>{application.job_title}</h1>
          <p className="muted">
            <Link to={`/recruiter/candidates/${application.candidate_id}`}>
              {application.candidate_full_name}
            </Link>{" "}
            · Applied {new Date(application.applied_at).toLocaleDateString()}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <span className={`badge ${TERMINAL_BADGE[application.status] ?? "badge-active"}`}>
            {application.status}
          </span>
          {nextStatuses.length > 0 && (
            <select
              value=""
              disabled={statusMutation.isPending}
              onChange={(e) => {
                const next = e.target.value as ApplicationStatus;
                if (!next) return;
                if (STATUSES_REQUIRING_CONFIRMATION.includes(next)) {
                  setPendingStatus(next);
                } else {
                  statusMutation.mutate(next);
                }
              }}
            >
              <option value="">Move to…</option>
              {nextStatuses.map((status) => (
                <option key={status} value={status}>
                  {status}
                </option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div className="detail-grid">
        <div className="stack-lg" style={{ gap: "1.5rem" }}>
          {/* Resume */}
          <section className="card">
            <h2>Resume</h2>
            {downloadError && <Alert>{downloadError}</Alert>}
            {application.resume_id ? (
              <button type="button" className="btn btn-ghost" onClick={() => void handleDownload()} disabled={downloading}>
                {downloading ? "Downloading…" : `Download ${application.resume_filename ?? "resume"}`}
              </button>
            ) : (
              <p className="muted">No resume on file for this application.</p>
            )}
          </section>

          {/* AI Screening */}
          <section className="card">
            <div className="page-header">
              <h2>AI Screening</h2>
              <button
                type="button"
                className="btn btn-primary btn-sm"
                disabled={screeningMutation.isPending || !application.resume_id}
                onClick={() => screeningMutation.mutate()}
                title={!application.resume_id ? "This application has no resume to screen" : undefined}
              >
                {screeningMutation.isPending ? "Screening…" : "Run AI screening"}
              </button>
            </div>
            <p className="muted" style={{ fontSize: "0.85rem" }}>
              AI-assisted opinion for you to review — not an automatic decision.
            </p>

            {screeningQuery.isPending && <p role="status">Loading…</p>}

            {latestScreening && latestScreening.status === "FAILED" && (
              <Alert>{latestScreening.error_message ?? "Screening failed."}</Alert>
            )}

            {latestScreening && latestScreening.status === "COMPLETED" && (
              <div className="stack-lg" style={{ gap: "0.85rem" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                  <span className="stat-value">{latestScreening.overall_score}</span>
                  <span
                    className={`badge ${RECOMMENDATION_BADGE[latestScreening.recommendation ?? ""] ?? "badge-active"}`}
                  >
                    {latestScreening.recommendation?.replace(/_/g, " ")}
                  </span>
                </div>
                <p>{latestScreening.summary}</p>
                {(latestScreening.matching_skills?.length ?? 0) > 0 && (
                  <p>
                    <strong>Matching skills:</strong> {latestScreening.matching_skills?.join(", ")}
                  </p>
                )}
                {(latestScreening.missing_skills?.length ?? 0) > 0 && (
                  <p>
                    <strong>Missing skills:</strong> {latestScreening.missing_skills?.join(", ")}
                  </p>
                )}
                {(latestScreening.strengths?.length ?? 0) > 0 && (
                  <div>
                    <strong>Strengths</strong>
                    <ul>
                      {latestScreening.strengths?.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {(latestScreening.concerns?.length ?? 0) > 0 && (
                  <div>
                    <strong>Concerns</strong>
                    <ul>
                      {latestScreening.concerns?.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  </div>
                )}
                <p className="muted" style={{ fontSize: "0.75rem" }}>
                  {latestScreening.provider} · {latestScreening.model} ·{" "}
                  {new Date(latestScreening.created_at).toLocaleString()}
                </p>
              </div>
            )}

            {!latestScreening && screeningQuery.isSuccess && (
              <p className="muted">No screening run yet.</p>
            )}
          </section>

          {/* Assessment */}
          <section className="card">
            <h2>Assessment</h2>
            {assessmentInvitationQuery.isPending && <p role="status">Loading…</p>}
            {assessmentInvitationQuery.isSuccess && !assessmentInvitationQuery.data && (
              <div className="stack-lg" style={{ gap: "0.75rem" }}>
                <p className="muted">No assessment assigned yet.</p>
                <div className="field-row" style={{ alignItems: "end" }}>
                  <label className="field" style={{ marginBottom: 0 }}>
                    <span>Assessment</span>
                    <select
                      value={selectedAssessmentId}
                      onChange={(e) => setSelectedAssessmentId(e.target.value)}
                    >
                      <option value="">Select an assessment…</option>
                      {assessmentsQuery.data?.map((a) => (
                        <option key={a.id} value={a.id}>
                          {a.title}
                        </option>
                      ))}
                    </select>
                  </label>
                  <button
                    type="button"
                    className="btn btn-primary"
                    disabled={!selectedAssessmentId || inviteMutation.isPending}
                    onClick={() => inviteMutation.mutate()}
                  >
                    {inviteMutation.isPending ? "Sending…" : "Send invitation"}
                  </button>
                </div>
                {inviteMutation.isError && (
                  <Alert>
                    {inviteMutation.error instanceof ApiError
                      ? inviteMutation.error.message
                      : "Could not send the invitation."}
                  </Alert>
                )}
              </div>
            )}
            {assessmentInvitationQuery.data && (
              <div className="stack-lg" style={{ gap: "0.5rem" }}>
                <p>
                  <strong>{assessmentInvitationQuery.data.assessment_title}</strong> —{" "}
                  <span className="badge badge-active">{assessmentInvitationQuery.data.status}</span>
                </p>
                {inviteMutation.data?.invitation_link && (
                  <Alert variant="success">
                    Invitation link (copy this to send manually if email isn't configured):{" "}
                    <code>{inviteMutation.data.invitation_link}</code>
                  </Alert>
                )}
                {assessmentInvitationQuery.data.result && (
                  <p>
                    Score: {assessmentInvitationQuery.data.result.score}/
                    {assessmentInvitationQuery.data.result.max_score} (
                    {assessmentInvitationQuery.data.result.percentage}%) —{" "}
                    <strong>{assessmentInvitationQuery.data.result.passed ? "Passed" : "Not passed"}</strong>
                  </p>
                )}
              </div>
            )}
          </section>
        </div>

        {/* Notes */}
        <section className="card">
          <h2>Notes</h2>
          <form onSubmit={handleNoteSubmit} noValidate style={{ marginBottom: "1rem" }}>
            <label className="field">
              <span>Add a note</span>
              <textarea
                rows={3}
                value={noteBody}
                onChange={(e) => setNoteBody(e.target.value)}
                disabled={noteMutation.isPending}
              />
            </label>
            <button
              type="submit"
              className="btn btn-ghost btn-sm"
              disabled={noteMutation.isPending || !noteBody.trim()}
            >
              {noteMutation.isPending ? "Saving…" : "Add note"}
            </button>
          </form>

          {notesQuery.isPending && <p role="status">Loading notes…</p>}
          {notesQuery.isSuccess && notesQuery.data.length === 0 && (
            <p className="muted">No notes yet.</p>
          )}
          {notesQuery.isSuccess && notesQuery.data.length > 0 && (
            <div className="timeline">
              {notesQuery.data.map((note) => (
                <div key={note.id} className="timeline-item">
                  <span className="timeline-dot" />
                  <div>
                    <div>{note.body}</div>
                    <div className="muted" style={{ fontSize: "0.75rem" }}>
                      {note.author_name} · {new Date(note.created_at).toLocaleString()}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>

      {pendingStatus && (
        <ConfirmDialog
          title={pendingStatus === "REJECTED" ? "Reject this application?" : "Withdraw this application?"}
          message={
            pendingStatus === "REJECTED"
              ? `This marks ${application.candidate_full_name}'s application for ${application.job_title} as rejected. This can't be undone.`
              : `This marks ${application.candidate_full_name}'s application for ${application.job_title} as withdrawn. This can't be undone.`
          }
          confirmLabel={pendingStatus === "REJECTED" ? "Reject application" : "Withdraw application"}
          isConfirming={statusMutation.isPending}
          onCancel={() => setPendingStatus(null)}
          onConfirm={() =>
            statusMutation.mutate(pendingStatus, { onSuccess: () => setPendingStatus(null) })
          }
        />
      )}
    </div>
  );
}
