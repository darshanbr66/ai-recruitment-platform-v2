import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { useAuth } from "../../auth/AuthContext";
import type { OrganizationResponse } from "../../../types/auth";
import { createOrganization, listOrganizations, updateOrganizationSettings } from "../../auth/api";

const ORGANIZATIONS_QUERY_KEY = ["admin", "organizations"];

/** Inline editor for the organization's careers contact email — the address
 * candidates see on the careers site and in system emails ("need to update
 * your information? contact ..."). Configuration, never hardcoded. */
function CareersContactCell({ org }: { org: OrganizationResponse }) {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(org.careers_contact_email ?? "");
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: () =>
      updateOrganizationSettings(
        org.id,
        { careers_contact_email: value.trim() || null },
        accessToken as string,
      ),
    onSuccess: () => {
      setEditing(false);
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ORGANIZATIONS_QUERY_KEY });
    },
    onError: (err) => setError(err instanceof ApiError ? err.message : "Could not save."),
  });

  if (!editing) {
    return (
      <span className="contact-cell">
        {org.careers_contact_email ?? <span className="muted">Not set</span>}
        <button
          type="button"
          className="link-button"
          onClick={() => {
            setValue(org.careers_contact_email ?? "");
            setEditing(true);
          }}
          aria-label={`Edit careers contact for ${org.name}`}
        >
          Edit
        </button>
      </span>
    );
  }

  return (
    <form
      className="contact-cell"
      onSubmit={(event) => {
        event.preventDefault();
        mutation.mutate();
      }}
    >
      <input
        type="email"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="careers@company.com"
        aria-label={`Careers contact email for ${org.name}`}
        disabled={mutation.isPending}
      />
      <button type="submit" className="btn btn-primary btn-sm" disabled={mutation.isPending}>
        {mutation.isPending ? "Saving…" : "Save"}
      </button>
      <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(false)}>
        Cancel
      </button>
      {error && <span className="field-error">{error}</span>}
    </form>
  );
}

/**
 * Platform-admin console: bootstraps a brand-new tenant (Organization +
 * its first ORG_ADMIN user) in one call — see
 * backend/app/services/organization_service.py::bootstrap_organization.
 * This is the real "register a new organization" flow; there is no
 * separate public self-serve signup in Phase 2 (only a SUPER_ADMIN can
 * create a tenant, since a tenant with zero users has nobody to manage it).
 */
export function OrganizationsPage() {
  const { accessToken } = useAuth();
  const queryClient = useQueryClient();

  const organizationsQuery = useQuery({
    queryKey: ORGANIZATIONS_QUERY_KEY,
    queryFn: () => listOrganizations(accessToken as string),
    enabled: accessToken !== null,
  });

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [adminFullName, setAdminFullName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [justCreatedSlug, setJustCreatedSlug] = useState<string | null>(null);

  const createOrgMutation = useMutation({
    mutationFn: () =>
      createOrganization(
        {
          name,
          slug,
          admin_full_name: adminFullName,
          admin_email: adminEmail,
          admin_password: adminPassword,
        },
        accessToken as string,
      ),
    onSuccess: (created) => {
      setJustCreatedSlug(created.slug);
      setName("");
      setSlug("");
      setAdminFullName("");
      setAdminEmail("");
      setAdminPassword("");
      setFormError(null);
      void queryClient.invalidateQueries({ queryKey: ORGANIZATIONS_QUERY_KEY });
    },
    onError: (err) => {
      setJustCreatedSlug(null);
      setFormError(err instanceof ApiError ? err.message : "Unable to reach the server.");
    },
  });

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    createOrgMutation.mutate();
  }

  return (
    <div className="stack-lg">
      <section>
        <h1>Organizations</h1>
        <p className="muted">Every tenant on the platform.</p>
      </section>

      {organizationsQuery.isPending && <p role="status">Loading organizations…</p>}
      {organizationsQuery.isError && (
        <Alert>
          {organizationsQuery.error instanceof ApiError
            ? organizationsQuery.error.message
            : "Could not load organizations."}
        </Alert>
      )}

      {organizationsQuery.isSuccess && (
        <section>
          {organizationsQuery.data.length === 0 ? (
            <div className="empty-state">
              <p className="empty-state-title">No organizations yet</p>
              <p>Create the first one below.</p>
            </div>
          ) : (
            <div className="table-scroll">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Slug</th>
                    <th>Status</th>
                    <th>Careers contact</th>
                    <th>Created</th>
                  </tr>
                </thead>
                <tbody>
                  {organizationsQuery.data.map((org) => (
                    <tr key={org.id}>
                      <td>{org.name}</td>
                      <td>
                        <code>{org.slug}</code>
                      </td>
                      <td>
                        <span className="badge badge-active">{org.status}</span>
                      </td>
                      <td>
                        <CareersContactCell org={org} />
                      </td>
                      <td>{new Date(org.created_at).toLocaleDateString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}

      <section className="card">
        <h2>Register a new organization</h2>
        <p className="muted">
          Creates the tenant and its first ORG_ADMIN account together — that admin can then sign
          in and invite the rest of their team from the Users page.
        </p>
        <form onSubmit={handleSubmit} noValidate>
          <label className="field">
            <span>Organization name</span>
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
              disabled={createOrgMutation.isPending}
            />
          </label>

          <label className="field">
            <span>Slug</span>
            <input
              required
              pattern="^[a-z0-9]+(-[a-z0-9]+)*$"
              placeholder="acme-corp"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              disabled={createOrgMutation.isPending}
            />
            <span className="field-hint">Lowercase letters, digits, and single hyphens only.</span>
          </label>

          <label className="field">
            <span>Admin full name</span>
            <input
              required
              value={adminFullName}
              onChange={(e) => setAdminFullName(e.target.value)}
              disabled={createOrgMutation.isPending}
            />
          </label>

          <label className="field">
            <span>Admin email</span>
            <input
              type="email"
              required
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
              disabled={createOrgMutation.isPending}
            />
          </label>

          <label className="field">
            <span>Admin temporary password</span>
            <input
              type="password"
              required
              minLength={10}
              value={adminPassword}
              onChange={(e) => setAdminPassword(e.target.value)}
              disabled={createOrgMutation.isPending}
            />
            <span className="field-hint">At least 10 characters.</span>
          </label>

          {formError && <Alert>{formError}</Alert>}
          {justCreatedSlug && (
            <Alert variant="success">Organization "{justCreatedSlug}" created.</Alert>
          )}

          <button type="submit" className="btn btn-primary" disabled={createOrgMutation.isPending}>
            {createOrgMutation.isPending ? "Creating…" : "Create organization"}
          </button>
        </form>
      </section>
    </div>
  );
}
