import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { BackLink } from "./BackLink";

describe("BackLink", () => {
  it("is a link to the given route, named by its text", () => {
    render(
      <MemoryRouter>
        <BackLink to="/recruiter/jobs">Back to jobs</BackLink>
      </MemoryRouter>,
    );
    expect(screen.getByRole("link", { name: "Back to jobs" })).toHaveAttribute("href", "/recruiter/jobs");
  });
});
