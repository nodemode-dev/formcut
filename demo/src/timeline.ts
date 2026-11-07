import { formatTimecode } from "../../frontend/src/engine/project";
import type { ProjectEngine } from "../../frontend/src/engine/project";
import type { Clip } from "../../frontend/src/engine/types";
import { icon } from "../../frontend/src/ui/icons";
import { getSource, onSources, PEAKS_PER_SECOND } from "./media";

const HEAD_W = 248;
const DRAG_MIME = "application/x-formcut-demo-media";

export interface TimelineApi {
  element: HTMLElement;
  split: () => void;
  removeSelected: (ripple: boolean) => void;
  markIn: () => void;
  markOut: () => void;
  setBlade: (on: boolean) => void;
  zoom: (factor: number) => void;
  fit: () => void;
  trackFor: (kind: Clip["kind"]) => number;
  dragMime: string;
}

export function buildTimeline(engine: ProjectEngine, say: (text: string) => void): TimelineApi {
  let pps = 56;
  let blade = false;
  let markedIn: number | null = null;
  const element = document.createElement("section");
  element.className = "pane pane-timeline";
  element.innerHTML = `
    <div class="tl-tabs">
      <div class="tl-tab-strip"><button class="tl-tab is-active" title="Timeline 1">Timeline 1</button></div>
      <span class="divider"></span>
      <button class="tool-chip" data-ref="mark-in" title="Mark in (I)">${icon("range")}Mark in</button>
      <button class="tool-chip" data-ref="mark-out" title="Mark out (O)">Mark out</button>
      <button class="tool-chip" data-ref="range-extract" title="Take the marked span out and close the gap" disabled>Extract</button>
      <button class="tool-chip" data-ref="range-lift" title="Take the marked span out and leave the gap" disabled>Lift</button>
      <button class="iconbtn" data-ref="range-clear" title="Clear the marked span" aria-label="Clear the marked span" disabled>${icon("close")}</button>
      <span class="spacer"></span>
      <span class="tl-tc" data-ref="tc"></span>
      <button class="iconbtn" data-ref="zoom-fit" title="Fit" aria-label="Fit">${icon("fit")}</button>
      <button class="iconbtn" data-ref="zoom-out" title="Zoom out" aria-label="Zoom out">${icon("zoomOut")}</button>
      <button class="iconbtn" data-ref="zoom-in" title="Zoom in" aria-label="Zoom in">${icon("zoomIn")}</button>
    </div>
    <div class="tl-scroller" data-ref="scroller">
      <div class="tl-grid" data-ref="grid">
        <div class="tl-corner tl-tools">
          <button class="iconbtn is-accent" data-ref="tool-select" title="Select (V)" aria-label="Select">${icon("pointer")}</button>
          <button class="iconbtn" data-ref="tool-blade" title="Blade (B)" aria-label="Blade">${icon("blade")}</button>
          <span class="divider"></span>
          <button class="iconbtn" data-ref="act-split" title="Split at the playhead (S)" aria-label="Split">${icon("split")}</button>
          <button class="iconbtn" data-ref="act-ripple" title="Ripple delete (Shift+Delete)" aria-label="Ripple delete">${icon("ripple")}</button>
          <button class="iconbtn" data-ref="act-track" title="Add a track" aria-label="Add a track">${icon("addTrack")}</button>
        </div>
        <div class="tl-ruler" data-ref="ruler"></div>
        <div class="tl-range" data-ref="range" hidden></div>
        <div class="playhead" data-ref="playhead"><button class="playhead-grab" data-ref="grab" aria-label="Scrub playhead"></button></div>
      </div>
    </div>`;
  const ref = <T extends HTMLElement>(name: string) => element.querySelector<T>(`[data-ref="${name}"]`)!;
  const scroller = ref("scroller");
  const grid = ref("grid");
  const ruler = ref("ruler");
  const playhead = ref("playhead");
  const rangeBand = ref("range");
  const tc = ref("tc");
  const toolSelect = ref("tool-select");
  const toolBlade = ref("tool-blade");
  const rangeButtons = ["range-extract", "range-lift", "range-clear"].map((name) => ref<HTMLButtonElement>(name));

  interface Row {
    head: HTMLElement;
    lane: HTMLElement;
    name: HTMLElement;
    clips: Map<string, HTMLElement>;
  }
  const rows: Row[] = [];
  const ticks: HTMLElement[] = [];
  const paintedWave = new WeakMap<HTMLCanvasElement, string>();

  const setStyle = (node: HTMLElement, prop: "left" | "width", value: string) => {
    if (node.style[prop] !== value) node.style[prop] = value;
  };
  const setText = (node: HTMLElement, value: string) => {
    if (node.textContent !== value) node.textContent = value;
  };

  const spanSeconds = () => Math.max(engine.snapshot.duration + 8, 24);

  const syncRuler = () => {
    const span = spanSeconds();
    const step = pps >= 90 ? 1 : pps >= 40 ? 2 : pps >= 22 ? 5 : 10;
    const count = Math.ceil(span / step);
    while (ticks.length < count) {
      const tick = document.createElement("span");
      tick.className = "tick";
      ruler.append(tick);
      ticks.push(tick);
    }
    ticks.forEach((tick, index) => {
      const visible = index < count;
      if (tick.hidden !== !visible) tick.hidden = !visible;
      if (!visible) return;
      setStyle(tick, "left", `${index * step * pps}px`);
      setText(tick, formatTimecode(index * step, engine.snapshot.fps).slice(3, 8));
    });
    const width = `${span * pps}px`;
    setStyle(ruler, "width", width);
    for (const row of rows) setStyle(row.lane, "width", width);
  };

  const ensureRows = () => {
    const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
    while (rows.length < tracks.length) {
      const head = document.createElement("div");
      head.className = "track-head";
      head.innerHTML = `<span class="name"></span>
        <button class="iconbtn" data-track="mute" title="Mute track" aria-label="Mute track">${icon("speaker")}</button>
        <button class="iconbtn" data-track="hide" title="Hide track" aria-label="Hide track">${icon("eye")}</button>`;
      const lane = document.createElement("div");
      lane.className = "lane";
      grid.insertBefore(head, rangeBand);
      grid.insertBefore(lane, rangeBand);
      rows.push({ head, lane, name: head.querySelector(".name")!, clips: new Map() });
    }
    tracks.forEach((track, index) => {
      const row = rows[index];
      row.lane.dataset.track = String(index);
      setText(row.name, track.name);
      const mute = row.head.querySelector<HTMLElement>('[data-track="mute"]')!;
      const hide = row.head.querySelector<HTMLElement>('[data-track="hide"]')!;
      mute.classList.toggle("is-off", !!track.muted);
      hide.classList.toggle("is-off", !!track.hidden);
      mute.dataset.index = String(index);
      hide.dataset.index = String(index);
    });
  };

  const makeClip = (clip: Clip): HTMLElement => {
    const el = document.createElement("div");
    el.className = `clip k-${clip.kind}`;
    el.dataset.clip = clip.id;
    el.tabIndex = 0;
    el.setAttribute("role", "button");
    const compact = clip.kind === "text";
    el.innerHTML = `<div class="bar"></div>${compact ? "" : '<div class="body"></div>'}<span class="clip-badge badge-trans" hidden>${icon("diamond")}</span><span class="clip-badge badge-mute" hidden>M</span><span class="trim trim-l"></span><span class="trim trim-r"></span>`;
    return el;
  };

  const paintWave = (canvas: HTMLCanvasElement, clip: Clip, width: number) => {
    const source = getSource(clip.mediaId);
    if (!source?.peaks) return;
    const key = `${width}:${clip.sourceIn ?? 0}:${clip.duration}:${clip.speed ?? 1}:${source.id}`;
    if (paintedWave.get(canvas) === key) return;
    paintedWave.set(canvas, key);
    const w = Math.max(2, Math.min(3000, Math.round(width)));
    const h = 28;
    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;
    const g = canvas.getContext("2d")!;
    g.clearRect(0, 0, w, h);
    g.fillStyle = getComputedStyle(element).getPropertyValue("--tag-audio").trim() || "white";
    const speed = clip.speed ?? 1;
    const from = (clip.sourceIn ?? 0) * PEAKS_PER_SECOND;
    const span = clip.duration * speed * PEAKS_PER_SECOND;
    for (let x = 0; x < w; x += 2) {
      const index = Math.floor(from + (x / w) * span) % source.peaks.length;
      const peak = Math.min(1, source.peaks[index] * 1.4);
      const bar = Math.max(1, peak * h);
      g.fillRect(x, (h - bar) / 2, 1.5, bar);
    }
  };

  const syncClip = (el: HTMLElement, clip: Clip, selected: boolean) => {
    const left = clip.start * pps;
    const width = Math.max(4, clip.duration * pps - 3);
    setStyle(el, "left", `${left}px`);
    setStyle(el, "width", `${width}px`);
    el.classList.toggle("is-selected", selected);
    setText(el.querySelector<HTMLElement>(".bar")!, clip.label);
    const trans = el.querySelector<HTMLElement>(".badge-trans")!;
    const mute = el.querySelector<HTMLElement>(".badge-mute")!;
    if (trans.hidden !== !clip.transitionIn) trans.hidden = !clip.transitionIn;
    if (mute.hidden !== !clip.muted) mute.hidden = !clip.muted;
    const body = el.querySelector<HTMLElement>(".body");
    if (!body) return;
    const source = getSource(clip.mediaId);
    if (clip.kind === "audio") {
      let canvas = body.querySelector<HTMLCanvasElement>("canvas");
      if (!canvas) {
        canvas = document.createElement("canvas");
        canvas.className = "wave-canvas";
        body.append(canvas);
      }
      paintWave(canvas, clip, width);
    } else if (source?.thumb && body.dataset.thumb !== source.id) {
      body.dataset.thumb = source.id;
      body.style.setProperty("--thumb", `url(${source.thumb})`);
    }
  };

  const reconcile = () => {
    ensureRows();
    const state = engine.snapshot;
    const tracks = state.timelines[state.activeTimeline].tracks;
    const selected = new Set(state.selection);
    tracks.forEach((track, index) => {
      const row = rows[index];
      const seen = new Set<string>();
      for (const clip of track.clips) {
        seen.add(clip.id);
        let el = row.clips.get(clip.id);
        if (!el) {
          el = document.querySelector<HTMLElement>(`.pane-timeline [data-clip="${clip.id}"]`) ?? makeClip(clip);
          row.clips.set(clip.id, el);
        }
        if (el.parentElement !== row.lane) row.lane.append(el);
        syncClip(el, clip, selected.has(clip.id));
      }
      for (const [id, el] of row.clips) {
        if (seen.has(id)) continue;
        if (el.parentElement === row.lane) el.remove();
        row.clips.delete(id);
      }
    });
    syncRuler();
    paintRange();
    paintHead();
  };

  const paintHead = () => {
    const s = engine.snapshot;
    setStyle(playhead, "left", `${HEAD_W + s.playhead * pps}px`);
    setText(tc, formatTimecode(s.playhead, s.fps));
    if (s.playing) {
      const x = s.playhead * pps;
      if (x < scroller.scrollLeft || x > scroller.scrollLeft + scroller.clientWidth - HEAD_W - 40) scroller.scrollLeft = Math.max(0, x - 80);
    }
  };

  const paintRange = () => {
    const mark = engine.range;
    if (rangeBand.hidden !== !mark) rangeBand.hidden = !mark;
    for (const button of rangeButtons) if (button.disabled !== !mark) button.disabled = !mark;
    if (!mark) return;
    setStyle(rangeBand, "left", `${HEAD_W + mark.start * pps}px`);
    setStyle(rangeBand, "width", `${(mark.end - mark.start) * pps}px`);
  };

  const trackFor = (kind: Clip["kind"]): number => {
    const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
    const name = kind === "audio" ? "Audio" : kind === "text" ? "Titles" : kind === "image" ? "Overlay" : "Video";
    const found = tracks.findIndex((track) => track.name === name);
    return found >= 0 ? found : 0;
  };

  const snapPoints = (skip: Set<string>): number[] => {
    const s = engine.snapshot;
    const points = [0, s.playhead];
    for (const track of s.timelines[s.activeTimeline].tracks) {
      for (const clip of track.clips) {
        if (skip.has(clip.id)) continue;
        points.push(clip.start, clip.start + clip.duration);
      }
    }
    return points;
  };
  const snap = (value: number, points: number[]): number => {
    for (const point of points) if (Math.abs(point - value) * pps < 8) return point;
    return value;
  };

  const timeAt = (clientX: number): number => (clientX - scroller.getBoundingClientRect().left + scroller.scrollLeft - HEAD_W) / pps;

  const laneIndexAt = (clientY: number): number => {
    let best = 0;
    rows.forEach((row, index) => {
      if (clientY >= row.lane.getBoundingClientRect().top) best = index;
    });
    return best;
  };

  const scrub = (event: PointerEvent) => {
    engine.dispatch("transport.seek", Math.max(0, timeAt(event.clientX)));
  };

  const track = (index: number) => engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks[index];

  const startMove = (event: PointerEvent, el: HTMLElement) => {
    const id = el.dataset.clip!;
    const found = engine.findClip(id);
    if (!found) return;
    const additive = event.shiftKey || event.metaKey || event.ctrlKey;
    if (additive) engine.dispatch("clip.select-toggle", id);
    else if (!engine.snapshot.selection.includes(id)) engine.dispatch("clip.select", id);
    if (track(found.trackIndex).locked) return;
    const group = engine.snapshot.selection.includes(id) ? engine.snapshot.selection : [id];
    const members = group.map((one) => ({ id: one, el: rows.flatMap((row) => [...row.clips]).find(([key]) => key === one)?.[1], clip: engine.findClip(one) }))
      .filter((m): m is { id: string; el: HTMLElement; clip: NonNullable<ReturnType<typeof engine.findClip>> } => !!m.el && !!m.clip);
    const startX = event.clientX;
    const points = snapPoints(new Set(group));
    const origin = found.clip.start;
    let delta = 0;
    let laneShift = 0;
    let moved = false;
    const rowOfStart = found.trackIndex;
    const onMove = (move: PointerEvent) => {
      if (!moved && Math.abs(move.clientX - startX) < 3 && Math.abs(move.clientY - event.clientY) < 4) return;
      moved = true;
      const raw = origin + (move.clientX - startX) / pps;
      const snapped = Math.max(0, snap(raw, points));
      delta = Math.max(-Math.min(...members.map((m) => m.clip.clip.start)), snapped - origin);
      const target = laneIndexAt(move.clientY);
      const dragKind = found.clip.kind;
      const targetName = track(target)?.name;
      const compatible = dragKind === "audio" ? targetName === "Audio" : targetName !== "Audio";
      laneShift = group.length === 1 && compatible ? target - rowOfStart : 0;
      for (const m of members) {
        setStyle(m.el, "left", `${(m.clip.clip.start + delta) * pps}px`);
        const lane = rows[m.clip.trackIndex + laneShift]?.lane;
        if (lane && m.el.parentElement !== lane) lane.append(m.el);
      }
    };
    const onUp = () => {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      if (!moved) return;
      if (members.length > 1) engine.dispatch("clips.move", { clipIds: group, deltaStart: delta, deltaTrack: 0 });
      else engine.dispatch("clip.move", { clipId: id, start: origin + delta, trackIndex: rowOfStart + laneShift });
      reconcile();
    };
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  };

  const startTrim = (event: PointerEvent, el: HTMLElement, edge: "l" | "r") => {
    const id = el.dataset.clip!;
    const found = engine.findClip(id);
    if (!found || track(found.trackIndex).locked) return;
    engine.dispatch("clip.select", id);
    const clip = found.clip;
    const points = snapPoints(new Set([id]));
    const source = getSource(clip.mediaId);
    const speed = clip.speed ?? 1;
    const bounded = !!source && !source.paint && (clip.kind === "video" || clip.kind === "audio");
    const maxLen = bounded ? Math.max(0.1, (source!.duration - (clip.sourceIn ?? 0)) / speed) : Infinity;
    const minStart = bounded ? Math.max(0, clip.start - (clip.sourceIn ?? 0) / speed) : 0;
    const startX = event.clientX;
    const origin = { start: clip.start, duration: clip.duration };
    let next = { ...origin };
    const onMove = (move: PointerEvent) => {
      const dt = (move.clientX - startX) / pps;
      if (edge === "l") {
        const start = Math.min(origin.start + origin.duration - 0.1, Math.max(minStart, snap(origin.start + dt, points)));
        next = { start, duration: origin.start + origin.duration - start };
      } else {
        const end = snap(origin.start + origin.duration + dt, points);
        next = { start: origin.start, duration: Math.min(maxLen, Math.max(0.1, end - origin.start)) };
      }
      setStyle(el, "left", `${next.start * pps}px`);
      setStyle(el, "width", `${Math.max(4, next.duration * pps - 3)}px`);
    };
    const onUp = () => {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
      if (next.start !== origin.start || next.duration !== origin.duration) engine.dispatch("clip.trim", { clipId: id, start: next.start, duration: next.duration });
      reconcile();
    };
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  };

  const startScrub = (event: PointerEvent) => {
    scrub(event);
    const onMove = (move: PointerEvent) => scrub(move);
    const onUp = () => {
      document.removeEventListener("pointermove", onMove);
      document.removeEventListener("pointerup", onUp);
    };
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onUp);
  };

  grid.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest(".track-head") || target.closest(".tl-corner")) return;
    const clipEl = target.closest<HTMLElement>(".clip");
    if (clipEl) {
      if (blade) {
        const time = timeAt(event.clientX);
        engine.dispatch("clip.split", { clipId: clipEl.dataset.clip, time });
        return;
      }
      const trim = target.closest<HTMLElement>(".trim");
      if (trim) startTrim(event, clipEl, trim.classList.contains("trim-l") ? "l" : "r");
      else startMove(event, clipEl);
      return;
    }
    if (target.closest(".tl-ruler") || target.closest(".playhead-grab")) {
      startScrub(event);
      return;
    }
    if (target.closest(".lane")) {
      engine.dispatch("clip.select", null);
      startScrub(event);
    }
  });

  grid.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-track]");
    if (!button) return;
    const index = Number(button.dataset.index);
    const t = track(index);
    if (!t) return;
    const patch = button.dataset.track === "mute" ? { muted: !t.muted } : { hidden: !t.hidden };
    engine.dispatch("track.update", { index, patch });
  });

  grid.addEventListener("dragover", (event) => {
    if (!event.dataTransfer?.types.includes(DRAG_MIME)) return;
    event.preventDefault();
    const lane = (event.target as HTMLElement).closest<HTMLElement>(".lane");
    for (const row of rows) row.lane.classList.toggle("is-drop", row.lane === lane);
  });
  grid.addEventListener("dragleave", (event) => {
    if (!grid.contains(event.relatedTarget as Node)) for (const row of rows) row.lane.classList.remove("is-drop");
  });
  grid.addEventListener("drop", (event) => {
    const id = event.dataTransfer?.getData(DRAG_MIME);
    for (const row of rows) row.lane.classList.remove("is-drop");
    if (!id) return;
    event.preventDefault();
    const lane = (event.target as HTMLElement).closest<HTMLElement>(".lane");
    document.dispatchEvent(new CustomEvent("formcut-demo:place", { detail: { id, time: Math.max(0, timeAt(event.clientX)), track: lane ? Number(lane.dataset.track) : null } }));
  });

  const split = () => {
    const s = engine.snapshot;
    const tracks = s.timelines[s.activeTimeline].tracks;
    const under = tracks.flatMap((t) => t.clips).filter((c) => s.playhead > c.start + 0.1 && s.playhead < c.start + c.duration - 0.1);
    const picked = under.filter((c) => s.selection.includes(c.id));
    const ids = (picked.length ? picked : under).map((c) => c.id);
    if (!ids.length) {
      say("Move the playhead inside a clip to split it");
      return;
    }
    engine.dispatch("clips.split", { clipIds: ids, time: s.playhead });
  };

  const removeSelected = (ripple: boolean) => {
    const ids = [...engine.snapshot.selection];
    if (!ids.length) return;
    if (ripple) for (const id of ids) engine.dispatch("clip.ripple-delete", { clipId: id });
    else engine.dispatch("clips.remove", ids);
  };

  const markIn = () => {
    markedIn = engine.snapshot.playhead;
    say(`In point at ${formatTimecode(markedIn, engine.snapshot.fps)}`);
  };
  const markOut = () => {
    const out = engine.snapshot.playhead;
    const start = markedIn ?? 0;
    if (out - start < 0.1) {
      say("Mark an in point before the out point");
      return;
    }
    engine.range = { start, end: out, timeline: engine.snapshot.activeTimeline };
    paintRange();
  };

  const setBlade = (on: boolean) => {
    blade = on;
    element.classList.toggle("mode-blade", on);
    toolBlade.classList.toggle("is-accent", on);
    toolSelect.classList.toggle("is-accent", !on);
  };

  const zoom = (factor: number) => {
    pps = Math.max(12, Math.min(360, pps * factor));
    reconcile();
  };
  const fit = () => {
    const room = scroller.clientWidth - HEAD_W - 24;
    pps = Math.max(12, Math.min(200, room / Math.max(2, engine.snapshot.duration)));
    scroller.scrollLeft = 0;
    reconcile();
  };

  ref("mark-in").addEventListener("click", markIn);
  ref("mark-out").addEventListener("click", markOut);
  rangeButtons[0].addEventListener("click", () => {
    const mark = engine.range;
    if (mark) engine.dispatch("timeline.cut-range", { start: mark.start, end: mark.end });
  });
  rangeButtons[1].addEventListener("click", () => {
    const mark = engine.range;
    if (mark) engine.dispatch("edit.lift", { start: mark.start, end: mark.end });
  });
  rangeButtons[2].addEventListener("click", () => {
    engine.dispatch("range.clear");
    paintRange();
  });
  ref("zoom-fit").addEventListener("click", fit);
  ref("zoom-out").addEventListener("click", () => zoom(1 / 1.25));
  ref("zoom-in").addEventListener("click", () => zoom(1.25));
  toolSelect.addEventListener("click", () => setBlade(false));
  toolBlade.addEventListener("click", () => setBlade(true));
  ref("act-split").addEventListener("click", split);
  ref("act-ripple").addEventListener("click", () => removeSelected(true));
  ref("act-track").addEventListener("click", () => engine.dispatch("track.insert", { index: 1, name: `Track ${engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks.length + 1}` }));

  engine.subscribe((_s, changed) => {
    if (changed === "playhead") paintHead();
    else if (changed === "clips" || changed === "timeline" || changed === "clip-selection" || changed === "project") reconcile();
  });
  onSources(() => reconcile());
  reconcile();

  return { element, split, removeSelected, markIn, markOut, setBlade, zoom, fit, trackFor, dragMime: DRAG_MIME };
}
