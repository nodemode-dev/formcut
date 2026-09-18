import { escapeHtml } from "./safe-text";
import { formatTimecode, type ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import type { Clip } from "../engine/types";
import { icon } from "./icons";
import { t } from "../i18n";
import { reconcileTimelineStructure } from "./timeline-structure";
import { paintClipBody } from "./clip-visuals";
import { buildKeyframeLanes } from "./keyframe-lanes";

let PX_PER_SEC = 90;
const HEAD_W = 208;

function clipHtml(c: Clip, selectedId: string | null): string {
  const left = c.start * PX_PER_SEC;
  const width = c.duration * PX_PER_SEC - 3;
  const compact = c.kind === "text" || c.kind === "filter";
  const label = escapeHtml(c.label);
  const inner = compact
    ? `<div class="bar">${c.kind === "filter" ? icon("magnet") : ""}${label}</div>${c.fx ? `<span class="fx-chip">fx</span>` : ""}`
    : `<div class="bar">${label}</div><div class="body"></div>`;
  const sel = c.id === selectedId ? " is-selected" : "";
  const badges =
    (c.transitionIn ? `<span class="clip-badge badge-trans" title="${c.transitionIn.type}">${icon("diamond")}</span>` : "") +
    (c.keyframes && c.keyframes.length ? `<span class="clip-badge badge-kf">${icon("diamond")}</span>` : "") +
    (c.muted ? `<span class="clip-badge badge-mute">M</span>` : "");
  return `<div class="clip k-${escapeHtml(c.kind)}${sel}" data-clip="${escapeHtml(c.id)}" style="left:${left}px;width:${width}px">${inner}${badges}<span class="trim trim-l"></span><span class="trim trim-r"></span></div>`;
}

export function buildTimelinePane(engine: ProjectEngine, bin: MediaBin): HTMLElement {
  const s = engine.snapshot;
  const tl = s.timelines[s.activeTimeline];
  const spanSec = Math.max(s.duration + 6, 18);
  const laneW = spanSec * PX_PER_SEC;
  const zoom = (factor: number) => {
    PX_PER_SEC = Math.max(12, Math.min(720, PX_PER_SEC * factor));
    el.dataset.scale = String(PX_PER_SEC);
    rulerEl.style.width = `${currentSpan * PX_PER_SEC}px`;
    for (const lane of lanes) lane.style.width = rulerEl.style.width;
    [...rulerEl.querySelectorAll<HTMLElement>(".tick")].forEach((tick, index) => { tick.style.left = `${index * 2 * PX_PER_SEC}px`; });
    el.dataset.scale = String(PX_PER_SEC);
  reconcile();
    scroller.scrollLeft = Math.max(0, engine.snapshot.playhead * PX_PER_SEC - scroller.clientWidth / 2);
    playhead.style.left = `${HEAD_W + engine.snapshot.playhead * PX_PER_SEC - scroller.scrollLeft}px`;
  };
  const ruler = Array.from({ length: Math.ceil(spanSec / 2) }, (_, i) => {
    const t = i * 2;
    return `<span class="tick" style="left:${t * PX_PER_SEC}px">${formatTimecode(t, s.fps)}</span>`;
  }).join("");

  const el = document.createElement("section");
  el.className = "pane pane-timeline";
  el.innerHTML = `
    <div class="tl-tabs" data-ref="tabs">
      ${s.timelines.map((t, i) => `<button class="tl-tab${i === s.activeTimeline ? " is-active" : ""}" data-tl="${i}">${t.name}</button>`).join("")}
      <button class="iconbtn">${icon("plus")}</button>
      <span class="spacer"></span>
      <button class="select-chip">${icon("layout")}${icon("chevD")}</button>
    </div>
    <div class="tl-toolbar">
      <button class="iconbtn is-accent" title="${t('tool.select')}" data-ref="tool-select">${icon("pointer")}</button>
      <button class="iconbtn" title="${t('tool.blade')}" data-ref="tool-blade">${icon("blade")}</button>
      <span class="divider"></span>
      <button class="iconbtn" title="${t('tool.split')}" data-ref="act-split">${icon("split")}</button>
      <button class="iconbtn" title="${t('tool.detach')}" data-ref="act-detach">${icon("detach")}</button>
      <button class="iconbtn" title="${t('tool.ripple')}" data-ref="act-ripple">${icon("ripple")}</button>
      <button class="iconbtn" title="${t('tool.delete')}" data-ref="act-delete">${icon("trash")}</button>
      <span class="divider"></span>
      <button class="iconbtn is-accent" title="${t('tool.snap')}" data-ref="snap">${icon("magnet")}</button>
      <span class="divider"></span>
      <button class="tool-chip" data-ref="chip-captions">${icon("captions")}${t("chip.captions")}</button>
      <button class="tool-chip" data-ref="chip-speak" disabled>${icon("speak")}${t("chip.speak")}</button>
      <button class="tool-chip" data-ref="chip-detach">${icon("detach")}${t("chip.detach")}</button>
      <button class="iconbtn" title="${t('tool.addtrack')}" data-ref="act-add-track">${icon("addTrack")}</button>
      <span class="spacer"></span>
      <span class="tl-tc" data-ref="tc">${formatTimecode(s.playhead, s.fps)}</span>
      <button class="iconbtn" title="${t('tool.fit')}" data-ref="zoom-fit">${icon("fit")}</button>
      <button class="iconbtn" title="${t('tool.zoomout')}" data-ref="zoom-out">${icon("zoomOut")}</button>
      <button class="iconbtn" title="${t('tool.zoomin')}" data-ref="zoom-in">${icon("zoomIn")}</button>
    </div>
    <div class="tl-scroller" data-ref="scroller">
      <div class="tl-grid" data-ref="grid">
        <div class="tl-corner"></div>
        <div class="tl-ruler" data-ref="ruler" style="width:${laneW}px">${ruler}</div>
        ${tl.tracks
          .map(
            (t) => `
          <div class="track-head">
            <span class="name">${t.name}</span>
            <button class="iconbtn">${icon("trash")}</button>
            <button class="iconbtn">${icon("lock")}</button>
            <button class="iconbtn">${icon("eye")}</button>
            <button class="iconbtn">${icon("speaker")}</button>
          </div>
          <div class="lane" style="width:${laneW}px">${t.clips.map((c) => clipHtml(c, s.selectedClipId)).join("")}</div>`,
          )
          .join("")}
      </div>
      <div class="playhead" data-ref="playhead" style="left:${HEAD_W + s.playhead * PX_PER_SEC}px"><button class="playhead-grab" data-ref="playhead-grab" aria-label="Scrub playhead"></button></div>
    </div>`;

  const playhead = el.querySelector<HTMLElement>('[data-ref="playhead"]')!;
  const tc = el.querySelector<HTMLElement>('[data-ref="tc"]')!;
  const scroller = el.querySelector<HTMLElement>('[data-ref="scroller"]')!;
  const rulerEl = el.querySelector<HTMLElement>('[data-ref="ruler"]')!;

  const scrubTo = (clientX: number) => {
    const rect = rulerEl.getBoundingClientRect();
    const state = engine.snapshot;
    let time = Math.max(0, (clientX - rect.left) / PX_PER_SEC);
    if (snapOn) {
      const tl = state.timelines[state.activeTimeline];
      const edges = [0, ...tl.tracks.flatMap((track) => track.clips.flatMap((clip) => [clip.start, clip.start + clip.duration]))];
      time = snapValue(time, edges);
    }
    engine.dispatch("transport.seek", Math.round(time * state.fps) / state.fps);
  };
  const beginScrub = (ev: PointerEvent, target: HTMLElement) => {
    if (ev.button !== 0) return;
    ev.preventDefault();
    engine.pause();
    target.setPointerCapture(ev.pointerId);
    scrubTo(ev.clientX);
    const move = (move_ev: PointerEvent) => scrubTo(move_ev.clientX);
    const end = (end_ev: PointerEvent) => {
      target.releasePointerCapture(end_ev.pointerId);
      target.removeEventListener("pointermove", move);
      target.removeEventListener("pointerup", end);
      target.removeEventListener("pointercancel", end);
    };
    target.addEventListener("pointermove", move);
    target.addEventListener("pointerup", end);
    target.addEventListener("pointercancel", end);
  };
  rulerEl.addEventListener("pointerdown", (ev) => beginScrub(ev, rulerEl));
  el.querySelector<HTMLElement>('[data-ref="playhead-grab"]')!.addEventListener("pointerdown", (ev) => beginScrub(ev, el.querySelector<HTMLElement>('[data-ref="playhead-grab"]')!));

  const lanes = Array.from(el.querySelectorAll<HTMLElement>(".lane"));
  let currentSpan = spanSec;

  const reconcile = () => {
    const state = engine.snapshot;
    const timeline = state.timelines[state.activeTimeline];
    reconcileTimelineStructure(el, engine, bin, lanes, currentSpan * PX_PER_SEC, PX_PER_SEC);
    const neededSpan = Math.max(state.duration + 6, 18);
    if (neededSpan > currentSpan) {
      const width = `${neededSpan * PX_PER_SEC}px`;
      const from = Math.ceil(currentSpan / 2) * 2;
      for (let t = from; t < neededSpan; t += 2) {
        rulerEl.insertAdjacentHTML(
          "beforeend",
          `<span class="tick" style="left:${t * PX_PER_SEC}px">${formatTimecode(t, state.fps)}</span>`,
        );
      }
      rulerEl.style.width = width;
      for (const lane of lanes) lane.style.width = width;
      currentSpan = neededSpan;
    }
    for (const [trackIndex, lane] of lanes.entries()) {
      const clips = timeline.tracks[trackIndex]?.clips ?? [];
      const byId = new Map(clips.map((c) => [c.id, c]));
      for (const node of Array.from(lane.querySelectorAll<HTMLElement>(".clip"))) {
        const clip = byId.get(node.dataset.clip!);
        if (!clip) {
          node.remove();
          continue;
        }
        byId.delete(clip.id);
        const left = `${clip.start * PX_PER_SEC}px`;
        const width = `${clip.duration * PX_PER_SEC - 3}px`;
        if (node.style.left !== left) node.style.left = left;
        if (node.style.width !== width) node.style.width = width;
        node.classList.toggle("is-selected", clip.id === state.selectedClipId);
        const label = node.querySelector<HTMLElement>(".bar");
        if (label && label.textContent !== clip.label) label.textContent = clip.label;
        const sig =
          (clip.transitionIn ? "t" : "") +
          (clip.keyframes && clip.keyframes.length ? "k" : "") +
          (clip.muted ? "m" : "");
        if (node.dataset.badges !== sig) {
          node.dataset.badges = sig;
          for (const old of node.querySelectorAll(".clip-badge")) old.remove();
          const trimL = node.querySelector(".trim-l")!;
          const badges =
            (clip.transitionIn
              ? `<span class="clip-badge badge-trans" title="${clip.transitionIn.type}">${icon("diamond")}</span>`
              : "") +
            (clip.keyframes && clip.keyframes.length
              ? `<span class="clip-badge badge-kf">${icon("diamond")}</span>`
              : "") +
            (clip.muted ? `<span class="clip-badge badge-mute">M</span>` : "");
          trimL.insertAdjacentHTML("beforebegin", badges);
        }
        // Waveforms and frames are drawn from cached media data; the painter
        // skips the work itself when nothing that changes the picture moved.
        paintClipBody(node, clip, bin);
      }
      for (const clip of byId.values()) {
        lane.insertAdjacentHTML("beforeend", clipHtml(clip, state.selectedClipId));
        const added = lane.querySelector<HTMLElement>(`.clip[data-clip="${clip.id}"]`);
        if (added) paintClipBody(added, clip, bin);
      }
    }
  };
  const syncSelection = () => {
    const selected = engine.snapshot.selectedClipId;
    for (const node of el.querySelectorAll<HTMLElement>(".clip")) {
      node.classList.toggle("is-selected", node.dataset.clip === selected);
    }
  };

  for (const [trackIndex, lane] of lanes.entries()) {
    lane.addEventListener("dragover", (ev) => {
      if (!ev.dataTransfer?.types.includes("application/x-formcut-media")) return;
      ev.preventDefault();
      ev.dataTransfer.dropEffect = "copy";
      if (!lane.classList.contains("is-drop")) lane.classList.add("is-drop");
    });
    lane.addEventListener("dragleave", () => lane.classList.remove("is-drop"));
    lane.addEventListener("drop", (ev) => {
      lane.classList.remove("is-drop");
      const mediaId = ev.dataTransfer?.getData("application/x-formcut-media");
      const item = mediaId ? bin.find(mediaId) : undefined;
      if (!item) return;
      ev.preventDefault();
      const rect = lane.getBoundingClientRect();
      const start = Math.max(0, (ev.clientX - rect.left) / PX_PER_SEC);
      const clip: Clip = {
        id: crypto.randomUUID(),
        kind: item.kind,
        label: item.name,
        start: Math.round(start * 10) / 10,
        duration: Math.max(item.duration, 0.5),
        mediaId: item.id,
        filmstrip: item.kind === "video",
      };
      engine.dispatch("clip.add", { trackIndex, clip });
    });
  }
  el.querySelector('[data-ref="tabs"]')!.addEventListener("click", (ev) => {
    const hit = (ev.target as HTMLElement).closest<HTMLElement>(".tl-tab");
    if (!hit) return;
    const tabs = el.querySelectorAll(".tl-tab");
    tabs.forEach((t) => t.classList.toggle("is-active", t === hit));
    engine.dispatch("timeline.activate", Number(hit.dataset.tl));
  });

  engine.subscribe((state, changed) => {
    if (changed === "clips" || changed === "timeline" || changed === "project") reconcile();
    if (changed === "clip-selection") syncSelection();
    if (changed !== "playhead") return;
    playhead.style.left = `${HEAD_W + state.playhead * PX_PER_SEC - scroller.scrollLeft}px`;
    const next = formatTimecode(state.playhead, state.fps);
    if (tc.textContent !== next) tc.textContent = next;
  });
  scroller.addEventListener("scroll", () => {
    playhead.style.left = `${HEAD_W + engine.snapshot.playhead * PX_PER_SEC - scroller.scrollLeft}px`;
  });

  let tool: "select" | "blade" = "select";
  const toolBtns = {
    select: el.querySelector<HTMLElement>('[data-ref="tool-select"]')!,
    blade: el.querySelector<HTMLElement>('[data-ref="tool-blade"]')!,
  };
  const setTool = (next: "select" | "blade") => {
    if (tool === next) return;
    tool = next;
    toolBtns.select.classList.toggle("is-accent", next === "select");
    toolBtns.blade.classList.toggle("is-accent", next === "blade");
    scroller.classList.toggle("mode-blade", next === "blade");
  };
  toolBtns.select.addEventListener("click", () => setTool("select"));
  toolBtns.blade.addEventListener("click", () => setTool("blade"));

  let snapOn = true;
  const snapBtn = el.querySelector<HTMLElement>('[data-ref="snap"]')!;
  snapBtn.addEventListener("click", () => {
    snapOn = !snapOn;
    snapBtn.classList.toggle("is-accent", snapOn);
  });
  const collectSnapPoints = (excludeId: string): number[] => {
    const state = engine.snapshot;
    const points = [0, state.playhead];
    for (const track of state.timelines[state.activeTimeline].tracks) {
      for (const clip of track.clips) {
        if (clip.id === excludeId) continue;
        points.push(clip.start, clip.start + clip.duration);
      }
    }
    return points;
  };
  const snapValue = (value: number, points: number[]): number => {
    let best = value;
    let bestDist = 8 / PX_PER_SEC;
    for (const point of points) {
      const dist = Math.abs(point - value);
      if (dist < bestDist) {
        best = point;
        bestDist = dist;
      }
    }
    return best;
  };

  type Drag = {
    kind: "move" | "trim-l" | "trim-r";
    node: HTMLElement;
    clipId: string;
    originX: number;
    start: number;
    duration: number;
    moved: boolean;
    laneIndex: number;
    snapPoints: number[];
  };
  let drag: Drag | null = null;

  scroller.addEventListener("pointerdown", (ev) => {
    const target = ev.target as HTMLElement;
    const node = target.closest<HTMLElement>(".clip");
    if (!node) {
      if (target.closest(".lane")) engine.dispatch("clip.select", null);
      return;
    }
    const clipId = node.dataset.clip!;
    const found = engine.findClip(clipId);
    if (!found) return;
    if (engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks[found.trackIndex].locked) return;
    if (tool === "blade") {
      const lane = node.parentElement!;
      const time = (ev.clientX - lane.getBoundingClientRect().left) / PX_PER_SEC;
      engine.dispatch("clip.split", { clipId, time });
      return;
    }
    engine.dispatch("clip.select", clipId);
    const kind = target.classList.contains("trim-l")
      ? "trim-l"
      : target.classList.contains("trim-r")
        ? "trim-r"
        : "move";
    drag = {
      kind,
      node,
      clipId,
      originX: ev.clientX,
      start: found.clip.start,
      duration: found.clip.duration,
      moved: false,
      laneIndex: found.trackIndex,
      snapPoints: snapOn ? collectSnapPoints(clipId) : [],
    };
    node.setPointerCapture(ev.pointerId);
  });
  scroller.addEventListener("pointermove", (ev) => {
    if (!drag) return;
    const dx = (ev.clientX - drag.originX) / PX_PER_SEC;
    if (!drag.moved && Math.abs(ev.clientX - drag.originX) < 3) return;
    drag.moved = true;
    let start = drag.start;
    let duration = drag.duration;
    if (drag.kind === "move") {
      start = Math.max(0, drag.start + dx);
      if (drag.snapPoints.length > 0) {
        const snappedStart = snapValue(start, drag.snapPoints);
        const snappedEnd = snapValue(start + duration, drag.snapPoints);
        if (snappedStart !== start) start = snappedStart;
        else if (snappedEnd !== start + duration) start = Math.max(0, snappedEnd - duration);
      }
      const over = lanes.findIndex((lane) => {
        const rect = lane.getBoundingClientRect();
        return ev.clientY >= rect.top && ev.clientY < rect.bottom;
      });
      if (over >= 0 && over !== drag.laneIndex) {
        lanes[over].append(drag.node);
        drag.laneIndex = over;
      }
    }
    if (drag.kind === "trim-l") {
      const shift = Math.min(dx, drag.duration - 0.1);
      start = Math.max(0, drag.start + shift);
      if (drag.snapPoints.length > 0) {
        const snapped = snapValue(start, drag.snapPoints);
        if (snapped <= drag.start + drag.duration - 0.1) start = Math.max(0, snapped);
      }
      duration = drag.duration - (start - drag.start);
    }
    if (drag.kind === "trim-r") {
      duration = Math.max(0.1, drag.duration + dx);
      if (drag.snapPoints.length > 0) {
        const snappedEnd = snapValue(drag.start + duration, drag.snapPoints);
        if (snappedEnd >= drag.start + 0.1) duration = snappedEnd - drag.start;
      }
    }
    drag.node.style.left = `${start * PX_PER_SEC}px`;
    drag.node.style.width = `${duration * PX_PER_SEC - 3}px`;
  });
  scroller.addEventListener("pointerup", () => {
    if (!drag) return;
    const { kind, node, clipId, moved, laneIndex } = drag;
    drag = null;
    if (!moved) return;
    const start = parseFloat(node.style.left) / PX_PER_SEC;
    const duration = (parseFloat(node.style.width) + 3) / PX_PER_SEC;
    if (kind === "move") engine.dispatch("clip.move", { clipId, start, trackIndex: laneIndex });
    else engine.dispatch("clip.trim", { clipId, start, duration });
  });

  el.querySelector('[data-ref="act-split"]')!.addEventListener("click", () => {
    const state = engine.snapshot;
    if (state.selectedClipId) {
      engine.dispatch("clip.split", { clipId: state.selectedClipId, time: state.playhead });
    }
  });
  el.querySelector('[data-ref="act-delete"]')!.addEventListener("click", () => {
    const selected = engine.snapshot.selectedClipId;
    if (selected) engine.dispatch("clip.remove", selected);
  });
  window.addEventListener("keydown", (ev) => {
    const target = ev.target as HTMLElement;
    if (target.closest("input,textarea,select,[contenteditable=true]") || document.querySelector(".modal-scrim:not([hidden])")) return;
    const meta = ev.metaKey || ev.ctrlKey;
    if (meta && ev.key.toLowerCase() === "z") {
      ev.preventDefault();
      engine.dispatch(ev.shiftKey ? "history.redo" : "history.undo");
      return;
    }
    if (ev.key === "Delete" || ev.key === "Backspace") {
      const selected = engine.snapshot.selectedClipId;
      if (selected) {
        ev.preventDefault();
        engine.dispatch("clip.remove", selected);
      }
    }
  });
  el.dataset.scale = String(PX_PER_SEC);
  const tabControls = el.querySelector(".tl-tabs")!;
  tabControls.querySelector<HTMLButtonElement>(".iconbtn")!.addEventListener("click", () => engine.dispatch("timeline.add", {}));
  const toolbar = el.querySelector(".tl-toolbar")!;
  const control = (ref: string) => toolbar.querySelector<HTMLButtonElement>(`[data-ref="${ref}"]`);
  control("zoom-in")?.addEventListener("click", () => zoom(1.4));
  control("zoom-out")?.addEventListener("click", () => zoom(1 / 1.4));
  control("zoom-fit")?.addEventListener("click", () => zoom((scroller.clientWidth - HEAD_W) / Math.max(1, engine.snapshot.duration) / PX_PER_SEC));
  control("act-add-track")?.addEventListener("click", () => engine.dispatch("track.add", {}));
  scroller.addEventListener("pointercancel", () => { drag = null; reconcile(); });
  reconcile();
  // The lane area lives under the timeline and is appended once: it renders its
  // own contents from the engine and never rebuilds the tracks above it.
  el.append(buildKeyframeLanes(engine, PX_PER_SEC));
  return el;
}
