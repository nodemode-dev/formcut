import type { ProjectEngine } from "../engine/project";
import { text } from "../i18n/text";

const STORE = "formcut.workArea";

export function installWorkArea(root: HTMLElement, engine: ProjectEngine, ruler: HTMLElement): void {
  const bar = document.createElement("div");
  bar.className = "work-area";
  bar.dataset.feature = "workarea";
  bar.hidden = true;
  bar.title = text("Work area: drag the ends, drag the bar to move, double-click to clear");
  bar.innerHTML = `<button class="work-grip" data-edge="start" aria-label="${text("Work area start")}"></button><button class="work-grip" data-edge="end" aria-label="${text("Work area end")}"></button>`;
  ruler.append(bar);
  const scale = () => Number(root.dataset.scale) || 90;
  let area: { start: number; end: number } | null = null;

  const key = () => engine.snapshot.projectId ?? "unsaved";
  const load = (): void => {
    try {
      const raw = localStorage.getItem(STORE);
      const all = raw ? (JSON.parse(raw) as Record<string, { start: number; end: number }>) : {};
      area = all[key()] ?? null;
    } catch {
      area = null;
    }
  };
  const save = (): void => {
    try {
      const raw = localStorage.getItem(STORE);
      const all = raw ? (JSON.parse(raw) as Record<string, { start: number; end: number }>) : {};
      if (area) all[key()] = area;
      else delete all[key()];
      localStorage.setItem(STORE, JSON.stringify(all));
    } catch {
      return;
    }
  };
  const paint = (): void => {
    if (!area) {
      if (!bar.hidden) bar.hidden = true;
      return;
    }
    const left = `${area.start * scale()}px`;
    const width = `${(area.end - area.start) * scale()}px`;
    if (bar.style.left !== left) bar.style.left = left;
    if (bar.style.width !== width) bar.style.width = width;
    if (bar.hidden && bar.dataset.featureOff !== "true") bar.hidden = false;
  };
  const commit = (): void => {
    engine.setWorkArea(area);
    save();
    paint();
  };

  const drag = (event: PointerEvent, mode: "start" | "end" | "move"): void => {
    if (event.button !== 0 || !area) return;
    event.preventDefault();
    event.stopPropagation();
    const from = { ...area };
    const originX = event.clientX;
    const px = scale();
    const min = 0.1;
    const duration = Math.max(engine.snapshot.duration, from.end);
    const move = (moveEvent: PointerEvent) => {
      const delta = (moveEvent.clientX - originX) / px;
      if (mode === "start") area = { start: Math.min(from.end - min, Math.max(0, from.start + delta)), end: from.end };
      else if (mode === "end") area = { start: from.start, end: Math.max(from.start + min, Math.min(duration, from.end + delta)) };
      else {
        const span = from.end - from.start;
        const start = Math.max(0, Math.min(duration - span, from.start + delta));
        area = { start, end: start + span };
      }
      paint();
    };
    const end = () => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      window.removeEventListener("pointercancel", end);
      bar.classList.remove("is-dragging");
      commit();
    };
    bar.classList.add("is-dragging");
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end);
    window.addEventListener("pointercancel", end);
  };

  bar.addEventListener("pointerdown", (event) => {
    const grip = (event.target as HTMLElement).closest<HTMLElement>("[data-edge]");
    drag(event, grip ? (grip.dataset.edge as "start" | "end") : "move");
  });
  bar.addEventListener("dblclick", (event) => {
    event.stopPropagation();
    area = null;
    commit();
  });
  let lastPress = { at: 0, x: 0 };
  root.addEventListener("pointerdown", (event) => {
    const target = event.target as HTMLElement;
    if (event.button !== 0 || target.closest(".work-area") || !target.closest(".tl-ruler, .playhead-grab")) return;
    const twice = event.timeStamp - lastPress.at < 350 && Math.abs(event.clientX - lastPress.x) < 6;
    lastPress = { at: event.timeStamp, x: event.clientX };
    if (!twice) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const state = engine.snapshot;
    const at = (event.clientX - ruler.getBoundingClientRect().left) / scale();
    const half = Math.max(1, Math.min(4, state.duration / 4));
    area = { start: Math.max(0, at - half), end: Math.min(Math.max(state.duration, at + half), at + half) };
    commit();
  }, true);
  window.addEventListener("keydown", (event) => {
    if (event.altKey || event.metaKey || event.ctrlKey) return;
    if (event.key !== "b" && event.key !== "n") return;
    const target = event.target as HTMLElement;
    if (target.closest("input,textarea,select,[contenteditable=true]") || document.querySelector(".modal-scrim:not([hidden]), .set-scrim:not([hidden])")) return;
    const state = engine.snapshot;
    const current = area ?? { start: 0, end: state.duration };
    area = event.key === "b" ? { start: Math.min(state.playhead, current.end - 0.1), end: current.end } : { start: current.start, end: Math.max(state.playhead, current.start + 0.1) };
    commit();
  });

  const observer = new MutationObserver(paint);
  observer.observe(root, { attributes: true, attributeFilter: ["data-scale"] });
  engine.subscribe((_state, changed) => {
    if (changed === "project") {
      load();
      engine.setWorkArea(area);
      paint();
    }
  });
  load();
  engine.setWorkArea(area);
  paint();
}
