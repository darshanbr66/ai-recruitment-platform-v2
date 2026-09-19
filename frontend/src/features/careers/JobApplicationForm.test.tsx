import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import * as careersApi from "./api";
import { JobApplicationForm } from "./JobApplicationForm";

function renderForm() {
  const queryClient = new QueryClient({ defaultOptions: { mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <JobApplicationForm slug="acme" jobId="job-1" />
    </QueryClientProvider>,
  );
}

function fill(label: string | RegExp, value: string) {
  fireEvent.change(screen.getByLabelText(label), { target: { value } });
}

function attachResume() {
  const file = new File(["%PDF-1.4"], "resume.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText(/Resume/), { target: { files: [file] } });
  return file;
}

describe("JobApplicationForm", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it("shows experience and availability fields only for experienced candidates", () => {
    renderForm();

    expect(screen.queryByLabelText(/Total experience/)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Notice period/)).not.toBeInTheDocument();
    // Always present, whatever the candidate type.
    expect(screen.getByLabelText("Current location")).toBeInTheDocument();
    expect(screen.getByLabelText("Preferred location")).toBeInTheDocument();
    expect(screen.getByLabelText("Highest qualification")).toBeInTheDocument();
    expect(screen.getByLabelText(/LinkedIn/)).toBeInTheDocument();
    expect(screen.getByLabelText(/GitHub/)).toBeInTheDocument();

    fill("I am a…", "FRESHER");
    expect(screen.queryByLabelText(/Total experience/)).not.toBeInTheDocument();

    fill("I am a…", "EXPERIENCED");
    expect(screen.getByLabelText(/Total experience/)).toBeInTheDocument();
    expect(screen.getByLabelText(/Notice period/)).toBeInTheDocument();
    expect(screen.getByLabelText("Current job title")).toBeInTheDocument();
    expect(screen.getByLabelText("Current company")).toBeInTheDocument();
    expect(screen.getByLabelText("I can join immediately")).toBeInTheDocument();
  });

  it("submits the experienced candidate's full profile", async () => {
    const apply = vi.spyOn(careersApi, "applyToJob").mockResolvedValue({
      id: "app-1",
      job_title: "Backend Engineer",
      candidate_email: "eli@example.com",
      status: "APPLIED",
      submitted_at: new Date().toISOString(),
    });

    renderForm();
    fill("Full name", "Eli Experienced");
    fill("Email", "eli@example.com");
    fill("I am a…", "EXPERIENCED");
    fill(/Total experience/, "6");
    fill(/Notice period/, "30");
    fill("Current job title", "Senior Engineer");
    fill("Current company", "Globex");
    fill("Current location", "Pune");
    fill("Preferred location", "Bengaluru");
    fill("Highest qualification", "B.Tech");
    fill(/LinkedIn/, "https://www.linkedin.com/in/eli");
    fill(/GitHub/, "https://github.com/eli");
    const file = attachResume();
    // jsdom doesn't count a programmatically assigned file toward `required`,
    // so a button click would be blocked by native validation; submit directly.
    fireEvent.submit(screen.getByRole("button", { name: "Submit application" }).closest("form")!);

    await waitFor(() => expect(apply).toHaveBeenCalledTimes(1));
    expect(apply).toHaveBeenCalledWith(
      "acme",
      "job-1",
      expect.objectContaining({
        candidate_type: "EXPERIENCED",
        years_experience: "6",
        notice_period_days: "30",
        immediate_joiner: false,
        current_title: "Senior Engineer",
        current_company: "Globex",
        current_location: "Pune",
        preferred_location: "Bengaluru",
        qualification: "B.Tech",
        linkedin_url: "https://www.linkedin.com/in/eli",
        github_url: "https://github.com/eli",
      }),
      file,
    );
    expect(await screen.findByText(/has been received/)).toBeInTheDocument();
  });

  it("does not need a notice period from an immediate joiner", () => {
    renderForm();
    fill("I am a…", "EXPERIENCED");

    expect(screen.getByLabelText(/Notice period/)).toBeRequired();
    fireEvent.click(screen.getByLabelText("I can join immediately"));

    const notice = screen.getByLabelText(/Notice period/);
    expect(notice).not.toBeRequired();
    expect(notice).toBeDisabled();
    expect(notice).toHaveValue(0);
  });

  it("asks for the candidate type before submitting", async () => {
    const apply = vi.spyOn(careersApi, "applyToJob");

    renderForm();
    fill("Full name", "Someone");
    fill("Email", "someone@example.com");
    attachResume();
    fireEvent.submit(screen.getByRole("button", { name: "Submit application" }).closest("form")!);

    expect(await screen.findByText(/fresher or an experienced professional/)).toBeInTheDocument();
    expect(apply).not.toHaveBeenCalled();
  });
});
