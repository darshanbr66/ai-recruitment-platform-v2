import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { ThemeToggle } from "../features/theme/ThemeToggle";

/**
 * Platform-administration shell — structurally separate from the recruiter
 * surface, mirroring the backend's own split between `/api/v1/recruiter/*`
 * and `/api/v1/admin/*` (docs/architecture.md § 5). Platform-level details
 * (organization IDs, tenant/system information) are shown here deliberately
 * — this surface is SUPER_ADMIN only, never seen by ordinary recruiter/org
 * admin users.
 */
export function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);

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
      <aside className={`sidebar sidebar-admin${menuOpen ? " open" : ""}`}>
        <div className="sidebar-brand">
          <span>Platform Administration</span>
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
          <NavLink
            to="/admin"
            end
            className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
            onClick={() => setMenuOpen(false)}
          >
            Organizations
          </NavLink>
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
            <span className="topbar-title">Super Admin</span>
          </div>
          <div className="topbar-user">
            <ThemeToggle />
            <div className="user-badge">
              <span className="user-name">{user?.full_name}</span>
              <span className="user-roles">SUPER_ADMIN</span>
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
