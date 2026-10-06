import type { ProjectEngine } from "../engine/project";
import type { Clip, KeyframeProp } from "../engine/types";
import { propPoints, samplePoints } from "../engine/keyframes";

// The stage as the device camera: with a device clip selected, a drag orbits (turn, tilt), space-drag pans, the wheel
// sets the distance. Listened for in the capture phase so the selection's move gesture does not also move the layer;
// the resize handles are left alone. One history entry per gesture (later updates are quiet). A value with keyframes
// is keyed at the playhead when the gesture ends.

const DEFAULTS: Record<string, number> = { yaw: 25, pitch: 12, distance: 1, panX: 0, panY: 0 };

export function installDeviceStage(engine: ProjectEngine): void {
  let space = false;
  const typing = (target: EventTarget | null) =>
    target instanceof HTMLElement && (target.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName));
  window.addEventListener("keydown", (event) => { if (event.code === "Space" && !typing(event.target)) space = true; });
  window.addEventListener("keyup", (event) => { if (event.code === "Space") space = false; });

  const host = () => document.querySelector<HTMLCanvasElement>(".render-canvas")?.parentElement ?? null;
  const selected = (): Clip | null => {
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id) : null;
    return found && found.clip.kind === "device" && found.clip.device ? found.clip : null;
  };
  const local = (clip: Clip) => Math.max(0, Math.min(clip.duration, engine.snapshot.playhead - clip.start));
  const keyed = (clip: Clip, name: string) => propPoints(clip, `device.${name}` as KeyframeProp);
  const current = (clip: Clip, name: string) =>
    samplePoints(keyed(clip, name), local(clip)) ?? (clip.device!.camera as Record<string, number> | undefined)?.[name] ?? DEFAULTS[name];

  /** Writes camera values: live into the clip (quiet after the first), keyed values once at the end. */
  const writer = (clip: Clip) => {
    let first = true;
    const pending: Record<string, number> = {};
    return {
      live(values: Record<string, number>) {
        const plain: Record<string, number> = {};
        for (const [name, v] of Object.entries(values)) {
          if (keyed(clip, name).length) pending[name] = v;
          else plain[name] = v;
        }
        if (Object.keys(plain).length) {
          engine.dispatch("clip.device", { clipId: clip.id, patch: { camera: plain }, quiet: !first });
          first = false;
        }
      },
      done() {
        if (!Object.keys(pending).length) return;
        const props = Object.fromEntries(Object.entries(pending).map(([name, v]) => [`device.${name}`, v]));
        engine.dispatch("clip.keyframes.set", { clipId: clip.id, keyframes: [{ t: local(clip), props }] });
      },
    };
  };

  document.addEventListener(
    "pointerdown",
    (event) => {
      const stage = host();
      const clip = selected();
      if (!stage || !clip || event.button !== 0 || !stage.contains(event.target as Node)) return;
      if (stage.dataset.boxCutout === "on") return;
      if ((event.target as HTMLElement).closest(".focus-overlay, .focus-panel")) return;
      const handle = (event.target as HTMLElement).closest<HTMLElement>("[data-handle]")?.dataset.handle;
      if (handle && handle !== "move") return;
      event.preventDefault();
      event.stopPropagation();
      const frame = stage.getBoundingClientRect();
      const panning = space;
      const start = { x: event.clientX, y: event.clientY };
      const from = Object.fromEntries(["yaw", "pitch", "panX", "panY"].map((n) => [n, current(clip, n)]));
      const out = writer(clip);
      let frameQueued = false;
      let latest = start;
      const apply = () => {
        frameQueued = false;
        const dx = latest.x - start.x;
        const dy = latest.y - start.y;
        if (panning) {
          out.live({ panX: from.panX + (dx / frame.height) * 2, panY: from.panY - (dy / frame.height) * 2 });
        } else {
          out.live({ yaw: from.yaw + dx * 0.4, pitch: Math.max(-60, Math.min(85, from.pitch - dy * 0.3)) });
        }
      };
      const move = (moved: PointerEvent) => {
        latest = { x: moved.clientX, y: moved.clientY };
        if (!frameQueued) {
          frameQueued = true;
          requestAnimationFrame(apply);
        }
      };
      const up = () => {
        window.removeEventListener("pointermove", move);
        window.removeEventListener("pointerup", up);
        apply();
        out.done();
      };
      window.addEventListener("pointermove", move);
      window.addEventListener("pointerup", up);
    },
    true,
  );

  let wheelGesture: { clip: string; out: ReturnType<typeof writer>; timer: number } | null = null;
  document.addEventListener(
    "wheel",
    (event) => {
      const stage = host();
      const clip = selected();
      if (!stage || !clip || !stage.contains(event.target as Node)) return;
      event.preventDefault();
      event.stopPropagation();
      if (!wheelGesture || wheelGesture.clip !== clip.id) wheelGesture = { clip: clip.id, out: writer(clip), timer: 0 };
      const next = Math.max(0.1, Math.min(3, current(clip, "distance") * Math.exp(event.deltaY * 0.001)));
      wheelGesture.out.live({ distance: Math.round(next * 1000) / 1000 });
      window.clearTimeout(wheelGesture.timer);
      const gesture = wheelGesture;
      gesture.timer = window.setTimeout(() => { gesture.out.done(); if (wheelGesture === gesture) wheelGesture = null; }, 400);
    },
    { capture: true, passive: false },
  );
}
