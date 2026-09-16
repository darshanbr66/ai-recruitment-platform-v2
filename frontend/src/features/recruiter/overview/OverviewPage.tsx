import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { BarList } from "../../../shared/components/BarList";
import { useAuth } from "../../auth/AuthContext";
import { listApplications } from "../applications/api";
import { getReportOverview } from "../reports/api";

const QUICK_LINKS = [
  { to: "/recruiter/jobs", title: "Post a job", description: "Create and publish a new requisition." },
  { to: "/recruiter/applications", title: "Review applications", description: "Move candidates through your pipeline." },
  { to: "/recruiter/assessments", title: "Assessments", description: "Send skills tests to candidates." },
  { to: "/recruiter/campus-drives", title: "Campus Drives", description: "Run a mass-hiring event for a college." },
];

/**
 * Recruiter dashboard. Every number here comes from
 * `GET /api/v1/recruiter/reports/overview` (real, tenant-scoped, computed
 * at request time — CLAUDE.md § 2: "Reports != hardcoded numbers"), the
 * same source of truth the Reports page uses, so the two never disagree.
 *
 * Deliberately shows no tenancy/architecture details (organization id,
 * phase numbers, etc.) — this is a normal recruiter's home screen, not a
 * developer view. Platform-level detail belongs on the SUPER_ADMIN-only
 * /admin surface instead.
 */
export function OverviewPage() {
  const { user, accessToken } = useAuth();

  const reportQuery = useQuery({
    queryKey: ["recruiter", "reports", "overview"],
    queryFn: () => getReportOverview(accessToken as string),
    enabled: accessToken !== null,
  });

  const applicationsQuery = useQuery({
    queryKey: ["recruiter", "applications", "all"],
    queryFn: () => listApplications(accessToken as string),
    enabled: accessToken !== null,
  });

  const recentApplications = useMemo(() => {
    if (!applicationsQuery.data) return [];
    return [...applicationsQuery.data]
      .sort((a, b) => new Date(b.applied_at).getTime() - new Date(a.applied_at).getTime())
      .slice(0, 6);
  }, [applicationsQuery.data]);

  return (
    <div className="stack-lg">
      <section>
        <h1>Welcome back, {user?.full_name.split(" ")[0]}</h1>
        <p className="muted">Here's what's happening with your hiring pipeline.</p>
      </section>

      {reportQuery.isError && (
        <Alert>
          {reportQuery.error instanceof ApiError ? reportQuery.error.message : "Could not load your overview."}
        </Alert>
      )}

      <section className="card-grid">
        <div className="stat-card">
          <span className="stat-label">Open jobs</span>
          {reportQuery.isPending && <span className="stat-value muted">…</span>}
          {reportQuery.isSuccess && <span className="stat-value">{reportQuery.data.open_jobs}</span>}
        </div>
        <div className="stat-card">
          <span className="stat-label">Candidates</span>
          {reportQuery.isPending && <span className="stat-value muted">…</span>}
          {reportQuery.isSuccess && <span className="stat-value">{reportQuery.data.total_candidates}</span>}
        </div>
        <div className="stat-card">
          <span className="stat-label">Applications</span>
          {reportQuery.isPending && <span className="stat-value muted">…</span>}
          {reportQuery.isSuccess && <span className="stat-value">{reportQuery.data.total_applications}</span>}
        </div>
        <div className="stat-card">
          <span className="stat-label">Assessment invitations</span>
          {reportQuery.isPending && <span className="stat-value muted">…</span>}
          {reportQuery.isSuccess && (
            <span className="stat-value">{reportQuery.data.assessments.total_invitations}</span>
          )}
        </div>
        <div className="stat-card">
          <span className="stat-label">Campus drives</span>
          {reportQuery.isPending && <span className="stat-value muted">…</span>}
          {reportQuery.isSuccess && <span className="stat-value">{reportQuery.data.campus_drives.length}</span>}
        </div>
      </section>

      <div className="detail-grid">
        <section className="card">
          <h2>Pipeline by stage</h2>
          {reportQuery.isPending && <p role="status">Loading…</p>}
          {reportQuery.isSuccess &&
            (reportQuery.data.applications_by_status.length === 0 ? (
              <p className="muted">No applications yet — once candidates apply, their stages show up here.</p>
            ) : (
              <BarList
                rows={reportQuery.data.applications_by_status.map((row) => ({
                  id: row.status,
                  label: row.status,
                  count: row.count,
                }))}
                total={reportQuery.data.total_applications}
              />
            ))}
        </section>

        <section className="card">
          <h2>Recent activity</h2>
          {applicationsQuery.isPending && <p role="status">Loading…</p>}
          {applicationsQuery.isSuccess &&
            (recentApplications.length === 0 ? (
              <p className="muted">No applications yet.</p>
            ) : (
              <div className="timeline">
                {recentApplications.map((application) => (
                  <div key={application.id} className="timeline-item">
                    <span className="timeline-dot" />
                    <div>
                      <Link to={`/recruiter/applications/${application.id}`}>
                        {application.candidate_full_name}
                      </Link>{" "}
                      applied to <strong>{application.job_title}</strong>
                      <div className="muted">
                        {new Date(application.applied_at).toLocaleString()} ·{" "}
                        <span className="badge badge-active">{application.status}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ))}
        </section>
      </div>

      <section>
        <h2>Quick actions</h2>
        <div className="card-grid">
          {QUICK_LINKS.map((link) => (
            <Link key={link.to} to={link.to} className="module-card" style={{ textDecoration: "none", color: "inherit" }}>
              <span className="module-title">{link.title}</span>
              <span className="module-phase">{link.description}</span>
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
