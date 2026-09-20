import { render } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { buildNetwork, NetworkBackdrop } from "./NetworkBackdrop";

describe("buildNetwork", () => {
  it("is deterministic for a seed and varies between seeds", () => {
    expect(buildNetwork(7, 30)).toEqual(buildNetwork(7, 30));
    expect(buildNetwork(8, 30).nodes).not.toEqual(buildNetwork(7, 30).nodes);
  });

  it("makes a network, not a hairball: no duplicate or self edges, and it stays sparse", () => {
    const { nodes, edges } = buildNetwork(3, 40);
    expect(nodes).toHaveLength(40);
    const keys = new Set<string>();
    for (const [a, b] of edges) {
      expect(a).not.toBe(b);
      const key = a < b ? `${a}-${b}` : `${b}-${a}`;
      expect(keys.has(key)).toBe(false);
      keys.add(key);
    }
    // each node initiates at most two links
    expect(edges.length).toBeLessThanOrEqual(nodes.length * 2);
  });

  it("marks about one node in seven as the amber accent", () => {
    const { nodes } = buildNetwork(1, 28);
    expect(nodes.filter((node) => node.accent)).toHaveLength(4);
  });
});

describe("NetworkBackdrop", () => {
  it("is purely decorative: hidden from assistive tech and not focusable", () => {
    const { container } = render(<NetworkBackdrop />);
    const svg = container.querySelector("svg");
    expect(svg).toHaveAttribute("aria-hidden", "true");
    expect(svg).toHaveAttribute("focusable", "false");
    expect(container.querySelectorAll("circle").length).toBe(30);
  });
});
