import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LogoMark } from "../../shared/components/Icon";
import { ThemeToggle } from "../theme/ThemeToggle";

/**
 * Floating navigation for the public home page. Transparent over the hero
 * (so the 3D stage reads edge to edge), it settles into a frosted bar once
 * the page has scrolled — a state change the user can see, not decoration.
 */
export function LandingNav() {
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header className={`landing-nav${scrolled ? " is-scrolled" : ""}`}>
      <Link to="/" className="landing-brand" aria-label="SIGVITAS home">
        <LogoMark size={30} />
        <span className="landing-brand-name">SIGVITAS</span>
      </Link>
      <nav className="landing-nav-links" aria-label="Sections">
        <a href="#openings">Openings</a>
        <a href="#process">Hiring Process</a>
        <a href="#campus">Campus</a>
      </nav>
      <div className="landing-nav-actions">
        <ThemeToggle />
        <Link to="/recruiter/login" className="btn btn-ghost btn-sm">
          Staff sign in
        </Link>
      </div>
    </header>
  );
}
