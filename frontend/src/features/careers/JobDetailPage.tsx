import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../lib/apiClient";
import { Alert } from "../../shared/components/Alert";
import { ThemeToggle } from "../theme/ThemeToggle";
import { applyToJob, getOpenJob } from "./api";

export function JobDetailPage() {
  const { slug = "", jobId = "" } = useParams<{ slug: string; jobId: string }>();
  const jobQuery = useQuery({
    queryKey: ["public", "job", slug, jobId],
    queryFn: () => getOpenJob(slug, jobId),
  });

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [resume, setResume] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const applyMutation = useMutation({
    mutationFn: () => {
      if (!resume) throw new Error("Resume is required.");
      return applyToJob(slug, jobId, { full_name: fullName, email, phone }, resume);
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to submit your application.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (!resume) {
      setFormError("Please attach your resume.");
      return;
    }
    applyMutation.mutate();
  }

  return (
    <div>
      <header className="public-nav">
        <Link to="/" className="topbar-title" style={{ textDecoration: "none", color: "inherit" }}>
          AI Recruitment Platform
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

            <section style={{ marginBottom: "2rem" }}>
              <h2>About this role</h2>
              <p className="job-description">{jobQuery.data.description}</p>
            </section>

            {applyMutation.isSuccess ? (
              <Alert variant="success">
                Thanks, {applyMutation.data.candidate_email}! Your application for{" "}
                <strong>{applyMutation.data.job_title}</strong> has been received. We'll be in
                touch.
              </Alert>
            ) : (
              <section className="card">
                <h2>Apply for this role</h2>
                <form onSubmit={handleSubmit} noValidate>
                  <label className="field">
                    <span>Full name</span>
                    <input
                      required
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      disabled={applyMutation.isPending}
                    />
                  </label>

                  <label className="field">
                    <span>Email</span>
                    <input
                      type="email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      disabled={applyMutation.isPending}
                    />
                  </label>

                  <label className="field">
                    <span>Phone</span>
                    <input
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                      disabled={applyMutation.isPending}
                    />
                  </label>

                  <label className="field">
                    <span>Resume (PDF, DOC, or DOCX)</span>
                    <input
                      type="file"
                      required
                      accept=".pdf,.doc,.docx"
                      onChange={(e) => setResume(e.target.files?.[0] ?? null)}
                      disabled={applyMutation.isPending}
                    />
                  </label>

                  {formError && <Alert>{formError}</Alert>}

                  <button
                    type="submit"
                    className="btn btn-primary"
                    disabled={applyMutation.isPending}
                  >
                    {applyMutation.isPending ? "Submitting…" : "Submit application"}
                  </button>
                </form>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
