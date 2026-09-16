import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useReveal } from "../../shared/hooks/useReveal";
import { ThemeToggle } from "../theme/ThemeToggle";

function Reveal({ children, className = "" }: { children: ReactNode; className?: string }) {
  const { ref, isVisible } = useReveal<HTMLDivElement>();
  return (
    <div ref={ref} className={`reveal ${isVisible ? "is-visible" : ""} ${className}`.trim()}>
      {children}
    </div>
  );
}

const FEATURES: { icon: string; title: string; description: string }[] = [
  {
    icon: "\u{1F4CB}",
    title: "Jobs & requisitions",
    description:
      "Create, edit, publish, put on hold, close, and reopen roles — nothing gets deleted, so your hiring history stays intact.",
  },
  {
    icon: "\u{1F465}",
    title: "Candidate pipeline",
    description: "A searchable, tenant-scoped candidate database with resumes and applications attached.",
  },
  {
    icon: "\u{1F916}",
    title: "AI-assisted screening",
    description:
      "Optional AI screening that assists recruiters — never replaces them. Works with your choice of provider, including free local models, and never fabricates a result.",
  },
  {
    icon: "\u{1F4DD}",
    title: "Assessments",
    description:
      "Import questions straight from a PDF, DOCX, XLSX, or CSV — preview, edit, and reorder before you publish an assessment.",
  },
  {
    icon: "\u{1F3EB}",
    title: "Campus drives",
    description:
      "Spin up a mass-hiring event with its own public application link — candidates apply with no login required.",
  },
  {
    icon: "\u{1F4CA}",
    title: "Reports & analytics",
    description: "A hiring funnel and breakdowns built entirely from your real data — no placeholder numbers.",
  },
];

const WORKFLOW_STEPS: { title: string; description: string }[] = [
  { title: "Post a job", description: "Define the role, openings, and requirements." },
  { title: "Candidates apply", description: "Via your career site or a dedicated campus drive link." },
  { title: "Resume parsed", description: "Structured candidate data extracted automatically." },
  { title: "AI-assisted screening", description: "An optional first pass that surfaces signal for recruiters." },
  { title: "Recruiter review", description: "Your team makes every screening and shortlisting call." },
  { title: "Assessment", description: "Send an optional skills assessment before the next round." },
  { title: "Interview & decision", description: "Move candidates through review to a final outcome." },
];

export function PublicHomePage() {
  return (
    <div className="landing">
      <header className="public-nav landing-nav">
        <h1 className="topbar-title landing-brand">AI Recruitment Platform</h1>
        <nav className="landing-nav-links">
          <a href="#features">Features</a>
          <a href="#workflow">Workflow</a>
          <a href="#ai">AI</a>
          <a href="#campus">Campus hiring</a>
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
          <p className="eyebrow">AI-powered recruitment platform</p>
          <h2 className="landing-hero-headline">
            Hire faster, without losing the human judgment that makes a good hire.
          </h2>
          <p className="landing-hero-sub">
            Run job postings, applications, AI-assisted screening, assessments, and campus hiring drives
            from one place — with recruiters always in control of the final call.
          </p>
          <div className="landing-hero-actions">
            <Link to="/recruiter/login" className="btn btn-primary btn-lg">
              Get started
            </Link>
            <Link to="/org/acme-corp" className="btn btn-ghost btn-lg">
              Browse open roles
            </Link>
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

      <section id="features" className="landing-section">
        <Reveal>
          <h2 className="landing-section-title">Everything recruiting needs, in one product</h2>
          <p className="landing-section-sub muted">
            Not a raw admin dashboard — a coherent workflow from job to hire.
          </p>
        </Reveal>
        <div className="landing-feature-grid">
          {FEATURES.map((feature) => (
            <Reveal key={feature.title} className="landing-feature-card">
              <span className="landing-feature-icon" aria-hidden="true">
                {feature.icon}
              </span>
              <h3>{feature.title}</h3>
              <p className="muted">{feature.description}</p>
            </Reveal>
          ))}
        </div>
      </section>

      <section id="workflow" className="landing-section landing-section-alt">
        <Reveal>
          <h2 className="landing-section-title">One workflow, start to finish</h2>
          <p className="landing-section-sub muted">
            Every application — from a job post or a campus drive — moves through the same lifecycle.
          </p>
        </Reveal>
        <div className="landing-workflow">
          {WORKFLOW_STEPS.map((step, index) => (
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
            <p className="eyebrow">AI, honestly</p>
            <h2 className="landing-section-title">AI assists your recruiters. It never replaces them.</h2>
            <p className="muted">
              AI-assisted screening gives recruiters a faster first pass over applications — it does not
              make hiring decisions. Every recommendation stays traceable back to the application it
              evaluated, and recruiters review and decide.
            </p>
            <p className="muted">
              No AI provider configured? Screening is simply unavailable until one is — the platform
              never fabricates a score or pretends a request succeeded when it didn't. You can also run
              it against a free, local model instead of a paid API.
            </p>
          </div>
          <ul className="landing-checklist">
            <li>Recruiter-assistive, not autonomous</li>
            <li>Full evaluation history, never overwritten</li>
            <li>Works with free/local or paid providers</li>
            <li>Fails gracefully — never a fake result</li>
          </ul>
        </Reveal>
      </section>

      <section id="analytics" className="landing-section landing-section-alt">
        <Reveal className="landing-split">
          <div>
            <p className="eyebrow">Reporting</p>
            <h2 className="landing-section-title">A hiring funnel built from your real data</h2>
            <p className="muted">
              Applications by job, status distribution, screening and assessment outcomes, and campus
              drive performance — every number is computed from what's actually in your database, with
              filters by date range, job, and department.
            </p>
          </div>
          <div className="landing-mock-window landing-mock-window-sm">
            <div className="landing-mock-bars">
              <div className="landing-mock-bar" style={{ height: "35%" }} />
              <div className="landing-mock-bar" style={{ height: "80%" }} />
              <div className="landing-mock-bar" style={{ height: "50%" }} />
              <div className="landing-mock-bar" style={{ height: "95%" }} />
            </div>
          </div>
        </Reveal>
      </section>

      <section id="campus" className="landing-section">
        <Reveal>
          <h2 className="landing-section-title">Campus hiring, without the spreadsheet chaos</h2>
          <p className="landing-section-sub muted">
            Mass-hiring events are a first-class part of the platform, not a bolted-on special case.
          </p>
        </Reveal>
        <div className="landing-feature-grid landing-feature-grid-3">
          <Reveal className="landing-feature-card">
            <h3>One link per drive</h3>
            <p className="muted">
              Create a drive against an existing job — or add a new one inline — and get a unique,
              shareable application link instantly.
            </p>
          </Reveal>
          <Reveal className="landing-feature-card">
            <h3>No login for candidates</h3>
            <p className="muted">
              Students apply directly from the link with their name, email, and resume — no account
              required.
            </p>
          </Reveal>
          <Reveal className="landing-feature-card">
            <h3>Live funnel tracking</h3>
            <p className="muted">
              Watch registrations turn into screened, assessed, and shortlisted candidates in real time.
              Closed drives stay in your history and can always reopen.
            </p>
          </Reveal>
        </div>
      </section>

      <section className="landing-final-cta">
        <Reveal>
          <h2>Ready to see it in action?</h2>
          <p className="muted">Sign in as a recruiter, or browse what candidates see today.</p>
          <div className="landing-hero-actions">
            <Link to="/recruiter/login" className="btn btn-primary btn-lg">
              Get started
            </Link>
            <Link to="/org/acme-corp" className="btn btn-ghost btn-lg">
              Browse open roles
            </Link>
          </div>
        </Reveal>
      </section>

      <footer className="landing-footer">
        <span>AI Recruitment Platform</span>
        <nav className="landing-footer-links">
          <Link to="/org/acme-corp">Browse open roles</Link>
          <Link to="/recruiter/login">Staff sign in</Link>
        </nav>
        <span className="muted">&copy; {new Date().getFullYear()} AI Recruitment Platform</span>
      </footer>
    </div>
  );
}
