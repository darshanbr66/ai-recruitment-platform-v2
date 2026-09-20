import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";

/**
 * A quick, quiet entrance for a page: a short fade and 6px rise, ~200ms.
 * Keyed by pathname, so moving between pages replays it while filtering or
 * paging within one page (query-string changes) does not. Deliberately an
 * entrance only — there is no exit animation, so navigation never waits on
 * an outgoing page. Recruiter pages are a work surface; this signals
 * "new page" and gets out of the way.
 */
export function PageTransition({ children }: { children: ReactNode }) {
  const { pathname } = useLocation();
  return (
    <div key={pathname} className="page-transition">
      {children}
    </div>
  );
}
