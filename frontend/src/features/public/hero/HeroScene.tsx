import { useEffect, useMemo, useRef, useState } from "react";
import { useMediaQuery } from "../../../shared/hooks/useMediaQuery";
import { useReducedMotion } from "../../../shared/hooks/useReducedMotion";
import type { SceneController } from "./network3d";
import { NetworkPoster } from "./NetworkPoster";
import { buildNetworkLayout, type NodeKind } from "./networkLayout";
import { isWebGLAvailable } from "./webgl";

export type SceneStatus = "idle" | "loading" | "ready" | "fallback";

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

/**
 * The hero's living background: the recruitment-intelligence network.
 *
 * Progressive by construction:
 *  1. The static SVG poster renders immediately — it *is* the first paint, so
 *     the page never waits on 3D and there's no layout shift.
 *  2. If the user wants motion and WebGL exists, Three.js (a separate chunk)
 *     is fetched after first paint, when the browser is idle.
 *  3. The WebGL canvas fades in over the poster once its first frame is ready.
 *  4. Anything going wrong — no WebGL, chunk fails to load, GPU context lost,
 *     reduced motion — leaves the poster in place. It is a complete fallback,
 *     not an error state.
 *
 * The render loop runs only while the hero is on screen and the tab is
 * visible; everything is disposed on unmount.
 */
export function HeroScene({ highlight }: { highlight: NodeKind | null }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const controllerRef = useRef<SceneController | null>(null);
  const reducedMotion = useReducedMotion();
  const compact = useMediaQuery("(max-width: 900px)");
  // Must match the landing.css breakpoint at which the hero stacks.
  const stacked = useMediaQuery("(max-width: 1100px)");
  const [status, setStatus] = useState<SceneStatus>("idle");
  const layout = useMemo(() => buildNetworkLayout({ density: compact ? "reduced" : "full" }), [compact]);

  const wants3d = !reducedMotion && isWebGLAvailable();
  // Where 3D isn't wanted or possible the poster is simply the final state.
  const shownStatus: SceneStatus = wants3d ? status : "fallback";

  useEffect(() => {
    if (!wants3d) return;
    const container = containerRef.current;
    const canvas = canvasRef.current;
    if (!container || !canvas) return;

    let cancelled = false;
    const teardown: (() => void)[] = [];

    async function start(host: HTMLDivElement, surface: HTMLCanvasElement) {
      try {
        setStatus("loading");
        const { createNetworkScene } = await import("./network3d");
        if (cancelled) return;

        const controller = createNetworkScene({
          canvas: surface,
          layout,
          compact,
          centered: stacked,
          onContextLost: () => {
            controllerRef.current?.dispose();
            controllerRef.current = null;
            setStatus("fallback");
          },
        });
        controllerRef.current = controller;
        teardown.push(() => {
          controller.dispose();
          controllerRef.current = null;
        });

        // size
        const resizeObserver = new ResizeObserver(([entry]) => {
          controller.resize(entry.contentRect.width, entry.contentRect.height);
        });
        resizeObserver.observe(host);
        teardown.push(() => resizeObserver.disconnect());
        const box = host.getBoundingClientRect();
        controller.resize(box.width, box.height);

        // run only while on screen AND the tab is visible
        let onScreen = true;
        const updateVisibility = () => controller.setVisible(onScreen && !document.hidden);
        const intersection = new IntersectionObserver(([entry]) => {
          onScreen = entry.isIntersecting;
          updateVisibility();
        });
        intersection.observe(host);
        document.addEventListener("visibilitychange", updateVisibility);
        teardown.push(() => {
          intersection.disconnect();
          document.removeEventListener("visibilitychange", updateVisibility);
        });
        updateVisibility();

        // pointer parallax + proximity (mouse/pen only — touch has no hover)
        const onPointerMove = (event: PointerEvent) => {
          if (event.pointerType === "touch") return;
          const rect = host.getBoundingClientRect();
          const x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
          const y = -(((event.clientY - rect.top) / rect.height) * 2 - 1);
          controller.setPointer(x, y, Math.abs(x) <= 1 && Math.abs(y) <= 1);
        };
        const onPointerLeave = () => controller.setPointer(0, 0, false);
        window.addEventListener("pointermove", onPointerMove, { passive: true });
        document.addEventListener("pointerleave", onPointerLeave);
        teardown.push(() => {
          window.removeEventListener("pointermove", onPointerMove);
          document.removeEventListener("pointerleave", onPointerLeave);
        });

        // scroll: the scene drifts back and fades as the hero scrolls away
        const onScroll = () => controller.setScroll(clamp01(window.scrollY / Math.max(1, host.offsetHeight)));
        window.addEventListener("scroll", onScroll, { passive: true });
        teardown.push(() => window.removeEventListener("scroll", onScroll));
        onScroll();

        // theme: re-read the palette when light/dark changes (explicit or OS)
        const onTheme = () => controller.setTheme();
        const themeObserver = new MutationObserver(onTheme);
        themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
        const scheme = window.matchMedia?.("(prefers-color-scheme: dark)");
        scheme?.addEventListener("change", onTheme);
        teardown.push(() => {
          themeObserver.disconnect();
          scheme?.removeEventListener("change", onTheme);
        });

        setStatus("ready");
      } catch {
        // chunk failed to load / GPU refused: the poster simply stays.
        if (!cancelled) setStatus("fallback");
      }
    }

    // Defer past first paint so 3D never competes with the page's own render.
    const schedule =
      "requestIdleCallback" in window
        ? (callback: () => void) => {
            const handle = window.requestIdleCallback(callback, { timeout: 1500 });
            return () => window.cancelIdleCallback(handle);
          }
        : (callback: () => void) => {
            const handle = window.setTimeout(callback, 250);
            return () => window.clearTimeout(handle);
          };
    const cancelSchedule = schedule(() => void start(container, canvas));

    return () => {
      cancelled = true;
      cancelSchedule();
      teardown.forEach((fn) => fn());
    };
  }, [wants3d, layout, compact, stacked]);

  // legend hover/focus -> emphasise a category in the live scene
  useEffect(() => {
    controllerRef.current?.setHighlight(highlight);
  }, [highlight, status]);

  return (
    <div ref={containerRef} className="hero-scene" data-scene-status={shownStatus} aria-hidden="true">
      <div className="hero-scene-poster">
        <NetworkPoster density={compact ? "reduced" : "full"} highlight={highlight} />
      </div>
      <canvas ref={canvasRef} className="hero-scene-canvas" />
    </div>
  );
}
