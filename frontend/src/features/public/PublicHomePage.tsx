import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { listOpenJobs } from "../careers/api";
import { useReveal } from "../../shared/hooks/useReveal";
import { ThemeToggle } from "../theme/ThemeToggle";

/** The one organization this deployment actually serves — the public home
 * page is SIGVITAS' own careers site, not a generic multi-tenant landing
 * page (SIGVITAS platform overhaul § 1). The underlying platform stays
 * multi-tenant-capable; only this page's copy and framing changes. */
const SIGVITAS_SLUG = "sigvitas";

function Reveal({ children, className = "" }: { children: ReactNode; className?: string }) {
  const { ref, isVisible } = useReveal<HTMLDivElement>();
  return (
    <div ref={ref} className={`reveal ${isVisible ? "is-visible" : ""} ${className}`.trim()}>
      {children}
    </div>
  );
}

const HIRING_STEPS: { title: string; description: string }[] = [
  { title: "Explore openings", description: "Browse current roles across engineering, design, and more." },
  { title: "Apply", description: "Submit your application and resume — no account required." },
  { title: "Resume review", description: "Our team reviews your background against the role." },
  { title: "Screening", description: "An initial pass — assisted by AI, always reviewed by a recruiter." },
  { title: "Assessment", description: "Some roles include a short skills assessment before the next round." },
  { title: "Interview", description: "Meet the team and talk through the role in more depth." },
  { title: "Decision", description: "We follow up either way, as soon as we can." },
];

export function PublicHomePage() {
  const openJobsQuery = useQuery({
    queryKey: ["public", "jobs", SIGVITAS_SLUG, "preview"],
    queryFn: () => listOpenJobs(SIGVITAS_SLUG),
  });
  const openJobs = (openJobsQuery.data ?? []).slice(0, 4);

  return (
    <div className="landing">
      <header className="public-nav landing-nav">
        <span className="topbar-title landing-brand">SIGVITAS</span>
        <nav className="landing-nav-links">
          <a href="#openings">Openings</a>
          <a href="#campus">Campus</a>
          <a href="#process">Hiring Process</a>
        </nav>
        <div className="landing-nav-actions">
          <ThemeToggle />
          <Link to="/recruiter/login" className="btn btn-ghost btn-sm">
            Staff sign in
          </Link>
        </div>
      </header>

      <section className="landing-hero">
        <div className="landing-hero-copy">
          <p className="eyebrow">SIGVITAS Careers</p>
          <h2 className="landing-hero-headline">Build what's next, with SIGVITAS.</h2>
          <p className="landing-hero-sub">
            Explore open roles, campus opportunities, and what it's actually like to work here —
            then apply in minutes.
          </p>
          <div className="landing-hero-actions">
            <Link to={`/org/${SIGVITAS_SLUG}`} className="btn btn-primary btn-lg">
              Explore Open Roles
            </Link>
            <a href="#campus" className="btn btn-ghost btn-lg">
              Campus Opportunities
            </a>
          </div>
        </div>
        <div className="landing-hero-visual" aria-hidden="true">
          <div className="landing-mock-window">
            <div className="landing-mock-titlebar">
              <span />
              <span />
              <span />
            </div>
            <div className="landing-mock-stats">
              <div className="landing-mock-stat" />
              <div className="landing-mock-stat" />
              <div className="landing-mock-stat" />
            </div>
            <div className="landing-mock-bars">
              <div className="landing-mock-bar" style={{ height: "40%" }} />
              <div className="landing-mock-bar" style={{ height: "70%" }} />
              <div className="landing-mock-bar" style={{ height: "55%" }} />
              <div className="landing-mock-bar" style={{ height: "90%" }} />
              <div className="landing-mock-bar" style={{ height: "65%" }} />
            </div>
          </div>
        </div>
      </section>

      <section id="openings" className="landing-section">
        <Reveal>
          <h2 className="landing-section-title">Current Openings</h2>
          <p className="landing-section-sub muted">
            A sample of what's open right now — see every role on our careers page.
          </p>
        </Reveal>
        <div className="landing-feature-grid landing-feature-grid-3">
          {openJobsQuery.isPending && (
            <Reveal className="landing-feature-card">
              <p className="muted">Loading current openings…</p>
            </Reveal>
          )}
          {openJobsQuery.isSuccess && openJobs.length === 0 && (
            <Reveal className="landing-feature-card">
              <p className="muted">No open roles right now — check back soon.</p>
            </Reveal>
          )}
          {openJobs.map((job) => (
            <Reveal key={job.id} className="landing-feature-card">
              <h3>{job.title}</h3>
              <p className="muted">
                {[job.department, job.location].filter(Boolean).join(" · ") || "SIGVITAS"}
              </p>
              <Link to={`/org/${SIGVITAS_SLUG}/jobs/${job.id}`} className="btn btn-ghost btn-sm">
                View role
              </Link>
            </Reveal>
          ))}
        </div>
        <div style={{ marginTop: "1.5rem" }}>
          <Link to={`/org/${SIGVITAS_SLUG}`} className="btn btn-primary">
            See all open roles
          </Link>
        </div>
      </section>

      <section id="process" className="landing-section landing-section-alt">
        <Reveal>
          <h2 className="landing-section-title">Our hiring process</h2>
          <p className="landing-section-sub muted">
            One clear path, whether you're applying directly or through a campus drive.
          </p>
        </Reveal>
        <div className="landing-workflow">
          {HIRING_STEPS.map((step, index) => (
            <Reveal key={step.title} className="landing-workflow-step">
              <span className="landing-workflow-index">{index + 1}</span>
              <div>
                <h3>{step.title}</h3>
                <p className="muted">{step.description}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      <section id="ai" className="landing-section">
        <Reveal className="landing-split">
          <div>
            <p className="eyebrow">How we review applications</p>
            <h2 className="landing-section-title">AI assists our recruiters. It never decides.</h2>
            <p className="muted">
              We use AI to help our team get through applications faster — surfacing signal for a
              recruiter to review, never making a hiring decision on its own. Every screening result
              stays traceable back to your application, and a person always makes the call.
            </p>
          </div>
          <ul className="landing-checklist">
            <li>Recruiter-assistive, never autonomous</li>
            <li>Your data stays tied to your application</li>
            <li>A person reviews every step that matters</li>
            <li>Assessment monitoring is disclosed upfront, never hidden</li>
          </ul>
        </Reveal>
      </section>

      <section id="campus" className="landing-section landing-section-alt">
        <Reveal>
          <h2 className="landing-section-title">Campus hiring</h2>
          <p className="landing-section-sub muted">
            SIGVITAS runs dedicated campus drives with colleges — watch for a drive link shared by
            your placement office, or check back here for upcoming opportunities.
          </p>
        </Reveal>
        <div className="landing-feature-grid landing-feature-grid-3">
          <Reveal className="landing-feature-card">
            <h3>Apply with a drive link</h3>
            <p className="muted">
              If your college is running a SIGVITAS drive, you'll get a direct application link —
              no account needed.
            </p>
          </Reveal>
          <Reveal className="landing-feature-card">
            <h3>Same hiring process</h3>
            <p className="muted">
              Campus applications go through the same review and assessment process as any other
              application.
            </p>
          </Reveal>
          <Reveal className="landing-feature-card">
            <h3>Clear updates</h3>
            <p className="muted">
              You'll hear from us at each step — and if a drive has closed, we'll let you know
              rather than leave you guessing.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="landing-final-cta">
        <Reveal>
          <h2>Ready to apply?</h2>
          <p className="muted">Explore open roles at SIGVITAS and submit your application today.</p>
          <div className="landing-hero-actions">
            <Link to={`/org/${SIGVITAS_SLUG}`} className="btn btn-primary btn-lg">
              Explore Open Roles
            </Link>
          </div>
        </Reveal>
      </section>

      <footer className="landing-footer">
        <span>SIGVITAS Careers</span>
        <nav className="landing-footer-links">
          <Link to={`/org/${SIGVITAS_SLUG}`}>Open roles</Link>
          <Link to="/recruiter/login">Staff sign in</Link>
        </nav>
        <span className="muted">&copy; {new Date().getFullYear()} SIGVITAS</span>
      </footer>
    </div>
  );
}
