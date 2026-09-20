import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { ApiError } from "../../../lib/apiClient";
import { Alert } from "../../../shared/components/Alert";
import { Icon } from "../../../shared/components/Icon";
import { Spinner } from "../../../shared/components/Spinner";
import type {
  EmailComposeRequest,
  EmailComposeResponse,
  EmailDraft,
  EmailTemplateField,
  EmailTemplateKey,
} from "../../../types/email";
import { composeEmail, listEmailTemplates, previewEmail, sendEmail } from "../applications/api";
import { composeGeneralEmail, previewGeneralEmail, sendGeneralEmail } from "./api";

/** What the email is about: one application (the candidate is the recipient and
 * the record supplies name/role) or nothing in particular (a general email to
 * addresses the sender types). */
export type ComposerTarget =
  | { kind: "application"; applicationId: string; candidateName: string; candidateEmail: string }
  | { kind: "general" };

export interface SentEmail {
  to: string[];
  subject: string;
}

interface Recipients {
  to: string[];
  cc: string[];
  bcc: string[];
}

interface PreviewView extends Recipients {
  replyTo: string;
  subject: string;
  html: string;
}

// Deliberately loose: the server does the authoritative validation. This only
// catches obvious typos before a round trip.
const EMAIL_PATTERN = /^[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+$/;

/** "a@x.com, b@y.com; c@z.com" -> ["a@x.com", "b@y.com", "c@z.com"]. */
function parseAddresses(text: string): string[] {
  return text
    .split(/[\s,;]+/)
    .map((token) => token.trim().replace(/^<|>$/g, ""))
    .filter(Boolean);
}

function invalidAddresses(addresses: string[]): string[] {
  return addresses.filter((address) => !EMAIL_PATTERN.test(address));
}

function errorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function TemplateFieldInput({
  field,
  value,
  onChange,
}: {
  field: EmailTemplateField;
  value: string;
  onChange: (value: string) => void;
}) {
  const label = field.required ? `${field.label} *` : field.label;
  let input;
  if (field.input_type === "select") {
    input = (
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select…</option>
        {field.options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    );
  } else if (field.input_type === "textarea") {
    input = (
      <textarea
        rows={3}
        value={value}
        placeholder={field.placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  } else {
    input = (
      <input
        type={field.input_type}
        value={value}
        placeholder={field.placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    );
  }
  return (
    <label className="field">
      <span>{label}</span>
      {input}
    </label>
  );
}

/**
 * The one place email is composed and sent from — always an explicit user
 * action, never a side effect of applying, assigning an assessment or changing
 * a status. Flow: (general only: enter recipients) -> choose a template -> the
 * server fills in the known details -> edit the subject/body if needed ->
 * preview the real HTML -> send. The predefined template is never modified;
 * edits belong to this one email.
 *
 * Which fields show, the placeholder rules and the final HTML all come from the
 * server (the same code path renders the preview and the sent email), so
 * nothing here can drift from what the recipient actually receives. The SMTP
 * account is server-side only; nothing in this component can see or choose it.
 */
export function EmailComposer({
  target,
  accessToken,
  initialTemplate,
  onCancel,
  onSent,
  onBusyChange,
}: {
  target: ComposerTarget;
  accessToken: string;
  initialTemplate?: EmailTemplateKey;
  onCancel: () => void;
  onSent: (result: SentEmail) => void;
  onBusyChange?: (busy: boolean) => void;
}) {
  const isGeneral = target.kind === "general";
  const targetKey = target.kind === "application" ? target.applicationId : "general";

  const tokenRef = useRef(accessToken);
  useEffect(() => {
    tokenRef.current = accessToken;
  }, [accessToken]);
  // The latest target for the async callbacks below, without re-triggering them.
  const targetRef = useRef(target);
  useEffect(() => {
    targetRef.current = target;
  }, [target]);

  const [toText, setToText] = useState("");
  const [ccText, setCcText] = useState("");
  const [bccText, setBccText] = useState("");
  const [recipientError, setRecipientError] = useState<string | null>(null);

  const [templateKey, setTemplateKey] = useState<EmailTemplateKey | "">(initialTemplate ?? "");
  const [variables, setVariables] = useState<Record<string, string>>({});
  const [subject, setSubject] = useState("");
  const [body, setBody] = useState("");
  // True once the user has typed in the subject/body — from then on a change to
  // the template fields no longer overwrites their text.
  const [edited, setEdited] = useState(false);
  const [reloadCount, setReloadCount] = useState(0);
  const [composing, setComposing] = useState(false);
  const [composeError, setComposeError] = useState<string | null>(null);
  const [missingRequired, setMissingRequired] = useState<string[]>([]);
  const [step, setStep] = useState<"edit" | "preview">("edit");
  const [previewView, setPreviewView] = useState<PreviewView | null>(null);

  const templatesQuery = useQuery({
    queryKey: ["recruiter", "email-templates"],
    queryFn: () => listEmailTemplates(tokenRef.current),
    staleTime: Infinity,
  });
  const template = templatesQuery.data?.find((t) => t.key === templateKey);
  const templateFields: EmailTemplateField[] = template
    ? ((isGeneral ? template.general_fields : template.fields) ?? [])
    : [];

  function composeRequest(request: EmailComposeRequest): Promise<EmailComposeResponse> {
    const current = targetRef.current;
    return current.kind === "application"
      ? composeEmail(current.applicationId, request, tokenRef.current)
      : composeGeneralEmail(request, tokenRef.current);
  }

  // Load (or re-load) the template text from the server.
  useEffect(() => {
    if (templateKey === "" || edited) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      setComposing(true);
      setComposeError(null);
      try {
        const composed = await composeRequest({ template_key: templateKey, variables });
        if (cancelled) return;
        setSubject(composed.subject);
        setBody(composed.body);
        setMissingRequired(composed.missing_required);
      } catch (error) {
        if (!cancelled) setComposeError(errorMessage(error, "Could not load the template."));
      } finally {
        if (!cancelled) setComposing(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
    // composeRequest reads refs only, so it is stable for this effect's purposes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetKey, templateKey, variables, edited, reloadCount]);

  const draft: EmailDraft | null =
    templateKey === "" ? null : { template_key: templateKey, subject, body, variables };

  function currentRecipients(): Recipients {
    return {
      to: parseAddresses(toText),
      cc: parseAddresses(ccText),
      bcc: parseAddresses(bccText),
    };
  }

  const previewMutation = useMutation({
    mutationFn: async (value: EmailDraft): Promise<PreviewView> => {
      const current = targetRef.current;
      if (current.kind === "application") {
        const result = await previewEmail(current.applicationId, value, tokenRef.current);
        return {
          to: [result.to],
          cc: [],
          bcc: [],
          replyTo: result.reply_to,
          subject: result.subject,
          html: result.html,
        };
      }
      const result = await previewGeneralEmail(
        { ...value, ...currentRecipients() },
        tokenRef.current,
      );
      return {
        to: result.to,
        cc: result.cc,
        bcc: result.bcc,
        replyTo: result.reply_to,
        subject: result.subject,
        html: result.html,
      };
    },
    onSuccess: (view) => {
      setPreviewView(view);
      setStep("preview");
    },
  });

  const sendMutation = useMutation({
    mutationFn: async (value: EmailDraft): Promise<SentEmail> => {
      const current = targetRef.current;
      if (current.kind === "application") {
        const result = await sendEmail(current.applicationId, value, tokenRef.current);
        return { to: [result.to], subject: result.subject };
      }
      const result = await sendGeneralEmail({ ...value, ...currentRecipients() }, tokenRef.current);
      return { to: [...result.to, ...result.cc, ...result.bcc], subject: result.subject };
    },
    onSuccess: (result) => onSent(result),
  });

  const busy = previewMutation.isPending || sendMutation.isPending;
  useEffect(() => {
    onBusyChange?.(busy);
  }, [busy, onBusyChange]);

  function selectTemplate(key: EmailTemplateKey | "") {
    setTemplateKey(key);
    setVariables({});
    setEdited(false);
    setSubject("");
    setBody("");
    setMissingRequired([]);
    setComposeError(null);
    previewMutation.reset();
  }

  function resetToTemplate() {
    setEdited(false);
    setReloadCount((count) => count + 1);
  }

  function handlePreview() {
    if (!draft) return;
    if (isGeneral) {
      const { to, cc, bcc } = currentRecipients();
      const bad = invalidAddresses([...to, ...cc, ...bcc]);
      if (to.length === 0) {
        setRecipientError("Enter at least one recipient in To.");
        return;
      }
      if (bad.length > 0) {
        setRecipientError(`Not a valid email address: ${bad.join(", ")}`);
        return;
      }
    }
    setRecipientError(null);
    previewMutation.mutate(draft);
  }

  const canPreview = draft !== null && !composing && subject.trim() !== "" && body.trim() !== "";

  return (
    <>
      <ol className="composer-steps" aria-label="Email steps">
        <li className={step === "edit" ? "is-current" : "is-done"} aria-current={step === "edit" ? "step" : undefined}>
          <span className="composer-step-dot" aria-hidden="true">
            {step === "edit" ? 1 : <Icon name="check" size={11} />}
          </span>
          Compose
        </li>
        <li className={step === "preview" ? "is-current" : undefined} aria-current={step === "preview" ? "step" : undefined}>
          <span className="composer-step-dot" aria-hidden="true">
            2
          </span>
          Review &amp; send
        </li>
      </ol>

      {target.kind === "application" ? (
        <p className="composer-note">
          <Icon name="shield" size={16} />
          <span>
            To: {target.candidateName} &lt;{target.candidateEmail}&gt; — sent only when you click Send.
            Nothing is emailed automatically.
          </span>
        </p>
      ) : (
        <p className="composer-note">
          <Icon name="shield" size={16} />
          <span>
            Sent from your organization's mailing account; replies come to you. Nothing is sent until
            you click Send, and every send is recorded in Activities.
          </span>
        </p>
      )}

      {step === "edit" && (
        <>
          {isGeneral && (
            <>
              <label className="field">
                <span>To *</span>
                <input
                  type="text"
                  inputMode="email"
                  value={toText}
                  placeholder="name@example.com (separate several with commas)"
                  onChange={(e) => setToText(e.target.value)}
                  disabled={busy}
                />
              </label>
              <div className="field-row">
                <label className="field">
                  <span>Cc</span>
                  <input
                    type="text"
                    inputMode="email"
                    value={ccText}
                    onChange={(e) => setCcText(e.target.value)}
                    disabled={busy}
                  />
                </label>
                <label className="field">
                  <span>Bcc</span>
                  <input
                    type="text"
                    inputMode="email"
                    value={bccText}
                    onChange={(e) => setBccText(e.target.value)}
                    disabled={busy}
                  />
                </label>
              </div>
            </>
          )}

          <label className="field">
            <span>Template</span>
            <select
              value={templateKey}
              onChange={(e) => selectTemplate(e.target.value as EmailTemplateKey | "")}
              disabled={templatesQuery.isPending || busy}
            >
              <option value="">Select a template…</option>
              {templatesQuery.data?.map((t) => {
                const unavailable = isGeneral && t.general_fields === null;
                return (
                  <option key={t.key} value={t.key} disabled={unavailable}>
                    {unavailable ? `${t.name} (needs an application)` : t.name}
                  </option>
                );
              })}
            </select>
          </label>
          {template && (
            <p className="field-hint" style={{ marginTop: "-0.5rem" }}>
              {template.description}
            </p>
          )}
          {templatesQuery.isError && (
            <Alert>{errorMessage(templatesQuery.error, "Could not load the email templates.")}</Alert>
          )}

          {template && templateFields.length > 0 && (
            <fieldset className="field">
              <legend>Template details</legend>
              {templateFields.map((field) => (
                <TemplateFieldInput
                  key={field.key}
                  field={field}
                  value={variables[field.key] ?? ""}
                  onChange={(value) => setVariables((current) => ({ ...current, [field.key]: value }))}
                />
              ))}
              {edited && (
                <p className="field-hint" style={{ margin: 0 }}>
                  You have edited the text below, so these details no longer update it.{" "}
                  <button type="button" className="btn btn-ghost btn-sm" onClick={resetToTemplate}>
                    Reset to template
                  </button>
                </p>
              )}
            </fieldset>
          )}

          {composing && <p role="status">Loading template…</p>}
          {composeError && <Alert>{composeError}</Alert>}
          {missingRequired.length > 0 && !composing && (
            <p className="field-hint">
              Fill in the required details above (marked *) before previewing.
            </p>
          )}

          {template && (
            <>
              <label className="field">
                <span>Subject</span>
                <input
                  value={subject}
                  onChange={(e) => {
                    setSubject(e.target.value);
                    setEdited(true);
                  }}
                  disabled={busy}
                />
              </label>
              <label className="field">
                <span>Message</span>
                <textarea
                  rows={14}
                  value={body}
                  onChange={(e) => {
                    setBody(e.target.value);
                    setEdited(true);
                  }}
                  disabled={busy}
                />
              </label>
              <p className="field-hint" style={{ marginTop: "-0.5rem" }}>
                Edit freely — this changes only this email, never the template. Leave a blank line
                between paragraphs.
              </p>
              {edited && (
                <button type="button" className="btn btn-ghost btn-sm" onClick={resetToTemplate}>
                  Reset to template
                </button>
              )}
            </>
          )}

          {recipientError && <Alert>{recipientError}</Alert>}
          {previewMutation.isError && (
            <Alert>{errorMessage(previewMutation.error, "Could not preview the email.")}</Alert>
          )}

          <div className="btn-group" style={{ marginTop: "1rem" }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!canPreview || busy}
              onClick={handlePreview}
            >
              {previewMutation.isPending ? <Spinner label="Preparing preview…" /> : "Preview"}
            </button>
            <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
              Cancel
            </button>
          </div>
        </>
      )}

      {step === "preview" && previewView && draft && (
        <>
          <div className="stack-sm" style={{ marginBottom: "0.75rem" }}>
            <div className="detail-row">
              <span className="detail-row-label">To</span>
              <span>{previewView.to.join(", ")}</span>
            </div>
            {previewView.cc.length > 0 && (
              <div className="detail-row">
                <span className="detail-row-label">Cc</span>
                <span>{previewView.cc.join(", ")}</span>
              </div>
            )}
            {previewView.bcc.length > 0 && (
              <div className="detail-row">
                <span className="detail-row-label">Bcc</span>
                <span>{previewView.bcc.join(", ")}</span>
              </div>
            )}
            <div className="detail-row">
              <span className="detail-row-label">Replies go to</span>
              <span>{previewView.replyTo}</span>
            </div>
            <div className="detail-row">
              <span className="detail-row-label">Subject</span>
              <strong>{previewView.subject}</strong>
            </div>
          </div>
          {/* The rendered email is untrusted markup: sandbox with no
              permissions, so nothing in it can run script or navigate. */}
          <iframe
            title="Email preview"
            sandbox=""
            srcDoc={previewView.html}
            style={{
              width: "100%",
              height: "440px",
              border: "1px solid var(--color-border)",
              borderRadius: "8px",
              background: "#ffffff",
            }}
          />
          {sendMutation.isError && (
            <Alert>{errorMessage(sendMutation.error, "The email could not be sent.")}</Alert>
          )}
          <div className="btn-group" style={{ marginTop: "1rem" }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={busy}
              onClick={() => sendMutation.mutate(draft)}
            >
              {sendMutation.isPending ? <Spinner label="Sending…" /> : "Send email"}
            </button>
            <button
              type="button"
              className="btn btn-ghost"
              disabled={busy}
              onClick={() => {
                sendMutation.reset();
                setStep("edit");
              }}
            >
              Back to edit
            </button>
            <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={busy}>
              Cancel
            </button>
          </div>
        </>
      )}
    </>
  );
}
