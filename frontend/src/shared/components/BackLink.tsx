import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { Icon } from "./Icon";

/** The "← Back to …" link: quiet, with an arrow that nudges on hover — the
 * same one on the public pages and inside the recruiter portal. */
export function BackLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="back-link">
      <Icon name="arrow-right" size={16} className="back-link-icon" />
      {children}
    </Link>
  );
}
