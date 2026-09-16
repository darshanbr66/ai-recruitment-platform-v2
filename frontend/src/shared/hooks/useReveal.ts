import { useEffect, useRef, useState } from "react";

/** Adds an `is-visible` class the first time the element scrolls into view —
 * used for the landing page's fade-in/slide-up section entrances. Starts
 * `true` (no animation) if IntersectionObserver isn't available, so content
 * is never hidden by a missing browser feature. */
export function useReveal<T extends HTMLElement>() {
  const ref = useRef<T | null>(null);
  const [isVisible, setIsVisible] = useState(typeof IntersectionObserver === "undefined");

  useEffect(() => {
    const node = ref.current;
    if (!node || typeof IntersectionObserver === "undefined") return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.15 },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, []);

  return { ref, isVisible };
}
