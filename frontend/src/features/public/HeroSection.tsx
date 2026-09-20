import { useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../../shared/components/Icon";
import { Magnetic } from "../../shared/components/Magnetic";
import { HeroScene } from "./hero/HeroScene";
import { NODE_KINDS, type NodeKind } from "./hero/networkLayout";

/**
 * The public hero. Left: the message and the two ways in. Behind and to the
 * right: the recruitment-intelligence network. Below: a legend that says what
 * the network *is* — hovering (or focusing, or pressing) a category lights it
 * up in the scene — so the visual explains the product instead of decorating
 * the page.
 */
export function HeroSection({
  careersPath,
  openRoleCount,
}: {
  careersPath: string;
  /** Live count from the jobs API; omitted while loading or when zero. */
  openRoleCount: number | null;
}) {
  const [hovered, setHovered] = useState<NodeKind | null>(null);
  const [pinned, setPinned] = useState<NodeKind | null>(null);
  const highlight = hovered ?? pinned;

  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-stage" aria-hidden="true" />
      <HeroScene highlight={highlight} />

      <div className="hero-inner">
        <div className="hero-copy">
          <p className="eyebrow hero-eyebrow">SIGVITAS Careers</p>
          <h1 id="hero-title" className="hero-title">
            Build what's next,
            <span className="hero-accent"> with SIGVITAS.</span>
          </h1>
          <p className="hero-sub">
            Explore open roles and campus opportunities, then apply in minutes. AI helps our
            recruiters review every application — a person always makes the decision.
          </p>

          <div className="hero-actions">
            <Magnetic>
              <Link to={careersPath} className="btn btn-primary btn-lg hero-cta">
                Explore Open Roles
                <Icon name="arrow-right" size={18} />
              </Link>
            </Magnetic>
            <a href="#process" className="btn btn-ghost btn-lg">
              How we hire
            </a>
          </div>

          <ul className="hero-proof" aria-label="At a glance">
            {openRoleCount !== null && openRoleCount > 0 && (
              <li className="hero-proof-live">
                <span className="live-dot" aria-hidden="true" />
                {openRoleCount} open {openRoleCount === 1 ? "role" : "roles"} right now
              </li>
            )}
            <li>No account needed to apply</li>
            <li>Every decision made by a person</li>
          </ul>
        </div>

        <div
          className="hero-legend"
          role="group"
          aria-label="What the network represents"
          onMouseLeave={() => setHovered(null)}
        >
          {NODE_KINDS.map(({ kind, label }) => (
            <button
              key={kind}
              type="button"
              className="legend-item"
              aria-pressed={pinned === kind}
              onMouseEnter={() => setHovered(kind)}
              onFocus={() => setHovered(kind)}
              onBlur={() => setHovered(null)}
              onClick={() => setPinned((current) => (current === kind ? null : kind))}
            >
              <span className="legend-swatch" data-kind={kind} aria-hidden="true" />
              {label}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
