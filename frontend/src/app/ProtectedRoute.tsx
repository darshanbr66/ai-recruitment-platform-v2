import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";

/**
 * Client-side route guard for UX only — the backend re-enforces every
 * authorization decision independently (CLAUDE.md § 2: "Frontend
 * authorization != backend authorization").
 */
export function ProtectedRoute({
  children,
  requireSuperAdmin = false,
}: {
  children: ReactNode;
  requireSuperAdmin?: boolean;
}) {
  const { status, isSuperAdmin } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="page-loading" role="status">
        Loading session…
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/recruiter/login" state={{ from: location }} replace />;
  }

  if (requireSuperAdmin && !isSuperAdmin) {
    return <Navigate to="/recruiter" replace />;
  }

  if (!requireSuperAdmin && isSuperAdmin) {
    return <Navigate to="/admin" replace />;
  }

  return <>{children}</>;
}
