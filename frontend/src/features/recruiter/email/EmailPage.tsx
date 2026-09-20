import { useState } from "react";
import { Alert } from "../../../shared/components/Alert";
import { useAuth } from "../../auth/AuthContext";
import { EmailComposer } from "./EmailComposer";

/**
 * General email: a professional, templated message to any address, sent from
 * the organization's configured mailing account — for HR/recruitment
 * communication that isn't tied to one application (partners, hiring managers,
 * colleges, anyone the sender types). It reuses the same composer, templates
 * and HTML layout as "Send Email" on an application, and every send is
 * recorded in Activities.
 *
 * UX gate only: the backend requires `application.email.send` (ORG_ADMIN and
 * RECRUITER) on every compose/preview/send call.
 */
export function EmailPage() {
  const { accessToken, user } = useAuth();
  const canSend = user?.roles.some((role) => role === "ORG_ADMIN" || role === "RECRUITER") ?? false;
  // Bumping the key remounts the composer, which is how "Cancel" (and a
  // successful send) return it to a clean, empty state.
  const [composerKey, setComposerKey] = useState(0);
  const [lastSent, setLastSent] = useState<string | null>(null);

  return (
    <div className="stack-lg">
      <div className="page-header">
        <div>
          <h1>Email</h1>
          <p className="muted">
            Send a professional email from a template to anyone — not just candidates. Pick a
            template, edit it if you like, preview it, then send. Nothing is sent until you click
            Send.
          </p>
        </div>
      </div>

      {!canSend && <Alert>You do not have permission to send email.</Alert>}

      {lastSent && <Alert variant="success">{lastSent}</Alert>}

      {canSend && accessToken !== null && (
        <section className="card email-page-card">
          <EmailComposer
            key={composerKey}
            target={{ kind: "general" }}
            accessToken={accessToken}
            onCancel={() => {
              setLastSent(null);
              setComposerKey((key) => key + 1);
            }}
            onSent={(result) => {
              setLastSent(`Email sent to ${result.to.join(", ")}: "${result.subject}".`);
              setComposerKey((key) => key + 1);
            }}
          />
        </section>
      )}
    </div>
  );
}
