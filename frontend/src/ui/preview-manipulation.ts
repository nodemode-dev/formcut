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
  let dragging = false;
  const draw = () => {
    const state = engine.snapshot, found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    const clip = found?.clip;
    const shown = clip && clip.kind !== "audio" && clip.kind !== "filter" && clip.start <= state.playhead && state.playhead <= clip.start + clip.duration && !state.timelines[state.activeTimeline].tracks[found!.trackIndex].hidden;
    overlay.hidden = !shown;
    if (!clip || !shown) return;
    const media = clip.mediaId ? bin.find(clip.mediaId) : null;
    const w = media?.width || state.width, h = media?.height || state.height;
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
  engine.subscribe((_state, event) => { if (!dragging && ["clips", "timeline", "clip-selection", "playhead"].includes(event)) draw(); });
  document.addEventListener("change", event => { if ((event.target as HTMLElement).matches("[data-brush]")) draw(); });
  bin.subscribe(draw); draw();
}
