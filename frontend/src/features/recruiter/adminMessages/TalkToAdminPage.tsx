import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { Avatar } from "../../../shared/components/Avatar";
import { EmptyState } from "../../../shared/components/EmptyState";
import { SkeletonCard } from "../../../shared/components/Skeleton";
import { Spinner } from "../../../shared/components/Spinner";
import type {
  AdminConversationDetail,
  AdminMessageResponse,
} from "../../../types/adminMessage";
import { useAuth } from "../../auth/AuthContext";
import {
  getAdminConversation,
  getMyAdminConversation,
  listAdminConversations,
  markAdminConversationRead,
  markMyAdminConversationRead,
  replyToAdminConversation,
  sendMessageToAdmins,
} from "./api";

/** Same cadence as the notification badge — this is a conversation, not a
 * live chat, and the backend is a plain REST endpoint (no WebSockets in
 * this architecture). */
const POLL_MS = 30_000;

const UNREAD_KEY = ["admin-messages", "unread-count"];
const MINE_KEY = ["admin-messages", "mine"];
const CONVERSATIONS_KEY = ["admin-messages", "conversations"];

function formatTimestamp(iso: string) {
  const at = new Date(iso);
  const today = new Date();
  const sameDay = at.toDateString() === today.toDateString();
  return sameDay
    ? at.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })
    : at.toLocaleString(undefined, {
        day: "numeric",
        month: "short",
        hour: "numeric",
        minute: "2-digit",
      });
}

/**
 * The messages themselves. `ownSide` says which side "you" are on, so the
 * same component serves the staff view (their messages on the right) and
 * the admin view (admin messages on the right) without either needing to
 * know about the other.
 */
function MessageThread({
  messages,
  ownSide,
  emptyHint,
}: {
  messages: AdminMessageResponse[];
  ownSide: "staff" | "admin";
  emptyHint: string;
}) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "nearest" });
  }, [messages.length]);

  if (messages.length === 0) {
    return (
      <EmptyState icon="inbox" title="No messages yet" compact>
        {emptyHint}
      </EmptyState>
    );
  }

  return (
    <ol className="admin-thread" aria-label="Conversation">
      {messages.map((message) => {
        const mine = ownSide === "admin" ? message.from_admin : !message.from_admin;
        return (
          <li key={message.id} className={`admin-message${mine ? " is-own" : ""}`}>
            <div className="admin-message-bubble">
              <div className="admin-message-meta">
                <strong>{message.sender_name ?? (message.from_admin ? "Admin" : "Team member")}</strong>
                <span className="muted">{formatTimestamp(message.created_at)}</span>
                {/* Only meaningful on your own messages: whether the other
                    side has opened it yet. */}
                {mine && (
                  <span className="muted admin-message-receipt">
                    {message.read_at ? "Read" : "Sent"}
                  </span>
                )}
              </div>
              <p className="admin-message-body">{message.body}</p>
            </div>
          </li>
        );
      })}
      <div ref={endRef} />
    </ol>
  );
}

function Composer({
  onSend,
  pending,
  error,
  placeholder,
  label,
}: {
  onSend: (body: string) => void;
  pending: boolean;
  error: string | null;
  placeholder: string;
  label: string;
}) {
  const [body, setBody] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = body.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setBody("");
  }

  return (
    <form onSubmit={handleSubmit} className="admin-composer">
      <label className="field">
        <span>{label}</span>
        <textarea
          rows={3}
          value={body}
          onChange={(e) => setBody(e.target.value)}
          placeholder={placeholder}
          disabled={pending}
        />
      </label>
      {error && <Alert>{error}</Alert>}
      <div className="btn-group">
        <button type="submit" className="btn btn-primary" disabled={pending || !body.trim()}>
          {pending ? <Spinner label="Sending…" /> : "Send message"}
        </button>
      </div>
    </form>
  );
}

/** A staff member's own thread with the admins. */
function MyConversation() {
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const conversationQuery = useQuery({
    queryKey: MINE_KEY,
    queryFn: () => getMyAdminConversation(token),
    enabled: accessToken !== null,
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
  });

  const conversation = conversationQuery.data;
  const unreadFromAdmin =
    conversation?.messages.some((m) => m.from_admin && m.read_at === null) ?? false;

  // Opening the thread marks the admins' replies read. Keyed on the flag so
  // it fires again when a new reply arrives while the page is open.
  useEffect(() => {
    if (!unreadFromAdmin) return;
    void markMyAdminConversationRead(token).then(() => {
      void queryClient.invalidateQueries({ queryKey: MINE_KEY });
      void queryClient.invalidateQueries({ queryKey: UNREAD_KEY });
    });
  }, [unreadFromAdmin, token, queryClient]);

  const sendMutation = useMutation({
    mutationFn: (body: string) => sendMessageToAdmins(body, token),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: MINE_KEY });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Unable to reach the server."),
  });

  if (conversationQuery.isPending) return <SkeletonCard lines={5} />;
  if (conversationQuery.isError) {
    return (
      <Alert>
        {conversationQuery.error instanceof ApiError
          ? conversationQuery.error.message
          : "Could not load your conversation."}
      </Alert>
    );
  }

  return (
    <section className="card">
      <h2>Your conversation with the admins</h2>
      <p className="muted">
        Messages are visible to the administrators of your organization only.
      </p>
      <MessageThread
        messages={conversation?.messages ?? []}
        ownSide="staff"
        emptyHint="Send the first message and an administrator will reply here."
      />
      <Composer
        label="Message"
        placeholder="Ask a question or raise something with your admin team…"
        onSend={(body) => sendMutation.mutate(body)}
        pending={sendMutation.isPending}
        error={error}
      />
    </section>
  );
}

/** The admin side: every conversation in the organization. */
function AdminInbox() {
  const { accessToken } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const conversationsQuery = useQuery({
    queryKey: CONVERSATIONS_KEY,
    queryFn: () => listAdminConversations(token),
    enabled: accessToken !== null,
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
  });

  const detailQuery = useQuery({
    queryKey: [...CONVERSATIONS_KEY, selectedId],
    queryFn: () => getAdminConversation(selectedId as string, token),
    enabled: accessToken !== null && selectedId !== null,
    refetchInterval: POLL_MS,
    refetchIntervalInBackground: false,
  });

  const detail: AdminConversationDetail | undefined = detailQuery.data;
  const unreadFromStaff =
    detail?.messages.some((m) => !m.from_admin && m.read_at === null) ?? false;

  useEffect(() => {
    if (!selectedId || !unreadFromStaff) return;
    void markAdminConversationRead(selectedId, token).then(() => {
      void queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY });
      void queryClient.invalidateQueries({ queryKey: UNREAD_KEY });
    });
  }, [selectedId, unreadFromStaff, token, queryClient]);

  const replyMutation = useMutation({
    mutationFn: (body: string) => replyToAdminConversation(selectedId as string, body, token),
    onSuccess: () => {
      setError(null);
      void queryClient.invalidateQueries({ queryKey: CONVERSATIONS_KEY });
    },
    onError: (err) =>
      setError(err instanceof ApiError ? err.message : "Unable to reach the server."),
  });

  if (conversationsQuery.isPending) return <SkeletonCard lines={5} />;
  if (conversationsQuery.isError) {
    return (
      <Alert>
        {conversationsQuery.error instanceof ApiError
          ? conversationsQuery.error.message
          : "Could not load conversations."}
      </Alert>
    );
  }

  const conversations = conversationsQuery.data ?? [];

  return (
    <div className="detail-grid">
      <section className="card">
        <h2>{detail ? detail.employee_name : "Select a conversation"}</h2>
        {detail ? (
          <>
            <p className="muted">{detail.employee_email}</p>
            <MessageThread
              messages={detail.messages}
              ownSide="admin"
              emptyHint="No messages in this conversation yet."
            />
            <Composer
              label="Reply"
              placeholder="Write your reply…"
              onSend={(body) => replyMutation.mutate(body)}
              pending={replyMutation.isPending}
              error={error}
            />
          </>
        ) : (
          <EmptyState icon="inbox" title="Nothing selected" compact>
            Choose a team member on the right to read and reply to their messages.
          </EmptyState>
        )}
      </section>

      <section className="card">
        <h2>Inbox</h2>
        {conversations.length === 0 ? (
          <EmptyState icon="inbox" title="No conversations" compact>
            Messages from your team will appear here.
          </EmptyState>
        ) : (
          <ul className="admin-conversation-list">
            {conversations.map((conversation) => (
              <li key={conversation.id}>
                <button
                  type="button"
                  className={`admin-conversation-item${
                    conversation.id === selectedId ? " is-selected" : ""
                  }`}
                  aria-current={conversation.id === selectedId}
                  onClick={() => setSelectedId(conversation.id)}
                >
                  <Avatar name={conversation.employee_name} />
                  <span className="admin-conversation-text">
                    <span className="admin-conversation-name">
                      {conversation.employee_name}
                      {conversation.unread_count > 0 && (
                        <span className="badge badge-warn">{conversation.unread_count} new</span>
                      )}
                    </span>
                    <span className="muted admin-conversation-preview">
                      {conversation.last_message_from_admin ? "You: " : ""}
                      {conversation.last_message_preview ?? "No messages yet"}
                    </span>
                    {conversation.last_message_at && (
                      <span className="muted admin-conversation-time">
                        {formatTimestamp(conversation.last_message_at)}
                      </span>
                    )}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/**
 * Talk to Admin. Which side you see follows the backend's permissions:
 * `admin_message.manage` (ORG_ADMIN) gets the organization's inbox,
 * `admin_message.send` (everyone else on staff) gets their own thread.
 * The role check here only picks the view — both sets of endpoints
 * re-check the permission and the organization server-side.
 */
export function TalkToAdminPage() {
  const { user } = useAuth();
  const isOrgAdmin = user?.roles.includes("ORG_ADMIN") ?? false;

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Talk to Admin</h1>
          <p className="muted">
            {isOrgAdmin
              ? "Messages from your team, and your replies."
              : "A direct line to your organization's administrators."}
          </p>
        </div>
      </div>
      {isOrgAdmin ? <AdminInbox /> : <MyConversation />}
    </div>
  );
}
