import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { SkeletonTable } from "../../../shared/components/Skeleton";
import { useAuth } from "../../auth/AuthContext";
import { listActivities } from "./api";

const ACTIVITIES_QUERY_KEY = ["recruiter", "activities"];

const ACTION_BADGE_CLASS: Record<string, string> = {
  JOB_REOPENED: "badge-active",
  CAMPUS_DRIVE_REOPENED: "badge-active",
  CAMPUS_DRIVE_ACTIVATED: "badge-active",
  LOGOUT: "badge-inactive",
  CAMPUS_DRIVE_CLOSED: "badge-inactive",
  JOB_CLOSED: "badge-inactive",
};

/** Actions ending in _DELETED/_FAILED read as danger, _CREATED as positive,
 * everything else as a neutral "something changed" — checked before the
 * lookup table above so a new action name still gets a sensible color. */
function actionBadgeClass(action: string): string {
  if (ACTION_BADGE_CLASS[action]) return ACTION_BADGE_CLASS[action];
  if (action.endsWith("_DELETED") || action.endsWith("_FAILED")) return "badge-danger";
  if (action.endsWith("_CREATED") || action === "LOGIN" || action === "USER_REACTIVATED") {
    return "badge-active";
  }
  return "badge-warn";
}

function formatActionLabel(action: string): string {
  return action
    .toLowerCase()
    .split("_")
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

function formatTimestamp(value: string): string {
  return new Date(value).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export function ActivitiesPage() {
  const { accessToken } = useAuth();
  const [search, setSearch] = useState("");
  const [actionFilter, setActionFilter] = useState("");
  const [entityTypeFilter, setEntityTypeFilter] = useState("");

  const activitiesQuery = useQuery({
    queryKey: [...ACTIVITIES_QUERY_KEY, search, actionFilter, entityTypeFilter],
    queryFn: () =>
      listActivities(
        {
          search: search.trim() || undefined,
          action: actionFilter || undefined,
          entity_type: entityTypeFilter || undefined,
        },
        accessToken as string,
      ),
    enabled: accessToken !== null,
  });

  const actionOptions = useMemo(() => {
    if (!activitiesQuery.data) return [];
    return Array.from(new Set(activitiesQuery.data.map((a) => a.action))).sort();
  }, [activitiesQuery.data]);

  const entityTypeOptions = useMemo(() => {
    if (!activitiesQuery.data) return [];
    return Array.from(new Set(activitiesQuery.data.map((a) => a.entity_type))).sort();
  }, [activitiesQuery.data]);

  const canView = !(activitiesQuery.error instanceof ApiError && activitiesQuery.error.status === 403);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Activities</h1>
          <p className="muted">
            An audit trail of deletions, edits, and status changes across your organization —
            visible only to organization administrators.
          </p>
        </div>
      </div>

      {activitiesQuery.isPending && <SkeletonTable columns={7} />}
      {activitiesQuery.isError && !canView && (
        <Alert>You do not have permission to view the activity log.</Alert>
      )}
      {activitiesQuery.isError && canView && (
        <Alert>
          {activitiesQuery.error instanceof ApiError
            ? activitiesQuery.error.message
            : "Could not load the activity log."}
        </Alert>
      )}

      {activitiesQuery.isSuccess && (
        <section className="stack-lg" style={{ gap: "1rem" }}>
          <div className="toolbar">
            <input
              className="search-input"
              placeholder="Search by actor, entity, reason…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <select value={actionFilter} onChange={(e) => setActionFilter(e.target.value)}>
              <option value="">All actions</option>
              {actionOptions.map((action) => (
                <option key={action} value={action}>
                  {formatActionLabel(action)}
                </option>
              ))}
            </select>
            <select value={entityTypeFilter} onChange={(e) => setEntityTypeFilter(e.target.value)}>
              <option value="">All entity types</option>
              {entityTypeOptions.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
          </div>

          {activitiesQuery.data.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state-title">No activity recorded yet</p>
              <p>Deletions, edits, and status changes will show up here as they happen.</p>
            </div>
          ) : (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Time</th>
                    <th>User</th>
                    <th>Action</th>
                    <th>Entity</th>
                    <th>Reason</th>
                    <th>Details</th>
                  </tr>
                </thead>
                <tbody>
                  {activitiesQuery.data.map((activity, index) => (
                    <tr key={activity.id}>
                      <td>{index + 1}</td>
                      <td>{formatTimestamp(activity.created_at)}</td>
                      <td>{activity.actor_name ?? "—"}</td>
                      <td>
                        <span className={`badge ${actionBadgeClass(activity.action)}`}>
                          {formatActionLabel(activity.action)}
                        </span>
                      </td>
                      <td>{activity.entity_label ?? activity.entity_type}</td>
                      <td>{activity.reason ?? "—"}</td>
                      <td className="muted">{activity.description ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
