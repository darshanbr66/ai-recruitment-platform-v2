import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { Modal } from "../../../shared/components/Modal";
import { Spinner } from "../../../shared/components/Spinner";
import { useToast } from "../../../shared/components/ToastContext";
import { useAuth } from "../../auth/AuthContext";
import { grantEarlyReapply } from "./api";

/**
 * HR "Allow Reapply": lets one candidate self-apply once before their
 * cooldown window ends. Nothing about their existing applications changes —
 * the grant is a separate, single-use record, and the reason is required
 * because it is what the audit trail shows alongside who granted it.
 */
export function AllowReapplyModal({
  candidateId,
  candidateName,
  eligibleFrom,
  onClose,
}: {
  candidateId: string;
  candidateName: string;
  /** When the window would otherwise open, for the explanatory copy. */
  eligibleFrom: string | null;
  onClose: () => void;
}) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [reason, setReason] = useState("");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () => grantEarlyReapply(candidateId, reason.trim(), accessToken as string),
    onSuccess: () => {
      showToast(`${candidateName} can now apply again.`, "success");
      void queryClient.invalidateQueries({
        queryKey: ["recruiter", "candidates", candidateId, "reapply-status"],
      });
      // The grant is recorded as an activity, which the journey renders.
      void queryClient.invalidateQueries({
        queryKey: ["recruiter", "candidates", candidateId, "history"],
      });
      onClose();
    },
    onError: (err) => {
      setError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (reason.trim().length === 0) {
      setError("A reason is required.");
      return;
    }
    mutation.mutate();
  }

  return (
    <Modal title="Allow reapply" onClose={mutation.isPending ? () => {} : onClose}>
      <form onSubmit={handleSubmit}>
        <p>
          <strong>Candidate:</strong> {candidateName}
        </p>
        <p className="muted">
          {eligibleFrom
            ? `${candidateName} could otherwise only apply again from ${new Date(
                eligibleFrom,
              ).toLocaleDateString(undefined, { day: "numeric", month: "long", year: "numeric" })}.`
            : `${candidateName} is currently inside the reapply restriction period.`}{" "}
          This lets them submit one more application now. Their previous applications and history
          are not affected, and this is recorded in Activities.
        </p>

        <label className="field">
          <span>Reason</span>
          <textarea
            required
            rows={3}
            value={reason}
            onChange={(e) => {
              setReason(e.target.value);
              if (error) setError(null);
            }}
            disabled={mutation.isPending}
            placeholder="e.g. Candidate has since completed a relevant certification"
          />
        </label>

        {error && <Alert>{error}</Alert>}

        <div className="btn-group" style={{ marginTop: "1rem" }}>
          <button type="submit" className="btn btn-primary" disabled={mutation.isPending}>
            {mutation.isPending ? <Spinner label="Saving…" /> : "Allow reapply"}
          </button>
          <button
            type="button"
            className="btn btn-ghost"
            onClick={onClose}
            disabled={mutation.isPending}
          >
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
