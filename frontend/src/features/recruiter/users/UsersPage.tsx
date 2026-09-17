import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { ASSIGNABLE_ROLES, type AssignableRole, type UserResponse } from "../../../types/auth";
import { Alert } from "../../../shared/components/Alert";
import { ConfirmDialog } from "../../../shared/components/ConfirmDialog";
import { Modal } from "../../../shared/components/Modal";
import { SkeletonTable } from "../../../shared/components/Skeleton";
import { Spinner } from "../../../shared/components/Spinner";
import { useToast } from "../../../shared/components/ToastContext";
import { useAuth } from "../../auth/AuthContext";
import { createUser, listUsers, updateUser } from "../../auth/api";

const USERS_QUERY_KEY = ["recruiter", "users"];

export function UsersPage() {
  const { accessToken, user: currentUser } = useAuth();
  const token = accessToken as string;
  const queryClient = useQueryClient();
  const { showToast } = useToast();

  const usersQuery = useQuery({
    queryKey: USERS_QUERY_KEY,
    queryFn: () => listUsers(token),
    enabled: accessToken !== null,
  });

  const [showForm, setShowForm] = useState(false);
  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<AssignableRole>("RECRUITER");
  const [formError, setFormError] = useState<string | null>(null);

  const [pendingDeactivate, setPendingDeactivate] = useState<UserResponse | null>(null);
  const [deactivateReason, setDeactivateReason] = useState("");
  const [deactivateError, setDeactivateError] = useState<string | null>(null);
  const [pendingReactivate, setPendingReactivate] = useState<UserResponse | null>(null);

  const createUserMutation = useMutation({
    mutationFn: () => createUser({ email, password, full_name: fullName, role }, token),
    onSuccess: () => {
      showToast(`Team member ${fullName} was added.`, "success");
      setEmail("");
      setFullName("");
      setPassword("");
      setRole("RECRUITER");
      setFormError(null);
      setShowForm(false);
      void queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
    },
    onError: (err) => {
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createUserMutation.mutate();
  }

  function closeForm() {
    if (createUserMutation.isPending) return;
    setShowForm(false);
  }

  const roleMutation = useMutation({
    mutationFn: ({ userId, newRole }: { userId: string; newRole: AssignableRole }) =>
      updateUser(userId, { role: newRole }, token),
    onSuccess: (updated) => {
      showToast(`${updated.full_name}'s role is now ${updated.roles.join(", ")}.`, "success");
      void queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
    },
    onError: (err) => {
      showToast(
        err instanceof ApiError ? err.message : "Could not change that team member's role.",
        "error",
      );
    },
  });

  const deactivateMutation = useMutation({
    mutationFn: () =>
      updateUser(
        pendingDeactivate!.id,
        { is_active: false, reason: deactivateReason.trim() || undefined },
        token,
      ),
    onSuccess: (updated) => {
      showToast(`${updated.full_name} was deactivated.`, "success");
      setPendingDeactivate(null);
      setDeactivateReason("");
      setDeactivateError(null);
      void queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
    },
    onError: (err) => {
      setDeactivateError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  const reactivateMutation = useMutation({
    mutationFn: () => updateUser(pendingReactivate!.id, { is_active: true }, token),
    onSuccess: (updated) => {
      showToast(`${updated.full_name} was reactivated.`, "success");
      setPendingReactivate(null);
      void queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
    },
    onError: (err) => {
      showToast(
        err instanceof ApiError ? err.message : "Could not reactivate that team member.",
        "error",
      );
      setPendingReactivate(null);
    },
  });

  function openDeactivateModal(teamUser: UserResponse) {
    setPendingDeactivate(teamUser);
    setDeactivateReason("");
    setDeactivateError(null);
  }

  function closeDeactivateModal() {
    if (deactivateMutation.isPending) return;
    setPendingDeactivate(null);
    setDeactivateReason("");
    setDeactivateError(null);
  }

  function handleDeactivateSubmit(event: FormEvent) {
    event.preventDefault();
    deactivateMutation.mutate();
  }

  // Today only ORG_ADMIN holds `user.read` (seeded in the Phase 2 migration),
  // and ORG_ADMIN is also the only role holding `user.create` — so a
  // successful list load already implies create access too.
  const canManageUsers = !(usersQuery.error instanceof ApiError && usersQuery.error.status === 403);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Team</h1>
          <p className="muted">Recruiters and admins who work in your organization.</p>
        </div>
        {canManageUsers && (
          <button type="button" className="btn btn-primary" onClick={() => setShowForm(true)}>
            + Add team member
          </button>
        )}
      </div>

      {usersQuery.isPending && <SkeletonTable columns={6} />}

      {usersQuery.isError && !canManageUsers && (
        <Alert>You do not have permission to view or manage team members.</Alert>
      )}

      {usersQuery.isError && canManageUsers && (
        <Alert>
          {usersQuery.error instanceof ApiError
            ? usersQuery.error.message
            : "Could not load team members."}
        </Alert>
      )}

      {usersQuery.isSuccess && (
        <section>
          {usersQuery.data.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state-title">No team members yet</p>
              <p>Add your first teammate below.</p>
            </div>
          ) : (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Name</th>
                    <th>Email</th>
                    <th>Role</th>
                    <th>Status</th>
                    {canManageUsers && <th>Actions</th>}
                  </tr>
                </thead>
                <tbody>
                  {usersQuery.data.map((teamUser, index) => {
                    const isSelf = teamUser.id === currentUser?.id;
                    const currentRole = (teamUser.roles[0] as AssignableRole | undefined) ?? "RECRUITER";
                    return (
                      <tr key={teamUser.id}>
                        <td>{index + 1}</td>
                        <td>
                          {teamUser.full_name}
                          {isSelf && <span className="muted"> (you)</span>}
                        </td>
                        <td>{teamUser.email}</td>
                        <td>
                          {canManageUsers && !isSelf ? (
                            <select
                              value={currentRole}
                              disabled={roleMutation.isPending}
                              onChange={(e) =>
                                roleMutation.mutate({
                                  userId: teamUser.id,
                                  newRole: e.target.value as AssignableRole,
                                })
                              }
                            >
                              {ASSIGNABLE_ROLES.map((option) => (
                                <option key={option} value={option}>
                                  {option}
                                </option>
                              ))}
                            </select>
                          ) : (
                            teamUser.roles.join(", ") || "—"
                          )}
                        </td>
                        <td>
                          <span
                            className={`badge ${teamUser.is_active ? "badge-active" : "badge-inactive"}`}
                          >
                            {teamUser.is_active ? "Active" : "Inactive"}
                          </span>
                        </td>
                        {canManageUsers && (
                          <td>
                            {isSelf ? (
                              <span className="muted" style={{ fontSize: "0.8rem" }}>
                                —
                              </span>
                            ) : teamUser.is_active ? (
                              <button
                                type="button"
                                className="btn btn-danger btn-sm"
                                onClick={() => openDeactivateModal(teamUser)}
                              >
                                Deactivate
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="btn btn-ghost btn-sm"
                                onClick={() => setPendingReactivate(teamUser)}
                              >
                                Reactivate
                              </button>
                            )}
                          </td>
                        )}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      {canManageUsers && showForm && (
        <Modal title="Add a team member" onClose={closeForm}>
          <form onSubmit={handleSubmit} noValidate>
            <label className="field">
              <span>Full name</span>
              <input
                required
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                disabled={createUserMutation.isPending}
              />
            </label>

            <label className="field">
              <span>Email</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                disabled={createUserMutation.isPending}
              />
            </label>

            <label className="field">
              <span>Temporary password</span>
              <input
                type="password"
                required
                minLength={10}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={createUserMutation.isPending}
              />
              <span className="field-hint">At least 10 characters.</span>
            </label>

            <label className="field">
              <span>Role</span>
              <select
                value={role}
                onChange={(e) => setRole(e.target.value as AssignableRole)}
                disabled={createUserMutation.isPending}
              >
                {ASSIGNABLE_ROLES.map((option) => (
                  <option key={option} value={option}>
                    {option}
                  </option>
                ))}
              </select>
            </label>

            {formError && <Alert>{formError}</Alert>}

            <div className="btn-group" style={{ marginTop: "1rem" }}>
              <button type="submit" className="btn btn-primary" disabled={createUserMutation.isPending}>
                {createUserMutation.isPending ? <Spinner label="Creating…" /> : "Create user"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={closeForm}
                disabled={createUserMutation.isPending}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}

      {pendingDeactivate && (
        <Modal title="Deactivate team member" onClose={closeDeactivateModal}>
          <form onSubmit={handleDeactivateSubmit}>
            <p>
              <strong>Team member:</strong> {pendingDeactivate.full_name}
              <br />
              <strong>Email:</strong> {pendingDeactivate.email}
            </p>
            <p className="muted">
              This immediately revokes {pendingDeactivate.full_name}'s ability to sign in. Their
              past work (jobs, assessments, notes, etc.) is preserved, and this action is recorded
              in Activities.
            </p>
            <label className="field">
              <span>Reason (optional)</span>
              <textarea
                rows={3}
                value={deactivateReason}
                onChange={(e) => setDeactivateReason(e.target.value)}
                disabled={deactivateMutation.isPending}
                placeholder="e.g. Left the team"
              />
            </label>

            {deactivateError && <Alert>{deactivateError}</Alert>}

            <div className="btn-group" style={{ marginTop: "1rem" }}>
              <button type="submit" className="btn btn-danger" disabled={deactivateMutation.isPending}>
                {deactivateMutation.isPending ? <Spinner label="Deactivating…" /> : "Deactivate"}
              </button>
              <button
                type="button"
                className="btn btn-ghost"
                onClick={closeDeactivateModal}
                disabled={deactivateMutation.isPending}
              >
                Cancel
              </button>
            </div>
          </form>
        </Modal>
      )}

      {pendingReactivate && (
        <ConfirmDialog
          title="Reactivate this team member?"
          message={`${pendingReactivate.full_name} will be able to sign in again immediately.`}
          confirmLabel="Reactivate"
          danger={false}
          isConfirming={reactivateMutation.isPending}
          onCancel={() => setPendingReactivate(null)}
          onConfirm={() => reactivateMutation.mutate()}
        />
      )}
    </div>
  );
}
