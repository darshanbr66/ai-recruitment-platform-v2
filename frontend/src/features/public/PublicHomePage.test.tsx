import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import * as careersApi from "../careers/api";
import { ThemeProvider } from "../theme/ThemeContext";
import { PublicHomePage } from "./PublicHomePage";

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <MemoryRouter>{ui}</MemoryRouter>
      </ThemeProvider>
    </QueryClientProvider>,
  );
}

const job = {
  id: "job-1",
  title: "Backend Engineer",
  department: "Engineering",
  location: "Remote",
  employment_type: "Full-time",
  openings_count: 1,
  created_at: new Date().toISOString(),
};

describe("PublicHomePage", () => {
  it("presents SIGVITAS' own careers site: SIGVITAS-first, with the AI shown as the intelligence behind it, not the brand", async () => {
    vi.spyOn(careersApi, "listOpenJobs").mockResolvedValue([]);

    renderWithProviders(<PublicHomePage />);

    expect(await screen.findByText("SIGVITAS")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/build what's next,\s*with sigvitas/i);

    // The public brand is SIGVITAS — never "AI Recruitment Platform" (that is the staff portal's name).
    expect(screen.queryByText(/ai recruitment platform/i)).not.toBeInTheDocument();
    // ...while the AI is still explained honestly: it assists, a person decides.
    expect(screen.getByText(/a person always makes the decision/i)).toBeInTheDocument();

    // Every occurrence of the primary CTA points at the real SIGVITAS
    // careers route, and no generic multi-tenant/SaaS language leaks in.
    for (const link of screen.getAllByRole("link", { name: /explore open roles/i })) {
      expect(link).toHaveAttribute("href", "/org/sigvitas");
    }
    for (const link of screen.getAllByRole("link", { name: /staff sign in/i })) {
      expect(link).toHaveAttribute("href", "/recruiter/login");
    }

    expect(screen.queryByText(/create your organization/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/for organizations/i)).not.toBeInTheDocument();
  });

  it("shows a live preview of current openings from the real jobs API", async () => {
    vi.spyOn(careersApi, "listOpenJobs").mockResolvedValue([job]);

    renderWithProviders(<PublicHomePage />);

    expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /backend engineer/i })).toHaveAttribute(
      "href",
      "/org/sigvitas/jobs/job-1",
    );
    // the live count in the hero comes from the same response
    expect(await screen.findByText(/1 open role right now/i)).toBeInTheDocument();
  });

  it("shows a designed empty state, and no live count, when nothing is open", async () => {
    vi.spyOn(careersApi, "listOpenJobs").mockResolvedValue([]);

    renderWithProviders(<PublicHomePage />);

    expect(await screen.findByText("No open roles right now")).toBeInTheDocument();
    expect(screen.queryByText(/^\d+ open roles? right now/i)).not.toBeInTheDocument();
  });

  it("falls back to the static network poster where WebGL isn't available", async () => {
    vi.spyOn(careersApi, "listOpenJobs").mockResolvedValue([]);

    const { container } = renderWithProviders(<PublicHomePage />);
    await screen.findByText("SIGVITAS");

    // jsdom has no WebGL: the poster is the (complete) final state, no error UI.
    expect(container.querySelector(".hero-scene")).toHaveAttribute("data-scene-status", "fallback");
    expect(container.querySelector(".network-poster")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("explains the network with a legend whose categories can be highlighted", async () => {
    vi.spyOn(careersApi, "listOpenJobs").mockResolvedValue([]);

    const { container } = renderWithProviders(<PublicHomePage />);
    const legend = await screen.findByRole("group", { name: "What the network represents" });
    const poster = () => container.querySelector(".network-poster");

    for (const label of ["Candidates", "Jobs", "Skills", "Assessments", "Organizations", "AI analysis"]) {
      expect(legend).toHaveTextContent(label);
    }
    expect(poster()).not.toHaveAttribute("data-highlight");

    const jobs = screen.getByRole("button", { name: "Jobs" });
    fireEvent.mouseEnter(jobs);
    expect(poster()).toHaveAttribute("data-highlight", "job");
    fireEvent.mouseLeave(legend);
    expect(poster()).not.toHaveAttribute("data-highlight");

    // pressing pins the highlight (also the keyboard / touch path)
    fireEvent.click(jobs);
    expect(jobs).toHaveAttribute("aria-pressed", "true");
    expect(poster()).toHaveAttribute("data-highlight", "job");
    fireEvent.click(jobs);
    expect(jobs).toHaveAttribute("aria-pressed", "false");
  });

  it("marks where AI helps and where only a person decides in the hiring process", async () => {
    vi.spyOn(careersApi, "listOpenJobs").mockResolvedValue([]);

    renderWithProviders(<PublicHomePage />);
    await screen.findByText("SIGVITAS");

    expect(screen.getAllByText("AI-assisted").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Human decision").length).toBeGreaterThan(0);
  });
});
