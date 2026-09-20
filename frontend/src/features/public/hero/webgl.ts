let cached: boolean | undefined;

/**
 * Whether this browser can create a WebGL context at all. Cheap, and cached:
 * the probe context is discarded immediately. Where the WebGL globals don't
 * exist (jsdom, very old browsers) it answers `false` without touching the
 * canvas API, so tests and legacy browsers go straight to the static poster.
 */
export function isWebGLAvailable(): boolean {
  if (cached !== undefined) return cached;
  if (
    typeof document === "undefined" ||
    (typeof WebGL2RenderingContext === "undefined" && typeof WebGLRenderingContext === "undefined")
  ) {
    return (cached = false);
  }
  try {
    const probe = document.createElement("canvas");
    const gl = probe.getContext("webgl2") ?? probe.getContext("webgl");
    cached = gl !== null;
    (gl as WebGLRenderingContext | null)?.getExtension("WEBGL_lose_context")?.loseContext();
  } catch {
    cached = false;
  }
  return cached;
}

/** Test seam: forget the cached probe result. */
export function resetWebGLProbe(): void {
  cached = undefined;
}
