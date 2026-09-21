import { useEffect, useLayoutEffect, useRef, useState, type FormEvent, type KeyboardEvent } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../../shared/components/Icon";
import { useMediaQuery } from "../../shared/hooks/useMediaQuery";
import { useReducedMotion } from "../../shared/hooks/useReducedMotion";
import { SIGVI_MAX_MESSAGE_CHARS } from "../../types/sigvi";
import { FormattedMessage } from "./formatMessage";
import { SigviAvatar } from "./SigviAvatar";
import { SigviJobCard } from "./SigviJobCard";
import { SIGVI_SUGGESTIONS } from "./suggestions";
import { useSigviChat, type ChatTurn } from "./useSigviChat";

const MOBILE_QUERY = "(max-width: 640px)";
const COUNTER_FROM = Math.floor(SIGVI_MAX_MESSAGE_CHARS * 0.8);

function AssistantTurn({ turn, onNavigate }: { turn: ChatTurn; onNavigate: () => void }) {
  const knowledge = (turn.sources ?? []).filter((source) => source.type === "knowledge");
  return (
    <div className="sigvi-row sigvi-row-assistant">
      <SigviAvatar size={26} />
      <div className="sigvi-stack">
        <div className="sigvi-bubble sigvi-bubble-assistant">
          <FormattedMessage text={turn.content} />
        </div>
        {turn.jobs && turn.jobs.length > 0 && (
          <div className="sigvi-jobs">
            {turn.jobs.map((job) => (
              <SigviJobCard key={job.id} job={job} onNavigate={onNavigate} />
            ))}
          </div>
        )}
        {knowledge.length > 0 && (
          <p className="sigvi-sources">
            Based on: {knowledge.map((source) => source.title).join(" · ")}
          </p>
        )}
      </div>
    </div>
  );
}

/**
 * The floating Sigvi assistant. Rendered through a portal into <body> for the
 * same reason `Modal` is: a `position: fixed` element inside a transformed
 * ancestor is positioned against that ancestor, not the viewport.
 *
 * Non-modal on desktop (the page stays usable beside it), a full-screen sheet
 * on phones. Escape closes it and returns focus to the launcher.
 */
export function SigviWidget({ organizationSlug }: { organizationSlug?: string }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState("");
  const { turns, status, error, send, retry, clear } = useSigviChat({ organizationSlug });
  const isMobile = useMediaQuery(MOBILE_QUERY);
  const reducedMotion = useReducedMotion();

  const launcherRef = useRef<HTMLButtonElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const logRef = useRef<HTMLDivElement>(null);
  const restoreFocus = useRef(false);
  const composing = useRef(false);

  const pending = status === "pending";

  // Opening moves focus to the message box; closing (button / Escape) returns
  // it to the launcher. Following a link out of the panel does neither.
  useEffect(() => {
    if (open) {
      inputRef.current?.focus({ preventScroll: true });
    } else if (restoreFocus.current) {
      restoreFocus.current = false;
      launcherRef.current?.focus({ preventScroll: true });
    }
  }, [open]);

  // Keep the newest message in view.
  useLayoutEffect(() => {
    const log = logRef.current;
    if (!log || !open) return;
    if (!reducedMotion && typeof log.scrollTo === "function") {
      log.scrollTo({ top: log.scrollHeight, behavior: "smooth" });
    } else {
      log.scrollTop = log.scrollHeight;
    }
  }, [turns.length, status, open, reducedMotion]);

  // A phone sheet covers the page, so the page must not scroll beneath it.
  useEffect(() => {
    if (!open || !isMobile) return;
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = previous;
    };
  }, [open, isMobile]);

  // Grow the box with its content (up to a cap), shrink back after sending.
  useLayoutEffect(() => {
    const input = inputRef.current;
    if (!input) return;
    input.style.height = "auto";
    input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
  }, [draft]);

  const close = () => {
    restoreFocus.current = true;
    setOpen(false);
  };

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (pending || draft.trim() === "") return;
    send(draft);
    setDraft("");
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey && !composing.current) {
      event.preventDefault();
      submit();
    }
  };

  const hasConversation = turns.length > 0 || error !== null;

  return createPortal(
    <div className="sigvi" data-open={open}>
      <button
        ref={launcherRef}
        type="button"
        className="sigvi-launcher"
        aria-label="Ask Sigvi, the AI assistant"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-controls="sigvi-panel"
        aria-hidden={open}
        inert={open}
        onClick={() => setOpen(true)}
      >
        <SigviAvatar size={30} />
        <span className="sigvi-launcher-label">Ask Sigvi</span>
      </button>

      <section
        id="sigvi-panel"
        className="sigvi-panel"
        role="dialog"
        aria-label="Sigvi, AI assistant"
        aria-modal="false"
        aria-hidden={!open}
        inert={!open}
        data-layout={isMobile ? "sheet" : "floating"}
        onKeyDown={(event) => {
          if (event.key === "Escape") close();
        }}
      >
        <header className="sigvi-header">
          <SigviAvatar size={36} />
          <div className="sigvi-header-text">
            <h2 className="sigvi-title">Sigvi</h2>
            <p className="sigvi-subtitle">AI assistant for Sigvitas</p>
          </div>
          <button
            type="button"
            className="sigvi-icon-btn"
            aria-label="Clear conversation"
            title="Clear conversation"
            disabled={!hasConversation}
            onClick={() => {
              clear();
              inputRef.current?.focus({ preventScroll: true });
            }}
          >
            <Icon name="trash" size={18} />
          </button>
          <button type="button" className="sigvi-icon-btn" aria-label="Close Sigvi" title="Close" onClick={close}>
            <Icon name="x" size={18} />
          </button>
        </header>

        <div
          ref={logRef}
          className="sigvi-log"
          role="log"
          aria-label="Conversation with Sigvi"
          aria-live="polite"
          aria-relevant="additions"
          tabIndex={0}
        >
          <div className="sigvi-row sigvi-row-assistant">
            <SigviAvatar size={26} />
            <div className="sigvi-bubble sigvi-bubble-assistant sigvi-welcome">
              <p>
                <strong>Hi, I'm Sigvi</strong> <span aria-hidden="true">👋</span>
              </p>
              <p>Your AI assistant for Sigvitas.</p>
              <p>How can I help you today?</p>
            </div>
          </div>

          {turns.length === 0 && (
            <div className="sigvi-suggestions" role="group" aria-label="Suggested questions">
              {SIGVI_SUGGESTIONS.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  className="sigvi-chip"
                  disabled={pending}
                  onClick={() => send(suggestion)}
                >
                  {suggestion}
                </button>
              ))}
            </div>
          )}

          {turns.map((turn) =>
            turn.role === "user" ? (
              <div key={turn.id} className="sigvi-row sigvi-row-user">
                <div className="sigvi-bubble sigvi-bubble-user">{turn.content}</div>
              </div>
            ) : (
              <AssistantTurn key={turn.id} turn={turn} onNavigate={() => setOpen(false)} />
            ),
          )}

          {pending && (
            <div className="sigvi-row sigvi-row-assistant" role="status">
              <SigviAvatar size={26} />
              <div className="sigvi-bubble sigvi-bubble-assistant sigvi-typing">
                <span className="sigvi-dots" aria-hidden="true">
                  <span />
                  <span />
                  <span />
                </span>
                <span>Sigvi is thinking…</span>
              </div>
            </div>
          )}

          {status === "error" && error && (
            <div className="sigvi-error" role="alert">
              <p>{error}</p>
              <button type="button" className="btn btn-ghost btn-sm" onClick={retry}>
                Retry
              </button>
            </div>
          )}
        </div>

        <form className="sigvi-composer" onSubmit={submit}>
          <div className="sigvi-composer-row">
            <textarea
              ref={inputRef}
              className="sigvi-input"
              aria-label="Message Sigvi"
              placeholder="Ask about roles, applying, or careers…"
              rows={1}
              maxLength={SIGVI_MAX_MESSAGE_CHARS}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={onKeyDown}
              onCompositionStart={() => {
                composing.current = true;
              }}
              onCompositionEnd={() => {
                composing.current = false;
              }}
            />
            <button
              type="submit"
              className="sigvi-send"
              aria-label="Send message"
              disabled={pending || draft.trim() === ""}
            >
              <Icon name="send" size={18} />
            </button>
          </div>
          <p className="sigvi-footnote">
            {draft.length >= COUNTER_FROM ? (
              <span className="sigvi-counter" aria-live="polite">
                {draft.length}/{SIGVI_MAX_MESSAGE_CHARS}
              </span>
            ) : (
              "Enter to send · Shift+Enter for a new line"
            )}
            <span>AI can make mistakes. Don't share sensitive details.</span>
          </p>
        </form>
      </section>
    </div>,
    document.body,
  );
}
