/** The stages of the hiring pipeline, in order, and which statuses belong to each. */
export const PIPELINE_STAGES: { key: string; label: string; statuses: string[] }[] = [
  { key: "applied", label: "Applied", statuses: ["APPLIED"] },
  { key: "review", label: "Review", statuses: ["UNDER_REVIEW"] },
  { key: "screening", label: "Screening", statuses: ["SCREENING"] },
  { key: "assessment", label: "Assessment", statuses: ["ASSESSMENT_INVITED", "ASSESSMENT_STARTED", "ASSESSMENT_COMPLETED"] },
  { key: "shortlisted", label: "Shortlisted", statuses: ["SHORTLISTED"] },
  { key: "interview", label: "Interview", statuses: ["INTERVIEW"] },
  { key: "selected", label: "Selected", statuses: ["SELECTED"] },
  { key: "hired", label: "Hired", statuses: ["HIRED"] },
];

/** Index of the stage a status belongs to, or -1 (REJECTED, or anything unknown). */
export function pipelineStageIndex(status: string): number {
  return PIPELINE_STAGES.findIndex((stage) => stage.statuses.includes(status));
}
