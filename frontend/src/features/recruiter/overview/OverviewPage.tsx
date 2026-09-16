import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../../auth/AuthContext";
import { listUsers } from "../../auth/api";
import { listCandidates } from "../candidates/api";
import { listJobs } from "../jobs/api";
import { listApplications } from "../applications/api";

const UPCOMING_MODULES = [
  { title: "AI Screening", phase: "Phase 5–6" },
  { title: "Assessments", phase: "Phase 7" },
  { title: "Campus Drives", phase: "Phase 8" },
  { title: "Reports", phase: "Phase 10" },
];

/**
 * Platform Overview. Every number here is computed from real data — the
 * team-member count is a live query — rather than hardcoded
 * (CLAUDE.md § 2: "Reports != hardcoded numbers"). Modules not yet built
 * are shown as labeled placeholders, not populated with fake data.
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
        <p className="muted">
          Organization ID <code>{user?.organization_id}</code>
        </p>
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
        <h2>Recruitment lifecycle</h2>
        <p className="muted">
          Identity/tenancy (Phase 2) and Jobs/Candidates/Applications (Phase 3) are live. The rest
          of the hiring workflow ships in the phases below.
        </p>
        <div className="card-grid">
          {UPCOMING_MODULES.map((module) => (
            <div key={module.title} className="module-card module-card-upcoming">
              <span className="module-title">{module.title}</span>
              <span className="module-phase">{module.phase}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
