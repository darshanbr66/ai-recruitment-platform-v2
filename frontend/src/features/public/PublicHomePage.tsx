import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { EmptyState } from "../../shared/components/EmptyState";
import { Icon, type IconName } from "../../shared/components/Icon";
import { Magnetic } from "../../shared/components/Magnetic";
import { NetworkBackdrop } from "../../shared/components/NetworkBackdrop";
import { Reveal } from "../../shared/components/Reveal";
import { Skeleton } from "../../shared/components/Skeleton";
import { listOpenJobs } from "../careers/api";
import { HeroSection } from "./HeroSection";
import { LandingNav } from "./LandingNav";

/** The one organization this deployment actually serves — the public home
 * page is SIGVITAS' own careers site, not a generic multi-tenant landing
 * page (SIGVITAS platform overhaul § 1). The underlying platform stays
 * multi-tenant-capable; only this page's copy and framing changes. */
const SIGVITAS_SLUG = "sigvitas";

/** Where a person, not the model, is the actor — marked in the pipeline. */
type StepTag = "ai" | "human";

const HIRING_STEPS: { title: string; description: string; tag?: StepTag }[] = [
  { title: "Explore openings", description: "Browse current roles across engineering, design, and more." },
  { title: "Apply", description: "Submit your application and resume — no account required." },
  { title: "Resume review", description: "Our team reviews your background against the role." },
  {
    title: "Screening",
    description: "An initial pass — assisted by AI, always reviewed by a recruiter.",
    tag: "ai",
  },
  { title: "Assessment", description: "Some roles include a short skills assessment before the next round." },
  { title: "Interview", description: "Meet the team and talk through the role in more depth." },
  { title: "Decision", description: "We follow up either way, as soon as we can.", tag: "human" },
];

const PRINCIPLES: { icon: IconName; title: string; text: string }[] = [
  { icon: "sparkles", title: "Recruiter-assistive, never autonomous", text: "AI surfaces signal for a recruiter to review. It never makes a hiring decision on its own." },
  { icon: "lock", title: "Your data stays tied to your application", text: "Every screening result stays traceable back to the application it belongs to." },
  { icon: "user", title: "A person reviews every step that matters", text: "A recruiter makes the call — and it's always a person who follows up." },
  { icon: "eye", title: "Monitoring is disclosed upfront", text: "If an assessment uses monitoring, you're told before you begin — never after." },
];

const CAMPUS: { icon: IconName; title: string; text: string }[] = [
  {
    icon: "campus",
    title: "Apply with a drive link",
    text: "If your college is running a SIGVITAS drive, you'll get a direct application link — no account needed.",
  },
  {
    icon: "graph",
    title: "Same hiring process",
    text: "Campus applications go through the same review and assessment process as any other application.",
  },
  {
    icon: "email",
    title: "Clear updates",
    text: "You'll hear from us at each step — and if a drive has closed, we'll let you know rather than leave you guessing.",
  },
];

function RoleCardSkeleton() {
  return (
    <div className="role-card role-card-skeleton" aria-hidden="true">
      <Skeleton height="1.1rem" width="62%" />
      <Skeleton height="0.8rem" width="40%" />
      <Skeleton height="1.6rem" width="5.5rem" style={{ borderRadius: 999, marginTop: "0.5rem" }} />
    </div>
  );
}

export function PublicHomePage() {
  const openJobsQuery = useQuery({
    queryKey: ["public", "jobs", SIGVITAS_SLUG, "preview"],
    queryFn: () => listOpenJobs(SIGVITAS_SLUG),
  });
  const allOpenJobs = openJobsQuery.data ?? [];
  const openJobs = allOpenJobs.slice(0, 6);
  const careersPath = `/org/${SIGVITAS_SLUG}`;

  return (
    <div className="landing">
      <LandingNav />

      <HeroSection
        careersPath={careersPath}
        openRoleCount={openJobsQuery.isSuccess ? allOpenJobs.length : null}
      />

      <section id="openings" className="landing-section">
        <Reveal>
          <p className="section-eyebrow">Open now</p>
          <h2 className="landing-section-title">Current openings</h2>
          <p className="landing-section-sub">
            A live look at what's open right now — see every role on our careers page.
          </p>
        </Reveal>

        <div className="role-grid">
          {openJobsQuery.isPending && [0, 1, 2].map((i) => <RoleCardSkeleton key={i} />)}
          {openJobsQuery.isSuccess && openJobs.length === 0 && (
            <div className="role-grid-empty">
              <EmptyState icon="jobs" title="No open roles right now">
                Check back soon — new openings are posted regularly.
              </EmptyState>
            </div>
          )}
          {openJobs.map((job, index) => (
            <Reveal key={job.id} delay={Math.min(index, 5) * 60}>
              <Link to={`${careersPath}/jobs/${job.id}`} className="role-card">
                <span className="role-card-title">{job.title}</span>
                <span className="role-card-meta">
                  {job.department && <span className="chip">{job.department}</span>}
                  {job.location && (
                    <span className="chip">
                      <Icon name="pin" size={13} />
                      {job.location}
                    </span>
                  )}
                </span>
                <span className="role-card-cta">
                  View role <Icon name="arrow-right" size={16} />
                </span>
              </Link>
            </Reveal>
          ))}
        </div>

        <Reveal className="landing-more">
          <Link to={careersPath} className="btn btn-primary">
            See all open roles
          </Link>
        </Reveal>
      </section>

      <section id="process" className="landing-section landing-section-alt">
        <div className="process">
          <Reveal className="process-intro">
            <p className="section-eyebrow">The path</p>
            <h2 className="landing-section-title">Our hiring process</h2>
            <p className="landing-section-sub">
              One clear path, whether you're applying directly or through a campus drive.
            </p>
            <ul className="process-key" aria-label="Key">
              <li>
                <span className="process-tag process-tag-ai">AI-assisted</span> a step where AI helps
                a recruiter
              </li>
              <li>
                <span className="process-tag process-tag-human">Human decision</span> a step only a
                person can take
              </li>
            </ul>
          </Reveal>

          <ol className="process-steps">
            {HIRING_STEPS.map((step, index) => (
              <Reveal as="li" key={step.title} className="process-step" delay={index * 55} direction="right">
                <span className="process-node" aria-hidden="true">
                  {index + 1}
                </span>
                <div className="process-body">
                  <h3>
                    {step.title}
                    {step.tag === "ai" && <span className="process-tag process-tag-ai">AI-assisted</span>}
                    {step.tag === "human" && <span className="process-tag process-tag-human">Human decision</span>}
                  </h3>
                  <p>{step.description}</p>
                </div>
              </Reveal>
            ))}
          </ol>
        </div>
      </section>

      <section id="ai" className="landing-section">
        <Reveal>
          <p className="section-eyebrow">How we review applications</p>
          <h2 className="landing-section-title">AI assists our recruiters. It never decides.</h2>
          <p className="landing-section-sub">
            We use AI to help our team get through applications faster — surfacing signal for a
            recruiter to review, never making a hiring decision on its own. Every screening result
            stays traceable back to your application, and a person always makes the call.
          </p>
        </Reveal>
        <div className="principle-grid">
          {PRINCIPLES.map((item, index) => (
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

      <section id="campus" className="landing-section landing-section-alt">
        <Reveal>
          <p className="section-eyebrow">Campus</p>
          <h2 className="landing-section-title">Campus hiring</h2>
          <p className="landing-section-sub">
            SIGVITAS runs dedicated campus drives with colleges — watch for a drive link shared by
            your placement office, or check back here for upcoming opportunities.
          </p>
        </Reveal>
        <div className="principle-grid principle-grid-3">
          {CAMPUS.map((item, index) => (
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
          <h2>Ready to apply?</h2>
          <p>Explore open roles at SIGVITAS and submit your application today.</p>
          <Magnetic>
            <Link to={careersPath} className="btn btn-primary btn-lg">
              Explore Open Roles
              <Icon name="arrow-right" size={18} />
            </Link>
          </Magnetic>
        </Reveal>
      </section>

      <footer className="landing-footer">
        <span>SIGVITAS Careers</span>
        <nav className="landing-footer-links" aria-label="Footer">
          <Link to={careersPath}>Open roles</Link>
          <Link to="/recruiter/login">Staff sign in</Link>
        </nav>
        <span className="muted">&copy; {new Date().getFullYear()} SIGVITAS</span>
      </footer>
    </div>
  );
}
