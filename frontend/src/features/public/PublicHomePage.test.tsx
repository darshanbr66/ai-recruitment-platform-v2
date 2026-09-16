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
    expect(screen.getByRole("link", { name: /browse open roles/i })).toHaveAttribute(
      "href",
      "/org/acme-corp",
    );
    expect(screen.getByRole("link", { name: /staff sign in/i })).toHaveAttribute(
      "href",
      "/recruiter/login",
    );
  });
});
