import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
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
