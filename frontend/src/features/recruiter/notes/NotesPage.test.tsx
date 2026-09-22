import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ToastProvider } from "../../../shared/components/ToastContext";
import type { NoteResponse } from "../../../types/note";
import * as candidatesApi from "../candidates/api";
import * as jobsApi from "../jobs/api";
import * as api from "./api";
import { NotesPage } from "./NotesPage";

const mockUser = { id: "user-1", full_name: "Acme Admin", roles: ["ORG_ADMIN"] };
vi.mock("../../auth/AuthContext", () => ({
  useAuth: () => ({ accessToken: "test-token", user: mockUser }),
}));

function makeNote(overrides: Partial<NoteResponse> = {}): NoteResponse {
  return {
    id: "note-1",
    application_id: null,
    candidate_id: null,
    job_id: null,
    author_id: "user-1",
    author_name: "Acme Admin",
    title: "Follow up",
    body: "Follow up with candidate next Monday.",
    category: null,
    color: null,
    visibility: "PRIVATE",
    pinned: false,
    pinned_at: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    ...overrides,
  };
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <ToastProvider>
          <NotesPage />
        </ToastProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

describe("NotesPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(candidatesApi, "listCandidates").mockResolvedValue([]);
    vi.spyOn(jobsApi, "listJobs").mockResolvedValue([]);
  });

  it("shows a skeleton then the note list", async () => {
    vi.spyOn(api, "listMyNotes").mockResolvedValue([makeNote()]);

    const { container } = renderPage();
    expect(container.querySelector(".skeleton-list")).toBeInTheDocument();

    await screen.findByText("Follow up");
    expect(screen.getByText("Follow up with candidate next Monday.")).toBeInTheDocument();
    expect(screen.getByText("Private")).toBeInTheDocument();
  });

  it("shows a professional empty state", async () => {
    vi.spyOn(api, "listMyNotes").mockResolvedValue([]);

    renderPage();

    expect(await screen.findByText("No notes yet")).toBeInTheDocument();
  });

  it("creates a new private note by default", async () => {
    vi.spyOn(api, "listMyNotes").mockResolvedValue([]);
    const createSpy = vi.spyOn(api, "createMyNote").mockResolvedValue(makeNote());

    renderPage();
    await screen.findByText("No notes yet");

    fireEvent.click(screen.getByRole("button", { name: "+ New note" }));
    const dialog = await screen.findByRole("dialog", { name: "New note" });
    fireEvent.change(within(dialog).getByLabelText("Content"), {
      target: { value: "Discuss salary expectations." },
    });
    fireEvent.click(within(dialog).getByRole("button", { name: /create note/i }));

    await waitFor(() =>
      expect(createSpy).toHaveBeenCalledWith(
        expect.objectContaining({ body: "Discuss salary expectations.", visibility: "PRIVATE" }),
        "test-token",
      ),
    );
  });

  it("only shows edit/delete for the current user's own notes", async () => {
    vi.spyOn(api, "listMyNotes").mockResolvedValue([
      makeNote({ id: "own-note", author_id: "user-1", visibility: "SHARED" }),
      makeNote({ id: "colleague-note", author_id: "user-2", author_name: "Rita Recruiter", title: "Team note" }),
    ]);

    renderPage();
    await screen.findByText("Team note");

    expect(screen.getAllByRole("button", { name: "Edit" })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: "Delete" })).toHaveLength(1);
  });

  it("deletes a note after confirmation", async () => {
    vi.spyOn(api, "listMyNotes").mockResolvedValue([makeNote()]);
    const deleteSpy = vi.spyOn(api, "deleteMyNote").mockResolvedValue(undefined);

    renderPage();
    await screen.findByText("Follow up");

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Delete this note?" });
    fireEvent.click(within(dialog).getByRole("button", { name: /delete note/i }));

    await waitFor(() => expect(deleteSpy).toHaveBeenCalledWith("note-1", "test-token"));
  });

  it("opens a note's detail view when its card is clicked", async () => {
    vi.spyOn(api, "listMyNotes").mockResolvedValue([
      makeNote({ title: "Long note", body: "A fairly long note body that deserves its own view." }),
    ]);

    renderPage();
    await screen.findByText("Long note");
    fireEvent.click(screen.getByText("Long note"));

    const dialog = await screen.findByRole("dialog", { name: "Long note" });
    expect(within(dialog).getByText("A fairly long note body that deserves its own view.")).toBeInTheDocument();
  });

  it("pins and unpins a note from the card and reflects it visually", async () => {
    const note = makeNote();
    vi.spyOn(api, "listMyNotes").mockResolvedValue([note]);
    const pinSpy = vi.spyOn(api, "togglePinNote").mockResolvedValue({ ...note, pinned: true, pinned_at: new Date().toISOString() });

    renderPage();
    await screen.findByText("Follow up");
    fireEvent.click(screen.getByRole("button", { name: "Pin" }));

    await waitFor(() => expect(pinSpy).toHaveBeenCalledWith("note-1", "test-token"));
  });

  it("only offers pin/edit/delete for the current user's own notes", async () => {
    vi.spyOn(api, "listMyNotes").mockResolvedValue([
      makeNote({ id: "own-note", author_id: "user-1" }),
      makeNote({ id: "colleague-note", author_id: "user-2", title: "Team note", visibility: "SHARED" }),
    ]);

    renderPage();
    await screen.findByText("Team note");

    expect(screen.getAllByRole("button", { name: "Pin" })).toHaveLength(1);
  });

  it("re-queries when the search box changes", async () => {
    const listSpy = vi.spyOn(api, "listMyNotes").mockResolvedValue([]);
    renderPage();
    await screen.findByText("No notes yet");

    fireEvent.change(screen.getByPlaceholderText("Search notes…"), { target: { value: "salary" } });

    await waitFor(() =>
      expect(listSpy).toHaveBeenLastCalledWith("test-token", {
        search: "salary",
        visibility: undefined,
        sort: "created_at",
        order: "desc",
      }),
    );
  });
});
