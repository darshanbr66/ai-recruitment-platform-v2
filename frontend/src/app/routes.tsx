import { Route, Routes } from "react-router-dom";
import { CandidatePlaceholderPage } from "../features/candidate/CandidatePlaceholderPage";
import { PublicHomePage } from "../features/public/PublicHomePage";
import { RecruiterPlaceholderPage } from "../features/recruiter/RecruiterPlaceholderPage";

/**
 * Three route trees, kept structurally separate per docs/architecture.md
 * § 6: public (anonymous), candidate (candidate JWT, from Phase 4), and
 * recruiter (staff JWT, from Phase 2). Each grows independently as its
 * phase is built — none of these subtrees should import from another.
 */
export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<PublicHomePage />} />
      <Route path="/candidate/*" element={<CandidatePlaceholderPage />} />
      <Route path="/recruiter/*" element={<RecruiterPlaceholderPage />} />
    </Routes>
  );
}
