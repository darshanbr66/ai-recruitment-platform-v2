import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { Modal } from "../../../shared/components/Modal";
import { SkeletonTable } from "../../../shared/components/Skeleton";
import { Spinner } from "../../../shared/components/Spinner";
import { useToast } from "../../../shared/components/ToastContext";
import type { CandidateResponse, CandidateSource } from "../../../types/recruitment";
import { useAuth } from "../../auth/AuthContext";
import { createCandidate, deleteCandidate, listCandidates } from "./api";

const CANDIDATES_QUERY_KEY = ["recruiter", "candidates"];

const SOURCE_BADGE: Record<CandidateSource, string> = {
  PORTAL: "badge-active",
  RECRUITER_ADDED: "badge-inactive",
  CAMPUS_IMPORT: "badge-warn",
  REFERRAL: "badge-inactive",
  OTHER: "badge-inactive",
};

export function CandidatesPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const { showToast } = useToast();
  const [showForm, setShowForm] = useState(false);

  const candidatesQuery = useQuery({
    queryKey: CANDIDATES_QUERY_KEY,
    queryFn: () => listCandidates(accessToken as string),
    enabled: accessToken !== null,
  });

  const [search, setSearch] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [location, setLocation] = useState("");
  const [currentTitle, setCurrentTitle] = useState("");
  const [yearsExperience, setYearsExperience] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [pendingDelete, setPendingDelete] = useState<CandidateResponse | null>(null);
  const [deleteReason, setDeleteReason] = useState("");
  const [deleteError, setDeleteError] = useState<string | null>(null);

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
      showToast("Candidate added.", "success");
      setFullName("");
      setEmail("");
      setPhone("");
      setLocation("");
      setCurrentTitle("");
      setYearsExperience("");
      setFormError(null);
      setShowForm(false);
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

  const deleteMutation = useMutation({
    mutationFn: () => deleteCandidate(pendingDelete!.id, deleteReason.trim(), accessToken as string),
    onSuccess: (_data, _vars) => {
      showToast(`${pendingDelete?.full_name} was deleted.`, "success");
      setPendingDelete(null);
      setDeleteReason("");
      setDeleteError(null);
      void queryClient.invalidateQueries({ queryKey: CANDIDATES_QUERY_KEY });
    },
    onError: (err) => {
      setDeleteError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function openDeleteModal(candidate: CandidateResponse) {
    setPendingDelete(candidate);
    setDeleteReason("");
    setDeleteError(null);
  }

  function closeDeleteModal() {
    if (deleteMutation.isPending) return;
    setPendingDelete(null);
    setDeleteReason("");
    setDeleteError(null);
  }

  function handleDeleteSubmit(event: FormEvent) {
    event.preventDefault();
    if (deleteReason.trim().length === 0) {
      setDeleteError("A reason for deletion is required.");
      return;
    }
    deleteMutation.mutate();
  }

  const canManageCandidates = !(
    candidatesQuery.error instanceof ApiError && candidatesQuery.error.status === 403
  );

  const filteredCandidates = useMemo(() => {
    if (!candidatesQuery.data) return [];
    const term = search.trim().toLowerCase();
    if (!term) return candidatesQuery.data;
    return candidatesQuery.data.filter(
      (candidate) =>
        candidate.full_name.toLowerCase().includes(term) ||
        candidate.email.toLowerCase().includes(term) ||
        (candidate.current_title ?? "").toLowerCase().includes(term) ||
        (candidate.location ?? "").toLowerCase().includes(term),
    );
  }, [candidatesQuery.data, search]);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Candidates</h1>
          <p className="muted">Everyone in your talent pipeline.</p>
        </div>
        {canManageCandidates && (
          <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>
            + Add candidate
          </button>
        )}
      </div>

      {candidatesQuery.isPending && <SkeletonTable columns={8} />}

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
        <section className="stack-lg" style={{ gap: "1rem" }}>
          {candidatesQuery.data.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state-title">No candidates yet</p>
              <p>They'll show up here automatically once your career site starts receiving applications.</p>
            </div>
          ) : (
            <>
              <div className="toolbar">
                <input
                  className="search-input"
                  placeholder="Search by name, email, title, or location…"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
              <div className="table-scroll">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Name</th>
                      <th>Email</th>
                      <th>Current title</th>
                      <th>Location</th>
                      <th>Experience</th>
                      <th>Source</th>
                      {canManageCandidates && <th>Actions</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCandidates.map((candidate, index) => (
                      <tr
                        key={candidate.id}
                        className="clickable-row"
                        onClick={() => navigate(`/recruiter/candidates/${candidate.id}`)}
                      >
                        <td>{index + 1}</td>
                        <td>{candidate.full_name}</td>
                        <td>{candidate.email}</td>
                        <td>{candidate.current_title ?? "—"}</td>
                        <td>{candidate.location ?? "—"}</td>
                        <td>
                          {candidate.years_experience !== null
                            ? `${candidate.years_experience} yrs`
                            : "—"}
                        </td>
                        <td>
                          <span className={`badge ${SOURCE_BADGE[candidate.source]}`}>
                            {candidate.source}
                          </span>
                        </td>
                        {canManageCandidates && (
                          <td onClick={(e) => e.stopPropagation()}>
                            <button
                              type="button"
                              className="btn btn-danger btn-sm"
                              onClick={() => openDeleteModal(candidate)}
                            >
                              Delete
                            </button>
                          </td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}

      {canManageCandidates && showForm && (
        <Modal title="Add a candidate" onClose={() => setShowForm(false)}>
          <form onSubmit={handleSubmit}>
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

            <div className="btn-group" style={{ marginTop: "1rem" }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={createCandidateMutation.isPending}
              >
                {createCandidateMutation.isPending ? <Spinner label="Adding…" /> : "Add candidate"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={() => setShowForm(false)}
                disabled={createCandidateMutation.isPending}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}

      {pendingDelete && (
        <Modal title="Delete candidate" onClose={closeDeleteModal}>
          <form onSubmit={handleDeleteSubmit}>
            <p>
              <strong>Candidate:</strong> {pendingDelete.full_name}
              <br />
              <strong>Email:</strong> {pendingDelete.email}
            </p>
            <p className="muted">
              This removes {pendingDelete.full_name} from your active candidate list. Their
              applications and history are preserved, and this action is recorded in Activities.
            </p>
            <label className="field">
              <span>Reason for deletion</span>
              <textarea
                required
                rows={3}
                value={deleteReason}
                onChange={(e) => {
                  setDeleteReason(e.target.value);
                  if (deleteError) setDeleteError(null);
                }}
                disabled={deleteMutation.isPending}
                placeholder="e.g. Duplicate candidate record"
              />
            </label>

            {deleteError && <Alert>{deleteError}</Alert>}

            <div className="btn-group" style={{ marginTop: "1rem" }}>
              <button type="submit" className="btn btn-danger" disabled={deleteMutation.isPending}>
                {deleteMutation.isPending ? <Spinner label="Deleting…" /> : "Delete Candidate"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={closeDeleteModal}
                disabled={deleteMutation.isPending}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}
