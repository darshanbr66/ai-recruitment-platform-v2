import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { SkeletonLines } from "../../../shared/components/Skeleton";
import { Spinner } from "../../../shared/components/Spinner";
import { useToast } from "../../../shared/components/ToastContext";
import type { AssessmentCreateRequest, AssessmentResponse } from "../../../types/assessment";
import { useAuth } from "../../auth/AuthContext";
import { AssessmentForm } from "./AssessmentForm";
import { getAssessment, updateAssessment } from "./api";

function toFormValue(assessment: AssessmentResponse): AssessmentCreateRequest {
  return {
    title: assessment.title,
    instructions: assessment.instructions,
    duration_minutes: assessment.duration_minutes,
    pass_score: assessment.pass_score,
    questions: assessment.questions.map((q) => ({
      prompt: q.prompt,
      type: q.type,
      points: q.points,
      options: q.options.map((o) => ({ label: o.label, is_correct: o.is_correct })),
    })),
  };
}

export function AssessmentDetailPage() {
  const { assessmentId = "" } = useParams<{ assessmentId: string }>();
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const assessmentQuery = useQuery({
    queryKey: ["recruiter", "assessments", assessmentId],
    queryFn: () => getAssessment(assessmentId, token),
    enabled: accessToken !== null && assessmentId !== "",
  });

  const [editing, setEditing] = useState(false);
  // Only meaningful while `editing` is true — `startEditing`/`cancelEditing`
  // set it from the latest server data in the same event handler that
  // flips `editing`, so it's never stale or out of sync on entry.
  const [formValue, setFormValue] = useState<AssessmentCreateRequest | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const canManage = !(assessmentQuery.error instanceof ApiError && assessmentQuery.error.status === 403);

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!formValue || !assessmentQuery.data) throw new Error("Nothing to save.");
      const locked = assessmentQuery.data.has_invitations;
      return updateAssessment(
        assessmentId,
        {
          title: formValue.title,
          instructions: formValue.instructions,
          duration_minutes: formValue.duration_minutes,
          pass_score: formValue.pass_score,
          // Omitted entirely when locked — sending an unchanged question
          // set would still trip the backend's has-invitations guard.
          ...(locked ? {} : { questions: formValue.questions }),
        },
        token,
      );
    },
    onSuccess: (updated) => {
      showToast("Assessment updated.", "success");
      setEditing(false);
      queryClient.setQueryData(["recruiter", "assessments", assessmentId], updated);
      void queryClient.invalidateQueries({ queryKey: ["recruiter", "assessments"] });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function startEditing() {
    if (assessmentQuery.data) setFormValue(toFormValue(assessmentQuery.data));
    setFormError(null);
    setEditing(true);
  }

  function cancelEditing() {
    if (assessmentQuery.data) setFormValue(toFormValue(assessmentQuery.data));
    setFormError(null);
    setEditing(false);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    saveMutation.mutate();
  }

  return (
    <div className="stack-lg">
      <p>
        <Link to="/recruiter/assessments">&larr; Back to assessments</Link>
      </p>

      {assessmentQuery.isPending && <SkeletonLines count={6} />}
      {assessmentQuery.isError && !canManage && (
        <Alert>You do not have permission to view this assessment.</Alert>
      )}
      {assessmentQuery.isError && canManage && (
        <Alert>
          {assessmentQuery.error instanceof ApiError
            ? assessmentQuery.error.message
            : "Could not load this assessment."}
        </Alert>
      )}

      {assessmentQuery.isSuccess && (
        <>
          <div className="page-header">
            <div>
              <h1>{assessmentQuery.data.title}</h1>
              <div style={{ display: "flex", gap: "0.5rem", marginTop: "0.35rem" }}>
                <span className={`badge ${assessmentQuery.data.deleted_at ? "badge-inactive" : "badge-active"}`}>
                  {assessmentQuery.data.deleted_at ? "Archived" : "Active"}
                </span>
                {assessmentQuery.data.has_invitations && (
                  <span className="badge badge-warn" title="Questions are locked because this assessment has been sent to a candidate">
                    In use — questions locked
                  </span>
                )}
              </div>
            </div>
            {canManage && !editing && (
              <button type="button" className="btn btn-primary" onClick={startEditing}>
                Edit
              </button>
            )}
          </div>

          {!editing ? (
            <section className="card stack-lg" style={{ gap: "1rem" }}>
              <div className="detail-row">
                <span className="detail-row-label">Instructions</span>
                <span>{assessmentQuery.data.instructions}</span>
              </div>
              <div className="detail-row">
                <span className="detail-row-label">Duration</span>
                <span>{assessmentQuery.data.duration_minutes} minutes</span>
              </div>
              <div className="detail-row">
                <span className="detail-row-label">Pass score</span>
                <span>{assessmentQuery.data.pass_score}%</span>
              </div>
              <div className="detail-row">
                <span className="detail-row-label">Created</span>
                <span>{new Date(assessmentQuery.data.created_at).toLocaleString()}</span>
              </div>
              <div className="detail-row">
                <span className="detail-row-label">Last updated</span>
                <span>{new Date(assessmentQuery.data.updated_at).toLocaleString()}</span>
              </div>

              <div>
                <h2>Questions ({assessmentQuery.data.questions.length})</h2>
                <div className="stack-lg" style={{ gap: "0.75rem" }}>
                  {assessmentQuery.data.questions.map((question, index) => (
                    <div key={question.id} className="card" style={{ background: "var(--color-bg)" }}>
                      <p>
                        <strong>
                          {index + 1}. {question.prompt}
                        </strong>{" "}
                        <span className="muted">
                          ({question.type === "MCQ_SINGLE" ? "Single choice" : "Multiple choice"},{" "}
                          {question.points} pt)
                        </span>
                      </p>
                      <ul style={{ margin: 0, paddingLeft: "1.25rem" }}>
                        {question.options.map((option) => (
                          <li key={option.id}>
                            {option.label} {option.is_correct && <span aria-label="Correct answer">✓</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </div>
            </section>
          ) : formValue ? (
            <section className="card">
              <form onSubmit={handleSubmit}>
                <AssessmentForm
                  value={formValue}
                  onChange={setFormValue}
                  disabled={saveMutation.isPending}
                  questionsLocked={assessmentQuery.data.has_invitations}
                  accessToken={token}
                />

                {formError && <Alert>{formError}</Alert>}

                <div className="btn-group" style={{ marginTop: "1.5rem" }}>
                  <button type="submit" className="btn btn-primary" disabled={saveMutation.isPending}>
                    {saveMutation.isPending ? <Spinner label="Saving…" /> : "Save changes"}
                  </button>
                  <button
                    type="button"
                    className="btn btn-ghost"
                    onClick={cancelEditing}
                    disabled={saveMutation.isPending}
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}
