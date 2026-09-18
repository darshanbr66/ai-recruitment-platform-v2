import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
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
  it("presents SIGVITAS' own careers site, not generic recruitment-SaaS positioning", async () => {
    vi.spyOn(careersApi, "listOpenJobs").mockResolvedValue([]);

    renderWithProviders(<PublicHomePage />);

    expect(await screen.findByText("SIGVITAS")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /build what's next, with sigvitas/i })).toBeInTheDocument();

    // Every occurrence of the primary CTA points at the real SIGVITAS
    // careers route, and no generic multi-tenant/SaaS language leaks in.
    for (const link of screen.getAllByRole("link", { name: /explore open roles/i })) {
      expect(link).toHaveAttribute("href", "/org/sigvitas");
    }
    for (const link of screen.getAllByRole("link", { name: /staff sign in/i })) {
      expect(link).toHaveAttribute("href", "/recruiter/login");
    }

    expect(screen.queryByText(/ai recruitment platform/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/create your organization/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/for organizations/i)).not.toBeInTheDocument();
  });

  it("shows a live preview of current openings from the real jobs API", async () => {
    vi.spyOn(careersApi, "listOpenJobs").mockResolvedValue([
      {
        id: "job-1",
        title: "Backend Engineer",
        department: "Engineering",
        location: "Remote",
        employment_type: "Full-time",
        openings_count: 1,
        created_at: new Date().toISOString(),
      },
    ]);

    renderWithProviders(<PublicHomePage />);

    expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();
  });
});
