import { useEffect, useRef, type ReactNode } from "react";
import { useReducedMotion } from "../hooks/useReducedMotion";

/**
 * A gentle pull toward the pointer for a primary call to action: the wrapped
 * control drifts a few pixels toward the cursor while it is near, and eases
 * back when it leaves. It only moves a wrapper, never the control itself, so
 * focus, clicks and semantics are untouched. Off for touch/coarse pointers
 * and for reduced motion.
 */
export function Magnetic({
  children,
  strength = 0.22,
  radius = 90,
}: {
  children: ReactNode;
  /** Fraction of the pointer offset the control follows (0–1). */
  strength?: number;
  /** Extra distance around the control, in px, that still attracts it. */
  radius?: number;
}) {
  const ref = useRef<HTMLSpanElement>(null);
  const reducedMotion = useReducedMotion();

  useEffect(() => {
    const node = ref.current;
    if (!node || reducedMotion) return;
    if (typeof window.matchMedia !== "function" || !window.matchMedia("(hover: hover) and (pointer: fine)").matches) {
      return;
    }

    function onMove(event: PointerEvent) {
      const box = node!.getBoundingClientRect();
      const dx = event.clientX - (box.left + box.width / 2);
      const dy = event.clientY - (box.top + box.height / 2);
      const near =
        Math.abs(dx) < box.width / 2 + radius && Math.abs(dy) < box.height / 2 + radius;
      node!.style.transform = near
        ? `translate3d(${(dx * strength).toFixed(1)}px, ${(dy * strength).toFixed(1)}px, 0)`
        : "";
    }
    function reset() {
      node!.style.transform = "";
    }

    window.addEventListener("pointermove", onMove, { passive: true });
    document.addEventListener("pointerleave", reset);
    return () => {
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerleave", reset);
      reset();
    };
  }, [reducedMotion, strength, radius]);

  return (
    <span ref={ref} className="magnetic">
      {children}
    </span>
  );
}
