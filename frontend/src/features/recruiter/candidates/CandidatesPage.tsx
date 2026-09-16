import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { useAuth } from "../../auth/AuthContext";
import { createCandidate, listCandidates } from "./api";

const CANDIDATES_QUERY_KEY = ["recruiter", "candidates"];

export function CandidatesPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const candidatesQuery = useQuery({
    queryKey: CANDIDATES_QUERY_KEY,
    queryFn: () => listCandidates(accessToken as string),
    enabled: accessToken !== null,
  });

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [currentTitle, setCurrentTitle] = useState("");
  const [yearsExperience, setYearsExperience] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const createCandidateMutation = useMutation({
    mutationFn: () =>
      createCandidate(
        {
          email,
          full_name: fullName,
          phone: phone || null,
          location: location || null,
          current_title: currentTitle || null,
          years_experience: yearsExperience ? Number(yearsExperience) : null,
        },
        accessToken as string,
      ),
    onSuccess: () => {
      setFullName("");
      setEmail("");
      setPhone("");
      setLocation("");
      setCurrentTitle("");
      setYearsExperience("");
      setFormError(null);
      void queryClient.invalidateQueries({ queryKey: CANDIDATES_QUERY_KEY });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createCandidateMutation.mutate();
  }

  const canManageCandidates = !(
    candidatesQuery.error instanceof ApiError && candidatesQuery.error.status === 403
  );

  return (
    <div className="stack-lg">
      <section>
        <h1>Candidates</h1>
        <p className="muted">People who have been added into your pipeline.</p>
      </section>

      {candidatesQuery.isPending && <p role="status">Loading candidates…</p>}

      {candidatesQuery.isError && !canManageCandidates && (
        <Alert>You do not have permission to view candidates.</Alert>
      )}
      {candidatesQuery.isError && canManageCandidates && (
        <Alert>
          {candidatesQuery.error instanceof ApiError
            ? candidatesQuery.error.message
            : "Could not load candidates."}
        </Alert>
      )}

      {candidatesQuery.isSuccess && (
        <section>
          {candidatesQuery.data.length === 0 ? (
            <p className="muted">No candidates yet — add the first one below.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Current title</th>
                  <th>Location</th>
                  <th>Experience</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {candidatesQuery.data.map((candidate) => (
                  <tr key={candidate.id}>
                    <td>{candidate.full_name}</td>
                    <td>{candidate.email}</td>
                    <td>{candidate.current_title ?? "—"}</td>
                    <td>{candidate.location ?? "—"}</td>
                    <td>
                      {candidate.years_experience !== null
                        ? `${candidate.years_experience} yrs`
                        : "—"}
                    </td>
                    <td>{candidate.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {canManageCandidates && (
        <section className="card">
          <h2>Add a candidate</h2>
          <form onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span>Full name</span>
              <input
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                disabled={createCandidateMutation.isPending}
              />
            </label>

            <label className="field">
              <span>Email</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={createCandidateMutation.isPending}
              />
            </label>

            <label className="field">
              <span>Phone</span>
              <input
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                disabled={createCandidateMutation.isPending}
              />
            </label>

            <label className="field">
              <span>Location</span>
              <input
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                disabled={createCandidateMutation.isPending}
              />
            </label>

            <label className="field">
              <span>Current title</span>
              <input
                value={currentTitle}
                onChange={(e) => setCurrentTitle(e.target.value)}
                disabled={createCandidateMutation.isPending}
              />
            </label>

            <label className="field">
              <span>Years of experience</span>
              <input
                type="number"
                min={0}
                max={80}
                value={yearsExperience}
                onChange={(e) => setYearsExperience(e.target.value)}
                disabled={createCandidateMutation.isPending}
              />
            </label>

            {formError && <Alert>{formError}</Alert>}

            <button
              type="submit"
              className="btn btn-primary"
              disabled={createCandidateMutation.isPending}
            >
              {createCandidateMutation.isPending ? "Adding…" : "Add candidate"}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
