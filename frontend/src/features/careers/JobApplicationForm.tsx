import { useMutation } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../lib/apiClient";
import { Alert } from "../../shared/components/Alert";
import type { CandidateType } from "../../types/recruitment";
import { applyToJob } from "./api";

const CANDIDATE_TYPE_LABELS: Record<CandidateType, string> = {
  FRESHER: "Fresher (no professional experience yet)",
  EXPERIENCED: "Experienced professional",
};

/**
 * The public application form. Which fields appear depends on the
 * candidate type: an experienced candidate also gives their experience,
 * current role and availability; a fresher does not. The backend enforces
 * the same rules (app/schemas/candidate.py::PublicApplicantProfile) — the
 * checks here only save a round trip.
 */
export function JobApplicationForm({ slug, jobId }: { slug: string; jobId: string }) {
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [candidateType, setCandidateType] = useState<CandidateType | "">("");
  const [yearsExperience, setYearsExperience] = useState("");
  const [noticePeriodDays, setNoticePeriodDays] = useState("");
  const [immediateJoiner, setImmediateJoiner] = useState(false);
  const [currentTitle, setCurrentTitle] = useState("");
  const [currentCompany, setCurrentCompany] = useState("");
  const [currentLocation, setCurrentLocation] = useState("");
  const [preferredLocation, setPreferredLocation] = useState("");
  const [qualification, setQualification] = useState("");
  const [linkedinUrl, setLinkedinUrl] = useState("");
  const [githubUrl, setGithubUrl] = useState("");
  const [resume, setResume] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const isExperienced = candidateType === "EXPERIENCED";

  const applyMutation = useMutation({
    mutationFn: () => {
      if (!resume) throw new Error("Resume is required.");
      if (candidateType === "") throw new Error("Candidate type is required.");
      return applyToJob(
        slug,
        jobId,
        {
          full_name: fullName,
          email,
          phone,
          candidate_type: candidateType,
          years_experience: yearsExperience,
          notice_period_days: noticePeriodDays,
          immediate_joiner: immediateJoiner,
          current_title: currentTitle,
          current_company: currentCompany,
          current_location: currentLocation,
          preferred_location: preferredLocation,
          qualification,
          linkedin_url: linkedinUrl,
          github_url: githubUrl,
        },
        resume,
      );
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to submit your application.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (candidateType === "") {
      setFormError("Please tell us whether you are a fresher or an experienced professional.");
      return;
    }
    if (!resume) {
      setFormError("Please attach your resume.");
      return;
    }
    applyMutation.mutate();
  }

  if (applyMutation.isSuccess) {
    return (
      <Alert variant="success">
        Thanks, {applyMutation.data.candidate_email}! Your application for{" "}
        <strong>{applyMutation.data.job_title}</strong> has been received. We'll be in touch.
      </Alert>
    );
  }

  const disabled = applyMutation.isPending;

  return (
    <section className="card">
      <h2>Apply for this role</h2>
      <form onSubmit={handleSubmit}>
        <label className="field">
          <span>Full name</span>
          <input
            required
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            disabled={disabled}
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={disabled}
            />
          </label>

          <label className="field">
            <span>Phone</span>
            <input value={phone} onChange={(e) => setPhone(e.target.value)} disabled={disabled} />
          </label>
        </div>

        <label className="field">
          <span>I am a…</span>
          <select
            required
            value={candidateType}
            onChange={(e) => setCandidateType(e.target.value as CandidateType | "")}
            disabled={disabled}
          >
            <option value="">Select…</option>
            {(Object.keys(CANDIDATE_TYPE_LABELS) as CandidateType[]).map((type) => (
              <option key={type} value={type}>
                {CANDIDATE_TYPE_LABELS[type]}
              </option>
            ))}
          </select>
        </label>

        {isExperienced && (
          <>
            <div className="field-row">
              <label className="field">
                <span>Total experience (years)</span>
                <input
                  type="number"
                  required
                  min={0}
                  max={80}
                  step={1}
                  value={yearsExperience}
                  onChange={(e) => setYearsExperience(e.target.value)}
                  disabled={disabled}
                />
              </label>

              <label className="field">
                <span>Notice period (days)</span>
                <input
                  type="number"
                  required={!immediateJoiner}
                  min={0}
                  max={365}
                  step={1}
                  value={immediateJoiner ? "0" : noticePeriodDays}
                  onChange={(e) => setNoticePeriodDays(e.target.value)}
                  disabled={disabled || immediateJoiner}
                />
              </label>
            </div>

            <label
              className="field"
              style={{ flexDirection: "row", alignItems: "center", gap: "0.6rem" }}
            >
              <input
                type="checkbox"
                checked={immediateJoiner}
                onChange={(e) => setImmediateJoiner(e.target.checked)}
                disabled={disabled}
                style={{ width: "auto" }}
              />
              <span>I can join immediately</span>
            </label>

            <div className="field-row">
              <label className="field">
                <span>Current job title</span>
                <input
                  value={currentTitle}
                  onChange={(e) => setCurrentTitle(e.target.value)}
                  disabled={disabled}
                />
              </label>

              <label className="field">
                <span>Current company</span>
                <input
                  value={currentCompany}
                  onChange={(e) => setCurrentCompany(e.target.value)}
                  disabled={disabled}
                />
              </label>
            </div>
          </>
        )}

        <div className="field-row">
          <label className="field">
            <span>Current location</span>
            <input
              value={currentLocation}
              onChange={(e) => setCurrentLocation(e.target.value)}
              disabled={disabled}
            />
          </label>

          <label className="field">
            <span>Preferred location</span>
            <input
              value={preferredLocation}
              onChange={(e) => setPreferredLocation(e.target.value)}
              disabled={disabled}
            />
          </label>
        </div>

        <label className="field">
          <span>Highest qualification</span>
          <input
            value={qualification}
            onChange={(e) => setQualification(e.target.value)}
            placeholder="e.g. B.Tech in Computer Science"
            disabled={disabled}
          />
        </label>

        <div className="field-row">
          <label className="field">
            <span>LinkedIn profile (optional)</span>
            <input
              type="url"
              value={linkedinUrl}
              onChange={(e) => setLinkedinUrl(e.target.value)}
              placeholder="https://www.linkedin.com/in/…"
              disabled={disabled}
            />
          </label>

          <label className="field">
            <span>GitHub profile (optional)</span>
            <input
              type="url"
              value={githubUrl}
              onChange={(e) => setGithubUrl(e.target.value)}
              placeholder="https://github.com/…"
              disabled={disabled}
            />
          </label>
        </div>

        <label className="field">
          <span>Resume (PDF, DOC, or DOCX)</span>
          <input
            type="file"
            required
            accept=".pdf,.doc,.docx"
            onChange={(e) => setResume(e.target.files?.[0] ?? null)}
            disabled={disabled}
          />
        </label>

        {formError && <Alert>{formError}</Alert>}

        <button type="submit" className="btn btn-primary" disabled={disabled}>
          {disabled ? "Submitting…" : "Submit application"}
        </button>
      </form>
    </section>
  );
}
