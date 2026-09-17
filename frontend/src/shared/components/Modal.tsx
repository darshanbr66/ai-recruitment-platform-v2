import { useEffect, type ReactNode } from "react";

/** Generic dialog surface — dimmed backdrop, background not interactive
 * while open, Escape-to-close, click-outside-to-close. Reuses the same
 * `.dialog-overlay`/`.dialog-card` styling as ConfirmDialog so every modal
 * in the app looks and behaves the same way. */
export function Modal({
  title,
  onClose,
  children,
  wide = false,
}: {
  title: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  return (
    <div className="dialog-overlay" role="presentation" onClick={onClose}>
      <div
        className="dialog-card"
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        style={wide ? { maxWidth: "640px", maxHeight: "90vh", overflowY: "auto" } : undefined}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="page-header" style={{ marginBottom: "1rem" }}>
          <h2 id="modal-title" style={{ margin: 0 }}>
            {title}
          </h2>
          <button type="button" className="btn btn-ghost btn-sm" aria-label="Close" onClick={onClose}>
            &times;
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
