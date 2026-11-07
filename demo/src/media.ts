export type SourceKind = "video" | "audio" | "image";

export interface Source {
  id: string;
  name: string;
  kind: SourceKind;
  duration: number;
  width: number;
  height: number;
  origin: "generated" | "file";
  paint?: (ctx: CanvasRenderingContext2D, t: number, w: number, h: number) => void;
  canvas?: HTMLCanvasElement;
  url?: string;
  bitmap?: ImageBitmap;
  buffer?: AudioBuffer;
  peaks?: Float32Array;
  thumb?: string;
  facts: Array<[string, string]>;
}

export const PEAKS_PER_SECOND = 50;
export const FRAME_W = 1280;
export const FRAME_H = 720;

const registry = new Map<string, Source>();
const listeners = new Set<() => void>();

export const allSources = (): Source[] => [...registry.values()];
export const getSource = (id: string | undefined): Source | undefined => (id ? registry.get(id) : undefined);
export const onSources = (fn: () => void): (() => void) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};

export function addSource(source: Source): Source {
  registry.set(source.id, source);
  for (const fn of listeners) fn();
  return source;
}

function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function paintWaves(ctx: CanvasRenderingContext2D, t: number, w: number, h: number): void {
  const ground = ctx.createLinearGradient(0, 0, w, h);
  ground.addColorStop(0, "hsl(232 72% 11%)");
  ground.addColorStop(1, "hsl(268 62% 21%)");
  ctx.fillStyle = ground;
  ctx.fillRect(0, 0, w, h);
  for (let band = 0; band < 7; band += 1) {
    const base = h * (0.28 + band * 0.1);
    const amp = h * 0.05 * (1 + band * 0.22);
    ctx.beginPath();
    ctx.moveTo(0, h);
    for (let x = 0; x <= w; x += 8) {
      const y = base + Math.sin(x * 0.004 * (1 + band * 0.27) + t * (0.55 + band * 0.14) + band * 1.3) * amp
        + Math.sin(x * 0.011 + t * 0.9 + band) * amp * 0.25;
      ctx.lineTo(x, y);
    }
    ctx.lineTo(w, h);
    ctx.closePath();
    ctx.fillStyle = `hsl(${205 + band * 15} 85% ${48 + band * 2}% / ${0.13 + band * 0.025})`;
    ctx.fill();
  }
}

const glowSprites = new Map<number, HTMLCanvasElement>();

function glowSprite(hue: number): HTMLCanvasElement {
  let sprite = glowSprites.get(hue);
  if (sprite) return sprite;
  sprite = document.createElement("canvas");
  sprite.width = 64;
  sprite.height = 64;
  const g = sprite.getContext("2d")!;
  const fill = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  fill.addColorStop(0, `hsl(${hue} 100% 82% / 1)`);
  fill.addColorStop(0.25, `hsl(${hue} 100% 62% / 0.55)`);
  fill.addColorStop(1, `hsl(${hue} 100% 50% / 0)`);
  g.fillStyle = fill;
  g.fillRect(0, 0, 64, 64);
  glowSprites.set(hue, sprite);
  return sprite;
}

const particleSeeds = (() => {
  const next = rng(2024);
  return Array.from({ length: 110 }, () => ({
    x: next(), y: next(), speed: 0.015 + next() * 0.05, size: 10 + next() * 54,
    hue: [18, 30, 42, 340][Math.floor(next() * 4)], sway: next() * 6.28, alpha: 0.35 + next() * 0.6,
  }));
})();

function paintParticles(ctx: CanvasRenderingContext2D, t: number, w: number, h: number): void {
  const ground = ctx.createRadialGradient(w * 0.5, h * 0.7, 0, w * 0.5, h * 0.7, w * 0.8);
  ground.addColorStop(0, "hsl(14 70% 15%)");
  ground.addColorStop(1, "hsl(260 40% 5%)");
  ctx.fillStyle = ground;
  ctx.fillRect(0, 0, w, h);
  ctx.save();
  ctx.globalCompositeOperation = "lighter";
  for (const p of particleSeeds) {
    const rise = (((p.y - t * p.speed) % 1) + 1) % 1;
    const x = (p.x + Math.sin(t * 0.6 + p.sway) * 0.03) * w;
    const twinkle = 0.65 + 0.35 * Math.sin(t * 1.7 + p.sway * 3);
    ctx.globalAlpha = p.alpha * twinkle;
    const size = p.size * (w / 1280);
    ctx.drawImage(glowSprite(p.hue), x - size, rise * h - size, size * 2, size * 2);
  }
  ctx.restore();
}

function paintPattern(ctx: CanvasRenderingContext2D, t: number, w: number, h: number): void {
  ctx.fillStyle = "hsl(0 0% 8%)";
  ctx.fillRect(0, 0, w, h);
  const bars = [
    "hsl(0 0% 100%)", "hsl(60 100% 50%)", "hsl(180 100% 50%)", "hsl(120 100% 40%)",
    "hsl(300 100% 50%)", "hsl(0 100% 50%)", "hsl(240 100% 50%)",
  ];
  const barW = w / bars.length;
  bars.forEach((color, index) => {
    ctx.fillStyle = color;
    ctx.fillRect(index * barW, 0, barW + 1, h * 0.66);
  });
  for (let step = 0; step < 16; step += 1) {
    ctx.fillStyle = `hsl(0 0% ${(step / 15) * 100}%)`;
    ctx.fillRect((step * w) / 16, h * 0.66, w / 16 + 1, h * 0.14);
  }
  const bx = w * (0.5 + 0.38 * Math.sin(t * 1.1));
  const by = h * (0.7 + 0.08 * Math.sin(t * 2.3));
  ctx.fillStyle = "hsl(0 0% 0% / 0.55)";
  ctx.beginPath();
  ctx.arc(bx, by, h * 0.07, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = "hsl(0 0% 100%)";
  ctx.lineWidth = 3;
  ctx.stroke();
  const total = Math.max(0, t);
  const mm = String(Math.floor(total / 60)).padStart(2, "0");
  const ss = String(Math.floor(total % 60)).padStart(2, "0");
  const ff = String(Math.floor((total % 1) * 30)).padStart(2, "0");
  ctx.fillStyle = "hsl(0 0% 100%)";
  ctx.font = `700 ${h * 0.085}px ui-monospace, Menlo, Consolas, monospace`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(`00:${mm}:${ss}:${ff}`, w / 2, h * 0.9);
}

function paintPlate(ctx: CanvasRenderingContext2D, _t: number, w: number, h: number): void {
  ctx.fillStyle = "hsl(255 25% 9%)";
  ctx.fillRect(0, 0, w, h);
  const blobs: Array<[number, number, number, number]> = [[0.25, 0.3, 25, 0.55], [0.7, 0.4, 330, 0.5], [0.5, 0.8, 275, 0.55], [0.85, 0.85, 20, 0.35]];
  for (const [bx, by, hue, size] of blobs) {
    const g = ctx.createRadialGradient(w * bx, h * by, 0, w * bx, h * by, w * size);
    g.addColorStop(0, `hsl(${hue} 95% 60% / 0.95)`);
    g.addColorStop(1, `hsl(${hue} 95% 55% / 0)`);
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, w, h);
  }
  ctx.strokeStyle = "hsl(0 0% 100% / 0.16)";
  ctx.lineWidth = 2;
  for (let i = 1; i < 6; i += 1) {
    ctx.beginPath();
    ctx.arc(w / 2, h / 2, (h / 6) * i, 0, Math.PI * 2);
    ctx.stroke();
  }
}

function thumbOf(paint: NonNullable<Source["paint"]>, at: number): string {
  const canvas = document.createElement("canvas");
  canvas.width = 160;
  canvas.height = 90;
  paint(canvas.getContext("2d")!, at, 160, 90);
  return canvas.toDataURL("image/jpeg", 0.8);
}

const generatedFacts = (label: string): Array<[string, string]> => [
  ["Type", label],
  ["Origin", "Generated in this page, no file"],
  ["Size", `${FRAME_W} x ${FRAME_H}`],
  ["Duration", "Unbounded, generated per frame"],
];

function generatedVideo(id: string, name: string, paint: NonNullable<Source["paint"]>, at: number): Source {
  return {
    id, name, kind: "video", duration: 60, width: FRAME_W, height: FRAME_H, origin: "generated",
    paint, thumb: thumbOf(paint, at), facts: generatedFacts("Procedural video"),
  };
}

export function computePeaks(buffer: AudioBuffer): Float32Array {
  const bins = Math.max(1, Math.ceil(buffer.duration * PEAKS_PER_SECOND));
  const peaks = new Float32Array(bins);
  const step = buffer.length / bins;
  for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
    const data = buffer.getChannelData(channel);
    for (let bin = 0; bin < bins; bin += 1) {
      const from = Math.floor(bin * step);
      const to = Math.min(buffer.length, Math.floor((bin + 1) * step));
      let peak = peaks[bin];
      const stride = Math.max(1, Math.floor((to - from) / 24));
      for (let i = from; i < to; i += stride) {
        const value = Math.abs(data[i]);
        if (value > peak) peak = value;
      }
      peaks[bin] = peak;
    }
  }
  return peaks;
}

export function audioFacts(buffer: AudioBuffer): Array<[string, string]> {
  let peak = 0;
  let sum = 0;
  let count = 0;
  for (let channel = 0; channel < buffer.numberOfChannels; channel += 1) {
    const data = buffer.getChannelData(channel);
    const stride = Math.max(1, Math.floor(data.length / 400000));
    for (let i = 0; i < data.length; i += stride) {
      const value = data[i];
      if (Math.abs(value) > peak) peak = Math.abs(value);
      sum += value * value;
      count += 1;
    }
  }
  const db = (x: number) => (x <= 0 ? "-inf dBFS" : `${(20 * Math.log10(x)).toFixed(1)} dBFS`);
  return [
    ["Audio", `${buffer.numberOfChannels} ch, ${buffer.sampleRate} Hz`],
    ["Peak", db(peak)],
    ["RMS", db(Math.sqrt(sum / Math.max(1, count)))],
  ];
}

async function synthTone(): Promise<AudioBuffer> {
  const rate = 44100;
  const seconds = 8;
  const ctx = new OfflineAudioContext(2, rate * seconds, rate);
  const master = ctx.createGain();
  master.gain.value = 0.34;
  master.connect(ctx.destination);
  const chords = [[220, 261.63, 329.63], [174.61, 220, 261.63], [261.63, 329.63, 392], [196, 246.94, 293.66]];
  chords.forEach((chord, index) => {
    const start = index * 2;
    chord.forEach((freq, voice) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = voice === 0 ? "sine" : "triangle";
      osc.frequency.value = freq / (voice === 0 ? 2 : 1);
      gain.gain.setValueAtTime(0, start);
      gain.gain.linearRampToValueAtTime(0.22, start + 0.25);
      gain.gain.linearRampToValueAtTime(0, start + 2.05);
      osc.connect(gain).connect(master);
      osc.start(start);
      osc.stop(start + 2.1);
    });
    for (let step = 0; step < 8; step += 1) {
      const at = start + step * 0.25;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = "square";
      osc.frequency.value = chord[step % 3] * 2;
      gain.gain.setValueAtTime(0.0001, at);
      gain.gain.exponentialRampToValueAtTime(0.07, at + 0.01);
      gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.2);
      osc.connect(gain).connect(master);
      osc.start(at);
      osc.stop(at + 0.22);
    }
  });
  for (let beat = 0; beat < seconds * 2; beat += 1) {
    const at = beat * 0.5;
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.frequency.setValueAtTime(130, at);
    osc.frequency.exponentialRampToValueAtTime(42, at + 0.14);
    gain.gain.setValueAtTime(0.7, at);
    gain.gain.exponentialRampToValueAtTime(0.001, at + 0.2);
    osc.connect(gain).connect(master);
    osc.start(at);
    osc.stop(at + 0.22);
  }
  return ctx.startRendering();
}

export async function installSamples(): Promise<void> {
  addSource(generatedVideo("gen-waves", "Aurora waves", paintWaves, 1.5));
  addSource(generatedVideo("gen-embers", "Rising embers", paintParticles, 3));
  addSource(generatedVideo("gen-pattern", "Test pattern", paintPattern, 2.4));
  const plate: Source = {
    id: "gen-plate", name: "Gradient plate", kind: "image", duration: 5, width: FRAME_W, height: FRAME_H,
    origin: "generated", paint: paintPlate, thumb: thumbOf(paintPlate, 0), facts: generatedFacts("Procedural still"),
  };
  addSource(plate);
  const buffer = await synthTone();
  addSource({
    id: "gen-tone", name: "Chord loop", kind: "audio", duration: buffer.duration, width: 0, height: 0,
    origin: "generated", buffer, peaks: computePeaks(buffer),
    facts: [["Type", "Synthesised audio"], ["Origin", "Generated in this page, no file"], ["Duration", `${buffer.duration.toFixed(2)} s`], ...audioFacts(buffer)],
  });
}

export function sourceCanvas(source: Source): HTMLCanvasElement {
  if (!source.canvas) {
    source.canvas = document.createElement("canvas");
    source.canvas.width = FRAME_W;
    source.canvas.height = FRAME_H;
  }
  return source.canvas;
}

const sizeText = (bytes: number): string =>
  bytes > 1048576 ? `${(bytes / 1048576).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;

function canPlay(video: HTMLVideoElement): string {
  const tests: Array<[string, string]> = [["H.264", 'video/mp4; codecs="avc1.42E01E"'], ["VP9", 'video/webm; codecs="vp9"'], ["AV1", 'video/mp4; codecs="av01.0.05M.08"'], ["HEVC", 'video/mp4; codecs="hvc1.1.6.L93.B0"']];
  return tests.filter(([, type]) => video.canPlayType(type) !== "").map(([name]) => name).join(", ") || "none reported";
}

function estimateFps(video: HTMLVideoElement): Promise<number | null> {
  const probe = video as HTMLVideoElement & { requestVideoFrameCallback?: (cb: (now: number, meta: { mediaTime: number }) => void) => number };
  if (!probe.requestVideoFrameCallback) return Promise.resolve(null);
  return new Promise((resolve) => {
    const times: number[] = [];
    let settled = false;
    const finish = () => {
      if (settled) return;
      settled = true;
      video.pause();
      const gaps = times.slice(1).map((time, index) => time - times[index]).filter((gap) => gap > 0.001).sort((a, b) => a - b);
      resolve(gaps.length >= 4 ? 1 / gaps[Math.floor(gaps.length / 2)] : null);
    };
    const onFrame = (_now: number, meta: { mediaTime: number }) => {
      times.push(meta.mediaTime);
      if (times.length >= 14) finish();
      else probe.requestVideoFrameCallback!(onFrame);
    };
    probe.requestVideoFrameCallback(onFrame);
    video.muted = true;
    video.play().catch(finish);
    window.setTimeout(finish, 1800);
  });
}

function seekTo(video: HTMLVideoElement, time: number): Promise<void> {
  return new Promise((resolve) => {
    if (Math.abs(video.currentTime - time) < 0.01 && video.readyState >= 2) {
      resolve();
      return;
    }
    const done = () => resolve();
    video.addEventListener("seeked", done, { once: true });
    video.currentTime = time;
    window.setTimeout(done, 1500);
  });
}

async function decodeAudio(file: File): Promise<AudioBuffer | null> {
  if (file.size > 400 * 1048576) return null;
  try {
    const data = await file.arrayBuffer();
    return await new OfflineAudioContext(1, 1, 44100).decodeAudioData(data);
  } catch {
    return null;
  }
}

let counter = 0;
const nextId = (): string => `file-${Date.now().toString(36)}-${counter++}`;

async function loadVideo(file: File): Promise<Source> {
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.preload = "auto";
  video.muted = true;
  video.playsInline = true;
  video.src = url;
  await new Promise<void>((resolve, reject) => {
    video.addEventListener("loadedmetadata", () => resolve(), { once: true });
    video.addEventListener("error", () => reject(new Error(`This browser cannot decode ${file.name}`)), { once: true });
  });
  const duration = Number.isFinite(video.duration) ? video.duration : 10;
  await seekTo(video, Math.min(0.5, duration / 2));
  const shot = document.createElement("canvas");
  shot.width = 160;
  shot.height = 90;
  shot.getContext("2d")!.drawImage(video, 0, 0, 160, 90);
  const thumb = shot.toDataURL("image/jpeg", 0.8);
  const buffer = await decodeAudio(file);
  const fps = await estimateFps(video);
  await seekTo(video, 0);
  const facts: Array<[string, string]> = [
    ["Type", file.type || "video"],
    ["Origin", "Your file, read in this page only"],
    ["Size", `${video.videoWidth} x ${video.videoHeight}`],
    ["File", sizeText(file.size)],
    ["Duration", `${duration.toFixed(2)} s`],
    ["Frame rate", fps ? `about ${fps.toFixed(2)} fps (measured)` : "not measured"],
    ["Decoders", canPlay(video)],
    ...(buffer ? audioFacts(buffer) : [["Audio", "none decoded"] as [string, string]]),
  ];
  return {
    id: nextId(), name: file.name, kind: "video", duration, width: video.videoWidth, height: video.videoHeight,
    origin: "file", url, thumb, buffer: buffer ?? undefined, peaks: buffer ? computePeaks(buffer) : undefined, facts,
  };
}

async function loadAudio(file: File): Promise<Source> {
  const buffer = await decodeAudio(file);
  if (!buffer) throw new Error(`This browser cannot decode ${file.name}`);
  return {
    id: nextId(), name: file.name, kind: "audio", duration: buffer.duration, width: 0, height: 0, origin: "file",
    buffer, peaks: computePeaks(buffer),
    facts: [["Type", file.type || "audio"], ["Origin", "Your file, read in this page only"], ["File", sizeText(file.size)], ["Duration", `${buffer.duration.toFixed(2)} s`], ...audioFacts(buffer)],
  };
}

async function loadImage(file: File): Promise<Source> {
  const bitmap = await createImageBitmap(file);
  const shot = document.createElement("canvas");
  shot.width = 160;
  shot.height = 90;
  const g = shot.getContext("2d")!;
  const fit = Math.max(160 / bitmap.width, 90 / bitmap.height);
  g.drawImage(bitmap, (160 - bitmap.width * fit) / 2, (90 - bitmap.height * fit) / 2, bitmap.width * fit, bitmap.height * fit);
  return {
    id: nextId(), name: file.name, kind: "image", duration: 5, width: bitmap.width, height: bitmap.height, origin: "file",
    bitmap, thumb: shot.toDataURL("image/jpeg", 0.8),
    facts: [["Type", file.type || "image"], ["Origin", "Your file, read in this page only"], ["Size", `${bitmap.width} x ${bitmap.height}`], ["File", sizeText(file.size)]],
  };
}

export async function loadFile(file: File): Promise<Source> {
  const type = file.type;
  const name = file.name.toLowerCase();
  if (type.startsWith("video/") || /\.(mp4|m4v|mov|webm|mkv|ogv)$/.test(name)) return addSource(await loadVideo(file));
  if (type.startsWith("audio/") || /\.(wav|mp3|m4a|aac|ogg|oga|opus|flac)$/.test(name)) return addSource(await loadAudio(file));
  if (type.startsWith("image/") || /\.(png|jpe?g|gif|webp|bmp|avif)$/.test(name)) return addSource(await loadImage(file));
  throw new Error(`${file.name} is not a video, audio or image file`);
}
