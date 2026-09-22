import { useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../../../shared/components/Icon";
import {
  alignmentToneClass,
  formatConfidence,
  formatScore,
  matchStatusMessage,
  type NormalizedMatch,
} from "./presentation";

/** Skill chips: a plain "✓ skill" chip for a match, "missing" chips get a
 * dashed/muted treatment via `chip-missing` so a recruiter reads matched vs.
 * missing at a glance, not just from the heading above each list. */
function SkillChips({ skills, missing = false }: { skills: string[]; missing?: boolean }) {
  if (skills.length === 0) {
    return <span className="muted" style={{ fontSize: "0.85rem" }}>{missing ? "None" : "—"}</span>;
  }
  return (
    <div className="skill-chip-row">
      {skills.map((skill) => (
        <span key={skill} className={missing ? "chip chip-missing" : "chip chip-match"}>
          <Icon name={missing ? "x" : "check"} size={12} />
          {skill}
        </span>
      ))}
    </div>
  );
}

/**
 * The one reusable result card for every internal-AI surface (chat results,
 * job-wide ranking, candidate analysis, comparison). Shows the deterministic
 * match score prominently, the AI-generated explanation clearly separated
 * below it, and evidence collapsed by default (expand-to-view — RAG
 * grounding is communicated, never dumped on the page).
 */
export function MatchResultCard({
  match,
  showJobTitle = false,
  compareSelected,
  onToggleCompare,
  onAnalyze,
}: {
  match: NormalizedMatch;
  /** Job-wide ranking already shows one job's title in the page header —
   * candidate-specific / comparison views across jobs need it on the card. */
  showJobTitle?: boolean;
  compareSelected?: boolean;
  onToggleCompare?: () => void;
  onAnalyze?: () => void;
}) {
  const [evidenceOpen, setEvidenceOpen] = useState(false);
  const statusMessage = matchStatusMessage({ status: match.status as "PENDING" | "COMPLETED" | "FAILED", error_message: null });

  return (
    <article className={`card ai-match-card${compareSelected ? " ai-match-card-selected" : ""}`}>
      <div className="ai-match-card-head">
        <div>
          <h3 style={{ margin: 0 }}>{match.candidateName}</h3>
          {showJobTitle && <p className="muted" style={{ margin: "0.15rem 0 0", fontSize: "0.85rem" }}>{match.jobTitle}</p>}
        </div>
        {onToggleCompare && (
          <label className="ai-compare-toggle">
            <input type="checkbox" checked={compareSelected ?? false} onChange={onToggleCompare} />
            Compare
          </label>
        )}
      </div>

      {statusMessage ? (
        <p className="muted">{statusMessage}</p>
      ) : (
        <>
          <div className="ai-score-row">
            <span className="ai-score-value">{formatScore(match.overallScore)}</span>
            <div className="ai-score-meta">
              <span className={`badge ${alignmentToneClass(match.roleAlignment)}`}>
                {match.roleAlignment ?? "Not scored"}
              </span>
              <span className="muted ai-confidence-label">{formatConfidence(match.confidence)}</span>
            </div>
          </div>

          {match.categories && match.categories.length > 0 && (
            <div className="ai-category-grid">
              {match.categories.map((category) => (
                <div key={category.label} className="ai-category-item">
                  <span className="detail-row-label">{category.label}</span>
                  <div className="bar-track">
                    <div
                      className="bar-fill"
                      style={{ ["--bar-tone" as string]: "var(--color-primary)", transform: `scaleX(${category.score})` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}

          <div className="ai-skill-section">
            <span className="detail-row-label">Matching skills</span>
            <SkillChips skills={match.matchingSkills} />
          </div>
          <div className="ai-skill-section">
            <span className="detail-row-label">Missing skills</span>
            <SkillChips skills={match.missingSkills} missing />
          </div>

          {match.potentialConcerns.length > 0 && (
            <div className="ai-skill-section">
              <span className="detail-row-label">Potential concerns</span>
              <ul className="ai-concern-list">
                {match.potentialConcerns.map((concern) => (
                  <li key={concern}>{concern}</li>
                ))}
              </ul>
            </div>
          )}

          {match.explanation && (
            <div className="ai-explanation">
              <span className="detail-row-label">Why</span>
              <p>{match.explanation}</p>
            </div>
          )}

          {match.evidence.length > 0 && (
            <div className="ai-evidence">
              <button
                type="button"
                className="link-button"
                onClick={() => setEvidenceOpen((open) => !open)}
                aria-expanded={evidenceOpen}
              >
                {evidenceOpen ? "Hide resume evidence" : `Show resume evidence (${match.evidence.length})`}
              </button>
              {evidenceOpen && (
                <ul className="ai-evidence-list">
                  {match.evidence.map((item, index) => (
                    <li key={`${item.resume_chunk_id}-${index}`}>
                      <span className="ai-evidence-tag">{item.requirement_label}</span>
                      <p>&ldquo;{item.excerpt}&rdquo;</p>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
        </>
      )}

      <div className="btn-group" style={{ marginTop: "0.75rem" }}>
        <Link className="btn btn-ghost btn-sm" to={`/recruiter/candidates/${match.candidateId}`}>
          View candidate
        </Link>
        {onAnalyze && (
          <button type="button" className="btn btn-ghost btn-sm" onClick={onAnalyze}>
            Analyze
          </button>
        )}
      </div>
    </article>
  );
}
