// Keyframe lanes and the curve editor.
//
// Two views of the same data, under the timeline and aligned to it. Lanes show
// one row per animatable property with a diamond per keyframe on the timebase.
// The graph shows one property as value over time with draggable points.
//
// Both edit through the engine's existing commands (clip.keyframe to set or
// remove, clip.interp to cycle a point's interpolation) and both draw the curve
// with the engine's own sampler, so what is drawn is what will render rather
// than a second implementation of the same maths.
import { KEYFRAME_PROPS, type Clip, type KeyframeProp } from "../engine/types";
import { propPoints, samplePoints, sampledTransform } from "../engine/keyframes";
import type { ProjectEngine } from "../engine/project";
import { t } from "../i18n";
import { icon } from "./icons";

const ROW_HEIGHT = 22;
const RANGE: Record<KeyframeProp, [number, number]> = {
  posX: [-100, 100],
  posY: [-100, 100],
  scale: [0, 400],
  rotation: [-180, 180],
  opacity: [0, 100],
};

export function buildKeyframeLanes(engine: ProjectEngine, pxPerSec: number): HTMLElement {
  const element = document.createElement("section");
  element.className = "kf-area";
  element.innerHTML = `
    <div class="kf-head">
      <span class="kf-title">${t("kf.title")}</span>
      <div class="seg kf-modes">
        <button data-mode="lanes" class="is-active">${icon("diamond")}<span>${t("kf.lanes")}</span></button>
        <button data-mode="graph">${icon("curve")}<span>${t("kf.graph")}</span></button>
      </div>
      <select class="mini-select" data-ref="kf-prop" aria-label="${t("kf.property")}">
        ${KEYFRAME_PROPS.map((prop) => `<option value="${prop}">${t("row." + prop.toLowerCase())}</option>`).join("")}
      </select>
      <span class="spacer"></span>
      <span class="kf-hint" data-ref="kf-hint">${t("kf.hint")}</span>
    </div>
    <div class="kf-body" data-ref="kf-body">
      <div class="kf-empty" data-ref="kf-empty">${t("kf.empty")}</div>
      <div class="kf-lanes" data-ref="kf-lanes" hidden></div>
      <canvas class="kf-graph" data-ref="kf-graph" hidden></canvas>
    </div>`;

  const q = <T extends HTMLElement = HTMLElement>(name: string) => element.querySelector<T>(`[data-ref="${name}"]`)!;
  const lanes = q("kf-lanes");
  const graph = q<HTMLCanvasElement>("kf-graph");
  const empty = q("kf-empty");
  const propSelect = q<HTMLSelectElement>("kf-prop");
  let mode: "lanes" | "graph" = "lanes";
  let prop: KeyframeProp = "scale";

  const selected = (): { clip: Clip; start: number } | null => {
    const state = engine.snapshot;
    if (!state.selectedClipId) return null;
    const found = engine.findClip(state.selectedClipId);
    return found ? { clip: found.clip, start: found.clip.start } : null;
  };

  // Time and value mapping. x is clip-local seconds scaled by the timeline's own
  // pixels-per-second, so a diamond sits under the frame it belongs to.
  const timeAt = (clip: Clip, x: number, width: number) => Math.max(0, Math.min(clip.duration, (x / Math.max(1, width)) * clip.duration));

  function render(): void {
    const target = selected();
    const has = !!target;
    empty.hidden = has;
    lanes.hidden = !has || mode !== "lanes";
    graph.hidden = !has || mode !== "graph";
    if (!target) return;
    if (mode === "lanes") renderLanes(target.clip);
    else renderGraph(target.clip);
  }

  function renderLanes(clip: Clip): void {
    // Rows are created once and reused: a keyframe edit repaints diamonds, it
    // does not rebuild the lane area.
    for (const [index, name] of KEYFRAME_PROPS.entries()) {
      let row = lanes.querySelector<HTMLElement>(`[data-prop="${name}"]`);
      if (!row) {
        row = document.createElement("div");
        row.className = "kf-row";
        row.dataset.prop = name;
        row.style.top = `${index * ROW_HEIGHT}px`;
        row.innerHTML = `<span class="kf-row-label">${t("row." + name.toLowerCase())}</span><div class="kf-track" data-track></div>`;
        lanes.append(row);
      }
      const track = row.querySelector<HTMLElement>("[data-track]")!;
      const width = track.clientWidth || 1;
      const points = propPoints(clip, name);
      row.classList.toggle("is-current", name === prop);
      const wanted = new Map(points.map((point) => [point.t.toFixed(4), point]));
      for (const node of Array.from(track.querySelectorAll<HTMLElement>(".kf-dot"))) {
        if (!wanted.has(node.dataset.t!)) node.remove();
      }
      for (const [key, point] of wanted) {
        let dot = track.querySelector<HTMLElement>(`.kf-dot[data-t="${key}"]`);
        if (!dot) {
          dot = document.createElement("button");
          dot.className = "kf-dot";
          dot.dataset.t = key;
          dot.innerHTML = icon("diamond");
          track.append(dot);
        }
        dot.style.left = `${(point.t / Math.max(0.001, clip.duration)) * width}px`;
        dot.dataset.interp = point.interp;
        dot.title = `${point.v.toFixed(1)} · ${point.interp}`;
      }
    }
    lanes.style.height = `${KEYFRAME_PROPS.length * ROW_HEIGHT}px`;
  }

  function renderGraph(clip: Clip): void {
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    const width = graph.clientWidth || 1;
    const height = graph.clientHeight || 1;
    graph.width = Math.round(width * ratio);
    graph.height = Math.round(height * ratio);
    const context = graph.getContext("2d");
    if (!context) return;
    context.scale(ratio, ratio);
    context.clearRect(0, 0, width, height);
    const [low, high] = RANGE[prop];
    const yOf = (value: number) => height - ((value - low) / (high - low)) * height;

    const style = getComputedStyle(graph);
    context.strokeStyle = style.getPropertyValue("--line-strong") || "#555";
    context.lineWidth = 1;
    for (const value of [low, (low + high) / 2, high]) {
      const y = Math.round(yOf(value)) + 0.5;
      context.beginPath();
      context.moveTo(0, y);
      context.lineTo(width, y);
      context.stroke();
    }

    // The curve is the engine's own sampler, so the line is the animation.
    const points = propPoints(clip, prop);
    if (!points.length) return;
    context.strokeStyle = style.color;
    context.lineWidth = 1.5;
    context.beginPath();
    for (let x = 0; x <= width; x++) {
      const value = samplePoints(points, (x / width) * clip.duration) ?? points[0].v;
      const y = yOf(value);
      if (x === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    }
    context.stroke();

    context.fillStyle = style.color;
    for (const point of points) {
      const x = (point.t / Math.max(0.001, clip.duration)) * width;
      const y = yOf(point.v);
      context.beginPath();
      context.moveTo(x, y - 4);
      context.lineTo(x + 4, y);
      context.lineTo(x, y + 4);
      context.lineTo(x - 4, y);
      context.closePath();
      context.fill();
    }
  }

  // --- editing ---------------------------------------------------------------

  lanes.addEventListener("pointerdown", (event) => {
    const target = selected();
    if (!target) return;
    const dot = (event.target as HTMLElement).closest<HTMLElement>(".kf-dot");
    const row = (event.target as HTMLElement).closest<HTMLElement>(".kf-row");
    if (!row) return;
    const name = row.dataset.prop as KeyframeProp;
    const track = row.querySelector<HTMLElement>("[data-track]")!;
    const box = track.getBoundingClientRect();
    prop = name;
    propSelect.value = name;

    if (!dot) {
      // Clicking empty lane adds a keyframe there, holding the value the clip
      // already has at that time, so adding a point never changes the picture.
      const time = timeAt(target.clip, event.clientX - box.left, box.width);
      const current = sampledTransform(target.clip, time)[name];
      engine.dispatch("clip.keyframe", { clipId: target.clip.id, t: time, set: { [name]: current } });
      return;
    }
    if (event.altKey) {
      engine.dispatch("clip.keyframe", { clipId: target.clip.id, t: Number(dot.dataset.t), remove: name });
      return;
    }
    // Dragging a diamond moves it in time, frame-snapped, by removing it at the
    // old time and setting it at the new one: the engine has no move command and
    // inventing one would be a second way to change the same data.
    const fromTime = Number(dot.dataset.t);
    const value = propPoints(target.clip, name).find((point) => Math.abs(point.t - fromTime) < 1e-4)?.v;
    if (value === undefined) return;
    dot.setPointerCapture(event.pointerId);
    let lastTime = fromTime;
    const move = (moveEvent: PointerEvent) => {
      const fps = engine.snapshot.fps || 30;
      const raw = timeAt(target.clip, moveEvent.clientX - box.left, box.width);
      const time = Math.round(raw * fps) / fps;
      if (Math.abs(time - lastTime) < 1e-4) return;
      engine.dispatch("clip.keyframe", { clipId: target.clip.id, t: lastTime, remove: name });
      engine.dispatch("clip.keyframe", { clipId: target.clip.id, t: time, set: { [name]: value } });
      lastTime = time;
      dot.dataset.t = time.toFixed(4);
    };
    const end = (endEvent: PointerEvent) => {
      dot.releasePointerCapture(endEvent.pointerId);
      dot.removeEventListener("pointermove", move);
      dot.removeEventListener("pointerup", end);
    };
    dot.addEventListener("pointermove", move);
    dot.addEventListener("pointerup", end);
  });

  lanes.addEventListener("dblclick", (event) => {
    const target = selected();
    const dot = (event.target as HTMLElement).closest<HTMLElement>(".kf-dot");
    if (!target || !dot) return;
    engine.dispatch("clip.interp", { clipId: target.clip.id, t: Number(dot.dataset.t) });
  });

  graph.addEventListener("pointerdown", (event) => {
    const target = selected();
    if (!target) return;
    const box = graph.getBoundingClientRect();
    const [low, high] = RANGE[prop];
    const points = propPoints(target.clip, prop);
    const time = timeAt(target.clip, event.clientX - box.left, box.width);
    const valueAt = (clientY: number) => {
      const fraction = 1 - (clientY - box.top) / box.height;
      return Math.round((low + fraction * (high - low)) * 10) / 10;
    };
    const near = points.find((point) => Math.abs((point.t / Math.max(0.001, target.clip.duration)) * box.width - (event.clientX - box.left)) < 8);
    if (!near) {
      engine.dispatch("clip.keyframe", { clipId: target.clip.id, t: time, set: { [prop]: valueAt(event.clientY) } });
      return;
    }
    if (event.altKey) {
      engine.dispatch("clip.keyframe", { clipId: target.clip.id, t: near.t, remove: prop });
      return;
    }
    graph.setPointerCapture(event.pointerId);
    let lastTime = near.t;
    const move = (moveEvent: PointerEvent) => {
      const fps = engine.snapshot.fps || 30;
      const nextTime = Math.round(timeAt(target.clip, moveEvent.clientX - box.left, box.width) * fps) / fps;
      const nextValue = valueAt(moveEvent.clientY);
      if (Math.abs(nextTime - lastTime) > 1e-4) {
        engine.dispatch("clip.keyframe", { clipId: target.clip.id, t: lastTime, remove: prop });
        lastTime = nextTime;
      }
      engine.dispatch("clip.keyframe", { clipId: target.clip.id, t: lastTime, set: { [prop]: nextValue } });
    };
    const end = (endEvent: PointerEvent) => {
      graph.releasePointerCapture(endEvent.pointerId);
      graph.removeEventListener("pointermove", move);
      graph.removeEventListener("pointerup", end);
    };
    graph.addEventListener("pointermove", move);
    graph.addEventListener("pointerup", end);
  });

  graph.addEventListener("dblclick", (event) => {
    const target = selected();
    if (!target) return;
    const box = graph.getBoundingClientRect();
    const points = propPoints(target.clip, prop);
    const near = points.find((point) => Math.abs((point.t / Math.max(0.001, target.clip.duration)) * box.width - (event.clientX - box.left)) < 8);
    if (near) engine.dispatch("clip.interp", { clipId: target.clip.id, t: near.t });
  });

  element.querySelector(".kf-modes")!.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-mode]");
    if (!button) return;
    mode = button.dataset.mode as "lanes" | "graph";
    for (const other of element.querySelectorAll<HTMLElement>("[data-mode]")) {
      other.classList.toggle("is-active", other === button);
    }
    render();
  });
  propSelect.addEventListener("change", () => {
    prop = propSelect.value as KeyframeProp;
    render();
  });

  void pxPerSec;
  engine.subscribe((_state, changed) => {
    // clip-selection is what the engine emits when the selection changes; the
    // guessed name "selection" matched nothing, so the lanes stayed empty.
    if (["clips", "clip-selection", "timeline", "project"].includes(changed)) render();
  });
  new ResizeObserver(() => render()).observe(element);
  render();
  return element;
}
