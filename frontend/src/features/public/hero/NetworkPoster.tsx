import { useMemo } from "react";
import { buildNetworkLayout, type LayoutDensity, type NodeKind } from "./networkLayout";

interface Projected {
  x: number;
  y: number;
  depth: number;
}

/** Euler XYZ (three.js order) applied to a point, then a gentle perspective
 * squeeze — enough to make a flat SVG read as orbits seen from slightly above. */
function project(tilt: [number, number, number], point: [number, number, number]): Projected {
  const [ax, ay, az] = tilt;
  let [x, y, z] = point;
  // Rz
  [x, y] = [x * Math.cos(az) - y * Math.sin(az), x * Math.sin(az) + y * Math.cos(az)];
  // Ry
  [x, z] = [x * Math.cos(ay) + z * Math.sin(ay), -x * Math.sin(ay) + z * Math.cos(ay)];
  // Rx
  [y, z] = [y * Math.cos(ax) - z * Math.sin(ax), y * Math.sin(ax) + z * Math.cos(ax)];
  // the scene is viewed from a touch above
  const view = 0.12;
  [y, z] = [y * Math.cos(view) - z * Math.sin(view), y * Math.sin(view) + z * Math.cos(view)];
  const perspective = 1 / (1 - z / 22);
  return { x: x * perspective, y: -y * perspective, depth: z };
}

const HEX = Array.from({ length: 6 }, (_, i) => [Math.cos((i / 6) * Math.PI * 2), Math.sin((i / 6) * Math.PI * 2)]);

/**
 * A static rendering of the recruitment-intelligence network: the WebGL
 * scene's exact layout, drawn as flat SVG. It is what shows while the 3D
 * scene loads, for anyone who prefers reduced motion, on devices without
 * WebGL, and if the GPU context is ever lost — the same picture in every case,
 * only without depth-of-field and movement.
 */
export function NetworkPoster({
  density = "full",
  highlight = null,
}: {
  density?: LayoutDensity;
  highlight?: NodeKind | null;
}) {
  const layout = useMemo(() => buildNetworkLayout({ density }), [density]);

  const scene = useMemo(() => {
    const rings = layout.orbits
      .filter((orbit) => orbit.kinds[0] !== "ai")
      .map((orbit) => {
        const points = Array.from({ length: 96 }, (_, i) => {
          const a = (i / 96) * Math.PI * 2;
          return project(orbit.tilt, [Math.cos(a) * orbit.radius, 0, Math.sin(a) * orbit.radius]);
        });
        return { kind: orbit.kinds[0], d: points.map((p, i) => `${i ? "L" : "M"}${p.x.toFixed(3)} ${p.y.toFixed(3)}`).join("") + "Z" };
      });

    const nodes = layout.nodes.map((node) => {
      const tilt = layout.orbits[node.orbit].tilt;
      return {
        ...node,
        ...project(tilt, [Math.cos(node.angle) * node.radius, node.height, Math.sin(node.angle) * node.radius]),
      };
    });
    return { rings, nodes };
  }, [layout]);

  const { rings, nodes } = scene;
  const particles = useMemo(() => {
    const out: { x: number; y: number }[] = [];
    for (let i = 0; i < layout.particles.length; i += 3 * 3) {
      out.push({ x: layout.particles[i] * 0.95, y: -layout.particles[i + 1] * 1.05 });
    }
    return out;
  }, [layout]);

  return (
    <svg
      className="network-poster"
      viewBox="-5.4 -4.4 10.8 8.8"
      preserveAspectRatio="xMidYMid meet"
      aria-hidden="true"
      focusable="false"
      data-highlight={highlight ?? undefined}
    >
      <defs>
        <radialGradient id="poster-core-glow">
          <stop offset="0%" stopColor="var(--kind-ai)" stopOpacity="0.55" />
          <stop offset="100%" stopColor="var(--kind-ai)" stopOpacity="0" />
        </radialGradient>
      </defs>

      {particles.map((particle, i) => (
        <circle key={i} cx={particle.x} cy={particle.y} r={0.028} className="poster-particle" />
      ))}

      {rings.map((ring) => (
        <path key={ring.kind} d={ring.d} className="poster-ring" style={{ stroke: `var(--kind-${ring.kind})` }} />
      ))}

      {layout.spokes.map((index) => (
        <line key={`s${index}`} x1={0} y1={0} x2={nodes[index].x} y2={nodes[index].y} className="poster-link" />
      ))}
      {layout.links.map(([from, to]) => (
        <line key={`l${from}-${to}`} x1={nodes[from].x} y1={nodes[from].y} x2={nodes[to].x} y2={nodes[to].y} className="poster-link" />
      ))}
      {layout.matches.map(([candidate, job]) => (
        <line
          key={`m${candidate}-${job}`}
          x1={nodes[candidate].x}
          y1={nodes[candidate].y}
          x2={nodes[job].x}
          y2={nodes[job].y}
          className="poster-match"
        />
      ))}

      <g className="poster-core" data-kind="ai">
        <circle r={2.1} fill="url(#poster-core-glow)" />
        <circle r={0.98} className="poster-core-wire" />
        <polygon
          points={HEX.map(([x, y]) => `${(x * 0.6).toFixed(3)},${(y * 0.6).toFixed(3)}`).join(" ")}
          className="poster-core-body"
        />
      </g>

      {[...nodes]
        .sort((a, b) => a.depth - b.depth)
        .map((node, i) => {
          const scale = 1 + node.depth * 0.045;
          const r = node.size * 1.5 * scale;
          const opacity = Math.min(1, Math.max(0.35, 0.72 + node.depth * 0.07));
          const common = {
            className: "poster-node",
            "data-kind": node.kind,
            "data-matched": node.matched || undefined,
            style: { opacity },
          } as const;
          switch (node.kind) {
            case "job":
              return <rect key={i} x={node.x - r} y={node.y - r} width={r * 2} height={r * 2} transform={`rotate(45 ${node.x} ${node.y})`} {...common} />;
            case "assessment":
              return <rect key={i} x={node.x - r} y={node.y - r} width={r * 2} height={r * 2} rx={r * 0.25} {...common} />;
            case "organization":
              return (
                <polygon
                  key={i}
                  points={HEX.map(([x, y]) => `${(node.x + x * r * 1.1).toFixed(3)},${(node.y + y * r * 1.1).toFixed(3)}`).join(" ")}
                  {...common}
                />
              );
            default:
              return <circle key={i} cx={node.x} cy={node.y} r={r} {...common} />;
          }
        })}
    </svg>
  );
}
