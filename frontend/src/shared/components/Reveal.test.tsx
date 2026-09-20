import { act, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Reveal } from "./Reveal";

afterEach(() => vi.unstubAllGlobals());

describe("Reveal", () => {
  it("is visible immediately where IntersectionObserver doesn't exist (content is never hidden by a missing feature)", () => {
    render(<Reveal>hello</Reveal>);
    expect(screen.getByText("hello")).toHaveClass("is-visible");
  });

  it("starts hidden and reveals once it scrolls into view, then stays revealed", () => {
    let trigger: (intersecting: boolean) => void = () => {};
    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: (entries: { isIntersecting: boolean }[]) => void) {
          trigger = (isIntersecting) => callback([{ isIntersecting }]);
        }
        observe() {}
        disconnect() {}
      },
    );

    render(
      <Reveal delay={120} direction="left">
        card
      </Reveal>,
    );
    const node = screen.getByText("card");
    expect(node).not.toHaveClass("is-visible");
    expect(node).toHaveClass("reveal", "reveal-left");
    expect(node.style.getPropertyValue("--reveal-delay")).toBe("120ms");

    act(() => trigger(true));
    expect(node).toHaveClass("is-visible");
    act(() => trigger(false));
    expect(node).toHaveClass("is-visible"); // latched: it doesn't hide again on scroll-out
  });

  it("renders as the requested element", () => {
    render(
      <ul>
        <Reveal as="li">item</Reveal>
      </ul>,
    );
    expect(screen.getByRole("listitem")).toHaveTextContent("item");
  });
});
