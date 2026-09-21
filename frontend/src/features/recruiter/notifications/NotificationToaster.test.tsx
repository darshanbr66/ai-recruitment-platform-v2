import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../../shared/components/ToastContext";
import type { NotificationResponse } from "../../../types/notification";
import * as api from "./api";
import { NotificationToaster } from "./NotificationToaster";

let mockAccessToken: string | null = "test-token";
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: mockAccessToken }),
}));

function makeNotification(
  n: number,
  overrides: Partial<NotificationResponse> = {},
): NotificationResponse {
  return {
    id: `notification-${n}`,
    type: "ASSESSMENT_STARTED",
    title: "Assessment started",
    message: "Darshan has started the Data Analyst assessment.",
    created_at: new Date(2026, 8, 21, 10, n).toISOString(),
    read_at: null,
    ...overrides,
  };
}

function renderToaster() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const view = render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <NotificationToaster />
      </ToastProvider>
    </QueryClientProvider>,
  );
  return { queryClient, ...view };
}

describe("NotificationToaster", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockAccessToken = "test-token";
    vi.spyOn(api, "acknowledgeNotifications").mockResolvedValue({ updated: 1 });
  });

  it("shows a toast when the candidate has started the assessment, then acknowledges it", async () => {
    vi.spyOn(api, "listUnreadNotifications").mockResolvedValue([makeNotification(1)]);

    renderToaster();

    expect(await screen.findByText("Assessment started")).toBeInTheDocument();
    expect(screen.getByText("Darshan has started the Data Analyst assessment.")).toBeInTheDocument();
    await waitFor(() =>
      expect(api.acknowledgeNotifications).toHaveBeenCalledWith(["notification-1"], "test-token"),
    );
  });

  it("shows a toast when the candidate has submitted the assessment", async () => {
    vi.spyOn(api, "listUnreadNotifications").mockResolvedValue([
      makeNotification(2, {
        type: "ASSESSMENT_SUBMITTED",
        title: "Assessment submitted",
        message: "Darshan has submitted the Data Analyst assessment.",
      }),
    ]);

    renderToaster();

    expect(await screen.findByText("Assessment submitted")).toBeInTheDocument();
    expect(screen.getByText("Darshan has submitted the Data Analyst assessment.")).toBeInTheDocument();
  });

  it("does not show the same notification again when the server returns it again", async () => {
    // e.g. the acknowledgement failed, so the next poll still lists the row.
    const list = vi.spyOn(api, "listUnreadNotifications").mockResolvedValue([makeNotification(1)]);
    vi.spyOn(api, "acknowledgeNotifications").mockRejectedValue(new Error("offline"));

    const { queryClient } = renderToaster();
    await screen.findByText("Assessment started");

    // Real polls are 30s apart; space these out so each has its own timestamp.
    for (let poll = 0; poll < 2; poll++) {
      await new Promise((resolve) => setTimeout(resolve, 5));
      await queryClient.refetchQueries({ queryKey: ["notifications", "unread"] });
    }

    expect(list).toHaveBeenCalledTimes(3);
    expect(screen.getAllByText("Assessment started")).toHaveLength(1);
    // The failed acknowledgement is retried on every poll rather than dropped.
    await waitFor(() => expect(api.acknowledgeNotifications).toHaveBeenCalledTimes(3));
  });

  it("shows a later, different notification as its own toast", async () => {
    const list = vi.spyOn(api, "listUnreadNotifications").mockResolvedValueOnce([makeNotification(1)]);

    const { queryClient } = renderToaster();
    await screen.findByText("Assessment started");

    list.mockResolvedValue([
      makeNotification(2, {
        type: "ASSESSMENT_SUBMITTED",
        title: "Assessment submitted",
        message: "Darshan has submitted the Data Analyst assessment.",
      }),
    ]);
    await queryClient.refetchQueries({ queryKey: ["notifications", "unread"] });

    expect(await screen.findByText("Assessment submitted")).toBeInTheDocument();
    expect(screen.getAllByText("Assessment started")).toHaveLength(1);
  });

  it("folds a large backlog into a summary instead of flooding the screen", async () => {
    vi.spyOn(api, "listUnreadNotifications").mockResolvedValue(
      [1, 2, 3, 4, 5, 6, 7].map((n) => makeNotification(n, { message: `Candidate ${n} has started.` })),
    );

    renderToaster();

    expect(await screen.findByText("2 earlier assessment updates.")).toBeInTheDocument();
    // The five most recent are shown; the two oldest are folded away.
    expect(screen.getAllByText(/^Candidate \d has started\.$/)).toHaveLength(5);
    expect(screen.queryByText("Candidate 1 has started.")).not.toBeInTheDocument();
    expect(screen.getByText("Candidate 7 has started.")).toBeInTheDocument();
    await waitFor(() => expect(api.acknowledgeNotifications).toHaveBeenCalledTimes(1));
    expect(vi.mocked(api.acknowledgeNotifications).mock.calls[0][0]).toHaveLength(7);
  });

  it("shows nothing and acknowledges nothing when there are no unread notifications", async () => {
    const list = vi.spyOn(api, "listUnreadNotifications").mockResolvedValue([]);

    renderToaster();
    await waitFor(() => expect(list).toHaveBeenCalled());

    expect(screen.queryByRole("button", { name: "Dismiss" })).not.toBeInTheDocument();
    expect(api.acknowledgeNotifications).not.toHaveBeenCalled();
  });

  it("does not poll without a signed-in session", () => {
    mockAccessToken = null;
    const list = vi.spyOn(api, "listUnreadNotifications").mockResolvedValue([]);

    renderToaster();

    expect(list).not.toHaveBeenCalled();
  });
});
