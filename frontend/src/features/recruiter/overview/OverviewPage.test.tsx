import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ReportOverview } from "../../../types/report";
import * as applicationsApi from "../applications/api";
import * as reportsApi from "../reports/api";
import { OverviewPage } from "./OverviewPage";

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token", user: { full_name: "Riya Recruiter" } }),
}));

const overview: ReportOverview = {
  total_jobs: 3,
  open_jobs: 2,
  total_candidates: 5,
  total_applications: 7,
  selected_candidates: 2,
  rejected_candidates: 3,
  hired_candidates: 1,
  applications_by_status: [],
  applications_by_job: [],
  screening: { total_runs: 0, completed: 0, failed: 0, average_score: null },
  assessments: { total_invitations: 0, submitted: 0, passed: 0 },
  campus_drives: [],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <OverviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OverviewPage dashboard cards", () => {
  it("shows candidate outcome cards and no Open jobs/Applications cards", async () => {
    vi.spyOn(reportsApi, "getReportOverview").mockResolvedValue(overview);
    vi.spyOn(applicationsApi, "listApplications").mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("Selected Candidates")).toBeInTheDocument();
    expect(screen.getByText("Rejected Candidates")).toBeInTheDocument();
    expect(screen.getByText("Hired Candidates")).toBeInTheDocument();
    expect(screen.queryByText("Open jobs")).not.toBeInTheDocument();
    expect(screen.queryByText("Applications")).not.toBeInTheDocument();
  });
});
