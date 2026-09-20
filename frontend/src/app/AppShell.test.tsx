import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { ThemeProvider } from "../features/theme/ThemeContext";
import { AppShell, type NavItem, type NavSection } from "./AppShell";

const ITEMS: NavItem[] = [
  { to: "/recruiter", label: "Overview", icon: "overview", end: true },
  { to: "/recruiter/jobs", label: "Jobs", icon: "jobs" },
  { to: "/recruiter/candidates", label: "Candidates", icon: "candidates" },
];
const SECTIONS: NavSection[] = [{ label: "Workspace", items: ITEMS }];

function renderShell({
  path = "/recruiter/jobs",
  tabs = ITEMS,
  onSignOut = () => {},
}: { path?: string; tabs?: NavItem[]; onSignOut?: () => void } = {}) {
  return render(
    <ThemeProvider>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route
            path="/recruiter"
            element={
              <AppShell
                brandTitle="AI Recruitment Platform"
                contextLabel="Recruiter Portal"
                sections={SECTIONS}
                upcoming={["Sourcing"]}
                tabs={tabs}
                userName="Riya Recruiter"
                userRole="RECRUITER"
                onSignOut={onSignOut}
              />
            }
          >
            <Route index element={<p>Overview page</p>} />
            <Route path="jobs" element={<p>Jobs page</p>} />
            <Route path="candidates" element={<p>Candidates page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  );
}

describe("AppShell", () => {
  it("renders the page in the content region, with a skip link straight to it", () => {
    renderShell();

    expect(screen.getByText("Jobs page")).toBeInTheDocument();
    const skip = screen.getByRole("link", { name: "Skip to main content" });
    expect(skip).toHaveAttribute("href", "#main-content");
    expect(document.getElementById("main-content")).toContainElement(screen.getByText("Jobs page"));
  });

  it("marks the current page in the navigation and names it in the top bar", () => {
    const { container } = renderShell({ path: "/recruiter/candidates" });
    const sidebar = container.querySelector(".sidebar") as HTMLElement;

    // exactly one item is current, and it is the page being viewed
    const current = within(sidebar).getAllByRole("link").filter((link) => link.getAttribute("aria-current") === "page");
    expect(current).toHaveLength(1);
    expect(current[0]).toHaveTextContent("Candidates");
    expect(current[0]).toHaveClass("active");

    expect(container.querySelector(".topbar-title")).toHaveTextContent("Candidates");
    expect(container.querySelector(".topbar-context")).toHaveTextContent("Recruiter Portal");
  });

  it("names the section from the longest matching route, not just the first prefix", () => {
    const { container } = renderShell({ path: "/recruiter/jobs" });

    // "/recruiter" (Overview, end-only) must not claim "/recruiter/jobs"
    expect(container.querySelector(".topbar-title")).toHaveTextContent("Jobs");
  });

  it("groups navigation, keeps disabled 'coming soon' items non-navigable, and shows who is signed in", () => {
    const { container } = renderShell();

    const sidebar = container.querySelector(".sidebar") as HTMLElement;
    expect(within(sidebar).getByText("Workspace")).toBeInTheDocument();
    for (const item of ITEMS) {
      expect(within(sidebar).getByRole("link", { name: item.label })).toHaveAttribute("href", item.to);
    }
    const upcoming = within(sidebar).getByText("Sourcing").closest(".sidebar-link");
    expect(upcoming).toHaveAttribute("aria-disabled", "true");
    expect(upcoming?.tagName).not.toBe("A");

    expect(container.querySelector(".topbar")).toHaveTextContent("Riya Recruiter");
    expect(container.querySelector(".topbar")).toHaveTextContent("RECRUITER");
  });

  it("signs out from the top bar", () => {
    const onSignOut = vi.fn();
    const { container } = renderShell({ onSignOut });

    fireEvent.click(within(container.querySelector(".topbar") as HTMLElement).getByRole("button", { name: "Sign out" }));

    expect(onSignOut).toHaveBeenCalledTimes(1);
  });

  it("opens the phone drawer from the menu button and closes it with Escape or the close button", () => {
    const { container } = renderShell();
    const sidebar = container.querySelector(".sidebar") as HTMLElement;
    expect(sidebar).not.toHaveClass("open");

    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(sidebar).toHaveClass("open");
    expect(screen.getByRole("button", { name: "Open menu" })).toHaveAttribute("aria-expanded", "true");

    fireEvent.keyDown(document, { key: "Escape" });
    expect(sidebar).not.toHaveClass("open");

    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    fireEvent.click(screen.getByRole("button", { name: "Close menu" }));
    expect(sidebar).not.toHaveClass("open");
  });

  it("closes the drawer when a navigation link is followed", () => {
    const { container } = renderShell({ path: "/recruiter" });
    const sidebar = container.querySelector(".sidebar") as HTMLElement;

    fireEvent.click(screen.getByRole("button", { name: "Open menu" }));
    expect(sidebar).toHaveClass("open");
    fireEvent.click(within(sidebar).getByRole("link", { name: "Candidates" }));

    expect(screen.getByText("Candidates page")).toBeInTheDocument();
    expect(sidebar).not.toHaveClass("open");
  });

  it("gives phones a bottom tab bar (with More) when tabs are supplied, and none otherwise", () => {
    const { container, unmount } = renderShell();
    const tabbar = container.querySelector(".tabbar") as HTMLElement;
    expect(within(tabbar).getAllByRole("link")).toHaveLength(ITEMS.length);
    expect(within(tabbar).getByRole("button", { name: "More" })).toBeInTheDocument();
    unmount();

    const admin = renderShell({ tabs: [] });
    expect(admin.container.querySelector(".tabbar")).toBeNull();
  });
});
