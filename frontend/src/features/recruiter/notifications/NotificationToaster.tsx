import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useToast } from "../../../shared/components/ToastContext";
import { useAuth } from "../../auth/AuthContext";
import { listUnreadNotifications } from "./api";

/** The server has no push channel, so the recruiter shell checks for new
 * notifications this often — only while the tab is visible. */
export const NOTIFICATION_POLL_INTERVAL_MS = 30_000;

/** A recruiter who was away can return to a backlog; show the latest few as
 * individual toasts and fold the rest into one summary line. */
const MAX_INDIVIDUAL_TOASTS = 5;

/**
 * Turns the signed-in user's unread server-side notifications (assessment
 * events, announcements, direct messages, calendar reminders) into the
 * app's normal toasts. Deliberately does NOT acknowledge them — a
 * notification must remain visible, unread, in the Notification Center
 * (`/recruiter/notifications`) until the recipient explicitly reads it
 * there, even after it has already been toasted once (product direction:
 * "it must remain available in Notification Center until read"). Renders
 * nothing itself.
 *
 * Never toasted twice in the same session: an id is remembered in `shown`
 * for the life of the page (covering React StrictMode's double effect and
 * repeated polls of the same still-unread row) — reloading the page may
 * re-toast a backlog once, which is the right tradeoff for a poll-only,
 * no-push-channel design.
 */
export function NotificationToaster() {
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const shown = useRef(new Set<string>());

  const { data } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => listUnreadNotifications(accessToken as string),
    enabled: accessToken !== null,
    refetchInterval: NOTIFICATION_POLL_INTERVAL_MS,
    refetchIntervalInBackground: false,
  });

  useEffect(() => {
    if (!data || data.length === 0) return;

    const fresh = data
      .filter((notification) => !shown.current.has(notification.id))
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    if (fresh.length === 0) return;
    fresh.forEach((notification) => shown.current.add(notification.id));

    const individual = fresh.slice(-MAX_INDIVIDUAL_TOASTS);
    const folded = fresh.length - individual.length;
    if (folded > 0) {
      showToast(`${folded} earlier notification${folded === 1 ? "" : "s"}.`, "info");
    }
    individual.forEach((notification) =>
      showToast(notification.message, "info", notification.title),
    );
  }, [data, showToast]);

  return null;
}
