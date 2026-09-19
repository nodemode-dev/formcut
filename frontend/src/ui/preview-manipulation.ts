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
  const guides = document.createElement("div");
  guides.className = "preview-guides";
  guides.hidden = true;
  guides.innerHTML = `<div class="guide-line" data-axis="x" hidden></div><div class="guide-line" data-axis="y" hidden></div>`;
  stage.append(guides);
  const guideX = guides.querySelector<HTMLElement>('[data-axis="x"]')!;
  const guideY = guides.querySelector<HTMLElement>('[data-axis="y"]')!;
  /** A clip's drawn box as stage fractions. */
  const layerBox = (clip: import("../engine/types").Clip, state = engine.snapshot) => {
    const media = clip.mediaId ? bin.find(clip.mediaId) : null;
    const cb = cropBox(clip);
    const w = (media?.width || state.width) * (1 - cb.left - cb.right), h = (media?.height || state.height) * (1 - cb.top - cb.bottom);
    const fit = Math.min(state.width / w, state.height / h);
    const tr = sampledTransform(clip, state.playhead - clip.start);
    const fw = w * fit / state.width * tr.scale / 100 * tr.width / 100;
    const fh = h * fit / state.height * tr.scale / 100 * tr.height / 100;
    const cx = 0.5 + tr.posX / 100, cy = 0.5 + tr.posY / 100;
    return { left: cx - fw / 2, cx, right: cx + fw / 2, top: cy - fh / 2, cy, bottom: cy + fh / 2, fw, fh };
  };
  /** Candidate guide positions per axis. */
  const guideCandidates = (skipId: string) => {
    const state = engine.snapshot;
    const xs = [0, 1 / 3, 0.5, 2 / 3, 1], ys = [0, 1 / 3, 0.5, 2 / 3, 1];
    for (const track of state.timelines[state.activeTimeline].tracks) {
      if (track.hidden) continue;
      for (const other of track.clips) {
        if (other.id === skipId || other.kind === "audio" || other.kind === "filter") continue;
        if (other.start > state.playhead || state.playhead > other.start + other.duration) continue;
        const box = layerBox(other, state);
        xs.push(box.left, box.cx, box.right);
        ys.push(box.top, box.cy, box.bottom);
      }
    }
    return { xs, ys };
  };
  const hideGuides = () => { guides.hidden = true; guideX.hidden = true; guideY.hidden = true; };
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
    const candidates = guideCandidates(found.clip.id);
    const startBox = layerBox(found.clip);
    const pointerMove = (next: PointerEvent) => {
      if (engine.snapshot.timelines !== token) return;
      const patch: Record<string, number> = {};
      const dx = (next.clientX - startX) / box.width * 100, dy = (next.clientY - startY) / box.height * 100;
      let lineX: number | null = null, lineY: number | null = null;
      const limitX = 6 / box.width, limitY = 6 / box.height;
      if (handle === "move") {
        patch.posX = tr.posX + dx; patch.posY = tr.posY + dy;
        if (!next.altKey) {
          const cxNow = 0.5 + patch.posX / 100, cyNow = 0.5 + patch.posY / 100;
          let bestX = limitX;
          for (const candidate of candidates.xs) for (const edge of [cxNow - startBox.fw / 2, cxNow, cxNow + startBox.fw / 2]) {
            const gap = candidate - edge;
            if (Math.abs(gap) < Math.abs(bestX)) { bestX = gap; lineX = candidate; }
          }
          if (lineX !== null) patch.posX += bestX * 100;
          let bestY = limitY;
          for (const candidate of candidates.ys) for (const edge of [cyNow - startBox.fh / 2, cyNow, cyNow + startBox.fh / 2]) {
            const gap = candidate - edge;
            if (Math.abs(gap) < Math.abs(bestY)) { bestY = gap; lineY = candidate; }
          }
          if (lineY !== null) patch.posY += bestY * 100;
          patch.posX = Math.round(patch.posX * 100) / 100 + 0;
          patch.posY = Math.round(patch.posY * 100) / 100 + 0;
        }
      }
      else if (handle === "rotate") patch.rotation = tr.rotation + (Math.atan2(next.clientY - cy, next.clientX - cx) - angle) * 180 / Math.PI;
      else if (handle.length === 2) {
        patch.scale = Math.max(1, Math.min(2000, tr.scale * Math.hypot(next.clientX - cx, next.clientY - cy) / distance));
        if (!next.altKey && startBox.fw > 0.001) {
          const grow = patch.scale / tr.scale;
          const half = { x: 0.5 + tr.posX / 100, y: 0.5 + tr.posY / 100 };
          const movingX = handle.includes("w") ? half.x - startBox.fw / 2 * grow : half.x + startBox.fw / 2 * grow;
          const movingY = handle.includes("n") ? half.y - startBox.fh / 2 * grow : half.y + startBox.fh / 2 * grow;
          let best: { scale: number; lineX?: number; lineY?: number } | null = null;
          for (const candidate of candidates.xs) {
            if (Math.abs(candidate - movingX) < limitX) {
              const wanted = Math.abs(candidate - half.x) * 2 / startBox.fw * tr.scale;
              if (wanted >= 1 && wanted <= 2000) { best = { scale: wanted, lineX: candidate }; break; }
            }
          }
          if (!best) for (const candidate of candidates.ys) {
            if (Math.abs(candidate - movingY) < limitY) {
              const wanted = Math.abs(candidate - half.y) * 2 / startBox.fh * tr.scale;
              if (wanted >= 1 && wanted <= 2000) { best = { scale: wanted, lineY: candidate }; break; }
            }
          }
          if (best) { patch.scale = Math.round(best.scale * 100) / 100; lineX = best.lineX ?? null; lineY = best.lineY ?? null; }
        }
      }
      else if (handle === "e" || handle === "w") patch.width = Math.max(1, tr.width + dx * (handle === "w" ? -1 : 1) * 2);
      else patch.height = Math.max(1, tr.height + dy * (handle === "n" ? -1 : 1) * 2);
      guides.hidden = lineX === null && lineY === null;
      guideX.hidden = lineX === null;
      guideY.hidden = lineY === null;
      if (lineX !== null) guideX.style.left = `${lineX * 100}%`;
      if (lineY !== null) guideY.style.top = `${lineY * 100}%`;
      engine.previewTransform(found.clip.id, patch); changed = true; draw();
    };
    const finish = (commit: boolean) => {
      overlay.removeEventListener("pointermove", pointerMove); overlay.removeEventListener("pointerup", up); overlay.removeEventListener("pointercancel", cancel);
      dragging = false;
      hideGuides();
      if (engine.snapshot.timelines === token && changed) {
        engine.finishTransform(found.clip.id, before, commit);
      }
      draw();
    };
    const up = () => finish(true), cancel = () => finish(false);
    overlay.addEventListener("pointermove", pointerMove); overlay.addEventListener("pointerup", up, { once: true }); overlay.addEventListener("pointercancel", cancel, { once: true });
  });
  const typing = document.createElement("div");
  typing.className = "canvas-typing";
  typing.hidden = true;
  typing.contentEditable = "true";
  typing.spellcheck = false;
  stage.append(typing);
  let typingId = "";
  const endTyping = (commit: boolean) => {
    if (!typingId) return;
    const id = typingId;
    typingId = "";
    typing.hidden = true;
    const next = typing.innerText.replace(/\n$/, "");
    const found = engine.findClip(id);
    if (commit && found && next !== (found.clip.textStyle?.content ?? found.clip.label)) {
      engine.dispatch("clip.text", { clipId: id, patch: { content: next } });
    }
  };
  stage.addEventListener("dblclick", (event) => {
    const state = engine.snapshot;
    const found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    if (!found || found.clip.kind !== "text") return;
    if (state.timelines[state.activeTimeline].tracks[found.trackIndex].locked) return;
    event.preventDefault();
    engine.pause();
    typingId = found.clip.id;
    typing.innerText = found.clip.textStyle?.content ?? found.clip.label;
    const box = layerBox(found.clip);
    typing.style.left = `${box.left * 100}%`;
    typing.style.top = `${box.top * 100}%`;
    typing.style.width = `${Math.max(0.1, box.right - box.left) * 100}%`;
    typing.hidden = false;
    typing.focus();
    const range = document.createRange();
    range.selectNodeContents(typing);
    window.getSelection()?.removeAllRanges();
    window.getSelection()?.addRange(range);
  });
  typing.addEventListener("keydown", (event) => {
    if (event.key === "Escape") { event.preventDefault(); endTyping(false); }
    if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); endTyping(true); }
    event.stopPropagation();
  });
  typing.addEventListener("blur", () => endTyping(true));

  engine.subscribe((_state, event) => { if (!dragging && ["clips", "timeline", "clip-selection", "playhead"].includes(event)) { draw(); drawCrop(); } });
  stage.addEventListener("formcut:crop-mode", () => { drawCrop(); draw(); });
  document.addEventListener("change", event => { if ((event.target as HTMLElement).matches("[data-brush]")) draw(); });
  bin.subscribe(draw); draw();
}
