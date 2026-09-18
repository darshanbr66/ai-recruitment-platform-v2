import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { Modal } from "../../../shared/components/Modal";
import { QrCode } from "../../../shared/components/QrCode";
import { useToast } from "../../../shared/components/ToastContext";
import type {
  CampusDriveFunnelCounts,
  CampusDriveResponse,
  CampusDriveStatus,
} from "../../../types/campusDrive";
import { useAuth } from "../../auth/AuthContext";
import { listApplicationsForDrive } from "../applications/api";
import { getCampusDrive, getCampusDriveFunnel, regenerateCampusDriveLink, updateCampusDrive } from "./api";

const WORKFLOW_STAGES = ["Registration", "Assessment", "Submitted", "Screening", "Shortlisted"];

const NEXT_ACTIONS: Record<CampusDriveStatus, { label: string; status: CampusDriveStatus; confirm?: boolean }[]> = {
  DRAFT: [{ label: "Activate", status: "ACTIVE" }],
  ACTIVE: [
    { label: "Pause", status: "PAUSED" },
    { label: "Close", status: "CLOSED", confirm: true },
  ],
  PAUSED: [
    { label: "Resume", status: "ACTIVE" },
    { label: "Close", status: "CLOSED", confirm: true },
  ],
  CLOSED: [{ label: "Reopen", status: "ACTIVE" }],
};

const STATUS_BADGE: Record<CampusDriveStatus, string> = {
  DRAFT: "badge-inactive",
  ACTIVE: "badge-active",
  PAUSED: "badge-warn",
  CLOSED: "badge-inactive",
};

const FUNNEL_STAGES: { key: keyof CampusDriveFunnelCounts; label: string }[] = [
  { key: "registered", label: "Registered" },
  { key: "screening", label: "Screened" },
  { key: "assessment_invited", label: "Assessment invited" },
  { key: "assessment_completed", label: "Assessment completed" },
  { key: "assessment_passed", label: "Assessment passed" },
  { key: "assessment_failed", label: "Assessment failed" },
  { key: "shortlisted", label: "Shortlisted" },
  { key: "interview", label: "Interview" },
  { key: "selected", label: "Selected" },
  { key: "rejected", label: "Rejected" },
  { key: "hired", label: "Hired" },
];

interface EditFormState {
  name: string;
  collegeName: string;
  description: string;
  registrationDeadline: string;
}

function driveToEditForm(drive: CampusDriveResponse): EditFormState {
  return {
    name: drive.name,
    collegeName: drive.college_name,
    description: drive.description ?? "",
    registrationDeadline: drive.registration_deadline ?? "",
  };
}

export function CampusDriveDetailPage() {
  const { driveId = "" } = useParams<{ driveId: string }>();
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [confirmingClose, setConfirmingClose] = useState(false);
  const [regeneratedLink, setRegeneratedLink] = useState<string | null>(null);
  const [showEditForm, setShowEditForm] = useState(false);
  const [editForm, setEditForm] = useState<EditFormState | null>(null);
  const [editError, setEditError] = useState<string | null>(null);

  const driveQueryKey = ["recruiter", "campus-drives", driveId];

  const driveQuery = useQuery({
    queryKey: driveQueryKey,
    queryFn: () => getCampusDrive(driveId, token),
    enabled: accessToken !== null,
  });

  const funnelQuery = useQuery({
    queryKey: ["recruiter", "campus-drives", driveId, "funnel"],
    queryFn: () => getCampusDriveFunnel(driveId, token),
    enabled: accessToken !== null,
  });

  const applicationsQuery = useQuery({
    queryKey: ["recruiter", "applications", "drive", driveId],
    queryFn: () => listApplicationsForDrive(driveId, token),
    enabled: accessToken !== null,
  });

  const statusMutation = useMutation({
    mutationFn: (status: CampusDriveStatus) => updateCampusDrive(driveId, { status }, token),
    onSuccess: (_data, status) => {
      showToast(`Drive status updated to ${status}.`, "success");
      setConfirmingClose(false);
      void queryClient.invalidateQueries({ queryKey: driveQueryKey });
    },
    onError: (err) => {
      showToast(err instanceof ApiError ? err.message : "Could not update the drive.", "error");
    },
  });

  const editMutation = useMutation({
    mutationFn: () => {
      if (!editForm) throw new Error("No changes to save.");
      return updateCampusDrive(
        driveId,
        {
          name: editForm.name,
          college_name: editForm.collegeName,
          description: editForm.description || null,
          registration_deadline: editForm.registrationDeadline || null,
        },
        token,
      );
    },
    onSuccess: () => {
      showToast("Campus drive updated.", "success");
      setShowEditForm(false);
      setEditError(null);
      void queryClient.invalidateQueries({ queryKey: driveQueryKey });
    },
    onError: (err) => {
      setEditError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function openEditForm() {
    if (!driveQuery.data) return;
    setEditForm(driveToEditForm(driveQuery.data));
    setEditError(null);
    setShowEditForm(true);
  }

  function handleEditSubmit(event: FormEvent) {
    event.preventDefault();
    editMutation.mutate();
  }

  const regenerateMutation = useMutation({
    mutationFn: () => regenerateCampusDriveLink(driveId, token),
    onSuccess: (drive) => {
      showToast("A new application link was generated. The old link no longer works.", "success");
      if (drive.application_link) setRegeneratedLink(drive.application_link);
      void queryClient.invalidateQueries({ queryKey: driveQueryKey });
    },
    onError: (err) => {
      showToast(err instanceof ApiError ? err.message : "Could not regenerate the link.", "error");
    },
  });

  async function copyLink(link: string) {
    try {
      await navigator.clipboard.writeText(link);
      showToast("Link copied to clipboard.", "success");
    } catch {
      showToast("Could not copy the link automatically — copy it manually.", "error");
    }
  }

  if (driveQuery.isPending) return <p role="status">Loading campus drive…</p>;
  if (driveQuery.isError || !driveQuery.data) {
    return (
      <Alert>
        {driveQuery.error instanceof ApiError ? driveQuery.error.message : "Campus drive not found."}
      </Alert>
    );
  }

  const drive = driveQuery.data;

  return (
    <div className="stack-lg">
      <p>
        <Link to="/recruiter/campus-drives">&larr; Back to campus drives</Link>
      </p>

      <div className="page-header">
        <div>
          <h1>{drive.name}</h1>
          <p className="muted">
            {drive.job_title} · {drive.college_name}
          </p>
          <span className={`badge ${STATUS_BADGE[drive.status]}`}>{drive.status}</span>
        </div>
        <div className="btn-group">
          <button type="button" className="btn btn-ghost btn-sm" onClick={openEditForm}>
            Edit Drive
          </button>
          {NEXT_ACTIONS[drive.status].map((action) => (
            <button
              key={action.status}
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={statusMutation.isPending}
              onClick={() =>
                action.confirm ? setConfirmingClose(true) : statusMutation.mutate(action.status)
              }
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      <section className="card">
        <div className="workflow-stepper">
          {WORKFLOW_STAGES.map((stage, index) => (
            <div key={stage} className="workflow-step">
              <span className="workflow-step-dot">{index + 1}</span>
              <span className="workflow-step-label">{stage}</span>
              {index < WORKFLOW_STAGES.length - 1 && <span className="workflow-step-arrow">&rarr;</span>}
            </div>
          ))}
        </div>
        <p className="field-hint" style={{ marginTop: "0.75rem" }}>
          {drive.default_assessment_title
            ? "Candidates register, then are automatically taken to the assessment before moving into screening."
            : "This drive is registration-only — candidates go straight into screening after they register."}
        </p>
      </section>

      {drive.description && (
        <section className="card">
          <h2>Description</h2>
          <p>{drive.description}</p>
        </section>
      )}

      <section className="card stack-sm">
        <div className="page-header">
          <h2>Candidate registration link</h2>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            disabled={regenerateMutation.isPending}
            onClick={() => regenerateMutation.mutate()}
          >
            {regenerateMutation.isPending ? "Generating…" : "Regenerate Link"}
          </button>
        </div>
        {regeneratedLink ? (
          <>
            <p className="muted">Share this link or scan the QR code to register candidates:</p>
            <div className="link-copy-row">
              <code className="link-copy-value">{regeneratedLink}</code>
              <button type="button" className="btn btn-ghost btn-sm" onClick={() => copyLink(regeneratedLink)}>
                Copy Registration Link
              </button>
              <a className="btn btn-ghost btn-sm" href={regeneratedLink} target="_blank" rel="noreferrer">
                Open link
              </a>
            </div>
            <QrCode value={regeneratedLink} filename={`${drive.name}-registration-qr.png`} />
          </>
        ) : (
          <p className="muted">
            The link was shown once when this drive was created (or last regenerated). Use
            "Regenerate Link" to get a fresh, shareable link and QR code — this invalidates the
            previous one.
          </p>
        )}
        {drive.registration_deadline && (
          <p className="muted">Registration deadline: {new Date(drive.registration_deadline).toLocaleDateString()}</p>
        )}
        {drive.default_assessment_title && (
          <p className="muted">Candidates are auto-invited to: {drive.default_assessment_title}</p>
        )}
      </section>

      <section className="card">
        <h2>Hiring funnel</h2>
        {funnelQuery.isPending && <p role="status">Loading funnel…</p>}
        {funnelQuery.isSuccess && (
          <div className="funnel-grid">
            {FUNNEL_STAGES.map((stage) => (
              <div key={stage.key} className="funnel-stat">
                <span className="funnel-stat-value">{funnelQuery.data[stage.key]}</span>
                <span className="funnel-stat-label">{stage.label}</span>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="card">
        <h2>Candidates in this drive</h2>
        {applicationsQuery.isPending && <p role="status">Loading…</p>}
        {applicationsQuery.isSuccess && applicationsQuery.data.length === 0 && (
          <p className="muted">
            No applications yet. Candidates who apply via this drive's link appear here automatically.
          </p>
        )}
        {applicationsQuery.isSuccess && applicationsQuery.data.length > 0 && (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Status</th>
                  <th>Applied</th>
                </tr>
              </thead>
              <tbody>
                {applicationsQuery.data.map((application) => (
                  <tr
                    key={application.id}
                    className="clickable-row"
                    onClick={() => navigate(`/recruiter/applications/${application.id}`)}
                  >
                    <td>{application.candidate_full_name}</td>
                    <td>
                      <span className="badge badge-active">{application.status}</span>
                    </td>
                    <td>{new Date(application.applied_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {confirmingClose && (
        <ConfirmDialog
          title="Close this campus drive?"
          message={`This closes "${drive.name}" at ${drive.college_name}. Existing applications are unaffected, and the drive stays in your history — you can reopen it at any time.`}
          confirmLabel="Close drive"
          isConfirming={statusMutation.isPending}
          onCancel={() => setConfirmingClose(false)}
          onConfirm={() => statusMutation.mutate("CLOSED")}
        />
      )}

      {showEditForm && editForm && (
        <Modal title={`Edit ${drive.name}`} onClose={() => setShowEditForm(false)}>
          <form onSubmit={handleEditSubmit}>
            <label className="field">
              <span>Drive name</span>
              <input
                required
                value={editForm.name}
                onChange={(e) => setEditForm({ ...editForm, name: e.target.value })}
                disabled={editMutation.isPending}
              />
            </label>
            <label className="field">
              <span>College / institution</span>
              <input
                required
                value={editForm.collegeName}
                onChange={(e) => setEditForm({ ...editForm, collegeName: e.target.value })}
                disabled={editMutation.isPending}
              />
            </label>
            <label className="field">
              <span>Description</span>
              <textarea
                rows={3}
                value={editForm.description}
                onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                disabled={editMutation.isPending}
              />
            </label>
            <label className="field">
              <span>Registration deadline</span>
              <input
                type="date"
                value={editForm.registrationDeadline}
                onChange={(e) => setEditForm({ ...editForm, registrationDeadline: e.target.value })}
                disabled={editMutation.isPending}
              />
            </label>

            {editError && <Alert>{editError}</Alert>}

            <div className="btn-group" style={{ marginTop: "1rem" }}>
              <button type="submit" className="btn btn-primary" disabled={editMutation.isPending}>
                {editMutation.isPending ? "Saving…" : "Save changes"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowEditForm(false)}
                disabled={editMutation.isPending}
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
