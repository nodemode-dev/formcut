import { formatTimecode } from "../../../frontend/src/engine/project";
import type { ProjectEngine } from "../../../frontend/src/engine/project";
import { icon } from "../../../frontend/src/ui/icons";
import { drawDeliver } from "./render";
import type { DeliverMixer } from "./audio";

export interface Preview {
  element: HTMLElement;
  canvas: HTMLCanvasElement;
  setFull: (full: boolean) => void;
  setNote: (text: string) => void;
  setCaptions: (on: boolean) => void;
  redraw: () => void;
}

export function buildPreview(engine: ProjectEngine, mixer: DeliverMixer): Preview {
  const element = document.createElement("section");
  element.className = "pane pane-preview";
  element.innerHTML = `<div class="pane-header"><div class="title">Preview</div><div class="meta" data-ref="meta" dir="ltr"></div>
    <div class="end"><button class="tool-chip" data-ref="guides" aria-pressed="true" title="Show the safe zones for this format">${icon("fit")}Safe zones</button></div></div>
    <div class="stage-wrap"><div class="stage" data-guides="on"><canvas class="render-canvas" aria-label="Preview"></canvas>
    <div class="guides" aria-hidden="true"><span class="guide-top"></span><span class="guide-bottom"></span><span class="guide-title"></span></div>
    <div class="preview-message" role="status"></div></div></div>
    <div class="transport"><span class="tc-field"></span><span class="tc-total"></span><div class="transport-btns">
    <button class="iconbtn" data-act="home" title="Start" aria-label="Start">${icon("toStart")}</button>
    <button class="iconbtn" data-act="back" title="Back half a second" aria-label="Back half a second">${icon("chevL")}</button>
    <button class="iconbtn play" data-act="toggle" title="Play or pause (Space)" aria-label="Play or pause"><span data-play>${icon("play")}</span><span data-pause hidden>${icon("pause")}</span></button>
    <button class="iconbtn" data-act="fwd" title="Forward half a second" aria-label="Forward half a second">${icon("chevR")}</button>
    <button class="iconbtn" data-act="end" title="End" aria-label="End">${icon("toEnd")}</button></div>
    <select class="mini-select" dir="ltr" aria-label="Preview resolution"><option value="0.5">Half</option><option value="1">Full size</option></select></div>`;
  const canvas = element.querySelector<HTMLCanvasElement>("canvas.render-canvas")!;
  const ctx = canvas.getContext("2d", { alpha: false })!;
  const stage = element.querySelector<HTMLElement>(".stage")!;
  const message = element.querySelector<HTMLElement>(".preview-message")!;
  const tc = element.querySelector<HTMLElement>(".tc-field")!;
  const total = element.querySelector<HTMLElement>(".tc-total")!;
  const meta = element.querySelector<HTMLElement>('[data-ref="meta"]')!;
  const playIcon = element.querySelector<HTMLElement>("[data-play]")!;
  const pauseIcon = element.querySelector<HTMLElement>("[data-pause]")!;
  const resolution = element.querySelector("select")!;
  const guidesButton = element.querySelector<HTMLButtonElement>('[data-ref="guides"]')!;
  let scale = 0.5;
  let userScale: number | null = null;
  let pending = false;
  let wasPlaying = false;
  let captions = true;
  let full = false;
  let shape = "";

  const setText = (node: HTMLElement, value: string) => {
    if (node.textContent !== value) node.textContent = value;
  };

  const sizeCanvas = () => {
    const s = engine.snapshot;
    const key = `${s.width}x${s.height}`;
    if (key !== shape) {
      shape = key;
      if (userScale === null) {
        scale = s.height > s.width ? 1 : 0.5;
        resolution.value = String(scale);
      }
    }
    const k = full ? 1 : scale;
    const w = Math.round(s.width * k);
    const h = Math.round(s.height * k);
    if (canvas.width !== w) canvas.width = w;
    if (canvas.height !== h) canvas.height = h;
    const aspect = `${s.width} / ${s.height}`;
    if (stage.style.getPropertyValue("--stage-aspect") !== aspect) stage.style.setProperty("--stage-aspect", aspect);
    const orient = s.height > s.width ? "vertical" : "landscape";
    if (stage.dataset.orient !== orient) stage.dataset.orient = orient;
    setText(meta, `${s.width} x ${s.height} · ${s.fps} fps`);
  };

  const paint = () => {
    pending = false;
    const s = engine.snapshot;
    sizeCanvas();
    mixer.syncVideos(s, s.playhead, s.playing);
    setText(tc, formatTimecode(s.playhead, s.fps));
    setText(total, `/ ${formatTimecode(s.duration, s.fps)}`);
    if (!s.playing && mixer.waiting(s, s.playhead)) return;
    drawDeliver(ctx, s, s.playhead, mixer, captions);
    canvas.dispatchEvent(new Event("frame"));
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
    schedule();
  });

  guidesButton.addEventListener("click", () => {
    const on = stage.dataset.guides !== "on";
    stage.dataset.guides = on ? "on" : "off";
    guidesButton.setAttribute("aria-pressed", String(on));
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
    userScale = Number(resolution.value);
    scale = userScale;
    schedule();
  });
  sizeCanvas();

  return {
    element,
    canvas,
    setFull: (on) => {
      full = on;
      resolution.disabled = on;
      setText(message, on ? "Rendering in real time" : "");
      schedule();
    },
    setNote: (text) => setText(message, text),
    setCaptions: (on) => {
      captions = on;
      schedule();
    },
    redraw: schedule,
  };
}
