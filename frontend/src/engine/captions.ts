// Audio preparation for transcription: decode, take one channel, slice the
// clip's own source range, then resample linearly to the 16 kHz the model wants.
import { sourceTime } from "./timing";
import { timelineTime } from "./coordinates";
import type { ProjectEngine } from "./project";
import { fileUrl, type MediaBin } from "./media";
import { defaultTextStyle, defaultTransform, type Clip } from "./types";
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

export async function transcribeClip(
  engine: ProjectEngine,
  bin: MediaBin,
  clipId: string,
  onStatus: (message: string) => void,
  language: "en" | "auto" = "en",
  trackIndex = 0,
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

  const chunks = await new Promise<CaptionChunk[]>((resolve, reject) => {
    const worker = new Worker(new URL("../workers/transcription.ts", import.meta.url), {
      type: "module",
    });
    worker.onerror = event => { worker.terminate(); reject(new Error(event.message || "Transcription worker failed")); };
    worker.onmessage = (ev: MessageEvent<{ type: string; message?: string; chunks?: CaptionChunk[] }>) => {
      if (ev.data.type === "progress") onStatus(ev.data.message ?? "Working");
      if (ev.data.type === "result") {
        worker.terminate();
        resolve(ev.data.chunks ?? []);
      }
      if (ev.data.type === "error") {
        worker.terminate();
        reject(new Error(ev.data.message));
      }
    };
    worker.postMessage({ audio, language }, [audio.buffer]);
  });

  if (chunks.length === 0) {
    onStatus(t("cap.nospeech"));
    return 0;
  }
  const captions: Clip[] = chunks.map((chunk, n) => {
    const start = clip.start + timelineTime(clip, sourceTime(clip, 0) + chunk.start);
    const end = clip.start + timelineTime(clip, sourceTime(clip, 0) + chunk.end);
    return {
      id: `cap${Date.now()}${n}`,
      kind: "text",
      label: chunk.text,
      start: Math.round(start * 100) / 100,
      duration: Math.max(1 / engine.snapshot.fps, end - start),
      textStyle: { ...defaultTextStyle(chunk.text), size: 5 },
      transform: { ...defaultTransform(), posY: 35 },
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
