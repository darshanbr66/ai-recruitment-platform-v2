import { createRandom } from "../../../shared/lib/seededRandom";

/**
 * The recruitment-intelligence network, as pure data. Both renderers — the
 * WebGL scene (network3d.ts) and the static SVG poster (NetworkPoster.tsx) —
 * are drawn from this one layout, so the fallback is the *same* picture, not
 * a different illustration.
 *
 * The metaphor: an AI core (the analysis) with orbital rings around it.
 * Skills orbit close, jobs further out, candidates on the widest working
 * ring, and assessments and organizations at the perimeter. A few
 * candidate–job pairs are "matched" — those are the connections a recruiter
 * reviews.
 */

export type NodeKind = "candidate" | "job" | "skill" | "assessment" | "organization" | "ai";

export const NODE_KINDS: { kind: NodeKind; label: string }[] = [
  { kind: "candidate", label: "Candidates" },
  { kind: "job", label: "Jobs" },
  { kind: "skill", label: "Skills" },
  { kind: "assessment", label: "Assessments" },
  { kind: "organization", label: "Organizations" },
  { kind: "ai", label: "AI analysis" },
];

export interface OrbitSpec {
  radius: number;
  /** Euler tilt (radians, x/y/z) of the orbital plane. */
  tilt: [number, number, number];
  /** Radians per second about the orbit's own axis; negative = counter-clockwise. */
  speed: number;
  kinds: NodeKind[];
}

export interface NetworkNode {
  kind: NodeKind;
  orbit: number;
  /** Position on the orbit, in that orbit's local (untilted) plane. */
  angle: number;
  radius: number;
  height: number;
  size: number;
  /** A candidate a recruiter has a match beam to. */
  matched: boolean;
}

export interface NetworkLayout {
  orbits: OrbitSpec[];
  nodes: NetworkNode[];
  /** Edges between nodes on the same orbit (they rotate together, so they are static). */
  links: [number, number][];
  /** Nodes joined straight to the core. */
  spokes: number[];
  /** [candidate node index, job node index] pairs drawn as live match beams. */
  matches: [number, number][];
  /** Flat xyz triples for the ambient particle field. */
  particles: Float32Array;
}

export type LayoutDensity = "full" | "reduced";

const ORBITS: OrbitSpec[] = [
  { radius: 1.75, tilt: [0.55, 0, 0.15], speed: 0.22, kinds: ["skill"] },
  { radius: 2.55, tilt: [-0.4, 0, 0.55], speed: -0.15, kinds: ["job"] },
  { radius: 3.35, tilt: [1.0, 0, -0.25], speed: 0.11, kinds: ["candidate"] },
  { radius: 4.15, tilt: [-0.2, 0, -0.75], speed: -0.075, kinds: ["assessment", "organization"] },
  { radius: 1.05, tilt: [0.2, 0, 0], speed: 0.6, kinds: ["ai"] },
];

const COUNTS: Record<LayoutDensity, Record<NodeKind, number>> = {
  full: { skill: 8, job: 5, candidate: 12, assessment: 3, organization: 2, ai: 3 },
  reduced: { skill: 5, job: 4, candidate: 8, assessment: 2, organization: 2, ai: 3 },
};

const SIZES: Record<NodeKind, number> = {
  candidate: 0.1,
  job: 0.15,
  skill: 0.06,
  assessment: 0.12,
  organization: 0.15,
  ai: 0.1,
};

const PARTICLES: Record<LayoutDensity, number> = { full: 260, reduced: 100 };
const MATCHES: Record<LayoutDensity, number> = { full: 3, reduced: 2 };

export function buildNetworkLayout({
  density = "full",
  seed = 20260920,
}: { density?: LayoutDensity; seed?: number } = {}): NetworkLayout {
  const random = createRandom(seed);
  const counts = COUNTS[density];
  const nodes: NetworkNode[] = [];
  const indexByOrbit: number[][] = ORBITS.map(() => []);

  ORBITS.forEach((orbit, orbitIndex) => {
    // Orbits that host several kinds interleave them around the ring.
    const total = orbit.kinds.reduce((sum, kind) => sum + counts[kind], 0);
    const sequence: NodeKind[] = [];
    const remaining = orbit.kinds.map((kind) => counts[kind]);
    for (let slot = 0; slot < total; slot++) {
      let pick = slot % orbit.kinds.length;
      if (remaining[pick] === 0) pick = remaining.findIndex((n) => n > 0);
      remaining[pick]--;
      sequence.push(orbit.kinds[pick]);
    }

    const phase = random() * Math.PI * 2;
    sequence.forEach((kind, slot) => {
      const index = nodes.length;
      nodes.push({
        kind,
        orbit: orbitIndex,
        angle: phase + (slot / total) * Math.PI * 2 + (random() - 0.5) * 0.28,
        radius: orbit.radius + (random() - 0.5) * 0.24,
        height: (random() - 0.5) * 0.5,
        size: SIZES[kind] * (0.85 + random() * 0.35),
        matched: false,
      });
      indexByOrbit[orbitIndex].push(index);
    });
  });

  // Ring "necklaces": neighbours of the same kind on an orbit are linked.
  const links: [number, number][] = [];
  for (const members of indexByOrbit) {
    for (let i = 0; i < members.length; i++) {
      const from = members[i];
      const to = members[(i + 1) % members.length];
      if (from !== to && nodes[from].kind === nodes[to].kind && members.length > 2) {
        links.push([from, to]);
      }
    }
  }

  // Spokes: every job, org and AI satellite reaches the core; a third of candidates too.
  const spokes = nodes
    .map((node, index) => ({ node, index }))
    .filter(({ node, index }) =>
      node.kind === "job" || node.kind === "organization" || node.kind === "ai" || (node.kind === "candidate" && index % 3 === 0),
    )
    .map(({ index }) => index);

  // Match beams: distinct candidates paired with jobs across orbits.
  const candidates = nodes.map((n, i) => (n.kind === "candidate" ? i : -1)).filter((i) => i >= 0);
  const jobs = nodes.map((n, i) => (n.kind === "job" ? i : -1)).filter((i) => i >= 0);
  const matches: [number, number][] = [];
  const pairs = Math.min(MATCHES[density], candidates.length, jobs.length);
  for (let k = 0; k < pairs; k++) {
    const candidate = candidates[(k * 3 + 1) % candidates.length];
    const job = jobs[k % jobs.length];
    if (!nodes[candidate].matched) {
      nodes[candidate].matched = true;
      matches.push([candidate, job]);
    }
  }

  // Ambient particles: a thin, slightly flattened shell around the whole scene.
  const particleCount = PARTICLES[density];
  const particles = new Float32Array(particleCount * 3);
  for (let i = 0; i < particleCount; i++) {
    const theta = random() * Math.PI * 2;
    const phi = Math.acos(2 * random() - 1);
    const radius = 5.4 + random() * 4.6;
    particles[i * 3] = radius * Math.sin(phi) * Math.cos(theta);
    particles[i * 3 + 1] = radius * Math.cos(phi) * 0.62;
    particles[i * 3 + 2] = radius * Math.sin(phi) * Math.sin(theta);
  }

  return { orbits: ORBITS, nodes, links, spokes, matches, particles };
}
