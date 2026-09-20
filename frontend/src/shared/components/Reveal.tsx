import type { CSSProperties, ReactNode } from "react";
import { useInView } from "../hooks/useInView";

type RevealTag = "div" | "section" | "article" | "li" | "p" | "h2" | "span";

/**
 * Scroll-reveal: content eases in (fade + a short rise) the first time it
 * scrolls into view. Movement carries direction — content arrives from where
 * it "belongs" — and `delay` staggers siblings so a group reads in order.
 * Reduced motion: the styles for `.reveal` collapse to a plain fade with no
 * travel (see styles/motion.css), and browsers without IntersectionObserver
 * show everything immediately (useInView starts `true`).
 */
export function Reveal({
  as = "div",
  children,
  className = "",
  delay = 0,
  direction = "up",
}: {
  as?: RevealTag;
  children: ReactNode;
  className?: string;
  /** Milliseconds; use multiples of ~60 for a natural stagger. */
  delay?: number;
  direction?: "up" | "left" | "right" | "none";
}) {
  const { ref, inView } = useInView<HTMLElement>();
  const Tag = as;
  const classes = `reveal reveal-${direction}${inView ? " is-visible" : ""}${className ? ` ${className}` : ""}`;
  const style = delay > 0 ? ({ "--reveal-delay": `${delay}ms` } as CSSProperties) : undefined;

  return (
    <Tag ref={ref as never} className={classes} style={style}>
      {children}
    </Tag>
  );
}
