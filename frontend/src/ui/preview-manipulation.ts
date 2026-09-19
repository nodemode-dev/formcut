import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { sampledTransform } from "../engine/keyframes";

export function previewManipulation(stage: HTMLElement, engine: ProjectEngine, bin: MediaBin): void {
  const overlay = document.createElement("div"); overlay.className = "preview-selection"; overlay.hidden = true;
  const move = document.createElement("button"); move.className = "preview-move"; move.dataset.handle = "move"; move.setAttribute("aria-label", "Move selected clip"); overlay.append(move);
  for (const direction of ["nw", "n", "ne", "e", "se", "s", "sw", "w", "rotate"]) {
    const handle = document.createElement("button"); handle.className = `preview-handle handle-${direction}`; handle.dataset.handle = direction; handle.setAttribute("aria-label", direction === "rotate" ? "Rotate selected clip" : `Resize selected clip ${direction}`); overlay.append(handle);
  }
  stage.append(overlay);
  const cropOverlay = document.createElement("div");
  cropOverlay.className = "preview-crop";
  cropOverlay.hidden = true;
  cropOverlay.innerHTML = `<div class="crop-window" data-ref="window"></div>` +
    ["left", "top", "right", "bottom"].map((edge) => `<button class="crop-grip grip-${edge}" data-edge="${edge}" aria-label="Crop ${edge}"></button>`).join("");
  stage.append(cropOverlay);
  const cropBox = (clip: import("../engine/types").Clip) => ({
    left: Math.min(0.45, Math.max(0, clip.crop?.left ?? 0)),
    top: Math.min(0.45, Math.max(0, clip.crop?.top ?? 0)),
    right: Math.min(0.45, Math.max(0, clip.crop?.right ?? 0)),
    bottom: Math.min(0.45, Math.max(0, clip.crop?.bottom ?? 0)),
  });
  const drawCrop = () => {
    const state = engine.snapshot;
    const found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    const clip = found?.clip;
    const on = stage.dataset.crop === "on" && clip && (clip.kind === "video" || clip.kind === "image") && clip.start <= state.playhead && state.playhead <= clip.start + clip.duration;
    cropOverlay.hidden = !on;
    if (!on || !clip) return;
    const media = clip.mediaId ? bin.find(clip.mediaId) : null;
    const w = media?.width || state.width, h = media?.height || state.height;
    const box = cropBox(clip);
    const cw = w * (1 - box.left - box.right), ch = h * (1 - box.top - box.bottom);
    const fit = Math.min(state.width / cw, state.height / ch);
    const tr = sampledTransform(clip, state.playhead - clip.start);
    const scale = fit * tr.scale / 100;
    const fullW = w * scale * tr.width / 100 / state.width * 100;
    const fullH = h * scale * tr.height / 100 / state.height * 100;
    const centerX = 50 + tr.posX - ((box.left - box.right) / 2) * fullW;
    const centerY = 50 + tr.posY - ((box.top - box.bottom) / 2) * fullH;
    cropOverlay.style.width = `${fullW}%`;
    cropOverlay.style.height = `${fullH}%`;
    cropOverlay.style.left = `${centerX}%`;
    cropOverlay.style.top = `${centerY}%`;
    const window_ = cropOverlay.querySelector<HTMLElement>('[data-ref="window"]')!;
    window_.style.left = `${box.left * 100}%`;
    window_.style.top = `${box.top * 100}%`;
    window_.style.right = `${box.right * 100}%`;
    window_.style.bottom = `${box.bottom * 100}%`;
    for (const grip of cropOverlay.querySelectorAll<HTMLElement>(".crop-grip")) {
      const edge = grip.dataset.edge!;
      if (edge === "left") { grip.style.left = `${box.left * 100}%`; grip.style.top = "50%"; }
      if (edge === "right") { grip.style.left = `${(1 - box.right) * 100}%`; grip.style.top = "50%"; }
      if (edge === "top") { grip.style.top = `${box.top * 100}%`; grip.style.left = "50%"; }
      if (edge === "bottom") { grip.style.top = `${(1 - box.bottom) * 100}%`; grip.style.left = "50%"; }
    }
  };
  cropOverlay.addEventListener("pointerdown", (event) => {
    const edge = (event.target as HTMLElement).closest<HTMLElement>("[data-edge]")?.dataset.edge as "left" | "top" | "right" | "bottom" | undefined;
    const id = engine.snapshot.selectedClipId, found = id ? engine.findClip(id) : null;
    if (!edge || !found || engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks[found.trackIndex].locked) return;
    event.preventDefault(); event.stopPropagation(); engine.pause();
    const frame = cropOverlay.getBoundingClientRect();
    const working = cropBox(found.clip);
    dragging = true;
    cropOverlay.setPointerCapture(event.pointerId);
    const moveGrip = (next: PointerEvent) => {
      if (edge === "left") working.left = Math.min(0.45, Math.max(0, (next.clientX - frame.left) / frame.width));
      if (edge === "right") working.right = Math.min(0.45, Math.max(0, (frame.right - next.clientX) / frame.width));
      if (edge === "top") working.top = Math.min(0.45, Math.max(0, (next.clientY - frame.top) / frame.height));
      if (edge === "bottom") working.bottom = Math.min(0.45, Math.max(0, (frame.bottom - next.clientY) / frame.height));
      const window_ = cropOverlay.querySelector<HTMLElement>('[data-ref="window"]')!;
      window_.style.left = `${working.left * 100}%`;
      window_.style.top = `${working.top * 100}%`;
      window_.style.right = `${working.right * 100}%`;
      window_.style.bottom = `${working.bottom * 100}%`;
    };
    const release = () => {
      cropOverlay.removeEventListener("pointermove", moveGrip);
      dragging = false;
      const rounded = Object.fromEntries(Object.entries(working).map(([k, v]) => [k, Math.round(v * 1000) / 1000]));
      engine.dispatch("clip.creator", { clipId: found.clip.id, patch: { crop: rounded } });
      drawCrop();
    };
    cropOverlay.addEventListener("pointermove", moveGrip);
    cropOverlay.addEventListener("pointerup", release, { once: true });
    cropOverlay.addEventListener("pointercancel", release, { once: true });
  });
  let dragging = false;
  const draw = () => {
    const state = engine.snapshot, found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    const clip = found?.clip;
    const shown = clip && clip.kind !== "audio" && clip.kind !== "filter" && clip.start <= state.playhead && state.playhead <= clip.start + clip.duration && !state.timelines[state.activeTimeline].tracks[found!.trackIndex].hidden;
    overlay.hidden = !shown;
    if (!clip || !shown) return;
    const media = clip.mediaId ? bin.find(clip.mediaId) : null;
    const box = cropBox(clip);
    const w = (media?.width || state.width) * (1 - box.left - box.right), h = (media?.height || state.height) * (1 - box.top - box.bottom);
    const fit = Math.min(state.width / w, state.height / h);
    const tr = sampledTransform(clip, state.playhead - clip.start);
    overlay.style.width = `${w * fit / state.width * tr.scale * tr.width / 100}%`;
    overlay.style.height = `${h * fit / state.height * tr.scale * tr.height / 100}%`;
    overlay.style.left = `${50 + tr.posX}%`; overlay.style.top = `${50 + tr.posY}%`;
    overlay.style.transform = `translate(-50%, -50%) rotate(${tr.rotation}deg)`;
    const brush = document.querySelector<HTMLElement>(".creator-panel")?.dataset.brush;
    overlay.style.pointerEvents = (brush && brush !== "off") || state.timelines[state.activeTimeline].tracks[found!.trackIndex].locked ? "none" : "auto";
  };
  overlay.addEventListener("pointerdown", event => {
    const handle = (event.target as HTMLElement).closest<HTMLElement>("[data-handle]")?.dataset.handle;
    const id = engine.snapshot.selectedClipId, found = id ? engine.findClip(id) : null;
    const brush = document.querySelector<HTMLElement>(".creator-panel")?.dataset.brush;
    if (!handle || !found || (brush && brush !== "off") || engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks[found.trackIndex].locked) return;
    event.preventDefault(); event.stopPropagation(); engine.pause();
    const tr = sampledTransform(found.clip, engine.snapshot.playhead - found.clip.start);
    const box = stage.getBoundingClientRect(), startX = event.clientX, startY = event.clientY;
    const cx = box.left + box.width * (0.5 + tr.posX / 100), cy = box.top + box.height * (0.5 + tr.posY / 100);
    const distance = Math.max(1, Math.hypot(startX - cx, startY - cy)), angle = Math.atan2(startY - cy, startX - cx);
    const token = engine.snapshot.timelines, before = structuredClone({ transform: found.clip.transform, keyframes: found.clip.keyframes });
    let changed = false;
    dragging = true; overlay.setPointerCapture(event.pointerId);
    const pointerMove = (next: PointerEvent) => {
      if (engine.snapshot.timelines !== token) return;
      const patch: Record<string, number> = {};
      const dx = (next.clientX - startX) / box.width * 100, dy = (next.clientY - startY) / box.height * 100;
      if (handle === "move") { patch.posX = tr.posX + dx; patch.posY = tr.posY + dy; }
      else if (handle === "rotate") patch.rotation = tr.rotation + (Math.atan2(next.clientY - cy, next.clientX - cx) - angle) * 180 / Math.PI;
      else if (handle.length === 2) patch.scale = Math.max(1, Math.min(2000, tr.scale * Math.hypot(next.clientX - cx, next.clientY - cy) / distance));
      else if (handle === "e" || handle === "w") patch.width = Math.max(1, tr.width + dx * (handle === "w" ? -1 : 1) * 2);
      else patch.height = Math.max(1, tr.height + dy * (handle === "n" ? -1 : 1) * 2);
      engine.previewTransform(found.clip.id, patch); changed = true; draw();
    };
    const finish = (commit: boolean) => {
      overlay.removeEventListener("pointermove", pointerMove); overlay.removeEventListener("pointerup", up); overlay.removeEventListener("pointercancel", cancel);
      dragging = false;
      if (engine.snapshot.timelines === token && changed) {
        engine.finishTransform(found.clip.id, before, commit);
      }
      draw();
    };
    const up = () => finish(true), cancel = () => finish(false);
    overlay.addEventListener("pointermove", pointerMove); overlay.addEventListener("pointerup", up, { once: true }); overlay.addEventListener("pointercancel", cancel, { once: true });
  });
  engine.subscribe((_state, event) => { if (!dragging && ["clips", "timeline", "clip-selection", "playhead"].includes(event)) { draw(); drawCrop(); } });
  stage.addEventListener("formcut:crop-mode", () => { drawCrop(); draw(); });
  document.addEventListener("change", event => { if ((event.target as HTMLElement).matches("[data-brush]")) draw(); });
  bin.subscribe(draw); draw();
}
