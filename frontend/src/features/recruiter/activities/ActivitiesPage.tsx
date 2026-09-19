import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { SkeletonTable } from "../../../shared/components/Skeleton";
import { useToast } from "../../../shared/components/ToastContext";
import type { ActivityResponse } from "../../../types/activity";
import { useAuth } from "../../auth/AuthContext";
import {
  countActivities,
  deleteActivity,
  deleteAllActivities,
  deleteSelectedActivities,
  listActivities,
} from "./api";

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

/** Header checkbox for "select all visible", with the mixed state when only
 * some rows are selected. `indeterminate` is a DOM property, not an attribute. */
function SelectAllCheckbox({
  checked,
  indeterminate,
  onChange,
}: {
  checked: boolean;
  indeterminate: boolean;
  onChange: () => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (ref.current) ref.current.indeterminate = indeterminate;
  }, [indeterminate]);
  return (
    <input
      ref={ref}
      type="checkbox"
      aria-label="Select all visible activities"
      checked={checked}
      onChange={onChange}
    />
  );
}

export function ActivitiesPage() {
  const { accessToken, user } = useAuth();
  const queryClient = useQueryClient();
  const { showToast } = useToast();
  // UX only — every delete endpoint re-checks `activity.delete` server-side.
  const canDelete = user?.roles.includes("ORG_ADMIN") ?? false;
  const [pendingDelete, setPendingDelete] = useState<ActivityResponse | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [pendingBulk, setPendingBulk] = useState<"selected" | "all" | null>(null);
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

  // Total for the whole organization (the table only shows the latest page),
  // so "Delete All" can say exactly how many entries it will remove.
  const countQuery = useQuery({
    queryKey: [...ACTIVITIES_QUERY_KEY, "count"],
    queryFn: () => countActivities(accessToken as string),
    enabled: accessToken !== null && canDelete,
  });
  const total = countQuery.data?.total;

  // Only rows that are on screen count as selected: a filter change or a
  // refresh can never leave an invisible row queued for deletion.
  const visibleActivities = activitiesQuery.data ?? [];
  const selectedIds = visibleActivities.filter((a) => selected.has(a.id)).map((a) => a.id);
  const allVisibleSelected =
    visibleActivities.length > 0 && selectedIds.length === visibleActivities.length;

  function clearSelection() {
    setSelected(new Set());
  }

  function toggleSelected(id: string) {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleSelectAllVisible() {
    setSelected(allVisibleSelected ? new Set() : new Set(visibleActivities.map((a) => a.id)));
  }

  function onBulkDeleted(deleted: number) {
    setPendingBulk(null);
    clearSelection();
    showToast(deleted === 1 ? "Deleted 1 activity." : `Deleted ${deleted} activities.`, "success");
    void queryClient.invalidateQueries({ queryKey: ACTIVITIES_QUERY_KEY });
  }

  function onBulkError(error: unknown) {
    setPendingBulk(null);
    showToast(
      error instanceof ApiError ? error.message : "Could not delete the activities.",
      "error",
    );
  }

  const deleteSelectedMutation = useMutation({
    mutationFn: () => deleteSelectedActivities(selectedIds, accessToken as string),
    onSuccess: (result) => onBulkDeleted(result.deleted),
    onError: onBulkError,
  });

  const deleteAllMutation = useMutation({
    mutationFn: () => deleteAllActivities(accessToken as string),
    onSuccess: (result) => onBulkDeleted(result.deleted),
    onError: onBulkError,
  });

  const deleteMutation = useMutation({
    mutationFn: (activityId: string) => deleteActivity(activityId, accessToken as string),
    onSuccess: () => {
      setPendingDelete(null);
      clearSelection();
      showToast("Activity entry deleted.", "success");
      void queryClient.invalidateQueries({ queryKey: ACTIVITIES_QUERY_KEY });
    },
    onError: (err) => {
      setPendingDelete(null);
      showToast(
        err instanceof ApiError ? err.message : "Could not delete the activity entry.",
        "error",
      );
    },
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
            visible only to organization administrators, who can also remove entries.
          </p>
        </div>
      </div>

      {activitiesQuery.isPending && <SkeletonTable columns={canDelete ? 8 : 7} />}
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
              onChange={(e) => {
                setSearch(e.target.value);
                clearSelection();
              }}
            />
            <select
              value={actionFilter}
              onChange={(e) => {
                setActionFilter(e.target.value);
                clearSelection();
              }}
            >
              <option value="">All actions</option>
              {actionOptions.map((action) => (
                <option key={action} value={action}>
                  {formatActionLabel(action)}
                </option>
              ))}
            </select>
            <select
              value={entityTypeFilter}
              onChange={(e) => {
                setEntityTypeFilter(e.target.value);
                clearSelection();
              }}
            >
              <option value="">All entity types</option>
              {entityTypeOptions.map((type) => (
                <option key={type} value={type}>
                  {type}
                </option>
              ))}
            </select>
            {canDelete && total !== undefined && total > 0 && (
              <button
                type="button"
                className="btn btn-danger btn-sm"
                style={{ marginLeft: "auto" }}
                onClick={() => setPendingBulk("all")}
              >
                Delete All
              </button>
            )}
          </div>

          {canDelete && selectedIds.length > 0 && (
            <div
              className="toolbar"
              role="toolbar"
              aria-label="Bulk actions"
              style={{ alignItems: "center", gap: "0.75rem" }}
            >
              <strong>{selectedIds.length} selected</strong>
              <button
                type="button"
                className="btn btn-danger btn-sm"
                onClick={() => setPendingBulk("selected")}
              >
                Delete Selected
              </button>
              <button type="button" className="btn btn-ghost btn-sm" onClick={clearSelection}>
                Clear
              </button>
            </div>
          )}

          {canDelete &&
            total !== undefined &&
            visibleActivities.length > 0 &&
            total > visibleActivities.length && (
              <p className="field-hint" style={{ margin: 0 }}>
                Showing the latest {visibleActivities.length} of {total} entries. Selecting rows
                affects only the ones shown; Delete All removes every entry.
              </p>
            )}

          {visibleActivities.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state-title">No activity recorded yet</p>
              <p>Deletions, edits, and status changes will show up here as they happen.</p>
            </div>
          ) : (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    {canDelete && (
                      <th style={{ width: "2.5rem" }}>
                        <SelectAllCheckbox
                          checked={allVisibleSelected}
                          indeterminate={selectedIds.length > 0 && !allVisibleSelected}
                          onChange={toggleSelectAllVisible}
                        />
                      </th>
                    )}
                    <th>#</th>
                    <th>Time</th>
                    <th>User</th>
                    <th>Action</th>
                    <th>Entity</th>
                    <th>Reason</th>
                    <th>Details</th>
                    {canDelete && <th aria-label="Actions" />}
                  </tr>
                </thead>
                <tbody>
                  {visibleActivities.map((activity, index) => (
                    <tr key={activity.id}>
                      {canDelete && (
                        <td>
                          <input
                            type="checkbox"
                            aria-label={`Select activity ${index + 1}: ${
                              activity.entity_label ?? activity.entity_type
                            }`}
                            checked={selected.has(activity.id)}
                            onChange={() => toggleSelected(activity.id)}
                          />
                        </td>
                      )}
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
                      {canDelete && (
                        <td>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => setPendingDelete(activity)}
                          >
                            Delete
                          </button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {pendingBulk === "selected" && (
        <ConfirmDialog
          title={
            selectedIds.length === 1
              ? "Delete 1 selected activity?"
              : `Delete ${selectedIds.length} selected activities?`
          }
          message="The selected entries will be permanently removed from the audit log. This cannot be undone."
          confirmLabel={
            selectedIds.length === 1 ? "Delete 1 activity" : `Delete ${selectedIds.length} activities`
          }
          isConfirming={deleteSelectedMutation.isPending}
          onConfirm={() => deleteSelectedMutation.mutate()}
          onCancel={() => setPendingBulk(null)}
        />
      )}

      {pendingBulk === "all" && (
        <ConfirmDialog
          title="Delete all activities for this organization?"
          message={`This permanently deletes ${
            total !== undefined
              ? `all ${total} ${total === 1 ? "activity" : "activities"}`
              : "every activity"
          } recorded for your organization, including entries not shown on this page. Other organizations are not affected. This cannot be undone.`}
          confirmLabel="Delete all activities"
          requireTypedText="DELETE"
          isConfirming={deleteAllMutation.isPending}
          onConfirm={() => deleteAllMutation.mutate()}
          onCancel={() => setPendingBulk(null)}
        />
      )}

      {pendingDelete && (
        <ConfirmDialog
          title="Delete this activity entry?"
          message={`"${
            pendingDelete.entity_label ?? pendingDelete.entity_type
          }" (${formatActionLabel(pendingDelete.action)}) will be permanently removed from the audit log. This cannot be undone.`}
          confirmLabel="Delete entry"
          isConfirming={deleteMutation.isPending}
          onConfirm={() => deleteMutation.mutate(pendingDelete.id)}
          onCancel={() => setPendingDelete(null)}
        />
      )}
    </div>
  );
}
