import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { MatchResultCard } from "./MatchResultCard";
import type { NormalizedMatch } from "./presentation";

const baseMatch: NormalizedMatch = {
  matchId: "match-1",
  candidateId: "cand-1",
  candidateName: "Priya Sharma",
  jobId: "job-1",
  jobTitle: "Full Stack Developer",
  status: "COMPLETED",
  overallScore: 95,
  confidence: "HIGH",
  matchingSkills: ["React", "Node.js", "MongoDB"],
  missingSkills: [],
  roleAlignment: "Strong alignment",
  explanation: "Candidate meets the core technical requirements and experience requirement.",
  potentialConcerns: [],
  evidence: [{ requirement_label: "React", resume_chunk_id: "chunk-1", excerpt: "Built React apps for 5 years.", similarity: 0.9 }],
  disclaimer: "AI-generated assessment. Final hiring decision remains with the recruitment team.",
};

function renderCard(match: NormalizedMatch, props: Partial<React.ComponentProps<typeof MatchResultCard>> = {}) {
  return render(
    <MemoryRouter>
      <MatchResultCard match={match} {...props} />
    </MemoryRouter>,
  );
}

describe("MatchResultCard", () => {
  it("shows the match score prominently, never labeled as 'AI confidence'", () => {
    renderCard(baseMatch);
    expect(screen.getByText("95%")).toBeInTheDocument();
    expect(screen.getByText("Strong alignment")).toBeInTheDocument();
    expect(screen.queryByText(/ai confidence/i)).not.toBeInTheDocument();
  });

  it("renders matching and missing skills separately", () => {
    renderCard({ ...baseMatch, missingSkills: ["AWS"] });
    expect(screen.getByText("React")).toBeInTheDocument();
    expect(screen.getByText("AWS")).toBeInTheDocument();
  });

  it("shows 'None' for missing skills when the candidate has none", () => {
    renderCard(baseMatch);
    expect(screen.getByText("None")).toBeInTheDocument();
  });

  it("renders the AI explanation clearly separated under its own 'Why' heading", () => {
    renderCard(baseMatch);
    expect(screen.getByText("Why")).toBeInTheDocument();
    expect(screen.getByText(/meets the core technical requirements/)).toBeInTheDocument();
  });

  it("keeps resume evidence collapsed by default and expands it on request", () => {
    renderCard(baseMatch);
    expect(screen.queryByText(/Built React apps for 5 years/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /show resume evidence/i }));
    expect(screen.getByText(/Built React apps for 5 years/)).toBeInTheDocument();
  });

  it("shows a status message instead of a score for a failed match, without exposing the raw error", () => {
    renderCard({ ...baseMatch, status: "FAILED" });
    expect(screen.queryByText("95%")).not.toBeInTheDocument();
    expect(screen.getByText(/could not be completed/i)).toBeInTheDocument();
  });

  it("supports a compare checkbox for the comparison flow", () => {
    const onToggleCompare = vi.fn();
    renderCard(baseMatch, { onToggleCompare, compareSelected: false });
    fireEvent.click(screen.getByRole("checkbox"));
    expect(onToggleCompare).toHaveBeenCalledTimes(1);
  });

  it("links to the candidate's detail page", () => {
    renderCard(baseMatch);
    expect(screen.getByRole("link", { name: /view candidate/i })).toHaveAttribute(
      "href",
      "/recruiter/candidates/cand-1",
    );
  });
});
