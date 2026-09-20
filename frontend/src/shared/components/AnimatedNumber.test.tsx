import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AnimatedNumber } from "./AnimatedNumber";

class ImmediateIntersectionObserver {
  private callback: (entries: { isIntersecting: boolean }[]) => void;
  constructor(callback: (entries: { isIntersecting: boolean }[]) => void) {
    this.callback = callback;
  }
  observe() {
    this.callback([{ isIntersecting: true }]);
  }
  disconnect() {}
}

function stubMatchMedia(reduced: boolean) {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("prefers-reduced-motion") ? reduced : false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("AnimatedNumber", () => {
  it("renders the true value straight away where it cannot animate (no IntersectionObserver)", () => {
    const { rerender } = render(<AnimatedNumber value={1234} />);
    expect(screen.getByText("1,234")).toBeInTheDocument();

    rerender(<AnimatedNumber value={5} />);
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("renders the true value straight away for reduced motion, even where it could animate", () => {
    stubMatchMedia(true);
    vi.stubGlobal("IntersectionObserver", ImmediateIntersectionObserver);

    render(<AnimatedNumber value={42} />);

    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("counts up from zero and settles exactly on the value", async () => {
    vi.useFakeTimers();
    stubMatchMedia(false);
    vi.stubGlobal("IntersectionObserver", ImmediateIntersectionObserver);

    const { container } = render(<AnimatedNumber value={100} duration={800} />);
    const shown = () => Number(container.textContent);

    expect(shown()).toBe(0);
    await act(async () => {
      vi.advanceTimersByTime(300);
    });
    expect(shown()).toBeGreaterThan(0);
    expect(shown()).toBeLessThan(100);
    await act(async () => {
      vi.advanceTimersByTime(1000);
    });
    expect(shown()).toBe(100);
  });

  it("uses the supplied formatter", () => {
    render(<AnimatedNumber value={7} format={(n) => `${n} pts`} />);
    expect(screen.getByText("7 pts")).toBeInTheDocument();
  });
});
