import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { triggerBlobDownload } from "../../../lib/downloadBlob";
import { Alert } from "../../../shared/components/Alert";
import { Avatar } from "../../../shared/components/Avatar";
import { BackLink } from "../../../shared/components/BackLink";
import { Icon } from "../../../shared/components/Icon";
import { PipelineTrack } from "../../../shared/components/PipelineTrack";
import { EmptyState } from "../../../shared/components/EmptyState";
import { SkeletonCard } from "../../../shared/components/Skeleton";
import { statusTone, toneBadgeClass } from "../../../shared/lib/statusTone";
import { ResumePreviewModal } from "../../../shared/components/ResumePreviewModal";
import { useAuth } from "../../auth/AuthContext";
import { downloadResume, listApplicationsForCandidate } from "../applications/api";
import { getCandidate } from "./api";

export function CandidateDetailPage() {
  const { candidateId = "" } = useParams<{ candidateId: string }>();
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const [downloadError, setDownloadError] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [previewing, setPreviewing] = useState<{ applicationId: string; filename: string } | null>(null);

  const candidateQuery = useQuery({
    queryKey: ["recruiter", "candidates", candidateId],
    queryFn: () => getCandidate(candidateId, token),
    enabled: accessToken !== null,
  });

  const applicationsQuery = useQuery({
    queryKey: ["recruiter", "applications", "candidate", candidateId],
    queryFn: () => listApplicationsForCandidate(candidateId, token),
    enabled: accessToken !== null,
  });

  async function handleDownload(applicationId: string, filename: string) {
    setDownloadError(null);
    setDownloadingId(applicationId);
    try {
      const { blob, filename: serverFilename } = await downloadResume(applicationId, token);
      triggerBlobDownload(blob, serverFilename ?? filename);
    } catch (err) {
      setDownloadError(err instanceof ApiError ? err.message : "Could not download the resume.");
    } finally {
      setDownloadingId(null);
    }
  }

  if (candidateQuery.isPending) {
    return (
      <div className="stack-lg" role="status" aria-label="Loading candidate">
        <SkeletonCard lines={2} />
        <SkeletonCard lines={5} />
      </div>
    );
  }

  if (candidateQuery.isError || !candidateQuery.data) {
    return (
      <Alert>
        {candidateQuery.error instanceof ApiError
          ? candidateQuery.error.message
          : "Candidate not found."}
      </Alert>
    );
  }

  const candidate = candidateQuery.data;
  // Distinct roles this candidate has applied for — separate from
  // `current_title` (their professional title today), one row per unique
  // job, each linking to that application (SIGVITAS platform overhaul § 14).
  const appliedRoles: [string, string][] = applicationsQuery.data
    ? [...new Map(applicationsQuery.data.map((a) => [a.job_title, a.id])).entries()]
    : [];

  return (
    <div className="stack-lg">
      <BackLink to="/recruiter/candidates">Back to candidates</BackLink>

      <div className="page-header profile-header">
        <div className="profile-identity">
          <Avatar name={candidate.full_name} large />
          <div>
            <h1>{candidate.full_name}</h1>
            <p className="muted">{candidate.email}</p>
            <ul className="profile-facts" aria-label="Candidate summary">
              {candidate.current_title && candidate.current_company && (
                <li className="chip">
                  <Icon name="jobs" size={13} />
                  {candidate.current_title} at {candidate.current_company}
                </li>
              )}
              {candidate.location && (
                <li className="chip">
                  <Icon name="pin" size={13} />
                  {candidate.location}
                </li>
              )}
              {candidate.years_experience !== null && (
                <li className="chip">
                  <Icon name="clock" size={13} />
                  {candidate.years_experience} yrs experience
                </li>
              )}
              {candidate.immediate_joiner ? (
                <li className="chip">Immediate joiner</li>
              ) : (
                candidate.notice_period_days !== null && (
                  <li className="chip">{candidate.notice_period_days}-day notice</li>
                )
              )}
              {candidate.linkedin_url && (
                <li>
                  <a className="chip" href={candidate.linkedin_url} target="_blank" rel="noopener noreferrer">
                    LinkedIn
                  </a>
                </li>
              )}
              {candidate.github_url && (
                <li>
                  <a className="chip" href={candidate.github_url} target="_blank" rel="noopener noreferrer">
                    GitHub
                  </a>
                </li>
              )}
            </ul>
          </div>
        </div>
        <span className={`badge ${candidate.is_active ? "badge-active" : "badge-inactive"}`}>
          {candidate.is_active ? "Active" : "Inactive"}
        </span>
      </div>

      <div className="detail-grid">
        <section className="card">
          <h2>Applications</h2>
          {applicationsQuery.isPending && <p role="status">Loading applications…</p>}
          {applicationsQuery.isError && <Alert>Could not load applications.</Alert>}
          {downloadError && <Alert>{downloadError}</Alert>}

          {applicationsQuery.isSuccess &&
            (applicationsQuery.data.length === 0 ? (
              <EmptyState icon="applications" title="No applications yet" compact>
                This candidate hasn't applied to any roles yet.
              </EmptyState>
            ) : (
              <div className="stack-lg" style={{ gap: "0.75rem" }}>
                {applicationsQuery.data.map((application) => (
                  <div key={application.id} className="detail-row" style={{ alignItems: "center" }}>
                    <div>
                      <div>{application.job_title}</div>
                      <div className="muted" style={{ fontSize: "0.8rem" }}>
                        Applied {new Date(application.applied_at).toLocaleDateString()}
                      </div>
                      <PipelineTrack status={application.status} compact />
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                      <span className={toneBadgeClass(statusTone(application.status))}>{application.status}</span>
                      {application.resume_id && (
                        <>
                          <button
                            type="button"
                            className="link-button"
                            onClick={() =>
                              setPreviewing({
                                applicationId: application.id,
                                filename: application.resume_filename ?? "resume",
                              })
                            }
                          >
                            Preview Resume
                          </button>
                          <button
                            type="button"
                            className="link-button"
                            disabled={downloadingId === application.id}
                            onClick={() =>
                              void handleDownload(
                                application.id,
                                application.resume_filename ?? "resume",
                              )
                            }
                          >
                            {downloadingId === application.id ? "Downloading…" : "Download"}
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ))}
        </section>

        <section className="card">
          <h2>Profile</h2>
          <div className="detail-row">
            <span className="detail-row-label">Phone</span>
            <span>{candidate.phone ?? "—"}</span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">Location</span>
            <span>{candidate.location ?? "—"}</span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">Current title</span>
            <span>{candidate.current_title ?? "—"}</span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">Applied roles</span>
            <span>
              {appliedRoles.length === 0 ? (
                "—"
              ) : (
                <span style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
                  {appliedRoles.map(([jobTitle, applicationId]) => (
                    <Link key={applicationId} to={`/recruiter/applications/${applicationId}`}>
                      {jobTitle}
                    </Link>
                  ))}
                </span>
              )}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">Experience</span>
            <span>
              {candidate.years_experience !== null ? `${candidate.years_experience} yrs` : "—"}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">Candidate type</span>
            <span>
              {candidate.candidate_type === null
                ? "—"
                : candidate.candidate_type === "FRESHER"
                  ? "Fresher"
                  : "Experienced"}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">Current company</span>
            <span>{candidate.current_company ?? "—"}</span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">Preferred location</span>
            <span>{candidate.preferred_location ?? "—"}</span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">Notice period</span>
            <span>
              {candidate.immediate_joiner
                ? "Immediate joiner"
                : candidate.notice_period_days !== null
                  ? `${candidate.notice_period_days} days`
                  : "—"}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">Qualification</span>
            <span>{candidate.qualification ?? "—"}</span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">LinkedIn</span>
            <span>
              {candidate.linkedin_url ? (
                <a href={candidate.linkedin_url} target="_blank" rel="noopener noreferrer">
                  {candidate.linkedin_url}
                </a>
              ) : (
                "—"
              )}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">GitHub</span>
            <span>
              {candidate.github_url ? (
                <a href={candidate.github_url} target="_blank" rel="noopener noreferrer">
                  {candidate.github_url}
                </a>
              ) : (
                "—"
              )}
            </span>
          </div>
          <div className="detail-row">
            <span className="detail-row-label">Source</span>
            <span>{candidate.source}</span>
          </div>
        </section>
      </div>

      {previewing && (
        <ResumePreviewModal
          filename={previewing.filename}
          fetchResume={() => downloadResume(previewing.applicationId, token)}
          onClose={() => setPreviewing(null)}
        />
      )}
    </div>
  );
}
