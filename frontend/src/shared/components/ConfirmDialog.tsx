import { useState } from "react";

/**
 * Confirmation dialog. For especially destructive actions pass
 * `requireTypedText`: the confirm button then stays disabled until the user
 * types that exact text, so it can't be triggered by a stray click or Enter.
 */
export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Confirm",
  danger = true,
  isConfirming = false,
  requireTypedText,
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmLabel?: string;
  danger?: boolean;
  isConfirming?: boolean;
  requireTypedText?: string;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const [typed, setTyped] = useState("");
  const confirmationSatisfied = requireTypedText === undefined || typed === requireTypedText;

  return (
    <div className="dialog-overlay" role="presentation" onClick={onCancel}>
      <div
        className="dialog-card"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 id="confirm-dialog-title">{title}</h2>
        <p className="muted">{message}</p>
        {requireTypedText !== undefined && (
          <label className="field">
            <span>
              Type <strong>{requireTypedText}</strong> to confirm
            </span>
            <input
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              autoComplete="off"
              disabled={isConfirming}
            />
          </label>
        )}
        <div className="dialog-actions">
          <button type="button" className="btn btn-ghost" onClick={onCancel} disabled={isConfirming}>
            Cancel
          </button>
          <button
            type="button"
            className={danger ? "btn btn-danger" : "btn btn-primary"}
            onClick={onConfirm}
            disabled={isConfirming || !confirmationSatisfied}
          >
            {isConfirming ? "Working…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
