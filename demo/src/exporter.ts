import type { ProjectEngine } from "../../frontend/src/engine/project";
import type { Mixer } from "./mixer";
import { toSrt } from "./captions";

export function download(blob: Blob, name: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 4000);
}

const safe = (title: string): string => title.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toLowerCase() || "formcut-demo";

export function exportPng(canvas: HTMLCanvasElement, title: string): Promise<void> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error("The frame could not be encoded"));
        return;
      }
      download(blob, `${safe(title)}.png`);
      resolve();
    }, "image/png");
  });
}

export function exportSrt(engine: ProjectEngine): number {
  const text = toSrt(engine.snapshot);
  if (!text) return 0;
  download(new Blob([text], { type: "text/plain" }), `${safe(engine.snapshot.title)}.srt`);
  return text.split("\n\n").length;
}

export function exportProject(engine: ProjectEngine): void {
  const s = engine.snapshot;
  const doc = { format: "formcut-demo-project", version: 1, title: s.title, width: s.width, height: s.height, fps: s.fps, timelines: s.timelines };
  download(new Blob([JSON.stringify(doc, null, 2)], { type: "application/json" }), `${safe(s.title)}.formcut.json`);
}

export function pickMime(): string | null {
  if (typeof MediaRecorder === "undefined") return null;
  const list = ["video/webm;codecs=vp9,opus", "video/webm;codecs=vp8,opus", "video/webm", "video/mp4"];
  return list.find((type) => MediaRecorder.isTypeSupported(type)) ?? null;
}

export interface RenderControl {
  cancel: () => void;
  done: Promise<Blob | null>;
}

export function renderVideo(engine: ProjectEngine, mixer: Mixer, canvas: HTMLCanvasElement, mime: string, progress: (fraction: number) => void): RenderControl {
  let cancelled = false;
  let stopWatch: () => void = () => {};
  const done = (async () => {
    engine.pause();
    engine.dispatch("transport.home");
    const video = canvas.captureStream(30);
    const stream = new MediaStream([...video.getVideoTracks(), ...mixer.tap.getAudioTracks()]);
    const recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 8_000_000 });
    const chunks: Blob[] = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size) chunks.push(event.data);
    };
    const stopped = new Promise<void>((resolve) => {
      recorder.onstop = () => resolve();
    });
    const wasLooping = engine.looping;
    engine.looping = false;
    const finish = new Promise<void>((resolve) => {
      stopWatch = engine.subscribe((state, changed) => {
        if (changed === "playhead") progress(state.duration > 0 ? state.playhead / state.duration : 0);
        if (changed === "transport" && !state.playing) resolve();
      });
    });
    recorder.start(250);
    engine.play();
    await finish;
    await new Promise((resolve) => window.setTimeout(resolve, 260));
    recorder.stop();
    await stopped;
    stopWatch();
    engine.looping = wasLooping;
    return cancelled ? null : new Blob(chunks, { type: mime.split(";")[0] });
  })();
  return {
    cancel: () => {
      cancelled = true;
      engine.pause();
    },
    done,
  };
}
