import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { useToast } from "../../../shared/components/ToastContext";
import type { ParsedQuestionsResponse, QuestionCreate, QuestionType } from "../../../types/assessment";
import { useAuth } from "../../auth/AuthContext";
import { createAssessment, listAssessments, parseImportQuestions } from "./api";

const ASSESSMENTS_QUERY_KEY = ["recruiter", "assessments"];

const TEMPLATE_CSV =
  "question,option_1,option_2,option_3,option_4,correct,type,points\n" +
  '"What is 2 + 2?",3,4,5,6,2,single,1\n' +
  '"Which of these are prime numbers?",2,4,6,7,"1,4",multiple,2\n';

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

function isBlankQuestion(q: QuestionCreate): boolean {
  return q.prompt.trim() === "" && q.options.every((o) => o.label.trim() === "");
}

function downloadTemplate() {
  const blob = new Blob([TEMPLATE_CSV], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "assessment-questions-template.csv";
  link.click();
  URL.revokeObjectURL(url);
}

export function AssessmentsPage() {
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const { showToast } = useToast();

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
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [preview, setPreview] = useState<ParsedQuestionsResponse | null>(null);
  const [selected, setSelected] = useState<boolean[]>([]);
  const [importError, setImportError] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: () =>
      createAssessment(
        { title, instructions, duration_minutes: durationMinutes, pass_score: passScore, questions },
        token,
      ),
    onSuccess: () => {
      showToast("Assessment created.", "success");
      setTitle("");
      setInstructions("");
      setDurationMinutes(30);
      setPassScore(60);
      setQuestions([emptyQuestion()]);
      setPreview(null);
      setFormError(null);
      setShowForm(false);
      void queryClient.invalidateQueries({ queryKey: ASSESSMENTS_QUERY_KEY });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  const importMutation = useMutation({
    mutationFn: (file: File) => parseImportQuestions(file, token),
    onSuccess: (result) => {
      setImportError(null);
      setPreview(result);
      setSelected(result.questions.map(() => true));
      if (result.questions.length === 0) {
        showToast("No usable questions were found in that file.", "error");
      } else {
        showToast(`Found ${result.questions.length} question(s) — review and add them below.`, "success");
      }
    },
    onError: (err) => {
      setImportError(err instanceof ApiError ? err.message : "Could not read that file.");
      setPreview(null);
    },
  });

  function handleFileChosen(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    setImportError(null);
    importMutation.mutate(file);
  }

  function toggleSelected(index: number) {
    setSelected((current) => current.map((v, i) => (i === index ? !v : v)));
  }

  function addSelectedQuestions() {
    if (!preview) return;
    const chosen = preview.questions.filter((_, i) => selected[i]);
    if (chosen.length === 0) return;
    setQuestions((current) => {
      const base = current.length === 1 && isBlankQuestion(current[0]) ? [] : current;
      return [...base, ...chosen];
    });
    setPreview(null);
    showToast(`Added ${chosen.length} question(s) to the assessment.`, "success");
  }

  function updateQuestion(index: number, patch: Partial<QuestionCreate>) {
    setQuestions((current) => current.map((q, i) => (i === index ? { ...q, ...patch } : q)));
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
        const options = q.options.map((o, j) => (j === oIndex ? { ...o, ...patch } : o));
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

  function moveQuestion(index: number, direction: -1 | 1) {
    setQuestions((current) => {
      const target = index + direction;
      if (target < 0 || target >= current.length) return current;
      const next = [...current];
      [next[index], next[target]] = [next[target], next[index]];
      return next;
    });
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

      {assessmentsQuery.isSuccess &&
        (assessmentsQuery.data.length === 0 ? (
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
        ))}

      {showForm && (
        <section className="card">
          <div className="page-header">
            <h2>Create an assessment</h2>
            <button
              type="button"
              className="btn btn-ghost btn-sm"
              onClick={() => {
                setShowForm(false);
                setPreview(null);
              }}
            >
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

            <fieldset className="field">
              <legend>Import questions</legend>
              <p className="field-hint" style={{ marginBottom: "0.6rem" }}>
                Upload a PDF, DOCX, XLSX, or CSV file. Tabular files (CSV/XLSX) need a{" "}
                <code>question</code> column, <code>option_1</code>/<code>option_2</code>/… columns, and
                a <code>correct</code> column (by number or letter). PDF/DOCX files need numbered
                questions with lettered options — mark the right one with a trailing <code>*</code> or
                add an <code>Answer: B</code> line.
              </p>
              <div className="btn-group">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.docx,.xlsx,.csv"
                  onChange={handleFileChosen}
                  style={{ display: "none" }}
                />
                <button
                  type="button"
                  className="btn btn-ghost btn-sm"
                  disabled={importMutation.isPending}
                  onClick={() => fileInputRef.current?.click()}
                >
                  {importMutation.isPending ? "Reading file…" : "Choose file to import"}
                </button>
                <button type="button" className="btn btn-ghost btn-sm" onClick={downloadTemplate}>
                  Download CSV template
                </button>
              </div>
              {importError && (
                <div style={{ marginTop: "0.6rem" }}>
                  <Alert>{importError}</Alert>
                </div>
              )}
            </fieldset>

            {preview && (
              <section className="card" style={{ background: "var(--color-bg)" }}>
                <h3>Import preview — nothing is saved yet</h3>
                {preview.warnings.length > 0 && (
                  <div className="stack-sm" style={{ marginBottom: "0.75rem" }}>
                    {preview.warnings.map((w, i) => (
                      <p key={i} className="field-hint" style={{ color: "var(--color-warn-text)" }}>
                        {w}
                      </p>
                    ))}
                  </div>
                )}
                {preview.questions.length === 0 ? (
                  <p className="muted">No usable questions were found — see the warnings above.</p>
                ) : (
                  <>
                    <div className="stack-lg" style={{ gap: "0.6rem" }}>
                      {preview.questions.map((q, i) => (
                        <label
                          key={i}
                          style={{
                            display: "flex",
                            flexDirection: "row",
                            alignItems: "flex-start",
                            gap: "0.6rem",
                          }}
                        >
                          <input
                            type="checkbox"
                            checked={selected[i] ?? true}
                            onChange={() => toggleSelected(i)}
                            style={{ marginTop: "0.2rem", width: "auto", flexShrink: 0 }}
                          />
                          <span>
                            <strong>{q.prompt}</strong> <span className="muted">({q.type}, {q.points} pt)</span>
                            <br />
                            <span className="muted">
                              {q.options
                                .map((o) => (o.is_correct ? `${o.label} ✓` : o.label))
                                .join(" · ")}
                            </span>
                          </span>
                        </label>
                      ))}
                    </div>
                    <div className="btn-group" style={{ marginTop: "1rem" }}>
                      <button
                        type="button"
                        className="btn btn-primary btn-sm"
                        onClick={addSelectedQuestions}
                        disabled={selected.every((v) => !v)}
                      >
                        Add {selected.filter(Boolean).length} selected question(s)
                      </button>
                      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setPreview(null)}>
                        Discard
                      </button>
                    </div>
                  </>
                )}
              </section>
            )}

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

                  <div className="btn-group" style={{ marginTop: "0.75rem" }}>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={qIndex === 0}
                      onClick={() => moveQuestion(qIndex, -1)}
                    >
                      Move up
                    </button>
                    <button
                      type="button"
                      className="btn btn-ghost btn-sm"
                      disabled={qIndex === questions.length - 1}
                      onClick={() => moveQuestion(qIndex, 1)}
                    >
                      Move down
                    </button>
                    {questions.length > 1 && (
                      <button
                        type="button"
                        className="btn btn-danger btn-sm"
                        onClick={() => removeQuestion(qIndex)}
                      >
                        Remove question
                      </button>
                    )}
                  </div>
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
