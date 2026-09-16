import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import type { CampusDriveStatus } from "../../../types/campusDrive";
import { useAuth } from "../../auth/AuthContext";
import { listApplicationsForDrive } from "../applications/api";
import { getCampusDrive, updateCampusDrive } from "./api";

const NEXT_ACTIONS: Record<CampusDriveStatus, { label: string; status: CampusDriveStatus }[]> = {
  PLANNED: [
    { label: "Activate", status: "ACTIVE" },
    { label: "Cancel", status: "CANCELLED" },
  ],
  ACTIVE: [{ label: "Close", status: "CLOSED" }],
  CLOSED: [],
  CANCELLED: [],
};

export function CampusDriveDetailPage() {
  const { driveId = "" } = useParams<{ driveId: string }>();
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [confirmingCancel, setConfirmingCancel] = useState(false);

  const driveQuery = useQuery({
    queryKey: ["recruiter", "campus-drives", driveId],
    queryFn: () => getCampusDrive(driveId, token),
    enabled: accessToken !== null,
  });

  const applicationsQuery = useQuery({
    queryKey: ["recruiter", "applications", "drive", driveId],
    queryFn: () => listApplicationsForDrive(driveId, token),
    enabled: accessToken !== null,
  });

  const statusMutation = useMutation({
    mutationFn: (status: CampusDriveStatus) => updateCampusDrive(driveId, { status }, token),
    onSuccess: () =>
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "campus-drives", driveId] }),
  });

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
            {drive.batch_year ? ` · Batch ${drive.batch_year}` : ""}
          </p>
        </div>
        <div style={{ display: "flex", gap: "0.5rem" }}>
          {NEXT_ACTIONS[drive.status].map((action) => (
            <button
              key={action.status}
              type="button"
              className="btn btn-ghost btn-sm"
              disabled={statusMutation.isPending}
              onClick={() =>
                action.status === "CANCELLED"
                  ? setConfirmingCancel(true)
                  : statusMutation.mutate(action.status)
              }
            >
              {action.label}
            </button>
          ))}
        </div>
      </div>

      <section className="card">
        <h2>Candidates in this drive</h2>
        {applicationsQuery.isPending && <p role="status">Loading…</p>}
        {applicationsQuery.isSuccess && applicationsQuery.data.length === 0 && (
          <p className="muted">
            No applications yet. Candidates who apply to {drive.job_title} while this drive is
            active are added here automatically.
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

      {confirmingCancel && (
        <ConfirmDialog
          title="Cancel this campus drive?"
          message={`This cancels "${drive.name}" at ${drive.college_name}. Existing applications are unaffected, but the drive will no longer accept new candidates.`}
          confirmLabel="Cancel drive"
          isConfirming={statusMutation.isPending}
          onCancel={() => setConfirmingCancel(false)}
          onConfirm={() =>
            statusMutation.mutate("CANCELLED", { onSuccess: () => setConfirmingCancel(false) })
          }
        />
      )}
    </div>
  );
}
