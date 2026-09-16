import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import type { QuestionCreate, QuestionType } from "../../../types/assessment";
import { useAuth } from "../../auth/AuthContext";
import { createAssessment, listAssessments } from "./api";

const ASSESSMENTS_QUERY_KEY = ["recruiter", "assessments"];

function emptyQuestion(): QuestionCreate {
  return {
    prompt: "",
    type: "MCQ_SINGLE",
    points: 1,
    options: [
      { label: "", is_correct: true },
      { label: "", is_correct: false },
    ],
  };
}

export function AssessmentsPage() {
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();

  const assessmentsQuery = useQuery({
    queryKey: ASSESSMENTS_QUERY_KEY,
    queryFn: () => listAssessments(token),
    enabled: accessToken !== null,
  });

  const [showForm, setShowForm] = useState(false);
  const [title, setTitle] = useState("");
  const [instructions, setInstructions] = useState("");
  const [durationMinutes, setDurationMinutes] = useState(30);
  const [passScore, setPassScore] = useState(60);
  const [questions, setQuestions] = useState<QuestionCreate[]>([emptyQuestion()]);
  const [formError, setFormError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createAssessment(
        { title, instructions, duration_minutes: durationMinutes, pass_score: passScore, questions },
        token,
      ),
    onSuccess: () => {
      setTitle("");
      setInstructions("");
      setDurationMinutes(30);
      setPassScore(60);
      setQuestions([emptyQuestion()]);
      setFormError(null);
      setShowForm(false);
      void queryClient.invalidateQueries({ queryKey: ASSESSMENTS_QUERY_KEY });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function updateQuestion(index: number, patch: Partial<QuestionCreate>) {
    setQuestions((current) =>
      current.map((q, i) => (i === index ? { ...q, ...patch } : q)),
    );
  }

  function updateQuestionType(index: number, type: QuestionType) {
    setQuestions((current) =>
      current.map((q, i) => {
        if (i !== index) return q;
        if (type === "MCQ_SINGLE") {
          let picked = false;
          const options = q.options.map((o) => {
            const isCorrect = !picked && o.is_correct;
            if (isCorrect) picked = true;
            return { ...o, is_correct: isCorrect };
          });
          if (!picked && options.length > 0) options[0].is_correct = true;
          return { ...q, type, options };
        }
        return { ...q, type };
      }),
    );
  }

  function updateOption(qIndex: number, oIndex: number, patch: { label?: string; is_correct?: boolean }) {
    setQuestions((current) =>
      current.map((q, i) => {
        if (i !== qIndex) return q;
        const options = q.options.map((o, j) => {
          if (j !== oIndex) return o;
          return { ...o, ...patch };
        });
        // MCQ_SINGLE: selecting one option clears the others.
        if (patch.is_correct && q.type === "MCQ_SINGLE") {
          return { ...q, options: options.map((o, j) => ({ ...o, is_correct: j === oIndex })) };
        }
        return { ...q, options };
      }),
    );
  }

  function addQuestion() {
    setQuestions((current) => [...current, emptyQuestion()]);
  }

  function removeQuestion(index: number) {
    setQuestions((current) => current.filter((_, i) => i !== index));
  }

  function addOption(qIndex: number) {
    setQuestions((current) =>
      current.map((q, i) =>
        i === qIndex ? { ...q, options: [...q.options, { label: "", is_correct: false }] } : q,
      ),
    );
  }

  function removeOption(qIndex: number, oIndex: number) {
    setQuestions((current) =>
      current.map((q, i) =>
        i === qIndex ? { ...q, options: q.options.filter((_, j) => j !== oIndex) } : q,
      ),
    );
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createMutation.mutate();
  }

  const canManage = !(assessmentsQuery.error instanceof ApiError && assessmentsQuery.error.status === 403);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Assessments</h1>
          <p className="muted">Reusable skills tests you can send to any candidate.</p>
        </div>
        {canManage && (
          <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>
            + New assessment
          </button>
        )}
      </div>

      {assessmentsQuery.isPending && <p role="status">Loading assessments…</p>}
      {assessmentsQuery.isError && !canManage && (
        <Alert>You do not have permission to view assessments.</Alert>
      )}

      {assessmentsQuery.isSuccess && (
        assessmentsQuery.data.length === 0 ? (
          <div className="empty-state">
            <p className="empty-state-title">No assessments yet</p>
            <p>Create one to start screening candidates with skills tests.</p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Questions</th>
                  <th>Duration</th>
                  <th>Pass score</th>
                </tr>
              </thead>
              <tbody>
                {assessmentsQuery.data.map((a) => (
                  <tr key={a.id}>
                    <td>{a.title}</td>
                    <td>{a.question_count}</td>
                    <td>{a.duration_minutes} min</td>
                    <td>{a.pass_score}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )
      )}

      {showForm && (
        <section className="card">
          <div className="page-header">
            <h2>Create an assessment</h2>
            <button type="button" className="btn btn-ghost btn-sm" onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
          <form onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span>Title</span>
              <input required value={title} onChange={(e) => setTitle(e.target.value)} />
            </label>
            <label className="field">
              <span>Instructions for the candidate</span>
              <textarea
                required
                rows={2}
                value={instructions}
                onChange={(e) => setInstructions(e.target.value)}
              />
            </label>
            <div className="field-row">
              <label className="field">
                <span>Duration (minutes)</span>
                <input
                  type="number"
                  min={1}
                  value={durationMinutes}
                  onChange={(e) => setDurationMinutes(Number(e.target.value))}
                />
              </label>
              <label className="field">
                <span>Pass score (%)</span>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={passScore}
                  onChange={(e) => setPassScore(Number(e.target.value))}
                />
              </label>
            </div>

            <h3>Questions</h3>
            <div className="stack-lg" style={{ gap: "1rem" }}>
              {questions.map((question, qIndex) => (
                <div key={qIndex} className="card" style={{ background: "var(--color-bg)" }}>
                  <div className="field-row">
                    <label className="field" style={{ gridColumn: "1 / -1" }}>
                      <span>Question {qIndex + 1}</span>
                      <input
                        required
                        value={question.prompt}
                        onChange={(e) => updateQuestion(qIndex, { prompt: e.target.value })}
                      />
                    </label>
                  </div>
                  <div className="field-row">
                    <label className="field">
                      <span>Type</span>
                      <select
                        value={question.type}
                        onChange={(e) => updateQuestionType(qIndex, e.target.value as QuestionType)}
                      >
                        <option value="MCQ_SINGLE">Single choice</option>
                        <option value="MCQ_MULTI">Multiple choice</option>
                      </select>
                    </label>
                    <label className="field">
                      <span>Points</span>
                      <input
                        type="number"
                        min={1}
                        value={question.points}
                        onChange={(e) => updateQuestion(qIndex, { points: Number(e.target.value) })}
                      />
                    </label>
                  </div>

                  <div className="stack-lg" style={{ gap: "0.4rem" }}>
                    {question.options.map((option, oIndex) => (
                      <div key={oIndex} style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                        <input
                          type={question.type === "MCQ_SINGLE" ? "radio" : "checkbox"}
                          name={`correct-${qIndex}`}
                          checked={option.is_correct}
                          onChange={(e) => updateOption(qIndex, oIndex, { is_correct: e.target.checked })}
                          title="Correct answer"
                        />
                        <input
                          required
                          placeholder={`Option ${oIndex + 1}`}
                          value={option.label}
                          onChange={(e) => updateOption(qIndex, oIndex, { label: e.target.value })}
                          style={{ flex: 1 }}
                        />
                        {question.options.length > 2 && (
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => removeOption(qIndex, oIndex)}
                          >
                            Remove
                          </button>
                        )}
                      </div>
                    ))}
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      onClick={() => addOption(qIndex)}
                      style={{ alignSelf: "flex-start" }}
                    >
                      + Add option
                    </button>
                  </div>

                  {questions.length > 1 && (
                    <button
                      type="button"
                      className="btn btn-danger btn-sm"
                      style={{ marginTop: "0.75rem" }}
                      onClick={() => removeQuestion(qIndex)}
                    >
                      Remove question
                    </button>
                  )}
                </div>
              ))}
            </div>

            <button
              type="button"
              className="btn btn-ghost"
              style={{ marginTop: "1rem" }}
              onClick={addQuestion}
            >
              + Add question
            </button>

            {formError && <Alert>{formError}</Alert>}

            <div style={{ marginTop: "1.5rem" }}>
              <button type="submit" className="btn btn-primary" disabled={createMutation.isPending}>
                {createMutation.isPending ? "Creating…" : "Create assessment"}
              </button>
            </div>
          </form>
        </section>
      )}
    </div>
  );
}
