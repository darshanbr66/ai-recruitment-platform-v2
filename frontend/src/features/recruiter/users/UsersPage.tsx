import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { ASSIGNABLE_ROLES, type AssignableRole } from "../../../types/auth";
import { Alert } from "../../../shared/components/Alert";
import { useAuth } from "../../auth/AuthContext";
import { createUser, listUsers } from "../../auth/api";

const USERS_QUERY_KEY = ["recruiter", "users"];

export function UsersPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const usersQuery = useQuery({
    queryKey: USERS_QUERY_KEY,
    queryFn: () => listUsers(accessToken as string),
    enabled: accessToken !== null,
  });

  const [email, setEmail] = useState("");
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<AssignableRole>("RECRUITER");
  const [formError, setFormError] = useState<string | null>(null);
  const [justCreatedEmail, setJustCreatedEmail] = useState<string | null>(null);

  const createUserMutation = useMutation({
    mutationFn: () =>
      createUser({ email, password, full_name: fullName, role }, accessToken as string),
    onSuccess: (created) => {
      setJustCreatedEmail(created.email);
      setEmail("");
      setFullName("");
      setPassword("");
      setRole("RECRUITER");
      setFormError(null);
      void queryClient.invalidateQueries({ queryKey: USERS_QUERY_KEY });
    },
    onError: (err) => {
      setJustCreatedEmail(null);
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createUserMutation.mutate();
  }

  // Today only ORG_ADMIN holds `user.read` (seeded in the Phase 2 migration),
  // and ORG_ADMIN is also the only role holding `user.create` — so a
  // successful list load already implies create access too.
  const canManageUsers = !(usersQuery.error instanceof ApiError && usersQuery.error.status === 403);

  return (
    <div className="stack-lg">
      <section>
        <h1>Users</h1>
        <p className="muted">Staff accounts within your organization.</p>
      </section>

      {usersQuery.isPending && <p role="status">Loading team members…</p>}

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
            <p className="muted">No team members yet.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Roles</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {usersQuery.data.map((teamUser) => (
                  <tr key={teamUser.id}>
                    <td>{teamUser.full_name}</td>
                    <td>{teamUser.email}</td>
                    <td>{teamUser.roles.join(", ") || "—"}</td>
                    <td>
                      <span
                        className={`badge ${teamUser.is_active ? "badge-active" : "badge-inactive"}`}
                      >
                        {teamUser.is_active ? "Active" : "Inactive"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}

      {canManageUsers && (
        <section className="card">
          <h2>Add a team member</h2>
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
            {justCreatedEmail && (
              <Alert variant="success">Created account for {justCreatedEmail}.</Alert>
            )}

            <button type="submit" className="btn btn-primary" disabled={createUserMutation.isPending}>
              {createUserMutation.isPending ? "Creating…" : "Create user"}
            </button>
          </form>
        </section>
      )}
    </div>
  );
}
