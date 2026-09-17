import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { ThemeProvider } from "../theme/ThemeContext";
import { PublicHomePage } from "./PublicHomePage";

function renderWithProviders(ui: React.ReactElement) {
  return render(
    <ThemeProvider>
      <MemoryRouter>{ui}</MemoryRouter>
    </ThemeProvider>,
  );
}

describe("PublicHomePage", () => {
  it("renders the platform heading and links to the demo career site and staff sign-in", () => {
    renderWithProviders(<PublicHomePage />);

    expect(screen.getByRole("heading", { name: /ai recruitment platform/i })).toBeInTheDocument();

    // The hero, final CTA, and footer each repeat these calls to action by
    // design (docs section "Final CTA" / "Footer" are distinct from Hero) —
    // every occurrence must point at the same destination.
    for (const link of screen.getAllByRole("link", { name: /browse open roles/i })) {
      expect(link).toHaveAttribute("href", "/org/sigvitas");
    }
    for (const link of screen.getAllByRole("link", { name: /staff sign in/i })) {
      expect(link).toHaveAttribute("href", "/recruiter/login");
    }
    for (const link of screen.getAllByRole("link", { name: /get started/i })) {
      expect(link).toHaveAttribute("href", "/recruiter/login");
    }
  });
});
