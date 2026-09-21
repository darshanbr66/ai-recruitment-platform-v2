import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Pagination } from "./Pagination";

describe("Pagination", () => {
  it("summarizes the visible range and total", () => {
    render(<Pagination page={2} pageSize={25} total={60} onPageChange={() => {}} noun="applications" />);
    expect(screen.getByText("Showing 26–50 of 60 applications")).toBeInTheDocument();
    expect(screen.getByText("Page 2 of 3")).toBeInTheDocument();
  });

  it("clamps the last page's range to the total", () => {
    render(<Pagination page={3} pageSize={25} total={60} onPageChange={() => {}} />);
    expect(screen.getByText("Showing 51–60 of 60 results")).toBeInTheDocument();
  });

  it("asks for the neighbouring page, and can't go past either end", () => {
    const onPageChange = vi.fn();
    const { rerender } = render(<Pagination page={1} pageSize={25} total={60} onPageChange={onPageChange} />);
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: "Next page" }));
    expect(onPageChange).toHaveBeenCalledWith(2);

    rerender(<Pagination page={3} pageSize={25} total={60} onPageChange={onPageChange} />);
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "Previous page" }));
    expect(onPageChange).toHaveBeenLastCalledWith(2);
  });

  it("locks the buttons while the next page is loading", () => {
    render(<Pagination page={2} pageSize={25} total={60} onPageChange={() => {}} disabled />);
    expect(screen.getByRole("button", { name: "Previous page" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next page" })).toBeDisabled();
  });

  it("shows no buttons for a single page, and says so for none", () => {
    const { rerender } = render(<Pagination page={1} pageSize={25} total={10} onPageChange={() => {}} />);
    expect(screen.getByText("Showing 1–10 of 10 results")).toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();

    rerender(<Pagination page={1} pageSize={25} total={0} onPageChange={() => {}} />);
    expect(screen.getByText("No results")).toBeInTheDocument();
  });
});
