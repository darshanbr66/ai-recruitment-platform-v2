import { render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { SceneController } from "./network3d";

// The WebGL probe and the Three.js scene are mocked: these tests are about the
// *lifecycle around* the 3D scene (when it loads, when it runs, when it is
// torn down, when it is skipped), which needs no GPU.
const webgl = vi.hoisted(() => ({ available: true }));
vi.mock("./webgl", () => ({ isWebGLAvailable: () => webgl.available }));

const scene = vi.hoisted(() => ({ create: vi.fn(), fail: false }));
vi.mock("./network3d", () => ({
  createNetworkScene: (options: unknown) => {
    if (scene.fail) throw new Error("no GPU");
    return scene.create(options);
  },
}));

import { HeroScene } from "./HeroScene";

function fakeController(): SceneController {
  return {
    setTheme: vi.fn(),
    setPointer: vi.fn(),
    setScroll: vi.fn(),
    setVisible: vi.fn(),
    setHighlight: vi.fn(),
    resize: vi.fn(),
    dispose: vi.fn(),
  };
}

let reducedMotion = false;

beforeEach(() => {
  webgl.available = true;
  scene.fail = false;
  reducedMotion = false;
  scene.create.mockReset();
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("prefers-reduced-motion") ? reducedMotion : false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  vi.stubGlobal("ResizeObserver", class { observe() {} disconnect() {} unobserve() {} });
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      private callback: (entries: { isIntersecting: boolean }[]) => void;
      constructor(callback: (entries: { isIntersecting: boolean }[]) => void) {
        this.callback = callback;
      }
      observe() {
        this.callback([{ isIntersecting: true }]);
      }
      disconnect() {}
    },
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("HeroScene", () => {
  it("shows the poster first, then loads the 3D scene and hands it to the page's controls", async () => {
    const controller = fakeController();
    scene.create.mockReturnValue(controller);

    const { container } = render(<HeroScene highlight={null} />);
    const root = container.querySelector(".hero-scene");
    // First paint: poster present, nothing waiting on WebGL.
    expect(container.querySelector(".network-poster")).toBeInTheDocument();
    expect(root).not.toHaveAttribute("data-scene-status", "ready");

    await waitFor(() => expect(root).toHaveAttribute("data-scene-status", "ready"), { timeout: 3000 });
    expect(scene.create).toHaveBeenCalledTimes(1);
    // (identity, not deep equality: deep-comparing a DOM node walks React's circular fiber links)
    expect(scene.create.mock.calls[0][0].canvas).toBe(container.querySelector("canvas"));
    // it runs while the hero is in view, and gets sized
    expect(controller.setVisible).toHaveBeenCalledWith(true);
    expect(controller.resize).toHaveBeenCalled();
  });

  it("forwards legend highlights to the live scene", async () => {
    const controller = fakeController();
    scene.create.mockReturnValue(controller);

    const { container, rerender } = render(<HeroScene highlight={null} />);
    await waitFor(() => expect(container.querySelector(".hero-scene")).toHaveAttribute("data-scene-status", "ready"), { timeout: 3000 });

    rerender(<HeroScene highlight="job" />);
    expect(controller.setHighlight).toHaveBeenLastCalledWith("job");
    rerender(<HeroScene highlight={null} />);
    expect(controller.setHighlight).toHaveBeenLastCalledWith(null);
  });

  it("disposes the scene and stops listening when it unmounts", async () => {
    const controller = fakeController();
    scene.create.mockReturnValue(controller);
    const removeWindowListener = vi.spyOn(window, "removeEventListener");

    const { container, unmount } = render(<HeroScene highlight={null} />);
    await waitFor(() => expect(container.querySelector(".hero-scene")).toHaveAttribute("data-scene-status", "ready"), { timeout: 3000 });

    unmount();
    expect(controller.dispose).toHaveBeenCalledTimes(1);
    const removed = removeWindowListener.mock.calls.map(([type]) => type);
    expect(removed).toEqual(expect.arrayContaining(["pointermove", "scroll"]));
  });

  it("never loads 3D when the user prefers reduced motion — the poster is the experience", async () => {
    reducedMotion = true;

    const { container } = render(<HeroScene highlight={null} />);
    expect(container.querySelector(".hero-scene")).toHaveAttribute("data-scene-status", "fallback");
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(scene.create).not.toHaveBeenCalled();
    expect(container.querySelector(".network-poster")).toBeInTheDocument();
  });

  it("never loads 3D on a device without WebGL", async () => {
    webgl.available = false;

    const { container } = render(<HeroScene highlight={null} />);
    expect(container.querySelector(".hero-scene")).toHaveAttribute("data-scene-status", "fallback");
    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(scene.create).not.toHaveBeenCalled();
  });

  it("falls back to the poster if the GPU refuses the scene", async () => {
    scene.fail = true;

    const { container } = render(<HeroScene highlight={null} />);
    await waitFor(
      () => expect(container.querySelector(".hero-scene")).toHaveAttribute("data-scene-status", "fallback"),
      { timeout: 3000 },
    );
    expect(container.querySelector(".network-poster")).toBeInTheDocument();
  });

  it("falls back to the poster when the GPU context is lost mid-session", async () => {
    const controller = fakeController();
    scene.create.mockReturnValue(controller);

    const { container } = render(<HeroScene highlight={null} />);
    const root = container.querySelector(".hero-scene");
    await waitFor(() => expect(root).toHaveAttribute("data-scene-status", "ready"), { timeout: 3000 });

    // the scene reports the loss through the callback it was created with
    scene.create.mock.calls[0][0].onContextLost();
    await waitFor(() => expect(root).toHaveAttribute("data-scene-status", "fallback"));
    expect(controller.dispose).toHaveBeenCalled();
  });
});
