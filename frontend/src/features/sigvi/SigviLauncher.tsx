import { forwardRef, useEffect, useState } from "react";
import { useReducedMotion } from "../../shared/hooks/useReducedMotion";
import { SigviMascot } from "./SigviMascot";

/** How often the resting launcher stirs again. */
const WAKE_EVERY_MS = 60_000;

/** A tiny constellation around the mascot — the same "talent graph" motif as
 * the hero's network, so Sigvi reads as part of the SIGVITAS site rather than
 * something floating over it. One SVG, one slow rotation. */
function OrbNetwork() {
  const nodes: [number, number][] = [
    [50, 4],
    [92, 34],
    [78, 88],
    [22, 86],
    [6, 32],
  ];
  return (
    <svg className="sigvi-orb-net" viewBox="0 0 100 100" aria-hidden="true" focusable="false">
      <path
        d={`M${nodes.map(([x, y]) => `${x} ${y}`).join(" L")} Z`}
        fill="none"
        stroke="currentColor"
        strokeOpacity="0.22"
        strokeWidth="0.7"
      />
      {nodes.map(([x, y], index) => (
        <circle
          key={index}
          className="sigvi-orb-node"
          cx={x}
          cy={y}
          r={index % 2 ? 1.7 : 2.3}
        />
      ))}
    </svg>
  );
}

/** The floating launcher: a glowing robot orb with a label beside it. */
export const SigviLauncher = forwardRef<
  HTMLButtonElement,
  { open: boolean; onOpen: () => void }
>(function SigviLauncher({ open, onOpen }, ref) {
  // The launcher animates for a few seconds and then rests (styles/sigvi.css —
  // an animation that runs forever keeps the whole page rendering). Once a
  // minute, while it is on show, the orb is remounted so its finite animations
  // play once more: a small sign of life, at almost no cost.
  const reducedMotion = useReducedMotion();
  const [wake, setWake] = useState(0);
  useEffect(() => {
    if (open || reducedMotion) return;
    const timer = window.setInterval(() => {
      if (!document.hidden) setWake((count) => count + 1);
    }, WAKE_EVERY_MS);
    return () => window.clearInterval(timer);
  }, [open, reducedMotion]);

  return (
    <button
      ref={ref}
      type="button"
      className="sigvi-launcher"
      aria-label="Ask Sigvi, the AI assistant"
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls="sigvi-panel"
      aria-hidden={open}
      inert={open}
      onClick={onOpen}
    >
      <span className="sigvi-orb" key={wake}>
        <OrbNetwork />
        <span className="sigvi-orb-ring" aria-hidden="true" />
        <SigviMascot size={46} variant="head" />
      </span>
      <span className="sigvi-launcher-text">
        <span className="sigvi-launcher-label">Ask Sigvi</span>
        <span className="sigvi-launcher-sub">AI assistant</span>
      </span>
    </button>
  );
});
