import type { ReactNode } from "react";
import { Icon, type IconName } from "./Icon";

/**
 * A designed empty state: what's missing, why it's worth filling, and the
 * one obvious next step. Restraint over illustration — a single line icon
 * inside a soft tile, then copy and (optionally) the action.
 */
export function EmptyState({
  icon = "graph",
  title,
  children,
  action,
  compact = false,
}: {
  icon?: IconName;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}) {
  return (
    <div className={`empty-state${compact ? " empty-state-compact" : ""}`}>
      <span className="empty-state-icon" aria-hidden="true">
        <Icon name={icon} size={compact ? 18 : 22} />
      </span>
      <p className="empty-state-title">{title}</p>
      {children && <p className="empty-state-text">{children}</p>}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}
