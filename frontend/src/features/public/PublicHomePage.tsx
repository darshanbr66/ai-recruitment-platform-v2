import { Link } from "react-router-dom";
import { Icon, type IconName } from "../../shared/components/Icon";
import { Magnetic } from "../../shared/components/Magnetic";
import { NetworkBackdrop } from "../../shared/components/NetworkBackdrop";
import { Reveal } from "../../shared/components/Reveal";
import { HeroSection } from "./HeroSection";
import { LandingNav } from "./LandingNav";

/** The one organization this deployment actually serves — the public home
 * page is SIGVITAS' own website (SIGVITAS platform overhaul § 1). The
 * underlying platform stays multi-tenant-capable; only this page's copy and
 * framing changes. */
const SIGVITAS_SLUG = "sigvitas";

/**
 * Company-first content (first HR meeting: "the homepage is a company
 * website, not a job board"). Recruitment content — openings, the hiring
 * process, how applications are reviewed, campus drives — lives on the
 * Careers page, reached only when a visitor chooses it.
 *
 * Content owner: SIGVITAS HR/marketing. The copy below states values and
 * how the company works, never facts the company hasn't published
 * (history, size, offices, clients) — replace/extend it here with approved
 * company content.
 */
const ABOUT_PARAGRAPHS = [
  "SIGVITAS is built on a simple idea: great work comes from capable people, thoughtful technology and a culture that lets both grow.",
  "We take on problems with care, stay close to the people we work with, and hold ourselves to a high standard in everything we deliver.",
];

const VALUES: { icon: IconName; title: string; text: string }[] = [
  {
    icon: "user",
    title: "People first",
    text: "Our people and the people we work with come first — in how we plan, build and decide.",
  },
  {
    icon: "sparkles",
    title: "Craft and quality",
    text: "We care about the details, and we take pride in work that is done properly.",
  },
  {
    icon: "shield",
    title: "Integrity",
    text: "We are honest about what we do, open about how we do it, and careful with trust.",
  },
  {
    icon: "graph",
    title: "Always learning",
    text: "We grow by learning continuously — from our work, from each other and from new ideas.",
  },
];

export function PublicHomePage() {
  const careersPath = `/org/${SIGVITAS_SLUG}`;

  return (
    <div className="landing">
      <LandingNav careersPath={careersPath} />

      <HeroSection careersPath={careersPath} />

      <section id="about" className="landing-section">
        <Reveal>
          <p className="section-eyebrow">About us</p>
          <h2 className="landing-section-title">Who we are</h2>
          {ABOUT_PARAGRAPHS.map((paragraph) => (
            <p key={paragraph} className="landing-section-sub">
              {paragraph}
            </p>
          ))}
        </Reveal>
      </section>

      <section id="values" className="landing-section landing-section-alt">
        <Reveal>
          <p className="section-eyebrow">What drives us</p>
          <h2 className="landing-section-title">Our values</h2>
          <p className="landing-section-sub">The principles behind how we work, every day.</p>
        </Reveal>
        <div className="principle-grid">
          {VALUES.map((item, index) => (
            <Reveal key={item.title} className="principle-card" delay={index * 70}>
              <span className="principle-icon">
                <Icon name={item.icon} size={20} />
              </span>
              <h3>{item.title}</h3>
              <p>{item.text}</p>
            </Reveal>
          ))}
        </div>
      </section>

      <section className="landing-final-cta">
        <NetworkBackdrop seed={11} count={26} />
        <Reveal className="landing-final-inner">
          <h2>Grow with SIGVITAS</h2>
          <p>Interested in building your career with us? Visit our careers page to learn more.</p>
          <Magnetic>
            <Link to={careersPath} className="btn btn-primary btn-lg">
              Careers at SIGVITAS
              <Icon name="arrow-right" size={18} />
            </Link>
          </Magnetic>
        </Reveal>
      </section>

      <footer className="landing-footer">
        <span>SIGVITAS</span>
        <nav className="landing-footer-links" aria-label="Footer">
          <a href="#about">About</a>
          <Link to={careersPath}>Careers</Link>
          <Link to="/recruiter/login">Staff sign in</Link>
        </nav>
        <span className="muted">&copy; {new Date().getFullYear()} SIGVITAS</span>
      </footer>
    </div>
  );
}
