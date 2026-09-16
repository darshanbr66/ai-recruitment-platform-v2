import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";

/**
 * Platform-administration shell — structurally separate from the recruiter
 * surface, mirroring the backend's own split between `/api/v1/recruiter/*`
 * and `/api/v1/admin/*` (docs/architecture.md § 5).
 */
export function AdminLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  async function handleLogout() {
    await logout();
    navigate("/recruiter/login", { replace: true });
  }

  return (
    <div className="app-shell">
      <aside className="sidebar sidebar-admin">
        <div className="sidebar-brand">Platform Administration</div>
        <nav className="sidebar-nav">
          <NavLink
            to="/admin"
            end
            className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
          >
            Organizations
          </NavLink>
        </nav>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <span className="topbar-title">Super Admin</span>
          <div className="topbar-user">
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
