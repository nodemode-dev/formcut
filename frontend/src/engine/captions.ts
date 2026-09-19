// Audio preparation for transcription: decode, take one channel, slice the
// clip's own source range, then resample linearly to the 16 kHz the model wants.
import { sourceTime } from "./timing";
import { timelineTime } from "./coordinates";
import type { ProjectEngine } from "./project";
import { fileUrl, type MediaBin } from "./media";
import { defaultTextStyle, defaultTransform, type Clip, type TextStyle } from "./types";
import { t } from "../i18n";

export interface CaptionChunk {
  text: string;
  start: number;
  end: number;
}

function resampleTo16k(buffer: AudioBuffer): Float32Array {
  const source = buffer.getChannelData(0);
  if (buffer.sampleRate === 16000) return Float32Array.from(source);
  const ratio = buffer.sampleRate / 16000;
  const out = new Float32Array(Math.floor(source.length / ratio));
  for (let i = 0; i < out.length; i += 1) {
    const src = i * ratio;
    const floor = Math.floor(src);
    const ceil = Math.min(floor + 1, source.length - 1);
    const t = src - floor;
    out[i] = source[floor] * (1 - t) + source[ceil] * t;
  }
  return out;
}

export interface CaptionOptions {
  language?: "en" | "auto";
  size?: "tiny" | "base" | "small";
  placement?: "top" | "centre" | "bottom";
  scale?: "small" | "medium" | "large";
  style?: Partial<TextStyle>;
  wordsPerCaption?: number;
  signal?: AbortSignal;
}

/** Placement and size turn into the transform and text size the captions use. */
export function captionLook(options: CaptionOptions): { posY: number; size: number } {
  const posY = options.placement === "top" ? -35 : options.placement === "centre" ? 0 : 35;
  const size = options.scale === "small" ? 4 : options.scale === "large" ? 7 : 5;
  return { posY, size };
}

/** Split chunks so no caption carries more than the chosen number of words. */
export function limitWords(chunks: CaptionChunk[], words?: number): CaptionChunk[] {
  if (!words || words < 1) return chunks;
  const out: CaptionChunk[] = [];
  for (const chunk of chunks) {
    const parts = chunk.text.trim().split(/\s+/).filter(Boolean);
    if (parts.length <= words) { out.push(chunk); continue; }
    const groups = Math.ceil(parts.length / words);
    const span = (chunk.end - chunk.start) / groups;
    for (let i = 0; i < groups; i += 1) {
      out.push({
        text: parts.slice(i * words, (i + 1) * words).join(" "),
        start: chunk.start + span * i,
        end: chunk.start + span * (i + 1),
      });
    }
  }
  return out;
}

export async function transcribeClip(
  engine: ProjectEngine,
  bin: MediaBin,
  clipId: string,
  onStatus: (message: string) => void,
  language: "en" | "auto" = "en",
  trackIndex = 0,
  options: CaptionOptions = {},
): Promise<number> {
  const found = engine.findClip(clipId);
  const media = found?.clip.mediaId ? bin.find(found.clip.mediaId) : null;
  if (!found || !media || (found.clip.kind !== "video" && found.clip.kind !== "audio")) {
    onStatus(t("cap.needmedia"));
    return 0;
  }
  const clip = structuredClone(found.clip);
  const timelineId = engine.snapshot.timelines[engine.snapshot.activeTimeline].id;
  onStatus(t("cap.decoding"));
  const bytes = await (await fetch(fileUrl(media.id))).arrayBuffer();
  const ctx = new AudioContext();
  let decoded: AudioBuffer;
  try {
    decoded = await ctx.decodeAudioData(bytes);
  } catch {
    onStatus(t("cap.nodecode"));
    void ctx.close();
    return 0;
  }
  void ctx.close();
  const sr = decoded.sampleRate;
  const startSample = Math.floor(sourceTime(clip, 0) * sr);
  const endSample = Math.min(decoded.length, Math.ceil(sourceTime(clip, clip.duration) * sr));
  if (endSample <= startSample) { onStatus("No audio in the selected range"); return 0; }
  const channel = decoded.getChannelData(0).subarray(startSample, endSample);
  const mono = new AudioBuffer({ length: channel.length, sampleRate: sr, numberOfChannels: 1 });
  mono.copyToChannel(Float32Array.from(channel), 0);
  const audio = resampleTo16k(mono);

  const chunks: CaptionChunk[] = await new Promise<CaptionChunk[]>((resolve, reject) => {
    const worker = new Worker(new URL("../workers/transcription.ts", import.meta.url), {
      type: "module",
    });
    worker.onerror = event => { worker.terminate(); reject(new Error(event.message || "Transcription worker failed")); };
    worker.onmessage = (ev: MessageEvent<{ type: string; message?: string; chunks?: CaptionChunk[]; device?: string; model?: string }>) => {
      if (ev.data.type === "progress") onStatus(ev.data.message ?? "Working");
      if (ev.data.type === "device") onStatus(`${ev.data.device === "webgpu" ? "WebGPU" : "WASM"}: ${ev.data.model ?? ""}`);
      if (ev.data.type === "result") {
        worker.terminate();
        resolve(ev.data.chunks ?? []);
      }
      if (ev.data.type === "error") {
        worker.terminate();
        reject(new Error(ev.data.message));
      }
    };
    options.signal?.addEventListener("abort", () => { worker.terminate(); reject(new Error("cancelled")); }, { once: true });
    worker.postMessage({ audio, language, size: options.size ?? "tiny" }, [audio.buffer]);
  });

  if (chunks.length === 0) {
    onStatus(t("cap.nospeech"));
    return 0;
  }
  const look = captionLook(options);
  const captions: Clip[] = limitWords(chunks, options.wordsPerCaption).map((chunk, n) => {
    const start = clip.start + timelineTime(clip, sourceTime(clip, 0) + chunk.start);
    const end = clip.start + timelineTime(clip, sourceTime(clip, 0) + chunk.end);
    return {
      id: `cap${Date.now()}${n}`,
      kind: "text",
      label: chunk.text,
      start: Math.round(start * 100) / 100,
      duration: Math.max(1 / engine.snapshot.fps, end - start),
      textStyle: { ...defaultTextStyle(chunk.text), size: look.size, ...(options.style ?? {}), content: chunk.text },
      transform: { ...defaultTransform(), posY: look.posY },
    };
  });
  if (engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timelineId || !engine.findClip(clipId)) throw new Error("The source timeline changed during transcription");
  const span = { start: captions[0].start, end: Math.max(...captions.map((c) => c.start + c.duration)) };
  const existing = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks[trackIndex];
  const occupied = !!existing && existing.clips.some((c) => c.start < span.end && c.start + c.duration > span.start);
  let destination = trackIndex;
  if (occupied) {
    const before = new Set(engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks.map((track) => track.id));
    engine.dispatch("track.add", { name: "Captions" });
    const added = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks.findIndex((track) => !before.has(track.id));
    if (added >= 0) destination = added;
  }
  engine.dispatch("captions.add", { trackIndex: destination, clips: captions });
  onStatus(`${t(destination === trackIndex ? "cap.added" : "cap.addednew")}: ${captions.length}`);
  return captions.length;
}

/** Typed or pasted lines become captions: spread across a clip, or laid end to end from a time. */
export function typedCaptions(
  engine: ProjectEngine,
  lines: string[],
  options: CaptionOptions & { spreadOverClipId?: string; from?: number; each?: number } = {},
): Clip[] {
  const text = lines.map((line) => line.trim()).filter(Boolean);
  if (!text.length) return [];
  const look = captionLook(options);
  const found = options.spreadOverClipId ? engine.findClip(options.spreadOverClipId) : null;
  const start = found ? found.clip.start : options.from ?? engine.snapshot.playhead;
  const total = found ? found.clip.duration : (options.each ?? 2) * text.length;
  const span = total / text.length;
  const made = text.map((line, index) => ({
    id: `cap${Date.now()}${index}`,
    kind: "text" as const,
    label: line,
    start: Math.round((start + span * index) * 100) / 100,
    duration: Math.round(span * 100) / 100,
    textStyle: { ...defaultTextStyle(line), size: look.size, ...(options.style ?? {}), content: line },
    transform: { ...defaultTransform(), posY: look.posY },
  }));
  return made;
}
