/**
 * Small deterministic PRNG (mulberry32). The decorative network artwork —
 * the SVG backdrop and the 3D scene's layout — is generated from a fixed seed,
 * so it is identical on every load and every render (no layout jitter between
 * SSR-style passes, stable snapshots in tests) instead of depending on
 * `Math.random()`.
 */
export function createRandom(seed: number): () => number {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
