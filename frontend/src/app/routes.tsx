import { Navigate, Route, Routes } from "react-router-dom";
import { CandidatePlaceholderPage } from "../features/candidate/CandidatePlaceholderPage";
import { AssessmentTakingPage } from "../features/careers/AssessmentTakingPage";
import { CampusDriveApplyPage } from "../features/careers/CampusDriveApplyPage";
import { CareersPage } from "../features/careers/CareersPage";
import { JobDetailPage } from "../features/careers/JobDetailPage";
import { LoginPage } from "../features/auth/LoginPage";
import { OrganizationsPage } from "../features/admin/organizations/OrganizationsPage";
import { ActivitiesPage } from "../features/recruiter/activities/ActivitiesPage";
import { ApplicationDetailPage } from "../features/recruiter/applications/ApplicationDetailPage";
import { ApplicationsPage } from "../features/recruiter/applications/ApplicationsPage";
import { AssessmentDetailPage } from "../features/recruiter/assessments/AssessmentDetailPage";
import { AssessmentsPage } from "../features/recruiter/assessments/AssessmentsPage";
import { CampusDriveDetailPage } from "../features/recruiter/campusDrives/CampusDriveDetailPage";
import { CampusDrivesPage } from "../features/recruiter/campusDrives/CampusDrivesPage";
import { CandidateDetailPage } from "../features/recruiter/candidates/CandidateDetailPage";
import { CandidatesPage } from "../features/recruiter/candidates/CandidatesPage";
import { JobsPage } from "../features/recruiter/jobs/JobsPage";
import { OverviewPage } from "../features/recruiter/overview/OverviewPage";
import { ReportsPage } from "../features/recruiter/reports/ReportsPage";
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
      <Route path="/org/:slug" element={<CareersPage />} />
      <Route path="/org/:slug/jobs/:jobId" element={<JobDetailPage />} />
      <Route path="/assessment/:token" element={<AssessmentTakingPage />} />
      <Route path="/campus-drive/:token" element={<CampusDriveApplyPage />} />
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
        <Route path="candidates/:candidateId" element={<CandidateDetailPage />} />
        <Route path="applications" element={<ApplicationsPage />} />
        <Route path="applications/:applicationId" element={<ApplicationDetailPage />} />
        <Route path="assessments" element={<AssessmentsPage />} />
        <Route path="assessments/:assessmentId" element={<AssessmentDetailPage />} />
        <Route path="campus-drives" element={<CampusDrivesPage />} />
        <Route path="campus-drives/:driveId" element={<CampusDriveDetailPage />} />
        <Route path="reports" element={<ReportsPage />} />
        <Route path="users" element={<UsersPage />} />
        <Route path="activities" element={<ActivitiesPage />} />
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
