import { Link } from "react-router-dom";
import { BackendStatus } from "../../shared/components/BackendStatus";

export function PublicHomePage() {
  return (
    <section className="public-home">
      <h1>AI Recruitment Platform</h1>
      <p>Public career portal — job browsing and search land in Phase 4.</p>
      <BackendStatus />
      <p className="public-home-links">
        <Link to="/recruiter/login" className="btn btn-primary">
          Staff sign in
        </Link>
      </p>
    </section>
  );
}
