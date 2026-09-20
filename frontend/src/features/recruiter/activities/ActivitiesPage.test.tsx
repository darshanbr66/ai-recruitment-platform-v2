import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError } from "../../../lib/apiClient";
import { ToastProvider } from "../../../shared/components/ToastContext";
import type { ActivityResponse } from "../../../types/activity";
import * as activitiesApi from "./api";
import { ActivitiesPage } from "./ActivitiesPage";

let mockRoles: string[] = ["ORG_ADMIN"];
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token", user: { roles: mockRoles } }),
}));

function makeEntry(n: number, overrides: Partial<ActivityResponse> = {}): ActivityResponse {
  return {
    id: `activity-${n}`,
    actor_name: "Acme Admin",
    action: "CANDIDATE_DELETED",
    entity_type: "candidate",
    entity_id: `cand-${n}`,
    entity_label: `Candidate ${n}`,
    description: `Candidate ${n} was deleted.`,
    reason: "Duplicate",
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

const entries = [1, 2, 3, 4].map((n) => makeEntry(n));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <ActivitiesPage />
      </ToastProvider>
    </QueryClientProvider>,
  );
}

function rowCheckbox(n: number) {
  return screen.getByRole("checkbox", { name: new RegExp(`Select activity ${n}:`) });
}

describe("ActivitiesPage delete", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockRoles = ["ORG_ADMIN"];
    vi.spyOn(activitiesApi, "countActivities").mockResolvedValue({ total: entries.length });
  });

  it("lets an org admin delete an entry after confirming", async () => {
    const list = vi.spyOn(activitiesApi, "listActivities").mockResolvedValue([entries[0]]);
    const remove = vi.spyOn(activitiesApi, "deleteActivity").mockResolvedValue(undefined);

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));

    // Nothing is deleted until the confirmation is accepted.
    expect(remove).not.toHaveBeenCalled();
    const dialog = await screen.findByRole("alertdialog");
    list.mockResolvedValue([]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete entry" }));

    await screen.findByText("No activity recorded yet");
    expect(remove).toHaveBeenCalledWith("activity-1", "test-token");
  });

  it("does not delete when the confirmation is cancelled", async () => {
    vi.spyOn(activitiesApi, "listActivities").mockResolvedValue([entries[0]]);
    const remove = vi.spyOn(activitiesApi, "deleteActivity").mockResolvedValue(undefined);

    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

    expect(remove).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("offers no delete or selection controls to non-admin roles", async () => {
    mockRoles = ["RECRUITER"];
    vi.spyOn(activitiesApi, "listActivities").mockResolvedValue(entries);

    renderPage();

    await screen.findByText("Candidate 1");
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete All" })).not.toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("toolbar", { name: "Bulk actions" })).not.toBeInTheDocument();
  });
});

describe("ActivitiesPage selection and bulk delete", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockRoles = ["ORG_ADMIN"];
    vi.spyOn(activitiesApi, "countActivities").mockResolvedValue({ total: entries.length });
    vi.spyOn(activitiesApi, "listActivities").mockResolvedValue(entries);
  });

  it("shows no bulk toolbar until something is selected, then a live count", async () => {
    renderPage();
    await screen.findByText("Candidate 1");
    expect(screen.queryByRole("toolbar", { name: "Bulk actions" })).not.toBeInTheDocument();

    fireEvent.click(rowCheckbox(1));
    const toolbar = screen.getByRole("toolbar", { name: "Bulk actions" });
    expect(within(toolbar).getByText("1 selected")).toBeInTheDocument();

    fireEvent.click(rowCheckbox(2));
    fireEvent.click(rowCheckbox(4));
    expect(within(toolbar).getByText("3 selected")).toBeInTheDocument();
    expect(rowCheckbox(3)).not.toBeChecked();

    fireEvent.click(rowCheckbox(2));
    expect(within(toolbar).getByText("2 selected")).toBeInTheDocument();
  });

  it("selects and clears every visible row from the header checkbox", async () => {
    renderPage();
    await screen.findByText("Candidate 1");
    const header = screen.getByRole("checkbox", {
      name: "Select all visible activities",
    }) as HTMLInputElement;

    fireEvent.click(rowCheckbox(1));
    expect(header.indeterminate).toBe(true); // some, not all
    expect(header).not.toBeChecked();

    fireEvent.click(header);
    expect(screen.getByText("4 selected")).toBeInTheDocument();
    expect(header).toBeChecked();
    expect(header.indeterminate).toBe(false);
    for (const n of [1, 2, 3, 4]) expect(rowCheckbox(n)).toBeChecked();

    fireEvent.click(header);
    expect(screen.queryByRole("toolbar", { name: "Bulk actions" })).not.toBeInTheDocument();
    for (const n of [1, 2, 3, 4]) expect(rowCheckbox(n)).not.toBeChecked();
  });

  it("Clear empties the selection without deleting anything", async () => {
    const remove = vi.spyOn(activitiesApi, "deleteSelectedActivities");
    renderPage();
    await screen.findByText("Candidate 1");

    fireEvent.click(rowCheckbox(1));
    fireEvent.click(rowCheckbox(3));
    fireEvent.click(screen.getByRole("button", { name: "Clear" }));

    expect(screen.queryByRole("toolbar", { name: "Bulk actions" })).not.toBeInTheDocument();
    expect(rowCheckbox(1)).not.toBeChecked();
    expect(remove).not.toHaveBeenCalled();
  });

  it("deletes exactly the selected activities after confirmation, then refreshes and clears", async () => {
    const remove = vi
      .spyOn(activitiesApi, "deleteSelectedActivities")
      .mockResolvedValue({ deleted: 3 });
    const list = vi.spyOn(activitiesApi, "listActivities");
    renderPage();
    await screen.findByText("Candidate 1");

    fireEvent.click(rowCheckbox(1));
    fireEvent.click(rowCheckbox(2));
    fireEvent.click(rowCheckbox(4));
    fireEvent.click(screen.getByRole("button", { name: "Delete Selected" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Delete 3 selected activities?")).toBeInTheDocument();
    expect(remove).not.toHaveBeenCalled(); // not until confirmed

    list.mockResolvedValue([entries[2]]);
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete 3 activities" }));

    await waitFor(() =>
      expect(remove).toHaveBeenCalledWith(
        ["activity-1", "activity-2", "activity-4"],
        "test-token",
      ),
    );
    expect(await screen.findByText("Deleted 3 activities.")).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText("Candidate 1")).not.toBeInTheDocument());
    expect(screen.getByText("Candidate 3")).toBeInTheDocument();
    expect(screen.queryByRole("toolbar", { name: "Bulk actions" })).not.toBeInTheDocument();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("keeps the selection and deletes nothing when the confirmation is cancelled", async () => {
    const remove = vi.spyOn(activitiesApi, "deleteSelectedActivities");
    renderPage();
    await screen.findByText("Candidate 1");

    fireEvent.click(rowCheckbox(1));
    fireEvent.click(rowCheckbox(2));
    fireEvent.click(screen.getByRole("button", { name: "Delete Selected" }));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

    expect(remove).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(screen.getByText("2 selected")).toBeInTheDocument();
  });

  it("reports a failed bulk delete and does not claim success", async () => {
    vi.spyOn(activitiesApi, "deleteSelectedActivities").mockRejectedValue(
      new ApiError("You do not have permission to perform this action.", 403, "forbidden"),
    );
    renderPage();
    await screen.findByText("Candidate 1");

    fireEvent.click(rowCheckbox(1));
    fireEvent.click(screen.getByRole("button", { name: "Delete Selected" }));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Delete 1 activity" }));

    expect(
      await screen.findByText("You do not have permission to perform this action."),
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Deleted /)).not.toBeInTheDocument();
  });

  it("drops the selection when a filter changes so hidden rows can't be deleted", async () => {
    renderPage();
    await screen.findByText("Candidate 1");

    fireEvent.click(rowCheckbox(1));
    expect(screen.getByText("1 selected")).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/Search by actor/), { target: { value: "x" } });

    expect(screen.queryByRole("toolbar", { name: "Bulk actions" })).not.toBeInTheDocument();
  });

  it("Delete All shows the organization-wide count and needs typed confirmation", async () => {
    vi.spyOn(activitiesApi, "countActivities").mockResolvedValue({ total: 250 });
    const removeAll = vi.spyOn(activitiesApi, "deleteAllActivities").mockResolvedValue({ deleted: 250 });
    const list = vi.spyOn(activitiesApi, "listActivities");
    renderPage();
    await screen.findByText("Candidate 1");

    fireEvent.click(await screen.findByRole("button", { name: "Delete All" }));

    const dialog = await screen.findByRole("alertdialog");
    expect(
      within(dialog).getByText("Delete all activities for this organization?"),
    ).toBeInTheDocument();
    expect(within(dialog).getByText(/all 250 activities/)).toBeInTheDocument();
    expect(within(dialog).getByText(/Other organizations are not affected/)).toBeInTheDocument();

    // A stray click can't confirm it: the button stays disabled until the
    // word is typed exactly.
    const confirm = within(dialog).getByRole("button", { name: "Delete all activities" });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "delete" } });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(dialog).getByRole("textbox"), { target: { value: "DELETE" } });
    expect(confirm).toBeEnabled();
    expect(removeAll).not.toHaveBeenCalled();

    list.mockResolvedValue([]);
    fireEvent.click(confirm);

    await waitFor(() => expect(removeAll).toHaveBeenCalledWith("test-token"));
    expect(await screen.findByText("Deleted 250 activities.")).toBeInTheDocument();
    await screen.findByText("No activity recorded yet");
  });

  it("Delete All can be cancelled without deleting anything", async () => {
    const removeAll = vi.spyOn(activitiesApi, "deleteAllActivities");
    renderPage();
    await screen.findByText("Candidate 1");

    fireEvent.click(await screen.findByRole("button", { name: "Delete All" }));
    const dialog = await screen.findByRole("alertdialog");
    fireEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));

    expect(removeAll).not.toHaveBeenCalled();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("explains when the table shows only part of the organization's entries", async () => {
    vi.spyOn(activitiesApi, "countActivities").mockResolvedValue({ total: 250 });
    renderPage();

    expect(await screen.findByText(/Showing the latest 4 of 250 entries/)).toBeInTheDocument();
  });
});

describe("ActivitiesPage timeline", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    mockRoles = ["ORG_ADMIN"];
  });

  const DAY = 24 * 60 * 60 * 1000;

  it("groups entries under a heading per day, newest first", async () => {
    const list = [
      makeEntry(1, { created_at: new Date().toISOString() }),
      makeEntry(2, { created_at: new Date(Date.now() - DAY).toISOString() }),
      makeEntry(3, { created_at: new Date(Date.now() - 30 * DAY).toISOString() }),
    ];
    vi.spyOn(activitiesApi, "listActivities").mockResolvedValue(list);
    vi.spyOn(activitiesApi, "countActivities").mockResolvedValue({ total: list.length });

    renderPage();
    await screen.findByText("Candidate 1");

    const headings = screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent);
    expect(headings[0]).toBe("Today");
    expect(headings[1]).toBe("Yesterday");
    expect(headings).toHaveLength(3);
    // The older date is written out rather than shown as a relative word.
    expect(headings[2]).not.toMatch(/today|yesterday/i);
  });

  it("keeps two entries from the same day under one heading", async () => {
    const list = [makeEntry(1), makeEntry(2)];
    vi.spyOn(activitiesApi, "listActivities").mockResolvedValue(list);
    vi.spyOn(activitiesApi, "countActivities").mockResolvedValue({ total: 2 });

    renderPage();
    await screen.findByText("Candidate 1");

    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(1);
    expect(screen.getAllByRole("listitem")).toHaveLength(2);
  });

  it("marks a selected entry", async () => {
    vi.spyOn(activitiesApi, "listActivities").mockResolvedValue([makeEntry(1)]);
    vi.spyOn(activitiesApi, "countActivities").mockResolvedValue({ total: 1 });

    renderPage();
    await screen.findByText("Candidate 1");
    fireEvent.click(rowCheckbox(1));
    expect(rowCheckbox(1).closest("li")).toHaveClass("is-selected");
  });

  it("hides selection and delete controls from users who cannot delete", async () => {
    mockRoles = ["RECRUITER"];
    vi.spyOn(activitiesApi, "listActivities").mockResolvedValue([makeEntry(1)]);
    vi.spyOn(activitiesApi, "countActivities").mockResolvedValue({ total: 1 });

    renderPage();
    await screen.findByText("Candidate 1");

    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });
});
