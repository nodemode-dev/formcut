import { previewManipulation } from "./preview-manipulation";
import type { ProjectEngine } from "../engine/project";
import { formatTimecode } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { api, waitJob } from "../engine/api";
import { AudioPlayback } from "../engine/audio-playback";
import { icon } from "./icons";

export function buildPreviewPane(engine: ProjectEngine, bin: MediaBin): HTMLElement {
  const element = document.createElement("section");
  element.className = "pane pane-preview";
  element.innerHTML = `<div class="pane-header"><div class="title">Preview</div><div class="meta" data-ref="meta"></div></div>
    <div class="stage-wrap"><div class="stage"><canvas class="render-canvas" aria-label="Video preview"></canvas><div class="preview-message" role="status"></div></div></div>
    <div class="transport"><span class="tc-field"></span><span class="tc-total"></span><div class="transport-btns">
    <button class="iconbtn" data-command="transport.home" title="Start">${icon("toStart")}</button>
    <button class="iconbtn" data-step="-1" title="Previous frame">${icon("stepBack")}</button>
    <button class="iconbtn play" data-command="transport.toggle" title="Play or pause"><span data-play>${icon("play")}</span><span data-pause hidden>${icon("pause")}</span></button>
    <button class="iconbtn" data-step="1" title="Next frame">${icon("stepFwd")}</button>
    <button class="iconbtn" data-command="transport.end" title="End">${icon("toEnd")}</button></div>
    <select class="mini-select" aria-label="Preview resolution"><option value="640">640 px</option><option value="960">960 px</option><option value="0">Full size</option></select></div>`;
  const canvas = element.querySelector("canvas")!;
  const context = canvas.getContext("2d", { alpha: false })!;
  const stage = element.querySelector<HTMLElement>(".stage")!;
  const message = element.querySelector<HTMLElement>(".preview-message")!;
  const tc = element.querySelector<HTMLElement>(".tc-field")!;
  const total = element.querySelector<HTMLElement>(".tc-total")!;
  const meta = element.querySelector<HTMLElement>('[data-ref="meta"]')!;
  const resolution = element.querySelector("select")!;
  const audio = new AudioPlayback((text) => status(text));
  engine.setClockSource(() => audio.position());
  let session = "", revision = 0, readyRevision = -1, busy = false, wanted = true, debounce = 0;
  let lastFrame = -1;
  let streamController: AbortController | undefined;
  let streamFrom = 0, streamStarted = 0, streamRetry = 0;
  const status = (text: string) => { if (message.textContent !== text) message.textContent = text; };
  const clock = () => {
    const s = engine.snapshot;
    const next = formatTimecode(s.playhead, s.fps);
    if (tc.textContent !== next) tc.textContent = next;
    const duration = "/ " + formatTimecode(s.duration, s.fps);
    if (total.textContent !== duration) total.textContent = duration;
    element.querySelector<HTMLElement>("[data-play]")!.hidden = s.playing;
    element.querySelector<HTMLElement>("[data-pause]")!.hidden = !s.playing;
  };
  // Audio follows the transport, and a mix is rendered only when the audio
  // signature changed. An edit that cannot reach the mix leaves playback alone.
  const syncAudio = () => {
    const s = engine.snapshot;
    if (!s.playing) { audio.pause(); return; }
    if (audio.needsMix(s)) { void audio.prepare(s, () => (engine.snapshot.playing ? engine.snapshot.playhead : null)); return; }
    if (audio.ready() && audio.position() === null) audio.play(s.playhead);
  };
  const prepareAudio = async () => {
    const s = engine.snapshot;
    if (audio.needsMix(s)) await audio.prepare(s, () => (engine.snapshot.playing ? engine.snapshot.playhead : null));
    else syncAudio();
  };
  const ensureSession = async (snapshot: typeof engine.snapshot, current: number): Promise<string> => {
    if (readyRevision === current && session) return session;
    const next = await api("/api/render/sessions", { project: snapshot, width: Number(resolution.value) || snapshot.width });
    const old = session;
    session = next.id;
    readyRevision = current;
    if (old && old !== session) await api(`/api/render/sessions/${old}`, undefined, "DELETE").catch(() => {});
    return session;
  };
  const stopStream = () => {
    streamController?.abort();
    streamController = undefined;
  };
  const stream = async (from: number) => {
    stopStream();
    const controller = new AbortController();
    streamController = controller;
    streamFrom = from;
    streamStarted = performance.now();
    const current = revision;
    const snapshot = structuredClone(engine.snapshot);
    try {
      const id = await ensureSession(snapshot, current);
      const response = await fetch(`/api/render/sessions/${id}/stream?start=${from}&fps=${snapshot.fps}`, { signal: controller.signal });
      if (!response.ok || !response.body) throw new Error("Playback stream failed");
      const reader = response.body.getReader();
      let pending = new Uint8Array(0);
      for (;;) {
        const { done, value } = await reader.read();
        if (done || controller.signal.aborted) break;
        const joined = new Uint8Array(pending.length + value.length);
        joined.set(pending);
        joined.set(value, pending.length);
        pending = joined;
        while (pending.length >= 12) {
          const head = new DataView(pending.buffer, pending.byteOffset, 12);
          const size = head.getUint32(0);
          if (pending.length < 12 + size) break;
          const at = head.getFloat64(4);
          const blob = new Blob([pending.slice(12, 12 + size)], { type: "image/jpeg" });
          pending = pending.slice(12 + size);
          const bitmap = await createImageBitmap(blob);
          if (!controller.signal.aborted && current === revision) {
            if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) { canvas.width = bitmap.width; canvas.height = bitmap.height; }
            context.drawImage(bitmap, 0, 0);
            canvas.dataset.revision = String(current);
            canvas.dataset.streamTime = at.toFixed(3);
            lastFrame = -1;
            status("");
          }
          bitmap.close();
        }
      }
    } catch (error) {
      if (!controller.signal.aborted && current === revision) {
        status(error instanceof Error ? error.message : "Playback failed");
        readyRevision = -1;
      }
      if (streamController === controller) {
        streamController = undefined;
        streamRetry = performance.now() + 1500;
      }
    }
  };
  const draw = async () => {
    if (busy || !wanted) return;
    busy = true;
    wanted = false;
    const current = revision;
    const snapshot = structuredClone(engine.snapshot);
    const time = Math.min(snapshot.playhead, Math.max(0, snapshot.duration - 1 / snapshot.fps));
    try {
      if (readyRevision !== current) await ensureSession(snapshot, current);
      const frame = Math.round(time * snapshot.fps);
      if (lastFrame === frame && current === readyRevision && !wanted && canvas.dataset.revision === String(current)) return;
      const response = await fetch(`/api/render/sessions/${session}/frame?time=${time}`);
      if (!response.ok) { const error = await response.json(); throw new Error(error.detail || "Frame render failed"); }
      const bitmap = await createImageBitmap(await response.blob());
      if (current === revision) {
        if (canvas.width !== bitmap.width || canvas.height !== bitmap.height) { canvas.width = bitmap.width; canvas.height = bitmap.height; }
        context.drawImage(bitmap, 0, 0);
        canvas.dataset.revision = String(current);
        lastFrame = frame;
        status("");
      }
      bitmap.close();
    } catch (error) {
      if (current === revision) { status(error instanceof Error ? error.message : "Preview failed"); readyRevision = -1; }
    } finally {
      busy = false;
      if (wanted) void draw();
    }
  };
  const invalidate = () => {
    revision++;
    lastFrame = -1;
    const s = engine.snapshot;
    stage.style.aspectRatio = `${s.width}/${s.height}`;
    stage.style.width = "auto";
    const text = `${s.width} x ${s.height} · ${s.fps} fps`;
    if (meta.textContent !== text) meta.textContent = text;
    window.clearTimeout(debounce);
    debounce = window.setTimeout(() => { if (engine.snapshot.playing) { void stream(engine.snapshot.playhead); void prepareAudio(); } else { wanted = true; void draw(); } }, 120);
    clock();
  };
  element.addEventListener("click", event => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("button");
    if (button?.dataset.command) engine.dispatch(button.dataset.command);
    if (button?.dataset.step) engine.dispatch("transport.step", Number(button.dataset.step));
  });
  resolution.addEventListener("change", invalidate);
  engine.subscribe((_state, changed) => {
    if (["clips", "timeline"].includes(changed)) invalidate();
    if (changed === "playhead") {
      clock();
      const s = engine.snapshot;
      // While audio drives the clock the two agree by construction, so a gap
      // means something moved the playhead: a seek, a scrub or a step. Re-anchor
      // the scheduled source to it rather than letting audio drag it back.
      const at = audio.position();
      if (s.playing && at !== null && Math.abs(at - s.playhead) > 0.25) audio.seek(s.playhead);
      if (!s.playing) { wanted = true; void draw(); }
      else if ((!streamController || Math.abs(s.playhead - (streamFrom + (performance.now() - streamStarted) / 1000)) > 0.35 || (performance.now() - streamStarted > 4000 && s.playhead - Number(canvas.dataset.streamTime ?? s.playhead) > 1.5)) && performance.now() >= streamRetry) void stream(s.playhead);
      // The playhead fires every frame; audio is driven by transport and seek.
    }
    if (changed === "transport") {
      clock();
      if (engine.snapshot.playing) { void prepareAudio(); void stream(engine.snapshot.playhead); }
      else { stopStream(); wanted = true; void draw(); }
      syncAudio();
    }
  });
  bin.subscribe(invalidate);
  // The stage is fitted explicitly rather than left to max-width and
  // max-height: when both clamps bind, the browser trims one dimension without
  // adjusting the other, and the frame stops matching the project's shape. The
  // arithmetic is the same letterbox fit the renderer uses.
  const wrap = stage.parentElement as HTMLElement | null;
  const sizeStage = () => {
    const s = engine.snapshot;
    const ratio = Math.max(1, s.width) / Math.max(1, s.height);
    stage.style.setProperty("--stage-aspect", `${Math.max(1, s.width)} / ${Math.max(1, s.height)}`);
    if (!wrap) return;
    const style = getComputedStyle(wrap);
    const room = {
      width: Math.max(0, wrap.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight)),
      height: Math.max(0, wrap.clientHeight - parseFloat(style.paddingTop) - parseFloat(style.paddingBottom)),
    };
    if (room.width < 2 || room.height < 2) return;
    const scale = Math.min(room.width / ratio, room.height);
    const height = Math.max(1, Math.floor(scale));
    const width = Math.max(1, Math.floor(height * ratio));
    if (stage.style.width !== `${width}px`) stage.style.width = `${width}px`;
    if (stage.style.height !== `${height}px`) stage.style.height = `${height}px`;
  };
  engine.subscribe((_state, event) => { if (event === "project" || event === "timeline") sizeStage(); });
  if (wrap) new ResizeObserver(() => sizeStage()).observe(wrap);
  sizeStage();
  previewManipulation(stage, engine, bin);
  invalidate();
  return element;
}
