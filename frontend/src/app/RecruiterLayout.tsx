import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { ThemeToggle } from "../features/theme/ThemeToggle";

const NAV_ITEMS = [
  { to: "/recruiter", label: "Overview", end: true },
  { to: "/recruiter/jobs", label: "Jobs" },
  { to: "/recruiter/candidates", label: "Candidates" },
  { to: "/recruiter/applications", label: "Applications" },
  { to: "/recruiter/assessments", label: "Assessments" },
  { to: "/recruiter/campus-drives", label: "Campus Drives" },
  { to: "/recruiter/reports", label: "Reports" },
  { to: "/recruiter/users", label: "Team" },
];

/** Admin-only nav entries — deliberately kept out of NAV_ITEMS so they
 * never render for a plain RECRUITER, not just permission-gated once the
 * page loads (CLAUDE.md: Activities must not appear in the normal
 * recruiter navigation). */
const ADMIN_NAV_ITEMS = [{ to: "/recruiter/activities", label: "Activities" }];

/**
 * Sidebar shell for the recruiter surface. Everything above is real.
 * Sourcing isn't built yet — AI Screening and Notes live inline on the
 * application detail page rather than as their own nav entries — so only
 * Sourcing is listed as a disabled "coming soon" entry.
 */
const UPCOMING_NAV_ITEMS = ["Sourcing"];

export function RecruiterLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const isOrgAdmin = user?.roles.includes("ORG_ADMIN") ?? false;

  async function handleLogout() {
    await logout();
    navigate("/recruiter/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <button
        type="button"
        className={`sidebar-overlay${menuOpen ? " open" : ""}`}
        aria-hidden={!menuOpen}
        onClick={() => setMenuOpen(false)}
      />
      <aside className={`sidebar${menuOpen ? " open" : ""}`}>
        <div className="sidebar-brand">
          <span>AI Recruitment Platform</span>
          <button
            type="button"
            className="sidebar-close"
            aria-label="Close menu"
            onClick={() => setMenuOpen(false)}
          >
            &times;
          </button>
        </div>
        <nav className="sidebar-nav">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
              onClick={() => setMenuOpen(false)}
            >
              {item.label}
            </NavLink>
          ))}
          {isOrgAdmin &&
            ADMIN_NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
                onClick={() => setMenuOpen(false)}
              >
                {item.label}
              </NavLink>
            ))}
          <div className="sidebar-section-label">Coming soon</div>
          {UPCOMING_NAV_ITEMS.map((label) => (
            <span key={label} className="sidebar-link disabled" aria-disabled="true">
              {label}
            </span>
          ))}
        </nav>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="mobile-menu-button"
              aria-label="Open menu"
              onClick={() => setMenuOpen(true)}
            >
              &#9776;
            </button>
            <span className="topbar-title">Recruiter Portal</span>
          </div>
          <div className="topbar-user">
            <ThemeToggle />
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
