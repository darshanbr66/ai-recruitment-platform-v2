import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "./EmptyState";

describe("EmptyState", () => {
  it("says what's missing, why, and offers the next step", () => {
    render(
      <EmptyState icon="candidates" title="No candidates yet" action={<button type="button">Create job</button>}>
        Start building your talent pipeline.
      </EmptyState>,
    );

    expect(screen.getByText("No candidates yet")).toBeInTheDocument();
    expect(screen.getByText("Start building your talent pipeline.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create job" })).toBeInTheDocument();
  });

  it("keeps its icon decorative, and omits absent parts", () => {
    const { container } = render(<EmptyState title="Nothing here" compact />);
    expect(container.querySelector(".empty-state-icon")).toHaveAttribute("aria-hidden", "true");
    expect(container.querySelector(".empty-state-text")).toBeNull();
    expect(container.querySelector(".empty-state-action")).toBeNull();
    expect(container.firstElementChild).toHaveClass("empty-state-compact");
  });
});
