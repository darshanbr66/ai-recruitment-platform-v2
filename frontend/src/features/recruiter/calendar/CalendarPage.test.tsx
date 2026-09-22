import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../../shared/components/ToastContext";
import type { CalendarEventResponse } from "../../../types/calendar";
import * as authApi from "../../auth/api";
import * as applicationsApi from "../applications/api";
import * as candidatesApi from "../candidates/api";
import * as jobsApi from "../jobs/api";
import * as api from "./api";
import { CalendarPage } from "./CalendarPage";

const mockUser = { id: "user-1", full_name: "Acme Admin", roles: ["ORG_ADMIN"] };
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token", user: mockUser }),
}));

function todayAt(hour: number): Date {
  const now = new Date();
  return new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, 0, 0);
}

function makeEvent(overrides: Partial<CalendarEventResponse> = {}): CalendarEventResponse {
  const start = todayAt(14);
  const end = todayAt(15);
  return {
    id: "event-1",
    title: "Interview with Priya",
    description: null,
    event_type: "INTERVIEW",
    status: "SCHEDULED",
    start_at: start.toISOString(),
    end_at: end.toISOString(),
    all_day: false,
    timezone: "Asia/Kolkata",
    organizer_id: "user-1",
    organizer_name: "Acme Admin",
    candidate_id: null,
    job_id: null,
    application_id: null,
    reminder_minutes_before: 15,
    reminder_fired_at: null,
    attendee_ids: [],
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function renderPage(initialEntries: string[] = ["/recruiter/calendar"]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <CalendarPage />
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("CalendarPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(candidatesApi, "listCandidates").mockResolvedValue([]);
    vi.spyOn(jobsApi, "listJobs").mockResolvedValue([]);
    vi.spyOn(applicationsApi, "listApplications").mockResolvedValue([]);
    vi.spyOn(authApi, "listUsers").mockResolvedValue([]);
  });

  it("shows a skeleton then renders the month grid with an event", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([makeEvent()]);

    const { container } = renderPage();
    expect(container.querySelector(".skeleton-list")).toBeInTheDocument();

    await screen.findByText("Interview with Priya");
    expect(screen.getByText("Calendar")).toBeInTheDocument();
  });

  it("shows a professional empty state when there are no events", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("No events in this range")).toBeInTheDocument();
  });

  it("switches between month, week and day views", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([makeEvent()]);

    renderPage();
    await screen.findByText("Interview with Priya");

    fireEvent.click(screen.getByRole("button", { name: "Week" }));
    await waitFor(() => expect(screen.getByText("Interview with Priya")).toBeInTheDocument());

    fireEvent.click(screen.getByRole("button", { name: "Day" }));
    await waitFor(() => expect(screen.getByText("Interview with Priya")).toBeInTheDocument());
  });

  it("creates a new event with the browser's timezone", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([]);
    const createSpy = vi.spyOn(api, "createEvent").mockResolvedValue(makeEvent());

    renderPage();
    await screen.findByText("No events in this range");

    fireEvent.click(screen.getByRole("button", { name: "+ New event" }));
    const dialog = await screen.findByRole("dialog", { name: "New event" });
    fireEvent.change(within(dialog).getByLabelText("Title"), {
      target: { value: "Panel interview" },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: /create event/i }));

    await waitFor(() =>
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({
          title: "Panel interview",
          event_type: "INTERVIEW",
          reminder_minutes_before: 15,
          timezone: expect.any(String),
        }),
        "test-token",
      ),
    );
  });

  it("opens the event detail view and allows the organizer to delete it", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([makeEvent()]);
    const deleteSpy = vi.spyOn(api, "deleteEvent").mockResolvedValue(undefined);

    renderPage();
    fireEvent.click(await screen.findByText("Interview with Priya"));

    const detail = await screen.findByRole("dialog", { name: "Interview with Priya" });
    fireEvent.click(within(detail).getByRole("button", { name: "Delete" }));

    const confirm = await screen.findByRole("alertdialog", { name: "Delete this event?" });
    fireEvent.click(within(confirm).getByRole("button", { name: /delete event/i }));

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("event-1", "test-token"));
  });

  it("hides edit/delete for events organized by someone else", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([
      makeEvent({ organizer_id: "user-2", organizer_name: "Rita Recruiter" }),
    ]);

    renderPage();
    fireEvent.click(await screen.findByText("Interview with Priya"));

    const detail = await screen.findByRole("dialog", { name: "Interview with Priya" });
    expect(within(detail).queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(within(detail).queryByRole("button", { name: "Delete" })).not.toBeInTheDocument();
  });

  it("re-queries with the search term", async () => {
    const listSpy = vi.spyOn(api, "listEvents").mockResolvedValue([]);
    renderPage();
    await screen.findByText("No events in this range");

    fireEvent.change(screen.getByPlaceholderText(/search events/i), { target: { value: "priya" } });

    await waitFor(() =>
      expect(listSpy).toHaveBeenLastCalledWith(
        "test-token",
        expect.objectContaining({ search: "priya" }),
      ),
    );
  });

  it("opens the linked event's detail view when arriving from a notification link", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([]);
    const getEventSpy = vi.spyOn(api, "getEvent").mockResolvedValue(makeEvent({ id: "event-77" }));

    renderPage(["/recruiter/calendar?event=event-77"]);

    await waitFor(() => expect(getEventSpy).toHaveBeenCalledWith("event-77", "test-token"));
    expect(await screen.findByRole("dialog", { name: "Interview with Priya" })).toBeInTheDocument();
  });
});
