// Transcription worker: english whisper-tiny at q8, chunk timestamps, and a
// hallucination filter because tiny models loop phrases on silence.
import { env, pipeline } from "@huggingface/transformers";
import ortRuntime from "onnxruntime-web/ort-wasm-simd-threaded.asyncify.mjs?url";
import ortBinary from "onnxruntime-web/ort-wasm-simd-threaded.asyncify.wasm?url";

env.allowLocalModels = false;
env.useBrowserCache = false;
env.remoteHost = `${self.location.origin}/api/models/hub/`;
const wasmFlags = env.backends.onnx?.wasm;
if (wasmFlags) wasmFlags.wasmPaths = { mjs: ortRuntime, wasm: ortBinary };

interface Chunk {
  text: string;
  timestamp: [number, number | null];
}

type Transcriber = (
  audio: Float32Array,
  options: Record<string, unknown>,
) => Promise<{ text?: string; chunks?: Chunk[] }>;

let transcriber: Transcriber | null = null;
let loadedModel = "";

const ENGLISH_ONLY: Record<string, string> = {
  tiny: "Xenova/whisper-tiny.en",
  base: "Xenova/whisper-base.en",
  small: "Xenova/whisper-small.en",
};
const MULTILINGUAL: Record<string, string> = {
  tiny: "onnx-community/whisper-tiny",
  base: "onnx-community/whisper-base",
  small: "onnx-community/whisper-small",
};

function modelFor(language: string, size = "tiny"): string {
  const table = language === "en" ? ENGLISH_ONLY : MULTILINGUAL;
  return table[size] ?? table.tiny;
}

async function bestDevice(): Promise<"webgpu" | "wasm"> {
  const gpu = (self.navigator as Navigator & { gpu?: { requestAdapter(): Promise<unknown> } }).gpu;
  if (!gpu) return "wasm";
  try {
    return (await gpu.requestAdapter()) ? "webgpu" : "wasm";
  } catch {
    return "wasm";
  }
}

function isRepetitiveText(text: string): boolean {
  const words = text.toLowerCase().split(/\s+/).filter((w) => w.length > 0);
  if (words.length < 4) return false;
  for (let phraseLen = 2; phraseLen <= 4; phraseLen += 1) {
    const phrases: Record<string, number> = {};
    for (let i = 0; i <= words.length - phraseLen; i += 1) {
      const phrase = words.slice(i, i + phraseLen).join(" ");
      phrases[phrase] = (phrases[phrase] ?? 0) + 1;
      if (phrases[phrase] > 3) return true;
    }
  }
  const counts: Record<string, number> = {};
  for (const word of words) {
    counts[word] = (counts[word] ?? 0) + 1;
    if (counts[word] > words.length * 0.5 && counts[word] > 4) return true;
  }
  return false;
}

type Phrase = { text: string; start: number; end: number; words?: { t: number; d: number; text: string }[] };

function phrasesFromWords(chunks: Chunk[], limit?: number): Phrase[] {
  const cap = limit && limit > 0 ? limit : 6;
  const out: Phrase[] = [];
  let phrase: Phrase | null = null;
  for (const chunk of chunks) {
    const text = chunk.text.trim();
    const start = chunk.timestamp[0] ?? 0;
    const end = chunk.timestamp[1] ?? start + 0.3;
    if (!text) continue;
    const words = phrase?.words ?? [];
    const gap = phrase ? start - phrase.end : 0;
    const closes = phrase && (words.length >= cap || gap > 0.7 || end - phrase.start > 3.5 || /[.!?]$/.test(words[words.length - 1]?.text ?? ""));
    if (!phrase || closes) {
      phrase = { text: "", start, end, words: [] };
      out.push(phrase);
    }
    phrase.words!.push({ t: Math.round((start - phrase.start) * 1000) / 1000, d: Math.round(Math.max(0.05, end - start) * 1000) / 1000, text });
    phrase.end = Math.max(phrase.end, end);
    phrase.text = phrase.words!.map((w) => w.text).join(" ");
  }
  return out;
}

self.onmessage = async (ev: MessageEvent<{ audio: Float32Array; language?: string; size?: string; wordsPerCaption?: number }>) => {
  try {
    const model = modelFor(ev.data.language ?? "en", ev.data.size ?? "tiny");
    const device = await bestDevice();
    if (!transcriber || loadedModel !== `${model}@${device}`) {
      self.postMessage({ type: "progress", message: "Loading Whisper model" });
      self.postMessage({ type: "device", device, model });
      loadedModel = `${model}@${device}`;
      transcriber = (await pipeline("automatic-speech-recognition", model, {
        dtype: device === "webgpu" ? "fp16" : "q8",
        device,
        progress_callback: (p: { status?: string; progress?: number }) => {
          if (p.status === "progress" && typeof p.progress === "number") {
            self.postMessage({
              type: "progress",
              message: `Downloading model ${Math.round(p.progress)}%`,
            });
          }
        },
      })) as unknown as Transcriber;
    }
    self.postMessage({ type: "progress", message: "Transcribing" });
    let result: { text?: string; chunks?: Chunk[] } = {};
    let byWord = true;
    try {
      result = await transcriber(ev.data.audio, { chunk_length_s: 30, return_timestamps: "word" });
      if (!(result.chunks ?? []).length || (result.chunks ?? []).some((c) => c.text.trim().split(/\s+/).length > 3)) byWord = false;
    } catch {
      byWord = false;
    }
    if (!byWord) result = await transcriber(ev.data.audio, { chunk_length_s: 30, return_timestamps: true });
    const chunks = byWord
      ? phrasesFromWords(result.chunks ?? [], ev.data.wordsPerCaption)
      : (result.chunks ?? []).map((c) => ({
          text: c.text.trim(),
          start: c.timestamp[0] ?? 0,
          end: c.timestamp[1] ?? (c.timestamp[0] ?? 0) + 2,
        }));
    self.postMessage({ type: "result", chunks: chunks.filter((c) => c.text.length > 0 && !isRepetitiveText(c.text)), byWord });
  } catch (err) {
    self.postMessage({ type: "error", message: err instanceof Error ? err.message : String(err) });
  }
};
