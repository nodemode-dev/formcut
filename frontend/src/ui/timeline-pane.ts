import { escapeHtml } from "./safe-text";
import { formatTimecode, type ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import type { Clip } from "../engine/types";
import { speedAt } from "../engine/timing";
import { icon } from "./icons";
import { reconcile as orderNodes } from "./keyed-list";
import { t } from "../i18n";
import { reconcileTimelineStructure } from "./timeline-structure";
import { paintClipBody } from "./clip-visuals";
import { installTrackKeyframes } from "./track-keyframes";
import { installWorkArea } from "./work-area";

let PX_PER_SEC = 90;
const HEAD_W = 248;

function clipHtml(c: Clip, selectedId: string | null): string {
  const left = c.start * PX_PER_SEC;
  const width = c.duration * PX_PER_SEC - 3;
  const compact = c.kind === "text" || c.kind === "filter";
  const label = escapeHtml(c.label);
  const inner = compact
    ? `<div class="bar">${c.kind === "filter" ? icon("sliders") : ""}${label}</div>${c.fx ? `<span class="fx-chip">fx</span>` : ""}`
    : `<div class="bar">${label}</div><div class="body"></div>`;
  const sel = c.id === selectedId ? " is-selected" : "";
  const badges =
    (c.transitionIn ? `<span class="clip-badge badge-trans" title="${c.transitionIn.type}">${icon("diamond")}</span>` : "") +
    (c.keyframes && c.keyframes.length ? `<span class="clip-badge badge-kf">${icon("diamond")}</span>` : "") +
    (c.muted ? `<span class="clip-badge badge-mute">M</span>` : "");
  return `<div class="clip k-${escapeHtml(c.kind)}${sel}" data-clip="${escapeHtml(c.id)}" role="button" tabindex="0" aria-label="${label}" style="left:${left}px;width:${width}px">${inner}${badges}<span class="trim trim-l"></span><span class="trim trim-r"></span></div>`;
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
    paintMarkers();
    el.dataset.scale = String(PX_PER_SEC);
  reconcile();
    paintRange();
    scroller.scrollLeft = Math.max(0, engine.snapshot.playhead * PX_PER_SEC - scroller.clientWidth / 2);
    playhead.style.left = `${HEAD_W + engine.snapshot.playhead * PX_PER_SEC}px`;
  };
  const ruler = Array.from({ length: Math.ceil(spanSec / 2) }, (_, i) => {
    const t = i * 2;
    return `<span class="tick" style="left:${t * PX_PER_SEC}px">${formatTimecode(t, s.fps)}</span>`;
  }).join("");

  const el = document.createElement("section");
  el.className = "pane pane-timeline";
  el.innerHTML = `
    <div class="tl-tabs" data-ref="tabs" data-feature="tl.tabs">
      <div class="tl-tab-strip" data-ref="tab-strip">
        ${s.timelines.map((t, i) => `<button class="tl-tab${i === s.activeTimeline ? " is-active" : ""}" data-tl="${i}" title="${t.name}">${t.name}</button>`).join("")}
      </div>
      <button class="iconbtn" data-ref="tl-add" title="${t("tl.add")}">${icon("plus")}</button>
      <button class="iconbtn" data-ref="tl-remove" title="${t("tl.remove")}">${icon("trash")}</button>
      <button class="select-chip">${icon("layout")}${icon("chevD")}</button>
      <span class="divider"></span>
      <button class="tool-chip" data-ref="chip-captions" data-feature="chip.captions">${icon("captions")}${t("chip.captions")}</button>
      <button class="tool-chip" data-ref="chip-speak" data-feature="chip.speak" disabled>${icon("speak")}${t("chip.speak")}</button>
      <button class="tool-chip" data-ref="chip-detach" data-feature="chip.detach">${icon("detach")}${t("chip.detach")}</button>
      <button class="tool-chip" data-ref="chip-focus" data-feature="chip.focus" title="${t("focus.tip")}">${icon("pip")}${t("focus.title")}</button>
      <button class="tool-chip" data-ref="chip-device" data-feature="chip.device" title="${t("dev.tip")}">${icon("phone")}${t("dev.add")}</button>
      <button class="iconbtn" title="${t('tool.addtrack')}" data-ref="act-add-track" data-feature="act.addTrack" data-label="${t('tool.addtrack')}">${icon("addTrack")}</button>
      <span class="divider"></span>
      <button class="tool-chip" data-ref="range-extract" data-feature="range.extract" title="${t("range.extract.tip")}" disabled>${icon("range")}${t("pro.extract")}</button>
      <button class="tool-chip" data-ref="range-lift" data-feature="range.lift" title="${t("range.lift.tip")}" disabled>${t("pro.lift")}</button>
      <button class="iconbtn" data-ref="range-clear" data-feature="range.clear" title="${t("range.clear")}" aria-label="${t("range.clear")}" disabled>${icon("close")}</button>
      <span class="spacer"></span>
      <span class="tl-tc" data-ref="tc">${formatTimecode(s.playhead, s.fps)}</span>
      <button class="iconbtn" title="${t('tool.fit')}" data-ref="zoom-fit" data-feature="zoom.fit" data-label="${t('tool.fit')}">${icon("fit")}</button>
      <button class="iconbtn" title="${t('tool.zoomout')}" data-ref="zoom-out" data-feature="zoom.out" data-label="${t('tool.zoomout')}">${icon("zoomOut")}</button>
      <button class="iconbtn" title="${t('tool.zoomin')}" data-ref="zoom-in" data-feature="zoom.in" data-label="${t('tool.zoomin')}">${icon("zoomIn")}</button>
    </div>
    <div class="tl-scroller" data-ref="scroller">
      <div class="tl-grid" data-ref="grid">
        <div class="tl-corner tl-tools">
      <button class="iconbtn is-accent" title="${t('tool.select')}" data-ref="tool-select" data-feature="tool.select" data-label="${t('tool.select')}">${icon("pointer")}</button>
      <button class="iconbtn" title="${t('tool.blade')}" data-ref="tool-blade" data-feature="tool.blade" data-label="${t('tool.blade')}">${icon("blade")}</button>
      <span class="divider"></span>
      <button class="iconbtn" title="${t('tool.split')}" data-ref="act-split" data-feature="act.split" data-label="${t('tool.split')}">${icon("split")}</button>
      <button class="iconbtn" title="${t('tool.detach')}" data-ref="act-detach" data-feature="act.detach" data-label="${t('tool.detach')}">${icon("detach")}</button>
      <button class="iconbtn" title="${t('tool.ripple')}" data-ref="act-ripple" data-feature="act.ripple" data-label="${t('tool.ripple')}">${icon("ripple")}</button>
      <span class="divider"></span>
      <button class="iconbtn is-accent" title="${t('tool.snap')}" data-ref="snap" data-feature="snap" data-label="${t('tool.snap')}">${icon("magnet")}</button>
        </div>
        <div class="tl-ruler" data-ref="ruler" style="width:${laneW}px">${ruler}<div class="tl-markers" data-ref="markers"></div></div>
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
        <div class="tl-range" data-ref="range" hidden></div>
        <div class="playhead" data-ref="playhead" style="left:${HEAD_W + s.playhead * PX_PER_SEC}px"><button class="playhead-grab" data-ref="playhead-grab" aria-label="Scrub playhead"></button></div>
      </div>
    </div>`;

  const playhead = el.querySelector<HTMLElement>('[data-ref="playhead"]')!;
  const tc = el.querySelector<HTMLElement>('[data-ref="tc"]')!;
  const scroller = el.querySelector<HTMLElement>('[data-ref="scroller"]')!;
  const rulerEl = el.querySelector<HTMLElement>('[data-ref="ruler"]')!;
  const rangeBand = el.querySelector<HTMLElement>('[data-ref="range"]')!;
  const rangeButtons = ["range-extract", "range-lift", "range-clear"].map((ref) => el.querySelector<HTMLButtonElement>(`[data-ref="${ref}"]`)!);
  const paintRange = () => {
    const mark = engine.range && engine.range.timeline === engine.snapshot.activeTimeline ? engine.range : null;
    if (rangeBand.hidden !== !mark) rangeBand.hidden = !mark;
    for (const button of rangeButtons) if (button.disabled !== !mark) button.disabled = !mark;
    if (!mark) return;
    const left = `${HEAD_W + mark.start * PX_PER_SEC}px`;
    const width = `${(mark.end - mark.start) * PX_PER_SEC}px`;
    if (rangeBand.style.left !== left) rangeBand.style.left = left;
    if (rangeBand.style.width !== width) rangeBand.style.width = width;
    const title = `${formatTimecode(mark.start, engine.snapshot.fps)} - ${formatTimecode(mark.end, engine.snapshot.fps)}`;
    if (rangeBand.title !== title) rangeBand.title = title;
  };
  rangeButtons[0].addEventListener("click", () => {
    const mark = engine.range;
    if (mark) engine.dispatch("timeline.cut-range", { start: mark.start, end: mark.end });
  });
  rangeButtons[1].addEventListener("click", () => {
    const mark = engine.range;
    if (mark) engine.dispatch("edit.lift", { start: mark.start, end: mark.end });
  });
  rangeButtons[2].addEventListener("click", () => engine.dispatch("range.clear"));

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

  const markerLayer = el.querySelector<HTMLElement>('[data-ref="markers"]')!;
  const markerNodes = new Map<string, HTMLElement>();
  const paintMarkers = () => {
    const state = engine.snapshot;
    const markers = state.timelines[state.activeTimeline].markers ?? [];
    const wanted = new Set(markers.map((marker) => marker.id));
    for (const [id, node] of markerNodes) if (!wanted.has(id)) markerNodes.delete(id);
    const ordered = markers.map((marker) => {
      let node = markerNodes.get(marker.id);
      if (!node) {
        const made = document.createElement("button");
        made.className = "tl-marker";
        made.type = "button";
        made.dataset.marker = marker.id;
        node = made;
        markerNodes.set(marker.id, node);
      }
      const left = `${marker.t * PX_PER_SEC}px`;
      if (node.style.left !== left) node.style.left = left;
      const colour = marker.colour || "";
      if (node.style.getPropertyValue("--marker") !== colour) node.style.setProperty("--marker", colour);
      const title = marker.note ? `${formatTimecode(marker.t, state.fps)} ${marker.note}` : formatTimecode(marker.t, state.fps);
      if (node.title !== title) node.title = title;
      return node;
    });
    orderNodes(markerLayer, ordered);
    paintKeyDiamonds();
  };
  // Keyframe diamonds on the ruler: one per key on the selected clip, at its
  // timeline instant, so a person scrubbing sees where the keys are without
  // opening the inspector. Patched in place; a node per key by its clip and time.
  const keyNodes = new Map<string, HTMLElement>();
  const paintKeyDiamonds = () => {
    const state = engine.snapshot;
    const found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    const keys = found?.clip.keyframes ?? [];
    const wanted = new Set<string>();
    const ordered: HTMLElement[] = [];
    for (const key of keys) {
      const id = `${found!.clip.id}:${key.t}`;
      wanted.add(id);
      let node = keyNodes.get(id);
      if (!node) {
        const made = document.createElement("span");
        made.className = "tl-key-diamond";
        made.dataset.keyDiamond = id;
        node = made;
        keyNodes.set(id, node);
      }
      const at = found!.clip.start + key.t;
      const left = `${at * PX_PER_SEC}px`;
      if (node.style.left !== left) node.style.left = left;
      const title = `${formatTimecode(at, state.fps)} ${Object.keys(key.props).join(", ")}`;
      if (node.title !== title) node.title = title;
      ordered.push(node);
    }
    for (const [id] of keyNodes) if (!wanted.has(id)) keyNodes.delete(id);
    const existing = Array.from(markerLayer.querySelectorAll<HTMLElement>(".tl-key-diamond"));
    for (const node of existing) if (!wanted.has(node.dataset.keyDiamond!)) node.remove();
    for (const node of ordered) if (node.parentElement !== markerLayer) markerLayer.append(node);
  };
  markerLayer.addEventListener("click", (ev) => {
    const node = (ev.target as HTMLElement).closest<HTMLElement>("[data-marker]");
    if (!node) return;
    ev.stopPropagation();
    if (ev.altKey) { engine.dispatch("marker.remove", { id: node.dataset.marker }); return; }
    const state = engine.snapshot;
    const marker = (state.timelines[state.activeTimeline].markers ?? []).find((entry) => entry.id === node.dataset.marker);
    if (marker) engine.dispatch("transport.seek", marker.t);
  });
  markerLayer.addEventListener("pointerdown", (ev) => { if ((ev.target as HTMLElement).closest("[data-marker]")) ev.stopPropagation(); });
  const reconcile = () => {
    paintMarkers();
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
        node.classList.toggle("is-selected", clip.id === state.selectedClipId || state.selection.includes(clip.id));
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
      paintKeyDiamonds();
      for (const clip of byId.values()) {
        lane.insertAdjacentHTML("beforeend", clipHtml(clip, state.selectedClipId));
        const added = lane.querySelector<HTMLElement>(`.clip[data-clip="${clip.id}"]`);
        if (added) paintClipBody(added, clip, bin);
      }
    }
  };
  const syncSelection = () => {
    const state = engine.snapshot;
    for (const node of el.querySelectorAll<HTMLElement>(".clip")) {
      node.classList.toggle("is-selected", node.dataset.clip === state.selectedClipId || state.selection.includes(node.dataset.clip!));
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
    if (changed === "clips" || changed === "timeline" || changed === "project") { reconcile(); paintRange(); }
    if (changed === "clip-selection") syncSelection();
    if (changed !== "playhead") return;
    playhead.style.left = `${HEAD_W + state.playhead * PX_PER_SEC}px`;
    const next = formatTimecode(state.playhead, state.fps);
    if (tc.textContent !== next) tc.textContent = next;
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
    const points = [0, state.playhead, ...(state.timelines[state.activeTimeline].markers ?? []).map((marker) => marker.t)];
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
    minStart: number;
  };
  let drag: Drag | null = null;

  const marqueeBox = document.createElement("div");
  marqueeBox.className = "tl-marquee";
  marqueeBox.hidden = true;
  scroller.append(marqueeBox);
  const beginMarquee = (ev: PointerEvent) => {
    ev.preventDefault();
    const box = scroller.getBoundingClientRect();
    const origin = { x: ev.clientX - box.left + scroller.scrollLeft, y: ev.clientY - box.top + scroller.scrollTop };
    let moved = false;
    const rect = { left: origin.x, top: origin.y, right: origin.x, bottom: origin.y };
    const paint = () => {
      const left = `${rect.left}px`, top = `${rect.top}px`, width = `${rect.right - rect.left}px`, height = `${rect.bottom - rect.top}px`;
      if (marqueeBox.style.left !== left) marqueeBox.style.left = left;
      if (marqueeBox.style.top !== top) marqueeBox.style.top = top;
      if (marqueeBox.style.width !== width) marqueeBox.style.width = width;
      if (marqueeBox.style.height !== height) marqueeBox.style.height = height;
    };
    const hits = (): string[] => {
      const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
      const ids: string[] = [];
      for (const [trackIndex, lane] of lanes.entries()) {
        if (tracks[trackIndex]?.locked) continue;
        const laneBox = lane.getBoundingClientRect();
        const laneTop = laneBox.top - box.top + scroller.scrollTop;
        const laneBottom = laneTop + laneBox.height;
        if (laneBottom < rect.top || laneTop > rect.bottom) continue;
        for (const clip of tracks[trackIndex].clips) {
          const clipLeft = clip.start * PX_PER_SEC + (laneBox.left - box.left + scroller.scrollLeft);
          const clipRight = clipLeft + clip.duration * PX_PER_SEC;
          if (clipRight >= rect.left && clipLeft <= rect.right) ids.push(clip.id);
        }
      }
      return ids;
    };
    const move = (moveEv: PointerEvent) => {
      const x = moveEv.clientX - box.left + scroller.scrollLeft;
      const y = moveEv.clientY - box.top + scroller.scrollTop;
      if (!moved && Math.hypot(x - origin.x, y - origin.y) < 4) return;
      moved = true;
      if (marqueeBox.hidden) marqueeBox.hidden = false;
      rect.left = Math.min(origin.x, x); rect.right = Math.max(origin.x, x);
      rect.top = Math.min(origin.y, y); rect.bottom = Math.max(origin.y, y);
      paint();
      engine.dispatch("clip.select-set", hits());
    };
    const up = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
      window.removeEventListener("pointercancel", up);
      if (!marqueeBox.hidden) marqueeBox.hidden = true;
      if (!moved) engine.dispatch("clip.select", null);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    window.addEventListener("pointercancel", up);
  };

  scroller.addEventListener("pointerdown", (ev) => {
    const target = ev.target as HTMLElement;
    const node = target.closest<HTMLElement>(".clip");
    if (!node) {
      if (target.closest(".lane") && tool === "select" && ev.button === 0) beginMarquee(ev);
      else if (target.closest(".lane")) engine.dispatch("clip.select", null);
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
    if (ev.shiftKey || ev.metaKey || ev.ctrlKey) {
      engine.dispatch("clip.select-toggle", clipId);
      return;
    }
    if (!engine.snapshot.selection.includes(clipId) || engine.snapshot.selection.length <= 1) engine.dispatch("clip.select", clipId);
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
      minStart: found.clip.kind === "video" || found.clip.kind === "audio" ? found.clip.start - (found.clip.sourceIn ?? 0) / speedAt(found.clip, 0) : 0,
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
      start = Math.max(0, drag.minStart, drag.start + shift);
      if (drag.snapPoints.length > 0) {
        const snapped = snapValue(start, drag.snapPoints);
        if (snapped <= drag.start + drag.duration - 0.1) start = Math.max(0, drag.minStart, snapped);
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
    const dragged = drag;
    drag = null;
    if (!moved) return;
    const start = parseFloat(node.style.left) / PX_PER_SEC;
    const duration = (parseFloat(node.style.width) + 3) / PX_PER_SEC;
    const set = engine.snapshot.selection;
    if (kind === "move" && set.length > 1 && set.includes(clipId)) {
      engine.dispatch("clips.move", { clipIds: set, deltaStart: start - dragged.start, deltaTrack: laneIndex - (engine.findClip(clipId)?.trackIndex ?? laneIndex) });
      reconcile();
      return;
    }
    if (kind === "move") engine.dispatch("clip.move", { clipId, start, trackIndex: laneIndex });
    else engine.dispatch("clip.trim", { clipId, start, duration });
  });

  el.querySelector('[data-ref="act-split"]')!.addEventListener("click", () => {
    const state = engine.snapshot;
    const ids = state.selection.length ? state.selection : state.selectedClipId ? [state.selectedClipId] : [];
    if (ids.length) engine.dispatch("clips.split", { clipIds: ids, time: state.playhead });
  });
  // The clip trash left the toolbar with the redesign; Delete, the Edit menu and
  // the Easy tray all still remove a clip, so the binding is kept optional here.
  el.querySelector('[data-ref="act-delete"]')?.addEventListener("click", () => {
    const state = engine.snapshot;
    if (state.selection.length > 1) engine.dispatch("clips.remove", state.selection);
    else if (state.selectedClipId) engine.dispatch("clip.remove", state.selectedClipId);
  });
  // A clip is a button for the keyboard: Enter or Space selects it (the
  // global keys below then cut, delete or nudge the selection), Left and
  // Right move focus along the track, Up and Down to the clip nearest in time
  // on the neighbouring track. Focus survives a selection because the
  // timeline patches is-selected in place rather than repainting.
  el.addEventListener("keydown", (ev) => {
    const clipNode = (ev.target as HTMLElement).closest<HTMLElement>(".clip[data-clip]");
    if (!clipNode || ev.metaKey || ev.ctrlKey || ev.altKey) return;
    if (ev.key === "Enter" || ev.key === " ") {
      ev.preventDefault();
      ev.stopPropagation();
      engine.dispatch("clip.select", clipNode.dataset.clip!);
      return;
    }
    if (!["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(ev.key)) return;
    ev.preventDefault();
    ev.stopPropagation();
    const lane = clipNode.closest<HTMLElement>(".lane");
    const inLane = (host: HTMLElement | null) => Array.from(host?.querySelectorAll<HTMLElement>(".clip[data-clip]") ?? []).sort((a, b) => parseFloat(a.style.left) - parseFloat(b.style.left));
    if (ev.key === "ArrowLeft" || ev.key === "ArrowRight") {
      const siblings = inLane(lane);
      const at = siblings.indexOf(clipNode);
      const next = siblings[at + (ev.key === "ArrowRight" ? 1 : -1)];
      next?.focus();
      return;
    }
    const allLanes = Array.from(el.querySelectorAll<HTMLElement>(".lane"));
    const laneAt = allLanes.indexOf(lane!);
    const target = allLanes[laneAt + (ev.key === "ArrowDown" ? 1 : -1)];
    if (!target) return;
    const here = parseFloat(clipNode.style.left);
    const nearest = inLane(target).sort((a, b) => Math.abs(parseFloat(a.style.left) - here) - Math.abs(parseFloat(b.style.left) - here))[0];
    nearest?.focus();
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
    if (meta && ev.key.toLowerCase() === "a") {
      ev.preventDefault();
      engine.dispatch("clip.select-all", {});
      return;
    }
    if (!meta && !ev.altKey && ev.key.toLowerCase() === "m") {
      ev.preventDefault();
      engine.dispatch("marker.add", { t: engine.snapshot.playhead });
      return;
    }
    if (ev.key === "Escape" && engine.snapshot.selection.length) {
      engine.dispatch("clip.select", null);
      return;
    }
    if (ev.key === "Delete" || ev.key === "Backspace") {
      const state = engine.snapshot;
      if (state.selection.length > 1) {
        ev.preventDefault();
        engine.dispatch("clips.remove", state.selection);
      } else if (state.selectedClipId) {
        ev.preventDefault();
        engine.dispatch("clip.remove", state.selectedClipId);
      }
    }
  });
  el.dataset.scale = String(PX_PER_SEC);
  // F21: alt and the wheel, or alt and a pinch, zoom the tracks. The moment
  // under the pointer is held still, so zooming feels like moving a lens over
  // the timeline rather than jumping somewhere else.
  const zoomScroller = el.querySelector<HTMLElement>(".tl-scroller");
  zoomScroller?.addEventListener("wheel", (event) => {
    if (!event.altKey && !event.ctrlKey) return;
    event.preventDefault();
    const box = zoomScroller.getBoundingClientRect();
    const before = (zoomScroller.scrollLeft + event.clientX - box.left - HEAD_W) / PX_PER_SEC;
    // A trackpad sends many small deltas, so a fixed 12 percent per event flew
    // past the whole timeline in a flick. The step follows the delta and is
    // capped, and zoom() already clamps the scale itself.
    const magnitude = Math.min(40, Math.abs(event.deltaY));
    const step = event.deltaY > 0 ? 1 - magnitude / 900 : 1 + magnitude / 900;
    zoom(step);
    window.requestAnimationFrame(() => {
      zoomScroller.scrollLeft = Math.max(0, before * PX_PER_SEC + HEAD_W - (event.clientX - box.left));
    });
  }, { passive: false });

  // Beats found in the inspector become snap points here. The event was being
  // dispatched with nothing listening for it, which is a feature that exists
  // and does nothing.
  let beatMarks: number[] = [];
  document.addEventListener("formcut:beats", (event) => {
    const detail = (event as CustomEvent).detail as { start: number; beats: number[] };
    beatMarks = (detail.beats ?? []).map((at) => at + detail.start);
    el.dataset.beats = String(beatMarks.length);
    paintBeats();
  });
  const paintBeats = () => {
    const ruler = el.querySelector<HTMLElement>(".tl-ruler");
    if (!ruler) return;
    for (const old of ruler.querySelectorAll(".tl-beat")) old.remove();
    for (const at of beatMarks) {
      const tick = document.createElement("span");
      tick.className = "tl-beat";
      tick.style.left = `${at * PX_PER_SEC}px`;
      ruler.append(tick);
    }
  };
  // Anything dragged near a beat lands on it.
  (window as unknown as { formcutSnapBeat?: (t: number) => number }).formcutSnapBeat = (time: number) => {
    if (!beatMarks.length) return time;
    const nearest = beatMarks.reduce((best, at) =>
      Math.abs(at - time) < Math.abs(best - time) ? at : best, beatMarks[0]);
    return Math.abs(nearest - time) < 8 / PX_PER_SEC ? nearest : time;
  };

  const tabControls = el.querySelector(".tl-tabs")!;
  tabControls.querySelector<HTMLButtonElement>('[data-ref="tl-add"]')!.addEventListener("click", () => engine.dispatch("timeline.add", {}));
  // Removing a timeline belongs with the tabs it removes, not in the clip tools.
  tabControls.querySelector<HTMLButtonElement>('[data-ref="tl-remove"]')!.addEventListener("click", () => {
    // timeline.remove takes an object; passing a bare number left index
    // undefined and the command threw, so the button did nothing at all.
    if (engine.snapshot.timelines.length > 1) engine.dispatch("timeline.remove", { index: engine.snapshot.activeTimeline });
  });
  // Double-click renames a tab in place. The field keeps the tab's own width and
  // caps what can be typed, so a long name cannot push the strip out of shape.
  const TAB_NAME_LIMIT = 18;
  // Tabs reorder by dragging: the one under the pointer swaps with its
  // neighbour as it passes it, so the order is committed a step at a time and
  // undo walks back through it.
  const strip = tabControls.querySelector<HTMLElement>('[data-ref="tab-strip"]')!;
  strip.addEventListener("pointerdown", (event) => {
    const tab = (event.target as HTMLElement).closest<HTMLElement>(".tl-tab");
    if (!tab || tab.querySelector("input")) return;
    let index = Number(tab.dataset.tl);
    const startX = event.clientX;
    let moved = false;
    const move = (next: PointerEvent) => {
      if (!moved && Math.abs(next.clientX - startX) < 8) return;
      moved = true;
      tab.classList.add("is-dragging");
      const others = [...strip.querySelectorAll<HTMLElement>(".tl-tab")];
      const over = others.find((other) => {
        const box = other.getBoundingClientRect();
        return next.clientX >= box.left && next.clientX <= box.right;
      });
      const target = over ? Number(over.dataset.tl) : index;
      if (target !== index) {
        engine.dispatch("timeline.move", { from: index, to: target });
        index = target;
      }
    };
    const release = () => {
      strip.removeEventListener("pointermove", move);
      tab.classList.remove("is-dragging");
    };
    strip.addEventListener("pointermove", move);
    strip.addEventListener("pointerup", release, { once: true });
    strip.addEventListener("pointercancel", release, { once: true });
  });
  tabControls.addEventListener("dblclick", (event) => {
    const tab = (event.target as HTMLElement).closest<HTMLElement>(".tl-tab");
    if (!tab || tab.querySelector("input")) return;
    const index = Number(tab.dataset.tl);
    const current = engine.snapshot.timelines[index];
    if (!current) return;
    const field = document.createElement("input");
    field.className = "tl-tab-rename";
    field.value = current.name;
    field.maxLength = TAB_NAME_LIMIT;
    tab.textContent = "";
    tab.append(field);
    field.focus();
    field.select();
    const finish = (commit: boolean) => {
      const next = field.value.trim().slice(0, TAB_NAME_LIMIT);
      field.remove();
      tab.textContent = commit && next ? next : current.name;
      if (commit && next && next !== current.name) {
        engine.dispatch("timeline.rename", { index, name: next });
      }
    };
    field.addEventListener("keydown", (key) => {
      key.stopPropagation();
      if (key.key === "Enter") { key.preventDefault(); finish(true); }
      if (key.key === "Escape") { key.preventDefault(); finish(false); }
    });
    field.addEventListener("blur", () => finish(true));
  });
  // The tools and the timeline actions now live in two different rows, so the
  // lookup is scoped to the pane rather than to the row that used to hold both.
  const toolbar = el;
  const control = (ref: string) => toolbar.querySelector<HTMLButtonElement>(`[data-ref="${ref}"]`);
  control("zoom-in")?.addEventListener("click", () => zoom(1.4));
  control("zoom-out")?.addEventListener("click", () => zoom(1 / 1.4));
  control("zoom-fit")?.addEventListener("click", () => zoom((scroller.clientWidth - HEAD_W) / Math.max(1, engine.snapshot.duration) / PX_PER_SEC));
  control("act-add-track")?.addEventListener("click", () => engine.dispatch("track.add", {}));
  scroller.addEventListener("pointercancel", () => { drag = null; reconcile(); });
  reconcile();
  paintRange();
  installTrackKeyframes(el, engine, lanes);
  installWorkArea(el, engine, rulerEl);
  return el;
}
