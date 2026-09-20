import { Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { ThemeToggle } from "../features/theme/ThemeToggle";
import { Avatar } from "../shared/components/Avatar";
import { Icon, LogoMark, type IconName } from "../shared/components/Icon";
import { PageTransition } from "../shared/components/PageTransition";
import { RouteFallback } from "../shared/components/RouteFallback";
import { useMediaQuery } from "../shared/hooks/useMediaQuery";

export interface NavItem {
  to: string;
  label: string;
  icon: IconName;
  end?: boolean;
}

export interface NavSection {
  label?: string;
  items: NavItem[];
}

/**
 * The application frame shared by the recruiter and platform-admin surfaces:
 * sidebar, contextual top bar, scrolling content region and (on phones) a
 * bottom tab bar. It knows nothing about roles or permissions — each layout
 * decides *which* navigation to pass in (the API remains the authority).
 *
 * Navigation feel: a single indicator slides between items instead of the
 * highlight snapping, the top bar names where you are, and on phones the four
 * most-used destinations sit under the thumb with everything else one tap
 * away in the drawer.
 */
export function AppShell({
  brandTitle,
  contextLabel,
  sections,
  upcoming = [],
  tabs = [],
  userName,
  userRole,
  onSignOut,
  variant = "recruiter",
}: {
  brandTitle: string;
  /** Small label above the page title in the top bar, e.g. "Recruiter Portal". */
  contextLabel: string;
  sections: NavSection[];
  upcoming?: string[];
  /** Up to four primary destinations for the phone tab bar. */
  tabs?: NavItem[];
  userName: string | undefined;
  userRole: string;
  onSignOut: () => void;
  variant?: "recruiter" | "admin";
}) {
  const location = useLocation();
  // The drawer is open *for a path*: navigating elsewhere closes it without an effect.
  const [drawerPath, setDrawerPath] = useState<string | null>(null);
  const menuOpen = drawerPath === location.pathname;
  const setMenuOpen = (open: boolean) => setDrawerPath(open ? location.pathname : null);
  const isPhone = useMediaQuery("(max-width: 720px)");
  const navRef = useRef<HTMLElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);
  const [indicator, setIndicator] = useState<{ y: number; h: number } | null>(null);
  const [indicatorReady, setIndicatorReady] = useState(false);

  const allItems = sections.flatMap((section) => section.items);
  const current = [...allItems]
    .sort((a, b) => b.to.length - a.to.length)
    .find((item) => (item.end ? location.pathname === item.to : location.pathname.startsWith(item.to)));

  // Move the sliding indicator to whichever link React Router marked active.
  useLayoutEffect(() => {
    const active = navRef.current?.querySelector<HTMLElement>(".sidebar-link.active");
    setIndicator(active ? { y: active.offsetTop, h: active.offsetHeight } : null);
  }, [location.pathname, sections]);

  // Enable the indicator's transition only after its first placement, so it
  // doesn't visibly fly in from the top on initial load.
  useEffect(() => {
    if (indicator && !indicatorReady) {
      const frame = requestAnimationFrame(() => setIndicatorReady(true));
      return () => cancelAnimationFrame(frame);
    }
  }, [indicator, indicatorReady]);

  // Drawer: close on Escape, and hand focus to its close button when it opens.
  useEffect(() => {
    if (!menuOpen) return;
    closeRef.current?.focus();
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setDrawerPath(null);
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, [menuOpen]);

  const drawerHidden = isPhone && !menuOpen;

  return (
    <div className={`app-shell app-shell-${variant}`}>
      <a href="#main-content" className="skip-link">
        Skip to main content
      </a>
      <button
        type="button"
        className={`sidebar-overlay${menuOpen ? " open" : ""}`}
        aria-hidden={!menuOpen}
        tabIndex={-1}
        onClick={() => setMenuOpen(false)}
      />
      <aside
        className={`sidebar${variant === "admin" ? " sidebar-admin" : ""}${menuOpen ? " open" : ""}`}
        aria-label="Primary"
        // A closed phone drawer is off-screen: keep it out of tab order and
        // the accessibility tree instead of leaving invisible focus stops.
        inert={drawerHidden}
      >
        <div className="sidebar-brand">
          <span className="brand-lockup">
            <LogoMark />
            <span className="brand-name">{brandTitle}</span>
          </span>
          <button
            ref={closeRef}
            type="button"
            className="sidebar-close"
            aria-label="Close menu"
            onClick={() => setMenuOpen(false)}
          >
            <Icon name="x" size={18} />
          </button>
        </div>

        <nav className="sidebar-nav" ref={navRef}>
          <span
            className={`nav-indicator${indicatorReady ? " ready" : ""}`}
            aria-hidden="true"
            style={
              indicator
                ? { transform: `translateY(${indicator.y}px)`, height: indicator.h, opacity: 1 }
                : { opacity: 0 }
            }
          />
          {sections.map((section, index) => (
            <div key={section.label ?? index} className="nav-group">
              {section.label && <div className="sidebar-section-label">{section.label}</div>}
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.end}
                  className={({ isActive }) => `sidebar-link${isActive ? " active" : ""}`}
                >
                  <Icon name={item.icon} size={18} />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}

          {upcoming.length > 0 && (
            <div className="nav-group">
              <div className="sidebar-section-label">Coming soon</div>
              {upcoming.map((label) => (
                <span key={label} className="sidebar-link disabled" aria-disabled="true">
                  <Icon name="search" size={18} />
                  <span>{label}</span>
                </span>
              ))}
            </div>
          )}
        </nav>

        <div className="sidebar-footer">
          <div className="sidebar-user">
            <Avatar name={userName} />
            <span className="sidebar-user-text">
              <span className="user-name">{userName}</span>
              <span className="user-roles">{userRole}</span>
            </span>
          </div>
          <button type="button" className="btn btn-ghost btn-sm sidebar-signout" onClick={onSignOut}>
            Sign out
          </button>
        </div>
      </aside>

      <div className="app-main">
        <header className="topbar">
          <div className="topbar-left">
            <button
              type="button"
              className="mobile-menu-button"
              aria-label="Open menu"
              aria-expanded={menuOpen}
              onClick={() => setMenuOpen(true)}
            >
              <Icon name="menu" size={18} />
            </button>
            <div className="topbar-heading">
              <span className="topbar-context">{contextLabel}</span>
              <span className="topbar-title">{current?.label ?? brandTitle}</span>
            </div>
          </div>
          <div className="topbar-user">
            <ThemeToggle />
            <div className="user-chip">
              <Avatar name={userName} />
              <div className="user-badge">
                <span className="user-name">{userName}</span>
                <span className="user-roles">{userRole}</span>
              </div>
            </div>
            <button type="button" className="btn btn-ghost topbar-signout" onClick={onSignOut}>
              Sign out
            </button>
          </div>
        </header>

        <main id="main-content" className="content" tabIndex={-1}>
          <PageTransition>
            <Suspense fallback={<RouteFallback />}>
              <Outlet />
            </Suspense>
          </PageTransition>
        </main>

        {tabs.length > 0 && (
          <nav className="tabbar" aria-label="Quick navigation">
            {tabs.map((tab) => (
              <NavLink
                key={tab.to}
                to={tab.to}
                end={tab.end}
                className={({ isActive }) => `tabbar-link${isActive ? " active" : ""}`}
              >
                <Icon name={tab.icon} size={20} />
                <span>{tab.label}</span>
              </NavLink>
            ))}
            <button type="button" className="tabbar-link" onClick={() => setMenuOpen(true)}>
              <Icon name="menu" size={20} />
              <span>More</span>
            </button>
          </nav>
        )}
      </div>
    </div>
  );
}
