import { useMemo } from "react";
import { createRandom } from "../lib/seededRandom";

export interface NetworkNode {
  x: number;
  y: number;
  r: number;
  accent: boolean;
}

export interface NetworkGraph {
  nodes: NetworkNode[];
  edges: [number, number][];
}

const WIDTH = 800;
const HEIGHT = 320;

/**
 * A deterministic little talent graph: scattered nodes, each joined to its
 * nearest neighbours (at most two links each, so it reads as a network and
 * not a hairball). One node in seven is the amber "human" accent.
 * Pure — the same seed always yields the same graph.
 */
export function buildNetwork(seed: number, count: number): NetworkGraph {
  const random = createRandom(seed);
  const nodes: NetworkNode[] = Array.from({ length: count }, (_, index) => ({
    x: 30 + random() * (WIDTH - 60),
    y: 24 + random() * (HEIGHT - 48),
    r: 1.6 + random() * 2.2,
    accent: index % 7 === 3,
  }));

  const edges: [number, number][] = [];
  const seen = new Set<string>();
  nodes.forEach((node, index) => {
    const nearest = nodes
      .map((other, otherIndex) => ({ otherIndex, distance: Math.hypot(node.x - other.x, node.y - other.y) }))
      .filter((candidate) => candidate.otherIndex !== index && candidate.distance < 150)
      .sort((a, b) => a.distance - b.distance)
      .slice(0, 2);
    for (const { otherIndex } of nearest) {
      const key = index < otherIndex ? `${index}-${otherIndex}` : `${otherIndex}-${index}`;
      if (!seen.has(key)) {
        seen.add(key);
        edges.push([index, otherIndex]);
      }
    }
  });
  return { nodes, edges };
}

/**
 * Ambient network artwork for headers and panels. Pure SVG + CSS: it drifts
 * very slowly on the compositor (one transform), a few nodes breathe, and it
 * is fully static under reduced motion. Decorative only — hidden from
 * assistive tech and never interactive.
 */
export function NetworkBackdrop({
  seed = 7,
  count = 30,
  className = "",
}: {
  seed?: number;
  count?: number;
  className?: string;
}) {
  const { nodes, edges } = useMemo(() => buildNetwork(seed, count), [seed, count]);

  return (
    <svg
      className={`network-backdrop ${className}`.trim()}
      viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
      preserveAspectRatio="xMidYMid slice"
      aria-hidden="true"
      focusable="false"
    >
      <g className="network-drift">
        {edges.map(([from, to]) => (
          <line
            key={`${from}-${to}`}
            x1={nodes[from].x}
            y1={nodes[from].y}
            x2={nodes[to].x}
            y2={nodes[to].y}
            className="network-edge"
          />
        ))}
        {nodes.map((node, index) => (
          <circle
            key={index}
            cx={node.x}
            cy={node.y}
            r={node.r}
            className={node.accent ? "network-node network-node-accent" : "network-node"}
            style={index % 5 === 0 ? { animationDelay: `${(index % 9) * 0.7}s` } : undefined}
          />
        ))}
      </g>
    </svg>
  );
}
