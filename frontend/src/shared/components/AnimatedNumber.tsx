import { useEffect, useRef, useState } from "react";
import { useInView } from "../hooks/useInView";
import { useReducedMotion } from "../hooks/useReducedMotion";

const defaultFormat = new Intl.NumberFormat();

/** Ease-out quartic: fast start, long soft landing — reads as a value
 * "settling", never bouncing. */
function easeOutQuart(t: number): number {
  return 1 - Math.pow(1 - t, 4);
}

/**
 * A count that settles into its value when it first scrolls into view and
 * whenever the value later changes. It always *renders the true value* when
 * it can't animate (reduced motion, no IntersectionObserver / rAF), so the
 * number a screen reader, a test or a print shows is never a mid-count frame.
 */
export function AnimatedNumber({
  value,
  duration = 900,
  format = (n) => defaultFormat.format(n),
  className,
}: {
  value: number;
  duration?: number;
  format?: (value: number) => string;
  className?: string;
}) {
  const reducedMotion = useReducedMotion();
  const canAnimate =
    !reducedMotion &&
    typeof IntersectionObserver !== "undefined" &&
    typeof requestAnimationFrame === "function";

  const { ref, inView } = useInView<HTMLSpanElement>({ threshold: 0.3 });
  const [display, setDisplay] = useState(canAnimate ? 0 : value);
  const shown = useRef(display);

  useEffect(() => {
    if (!canAnimate) {
      shown.current = value;
      return;
    }
    if (!inView || shown.current === value) return;

    const from = shown.current;
    const startedAt = performance.now();
    let frame = 0;

    const tick = (now: number) => {
      // (a frame's timestamp can precede `startedAt` by a hair: never go negative)
      const progress = Math.min(1, Math.max(0, (now - startedAt) / duration));
      const next = progress === 1 ? value : from + (value - from) * easeOutQuart(progress);
      shown.current = next;
      setDisplay(next);
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [value, inView, canAnimate, duration]);

  return (
    <span ref={ref} className={className}>
      {format(Math.round(canAnimate ? display : value))}
    </span>
  );
}
