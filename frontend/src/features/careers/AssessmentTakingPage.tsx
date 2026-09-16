import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError } from "../../lib/apiClient";
import { Alert } from "../../shared/components/Alert";
import { ThemeToggle } from "../theme/ThemeToggle";
import { getAssessmentInvitation, startAssessment, submitAssessment } from "./api";

export function AssessmentTakingPage() {
  const { token = "" } = useParams<{ token: string }>();
  const queryClient = useQueryClient();
  const [answers, setAnswers] = useState<Record<string, string[]>>({});

  const invitationQuery = useQuery({
    queryKey: ["public", "assessment", token],
    queryFn: () => getAssessmentInvitation(token),
  });

  const startMutation = useMutation({
    mutationFn: () => startAssessment(token),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["public", "assessment", token] }),
  });

  const submitMutation = useMutation({
    mutationFn: () =>
      submitAssessment(
        token,
        Object.entries(answers).map(([question_id, selected_option_ids]) => ({
          question_id,
          selected_option_ids,
        })),
      ),
  });

  function toggleOption(questionId: string, optionId: string, multi: boolean) {
    setAnswers((current) => {
      const existing = current[questionId] ?? [];
      if (multi) {
        const next = existing.includes(optionId)
          ? existing.filter((id) => id !== optionId)
          : [...existing, optionId];
        return { ...current, [questionId]: next };
      }
      return { ...current, [questionId]: [optionId] };
    });
  }

  return (
    <div>
      <header className="public-nav">
        <span className="topbar-title">AI Recruitment Platform</span>
        <ThemeToggle />
      </header>
      <div className="public-shell">
        {invitationQuery.isPending && <p role="status">Loading assessment…</p>}
        {invitationQuery.isError && (
          <Alert>
            {invitationQuery.error instanceof ApiError
              ? invitationQuery.error.message
              : "This invitation link is no longer valid."}
          </Alert>
        )}

        {invitationQuery.isSuccess && submitMutation.isSuccess && (
          <Alert variant="success">
            Thanks — your assessment has been submitted. You scored {submitMutation.data.percentage}%.
          </Alert>
        )}

        {invitationQuery.isSuccess && !submitMutation.isSuccess && (
          <>
            <h1>{invitationQuery.data.assessment_title}</h1>
            <p className="muted">
              {invitationQuery.data.job_title} at {invitationQuery.data.organization_name}
            </p>

            {invitationQuery.data.status === "SUBMITTED" && (
              <Alert variant="success">You've already submitted this assessment. Thank you!</Alert>
            )}

            {invitationQuery.data.status === "SENT" && (
              <section className="card">
                <p>{invitationQuery.data.instructions}</p>
                <p className="muted">
                  Duration: {invitationQuery.data.duration_minutes} minutes ·{" "}
                  {invitationQuery.data.questions.length} question(s)
                </p>
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={startMutation.isPending}
                  onClick={() => startMutation.mutate()}
                >
                  {startMutation.isPending ? "Starting…" : "Start assessment"}
                </button>
              </section>
            )}

            {invitationQuery.data.status === "STARTED" && (
              <section className="stack-lg">
                <p className="muted">{invitationQuery.data.instructions}</p>
                {invitationQuery.data.questions.map((question, index) => (
                  <div key={question.id} className="card">
                    <p>
                      <strong>
                        {index + 1}. {question.prompt}
                      </strong>{" "}
                      <span className="muted">({question.points} pt{question.points === 1 ? "" : "s"})</span>
                    </p>
                    <div className="stack-lg" style={{ gap: "0.4rem" }}>
                      {question.options.map((option) => (
                        <label
                          key={option.id}
                          style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
                        >
                          <input
                            type={question.type === "MCQ_MULTI" ? "checkbox" : "radio"}
                            name={question.id}
                            checked={(answers[question.id] ?? []).includes(option.id)}
                            onChange={() =>
                              toggleOption(question.id, option.id, question.type === "MCQ_MULTI")
                            }
                          />
                          {option.label}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}

                {submitMutation.isError && (
                  <Alert>
                    {submitMutation.error instanceof ApiError
                      ? submitMutation.error.message
                      : "Could not submit your answers."}
                  </Alert>
                )}

                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={submitMutation.isPending}
                  onClick={() => submitMutation.mutate()}
                >
                  {submitMutation.isPending ? "Submitting…" : "Submit assessment"}
                </button>
              </section>
            )}
          </>
        )}
      </div>
    </div>
  );
}
