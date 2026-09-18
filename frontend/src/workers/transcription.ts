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

function modelFor(language: string): string {
  // english-only tiny for en, multilingual tiny otherwise
  return language === "en" ? "Xenova/whisper-tiny.en" : "onnx-community/whisper-tiny";
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

self.onmessage = async (ev: MessageEvent<{ audio: Float32Array; language?: string }>) => {
  try {
    const model = modelFor(ev.data.language ?? "en");
    if (!transcriber || loadedModel !== model) {
      self.postMessage({ type: "progress", message: "Loading Whisper model" });
      loadedModel = model;
      transcriber = (await pipeline("automatic-speech-recognition", model, {
        dtype: "q8",
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
    const result = await transcriber(ev.data.audio, {
      chunk_length_s: 30,
      return_timestamps: true,
    });
    const chunks = (result.chunks ?? [])
      .map((c) => ({
        text: c.text.trim(),
        start: c.timestamp[0] ?? 0,
        end: c.timestamp[1] ?? (c.timestamp[0] ?? 0) + 2,
      }))
      .filter((c) => c.text.length > 0 && !isRepetitiveText(c.text));
    self.postMessage({ type: "result", chunks });
  } catch (err) {
    self.postMessage({ type: "error", message: err instanceof Error ? err.message : String(err) });
  }
};
