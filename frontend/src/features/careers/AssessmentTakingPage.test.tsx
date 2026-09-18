import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import type { PublicInvitationView, PublicSubmissionResult } from "../../types/assessment";
import { ThemeProvider } from "../theme/ThemeContext";
import { AssessmentTakingPage } from "./AssessmentTakingPage";
import * as careersApi from "./api";

const sentInvitation: PublicInvitationView = {
  status: "SENT",
  assessment_title: "Python Basics",
  instructions: "Answer everything.",
  duration_minutes: 30,
  job_title: "Backend Engineer",
  organization_name: "SIGVITAS",
  expires_at: new Date(Date.now() + 86_400_000).toISOString(),
  started_at: null,
  questions: [
    {
      id: "q1",
      prompt: "2 + 2?",
      type: "MCQ_SINGLE",
      points: 1,
      options: [
        { id: "o1", label: "3" },
        { id: "o2", label: "4" },
      ],
    },
  ],
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MemoryRouter initialEntries={["/assessment/tok123"]}>
          <Routes>
            <Route path="/assessment/:token" element={<AssessmentTakingPage />} />
          </Routes>
        </MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

describe("AssessmentTakingPage monitoring consent", () => {
  it("requires the consent checkbox before Start Assessment is enabled", async () => {
    vi.spyOn(careersApi, "getAssessmentInvitation").mockResolvedValue(sentInvitation);

    renderPage();

    expect(await screen.findByRole("heading", { name: "Before You Begin" })).toBeInTheDocument();
    const startButton = screen.getByRole("button", { name: "Start Assessment" });
    expect(startButton).toBeDisabled();

    fireEvent.click(
      screen.getByLabelText("I understand and agree to browser-based assessment monitoring."),
    );
    expect(startButton).not.toBeDisabled();
  });

  it("starts the assessment and sends a consent event once accepted", async () => {
    const startedInvitation: PublicInvitationView = {
      ...sentInvitation,
      status: "STARTED",
      started_at: new Date().toISOString(),
    };
    vi.spyOn(careersApi, "getAssessmentInvitation").mockImplementation(() =>
      Promise.resolve(startSpy.mock.calls.length > 0 ? startedInvitation : sentInvitation),
    );
    const startSpy = vi.spyOn(careersApi, "startAssessment").mockResolvedValue(startedInvitation);
    const eventsSpy = vi.spyOn(careersApi, "sendMonitoringEvents").mockResolvedValue(undefined);

    renderPage();
    await screen.findByRole("heading", { name: "Before You Begin" });
    fireEvent.click(
      screen.getByLabelText("I understand and agree to browser-based assessment monitoring."),
    );
    fireEvent.click(screen.getByRole("button", { name: "Start Assessment" }));

    await screen.findByText(/2 \+ 2\?/);
    expect(startSpy).toHaveBeenCalledWith("tok123");
    expect(eventsSpy).toHaveBeenCalled();
    const [, events] = eventsSpy.mock.calls[0];
    expect(events.some((e) => e.event_type === "MONITORING_CONSENT_GIVEN")).toBe(true);
  });

  it("shows a polished success screen with no score after submission", async () => {
    const started: PublicInvitationView = {
      ...sentInvitation,
      status: "STARTED",
      started_at: new Date().toISOString(),
    };
    vi.spyOn(careersApi, "getAssessmentInvitation").mockResolvedValue(started);
    const submissionResult: PublicSubmissionResult = { submitted_at: new Date().toISOString() };
    vi.spyOn(careersApi, "submitAssessment").mockResolvedValue(submissionResult);

    renderPage();
    await screen.findByText(/2 \+ 2\?/);
    fireEvent.click(screen.getByLabelText("4"));
    fireEvent.click(screen.getByRole("button", { name: "Submit assessment" }));

    expect(await screen.findByRole("heading", { name: "Assessment Submitted" })).toBeInTheDocument();
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });
});
