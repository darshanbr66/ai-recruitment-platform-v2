import { act, fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ToastProvider, useToast } from "./ToastContext";

function Trigger({ title }: { title?: string }) {
  const { showToast } = useToast();
  return (
    <button type="button" onClick={() => showToast("Saved.", "success", title)}>
      trigger
    </button>
  );
}

describe("ToastProvider", () => {
  it("still renders a plain message toast with its variant and no heading", () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "trigger" }));

    const toast = screen.getByText("Saved.").closest(".toast");
    expect(toast).toHaveClass("toast-success");
    expect(toast?.querySelector(".toast-title")).toBeNull();
  });

  it("renders an optional title above the message", () => {
    render(
      <ToastProvider>
        <Trigger title="Assessment started" />
      </ToastProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: "trigger" }));

    expect(screen.getByText("Assessment started")).toHaveClass("toast-title");
    expect(screen.getByText("Saved.")).toBeInTheDocument();
  });

  it("can be dismissed", () => {
    render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>,
    );
    fireEvent.click(screen.getByRole("button", { name: "trigger" }));

    act(() => {
      fireEvent.click(screen.getByRole("button", { name: "Dismiss" }));
    });

    expect(screen.queryByText("Saved.")).not.toBeInTheDocument();
  });
});
