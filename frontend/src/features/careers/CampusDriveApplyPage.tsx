import { useMutation, useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../lib/apiClient";
import { Alert } from "../../shared/components/Alert";
import { ThemeToggle } from "../theme/ThemeToggle";
import { applyToCampusDrive, getCampusDriveByToken } from "./api";

export function CampusDriveApplyPage() {
  const { token = "" } = useParams<{ token: string }>();
  const driveQuery = useQuery({
    queryKey: ["public", "campus-drive", token],
    queryFn: () => getCampusDriveByToken(token),
  });

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [resume, setResume] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const applyMutation = useMutation({
    mutationFn: () => {
      if (!resume) throw new Error("Resume is required.");
      return applyToCampusDrive(token, { full_name: fullName, email, phone }, resume);
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
        {driveQuery.isPending && <p role="status">Loading drive details…</p>}
        {driveQuery.isError && (
          <Alert>
            {driveQuery.error instanceof ApiError
              ? driveQuery.error.message
              : "This campus drive link is no longer valid."}
          </Alert>
        )}

        {driveQuery.isSuccess && (
          <>
            <h1>{driveQuery.data.name}</h1>
            <p className="muted">
              {driveQuery.data.organization_name} · {driveQuery.data.college_name}
            </p>
            <div className="job-card-meta" style={{ marginBottom: "1.5rem" }}>
              <span>Hiring for: {driveQuery.data.job_title}</span>
              {driveQuery.data.registration_deadline && (
                <span>
                  Register by {new Date(driveQuery.data.registration_deadline).toLocaleDateString()}
                </span>
              )}
            </div>

            {driveQuery.data.description && (
              <section style={{ marginBottom: "1.5rem" }}>
                <h2>About this drive</h2>
                <p className="job-description">{driveQuery.data.description}</p>
              </section>
            )}

            <section style={{ marginBottom: "2rem" }}>
              <h2>About the role</h2>
              <p className="job-description">{driveQuery.data.job_description}</p>
            </section>

            {driveQuery.data.status !== "ACTIVE" ? (
              <Alert>This campus drive is not currently accepting applications.</Alert>
            ) : applyMutation.isSuccess ? (
              <Alert variant="success">
                Thanks, {applyMutation.data.candidate_email}! Your application for{" "}
                <strong>{applyMutation.data.job_title}</strong> has been received.
                {applyMutation.data.assessment_invitation_link
                  ? " This drive includes an assessment — check your email for the invitation link to complete it."
                  : " We'll be in touch."}
              </Alert>
            ) : (
              <section className="card">
                <h2>Apply for this drive</h2>
                {driveQuery.data.has_assessment && (
                  <p className="field-hint" style={{ marginBottom: "1rem" }}>
                    This drive includes an assessment — after you apply, you'll be directed to take it.
                  </p>
                )}
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

                  <button type="submit" className="btn btn-primary" disabled={applyMutation.isPending}>
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
