import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";

const NAV_ITEMS = [
  { to: "/recruiter", label: "Overview", end: true },
  { to: "/recruiter/jobs", label: "Jobs" },
  { to: "/recruiter/candidates", label: "Candidates" },
  { to: "/recruiter/applications", label: "Applications" },
  { to: "/recruiter/users", label: "Users" },
];

/**
 * Sidebar shell for the recruiter surface (docs/architecture.md § 6).
 * Jobs/Candidates/Applications/Users are real (Phase 2-3). Everything else
 * from the product scope (Sourcing, Screening, Assessments, Reports, Campus
 * Drives) is listed as a disabled "coming soon" entry so the navigation
 * honestly reflects what later phases will add, rather than linking to
 * nothing.
 */
const UPCOMING_NAV_ITEMS = ["Sourcing", "Screening", "Assessments", "Campus Drives", "Notes", "Reports"];

export function RecruiterLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/recruiter/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="sidebar-brand">AI Recruitment Platform</div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
            >
              {item.label}
            </NavLink>
          ))}
          <div className="sidebar-section-label">Coming in later phases</div>
          {UPCOMING_NAV_ITEMS.map((label) => (
            <span key={label} className="sidebar-link disabled" aria-disabled="true">
              {label}
            </span>
          ))}
        </nav>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <span className="topbar-title">Recruiter Portal</span>
          <div className="topbar-user">
            <div className="user-badge">
              <span className="user-name">{user?.full_name}</span>
              <span className="user-roles">{user?.roles.join(", ")}</span>
            </div>
            <button type="button" className="btn btn-ghost" onClick={() => void handleLogout()}>
              Sign out
            </button>
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
