import { Link } from "react-router-dom";
import { ThemeToggle } from "../theme/ThemeToggle";

export function PublicHomePage() {
  return (
    <section className="public-home">
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <ThemeToggle />
      </div>
      <h1>AI Recruitment Platform</h1>
      <p className="muted">AI-assisted hiring — from job posting to offer.</p>
      <p className="public-home-links">
        <Link to="/org/acme-corp" className="btn btn-primary">
          Browse open roles
        </Link>{" "}
        <Link to="/recruiter/login" className="btn btn-ghost">
          Staff sign in
        </Link>
      </p>
    </section>
  );
}
