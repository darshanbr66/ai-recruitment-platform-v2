# AI / RAG Screening

Status: Phase 0 design. Resume intelligence (extraction/chunking/embeddings)
is Phase 5; AI screening (evaluation/scoring) is Phase 6. No provider is
chosen yet — this document specifies the interfaces and data model, not a
vendor integration.

## 1. Design goal

AI screening must be traceable, re-runnable without destroying history, and
decoupled from the Candidate model (`CLAUDE.md` § 2: "AI != Candidate").
Concretely: a screening result is always a property of a `ScreeningRun`
against an `Application` — never a field mutated directly on `Candidate` or
`Application` — so re-screening after a resume update or a prompt change
produces a new, independently inspectable run.

## 2. Pipeline

```
Resume (file)
  → DocumentExtractor.extract(file) → plain text                    [Phase 5]
  → ResumeDocument (stores extracted_text, extraction_engine)
  → chunking service → ResumeChunk[] (content, token_count)
  → EmbeddingProvider.embed(chunk.content) → embedding vector(N)
  → stored in resume_chunks.embedding (pgvector column)

Job → JobRequirement[] (label, description, weight, is_mandatory)

ScreeningRun (per Application, triggered manually by a recruiter or          [Phase 6]
              automatically on application submission — configurable)
  → for each JobRequirement:
      AIRun (provider, model, prompt_version, input_hash recorded)
        → retrieval: top-k ResumeChunks by pgvector similarity to the
          requirement (embedding-to-embedding, or embedding-to-query-text)
        → LLMProvider.evaluate(requirement, retrieved_chunks) →
          verdict (MEETS/PARTIAL/DOES_NOT_MEET/INSUFFICIENT_EVIDENCE) + rationale
        → RequirementEvaluation (verdict, score, rationale)
          → EvaluationEvidence[] (resume_chunk_id, similarity_score, excerpt) per supporting chunk
  → ScreeningRun.overall_score = aggregation of RequirementEvaluations
    (weighted by JobRequirement.weight; aggregation function documented in
    code, not just implied by the schema, once implemented)
```

## 3. Traceability requirements (what must be reconstructable later)

For any `RequirementEvaluation`, it must be possible to answer, from stored
data alone:

- What was evaluated → `job_requirement_id` → `JobRequirement`.
- Against which application/job → `AIRun.screening_run_id` →
  `ScreeningRun.application_id`.
- Which provider/model/prompt version produced it → `AIRun.provider`,
  `AIRun.model`, `AIRun.prompt_version`.
- What evidence supported the result → `EvaluationEvidence` rows → the exact
  `ResumeChunk`s and their similarity scores.
- When it happened → `AIRun.started_at`/`completed_at`.

This is why `AIRun` sits between `ScreeningRun` and `RequirementEvaluation`
rather than requirement evaluations hanging directly off the run as bare
rows with provider/model duplicated on each — one `AIRun` row per
requirement (or per run, if a single LLM call evaluates all requirements at
once — an implementation choice made in Phase 6, not fixed here) keeps the
provenance data normalized.

## 4. Re-running screening

A new `ScreeningRun` is a new row; nothing about a prior run is edited or
deleted. "Current score" for display purposes is defined as the most recent
`ScreeningRun` with `status=COMPLETED` for that application — a derived
read, not a stored/mutated pointer. This means:

- Comparing two screening runs (e.g. after a resume re-upload) is just
  reading two rows.
- An AI provider outage or bug that produces a bad run is isolated to that
  run's rows; it doesn't corrupt or require rolling back prior state.

## 5. Provider abstraction

`backend/app/integrations/ai/` defines the seams; concrete adapters live
beside the interfaces and are selected by configuration:

```python
class DocumentExtractor(Protocol):
    def extract(self, file_bytes: bytes, content_type: str) -> str: ...

class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...
    @property
    def dimension(self) -> int: ...

class LLMProvider(Protocol):
    def evaluate_requirement(
        self, requirement: str, evidence_chunks: list[str]
    ) -> RequirementVerdict: ...
```

Domain services in `services/screening/` depend only on these interfaces
(injected via configuration/DI), never on a specific vendor SDK. No
orchestration framework (LangChain/LangGraph) is assumed to exist; if one is
introduced later, it is confined inside a concrete adapter implementing
these same interfaces — `services/screening/` does not change.

## 6. Open items (not decided in Phase 0)

- Which embedding provider/model, and therefore the `vector(N)` dimension
  for `resume_chunks.embedding` — deferred to Phase 5, when it's chosen
  alongside a cost/latency evaluation.
- Whether `ScreeningRun` triggers automatically on application submission or
  only on explicit recruiter action — deferred to Phase 6; likely
  configurable per organization rather than hardcoded either way.
- Chunking strategy (fixed-size vs. semantic/section-aware) — deferred to
  Phase 5, informed by real resume samples.
