import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate, type Location } from "react-router-dom";
import { ApiError } from "../../lib/apiClient";
import { Icon, LogoMark } from "../../shared/components/Icon";
import { NetworkBackdrop } from "../../shared/components/NetworkBackdrop";
import { ThemeToggle } from "../theme/ThemeToggle";
import { useAuth } from "./AuthContext";

/**
 * One login form for every staff principal (ORG_ADMIN, RECRUITER,
 * HIRING_MANAGER, INTERVIEWER, SUPER_ADMIN) — login is staff auth, not
 * "recruiter business data" (see backend/app/api/v1/recruiter/auth.py).
 * Where the caller lands afterward depends on which kind of account it is.
 */
export function LoginPage() {
  const { status, isSuperAdmin, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (status === "authenticated") {
    return <Navigate to={isSuperAdmin ? "/admin" : "/recruiter"} replace />;
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      const user = await login(email, password);
      const from = (location.state as { from?: Location } | null | undefined)?.from;
      const fallback = user.organization_id === null ? "/admin" : "/recruiter";
      navigate(from?.pathname ?? fallback, { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="auth-shell">
      <Link to="/" className="auth-home-link">
        &larr; Back to Home
      </Link>
      <ThemeToggle />

      <aside className="auth-brand" aria-hidden="true">
        <NetworkBackdrop seed={3} count={40} />
        <div className="auth-brand-inner">
          <LogoMark size={44} />
          <h2>Recruitment intelligence, with people in the loop.</h2>
          <ul>
            <li>
              <Icon name="sparkles" size={16} /> AI-assisted screening, always recruiter-reviewed
            </li>
            <li>
              <Icon name="shield" size={16} /> Every decision traceable to its application
            </li>
            <li>
              <Icon name="eye" size={16} /> Assessments with transparent monitoring
            </li>
          </ul>
        </div>
      </aside>

      <div className="auth-card">
        <p className="eyebrow">AI Recruitment Platform</p>
        <h1>Sign in</h1>
        <p className="muted">Recruiters, hiring managers, and organization admins sign in here.</p>

        <form onSubmit={handleSubmit}>
          <label className="field">
            <span>Email</span>
            <input
              type="email"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
            />
          </label>

          <label className="field">
            <span>Password</span>
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={isSubmitting}
            />
          </label>

          {error && (
            <p className="alert alert-error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
            {isSubmitting ? "Signing in…" : "Sign in"}
          </button>
        </form>
      </div>
    </div>
  );
}
