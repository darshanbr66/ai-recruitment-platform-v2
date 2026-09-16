import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../lib/apiClient";
import { Alert } from "../../shared/components/Alert";
import { ThemeToggle } from "../theme/ThemeToggle";
import { listOpenJobs } from "./api";

/**
 * Anonymous career site for one organization (CLAUDE.md § 1: "public career
 * site: anonymous job browse/search/details, entry point into candidate
 * apply flow"). Reached at /org/:slug — in production each tenant would
 * share this link (or a mapped custom domain) with candidates directly.
 */
export function CareersPage() {
  const { slug = "" } = useParams<{ slug: string }>();
  const jobsQuery = useQuery({
    queryKey: ["public", "jobs", slug],
    queryFn: () => listOpenJobs(slug),
  });

  return (
    <div>
      <header className="public-nav">
        <Link to="/" className="topbar-title" style={{ textDecoration: "none", color: "inherit" }}>
          AI Recruitment Platform
        </Link>
        <ThemeToggle />
      </header>
      <div className="public-shell">
        <h1>Open roles</h1>
        <p className="muted">Browse current openings and apply directly — no account required.</p>

        {jobsQuery.isPending && <p role="status">Loading open roles…</p>}

        {jobsQuery.isError && (
          <Alert>
            {jobsQuery.error instanceof ApiError
              ? jobsQuery.error.message
              : "Could not load open roles."}
          </Alert>
        )}

        {jobsQuery.isSuccess && jobsQuery.data.length === 0 && (
          <div className="empty-state">
            <p className="empty-state-title">No open roles right now</p>
            <p>Check back soon — new openings are posted regularly.</p>
          </div>
        )}

        {jobsQuery.isSuccess &&
          jobsQuery.data.map((job) => (
            <Link key={job.id} to={`/org/${slug}/jobs/${job.id}`} className="job-card">
              <div className="job-card-title">{job.title}</div>
              <div className="job-card-meta">
                {job.department && <span>{job.department}</span>}
                {job.location && <span>{job.location}</span>}
                {job.employment_type && <span>{job.employment_type}</span>}
              </div>
            </Link>
          ))}
      </div>
    </div>
  );
}
