import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../../shared/components/ToastContext";
import type {
  ApplicationResponse,
  CandidateHistoryResponse,
  CandidateResponse,
  JobResponse,
} from "../../../types/recruitment";
import * as applicationsApi from "../applications/api";
import * as jobsApi from "../jobs/api";
import { CandidateDetailPage } from "./CandidateDetailPage";
import * as candidatesApi from "./api";

vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token", user: { roles: ["RECRUITER"] } }),
}));

const candidate: CandidateResponse = {
  id: "cand-1",
  organization_id: "org-1",
  email: "priya@example.com",
  full_name: "Priya Candidate",
  phone: "+919876543210",
  location: null,
  current_title: "Software Engineer",
  years_experience: 3,
  current_company: null,
  preferred_location: null,
  candidate_type: null,
  notice_period_days: null,
  immediate_joiner: null,
  qualification: null,
  linkedin_url: null,
  github_url: null,
  date_of_birth: "1998-04-12",
  place_of_birth: "Madurai",
  languages: ["English", "Tamil"],
  email_verified_at: new Date().toISOString(),
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
    candidate_email: "priya@example.com",
    candidate_phone: null,
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

const history: CandidateHistoryResponse = {
  candidate_id: "cand-1",
  applications: [
    {
      application_id: "app-1",
      job_id: "job-1",
      job_title: "Full Stack Developer",
      source: "PORTAL",
      status: "AI_SCREENED_OUT",
      applied_at: new Date().toISOString(),
      is_original: true,
      deleted_at: null,
      screenings: [
        {
          id: "run-1",
          application_id: "app-1",
          requested_by_user_id: null,
          status: "COMPLETED",
          provider: "gemini",
          model: "gemini-test",
          overall_score: 18,
          recommendation: "NOT_A_MATCH",
          summary: "Resume is for accounting roles.",
          matching_skills: [],
          missing_skills: ["React.js"],
          strengths: [],
          concerns: [],
          experience_assessment: "",
          education_assessment: "",
          decision: "NOT_MATCH",
          matched_requirements: [],
          missing_requirements: ["React.js", "Node.js"],
          error_message: null,
          created_at: new Date().toISOString(),
          completed_at: new Date().toISOString(),
        },
      ],
    },
  ],
  timeline: [
    {
      id: "act-1",
      action: "AI_SCREENED_OUT",
      entity_type: "application",
      entity_id: "app-1",
      actor_name: null,
      description: "Automatic AI screening judged the resume a NOT_MATCH for this job.",
      reason: null,
      created_at: new Date().toISOString(),
    },
  ],
};

const openJob = {
  id: "job-2",
  title: "Data Analyst",
  status: "OPEN",
  deleted_at: null,
} as JobResponse;

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <MemoryRouter initialEntries={["/recruiter/candidates/cand-1"]}>
          <Routes>
            <Route path="/recruiter/candidates/:candidateId" element={<CandidateDetailPage />} />
          </Routes>
        </MemoryRouter>
      </ToastProvider>
    </QueryClientProvider>,
  );
}

describe("CandidateDetailPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(candidatesApi, "getCandidate").mockResolvedValue(candidate);
    vi.spyOn(candidatesApi, "getCandidateHistory").mockResolvedValue(history);
    vi.spyOn(jobsApi, "listJobs").mockResolvedValue([openJob]);
  });

  it("shows Current title and a distinct Applied roles list from multiple applications", async () => {
    vi.spyOn(applicationsApi, "listApplicationsForCandidate").mockResolvedValue([
      application({ id: "app-1", job_title: "Full Stack Developer" }),
      application({ id: "app-2", job_title: "Frontend Developer" }),
    ]);

    renderPage();

    expect(await screen.findByText("Software Engineer")).toBeInTheDocument();
    const fullStackLinks = await screen.findAllByRole("link", { name: "Full Stack Developer" });
    expect(fullStackLinks[0]).toHaveAttribute("href", "/recruiter/applications/app-1");
    expect(screen.getByRole("link", { name: "Frontend Developer" })).toHaveAttribute(
      "href",
      "/recruiter/applications/app-2",
    );
  });

  it("shows the new identity fields and email verification status", async () => {
    vi.spyOn(applicationsApi, "listApplicationsForCandidate").mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("Madurai")).toBeInTheDocument();
    expect(screen.getByText("English, Tamil")).toBeInTheDocument();
    expect(screen.getByText("+919876543210")).toBeInTheDocument();
    expect(screen.getByText(/^Verified /)).toBeInTheDocument();
  });

  it("shows the original application, AI screening evidence and activity, marked as advisory", async () => {
    vi.spyOn(applicationsApi, "listApplicationsForCandidate").mockResolvedValue([]);

    renderPage();

    const roles = await screen.findByRole("region", { name: /roles & ai screening/i });
    expect(await within(roles).findByText("Original application")).toBeInTheDocument();
    expect(within(roles).getByText("AI: not a match")).toBeInTheDocument();
    expect(within(roles).getByText(/React\.js, Node\.js/)).toBeInTheDocument();
    expect(within(roles).getByText(/AI screening is advisory/)).toBeInTheDocument();
    expect(screen.getByText("AI screening: screened out")).toBeInTheDocument();
  });

  it("lets HR match the candidate to another job", async () => {
    vi.spyOn(applicationsApi, "listApplicationsForCandidate").mockResolvedValue([]);
    const match = vi
      .spyOn(candidatesApi, "matchCandidateToJob")
      .mockResolvedValue(application({ id: "app-2", job_id: "job-2", job_title: "Data Analyst", source: "HR_MATCH" }));

    renderPage();

    const select = await screen.findByRole("combobox", { name: "Job" });
    await screen.findByRole("option", { name: "Data Analyst" });
    fireEvent.change(select, { target: { value: "job-2" } });
    fireEvent.change(screen.getByLabelText("Reason (optional)"), { target: { value: "Strong SQL" } });
    fireEvent.click(screen.getByRole("button", { name: "Match candidate" }));

    await waitFor(() =>
      expect(match).toHaveBeenCalledWith("cand-1", { job_id: "job-2", reason: "Strong SQL" }, "test-token"),
    );
  });
});
