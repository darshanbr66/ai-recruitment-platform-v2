import {
  AdditiveBlending,
  BoxGeometry,
  BufferAttribute,
  BufferGeometry,
  CanvasTexture,
  Color,
  DirectionalLight,
  DodecahedronGeometry,
  DynamicDrawUsage,
  EdgesGeometry,
  Fog,
  Group,
  HemisphereLight,
  IcosahedronGeometry,
  InstancedMesh,
  LineBasicMaterial,
  LineLoop,
  LineSegments,
  Matrix4,
  Mesh,
  MeshStandardMaterial,
  NormalBlending,
  OctahedronGeometry,
  PerspectiveCamera,
  Points,
  PointsMaterial,
  Quaternion,
  Scene,
  Sprite,
  SpriteMaterial,
  SRGBColorSpace,
  TetrahedronGeometry,
  Vector3,
  WebGLRenderer,
} from "three";
import type { NetworkLayout, NodeKind } from "./networkLayout";

/**
 * The recruitment-intelligence scene (Three.js, used directly — no React
 * renderer on top). Everything that moves is a transform on a few Groups;
 * the link/ring geometry is static in each orbit's local space, so nothing is
 * rebuilt per frame except the handful of live "match beams".
 *
 * Draw cost: one InstancedMesh per node category (≈8 draw calls for ~40
 * nodes), a few line objects, one Points object for the particle field.
 */

export interface SceneController {
  /** Re-read the theme palette (call when light/dark changes). */
  setTheme(): void;
  /** Pointer position in NDC (-1..1) over the scene, or `null` when it left. */
  setPointer(x: number, y: number, active: boolean): void;
  /** 0 at the top of the page → 1 once the hero has scrolled away. */
  setScroll(progress: number): void;
  /** Runs the render loop only while true (in view + tab visible). */
  setVisible(visible: boolean): void;
  /** Emphasise one category (legend hover); `null` clears it. */
  setHighlight(kind: NodeKind | null): void;
  resize(width: number, height: number): void;
  dispose(): void;
}

export interface SceneOptions {
  canvas: HTMLCanvasElement;
  layout: NetworkLayout;
  /** Phones/tablets: no per-node pointer proximity, lower pixel ratio cap. */
  compact: boolean;
  /** The hero is stacked (scene below the copy): fit and centre in the box
   * instead of sitting in the right half beside the text. */
  centered: boolean;
  onContextLost: () => void;
}

interface Palette {
  dark: boolean;
  bg: Color;
  kinds: Record<NodeKind, Color>;
  match: Color;
  particle: Color;
}

const CAMERA_Z = 11;
const CAMERA_FOV = 38;
const SCENE_DIAMETER = 8.7;

function readPalette(): Palette {
  const root = document.documentElement;
  const style = getComputedStyle(root);
  const read = (name: string, fallback: string) => new Color(style.getPropertyValue(name).trim() || fallback);
  const themeAttribute = root.getAttribute("data-theme");
  const dark = themeAttribute
    ? themeAttribute === "dark"
    : (window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false);

  return {
    dark,
    bg: read("--stage-bg", dark ? "#070a11" : "#eef2fa"),
    kinds: {
      candidate: read("--kind-candidate", "#2456e6"),
      job: read("--kind-job", "#0e8fb3"),
      skill: read("--kind-skill", "#64748b"),
      assessment: read("--kind-assessment", "#0f9d76"),
      organization: read("--kind-organization", "#1e293b"),
      ai: read("--kind-ai", "#3d6bf5"),
    },
    match: read("--kind-match", "#e08a00"),
    particle: read("--kind-particle", "#8a97ad"),
  };
}

function geometryFor(kind: NodeKind): BufferGeometry {
  switch (kind) {
    case "candidate":
      return new IcosahedronGeometry(1, 0);
    case "job":
      return new OctahedronGeometry(1, 0);
    case "skill":
      return new TetrahedronGeometry(1, 0);
    case "assessment":
      return new BoxGeometry(1.5, 1.5, 1.5);
    case "organization":
      return new DodecahedronGeometry(1, 0);
    case "ai":
      return new IcosahedronGeometry(1, 1);
  }
}

function makeDotTexture(): CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const context = canvas.getContext("2d");
  if (context) {
    const gradient = context.createRadialGradient(32, 32, 0, 32, 32, 32);
    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(0.35, "rgba(255,255,255,0.55)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    context.fillStyle = gradient;
    context.fillRect(0, 0, 64, 64);
  }
  const texture = new CanvasTexture(canvas);
  texture.colorSpace = SRGBColorSpace;
  return texture;
}

interface Item {
  position: Vector3;
  quaternion: Quaternion;
  size: number;
  hover: number;
}

interface Cluster {
  kind: NodeKind;
  matched: boolean;
  mesh: InstancedMesh;
  material: MeshStandardMaterial;
  base: Color;
  items: Item[];
  spin: Group;
  dim: number;
}

const clamp01 = (value: number) => Math.min(1, Math.max(0, value));

export function createNetworkScene({ canvas, layout, compact, centered, onContextLost }: SceneOptions): SceneController {
  let palette = readPalette();

  const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true, powerPreference: "high-performance" });
  renderer.setClearColor(0x000000, 0);
  let pixelRatio = Math.min(window.devicePixelRatio || 1, compact ? 1.5 : 1.75);
  renderer.setPixelRatio(pixelRatio);

  const scene = new Scene();
  scene.fog = new Fog(palette.bg, 9, 20);
  const camera = new PerspectiveCamera(CAMERA_FOV, 1, 0.1, 60);
  camera.position.set(0, 0, CAMERA_Z);

  const hemisphere = new HemisphereLight(0xffffff, 0x334466, 1.5);
  const sun = new DirectionalLight(0xffffff, 2.4);
  sun.position.set(4, 5, 7);
  scene.add(hemisphere, sun);

  const root = new Group();
  scene.add(root);

  const dotTexture = makeDotTexture();
  const disposables: { dispose(): void }[] = [dotTexture];
  const blendables: { blending: number; needsUpdate: boolean }[] = [];
  const track = <T extends { dispose(): void }>(resource: T): T => {
    disposables.push(resource);
    return resource;
  };

  // ---- core -------------------------------------------------------------
  const core = new Group();
  root.add(core);
  const coreMaterial = track(
    new MeshStandardMaterial({ color: palette.kinds.ai, emissive: palette.kinds.ai, emissiveIntensity: 0.85, roughness: 0.3, metalness: 0.2, flatShading: true }),
  );
  const coreMesh = new Mesh(track(new IcosahedronGeometry(0.62, 1)), coreMaterial);
  const coreWireMaterial = track(new LineBasicMaterial({ color: palette.kinds.ai, transparent: true, opacity: 0.6 }));
  const wireShell = new IcosahedronGeometry(1.0, 1);
  const coreWire = new LineSegments(track(new EdgesGeometry(wireShell)), coreWireMaterial);
  wireShell.dispose(); // EdgesGeometry has copied what it needs
  const haloMaterial = track(
    new SpriteMaterial({ map: dotTexture, color: palette.kinds.ai, transparent: true, opacity: 0.5, depthWrite: false }),
  );
  const halo = new Sprite(haloMaterial);
  halo.scale.setScalar(4.4);
  core.add(coreMesh, coreWire, halo);
  blendables.push(haloMaterial);

  // ---- orbits, nodes, links ------------------------------------------------
  const spins: Group[] = [];
  const ringMaterials: LineBasicMaterial[] = [];
  const linkMaterials: LineBasicMaterial[] = [];
  const nodeItem: { spin: Group; position: Vector3 }[] = [];

  layout.orbits.forEach((orbit, orbitIndex) => {
    const tilt = new Group();
    tilt.rotation.set(orbit.tilt[0], orbit.tilt[1], orbit.tilt[2]);
    const spin = new Group();
    tilt.add(spin);
    root.add(tilt);
    spins.push(spin);

    if (orbit.kinds[0] !== "ai") {
      const segments = 160;
      const points = new Float32Array(segments * 3);
      for (let i = 0; i < segments; i++) {
        const a = (i / segments) * Math.PI * 2;
        points[i * 3] = Math.cos(a) * orbit.radius;
        points[i * 3 + 2] = Math.sin(a) * orbit.radius;
      }
      const ringGeometry = track(new BufferGeometry());
      ringGeometry.setAttribute("position", new BufferAttribute(points, 3));
      const ringMaterial = track(new LineBasicMaterial({ color: palette.kinds[orbit.kinds[0]], transparent: true, opacity: 0.3 }));
      ringMaterials.push(ringMaterial);
      tilt.add(new LineLoop(ringGeometry, ringMaterial));
    }

    // Static link geometry, in the spinning orbit's own space.
    const local = (index: number) => {
      const node = layout.nodes[index];
      return new Vector3(Math.cos(node.angle) * node.radius, node.height, Math.sin(node.angle) * node.radius);
    };
    const segmentPoints: number[] = [];
    for (const [from, to] of layout.links) {
      if (layout.nodes[from].orbit !== orbitIndex) continue;
      const a = local(from);
      const b = local(to);
      segmentPoints.push(a.x, a.y, a.z, b.x, b.y, b.z);
    }
    for (const index of layout.spokes) {
      if (layout.nodes[index].orbit !== orbitIndex) continue;
      const p = local(index);
      segmentPoints.push(0, 0, 0, p.x, p.y, p.z);
    }
    if (segmentPoints.length > 0) {
      const linkGeometry = track(new BufferGeometry());
      linkGeometry.setAttribute("position", new BufferAttribute(new Float32Array(segmentPoints), 3));
      const linkMaterial = track(new LineBasicMaterial({ color: palette.kinds.candidate, transparent: true, opacity: 0.2 }));
      linkMaterials.push(linkMaterial);
      spin.add(new LineSegments(linkGeometry, linkMaterial));
    }
  });

  // One InstancedMesh per (orbit, category, matched) — a matched candidate is
  // a separate amber mesh so it can carry its own emissive colour.
  const clusters: Cluster[] = [];
  const groupKeys = new Map<string, number[]>();
  layout.nodes.forEach((node, index) => {
    const key = `${node.orbit}|${node.kind}|${node.matched}`;
    groupKeys.set(key, [...(groupKeys.get(key) ?? []), index]);
  });

  const scratchQuaternion = new Quaternion();
  for (const [key, indices] of groupKeys) {
    const [orbitText, kindText, matchedText] = key.split("|");
    const kind = kindText as NodeKind;
    const matched = matchedText === "true";
    const spin = spins[Number(orbitText)];

    const base = (matched ? palette.match : palette.kinds[kind]).clone();
    const material = track(
      new MeshStandardMaterial({ color: base.clone(), emissive: base.clone(), emissiveIntensity: 0.3, roughness: 0.5, metalness: 0.1, flatShading: true }),
    );
    const mesh = new InstancedMesh(track(geometryFor(kind)), material, indices.length);
    mesh.instanceMatrix.setUsage(DynamicDrawUsage);
    const items: Item[] = indices.map((index) => {
      const node = layout.nodes[index];
      const position = new Vector3(Math.cos(node.angle) * node.radius, node.height, Math.sin(node.angle) * node.radius);
      // A stable pseudo-random facing per node.
      scratchQuaternion.setFromAxisAngle(new Vector3(Math.sin(index * 1.7), Math.cos(index * 2.3), Math.sin(index * 0.9)).normalize(), index * 0.9);
      nodeItem[index] = { spin, position };
      return { position, quaternion: scratchQuaternion.clone(), size: node.size, hover: 0 };
    });
    spin.add(mesh);
    clusters.push({ kind, matched, mesh, material, base, items, spin, dim: 0 });
  }

  const matrix = new Matrix4();
  const one = new Vector3();
  function writeMatrices(cluster: Cluster) {
    cluster.items.forEach((item, slot) => {
      one.setScalar(item.size * (1 + item.hover * 0.55));
      matrix.compose(item.position, item.quaternion, one);
      cluster.mesh.setMatrixAt(slot, matrix);
    });
    cluster.mesh.instanceMatrix.needsUpdate = true;
  }
  clusters.forEach(writeMatrices);

  // ---- particle field ------------------------------------------------------
  const particleGeometry = track(new BufferGeometry());
  particleGeometry.setAttribute("position", new BufferAttribute(layout.particles, 3));
  const particleMaterial = track(
    new PointsMaterial({ color: palette.particle, size: 0.06, map: dotTexture, transparent: true, opacity: 0.55, depthWrite: false, sizeAttenuation: true }),
  );
  const particles = new Points(particleGeometry, particleMaterial);
  root.add(particles);
  blendables.push(particleMaterial);

  // ---- live match beams ----------------------------------------------------
  const beamPositions = new Float32Array(layout.matches.length * 6);
  const beamGeometry = track(new BufferGeometry());
  beamGeometry.setAttribute("position", new BufferAttribute(beamPositions, 3));
  const beamMaterial = track(new LineBasicMaterial({ color: palette.match, transparent: true, opacity: 0.7, depthWrite: false }));
  const beams = new LineSegments(beamGeometry, beamMaterial);
  const pulsePositions = new Float32Array(layout.matches.length * 3);
  const pulseGeometry = track(new BufferGeometry());
  pulseGeometry.setAttribute("position", new BufferAttribute(pulsePositions, 3));
  const pulseMaterial = track(
    new PointsMaterial({ color: palette.match, size: 0.2, map: dotTexture, transparent: true, depthWrite: false, sizeAttenuation: true }),
  );
  const pulses = new Points(pulseGeometry, pulseMaterial);
  root.add(beams, pulses);
  blendables.push(beamMaterial, pulseMaterial);
  beams.frustumCulled = false;
  pulses.frustumCulled = false;

  // ---- theme ------------------------------------------------------------
  function applyPalette() {
    const { dark } = palette;
    (scene.fog as Fog).color.copy(palette.bg);
    hemisphere.intensity = dark ? 1.35 : 1.9;
    hemisphere.groundColor.set(dark ? 0x223355 : 0x9aa8c4);
    sun.intensity = dark ? 2.4 : 2.0;

    coreMaterial.color.copy(palette.kinds.ai);
    coreMaterial.emissive.copy(palette.kinds.ai);
    coreWireMaterial.color.copy(palette.kinds.ai);
    haloMaterial.color.copy(palette.kinds.ai);
    haloMaterial.opacity = dark ? 0.45 : 0.26;

    layout.orbits
      .filter((orbit) => orbit.kinds[0] !== "ai")
      .forEach((orbit, i) => {
        ringMaterials[i].color.copy(palette.kinds[orbit.kinds[0]]);
        ringMaterials[i].opacity = dark ? 0.2 : 0.28;
      });
    linkMaterials.forEach((material) => {
      material.color.copy(palette.kinds.candidate);
      material.opacity = dark ? 0.14 : 0.2;
    });
    clusters.forEach((cluster) => {
      cluster.base.copy(cluster.matched ? palette.match : palette.kinds[cluster.kind]);
    });
    particleMaterial.color.copy(palette.particle);
    particleMaterial.opacity = dark ? 0.55 : 0.5;
    beamMaterial.color.copy(palette.match);
    pulseMaterial.color.copy(palette.match);

    const blending = dark ? AdditiveBlending : NormalBlending;
    blendables.forEach((material) => {
      material.blending = blending;
      material.needsUpdate = true;
    });
  }
  applyPalette();

  // ---- state driven by the page ------------------------------------------
  const pointerTarget = { x: 0, y: 0 };
  const pointer = { x: 0, y: 0 };
  let pointerActive = false;
  let scrollTarget = 0;
  let scroll = 0;
  let highlight: NodeKind | null = null;
  let coreGlow = 0;
  let width = 1;
  let height = 1;
  let baseX = 0;
  let baseY = 0;
  let baseScale = 1;
  let visible = false;
  let disposed = false;
  let frameHandle = 0;
  let last = 0;
  let time = 0;
  let lastOpacity = 1;

  // frame-time governor: shed pixel ratio if the device can't hold ~40fps
  let sampleCount = 0;
  let sampleTotal = 0;

  function applyResponsive() {
    const aspect = width / height;
    camera.aspect = aspect;
    camera.updateProjectionMatrix();
    const visibleHeight = 2 * CAMERA_Z * Math.tan((CAMERA_FOV * Math.PI) / 360);
    const visibleWidth = visibleHeight * aspect;
    if (centered) {
      // Stacked hero: the scene owns its box — fit it whole and centre it.
      baseScale = Math.min(1, (Math.min(visibleWidth, visibleHeight) * 0.94) / SCENE_DIAMETER);
      baseX = 0;
      baseY = 0;
    } else if (aspect >= 1.15) {
      // Wide screens: the network sits in the right half, beside the copy.
      baseScale = Math.min(0.95, (visibleHeight * 0.72) / SCENE_DIAMETER);
      baseX = visibleWidth * 0.21;
      baseY = visibleHeight * 0.05; // a little high: the legend sits beneath
    } else {
      // Narrow screens: centred behind the copy, cropped rather than tiny.
      baseScale = Math.min(1, Math.max(0.6, (visibleWidth * 1.2) / SCENE_DIAMETER));
      baseX = 0;
      baseY = visibleHeight * 0.1;
    }
  }

  function resize(nextWidth: number, nextHeight: number) {
    width = Math.max(1, nextWidth);
    height = Math.max(1, nextHeight);
    renderer.setPixelRatio(pixelRatio);
    renderer.setSize(width, height, false);
    applyResponsive();
    if (visible) renderer.render(scene, camera);
  }

  const va = new Vector3();
  const vb = new Vector3();
  const projected = new Vector3();

  function updateBeams() {
    layout.matches.forEach(([candidate, job], k) => {
      const a = nodeItem[candidate];
      const b = nodeItem[job];
      va.copy(a.position).applyMatrix4(a.spin.matrixWorld);
      vb.copy(b.position).applyMatrix4(b.spin.matrixWorld);
      root.worldToLocal(va);
      root.worldToLocal(vb);
      const b6 = k * 6;
      beamPositions[b6] = va.x;
      beamPositions[b6 + 1] = va.y;
      beamPositions[b6 + 2] = va.z;
      beamPositions[b6 + 3] = vb.x;
      beamPositions[b6 + 4] = vb.y;
      beamPositions[b6 + 5] = vb.z;
      const t = (time * 0.32 + k * 0.21) % 1;
      const p3 = k * 3;
      pulsePositions[p3] = va.x + (vb.x - va.x) * t;
      pulsePositions[p3 + 1] = va.y + (vb.y - va.y) * t;
      pulsePositions[p3 + 2] = va.z + (vb.z - va.z) * t;
    });
    beamGeometry.attributes.position.needsUpdate = true;
    pulseGeometry.attributes.position.needsUpdate = true;
    beamMaterial.opacity = (palette.dark ? 0.4 : 0.5) + Math.sin(time * 1.6) * 0.1;
  }

  function frame(now: number) {
    if (disposed || !visible) return;
    frameHandle = requestAnimationFrame(frame);
    const dt = Math.min(0.05, (now - last) / 1000 || 0.016);
    last = now;
    time += dt;

    const ease = (rate: number) => 1 - Math.exp(-dt * rate);
    pointer.x += (pointerTarget.x - pointer.x) * ease(3.2);
    pointer.y += (pointerTarget.y - pointer.y) * ease(3.2);
    scroll += (scrollTarget - scroll) * ease(4);

    const sway = Math.sin(time * 0.21) * 0.05;
    root.rotation.y = pointer.x * 0.3 + sway + scroll * 0.75;
    root.rotation.x = 0.12 - pointer.y * 0.18 + scroll * 0.1;
    root.position.set(baseX, baseY + scroll * 1.7, -scroll * 1.5);
    root.scale.setScalar(baseScale * (1 - scroll * 0.12));
    camera.position.z = CAMERA_Z + scroll * 2.5;

    layout.orbits.forEach((orbit, i) => {
      spins[i].rotation.y += orbit.speed * dt;
    });
    coreMesh.rotation.y += dt * 0.35;
    coreMesh.rotation.x += dt * 0.12;
    coreWire.rotation.y -= dt * 0.18;
    coreWire.rotation.z += dt * 0.08;
    const pulse = 1 + Math.sin(time * 1.4) * 0.035;
    coreGlow += ((highlight === "ai" ? 1 : 0) - coreGlow) * ease(6);
    core.scale.setScalar(pulse * (1 + coreGlow * 0.12));
    coreMaterial.emissiveIntensity = 0.85 + coreGlow * 0.9;
    particles.rotation.y += dt * 0.012;

    root.updateMatrixWorld(true);
    updateBeams();

    // pointer proximity: nodes near the cursor swell slightly
    const proximityRadius = 0.2;
    camera.updateMatrixWorld();
    const hovering = pointerActive && !compact;
    for (const cluster of clusters) {
      let dirty = false;
      cluster.items.forEach((item) => {
        let target = 0;
        if (hovering) {
          projected.copy(item.position).applyMatrix4(cluster.spin.matrixWorld).project(camera);
          const distance = Math.hypot(projected.x - pointerTarget.x, projected.y - pointerTarget.y);
          target = distance < proximityRadius ? 1 - distance / proximityRadius : 0;
        }
        const next = item.hover + (target - item.hover) * ease(9);
        if (Math.abs(next - item.hover) > 0.0008 || (next > 0.001 && next !== item.hover)) dirty = true;
        item.hover = next < 0.001 ? 0 : next;
      });
      if (dirty) writeMatrices(cluster);

      // category emphasis (legend hover)
      const dimTarget = highlight !== null && highlight !== cluster.kind ? 0.78 : 0;
      cluster.dim += (dimTarget - cluster.dim) * ease(7);
      cluster.material.color.copy(cluster.base).lerp(palette.bg, cluster.dim);
      cluster.material.emissive.copy(cluster.material.color);
      cluster.material.emissiveIntensity = highlight === cluster.kind ? 0.95 : 0.3 - cluster.dim * 0.2;
    }

    const opacity = clamp01(1 - scroll * 0.9);
    if (Math.abs(opacity - lastOpacity) > 0.01) {
      canvas.style.opacity = String(opacity);
      lastOpacity = opacity;
    }

    renderer.render(scene, camera);

    sampleTotal += dt * 1000;
    if (++sampleCount === 150) {
      if (sampleTotal / sampleCount > 26 && pixelRatio > 1) {
        pixelRatio = Math.max(1, pixelRatio - 0.5);
        renderer.setPixelRatio(pixelRatio);
        renderer.setSize(width, height, false);
      }
      sampleCount = 0;
      sampleTotal = 0;
    }
  }

  function handleContextLost(event: Event) {
    event.preventDefault();
    onContextLost();
  }
  canvas.addEventListener("webglcontextlost", handleContextLost);

  return {
    setTheme() {
      palette = readPalette();
      applyPalette();
    },
    setPointer(x, y, active) {
      pointerTarget.x = x;
      pointerTarget.y = y;
      pointerActive = active;
      if (!active) {
        pointerTarget.x = 0;
        pointerTarget.y = 0;
      }
    },
    setScroll(progress) {
      scrollTarget = clamp01(progress);
    },
    setVisible(next) {
      if (disposed || next === visible) return;
      visible = next;
      cancelAnimationFrame(frameHandle);
      if (visible) {
        last = performance.now();
        frameHandle = requestAnimationFrame(frame);
      }
    },
    setHighlight(kind) {
      highlight = kind;
    },
    resize,
    dispose() {
      if (disposed) return;
      disposed = true;
      visible = false;
      cancelAnimationFrame(frameHandle);
      canvas.removeEventListener("webglcontextlost", handleContextLost);
      clusters.forEach((cluster) => cluster.mesh.dispose());
      disposables.forEach((resource) => resource.dispose());
      renderer.dispose();
      renderer.forceContextLoss();
    },
  };
}
