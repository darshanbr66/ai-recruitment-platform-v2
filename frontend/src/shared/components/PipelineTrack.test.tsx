import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { pipelineStageIndex } from "../lib/pipelineStages";
import { PipelineTrack } from "./PipelineTrack";

describe("pipelineStageIndex", () => {
  it("maps every assessment status to the one assessment stage", () => {
    const stage = pipelineStageIndex("ASSESSMENT_INVITED");
    expect(stage).toBeGreaterThan(-1);
    expect(pipelineStageIndex("ASSESSMENT_STARTED")).toBe(stage);
    expect(pipelineStageIndex("ASSESSMENT_COMPLETED")).toBe(stage);
  });

  it("puts REJECTED and unknown statuses off the track", () => {
    expect(pipelineStageIndex("REJECTED")).toBe(-1);
    expect(pipelineStageIndex("SOMETHING_ELSE")).toBe(-1);
  });
});

describe("PipelineTrack", () => {
  it("marks earlier stages done, the current one as the step, and later ones pending", () => {
    render(<PipelineTrack status="SHORTLISTED" />);
    const stages = within(screen.getByRole("list", { name: "Application pipeline" })).getAllByRole("listitem");

    const current = stages.filter((li) => li.getAttribute("aria-current") === "step");
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveTextContent("Shortlisted");
    expect(stages.filter((li) => li.classList.contains("is-done")).map((li) => li.textContent)).toEqual(
      expect.arrayContaining([expect.stringContaining("Applied"), expect.stringContaining("Screening")]),
    );
    expect(stages.filter((li) => li.classList.contains("is-todo")).length).toBeGreaterThan(0);
  });

  it("shows the exact status under a stage that covers several statuses", () => {
    render(<PipelineTrack status="ASSESSMENT_STARTED" />);
    expect(screen.getByText("Assessment started")).toBeInTheDocument();
  });

  it("says so, and highlights no stage, when the application was rejected", () => {
    render(<PipelineTrack status="REJECTED" />);
    expect(screen.getByRole("status")).toHaveTextContent(/rejected/i);
    expect(document.querySelector('[aria-current="step"]')).toBeNull();
  });

  it("renders a compact bar with an accessible summary instead of the full list", () => {
    render(<PipelineTrack status="INTERVIEW" compact />);
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
    expect(screen.getByRole("img", { name: /stage \d of 8/i })).toBeInTheDocument();
  });
});
