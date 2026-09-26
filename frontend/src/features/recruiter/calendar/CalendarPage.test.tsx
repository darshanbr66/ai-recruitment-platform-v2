import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../../shared/components/ToastContext";
import type { CalendarEventResponse } from "../../../types/calendar";
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

/** The directory the attendee selector renders — `user-1` is the signed-in
 * organizer, who is never offered as an attendee of their own event. */
const ATTENDEE_OPTIONS = [
  { id: "user-1", full_name: "Acme Admin", email: "admin@acme.test" },
  { id: "user-2", full_name: "Rita Recruiter", email: "rita@acme.test" },
  { id: "user-3", full_name: "Hari Hiring", email: "hari@acme.test" },
];

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

/** Opens the new-event modal and the attendee popover inside it — the state
 * the attendee tests start from. */
async function openAttendeePopover() {
  renderPage();
  await screen.findByText("No events in this range");

  fireEvent.click(screen.getByRole("button", { name: "+ New event" }));
  const dialog = await screen.findByRole("dialog", { name: "New event" });
  const search = await within(dialog).findByLabelText("Search attendees");
  // Focus the way a click in the browser would, then open the popover.
  search.focus();
  fireEvent.click(search);
  await within(dialog).findByRole("listbox");
  return { dialog, search };
}

describe("CalendarPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(candidatesApi, "listCandidates").mockResolvedValue([]);
    vi.spyOn(jobsApi, "listJobs").mockResolvedValue([]);
    vi.spyOn(applicationsApi, "listApplications").mockResolvedValue([]);
    vi.spyOn(api, "listAttendeeOptions").mockResolvedValue(ATTENDEE_OPTIONS);
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

  it("submits the attendees picked in the selector, and drops one removed by its chip", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([]);
    const createSpy = vi.spyOn(api, "createEvent").mockResolvedValue(makeEvent());

    const { dialog } = await openAttendeePopover();
    fireEvent.change(within(dialog).getByLabelText("Title"), { target: { value: "Panel interview" } });

    // The organizer themselves is not offered as an attendee.
    expect(within(dialog).queryByRole("option", { name: /Acme Admin/ })).not.toBeInTheDocument();

    fireEvent.click(within(dialog).getByRole("option", { name: /Rita Recruiter/ }));
    fireEvent.click(within(dialog).getByRole("option", { name: /Hari Hiring/ }));

    // Remove one again via its chip — the other stays selected.
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove Hari Hiring" }));

    fireEvent.click(within(dialog).getByRole("button", { name: /create event/i }));

    await waitFor(() =>
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Panel interview", attendee_ids: ["user-2"] }),
        "test-token",
      ),
    );
  });

  it("keeps the directory out of the modal until the attendee search is opened", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([]);

    renderPage();
    await screen.findByText("No events in this range");

    fireEvent.click(screen.getByRole("button", { name: "+ New event" }));
    const dialog = await screen.findByRole("dialog", { name: "New event" });

    // The options query has resolved (the search input is rendered), yet no
    // part of the directory is in the DOM taking up space.
    await within(dialog).findByLabelText("Search attendees");
    expect(within(dialog).queryByRole("listbox")).not.toBeInTheDocument();
    expect(within(dialog).queryByText("rita@acme.test")).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("option", { name: /Rita Recruiter/ })).not.toBeInTheDocument();
  });

  it("opens the attendee popover on focus and closes it on an outside click", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([]);

    renderPage();
    await screen.findByText("No events in this range");

    fireEvent.click(screen.getByRole("button", { name: "+ New event" }));
    const dialog = await screen.findByRole("dialog", { name: "New event" });
    const search = await within(dialog).findByLabelText("Search attendees");

    search.focus();
    fireEvent.focus(search);

    const listbox = await within(dialog).findByRole("listbox");
    expect(within(listbox).getByRole("option", { name: /Rita Recruiter/ })).toBeInTheDocument();
    expect(within(listbox).getByRole("option", { name: /Hari Hiring/ })).toBeInTheDocument();
    expect(search).toHaveAttribute("aria-expanded", "true");

    fireEvent.mouseDown(document.body);

    await waitFor(() => expect(within(dialog).queryByRole("listbox")).not.toBeInTheDocument());
    expect(search).toHaveAttribute("aria-expanded", "false");
  });

  it("filters the attendee popover by name or email as the user types", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([]);

    const { dialog, search } = await openAttendeePopover();

    fireEvent.change(search, { target: { value: "hari@acme" } });
    expect(within(dialog).getByRole("option", { name: /Hari Hiring/ })).toBeInTheDocument();
    expect(within(dialog).queryByRole("option", { name: /Rita Recruiter/ })).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: "Rita" } });
    expect(within(dialog).getByRole("option", { name: /Rita Recruiter/ })).toBeInTheDocument();
    expect(within(dialog).queryByRole("option", { name: /Hari Hiring/ })).not.toBeInTheDocument();

    fireEvent.change(search, { target: { value: "nobody" } });
    expect(within(dialog).getByText(/No one matches/)).toBeInTheDocument();
  });

  it("turns a picked person into a chip and stops offering them again", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([]);

    const { dialog } = await openAttendeePopover();

    fireEvent.click(within(dialog).getByRole("option", { name: /Rita Recruiter/ }));

    // Chip appears with a remove control...
    const chips = within(dialog).getByRole("list", { name: "Selected attendees" });
    expect(within(chips).getByText("Rita Recruiter")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Remove Rita Recruiter" })).toBeInTheDocument();
    expect(within(dialog).getByText("1 attendee selected.")).toBeInTheDocument();

    // ...and she is no longer a selectable duplicate, while the popover stays
    // open on the rest of the directory.
    expect(within(dialog).queryByRole("option", { name: /Rita Recruiter/ })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("option", { name: /Hari Hiring/ })).toBeInTheDocument();

    // Removing the chip makes her selectable again.
    fireEvent.click(within(dialog).getByRole("button", { name: "Remove Rita Recruiter" }));
    expect(within(dialog).queryByRole("button", { name: "Remove Rita Recruiter" })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("option", { name: /Rita Recruiter/ })).toBeInTheDocument();
    expect(
      within(dialog).getByText("No attendees selected — the event will be yours alone."),
    ).toBeInTheDocument();
  });

  it("lets the keyboard walk the popover and pick a person with Enter", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([]);
    const createSpy = vi.spyOn(api, "createEvent").mockResolvedValue(makeEvent());

    renderPage();
    await screen.findByText("No events in this range");

    fireEvent.click(screen.getByRole("button", { name: "+ New event" }));
    const dialog = await screen.findByRole("dialog", { name: "New event" });
    fireEvent.change(within(dialog).getByLabelText("Title"), { target: { value: "Panel interview" } });

    const search = await within(dialog).findByLabelText("Search attendees");
    search.focus();

    // ArrowDown opens the popover, then moves the highlight to the second row.
    fireEvent.keyDown(search, { key: "ArrowDown" });
    await within(dialog).findByRole("listbox");
    fireEvent.keyDown(search, { key: "ArrowDown" });

    const hari = within(dialog).getByRole("option", { name: /Hari Hiring/ });
    expect(hari).toHaveAttribute("aria-selected", "true");
    expect(search).toHaveAttribute("aria-activedescendant", hari.id);

    fireEvent.keyDown(search, { key: "Enter" });
    expect(within(dialog).getByRole("button", { name: "Remove Hari Hiring" })).toBeInTheDocument();
    // Enter picked a person; it must not have submitted the form.
    expect(createSpy).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole("button", { name: /create event/i }));
    await waitFor(() =>
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({ title: "Panel interview", attendee_ids: ["user-3"] }),
        "test-token",
      ),
    );
  });

  it("keeps Escape on the popover from discarding the half-filled event form", async () => {
    vi.spyOn(api, "listEvents").mockResolvedValue([]);

    const { dialog, search } = await openAttendeePopover();

    fireEvent.keyDown(search, { key: "Escape" });

    await waitFor(() => expect(within(dialog).queryByRole("listbox")).not.toBeInTheDocument());
    // The event form itself is still open.
    expect(screen.getByRole("dialog", { name: "New event" })).toBeInTheDocument();
    expect(search).toBeInTheDocument();
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
