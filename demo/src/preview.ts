import { formatTimecode } from "../../frontend/src/engine/project";
import type { ProjectEngine } from "../../frontend/src/engine/project";
import { icon } from "../../frontend/src/ui/icons";
import { drawFrame } from "./render";
import type { Mixer } from "./mixer";
import type { LumaScope } from "./scope";

export interface Preview {
  element: HTMLElement;
  canvas: HTMLCanvasElement;
  setFull: (full: boolean) => void;
  setNote: (text: string) => void;
  redraw: () => void;
}

export function buildPreview(engine: ProjectEngine, mixer: Mixer, scope: LumaScope): Preview {
  const element = document.createElement("section");
  element.className = "pane pane-preview";
  element.innerHTML = `<div class="pane-header"><div class="title">Preview</div><div class="meta" data-ref="meta" dir="ltr"></div><div class="end"></div></div>
    <div class="stage-wrap"><div class="stage"><canvas class="render-canvas" aria-label="Video preview"></canvas><div class="preview-message" role="status"></div></div></div>
    <div class="transport"><span class="tc-field"></span><span class="tc-total"></span><div class="transport-btns">
    <button class="iconbtn" data-act="home" title="Start" aria-label="Start">${icon("toStart")}</button>
    <button class="iconbtn" data-act="back" title="Back half a second" aria-label="Back half a second">${icon("chevL")}</button>
    <button class="iconbtn play" data-act="toggle" title="Play or pause (Space)" aria-label="Play or pause"><span data-play>${icon("play")}</span><span data-pause hidden>${icon("pause")}</span></button>
    <button class="iconbtn" data-act="fwd" title="Forward half a second" aria-label="Forward half a second">${icon("chevR")}</button>
    <button class="iconbtn" data-act="end" title="End" aria-label="End">${icon("toEnd")}</button></div>
    <select class="mini-select" dir="ltr" aria-label="Preview resolution"><option value="0.5" selected>Half</option><option value="1">Full size</option></select></div>`;
  const canvas = element.querySelector("canvas")!;
  const ctx = canvas.getContext("2d", { alpha: false })!;
  const stage = element.querySelector<HTMLElement>(".stage")!;
  const message = element.querySelector<HTMLElement>(".preview-message")!;
  const tc = element.querySelector<HTMLElement>(".tc-field")!;
  const total = element.querySelector<HTMLElement>(".tc-total")!;
  const meta = element.querySelector<HTMLElement>('[data-ref="meta"]')!;
  const playIcon = element.querySelector<HTMLElement>("[data-play]")!;
  const pauseIcon = element.querySelector<HTMLElement>("[data-pause]")!;
  const resolution = element.querySelector("select")!;
  let scale = 0.5;
  let pending = false;
  let wasPlaying = false;
  let scopeForce = true;

  const setText = (node: HTMLElement, value: string) => {
    if (node.textContent !== value) node.textContent = value;
  };

  const sizeCanvas = () => {
    const s = engine.snapshot;
    const w = Math.round(s.width * scale);
    const h = Math.round(s.height * scale);
    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;
    const aspect = `${s.width} / ${s.height}`;
    if (stage.style.getPropertyValue("--stage-aspect") !== aspect) stage.style.setProperty("--stage-aspect", aspect);
    setText(meta, `${s.width} x ${s.height} · ${s.fps} fps`);
  };

  const paint = () => {
    pending = false;
    const s = engine.snapshot;
    sizeCanvas();
    mixer.syncVideos(s, s.playhead, s.playing);
    drawFrame(ctx, s, s.playhead, mixer);
    scope.update(canvas, scopeForce || !s.playing);
    scopeForce = false;
    const next = formatTimecode(s.playhead, s.fps);
    setText(tc, next);
    setText(total, `/ ${formatTimecode(s.duration, s.fps)}`);
    if (s.playing) schedule();
  };

  const schedule = () => {
    if (pending) return;
    pending = true;
    requestAnimationFrame(paint);
  };

  mixer.onFrame = schedule;

  const syncAudio = (changedClips: boolean) => {
    const s = engine.snapshot;
    if (!s.playing) {
      if (wasPlaying) mixer.stop();
      wasPlaying = false;
      return;
    }
    const at = mixer.position();
    const drift = at === null ? 0 : Math.abs(at - s.playhead);
    if (!wasPlaying || drift > 0.35 || (changedClips && mixer.changed(s))) {
      wasPlaying = true;
      void mixer.start(s, s.playhead);
    }
  };

  engine.setClockSource(() => mixer.position());
  engine.subscribe((s, changed) => {
    if (changed === "transport") {
      const playing = s.playing;
      if (playIcon.hidden !== playing) playIcon.hidden = playing;
      if (pauseIcon.hidden !== !playing) pauseIcon.hidden = !playing;
      if (playing && wasPlaying) wasPlaying = false;
      syncAudio(false);
    } else if (changed === "playhead") {
      if (s.playing) syncAudio(false);
    } else if (changed === "clips") {
      syncAudio(true);
    }
    scopeForce = true;
    schedule();
  });

  element.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-act]");
    if (!button) return;
    const act = button.dataset.act;
    if (act === "toggle") engine.dispatch("transport.toggle");
    else if (act === "home") engine.dispatch("transport.home");
    else if (act === "end") engine.dispatch("transport.end");
    else if (act === "back") engine.dispatch("transport.skip", -0.5);
    else if (act === "fwd") engine.dispatch("transport.skip", 0.5);
  });
  resolution.addEventListener("change", () => {
    scale = Number(resolution.value);
    schedule();
  });
  sizeCanvas();

  return {
    element,
    canvas,
    setFull: (full) => {
      scale = full ? 1 : Number(resolution.value);
      resolution.disabled = full;
      setText(message, full ? "Rendering to WebM in real time" : "");
      schedule();
    },
    setNote: (text) => setText(message, text),
    redraw: schedule,
  };
}
