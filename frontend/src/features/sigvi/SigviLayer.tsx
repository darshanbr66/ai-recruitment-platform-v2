import { Component, lazy, Suspense, useEffect, useState, type ReactNode } from "react";
import { Outlet, useMatch } from "react-router-dom";

/** The widget is its own chunk: nobody pays for it until the page has
 * painted. */
const SigviWidget = lazy(async () => ({
  default: (await import("./SigviWidget")).SigviWidget,
}));

/** The assistant is an extra, never a dependency: if its chunk fails to load
 * (offline, a stale deploy) the page must carry on without it. */
class SigviBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}

/** True once the browser is idle after first paint — so loading Sigvi never
 * competes with the page (or the hero scene) for the critical path. */
function useAfterIdle(timeoutMs = 1500) {
  const [ready, setReady] = useState(false);
  useEffect(() => {
    const idle = window.requestIdleCallback;
    if (typeof idle === "function") {
      const handle = idle(() => setReady(true), { timeout: timeoutMs });
      return () => window.cancelIdleCallback?.(handle);
    }
    const handle = window.setTimeout(() => setReady(true), 300);
    return () => window.clearTimeout(handle);
  }, [timeoutMs]);
  return ready;
}

/**
 * Layout route for the pages Sigvi appears on — the public home page, the
 * careers list and a role's page. Deliberately NOT the assessment or campus
 * drive pages (an assistant beside a test would defeat it), and never the
 * recruiter/admin app. Being a layout route, the widget stays mounted — and
 * the conversation survives — as a visitor moves between these pages.
 */
export function SigviLayer() {
  const careersMatch = useMatch({ path: "/org/:slug", end: false });
  const ready = useAfterIdle();

  return (
    <>
      <Outlet />
      {ready && (
        <SigviBoundary>
          <Suspense fallback={null}>
            <SigviWidget organizationSlug={careersMatch?.params.slug} />
          </Suspense>
        </SigviBoundary>
      )}
    </>
  );
}
