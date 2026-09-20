import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog", () => {
  it("mounts under document.body, outside the page that opened it", () => {
    const { container } = render(
      <div className="page-transition" style={{ transform: "translateY(0)" }}>
        <ConfirmDialog title="Delete entry?" message="Cannot be undone." onConfirm={() => {}} onCancel={() => {}} />
      </div>,
    );

    const overlay = screen.getByRole("alertdialog", { name: "Delete entry?" }).parentElement!;
    expect(overlay.parentElement).toBe(document.body);
    expect(container.contains(overlay)).toBe(false);
  });

  it("still confirms, cancels, and cancels on an overlay click", () => {
    const onConfirm = vi.fn();
    const onCancel = vi.fn();
    render(<ConfirmDialog title="Delete entry?" message="x" confirmLabel="Delete entry" onConfirm={onConfirm} onCancel={onCancel} />);

    fireEvent.click(screen.getByRole("button", { name: "Delete entry" }));
    expect(onConfirm).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("alertdialog").parentElement!);
    expect(onCancel).toHaveBeenCalledTimes(2);
  });
});
