import "@testing-library/jest-dom/vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi, type MockInstance } from "vitest";
import { ApiError } from "../../lib/apiClient";
import type { SigviChatResponse } from "../../types/sigvi";
import * as sigviApi from "./api";
import { SigviWidget } from "./SigviWidget";

/** The redesigned experience: welcome screen, launcher, mascot reactions, the
 * one-time teaser and the phone keyboard. (Conversation mechanics are in
 * SigviWidget.test.tsx.) */

function reply(message: string): SigviChatResponse {
  return { conversation_id: "11111111-1111-4111-8111-111111111111", message, sources: [], jobs: [] };
}

function renderWidget(props: { organizationSlug?: string; teaser?: boolean } = {}) {
  return render(
    <MemoryRouter>
      <SigviWidget {...props} />
    </MemoryRouter>,
  );
}

const launcher = () => screen.getByRole("button", { name: /ask sigvi/i });
const input = () => screen.getByRole("textbox", { name: /message sigvi/i });
const openPanel = () => fireEvent.click(launcher());
const type = (text: string) => fireEvent.change(input(), { target: { value: text } });
const pressEnter = () => fireEvent.keyDown(input(), { key: "Enter" });

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((res) => {
    resolve = res;
  });
  return { promise, resolve };
}

let send: MockInstance<typeof sigviApi.sendChatMessage>;

beforeEach(() => {
  send = vi.spyOn(sigviApi, "sendChatMessage").mockResolvedValue(reply("Hello from Sigvi."));
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  window.sessionStorage.clear();
  document.body.style.overflow = "";
});

describe("welcome screen", () => {
  it("introduces Sigvi, lists what it can help with, and presents the mascot as a named image", () => {
    renderWidget();
    openPanel();

    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByRole("heading", { name: /hi, i'm sigvi/i })).toBeInTheDocument();
    expect(within(dialog).getByText("I can help you explore:")).toBeInTheDocument();
    for (const item of [
      "Current job openings",
      "How to apply",
      "The hiring process",
      "Campus opportunities",
      "Assessments",
      "SIGVITAS and career questions",
      "General questions",
    ]) {
      expect(within(dialog).getByText(item)).toBeInTheDocument();
    }
    expect(within(dialog).getByRole("img", { name: /sigvi.*robot/i })).toBeInTheDocument();
  });

  it.each([
    "Show me current openings",
    "How do I apply?",
    "How does the hiring process work?",
    "Tell me about SIGVITAS",
    "How does the assessment work?",
  ])("the “%s” card sends exactly that question", async (label) => {
    renderWidget();
    openPanel();

    fireEvent.click(screen.getByRole("button", { name: label }));

    await screen.findByText("Hello from Sigvi.");
    expect(send).toHaveBeenCalledTimes(1);
    expect(send).toHaveBeenCalledWith(expect.objectContaining({ message: label, history: [] }));
  });

  it("gives every suggestion an icon that assistive tech ignores", () => {
    renderWidget();
    openPanel();

    const cards = within(screen.getByRole("group", { name: /suggested questions/i })).getAllByRole("button");
    expect(cards).toHaveLength(5);
    cards.forEach((card) => {
      const icon = card.querySelector(".sigvi-suggest-icon");
      expect(icon).toHaveAttribute("aria-hidden", "true");
      expect(icon?.querySelector("svg")).not.toBeNull();
    });
  });

  it("is replaced by a compact greeting once the conversation starts", async () => {
    renderWidget();
    openPanel();
    type("hello");
    pressEnter();
    await screen.findByText("Hello from Sigvi.");

    expect(screen.queryByText("I can help you explore:")).not.toBeInTheDocument();
    expect(screen.queryByRole("img", { name: /sigvi.*robot/i })).not.toBeInTheDocument();
    expect(screen.getByText("How can I help you today?")).toBeInTheDocument();
  });
});

describe("the launcher", () => {
  it("shows the mascot beside an 'Ask Sigvi' label, with a single accessible name", () => {
    renderWidget();

    const button = launcher();
    expect(within(button).getByText("Ask Sigvi")).toBeInTheDocument();
    expect(within(button).getByText("AI assistant")).toBeInTheDocument();
    expect(button.querySelector("svg.sigvi-mascot")).toHaveAttribute("aria-hidden", "true");
    expect(button).toHaveAccessibleName("Ask Sigvi, the AI assistant");
  });
});

describe("the launcher's resting and waking", () => {
  beforeEach(() => vi.useFakeTimers());
  const orb = () => document.querySelector(".sigvi-orb");
  const advance = (ms: number) =>
    act(() => {
      vi.advanceTimersByTime(ms);
    });

  it("stirs once a minute (a fresh orb replays its finite animations)", () => {
    renderWidget();
    const first = orb();

    advance(59_000);
    expect(orb()).toBe(first);
    advance(2_000);
    expect(orb()).not.toBe(first);
    expect(orb()).not.toBeNull();
  });

  it("does not stir while the panel is open", () => {
    renderWidget();
    openPanel();
    const first = orb();

    advance(130_000);

    expect(orb()).toBe(first);
  });

  it("does not stir for people who asked for reduced motion", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
    renderWidget();
    const first = orb();

    advance(130_000);

    expect(orb()).toBe(first);
  });
});

describe("the mascot's reactions", () => {
  const headerMascot = () => document.querySelector(".sigvi-header svg.sigvi-mascot");

  it("thinks while a reply is on its way, celebrates when it lands, then settles", async () => {
    const pending = deferred<SigviChatResponse>();
    send.mockReturnValueOnce(pending.promise);
    renderWidget();
    openPanel();
    expect(headerMascot()).toHaveAttribute("data-state", "idle");

    type("hello");
    pressEnter();
    const status = await screen.findByRole("status");

    expect(headerMascot()).toHaveAttribute("data-state", "thinking");
    expect(within(status).getByText(/sigvi is thinking/i)).toBeInTheDocument();
    expect(status.querySelector("svg.sigvi-mascot")).toHaveAttribute("data-state", "thinking");

    await act(async () => pending.resolve(reply("All done.")));
    await screen.findByText("All done.");
    expect(headerMascot()).toHaveAttribute("data-state", "delight");

    await waitFor(() => expect(headerMascot()).toHaveAttribute("data-state", "idle"), { timeout: 3000 });
  });

  it("does not celebrate an error", async () => {
    send.mockRejectedValueOnce(new ApiError("nope", 503, "ai_unavailable"));
    renderWidget();
    openPanel();
    type("hi");
    pressEnter();
    await screen.findByRole("alert");

    expect(headerMascot()).toHaveAttribute("data-state", "idle");
  });

  it("keeps the small avatars beside messages still", async () => {
    renderWidget();
    openPanel();
    type("hi");
    pressEnter();
    await screen.findByText("Hello from Sigvi.");

    expect(document.querySelector(".sigvi-row-assistant svg.sigvi-mascot")).toHaveAttribute(
      "data-animated",
      "false",
    );
  });
});

describe("the one-time teaser", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    window.sessionStorage.clear();
  });

  const teaserText = () => screen.queryByText("Ask me about open roles.");
  const advance = (ms: number) =>
    act(() => {
      vi.advanceTimersByTime(ms);
    });

  it("appears a few seconds after load on the home page, never sooner", () => {
    renderWidget({ teaser: true });

    advance(4000);
    expect(teaserText()).not.toBeInTheDocument();
    advance(1500);
    expect(teaserText()).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /i'm sigvi/i })).toBeInTheDocument();
    // it never competes for the launcher's accessible name
    expect(screen.getAllByRole("button", { name: /ask sigvi/i })).toHaveLength(1);
  });

  it("does not appear on pages that didn't ask for it", () => {
    renderWidget({ teaser: false });

    advance(30000);
    expect(teaserText()).not.toBeInTheDocument();
  });

  it("opens the chat when clicked, and is gone for the rest of the session", () => {
    const { unmount } = renderWidget({ teaser: true });
    advance(5500);

    fireEvent.click(screen.getByRole("button", { name: /i'm sigvi/i }));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(teaserText()).not.toBeInTheDocument();
    unmount();

    renderWidget({ teaser: true });
    advance(30000);
    expect(teaserText()).not.toBeInTheDocument();
  });

  it("can be dismissed, and stays dismissed", () => {
    const { unmount } = renderWidget({ teaser: true });
    advance(5500);

    fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));

    expect(teaserText()).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    unmount();

    renderWidget({ teaser: true });
    advance(30000);
    expect(teaserText()).not.toBeInTheDocument();
  });

  it("goes away by itself if ignored", () => {
    renderWidget({ teaser: true });
    advance(5500);
    expect(teaserText()).toBeInTheDocument();

    advance(16000);

    expect(teaserText()).not.toBeInTheDocument();
  });

  it("opening from the launcher instead also retires it", () => {
    renderWidget({ teaser: true });
    advance(5500);

    fireEvent.click(launcher());

    expect(teaserText()).not.toBeInTheDocument();
  });

  it("still works when session storage is unavailable", () => {
    const original = Object.getOwnPropertyDescriptor(window, "sessionStorage");
    Object.defineProperty(window, "sessionStorage", {
      configurable: true,
      get() {
        throw new Error("blocked");
      },
    });
    try {
      renderWidget({ teaser: true });
      advance(5500);
      expect(teaserText()).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: /dismiss/i }));
      expect(teaserText()).not.toBeInTheDocument();
    } finally {
      if (original) Object.defineProperty(window, "sessionStorage", original);
    }
  });
});

describe("phone keyboard", () => {
  function stubViewport(height: number, mobile: boolean) {
    const listeners = new Map<string, () => void>();
    const viewport = {
      height,
      offsetTop: 0,
      addEventListener: (name: string, fn: () => void) => listeners.set(name, fn),
      removeEventListener: (name: string) => listeners.delete(name),
    };
    vi.stubGlobal("visualViewport", viewport);
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: mobile && query.includes("max-width: 640px"),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));
    return { viewport, listeners };
  }

  it("sizes the sheet to the visible viewport, so the keyboard cannot cover the input", () => {
    const { viewport, listeners } = stubViewport(780, true);
    renderWidget();
    openPanel();
    const panel = screen.getByRole("dialog");
    expect(panel.style.getPropertyValue("--sigvi-vh")).toBe("780px");

    // the on-screen keyboard opens
    viewport.height = 430;
    act(() => listeners.get("resize")?.());
    expect(panel.style.getPropertyValue("--sigvi-vh")).toBe("430px");

    fireEvent.click(screen.getByRole("button", { name: /close sigvi/i }));
    expect(panel.style.getPropertyValue("--sigvi-vh")).toBe("");
  });

  it("leaves the desktop layout alone", () => {
    stubViewport(500, false);
    renderWidget();
    openPanel();

    expect(screen.getByRole("dialog").style.getPropertyValue("--sigvi-vh")).toBe("");
  });
});
