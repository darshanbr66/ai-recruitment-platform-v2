import { Navigate, Route, Routes } from "react-router-dom";
import { CandidatePlaceholderPage } from "../features/candidate/CandidatePlaceholderPage";
import { LoginPage } from "../features/auth/LoginPage";
import { OrganizationsPage } from "../features/admin/organizations/OrganizationsPage";
import { ApplicationsPage } from "../features/recruiter/applications/ApplicationsPage";
import { CandidatesPage } from "../features/recruiter/candidates/CandidatesPage";
import { JobsPage } from "../features/recruiter/jobs/JobsPage";
import { OverviewPage } from "../features/recruiter/overview/OverviewPage";
import { PublicHomePage } from "../features/public/PublicHomePage";
import { UsersPage } from "../features/recruiter/users/UsersPage";
import { AdminLayout } from "./AdminLayout";
import { ProtectedRoute } from "./ProtectedRoute";
import { RecruiterLayout } from "./RecruiterLayout";

/**
 * Three route trees, kept structurally separate per docs/architecture.md
 * § 6: public (anonymous), candidate (candidate JWT, from Phase 4), and
 * recruiter (staff JWT, from Phase 2). Each grows independently as its
 * phase is built — none of these subtrees should import from another.
 *
 * `/admin` is its own protected tree (SUPER_ADMIN only), mirroring the
 * backend's `/api/v1/admin/*` split from `/api/v1/recruiter/*`.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<PublicHomePage />} />
      <Route path="/candidate/*" element={<CandidatePlaceholderPage />} />

      <Route path="/recruiter/login" element={<LoginPage />} />
      <Route
        path="/recruiter"
        element={
          <ProtectedRoute>
            <RecruiterLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<OverviewPage />} />
        <Route path="jobs" element={<JobsPage />} />
        <Route path="candidates" element={<CandidatesPage />} />
        <Route path="applications" element={<ApplicationsPage />} />
        <Route path="users" element={<UsersPage />} />
      </Route>

      <Route
        path="/admin"
        element={
          <ProtectedRoute requireSuperAdmin>
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<OrganizationsPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
