import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../lib/apiClient";
import { Alert } from "../../shared/components/Alert";
import { EmptyState } from "../../shared/components/EmptyState";
import { Icon } from "../../shared/components/Icon";
import { NetworkBackdrop } from "../../shared/components/NetworkBackdrop";
import { Reveal } from "../../shared/components/Reveal";
import { Skeleton } from "../../shared/components/Skeleton";
import { PublicHeader } from "../public/PublicHeader";
import { listOpenJobs } from "./api";
import { displayNameFromSlug } from "./orgName";

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
    <div className="public-page">
      <PublicHeader title={displayNameFromSlug(slug)} />
      <main className="public-shell">
        <header className="public-hero">
          <NetworkBackdrop seed={9} count={28} />
          <p className="section-eyebrow">{displayNameFromSlug(slug)} Careers</p>
          <h1>Open roles</h1>
          <p className="muted">Browse current openings and apply directly — no account required.</p>
          {jobsQuery.isSuccess && jobsQuery.data.length > 0 && (
            <span className="chip public-hero-count">
              <span className="live-dot" aria-hidden="true" />
              {jobsQuery.data.length} open {jobsQuery.data.length === 1 ? "role" : "roles"}
            </span>
          )}
        </header>

        {jobsQuery.isPending && (
          <div className="role-list" role="status" aria-label="Loading open roles">
            {[0, 1, 2].map((i) => (
              <div key={i} className="role-card role-card-skeleton" aria-hidden="true">
                <Skeleton height="1.1rem" width="55%" />
                <Skeleton height="0.8rem" width="35%" />
              </div>
            ))}
          </div>
        )}

        {jobsQuery.isError && (
          <Alert>
            {jobsQuery.error instanceof ApiError
              ? jobsQuery.error.message
              : "Could not load open roles."}
          </Alert>
        )}

        {jobsQuery.isSuccess && jobsQuery.data.length === 0 && (
          <EmptyState icon="jobs" title="No open roles right now">
            Check back soon — new openings are posted regularly.
          </EmptyState>
        )}

        {jobsQuery.isSuccess && jobsQuery.data.length > 0 && (
          <div className="role-list">
            {jobsQuery.data.map((job, index) => (
              <Reveal key={job.id} delay={Math.min(index, 6) * 50}>
                <Link to={`/org/${slug}/jobs/${job.id}`} className="role-card">
                  <span className="role-card-title">{job.title}</span>
                  <span className="role-card-meta">
                    {job.department && <span className="chip">{job.department}</span>}
                    {job.location && (
                      <span className="chip">
                        <Icon name="pin" size={13} />
                        {job.location}
                      </span>
                    )}
                    {job.employment_type && <span className="chip">{job.employment_type}</span>}
                  </span>
                  <span className="role-card-cta">
                    View role <Icon name="arrow-right" size={16} />
                  </span>
                </Link>
              </Reveal>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
