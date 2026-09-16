import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { useAuth } from "../../auth/AuthContext";
import { listUsers } from "../../auth/api";
import { listCandidates } from "../candidates/api";
import { listJobs } from "../jobs/api";
import { listApplications } from "../applications/api";

const QUICK_LINKS = [
  { to: "/recruiter/jobs", title: "Post a job", description: "Create and publish a new requisition." },
  { to: "/recruiter/applications", title: "Review applications", description: "Move candidates through your pipeline." },
  { to: "/recruiter/assessments", title: "Assessments", description: "Send skills tests to candidates." },
  { to: "/recruiter/campus-drives", title: "Campus Drives", description: "Run a mass-hiring event for a college." },
];

/**
 * Recruiter dashboard. Every number here is computed from real data — the
 * team-member count is a live query — rather than hardcoded
 * (CLAUDE.md § 2: "Reports != hardcoded numbers").
 *
 * Deliberately shows no tenancy/architecture details (organization id,
 * phase numbers, etc.) — this is a normal recruiter's home screen, not a
 * developer view (CLAUDE.md § 4/§ 21). Platform-level detail belongs on
 * the SUPER_ADMIN-only /admin surface instead.
 */
export function OverviewPage() {
  const { user, accessToken } = useAuth();

  const teamQuery = useQuery({
    queryKey: ["recruiter", "users", "count"],
    queryFn: () => listUsers(accessToken as string),
    enabled: accessToken !== null,
  });
  const jobsQuery = useQuery({
    queryKey: ["recruiter", "jobs", "count"],
    queryFn: () => listJobs(accessToken as string),
    enabled: accessToken !== null,
  });
  const candidatesQuery = useQuery({
    queryKey: ["recruiter", "candidates", "count"],
    queryFn: () => listCandidates(accessToken as string),
    enabled: accessToken !== null,
  });
  const applicationsQuery = useQuery({
    queryKey: ["recruiter", "applications", "count"],
    queryFn: () => listApplications(accessToken as string),
    enabled: accessToken !== null,
  });

  return (
    <div className="stack-lg">
      <section>
        <h1>Welcome back, {user?.full_name.split(" ")[0]}</h1>
        <p className="muted">Here's what's happening with your hiring pipeline.</p>
      </section>

      <section className="card-grid">
        <div className="stat-card">
          <span className="stat-label">Open jobs</span>
          {jobsQuery.isPending && <span className="stat-value muted">Loading…</span>}
          {jobsQuery.isError && <span className="stat-value muted">Unavailable</span>}
          {jobsQuery.isSuccess && (
            <span className="stat-value">
              {jobsQuery.data.filter((job) => job.status === "OPEN").length}
            </span>
          )}
        </div>
        <div className="stat-card">
          <span className="stat-label">Candidates</span>
          {candidatesQuery.isPending && <span className="stat-value muted">Loading…</span>}
          {candidatesQuery.isError && <span className="stat-value muted">Unavailable</span>}
          {candidatesQuery.isSuccess && (
            <span className="stat-value">{candidatesQuery.data.length}</span>
          )}
        </div>
        <div className="stat-card">
          <span className="stat-label">Applications</span>
          {applicationsQuery.isPending && <span className="stat-value muted">Loading…</span>}
          {applicationsQuery.isError && <span className="stat-value muted">Unavailable</span>}
          {applicationsQuery.isSuccess && (
            <span className="stat-value">{applicationsQuery.data.length}</span>
          )}
        </div>
        <div className="stat-card">
          <span className="stat-label">Team members</span>
          {teamQuery.isPending && <span className="stat-value muted">Loading…</span>}
          {teamQuery.isError && <span className="stat-value muted">Unavailable</span>}
          {teamQuery.isSuccess && <span className="stat-value">{teamQuery.data.length}</span>}
        </div>
      </section>

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
