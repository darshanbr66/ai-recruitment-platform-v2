import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { useToast } from "../../../shared/components/ToastContext";
import { useAuth } from "../../auth/AuthContext";
import { acknowledgeNotifications, listUnreadNotifications } from "./api";

/** The server has no push channel, so the recruiter shell checks for new
 * notifications this often — only while the tab is visible. */
export const NOTIFICATION_POLL_INTERVAL_MS = 30_000;

/** A recruiter who was away can return to a backlog; show the latest few as
 * individual toasts and fold the rest into one summary line. */
const MAX_INDIVIDUAL_TOASTS = 5;

/**
 * Turns the signed-in user's unread server-side notifications (e.g. "a
 * candidate started your assessment") into the app's normal toasts, then
 * acknowledges them so they are never shown again. Renders nothing.
 *
 * Never shown twice: an id is remembered in `shown` for the life of the page
 * (covering React StrictMode's double effect and a failed acknowledgement that
 * makes the server return the same row again), and once acknowledged the
 * server stops returning it (covering reloads and other tabs).
 */
export function NotificationToaster() {
  const { accessToken } = useAuth();
  const { showToast } = useToast();
  const shown = useRef(new Set<string>());

  const { data, dataUpdatedAt } = useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => listUnreadNotifications(accessToken as string),
    enabled: accessToken !== null,
    refetchInterval: NOTIFICATION_POLL_INTERVAL_MS,
    refetchIntervalInBackground: false,
  });

  // `dataUpdatedAt` is a dependency so an acknowledgement that failed is
  // retried on the next poll even when the server returns identical rows.
  useEffect(() => {
    if (!data || data.length === 0 || accessToken === null) return;

    const fresh = data
      .filter((notification) => !shown.current.has(notification.id))
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    fresh.forEach((notification) => shown.current.add(notification.id));

    const individual = fresh.slice(-MAX_INDIVIDUAL_TOASTS);
    const folded = fresh.length - individual.length;
    if (folded > 0) {
      showToast(`${folded} earlier assessment update${folded === 1 ? "" : "s"}.`, "info");
    }
    individual.forEach((notification) =>
      showToast(notification.message, "success", notification.title),
    );

    acknowledgeNotifications(
      data.map((notification) => notification.id),
      accessToken,
    ).catch(() => {
      // Retried on the next poll; `shown` prevents a repeat toast meanwhile.
    });
  }, [data, dataUpdatedAt, accessToken, showToast]);

  return null;
}
