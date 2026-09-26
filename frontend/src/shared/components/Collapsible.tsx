import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";

/** Below this width the panel sits full-width under the main column, where
 * a tall block costs the whole screen — so it collapses harder. */
const NARROW = "(max-width: 768px)";
const NARROW_MAX_HEIGHT = 220;

function useCollapsedHeight(requested: number): number {
  // Start from the requested height: SSR/JSDOM have no matchMedia, and a
  // first paint that is too tall is corrected on the effect below.
  const [narrow, setNarrow] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return;
    const query = window.matchMedia(NARROW);
    const sync = () => setNarrow(query.matches);
    sync();
    query.addEventListener("change", sync);
    return () => query.removeEventListener("change", sync);
  }, []);

  return narrow ? Math.min(requested, NARROW_MAX_HEIGHT) : requested;
}

/**
 * Caps tall content behind a "Show more" toggle, and gets out of the way
 * entirely when the content already fits — short panels render exactly as
 * they did before, with no control at all.
 *
 * Nothing is ever removed from the DOM: the overflow is clipped, not
 * unmounted, so the full text stays available to find-in-page and to
 * assistive technology, and the toggle is a real <button> carrying
 * `aria-expanded`/`aria-controls`.
 *
 * Whether the control is needed is *measured* against the height actually
 * applied, rather than guessed from a character count, so it stays correct
 * at any viewport width — the same profile field wraps to three lines on a
 * phone and one on a desktop. That single measurement is also why the cap
 * is chosen here rather than in a CSS media query: a cap the measurement
 * did not know about could clip content and offer no way to reveal it.
 */
export function Collapsible({
  children,
  collapsedHeight = 320,
  showMoreLabel = "Show more",
  showLessLabel = "Show less",
  label,
}: {
  children: ReactNode;
  /** Height, in px, the collapsed state is capped at on a wide screen. */
  collapsedHeight?: number;
  showMoreLabel?: string;
  showLessLabel?: string;
  /** Names the region for screen readers, e.g. "Profile details". */
  label?: string;
}) {
  const contentId = useId();
  const contentRef = useRef<HTMLDivElement>(null);
  const [expanded, setExpanded] = useState(false);
  const [overflowing, setOverflowing] = useState(false);
  const effectiveHeight = useCollapsedHeight(collapsedHeight);

  const measure = useCallback(() => {
    const node = contentRef.current;
    if (!node) return;
    // scrollHeight is the *full* height even while clipped, so this stays
    // accurate in both states and never flip-flops once expanded.
    setOverflowing(node.scrollHeight > effectiveHeight + 1);
  }, [effectiveHeight]);

  useEffect(() => {
    const node = contentRef.current;
    if (!node) return;
    measure();
    // Content can change height after mount (a query resolving, an image
    // loading, the window resizing) — re-measure instead of trusting the
    // first paint. ResizeObserver is unavailable in some test/JSDOM
    // environments, where the one-off measure above is enough.
    if (typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(measure);
    observer.observe(node);
    return () => observer.disconnect();
  }, [measure, children]);

  const clipped = overflowing && !expanded;

  return (
    <div className="collapsible">
      <div
        id={contentId}
        ref={contentRef}
        className={`collapsible-content${clipped ? " is-clipped" : ""}`}
        style={{ "--collapsed-height": `${effectiveHeight}px` } as CSSProperties}
        aria-label={label}
      >
        {children}
      </div>
      {overflowing && (
        <button
          type="button"
          className="link-button collapsible-toggle"
          aria-expanded={expanded}
          aria-controls={contentId}
          onClick={() => setExpanded((value) => !value)}
        >
          {expanded ? showLessLabel : showMoreLabel}
        </button>
      )}
    </div>
  );
}
