import { describe, expect, it } from "vitest";
import { buildNetworkLayout, NODE_KINDS } from "./networkLayout";

describe("buildNetworkLayout", () => {
  it("is deterministic: the same seed always yields the same network", () => {
    const a = buildNetworkLayout({ seed: 42 });
    const b = buildNetworkLayout({ seed: 42 });
    expect(a.nodes).toEqual(b.nodes);
    expect(a.links).toEqual(b.links);
    expect(a.matches).toEqual(b.matches);
    expect(Array.from(a.particles)).toEqual(Array.from(b.particles));
    expect(buildNetworkLayout({ seed: 43 }).nodes).not.toEqual(a.nodes);
  });

  it("represents every category the legend names, on the right orbits", () => {
    const layout = buildNetworkLayout();
    const kinds = new Set(layout.nodes.map((node) => node.kind));
    for (const { kind } of NODE_KINDS) expect(kinds.has(kind)).toBe(true);

    const orbitsOf = (kind: string) => new Set(layout.nodes.filter((n) => n.kind === kind).map((n) => n.orbit));
    // each of these categories lives on a single, dedicated orbit
    for (const kind of ["skill", "job", "candidate", "ai"]) expect(orbitsOf(kind).size).toBe(1);
    // assessments and organizations share the outer ring
    expect(orbitsOf("assessment")).toEqual(orbitsOf("organization"));
  });

  it("has fewer nodes and particles in the reduced (phone/tablet) density", () => {
    const full = buildNetworkLayout({ density: "full" });
    const reduced = buildNetworkLayout({ density: "reduced" });
    expect(reduced.nodes.length).toBeLessThan(full.nodes.length);
    expect(reduced.particles.length).toBeLessThan(full.particles.length);
    expect(reduced.matches.length).toBeLessThanOrEqual(full.matches.length);
    // ...but the concept survives: every category is still there
    for (const { kind } of NODE_KINDS) expect(reduced.nodes.some((n) => n.kind === kind)).toBe(true);
  });

  it("only references nodes that exist, and joins nodes that share an orbit", () => {
    const { nodes, links, spokes, matches } = buildNetworkLayout();
    const valid = (index: number) => Number.isInteger(index) && index >= 0 && index < nodes.length;

    for (const [from, to] of links) {
      expect(valid(from) && valid(to)).toBe(true);
      // links are static in an orbit's local space, so both ends must rotate together
      expect(nodes[from].orbit).toBe(nodes[to].orbit);
    }
    for (const spoke of spokes) expect(valid(spoke)).toBe(true);
    for (const [candidate, job] of matches) {
      expect(nodes[candidate].kind).toBe("candidate");
      expect(nodes[job].kind).toBe("job");
    }
  });

  it("marks exactly the matched candidates, one per match beam", () => {
    const { nodes, matches } = buildNetworkLayout();
    const matched = nodes.filter((node) => node.matched);
    expect(matched.length).toBe(matches.length);
    expect(matched.every((node) => node.kind === "candidate")).toBe(true);
    expect(new Set(matches.map(([candidate]) => candidate)).size).toBe(matches.length);
  });

  it("keeps everything inside the scene volume", () => {
    const { nodes, particles } = buildNetworkLayout();
    for (const node of nodes) {
      expect(node.radius).toBeGreaterThan(0.5);
      expect(node.radius).toBeLessThan(4.6);
      expect(Math.abs(node.height)).toBeLessThan(0.5);
    }
    expect(particles.length % 3).toBe(0);
    for (let i = 0; i < particles.length; i += 3) {
      const distance = Math.hypot(particles[i], particles[i + 1], particles[i + 2]);
      expect(distance).toBeLessThan(10.5);
    }
  });
});
