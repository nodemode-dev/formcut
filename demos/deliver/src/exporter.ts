import type { ProjectEngine } from "../../../frontend/src/engine/project";
import { download } from "../../../demo/src/exporter";
import { chapterList, chapterVtt, captionsOf, toSrt, toVtt } from "./captions";
import { gainFor, measure, renderMix, toDb, wavOf } from "./audio";
import type { DeliverMixer, Loudness } from "./audio";
import { TARGETS } from "./inspector";
import type { MixApi } from "./inspector";
import type { Preview } from "./preview";

interface Preset {
  id: string;
  name: string;
  detail: string;
  timeline: number;
  target: string;
  kind: "video" | "wav" | "text";
  captions: "burn" | "sidecar";
}

export const PRESETS: Preset[] = [
  { id: "landscape", name: "Landscape 16:9, captions burned in", detail: "WebM, 1280 x 720, Talk timeline, streaming loudness", timeline: 0, target: "stream", kind: "video", captions: "burn" },
  { id: "vertical", name: "Vertical 9:16, captions burned in", detail: "WebM, 540 x 960, Vertical timeline, shorts loudness", timeline: 1, target: "shorts", kind: "video", captions: "burn" },
  { id: "sidecar", name: "Landscape 16:9 with caption file", detail: "WebM without burned captions, plus the .srt beside it", timeline: 0, target: "stream", kind: "video", captions: "sidecar" },
  { id: "broadcast", name: "Audio master, EBU R128", detail: "WAV, 16-bit stereo, -23 LUFS, true peak under -1 dBTP", timeline: 0, target: "ebu", kind: "wav", captions: "sidecar" },
  { id: "text", name: "Captions and chapters", detail: ".srt, .vtt, a chapter list and a chapters .vtt", timeline: 0, target: "stream", kind: "text", captions: "sidecar" },
];

const safe = (title: string): string => title.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "").toLowerCase() || "formcut-deliver";

export interface ExporterHooks {
  mixer: DeliverMixer;
  preview: Preview;
  mix: MixApi;
  activate: (index: number) => void;
  say: (text: string) => void;
  mime: () => string | null;
}

export interface ExporterApi {
  element: HTMLElement;
  open: () => void;
}

export function buildExporter(engine: ProjectEngine, hooks: ExporterHooks): ExporterApi {
  const { mixer, preview, mix, say } = hooks;
  const element = document.createElement("div");
  element.className = "modal-scrim";
  element.hidden = true;
  element.innerHTML = `<div class="modal-panel export-panel" role="dialog" aria-label="Export" aria-modal="true">
    <div class="modal-title">Export</div>
    <div class="dl-presets" data-ref="presets">${PRESETS.map((p, i) => `<button class="dl-preset${i === 0 ? " is-active" : ""}" type="button" data-preset="${p.id}"><b>${p.name}</b><span>${p.detail}</span></button>`).join("")}</div>
    <div class="modal-row export-estimate" data-ref="estimate"></div>
    <div class="dl-progress" data-ref="progress" hidden><span class="dl-bar"><i data-ref="bar"></i></span><span data-ref="progress-text"></span></div>
    <div class="dl-report" data-ref="report" hidden></div>
    <div class="modal-actions"><button class="tool-chip" data-ref="cancel" type="button">Close</button><button class="tool-chip is-primary" data-ref="go" type="button">Export</button></div>
  </div>`;
  const ref = <T extends HTMLElement>(name: string) => element.querySelector<T>(`[data-ref="${name}"]`)!;
  const setText = (node: HTMLElement, value: string) => {
    if (node.textContent !== value) node.textContent = value;
  };
  let current = PRESETS[0];
  let busy = false;
  let cancelled = false;
  let stopRender: () => void = () => {};

  const targetOf = (preset: Preset): [string, number, number] => {
    const found = TARGETS.find(([id]) => id === preset.target) ?? TARGETS[0];
    return [found[1], found[2], found[3]];
  };
  const paintEstimate = () => {
    const [name, goal, ceiling] = targetOf(current);
    const length = engine.snapshot.duration;
    const tl = engine.snapshot.timelines[current.timeline];
    const size = tl.width && tl.height ? `${tl.width} x ${tl.height}` : "";
    setText(ref("estimate"), current.kind === "text" ? `${captionsOf(engine.snapshot, current.timeline).length} captions, ${(tl.markers ?? []).length} chapters` : `${size} · ${length.toFixed(0)} s · ${name}, ceiling ${ceiling} dBTP (${goal} LUFS)`);
  };
  const select = (id: string) => {
    current = PRESETS.find((p) => p.id === id) ?? PRESETS[0];
    element.querySelectorAll<HTMLElement>(".dl-preset").forEach((node) => node.classList.toggle("is-active", node.dataset.preset === current.id));
    ref("report").hidden = true;
    paintEstimate();
  };
  ref("presets").addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-preset]");
    if (button && !busy) select(button.dataset.preset!);
  });

  const progress = (text: string, fraction: number) => {
    ref("progress").hidden = false;
    setText(ref("progress-text"), text);
    const width = `${Math.round(fraction * 100)}%`;
    if (ref("bar").style.width !== width) ref("bar").style.width = width;
  };

  const fit = async (preset: Preset): Promise<Loudness> => {
    const [, goal, ceiling] = targetOf(preset);
    mix.setTarget(preset.target);
    progress("Measuring the mix", 0.02);
    const first = measure(await renderMix(engine.snapshot, engine.snapshot.duration, 1));
    mixer.trim = 10 ** (gainFor(goal, ceiling, first) / 20);
    return measure(await renderMix(engine.snapshot, engine.snapshot.duration, mixer.trim));
  };

  const record = (mime: string): Promise<Blob | null> =>
    new Promise((resolve) => {
      const canvas = preview.canvas;
      engine.pause();
      engine.dispatch("transport.home");
      const stream = new MediaStream([...canvas.captureStream(30).getVideoTracks(), ...mixer.tap.getAudioTracks()]);
      const recorder = new MediaRecorder(stream, { mimeType: mime, videoBitsPerSecond: 6_000_000 });
      const chunks: Blob[] = [];
      recorder.ondataavailable = (event) => {
        if (event.data.size) chunks.push(event.data);
      };
      const looping = engine.looping;
      engine.looping = false;
      let stopWatch: () => void = () => {};
      recorder.onstop = () => {
        stopWatch();
        engine.looping = looping;
        resolve(cancelled ? null : new Blob(chunks, { type: mime.split(";")[0] }));
      };
      stopWatch = engine.subscribe((s, changed) => {
        if (changed === "playhead") progress("Rendering in real time", s.duration > 0 ? 0.1 + 0.88 * (s.playhead / s.duration) : 0);
        if (changed === "transport" && !s.playing) window.setTimeout(() => recorder.stop(), 260);
      });
      stopRender = () => {
        cancelled = true;
        engine.pause();
      };
      recorder.start(250);
      engine.play();
    });

  const row = (label: string, value: string, ok?: boolean): string => `<span>${label}</span><b${ok === undefined ? "" : ` class="${ok ? "is-ok" : "is-bad"}"`}>${value}</b>`;
  const showReport = (lines: string[]) => {
    const box = ref("report");
    box.innerHTML = `<div class="dl-stats">${lines.join("")}</div>`;
    box.hidden = false;
  };

  const run = async () => {
    if (busy) return;
    busy = true;
    cancelled = false;
    const preset = current;
    ref<HTMLButtonElement>("go").disabled = true;
    ref("report").hidden = true;
    const [, goal, ceiling] = targetOf(preset);
    try {
      if (engine.snapshot.activeTimeline !== preset.timeline) hooks.activate(preset.timeline);
      const base = safe(engine.snapshot.title);
      const name = `${base}-${preset.id}`;
      const lines: string[] = [row("Preset", preset.name)];
      if (preset.kind === "text") {
        const clips = captionsOf(engine.snapshot, preset.timeline);
        const marks = engine.snapshot.timelines[preset.timeline].markers ?? [];
        download(new Blob([toSrt(clips)], { type: "text/plain" }), `${name}.srt`);
        download(new Blob([toVtt(clips)], { type: "text/vtt" }), `${name}.vtt`);
        download(new Blob([chapterList(marks)], { type: "text/plain" }), `${name}-chapters.txt`);
        download(new Blob([chapterVtt(marks, engine.snapshot.duration)], { type: "text/vtt" }), `${name}-chapters.vtt`);
        lines.push(row("Captions", `${clips.length} cues in .srt and .vtt`), row("Chapters", `${marks.length} in a list and a .vtt`));
        showReport(lines);
        say("Saved captions and chapters");
        return;
      }
      const loud = await fit(preset);
      const held = loud.truePeak >= ceiling - 0.15 && loud.integrated < goal - 0.5;
      lines.push(row("Integrated", `${loud.integrated.toFixed(1)} LUFS${held ? ` (target ${goal}, held by the ${ceiling} dBTP ceiling)` : ""}`, held || Math.abs(loud.integrated - goal) <= 1), row("True peak", `${loud.truePeak.toFixed(1)} dBTP`, loud.truePeak <= ceiling + 0.05), row("Master trim", `${toDb(mixer.trim).toFixed(1)} dB`));
      if (preset.kind === "wav") {
        progress("Writing the WAV", 0.9);
        const mixdown = await renderMix(engine.snapshot, engine.snapshot.duration, mixer.trim);
        const blob = wavOf(mixdown);
        download(blob, `${name}.wav`);
        lines.push(row("File", `${(blob.size / 1048576).toFixed(1)} MB, 44.1 kHz, 16-bit stereo`), row("Length", `${engine.snapshot.duration.toFixed(1)} s`));
        showReport(lines);
        say("Saved the audio master");
        return;
      }
      const mime = hooks.mime();
      if (!mime) {
        say("This browser has no MediaRecorder with WebM support");
        return;
      }
      preview.setCaptions(preset.captions === "burn");
      preview.setFull(true);
      const blob = await record(mime);
      preview.setFull(false);
      preview.setCaptions(true);
      if (!blob || !blob.size) {
        say("Render cancelled");
        return;
      }
      download(blob, `${name}.webm`);
      const tl = engine.snapshot.timelines[preset.timeline];
      lines.push(row("File", `${(blob.size / 1048576).toFixed(1)} MB WebM, ${tl.width} x ${tl.height}`), row("Length", `${engine.snapshot.duration.toFixed(1)} s`), row("Captions", preset.captions === "burn" ? "burned into the picture" : "left out of the picture"));
      if (preset.captions === "sidecar") {
        const clips = captionsOf(engine.snapshot, preset.timeline);
        download(new Blob([toSrt(clips)], { type: "text/plain" }), `${name}.srt`);
        lines.push(row("Sidecar", `${clips.length} cues in ${name}.srt`));
      }
      showReport(lines);
      say(`Exported ${(blob.size / 1048576).toFixed(1)} MB WebM`);
    } finally {
      busy = false;
      ref<HTMLButtonElement>("go").disabled = false;
      ref("progress").hidden = true;
      preview.setFull(false);
    }
  };

  ref("go").addEventListener("click", () => void run());
  ref("cancel").addEventListener("click", () => {
    if (busy) stopRender();
    else element.hidden = true;
  });
  element.addEventListener("pointerdown", (event) => {
    if (event.target === element && !busy) element.hidden = true;
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !element.hidden) {
      if (busy) stopRender();
      else element.hidden = true;
    }
  });
  paintEstimate();
  return {
    element,
    open: () => {
      element.hidden = false;
      paintEstimate();
    },
  };
}
