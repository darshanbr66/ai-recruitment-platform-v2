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

describe("PublicHomePage", () => {
  it("presents the company first: SIGVITAS-branded, with Careers as a deliberate choice", async () => {
    renderWithProviders(<PublicHomePage />);

    expect((await screen.findAllByText("SIGVITAS")).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/build what's next,\s*with sigvitas/i);
    expect(screen.getByRole("heading", { name: "Who we are" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Our values" })).toBeInTheDocument();

    // The public brand is SIGVITAS — never "AI Recruitment Platform" (the staff portal's name).
    expect(screen.queryByText(/ai recruitment platform/i)).not.toBeInTheDocument();

    // Careers is reachable, and every careers link points at the real careers route.
    const careersLinks = screen.getAllByRole("link", { name: /careers/i });
    expect(careersLinks.length).toBeGreaterThan(0);
    for (const link of careersLinks) {
      expect(link).toHaveAttribute("href", "/org/sigvitas");
    }
    for (const link of screen.getAllByRole("link", { name: /staff sign in/i })) {
      expect(link).toHaveAttribute("href", "/recruiter/login");
    }
    expect(screen.queryByText(/create your organization/i)).not.toBeInTheDocument();
  });

  it("is not a job board: no openings, no 'Explore Open Roles', no hiring process", async () => {
    const listOpenJobs = vi.spyOn(careersApi, "listOpenJobs");

    renderWithProviders(<PublicHomePage />);
    await screen.findByRole("heading", { name: "Who we are" });

    expect(screen.queryByText(/explore open roles/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/our hiring process/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/current openings/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/open roles? right now/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /openings/i })).not.toBeInTheDocument();
    // The homepage doesn't even fetch jobs.
    expect(listOpenJobs).not.toHaveBeenCalled();
  });

  it("falls back to the static network poster where WebGL isn't available", async () => {
    const { container } = renderWithProviders(<PublicHomePage />);
    await screen.findByRole("heading", { level: 1 });

    // jsdom has no WebGL: the poster is the (complete) final state, no error UI.
    expect(container.querySelector(".hero-scene")).toHaveAttribute("data-scene-status", "fallback");
    expect(container.querySelector(".network-poster")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("explains the network with a legend whose categories can be highlighted", async () => {
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
});
