import { useEffect, useRef, useState } from "react";

interface InViewOptions {
  /** Fraction of the element that must be visible. */
  threshold?: number;
  /** Grow/shrink the viewport used for the test, e.g. "0px 0px -10% 0px". */
  rootMargin?: string;
  /** Latch to `true` the first time it enters view (default), or track live. */
  once?: boolean;
}

/**
 * Whether an element is in the viewport. Starts `true` when
 * IntersectionObserver isn't available so content is never hidden by a
 * missing browser feature — entrance animations then simply don't run.
 */
export function useInView<T extends Element>({
  threshold = 0.15,
  rootMargin = "0px",
  once = true,
}: InViewOptions = {}) {
  const ref = useRef<T | null>(null);
  const [inView, setInView] = useState(typeof IntersectionObserver === "undefined");

  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          if (once) observer.disconnect();
        } else if (!once) {
          setInView(false);
        }
      },
      { threshold, rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [threshold, rootMargin, once]);

  return { ref, inView };
}
