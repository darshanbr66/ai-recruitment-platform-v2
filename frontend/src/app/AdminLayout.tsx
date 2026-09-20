import { useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { AppShell, type NavSection } from "./AppShell";

const SECTIONS: NavSection[] = [
  { items: [{ to: "/admin", label: "Organizations", icon: "graph", end: true }] },
];

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

  async function handleLogout() {
    await logout();
    navigate("/recruiter/login", { replace: true });
  }

  return (
    <AppShell
      variant="admin"
      brandTitle="Platform Administration"
      contextLabel="Super Admin"
      sections={SECTIONS}
      userName={user?.full_name}
      userRole="SUPER_ADMIN"
      onSignOut={() => void handleLogout()}
    />
  );
}
