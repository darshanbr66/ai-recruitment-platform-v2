import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { ApplicationResponse, CandidateResponse } from "../../../types/recruitment";
import * as applicationsApi from "../applications/api";
import { CandidateDetailPage } from "./CandidateDetailPage";
import * as candidatesApi from "./api";

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token" }),
}));

const candidate: CandidateResponse = {
  id: "cand-1",
  organization_id: "org-1",
  email: "priya@example.com",
  full_name: "Priya Candidate",
  phone: null,
  location: null,
  current_title: "Software Engineer",
  years_experience: 3,
  source: "PORTAL",
  is_active: true,
  deleted_at: null,
  created_at: new Date().toISOString(),
  updated_at: new Date().toISOString(),
};

function application(overrides: Partial<ApplicationResponse>): ApplicationResponse {
  return {
    id: "app-1",
    organization_id: "org-1",
    candidate_id: "cand-1",
    candidate_full_name: "Priya Candidate",
    job_id: "job-1",
    job_title: "Full Stack Developer",
    campus_drive_id: null,
    status: "APPLIED",
    source: "PORTAL",
    applied_at: new Date().toISOString(),
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    resume_id: null,
    resume_filename: null,
    deleted_at: null,
    ...overrides,
  };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/recruiter/candidates/cand-1"]}>
        <Routes>
          <Route path="/recruiter/candidates/:candidateId" element={<CandidateDetailPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CandidateDetailPage applied roles", () => {
  it("shows Current title and a distinct Applied roles list from multiple applications", async () => {
    vi.spyOn(candidatesApi, "getCandidate").mockResolvedValue(candidate);
    vi.spyOn(applicationsApi, "listApplicationsForCandidate").mockResolvedValue([
      application({ id: "app-1", job_title: "Full Stack Developer" }),
      application({ id: "app-2", job_title: "Frontend Developer" }),
    ]);

    renderPage();

    expect(await screen.findByText("Software Engineer")).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Full Stack Developer" })).toHaveAttribute(
      "href",
      "/recruiter/applications/app-1",
    );
    expect(screen.getByRole("link", { name: "Frontend Developer" })).toHaveAttribute(
      "href",
      "/recruiter/applications/app-2",
    );
  });
});
