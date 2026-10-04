import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import type { Keyframe as ClipKeyframe } from "../engine/types";
import { api } from "../engine/api";
import { sampledTransform } from "../engine/keyframes";
import { icon } from "./icons";
import { t } from "../i18n";

// Focus moves (beyond CapCut 12 of 13): numbered areas drawn on a clip's picture become a camera move, composed by
// the engine (backend/app/focus_motion.py) and applied as the clip's scale, posX and posY keyframes in one replace,
// so it undoes in one step and stays editable. Areas live in the clip's own picture coordinates (0 to 1), mapped to
// the stage the way the preview places the clip (preview-manipulation.ts layerBox).

type Area = [number, number, number, number];
type Speed = "fast" | "medium" | "slow";
const FOCUS_PROPS = ["scale", "posX", "posY"];
const PRESETS: Record<string, { areas: Area[]; speed: Speed; loop: boolean }> = {
  scan: { areas: [[0, 0.15, 0.45, 0.85], [0.55, 0.15, 1, 0.85]], speed: "slow", loop: false },
  down: { areas: [[0.1, 0, 0.9, 0.42], [0.1, 0.58, 0.9, 1]], speed: "slow", loop: false },
  push: { areas: [[0.3, 0.3, 0.7, 0.7]], speed: "slow", loop: false },
  outback: { areas: [[0.3, 0.3, 0.7, 0.7]], speed: "medium", loop: true },
};

export function installFocusMoves(chip: HTMLButtonElement, engine: ProjectEngine, bin: MediaBin): void {
  let session: { close: () => void } | undefined;
  chip.addEventListener("click", () => {
    session?.close();
    session = open(engine, bin, () => { session = undefined; }) ?? undefined;
  });
}

function open(engine: ProjectEngine, bin: MediaBin, closed: () => void): { close: () => void } | null {
  const state = engine.snapshot;
  const clip = state.selectedClipId ? engine.findClip(state.selectedClipId)?.clip : undefined;
  const stage = document.querySelector<HTMLCanvasElement>(".render-canvas")?.parentElement;
  if (!stage) return null;
  if (!clip || (clip.kind !== "video" && clip.kind !== "image")) {
    window.alert(t("focus.needClip"));
    return null;
  }
  const clipId = clip.id;
  engine.pause();
  engine.dispatch("transport.seek", clip.start);
  const areas: Area[] = [];
  let speed: Speed = "medium", loop = false, composed = false, seed = 0;

  /** The clip's picture as stage fractions, as the preview draws it at the playhead. */
  const box = () => {
    const now = engine.snapshot, current = engine.findClip(clipId)?.clip ?? clip;
    const media = current.mediaId ? bin.find(current.mediaId) : null;
    const crop = current.crop ?? {};
    const w = (media?.width || now.width) * (1 - (crop.left ?? 0) - (crop.right ?? 0));
    const h = (media?.height || now.height) * (1 - (crop.top ?? 0) - (crop.bottom ?? 0));
    const fit = Math.min(now.width / w, now.height / h);
    const tr = sampledTransform(current, now.playhead - current.start);
    const fw = ((w * fit) / now.width) * (tr.scale / 100) * (tr.width / 100);
    const fh = ((h * fit) / now.height) * (tr.scale / 100) * (tr.height / 100);
    return { left: 0.5 + tr.posX / 100 - fw / 2, top: 0.5 + tr.posY / 100 - fh / 2, fw, fh, w, h };
  };

  const overlay = document.createElement("div");
  overlay.className = "focus-overlay";
  overlay.setAttribute("aria-label", t("focus.hint"));
  const panel = document.createElement("div");
  panel.className = "focus-panel";
  panel.setAttribute("role", "dialog");
  panel.setAttribute("aria-label", t("focus.title"));
  panel.innerHTML = `
    <div class="focus-head" data-ref="grip"><span class="focus-title">${t("focus.title")}</span><span class="focus-count" data-ref="count"></span>
      <button class="iconbtn" data-ref="reset" title="${t("focus.reset")}" aria-label="${t("focus.reset")}">${icon("reset")}</button>
      <button class="iconbtn" data-ref="done" title="${t("focus.done")}" aria-label="${t("focus.done")}">${icon("close")}</button></div>
    <p class="focus-hint" data-ref="hint">${t("focus.hint")}</p>
    <div class="focus-row"><span>${t("focus.motion")}</span><div class="focus-seg">
      <button data-motion="2d" class="is-on">2D</button><button data-motion="3d" disabled title="${t("focus.only3d")}">3D</button></div></div>
    <div class="focus-row"><span>${t("focus.speed")}</span><div class="focus-seg">
      <button data-speed="fast">${t("focus.fast")}</button><button data-speed="medium" class="is-on">${t("focus.medium")}</button><button data-speed="slow">${t("focus.slow")}</button></div></div>
    <label class="focus-row focus-loop"><input type="checkbox" data-ref="loop" /> ${t("focus.loop")}</label>
    <div class="focus-row"><span>${t("focus.presets")}</span><select data-ref="preset"><option value="">${t("focus.choose")}</option>
      <option value="scan">${t("focus.scan")}</option><option value="down">${t("focus.down")}</option>
      <option value="push">${t("focus.push")}</option><option value="outback">${t("focus.outback")}</option></select></div>
    <button class="focus-primary" data-ref="compose" disabled>${t("focus.compose")}</button>
    <button class="focus-secondary" data-ref="edit" hidden>${t("focus.edit")}</button>`;
  stage.append(overlay, panel);
  const ref = <T extends HTMLElement>(name: string) => panel.querySelector<T>(`[data-ref="${name}"]`)!;
  const shown: HTMLElement[] = [];

  /** Draw the areas, reusing their elements (no rebuild, no flash). */
  const paint = () => {
    const b = box();
    while (shown.length < areas.length) {
      const el = document.createElement("div");
      el.className = "focus-area";
      el.innerHTML = `<span class="focus-badge"></span><button class="focus-delete" aria-label="${t("focus.delete")}">${icon("close")}</button><span class="focus-resize"></span>`;
      overlay.append(el);
      shown.push(el);
    }
    while (shown.length > areas.length) shown.pop()!.remove();
    areas.forEach(([x0, y0, x1, y1], index) => {
      const el = shown[index];
      el.dataset.index = String(index);
      el.style.left = `${(b.left + x0 * b.fw) * 100}%`;
      el.style.top = `${(b.top + y0 * b.fh) * 100}%`;
      el.style.width = `${(x1 - x0) * b.fw * 100}%`;
      el.style.height = `${(y1 - y0) * b.fh * 100}%`;
      const badge = el.querySelector<HTMLElement>(".focus-badge")!;
      if (badge.textContent !== String(index + 1)) badge.textContent = String(index + 1);
    });
    overlay.hidden = composed;
    const count = t("focus.count").replace("{count}", String(areas.length));
    if (ref("count").textContent !== count) ref("count").textContent = count;
    const compose = ref<HTMLButtonElement>("compose");
    compose.disabled = areas.length === 0;
    compose.textContent = composed ? t("focus.shuffle") : t("focus.compose");
    ref("edit").hidden = !composed;
    ref("hint").hidden = !warning && (composed || areas.length > 0);
  };
  let warning = false, warned: number | undefined;
  const warn = () => {
    warning = true;
    ref("hint").classList.add("is-warn");
    paint();
    window.clearTimeout(warned);
    warned = window.setTimeout(() => { warning = false; ref("hint").classList.remove("is-warn"); paint(); }, 2000);
  };

  /** A pointer position as unit coordinates on the clip's picture, clamped to it. */
  const onPicture = (event: PointerEvent): [number, number] => {
    const rect = stage.getBoundingClientRect(), b = box();
    const fx = (event.clientX - rect.left) / rect.width, fy = (event.clientY - rect.top) / rect.height;
    return [Math.min(1, Math.max(0, (fx - b.left) / b.fw)), Math.min(1, Math.max(0, (fy - b.top) / b.fh))];
  };

  overlay.addEventListener("pointerdown", (event) => {
    const target = event.target as HTMLElement, area = target.closest<HTMLElement>(".focus-area");
    if (target.closest(".focus-delete")) {
      areas.splice(Number(area!.dataset.index), 1);
      paint();
      return;
    }
    event.preventDefault();
    overlay.setPointerCapture(event.pointerId);
    const [sx, sy] = onPicture(event);
    const index = area ? Number(area.dataset.index) : areas.push([sx, sy, sx, sy]) - 1;
    const start = [...areas[index]] as Area;
    const mode = !area ? "draw" : target.closest(".focus-resize") ? "resize" : "move";
    const move = (moved: PointerEvent) => {
      const [x, y] = onPicture(moved);
      if (mode === "draw") areas[index] = [Math.min(sx, x), Math.min(sy, y), Math.max(sx, x), Math.max(sy, y)];
      else if (mode === "resize") areas[index] = [start[0], start[1], Math.max(start[0] + 0.02, x), Math.max(start[1] + 0.02, y)];
      else {
        const w = start[2] - start[0], h = start[3] - start[1];
        const x0 = Math.min(1 - w, Math.max(0, start[0] + x - sx)), y0 = Math.min(1 - h, Math.max(0, start[1] + y - sy));
        areas[index] = [x0, y0, x0 + w, y0 + h];
      }
      paint();
    };
    const up = () => {
      overlay.removeEventListener("pointermove", move);
      const [x0, y0, x1, y1] = areas[index];
      if (mode === "draw" && (x1 - x0 < 0.02 || y1 - y0 < 0.02)) {
        // a click, or a drag outside the clip's picture (it clamps to nothing): say where to draw
        areas.splice(index, 1);
        warn();
      }
      paint();
    };
    overlay.addEventListener("pointermove", move);
    overlay.addEventListener("pointerup", up, { once: true });
  });

  const compose = async () => {
    const current = engine.findClip(clipId)?.clip;
    if (!current || areas.length === 0) return;
    const b = box(), now = engine.snapshot;
    if (composed) seed = Math.floor(Math.random() * 1_000_000_000) + 1;
    const button = ref<HTMLButtonElement>("compose");
    button.disabled = true;
    try {
      const made = await api<{ keyframes: ClipKeyframe[] }>("/api/focus-motion", {
        duration: current.duration, canvas: [now.width, now.height], picture: [b.w, b.h], areas,
        base: current.transform, speed, loop, ...(seed ? { seed } : {}),
      });
      const kept = (current.keyframes ?? [])
        .map((frame) => ({ ...frame, props: Object.fromEntries(Object.entries(frame.props).filter(([prop]) => !FOCUS_PROPS.includes(prop))) }))
        .filter((frame) => Object.keys(frame.props).length > 0);
      engine.dispatch("clip.keyframes.replace", { clipId, keyframes: [...kept, ...made.keyframes] as ClipKeyframe[] });
      composed = true;
      engine.dispatch("transport.seek", current.start);
      engine.play();
    } catch (error) {
      window.alert((error as Error).message || t("focus.failed"));
    } finally {
      paint();
    }
  };

  ref("compose").addEventListener("click", () => { void compose(); });
  ref("edit").addEventListener("click", () => { composed = false; engine.pause(); engine.dispatch("transport.seek", clip.start); paint(); });
  ref("reset").addEventListener("click", () => { areas.length = 0; composed = false; seed = 0; paint(); });
  ref<HTMLInputElement>("loop").addEventListener("change", (event) => { loop = (event.target as HTMLInputElement).checked; });
  const pick = (attribute: string, apply: (value: string) => void) => {
    for (const button of panel.querySelectorAll<HTMLButtonElement>(`[data-${attribute}]`)) {
      button.addEventListener("click", () => {
        for (const other of panel.querySelectorAll(`[data-${attribute}]`)) other.classList.toggle("is-on", other === button);
        apply(button.dataset[attribute]!);
      });
    }
  };
  pick("speed", (value) => { speed = value as Speed; });
  ref<HTMLSelectElement>("preset").addEventListener("change", (event) => {
    const chosen = PRESETS[(event.target as HTMLSelectElement).value];
    if (!chosen) return;
    areas.splice(0, areas.length, ...chosen.areas.map((area) => [...area] as Area));
    speed = chosen.speed;
    loop = chosen.loop;
    ref<HTMLInputElement>("loop").checked = loop;
    for (const button of panel.querySelectorAll<HTMLElement>("[data-speed]")) button.classList.toggle("is-on", button.dataset.speed === speed);
    composed = false;
    paint();
  });

  // the panel moves by its header, so it can be put where it does not cover what is being drawn on
  ref("grip").addEventListener("pointerdown", (event) => {
    if ((event.target as HTMLElement).closest("button")) return;
    event.preventDefault();
    const grip = ref("grip");
    grip.setPointerCapture(event.pointerId);
    const bounds = stage.getBoundingClientRect(), from = panel.getBoundingClientRect();
    const dx = event.clientX - from.left, dy = event.clientY - from.top;
    const move = (moved: PointerEvent) => {
      panel.style.left = `${Math.min(bounds.width - from.width, Math.max(0, moved.clientX - bounds.left - dx))}px`;
      panel.style.top = `${Math.min(bounds.height - from.height, Math.max(0, moved.clientY - bounds.top - dy))}px`;
      panel.style.bottom = "auto";
    };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", () => grip.removeEventListener("pointermove", move), { once: true });
  });
  const keys = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
  const relayout = new ResizeObserver(() => paint());
  const close = () => {
    relayout.disconnect();
    document.removeEventListener("keydown", keys);
    overlay.remove();
    panel.remove();
    closed();
  };
  ref("done").addEventListener("click", close);
  document.addEventListener("keydown", keys);
  relayout.observe(stage);
  paint();
  return { close };
}
