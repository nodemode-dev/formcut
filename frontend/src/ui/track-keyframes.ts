import { easeAt } from "../engine/timing";
import { KEYFRAME_PROPS, type Clip, type KeyframeProp } from "../engine/types";
import { propPoints, samplePoints, sampledTransform } from "../engine/keyframes";
import type { ProjectEngine } from "../engine/project";
import { t } from "../i18n";
import { icon } from "./icons";

const ROW = 22;
const GRAPH_H = ROW * KEYFRAME_PROPS.length;
const graphHeight = (body: HTMLElement): number => {
  const track = parseFloat(body.style.getPropertyValue("--track-h"));
  const row = Number.isFinite(track) && track > 0 ? Math.min(44, Math.max(18, track * 0.393)) : ROW;
  return Math.round(row * KEYFRAME_PROPS.length);
};
const SVG_NS = "http://www.w3.org/2000/svg";
const RANGE: Record<KeyframeProp, [number, number]> = {
  posX: [-100, 100],
  posY: [-100, 100],
  scale: [0, 400],
  rotation: [-180, 180],
  opacity: [0, 100],
};

type Mode = "lanes" | "graph";
type Point = ReturnType<typeof propPoints>[number];
type Mark = { clip: Clip; point: Point };

interface Block {
  lane: HTMLElement;
  toggle: HTMLButtonElement;
  head: HTMLElement;
  body: HTMLElement;
  labels: HTMLElement;
  select: HTMLSelectElement;
  spans: HTMLElement;
  rows: HTMLElement;
  graph: SVGSVGElement;
  guides: SVGGElement;
  curves: SVGGElement;
  handles: SVGGElement;
  mode: Mode;
  prop: KeyframeProp;
  curved: boolean;
}

const CURVE_STORE = "formcut.kfCurves";
const readCurved = (): boolean => {
  try {
    return localStorage.getItem(CURVE_STORE) !== "off";
  } catch {
    return true;
  }
};
const writeCurved = (on: boolean): void => {
  try {
    localStorage.setItem(CURVE_STORE, on ? "on" : "off");
  } catch {
    return;
  }
};

function patch<E extends Element, T>(parent: Element, items: Array<readonly [string, T]>, make: () => E, update: (node: E, item: T) => void): void {
  const existing = new Map<string, E>();
  for (const node of Array.from(parent.children) as E[]) existing.set(node.getAttribute("data-key") ?? "", node);
  for (const [key, item] of items) {
    let node = existing.get(key);
    if (node) existing.delete(key);
    else {
      node = make();
      node.setAttribute("data-key", key);
      parent.append(node);
    }
    update(node, item);
  }
  for (const stale of existing.values()) stale.remove();
}

function svgNode<K extends keyof SVGElementTagNameMap>(tag: K, className: string): SVGElementTagNameMap[K] {
  const node = document.createElementNS(SVG_NS, tag);
  node.setAttribute("class", className);
  return node;
}

function setAttr(node: Element, name: string, value: string): void {
  if (node.getAttribute(name) !== value) node.setAttribute(name, value);
}

export function installTrackKeyframes(root: HTMLElement, engine: ProjectEngine, lanes: HTMLElement[]): void {
  const blocks = new Map<HTMLElement, Block>();
  const open = new Set<number>();
  const scale = () => Number(root.dataset.scale) || 90;
  const clipsOn = (index: number): Clip[] => {
    const state = engine.snapshot;
    return state.timelines[state.activeTimeline].tracks[index]?.clips ?? [];
  };
  const findClip = (index: number, id: string | null) => clipsOn(index).find((clip) => clip.id === id);
  const clipAt = (index: number, time: number) => clipsOn(index).find((clip) => time >= clip.start && time <= clip.start + clip.duration);
  const localTime = (clip: Clip, seconds: number) => {
    const fps = engine.snapshot.fps || 30;
    return Math.max(0, Math.min(clip.duration, Math.round(seconds * fps) / fps));
  };

  const paintLanes = (block: Block, clips: Clip[], px: number) => {
    for (const row of Array.from(block.rows.children) as HTMLElement[]) {
      const prop = row.dataset.prop as KeyframeProp;
      const marks: Array<readonly [string, Mark]> = [];
      for (const clip of clips) for (const point of propPoints(clip, prop)) marks.push([`${clip.id}|${point.t.toFixed(4)}`, { clip, point }]);
      patch(row, marks, () => {
        const dot = document.createElement("button");
        dot.type = "button";
        dot.className = "kfb-dot";
        dot.innerHTML = icon("diamond");
        return dot;
      }, (dot, { clip, point }) => {
        setAttr(dot, "data-clip", clip.id);
        setAttr(dot, "data-t", point.t.toFixed(4));
        setAttr(dot, "data-interp", point.interp);
        setAttr(dot, "title", `${point.v.toFixed(1)} · ${point.interp}`);
        const left = `${(clip.start + point.t) * px}px`;
        if (dot.style.left !== left) dot.style.left = left;
      });
    }
  };

  const paintGraph = (block: Block, clips: Clip[], px: number) => {
    const width = Math.max(1, parseFloat(block.body.style.width) || block.lane.offsetWidth);
    setAttr(block.graph, "width", String(width));
    const height = graphHeight(block.body);
    if (block.graph.getAttribute("height") !== String(height)) setAttr(block.graph, "height", String(height));
    const [low, high] = RANGE[block.prop];
    const yOf = (value: number) => 4 + (1 - (value - low) / (high - low)) * (height - 8);
    patch(block.guides, [low, (low + high) / 2, high].map((value, i) => [`g${i}`, value] as const), () => svgNode("line", "kfb-guide"), (line, value) => {
      const y = String(Math.round(yOf(value)) + 0.5);
      setAttr(line, "x1", "0");
      setAttr(line, "x2", String(width));
      setAttr(line, "y1", y);
      setAttr(line, "y2", y);
    });
    const animated = clips.map((clip) => ({ clip, points: propPoints(clip, block.prop) })).filter((entry) => entry.points.length > 0);
    patch(block.curves, animated.map((entry) => [entry.clip.id, entry] as const), () => svgNode("path", "kfb-curve"), (path, { clip, points }) => {
      const span = clip.duration * px;
      let d = "";
      if (block.curved) {
        const step = Math.max(2, span / 480);
        for (let x = 0; x <= span + 0.01; x += step) {
          const value = samplePoints(points, Math.min(clip.duration, x / px)) ?? points[0].v;
          d += `${d ? "L" : "M"}${(clip.start * px + x).toFixed(1)} ${yOf(value).toFixed(1)}`;
        }
      } else {
        const sorted = [...points].sort((a, b) => a.t - b.t);
        d = `M${(clip.start * px).toFixed(1)} ${yOf(sorted[0].v).toFixed(1)}`;
        // The lane used to join keyframes with straight lines whatever their
        // easing, so an eased move looked exactly like a linear one. Each
        // segment is now sampled through the same easing the renderer applies.
        for (let index = 0; index < sorted.length; index += 1) {
          const point = sorted[index];
          const previous = sorted[index - 1];
          if (!previous) { d += `L${((clip.start + point.t) * px).toFixed(1)} ${yOf(point.v).toFixed(1)}`; continue; }
          const steps = Math.max(2, Math.min(48, Math.round((point.t - previous.t) * px / 6)));
          for (let step = 1; step <= steps; step += 1) {
            const progress = step / steps;
            const eased = easeAt(progress, previous.interp, previous.handles);
            const time = previous.t + (point.t - previous.t) * progress;
            const value = previous.v + (point.v - previous.v) * eased;
            d += `L${((clip.start + time) * px).toFixed(1)} ${yOf(value).toFixed(1)}`;
          }
        }
        d += `L${((clip.start + clip.duration) * px).toFixed(1)} ${yOf(sorted[sorted.length - 1].v).toFixed(1)}`;
      }
      setAttr(path, "d", d);
      path.classList.toggle("is-linear", !block.curved);
    });
    const marks = animated.flatMap(({ clip, points }) => points.map((point) => [`${clip.id}|${point.t.toFixed(4)}`, { clip, point }] as const));
    patch(block.handles, marks, () => svgNode("path", "kfb-handle"), (handle, { clip, point }) => {
      const x = (clip.start + point.t) * px;
      const y = yOf(point.v);
      setAttr(handle, "d", `M${x.toFixed(1)} ${(y - 4).toFixed(1)}L${(x + 4).toFixed(1)} ${y.toFixed(1)}L${x.toFixed(1)} ${(y + 4).toFixed(1)}L${(x - 4).toFixed(1)} ${y.toFixed(1)}Z`);
      setAttr(handle, "data-clip", clip.id);
      setAttr(handle, "data-t", point.t.toFixed(4));
      setAttr(handle, "data-interp", point.interp);
    });
  };

  const paint = (block: Block) => {
    const index = lanes.indexOf(block.lane);
    if (index < 0 || block.body.hidden) return;
    const px = scale();
    const clips = clipsOn(index);
    patch(block.spans, clips.map((clip) => [clip.id, clip] as const), () => {
      const span = document.createElement("div");
      span.className = "kfb-span";
      return span;
    }, (span, clip) => {
      const left = `${clip.start * px}px`;
      const width = `${Math.max(2, clip.duration * px - 3)}px`;
      if (span.style.left !== left) span.style.left = left;
      if (span.style.width !== width) span.style.width = width;
      if (span.textContent !== clip.label) span.textContent = clip.label;
    });
    if (block.mode === "lanes") paintLanes(block, clips, px);
    else paintGraph(block, clips, px);
  };

  const show = (block: Block) => {
    const shown = open.has(lanes.indexOf(block.lane));
    setAttr(block.toggle, "aria-expanded", String(shown));
    if (block.head.hidden === shown) {
      block.head.hidden = !shown;
      block.body.hidden = !shown;
    }
    if (shown) paint(block);
  };

  const dragAlong = (start: PointerEvent, clip: Clip, from: number, prop: KeyframeProp, value: number, read: (event: PointerEvent) => { t: number; v: number }) => {
    let lastTime = from;
    let lastValue = value;
    const move = (event: PointerEvent) => {
      if (event.pointerId !== start.pointerId) return;
      const next = read(event);
      const time = localTime(clip, next.t);
      const moved = Math.abs(time - lastTime) >= 1e-4;
      if (!moved && next.v === lastValue) return;
      if (moved) engine.dispatch("clip.keyframe", { clipId: clip.id, t: lastTime, remove: prop });
      engine.dispatch("clip.keyframe", { clipId: clip.id, t: time, set: { [prop]: next.v } });
      lastTime = time;
      lastValue = next.v;
    };
    const end = (event: PointerEvent) => {
      if (event.pointerId !== start.pointerId) return;
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
  };

  const wire = (block: Block) => {
    block.toggle.addEventListener("click", () => {
      const index = lanes.indexOf(block.lane);
      if (index < 0) return;
      if (open.has(index)) open.delete(index);
      else open.add(index);
      show(block);
    });
    block.head.querySelector(".kfb-modes")!.addEventListener("click", (event) => {
      const button = (event.target as Element).closest<HTMLButtonElement>("[data-mode]");
      if (!button) return;
      block.mode = button.dataset.mode as Mode;
      for (const other of block.head.querySelectorAll<HTMLElement>("[data-mode]")) other.classList.toggle("is-active", other === button);
      const graphMode = block.mode === "graph";
      block.select.hidden = !graphMode;
      const curvedButton = block.head.querySelector<HTMLButtonElement>("[data-curved]")!;
      curvedButton.hidden = !graphMode;
      curvedButton.setAttribute("aria-pressed", String(block.curved));
      curvedButton.classList.toggle("is-active", block.curved);
      block.labels.hidden = graphMode;
      block.rows.hidden = graphMode;
      block.graph.toggleAttribute("hidden", !graphMode);
      paint(block);
    });
    block.head.querySelector<HTMLButtonElement>("[data-curved]")!.addEventListener("click", (event) => {
      block.curved = !block.curved;
      writeCurved(block.curved);
      const button = event.currentTarget as HTMLButtonElement;
      button.setAttribute("aria-pressed", String(block.curved));
      button.classList.toggle("is-active", block.curved);
      paint(block);
    });
    block.select.addEventListener("change", () => {
      block.prop = block.select.value as KeyframeProp;
      paint(block);
    });
    block.body.addEventListener("pointerdown", (event) => {
      const index = lanes.indexOf(block.lane);
      if (event.button !== 0 || index < 0) return;
      const target = event.target as Element;
      const px = scale();
      const timeAt = (clientX: number) => (clientX - block.body.getBoundingClientRect().left) / px;
      if (block.mode === "lanes") {
        const row = target.closest<HTMLElement>(".kfb-row");
        if (!row) return;
        const prop = row.dataset.prop as KeyframeProp;
        const dot = target.closest<HTMLElement>(".kfb-dot");
        if (!dot) {
          const time = timeAt(event.clientX);
          const clip = clipAt(index, time);
          if (!clip) return;
          const local = localTime(clip, time - clip.start);
          engine.dispatch("clip.keyframe", { clipId: clip.id, t: local, set: { [prop]: sampledTransform(clip, local)[prop] } });
          return;
        }
        const clip = findClip(index, dot.getAttribute("data-clip"));
        if (!clip) return;
        const from = Number(dot.getAttribute("data-t"));
        if (event.altKey) {
          engine.dispatch("clip.keyframe", { clipId: clip.id, t: from, remove: prop });
          return;
        }
        const value = propPoints(clip, prop).find((point) => Math.abs(point.t - from) < 1e-4)?.v;
        if (value === undefined) return;
        dragAlong(event, clip, from, prop, value, (moveEvent) => ({ t: timeAt(moveEvent.clientX) - clip.start, v: value }));
        return;
      }
      if (!target.closest(".kfb-graph")) return;
      const [low, high] = RANGE[block.prop];
      const valueAt = (clientY: number) => {
        const box = block.graph.getBoundingClientRect();
        const fraction = 1 - (clientY - box.top - 4) / (graphHeight(block.body) - 8);
        return Math.round(Math.max(low, Math.min(high, low + fraction * (high - low))) * 10) / 10;
      };
      const handle = target.closest(".kfb-handle");
      if (!handle) {
        const time = timeAt(event.clientX);
        const clip = clipAt(index, time);
        if (!clip) return;
        engine.dispatch("clip.keyframe", { clipId: clip.id, t: localTime(clip, time - clip.start), set: { [block.prop]: valueAt(event.clientY) } });
        return;
      }
      const clip = findClip(index, handle.getAttribute("data-clip"));
      if (!clip) return;
      const from = Number(handle.getAttribute("data-t"));
      if (event.altKey) {
        engine.dispatch("clip.keyframe", { clipId: clip.id, t: from, remove: block.prop });
        return;
      }
      const value = propPoints(clip, block.prop).find((point) => Math.abs(point.t - from) < 1e-4)?.v;
      if (value === undefined) return;
      dragAlong(event, clip, from, block.prop, value, (moveEvent) => ({ t: timeAt(moveEvent.clientX) - clip.start, v: valueAt(moveEvent.clientY) }));
    });
    block.body.addEventListener("dblclick", (event) => {
      const index = lanes.indexOf(block.lane);
      const mark = (event.target as Element).closest(".kfb-dot, .kfb-handle");
      const clip = mark && index >= 0 ? findClip(index, mark.getAttribute("data-clip")) : undefined;
      if (mark && clip) engine.dispatch("clip.interp", { clipId: clip.id, t: Number(mark.getAttribute("data-t")) });
    });
    block.body.addEventListener("keydown", (event) => {
      if (event.key !== "Delete" && event.key !== "Backspace") return;
      const dot = (event.target as Element).closest<HTMLElement>(".kfb-dot");
      const row = dot?.closest<HTMLElement>(".kfb-row");
      const index = lanes.indexOf(block.lane);
      const clip = dot && index >= 0 ? findClip(index, dot.getAttribute("data-clip")) : undefined;
      if (!dot || !row || !clip) return;
      event.preventDefault();
      event.stopPropagation();
      engine.dispatch("clip.keyframe", { clipId: clip.id, t: Number(dot.getAttribute("data-t")), remove: row.dataset.prop as KeyframeProp });
    });
  };

  const create = (lane: HTMLElement): Block => {
    const label = (prop: KeyframeProp) => t("row." + prop.toLowerCase());
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "iconbtn kfb-toggle";
    toggle.dataset.feature = "kf.toggle";
    toggle.title = t("kf.title");
    toggle.setAttribute("aria-label", t("kf.title"));
    toggle.setAttribute("aria-expanded", "false");
    toggle.innerHTML = icon("diamond");
    const head = document.createElement("div");
    head.className = "kfb-head";
    head.hidden = true;
    head.innerHTML = `
      <div class="kfb-bar">
        <div class="seg kfb-modes">
          <button type="button" data-mode="lanes" class="is-active" title="${t("kf.lanes")}" aria-label="${t("kf.lanes")}">${icon("diamond")}</button>
          <button type="button" data-mode="graph" title="${t("kf.graph")}" aria-label="${t("kf.graph")}">${icon("curve")}</button>
        </div>
        <select class="mini-select" aria-label="${t("kf.property")}" hidden>${KEYFRAME_PROPS.map((prop) => `<option value="${prop}">${label(prop)}</option>`).join("")}</select>
        <button type="button" class="iconbtn kfb-curved" data-curved title="${t("kf.curves")}" aria-label="${t("kf.curves")}" aria-pressed="true" hidden>${icon("activity")}</button>
      </div>
      <div class="kfb-labels">${KEYFRAME_PROPS.map((prop) => `<span>${label(prop)}</span>`).join("")}</div>`;
    const body = document.createElement("div");
    body.className = "kfb-body";
    body.hidden = true;
    body.title = t("kf.hint");
    body.innerHTML = `<div class="kfb-spans"></div><div class="kfb-rows">${KEYFRAME_PROPS.map((prop) => `<div class="kfb-row" data-prop="${prop}"></div>`).join("")}</div>`;
    const graph = svgNode("svg", "kfb-graph");
    graph.setAttribute("height", String(GRAPH_H));
    graph.toggleAttribute("hidden", true);
    const guides = svgNode("g", "kfb-guides");
    const curves = svgNode("g", "kfb-curves");
    const handles = svgNode("g", "kfb-handles");
    graph.append(guides, curves, handles);
    body.append(graph);
    const select = head.querySelector<HTMLSelectElement>("select")!;
    select.value = "scale";
    lane.previousElementSibling?.append(toggle);
    lane.after(head, body);
    const trackHeight = lane.style.getPropertyValue("--track-h");
    if (trackHeight) { head.style.setProperty("--track-h", trackHeight); body.style.setProperty("--track-h", trackHeight); }
    const block: Block = {
      lane, toggle, head, body, select, graph, guides, curves, handles,
      labels: head.querySelector<HTMLElement>(".kfb-labels")!,
      spans: body.querySelector<HTMLElement>(".kfb-spans")!,
      rows: body.querySelector<HTMLElement>(".kfb-rows")!,
      mode: "lanes",
      prop: "scale",
      curved: readCurved(),
    };
    wire(block);
    return block;
  };

  const sync = () => {
    for (const [lane, block] of blocks) {
      if (lanes.includes(lane)) continue;
      block.head.remove();
      block.body.remove();
      block.toggle.remove();
      blocks.delete(lane);
    }
    for (const index of Array.from(open)) if (index >= lanes.length) open.delete(index);
    for (const lane of lanes) {
      let block = blocks.get(lane);
      if (!block) {
        block = create(lane);
        blocks.set(lane, block);
      }
      if (lane.style.width && block.body.style.width !== lane.style.width) block.body.style.width = lane.style.width;
      show(block);
    }
  };

  engine.subscribe((_state, changed) => {
    if (changed === "clips" || changed === "timeline" || changed === "project") sync();
  });
  new MutationObserver(() => {
    for (const [lane, block] of blocks) {
      if (lane.style.width && block.body.style.width !== lane.style.width) block.body.style.width = lane.style.width;
      paint(block);
    }
  }).observe(root, { attributes: true, attributeFilter: ["data-scale"] });
  root.addEventListener("formcut:track-height", (event) => {
    const block = blocks.get(event.target as HTMLElement);
    if (block && block.mode === "graph" && !block.body.hidden) paint(block);
  });
  sync();
}
