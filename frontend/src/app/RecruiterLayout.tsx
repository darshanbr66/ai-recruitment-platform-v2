import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../features/auth/AuthContext";
import { getUnreadCount } from "../features/recruiter/notifications/api";
import { NotificationToaster } from "../features/recruiter/notifications/NotificationToaster";
import { AppShell, type NavItem, type NavSection } from "./AppShell";

const WORKSPACE_ITEMS: NavItem[] = [
  { to: "/recruiter", label: "Overview", icon: "overview", end: true },
  { to: "/recruiter/jobs", label: "Jobs", icon: "jobs" },
  { to: "/recruiter/candidates", label: "Candidates", icon: "candidates" },
  { to: "/recruiter/applications", label: "Applications", icon: "applications" },
  { to: "/recruiter/assessments", label: "Assessments", icon: "assessments" },
  { to: "/recruiter/campus-drives", label: "Campus Drives", icon: "campus" },
  { to: "/recruiter/notes", label: "Notes", icon: "notes" },
  { to: "/recruiter/calendar", label: "Calendar", icon: "calendar" },
];

/** Only ORG_ADMIN/RECRUITER/HIRING_MANAGER get `internal_ai.use` on the
 * backend (see the Phase A migration seeding it) — hidden for everyone else
 * so it never appears as a dead end for an INTERVIEWER. UX only: the API
 * enforces the permission independently. */
const AI_NAV_ITEM: NavItem = { to: "/recruiter/ai", label: "AI Intelligence", icon: "sparkles" };
const AI_ROLES = ["ORG_ADMIN", "RECRUITER", "HIRING_MANAGER"];

const INSIGHT_ITEMS: NavItem[] = [
  { to: "/recruiter/reports", label: "Reports", icon: "reports" },
  { to: "/recruiter/users", label: "Team", icon: "team" },
];

/** Poll cadence for the sidebar's unread badge — shares the same interval
 * as NotificationToaster's own poll for a consistent "how fresh is this"
 * feel, but is otherwise an independent, lightweight COUNT query. */
const UNREAD_BADGE_POLL_MS = 30_000;

/** Roles that may send email (backend permission `application.email.send`).
 * Hidden for everyone else so it never shows in a HIRING_MANAGER/INTERVIEWER's
 * navigation — UX only, the API enforces it. */
const EMAIL_NAV_ITEM: NavItem = { to: "/recruiter/email", label: "Email", icon: "email" };
const EMAIL_ROLES = ["ORG_ADMIN", "RECRUITER"];

/** Admin-only nav entries — deliberately kept out of the always-on items so
 * they never render for a plain RECRUITER, not just permission-gated once the
 * page loads (CLAUDE.md: Activities must not appear in the normal
 * recruiter navigation). */
const ADMIN_NAV_ITEMS: NavItem[] = [
  { to: "/recruiter/activities", label: "Activities", icon: "activities" },
];

/**
 * Sourcing isn't built yet — AI Screening and Notes live inline on the
 * application detail page rather than as their own nav entries — so only
 * Sourcing is listed, as a disabled "coming soon" entry.
 */
const UPCOMING_NAV_ITEMS = ["Sourcing"];

/** The four destinations recruiters reach for most — the phone tab bar. */
const TAB_ITEMS: NavItem[] = WORKSPACE_ITEMS.slice(0, 4);

export function RecruiterLayout() {
  const { user, logout, accessToken } = useAuth();
  const navigate = useNavigate();
  const isOrgAdmin = user?.roles.includes("ORG_ADMIN") ?? false;
  const canSendEmail = user?.roles.some((role) => EMAIL_ROLES.includes(role)) ?? false;
  const canUseAi = user?.roles.some((role) => AI_ROLES.includes(role)) ?? false;

  const unreadQuery = useQuery({
    queryKey: ["notifications", "unread-count"],
    queryFn: () => getUnreadCount(accessToken as string),
    enabled: accessToken !== null,
    refetchInterval: UNREAD_BADGE_POLL_MS,
    refetchIntervalInBackground: false,
  });
  const notificationsNavItem: NavItem = {
    to: "/recruiter/notifications",
    label: "Notifications",
    icon: "inbox",
    badge: unreadQuery.data?.unread,
  };

  async function handleLogout() {
    await logout();
    navigate("/recruiter/login", { replace: true });
  }

  const sections: NavSection[] = [
    {
      label: "Workspace",
      items: [...(canUseAi ? [AI_NAV_ITEM] : []), notificationsNavItem, ...WORKSPACE_ITEMS],
    },
    {
      label: "Organization",
      items: [
        ...INSIGHT_ITEMS,
        ...(canSendEmail ? [EMAIL_NAV_ITEM] : []),
        ...(isOrgAdmin ? ADMIN_NAV_ITEMS : []),
      ],
    },
  ];

  return (
    <>
      <NotificationToaster />
      <AppShell
        brandTitle="AI Recruitment Platform"
        contextLabel="Recruiter Portal"
        sections={sections}
        upcoming={UPCOMING_NAV_ITEMS}
        tabs={TAB_ITEMS}
        userName={user?.full_name}
        userRole={user?.roles.join(", ") ?? ""}
        onSignOut={() => void handleLogout()}
        notificationBell={{ unreadCount: unreadQuery.data?.unread ?? 0, to: "/recruiter/notifications" }}
      />
    </>
  );
}
