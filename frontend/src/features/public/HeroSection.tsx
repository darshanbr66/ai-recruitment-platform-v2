import { useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "../../shared/components/Icon";
import { Magnetic } from "../../shared/components/Magnetic";
import { HeroScene } from "./hero/HeroScene";
import { NODE_KINDS, type NodeKind } from "./hero/networkLayout";

/**
 * The public hero. Left: the company message and the two ways in (learn about
 * the company, or deliberately choose Careers). Behind and to the right: the
 * network visual. Below: a legend that says what
 * the network *is* — hovering (or focusing, or pressing) a category lights it
 * up in the scene — so the visual explains the product instead of decorating
 * the page.
 */
export function HeroSection({ careersPath }: { careersPath: string }) {
  const [hovered, setHovered] = useState<NodeKind | null>(null);
  const [pinned, setPinned] = useState<NodeKind | null>(null);
  const highlight = hovered ?? pinned;

  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="hero-stage" aria-hidden="true" />
      <HeroScene highlight={highlight} />

      <div className="hero-inner">
        <div className="hero-copy">
          <p className="eyebrow hero-eyebrow">SIGVITAS</p>
          <h1 id="hero-title" className="hero-title">
            Build what's next,
            <span className="hero-accent"> with SIGVITAS.</span>
          </h1>
          <p className="hero-sub">
            People, technology and a culture built to grow both. Get to know SIGVITAS — who we
            are, what we value, and how we work.
          </p>

          <div className="hero-actions">
            <Magnetic>
              <a href="#about" className="btn btn-primary btn-lg hero-cta">
                About SIGVITAS
                <Icon name="arrow-right" size={18} />
              </a>
            </Magnetic>
            <Link to={careersPath} className="btn btn-ghost btn-lg">
              Careers
            </Link>
          </div>
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
