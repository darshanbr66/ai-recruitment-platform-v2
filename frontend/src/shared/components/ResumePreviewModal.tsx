import { useEffect, useState } from "react";
import { ApiError } from "../../lib/apiClient";
import { triggerBlobDownload } from "../../lib/downloadBlob";
import { Alert } from "./Alert";
import { Modal } from "./Modal";

/** Fetches the resume through the same authenticated, tenant-scoped
 * download endpoint as a plain download (never exposes the raw storage
 * path — the URL is always `/api/v1/recruiter/applications/{id}/resume`)
 * and renders it in-page for file types the browser can display inline.
 * Falls back to a "preview not available" message with a Download button
 * for anything else (e.g. .doc/.docx). */
export function ResumePreviewModal({
  filename,
  fetchResume,
  onClose,
}: {
  filename: string;
  fetchResume: () => Promise<{ blob: Blob; filename: string | null }>;
  onClose: () => void;
}) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "error"; message: string }
    | { status: "ready"; blob: Blob; objectUrl: string; resolvedFilename: string }
  >({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    let objectUrl: string | null = null;

    async function load() {
      try {
        const { blob, filename: serverFilename } = await fetchResume();
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setState({ status: "ready", blob, objectUrl, resolvedFilename: serverFilename ?? filename });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load the resume.",
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function download() {
    if (state.status !== "ready") return;
    triggerBlobDownload(state.blob, state.resolvedFilename);
  }

  const canPreviewInline = state.status === "ready" && state.blob.type === "application/pdf";

  return (
    <Modal title="Resume preview" onClose={onClose} wide>
      {state.status === "loading" && <p role="status">Loading resume…</p>}
      {state.status === "error" && <Alert>{state.message}</Alert>}

      {state.status === "ready" && (
        <div className="stack-sm">
          {canPreviewInline ? (
            <iframe
              src={state.objectUrl}
              title="Resume preview"
              style={{
                width: "100%",
                height: "70vh",
                border: "1px solid var(--color-border)",
                borderRadius: 8,
              }}
            />
          ) : (
            <p className="muted">
              Preview is not available for this file type ({state.resolvedFilename}). Download it to
              view the contents.
            </p>
          )}
          <div className="btn-group" style={{ marginTop: "0.75rem" }}>
            <button type="button" className="btn btn-primary btn-sm" onClick={download}>
              Download
            </button>
            <button type="button" className="btn btn-ghost btn-sm" onClick={onClose}>
              Close
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
