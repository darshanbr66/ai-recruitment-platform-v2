import { useState } from "react";
import { Modal } from "../../../shared/components/Modal";
import type { EmailSendResult, EmailTemplateKey } from "../../../types/email";
import { EmailComposer } from "../email/EmailComposer";

/**
 * "Send Email" for one application: the shared composer (see
 * `../email/EmailComposer.tsx`) in a dialog, addressed to that application's
 * candidate. The same composer, unaddressed, powers the general Email page.
 */
export function EmailComposerModal({
  applicationId,
  candidateName,
  candidateEmail,
  accessToken,
  initialTemplate,
  onClose,
  onSent,
}: {
  applicationId: string;
  candidateName: string;
  candidateEmail: string;
  accessToken: string;
  initialTemplate?: EmailTemplateKey;
  onClose: () => void;
  onSent: (result: EmailSendResult) => void;
}) {
  // The dialog can't be dismissed (Esc / backdrop) while a request is in flight.
  const [busy, setBusy] = useState(false);

  return (
    <Modal title="Send Email" onClose={busy ? () => undefined : onClose} wide>
      <EmailComposer
        target={{ kind: "application", applicationId, candidateName, candidateEmail }}
        accessToken={accessToken}
        initialTemplate={initialTemplate}
        onCancel={onClose}
        onBusyChange={setBusy}
        onSent={(result) => onSent({ sent: true, to: result.to[0] ?? candidateEmail, subject: result.subject })}
      />
    </Modal>
  );
}
