import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { Modal } from "./Modal";

describe("Modal", () => {
  it("renders its title and children, and blocks background interaction", () => {
    render(
      <Modal title="Delete job" onClose={() => {}}>
        <p>Are you sure?</p>
      </Modal>,
    );

    const dialog = screen.getByRole("dialog", { name: "Delete job" });
    expect(dialog).toBeInTheDocument();
    expect(screen.getByText("Are you sure?")).toBeInTheDocument();
  });

  it("closes on Escape", () => {
    const onClose = vi.fn();
    render(
      <Modal title="Delete job" onClose={onClose}>
        <p>Are you sure?</p>
      </Modal>,
    );

    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes on an outside (overlay) click, but not on a click inside the card", () => {
    const onClose = vi.fn();
    render(
      <Modal title="Delete job" onClose={onClose}>
        <p>Are you sure?</p>
      </Modal>,
    );

    fireEvent.click(screen.getByText("Are you sure?"));
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("dialog", { name: "Delete job" }).parentElement!);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("closes via the explicit close button", () => {
    const onClose = vi.fn();
    render(
      <Modal title="Delete job" onClose={onClose}>
        <p>Are you sure?</p>
      </Modal>,
    );

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe("Modal viewport positioning", () => {
  it("mounts the overlay directly under document.body, outside the page that opened it", () => {
    const { container } = render(
      <div className="page-transition" style={{ transform: "translateY(0)" }}>
        <Modal title="Create a job" onClose={() => {}}>
          <p>Form</p>
        </Modal>
      </div>,
    );

    const overlay = screen.getByRole("dialog", { name: "Create a job" }).parentElement!;
    expect(overlay).toHaveClass("dialog-overlay");
    // A transformed ancestor would become the containing block of a fixed
    // overlay; being a direct child of <body> means nothing can.
    expect(overlay.parentElement).toBe(document.body);
    expect(container.contains(overlay)).toBe(false);
  });

  it("removes the overlay from the body when it closes", () => {
    const { unmount } = render(
      <Modal title="Create a job" onClose={() => {}}>
        <p>Form</p>
      </Modal>,
    );
    expect(document.querySelector(".dialog-overlay")).not.toBeNull();
    unmount();
    expect(document.querySelector(".dialog-overlay")).toBeNull();
  });

  it("gives the wide variant a class rather than an inline size", () => {
    render(
      <Modal title="Create an assessment" onClose={() => {}} wide>
        <p>Form</p>
      </Modal>,
    );
    const card = screen.getByRole("dialog", { name: "Create an assessment" });
    expect(card).toHaveClass("dialog-card", "dialog-card-wide");
    expect(card.getAttribute("style")).toBeNull();
  });
});

describe("dialog stylesheet", () => {
  const indexCss = readFileSync("src/index.css", "utf8"); // vitest runs from the frontend root
  // jsdom does no layout, so the positioning contract is pinned at the source.
  function rule(selector: string): string {
    // a selector can have several rules (the card has one for its animation)
    const pattern = new RegExp(String.raw`(?:^|\n)${selector.replace(".", String.raw`\.`)}\s*\{([^}]*)\}`, "g");
    const bodies = [...indexCss.matchAll(pattern)].map((m) => m[1]);
    expect(bodies.length, `rule for ${selector}`).toBeGreaterThan(0);
    return bodies.join("\n");
  }

  it("anchors the overlay to the viewport", () => {
    const overlay = rule(".dialog-overlay");
    expect(overlay).toMatch(/position:\s*fixed/);
    expect(overlay).toMatch(/inset:\s*0/);
    expect(overlay).toMatch(/overscroll-behavior:\s*contain/);
  });

  it("makes a tall dialog scroll itself, capped to the viewport", () => {
    const card = rule(".dialog-card");
    expect(card).toMatch(/max-height:\s*calc\(100dvh/);
    expect(card).toMatch(/overflow-y:\s*auto/);
  });
});
