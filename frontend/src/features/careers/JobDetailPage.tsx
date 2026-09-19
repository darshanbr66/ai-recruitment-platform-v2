import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../lib/apiClient";
import { Alert } from "../../shared/components/Alert";
import { ThemeToggle } from "../theme/ThemeToggle";
import { getOpenJob } from "./api";
import { JobApplicationForm } from "./JobApplicationForm";

export function JobDetailPage() {
  const { slug = "", jobId = "" } = useParams<{ slug: string; jobId: string }>();
  const jobQuery = useQuery({
    queryKey: ["public", "job", slug, jobId],
    queryFn: () => getOpenJob(slug, jobId),
  });

  return (
    <div>
      <header className="public-nav">
        <Link to="/" className="topbar-title" style={{ textDecoration: "none", color: "inherit" }}>
          {jobQuery.data?.organization.name ?? "Careers"}
        </Link>
        <ThemeToggle />
      </header>
      <div className="public-shell">
        <p>
          <Link to={`/org/${slug}`}>&larr; Back to open roles</Link>
        </p>

        {jobQuery.isPending && <p role="status">Loading role details…</p>}
        {jobQuery.isError && (
          <Alert>
            {jobQuery.error instanceof ApiError
              ? jobQuery.error.message
              : "This role could not be found."}
          </Alert>
        )}

        {jobQuery.isSuccess && (
          <>
            <h1>{jobQuery.data.title}</h1>
            <p className="muted">Careers at {jobQuery.data.organization.name}</p>
            <div className="job-card-meta" style={{ marginBottom: "1.5rem" }}>
              {jobQuery.data.department && <span>{jobQuery.data.department}</span>}
              {jobQuery.data.location && <span>{jobQuery.data.location}</span>}
              {jobQuery.data.employment_type && <span>{jobQuery.data.employment_type}</span>}
              <span>{jobQuery.data.openings_count} opening(s)</span>
            </div>

            {jobQuery.data.description && (
              <section style={{ marginBottom: "2rem" }}>
                <h2>Job Description</h2>
                <p className="job-description">{jobQuery.data.description}</p>
              </section>
            )}

            <JobApplicationForm slug={slug} jobId={jobId} />
          </>
        )}
      </div>
    </div>
  );
}
