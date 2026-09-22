import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { EmptyState } from "../../../shared/components/EmptyState";
import { Modal } from "../../../shared/components/Modal";
import { SkeletonList } from "../../../shared/components/Skeleton";
import { Spinner } from "../../../shared/components/Spinner";
import { useToast } from "../../../shared/components/ToastContext";
import type { AnnouncementTarget, NotificationResponse, NotificationType } from "../../../types/notification";
import { useAuth } from "../../auth/AuthContext";
import { listUsers } from "../../auth/api";
import { listDepartments } from "../team/api";
import {
  acknowledgeAllNotifications,
  acknowledgeNotifications,
  listAllNotifications,
  sendAnnouncement,
  sendDirectMessage,
} from "./api";

const NOTIFICATIONS_QUERY_KEY = ["recruiter", "notifications", "all"];

const TYPE_LABEL: Record<NotificationType, string> = {
  ASSESSMENT_STARTED: "Assessment",
  ASSESSMENT_SUBMITTED: "Assessment",
  ANNOUNCEMENT: "Announcement",
  DIRECT_MESSAGE: "Message",
  CALENDAR_REMINDER: "Reminder",
};

const TYPE_BADGE: Record<NotificationType, string> = {
  ASSESSMENT_STARTED: "badge-info",
  ASSESSMENT_SUBMITTED: "badge-info",
  ANNOUNCEMENT: "badge-accent",
  DIRECT_MESSAGE: "badge-active",
  CALENDAR_REMINDER: "badge-warn",
};

function relatedEntityLink(notification: NotificationResponse): { to: string; label: string } | null {
  if (!notification.related_entity_type || !notification.related_entity_id) return null;
  switch (notification.related_entity_type) {
    case "APPLICATION":
      return { to: `/recruiter/applications/${notification.related_entity_id}`, label: "View application" };
    case "CANDIDATE":
      return { to: `/recruiter/candidates/${notification.related_entity_id}`, label: "View candidate" };
    default:
      return null;
  }
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  return `${date.toLocaleDateString()} · ${date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

export function NotificationsPage() {
  const { accessToken, user } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const [composer, setComposer] = useState<"announcement" | "message" | null>(null);

  const isOrgAdmin = user?.roles.includes("ORG_ADMIN") ?? false;

  const notificationsQuery = useQuery({
    queryKey: [...NOTIFICATIONS_QUERY_KEY, filter],
    queryFn: () => listAllNotifications(token, { unreadOnly: filter === "unread", limit: 100 }),
    enabled: accessToken !== null,
  });

  const markReadMutation = useMutation({
    mutationFn: (id: string) => acknowledgeNotifications([id], token),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_QUERY_KEY }),
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => acknowledgeAllNotifications(token),
    onSuccess: (result) => {
      showToast(result.updated > 0 ? `Marked ${result.updated} notification(s) as read.` : "Nothing to mark.", "success");
      void queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_QUERY_KEY });
    },
  });

  const unreadCount = useMemo(
    () => notificationsQuery.data?.filter((n) => n.read_at === null).length ?? 0,
    [notificationsQuery.data],
  );

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Notifications</h1>
          <p className="muted">Announcements, messages and updates for your organization.</p>
        </div>
        <div className="page-header-actions">
          {isOrgAdmin && (
            <button type="button" className="btn btn-ghost" onClick={() => setComposer("announcement")}>
              + Announcement
            </button>
          )}
          <button type="button" className="btn btn-ghost" onClick={() => setComposer("message")}>
            + Message a colleague
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => markAllReadMutation.mutate()}
            disabled={markAllReadMutation.isPending || unreadCount === 0}
          >
            {markAllReadMutation.isPending ? <Spinner label="Marking…" /> : "Mark all as read"}
          </button>
        </div>
      </div>

      <div className="toolbar">
        <div className="segmented-control">
          <button
            type="button"
            className={`btn btn-sm ${filter === "all" ? "btn-primary" : "btn-ghost"}`}
            onClick={() => setFilter("all")}
          >
            All
          </button>
          <button
            type="button"
            className={`btn btn-sm ${filter === "unread" ? "btn-primary" : "btn-ghost"}`}
            onClick={() => setFilter("unread")}
          >
            Unread{unreadCount > 0 ? ` (${unreadCount})` : ""}
          </button>
        </div>
      </div>

      {notificationsQuery.isPending && <SkeletonList rows={6} />}
      {notificationsQuery.isError && (
        <Alert>
          {notificationsQuery.error instanceof ApiError
            ? notificationsQuery.error.message
            : "Could not load notifications."}
        </Alert>
      )}

      {notificationsQuery.isSuccess && notificationsQuery.data.length === 0 && (
        <EmptyState icon="inbox" title={filter === "unread" ? "You're all caught up" : "No notifications yet"}>
          {filter === "unread"
            ? "Nothing new right now — announcements, messages and updates will show up here."
            : "Announcements, direct messages and system updates for your organization will appear here."}
        </EmptyState>
      )}

      {notificationsQuery.isSuccess && notificationsQuery.data.length > 0 && (
        <ul className="stack-sm notification-list" style={{ listStyle: "none", margin: 0, padding: 0 }}>
          {notificationsQuery.data.map((notification) => {
            const isUnread = notification.read_at === null;
            const link = relatedEntityLink(notification);
            return (
              <li
                key={notification.id}
                className={`card notification-item${isUnread ? " notification-item-unread" : ""}`}
              >
                <div className="notification-item-head">
                  <span className={`badge ${TYPE_BADGE[notification.type]}`}>{TYPE_LABEL[notification.type]}</span>
                  <span className="muted notification-item-time">{formatTimestamp(notification.created_at)}</span>
                </div>
                <h3 style={{ margin: "0.4rem 0 0.15rem" }}>{notification.title}</h3>
                <p style={{ margin: 0 }}>{notification.message}</p>
                <div className="notification-item-foot">
                  <span className="muted" style={{ fontSize: "0.78rem" }}>
                    {notification.sender_name ? `From ${notification.sender_name}` : "System"}
                  </span>
                  <div className="btn-group">
                    {link && (
                      <Link className="btn btn-ghost btn-sm" to={link.to}>
                        {link.label}
                      </Link>
                    )}
                    {isUnread && (
                      <button
                        type="button"
                        className="btn btn-ghost btn-sm"
                        onClick={() => markReadMutation.mutate(notification.id)}
                        disabled={markReadMutation.isPending}
                      >
                        Mark as read
                      </button>
                    )}
                  </div>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {composer === "announcement" && (
        <AnnouncementComposer
          token={token}
          onClose={() => setComposer(null)}
          onSent={(count) => {
            showToast(`Announcement sent to ${count} recipient(s).`, "success");
            setComposer(null);
            void queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_QUERY_KEY });
          }}
        />
      )}

      {composer === "message" && (
        <DirectMessageComposer
          token={token}
          onClose={() => setComposer(null)}
          onSent={() => {
            showToast("Message sent.", "success");
            setComposer(null);
          }}
        />
      )}
    </div>
  );
}

function AnnouncementComposer({
  token,
  onClose,
  onSent,
}: {
  token: string;
  onClose: () => void;
  onSent: (recipients: number) => void;
}) {
  const [target, setTarget] = useState<AnnouncementTarget>("EVERYONE");
  const [departmentId, setDepartmentId] = useState("");
  const [userIds, setUserIds] = useState<Set<string>>(new Set());
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  const departmentsQuery = useQuery({
    queryKey: ["recruiter", "departments"],
    queryFn: () => listDepartments(token),
    enabled: target === "DEPARTMENT",
  });
  const usersQuery = useQuery({
    queryKey: ["recruiter", "users"],
    queryFn: () => listUsers(token),
    enabled: target === "EMPLOYEES",
  });

  const sendMutation = useMutation({
    mutationFn: () =>
      sendAnnouncement(
        {
          title,
          message,
          target,
          department_id: target === "DEPARTMENT" ? departmentId || null : null,
          user_ids: target === "EMPLOYEES" ? Array.from(userIds) : [],
        },
        token,
      ),
    onSuccess: (result) => onSent(result.recipients_notified),
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to reach the server."),
  });

  function toggleUser(id: string) {
    setUserIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (target === "DEPARTMENT" && !departmentId) {
      setError("Choose a department.");
      return;
    }
    if (target === "EMPLOYEES" && userIds.size === 0) {
      setError("Select at least one person.");
      return;
    }
    setError(null);
    sendMutation.mutate();
  }

  return (
    <Modal title="Send an announcement" onClose={onClose} wide>
      <form onSubmit={handleSubmit}>
        <label className="field">
          <span>Recipients</span>
          <select value={target} onChange={(e) => setTarget(e.target.value as AnnouncementTarget)}>
            <option value="EVERYONE">Everyone in the organization</option>
            <option value="DEPARTMENT">A department</option>
            <option value="EMPLOYEES">Specific people</option>
          </select>
        </label>

        {target === "DEPARTMENT" && (
          <label className="field">
            <span>Department</span>
            {departmentsQuery.isPending ? (
              <Spinner label="Loading departments…" />
            ) : (
              <select value={departmentId} onChange={(e) => setDepartmentId(e.target.value)}>
                <option value="" disabled>
                  Select a department…
                </option>
                {departmentsQuery.data?.map((dept) => (
                  <option key={dept.id} value={dept.id}>
                    {dept.name}
                  </option>
                ))}
              </select>
            )}
          </label>
        )}

        {target === "EMPLOYEES" && (
          <div className="field">
            <span>People</span>
            {usersQuery.isPending ? (
              <Spinner label="Loading people…" />
            ) : (
              <div className="stack-sm" style={{ maxHeight: "12rem", overflowY: "auto" }}>
                {usersQuery.data?.map((teamUser) => (
                  <label key={teamUser.id} className="checkbox-row">
                    <input
                      type="checkbox"
                      checked={userIds.has(teamUser.id)}
                      onChange={() => toggleUser(teamUser.id)}
                    />
                    {teamUser.full_name} <span className="muted">({teamUser.email})</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        <label className="field">
          <span>Title</span>
          <input required value={title} onChange={(e) => setTitle(e.target.value)} disabled={sendMutation.isPending} />
        </label>
        <label className="field">
          <span>Message</span>
          <textarea
            required
            rows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            disabled={sendMutation.isPending}
            placeholder="e.g. Tomorrow the office will be closed due to maintenance."
          />
        </label>

        {error && <Alert>{error}</Alert>}

        <div className="btn-group" style={{ marginTop: "1rem" }}>
          <button type="submit" className="btn btn-primary" disabled={sendMutation.isPending}>
            {sendMutation.isPending ? <Spinner label="Sending…" /> : "Send announcement"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={sendMutation.isPending}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}

function DirectMessageComposer({
  token,
  onClose,
  onSent,
}: {
  token: string;
  onClose: () => void;
  onSent: () => void;
}) {
  const [recipientId, setRecipientId] = useState("");
  const [title, setTitle] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);

  const usersQuery = useQuery({ queryKey: ["recruiter", "users"], queryFn: () => listUsers(token) });

  const sendMutation = useMutation({
    mutationFn: () => sendDirectMessage({ recipient_user_id: recipientId, title, message }, token),
    onSuccess: onSent,
    onError: (err) => setError(err instanceof ApiError ? err.message : "Unable to reach the server."),
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!recipientId) {
      setError("Choose a recipient.");
      return;
    }
    setError(null);
    sendMutation.mutate();
  }

  return (
    <Modal title="Message a colleague" onClose={onClose}>
      <form onSubmit={handleSubmit}>
        <label className="field">
          <span>To</span>
          {usersQuery.isPending ? (
            <Spinner label="Loading people…" />
          ) : (
            <select value={recipientId} onChange={(e) => setRecipientId(e.target.value)}>
              <option value="" disabled>
                Select a person…
              </option>
              {usersQuery.data?.map((teamUser) => (
                <option key={teamUser.id} value={teamUser.id}>
                  {teamUser.full_name} ({teamUser.email})
                </option>
              ))}
            </select>
          )}
        </label>
        <label className="field">
          <span>Title</span>
          <input required value={title} onChange={(e) => setTitle(e.target.value)} disabled={sendMutation.isPending} />
        </label>
        <label className="field">
          <span>Message</span>
          <textarea
            required
            rows={4}
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            disabled={sendMutation.isPending}
          />
        </label>

        {error && <Alert>{error}</Alert>}

        <div className="btn-group" style={{ marginTop: "1rem" }}>
          <button type="submit" className="btn btn-primary" disabled={sendMutation.isPending}>
            {sendMutation.isPending ? <Spinner label="Sending…" /> : "Send message"}
          </button>
          <button type="button" className="btn btn-ghost" onClick={onClose} disabled={sendMutation.isPending}>
            Cancel
          </button>
        </div>
      </form>
    </Modal>
  );
}
