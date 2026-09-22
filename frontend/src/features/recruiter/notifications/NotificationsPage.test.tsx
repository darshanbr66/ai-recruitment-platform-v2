import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../../shared/components/ToastContext";
import type { NotificationResponse } from "../../../types/notification";
import type { UserResponse } from "../../../types/auth";
import * as authApi from "../../auth/api";
import * as teamApi from "../team/api";
import * as api from "./api";
import { NotificationsPage } from "./NotificationsPage";

let mockUser: { full_name: string; roles: string[] } = { full_name: "Acme Admin", roles: ["ORG_ADMIN"] };
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token", user: mockUser }),
}));

function makeNotification(overrides: Partial<NotificationResponse> = {}): NotificationResponse {
  return {
    id: "notif-1",
    type: "ANNOUNCEMENT",
    title: "Maintenance",
    message: "Office closed tomorrow.",
    created_at: new Date().toISOString(),
    read_at: null,
    sender_id: "user-1",
    sender_name: "Acme Admin",
    related_entity_type: null,
    related_entity_id: null,
    ...overrides,
  };
}

const sampleUsers: UserResponse[] = [
  { id: "user-2", organization_id: "org-1", email: "rita@example.com", full_name: "Rita Recruiter", is_active: true, created_at: new Date().toISOString(), roles: ["RECRUITER"] },
];

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <NotificationsPage />
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("NotificationsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockUser = { full_name: "Acme Admin", roles: ["ORG_ADMIN"] };
    vi.spyOn(authApi, "listUsers").mockResolvedValue(sampleUsers);
    vi.spyOn(teamApi, "listDepartments").mockResolvedValue([]);
  });

  it("shows a skeleton then the notification list", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([makeNotification()]);

    const { container } = renderPage();
    expect(container.querySelector(".skeleton-list")).toBeInTheDocument();

    await screen.findByText("Maintenance");
    expect(screen.getByText("Office closed tomorrow.")).toBeInTheDocument();
    expect(screen.getByText("From Acme Admin")).toBeInTheDocument();
  });

  it("shows a professional empty state when there is nothing", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("No notifications yet")).toBeInTheDocument();
  });

  it("marks a notification as read when its card is opened", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([makeNotification()]);
    const markSpy = vi.spyOn(api, "acknowledgeNotifications").mockResolvedValue({ updated: 1 });

    renderPage();
    await screen.findByText("Maintenance");

    fireEvent.click(screen.getByText("Maintenance"));

    await waitFor(() => expect(markSpy).toHaveBeenCalledWith(["notif-1"], "test-token"));
    expect(await screen.findByRole("dialog", { name: "Maintenance" })).toBeInTheDocument();
  });

  it("does not re-acknowledge an already-read notification when opened", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([
      makeNotification({ read_at: new Date().toISOString() }),
    ]);
    const markSpy = vi.spyOn(api, "acknowledgeNotifications").mockResolvedValue({ updated: 0 });

    renderPage();
    await screen.findByText("Maintenance");
    fireEvent.click(screen.getByText("Maintenance"));

    await screen.findByRole("dialog", { name: "Maintenance" });
    expect(markSpy).not.toHaveBeenCalled();
  });

  it("deletes a notification from its detail view after confirmation", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([
      makeNotification({ read_at: new Date().toISOString() }),
    ]);
    const deleteSpy = vi.spyOn(api, "deleteNotification").mockResolvedValue(undefined);

    renderPage();
    await screen.findByText("Maintenance");
    fireEvent.click(screen.getByText("Maintenance"));

    const dialog = await screen.findByRole("dialog", { name: "Maintenance" });
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete" }));

    const confirm = await screen.findByRole("alertdialog", { name: "Delete this notification?" });
    fireEvent.click(within(confirm).getByRole("button", { name: /delete notification/i }));

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("notif-1", "test-token"));
  });

  it("marks all notifications as read and disables the button when nothing is unread", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([makeNotification({ read_at: new Date().toISOString() })]);
    renderPage();

    await screen.findByText("Maintenance");
    expect(screen.getByRole("button", { name: /mark all as read/i })).toBeDisabled();
  });

  it("shows a 'View candidate' link in the detail view when the notification references one", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([
      makeNotification({ related_entity_type: "CANDIDATE", related_entity_id: "cand-9" }),
    ]);

    renderPage();
    await screen.findByText("Maintenance");
    fireEvent.click(screen.getByText("Maintenance"));

    const dialog = await screen.findByRole("dialog", { name: "Maintenance" });
    expect(within(dialog).getByRole("link", { name: "View candidate" })).toHaveAttribute(
      "href",
      "/recruiter/candidates/cand-9",
    );
  });

  it("shows the announcement composer only for ORG_ADMIN", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([]);
    mockUser = { full_name: "Rita Recruiter", roles: ["RECRUITER"] };

    renderPage();
    await screen.findByText("No notifications yet");

    expect(screen.queryByRole("button", { name: "+ Announcement" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /message a colleague/i })).toBeInTheDocument();
  });

  it("sends an announcement to everyone", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([]);
    const announceSpy = vi.spyOn(api, "sendAnnouncement").mockResolvedValue({ recipients_notified: 3 });

    renderPage();
    await screen.findByText("No notifications yet");

    fireEvent.click(screen.getByRole("button", { name: "+ Announcement" }));
    const dialog = await screen.findByRole("dialog", { name: "Send an announcement" });
    fireEvent.change(within(dialog).getByLabelText("Title"), { target: { value: "Holiday" } });
    fireEvent.change(within(dialog).getByLabelText("Message"), { target: { value: "Office closed Monday." } });
    fireEvent.click(within(dialog).getByRole("button", { name: /send announcement/i }));

    await waitFor(() =>
      expect(announceSpy).toHaveBeenCalledWith(
        { title: "Holiday", message: "Office closed Monday.", target: "EVERYONE", department_id: null, user_ids: [] },
        "test-token",
      ),
    );
    expect(await screen.findByText(/announcement sent to 3 recipient/i)).toBeInTheDocument();
  });

  it("sends a direct message to a selected colleague", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([]);
    const sendSpy = vi.spyOn(api, "sendDirectMessage").mockResolvedValue(makeNotification({ type: "DIRECT_MESSAGE" }));

    renderPage();
    await screen.findByText("No notifications yet");

    fireEvent.click(screen.getByRole("button", { name: /message a colleague/i }));
    const dialog = await screen.findByRole("dialog", { name: "Message a colleague" });
    await within(dialog).findByText(/rita recruiter/i);
    fireEvent.change(within(dialog).getByLabelText("To"), { target: { value: "user-2" } });
    fireEvent.change(within(dialog).getByLabelText("Title"), { target: { value: "Quick check-in" } });
    fireEvent.change(within(dialog).getByLabelText("Message"), { target: { value: "Got a minute?" } });
    fireEvent.click(within(dialog).getByRole("button", { name: /send message/i }));

    await waitFor(() =>
      expect(sendSpy).toHaveBeenCalledWith(
        { recipient_user_id: "user-2", title: "Quick check-in", message: "Got a minute?" },
        "test-token",
      ),
    );
  });

  it("filters to unread only", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([makeNotification()]);

    renderPage();
    await screen.findByText("Maintenance");

    fireEvent.click(screen.getByRole("button", { name: /unread/i }));

    await waitFor(() =>
      expect(api.listAllNotifications).toHaveBeenCalledWith("test-token", {
        unreadOnly: true,
        search: undefined,
        limit: 100,
      }),
    );
  });

  it("searches received notifications", async () => {
    const listSpy = vi.spyOn(api, "listAllNotifications").mockResolvedValue([makeNotification()]);
    renderPage();
    await screen.findByText("Maintenance");

    fireEvent.change(screen.getByPlaceholderText("Search notifications…"), { target: { value: "office" } });

    await waitFor(() =>
      expect(listSpy).toHaveBeenLastCalledWith("test-token", {
        unreadOnly: false,
        search: "office",
        limit: 100,
      }),
    );
  });

  it("switches to the Sent tab and lists broadcasts sent by the caller", async () => {
    vi.spyOn(api, "listAllNotifications").mockResolvedValue([]);
    vi.spyOn(api, "listSentNotifications").mockResolvedValue([
      {
        id: "sent-1",
        type: "ANNOUNCEMENT",
        title: "Policy update",
        message: "New policy in effect starting Monday.",
        created_at: new Date().toISOString(),
        target_description: "Everyone in the organization",
        recipient_count: 4,
        read_count: 2,
        recipient_name: null,
      },
    ]);

    renderPage();
    await screen.findByText("No notifications yet");

    fireEvent.click(screen.getByRole("button", { name: "Sent" }));

    await screen.findByText("Policy update");
    expect(screen.getByText(/2\/4 read/)).toBeInTheDocument();
  });
});
