import { propPoints, samplePoints } from "../../../frontend/src/engine/keyframes";
import { sourceTime } from "../../../frontend/src/engine/timing";
import type { Clip, KeyframeProp, ProjectState, Track } from "../../../frontend/src/engine/types";
import { getSource } from "../../../demo/src/media";

const VOLUME = "volume" as KeyframeProp;
const LEAD = 0.06;

export const volumeAt = (clip: Clip, local: number): number => {
  const keyed = samplePoints(propPoints(clip, VOLUME), local);
  return clip.muted ? 0 : (clip.volume ?? 1) * (keyed ?? 1);
};

export interface Meter {
  peak: number;
  rms: number;
}

export interface BusTap {
  trackId: string;
  analyser: AnalyserNode;
}

export interface Graph {
  master: GainNode;
  taps: BusTap[];
  nodes: AudioScheduledSourceNode[];
}

const envelopeSteps = (clip: Clip, level: (t: number) => number, from: number, to: number, param: AudioParam, when: number): void => {
  const step = 0.05;
  param.setValueAtTime(level(from), when);
  for (let t = from + step; t < to; t += step) param.linearRampToValueAtTime(level(t), when + (t - from));
  param.linearRampToValueAtTime(level(to), when + (to - from));
};

export function buildGraph(ctx: BaseAudioContext, destination: AudioNode, state: ProjectState, from: number, when: number, withTaps: boolean): Graph {
  const master = ctx.createGain();
  master.connect(destination);
  const graph: Graph = { master, taps: [], nodes: [] };
  const tracks: Track[] = state.timelines[state.activeTimeline].tracks;
  for (const track of tracks) {
    const clips = track.clips.filter((clip) => clip.kind === "audio");
    if (!clips.length || track.muted) continue;
    const bus = ctx.createGain();
    bus.connect(master);
    if (withTaps) {
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 2048;
      bus.connect(analyser);
      graph.taps.push({ trackId: track.id, analyser });
    }
    for (const clip of clips) {
      const source = getSource(clip.mediaId);
      if (!source?.buffer) continue;
      const local0 = from - clip.start;
      if (local0 >= clip.duration) continue;
      const into = Math.max(0, local0);
      const start = when + Math.max(0, -local0);
      const length = clip.duration - into;
      const node = ctx.createBufferSource();
      node.buffer = source.buffer;
      node.playbackRate.value = clip.speed ?? 1;
      const gain = ctx.createGain();
      const fadeIn = clip.fadeIn ?? 0;
      const fadeOut = clip.fadeOut ?? 0;
      const level = (local: number): number => {
        const rise = fadeIn && local < fadeIn ? local / fadeIn : 1;
        const fall = fadeOut && clip.duration - local < fadeOut ? Math.max(0, clip.duration - local) / fadeOut : 1;
        return volumeAt(clip, local) * Math.min(rise, fall);
      };
      envelopeSteps(clip, level, into, clip.duration, gain.gain, start);
      node.connect(gain).connect(bus);
      node.start(start, sourceTime(clip, into) % Math.max(0.01, source.buffer.duration));
      node.stop(start + length);
      graph.nodes.push(node);
    }
  }
  return graph;
}

export function meterOf(analyser: AnalyserNode, buffer: Float32Array<ArrayBuffer>): Meter {
  analyser.getFloatTimeDomainData(buffer);
  let peak = 0;
  let sum = 0;
  for (let i = 0; i < buffer.length; i += 1) {
    const v = Math.abs(buffer[i]);
    if (v > peak) peak = v;
    sum += v * v;
  }
  return { peak, rms: Math.sqrt(sum / buffer.length) };
}

export const toDb = (value: number): number => (value > 1e-6 ? 20 * Math.log10(value) : -120);

interface VideoSlot {
  el: HTMLVideoElement;
}

export class DeliverMixer {
  private ctx?: AudioContext;
  private tapNode?: MediaStreamAudioDestinationNode;
  private graph?: Graph;
  private slots = new Map<string, VideoSlot>();
  private origin = 0;
  private ctxStart = 0;
  private running = false;
  private signature = "";
  trim = 1;
  onFrame: () => void = () => {};

  get tap(): MediaStream {
    this.ensure();
    return this.tapNode!.stream;
  }

  get taps(): BusTap[] {
    return this.graph?.taps ?? [];
  }

  get master(): GainNode | undefined {
    return this.graph?.master;
  }

  private ensure(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.tapNode = this.ctx.createMediaStreamDestination();
    }
    return this.ctx;
  }

  video(clip: Clip): HTMLVideoElement | null {
    const source = getSource(clip.mediaId);
    if (!source?.url) return null;
    let slot = this.slots.get(clip.id);
    if (!slot) {
      const el = document.createElement("video");
      el.preload = "auto";
      el.playsInline = true;
      el.muted = true;
      el.src = source.url;
      el.addEventListener("seeked", () => this.onFrame());
      el.addEventListener("loadeddata", () => this.onFrame());
      slot = { el };
      this.slots.set(clip.id, slot);
    }
    return slot.el;
  }

  private tailOf(track: Track, clip: Clip): number {
    const end = clip.start + clip.duration;
    const next = track.clips.find((other) => other !== clip && other.transitionIn && Math.abs(other.start - end) < 0.06);
    return next?.transitionIn?.duration ?? 0;
  }

  private activeVideos(state: ProjectState, t: number): Array<{ clip: Clip; track: Track }> {
    const out: Array<{ clip: Clip; track: Track }> = [];
    for (const track of state.timelines[state.activeTimeline].tracks) {
      if (track.hidden) continue;
      for (const clip of track.clips) {
        if (clip.kind !== "video") continue;
        const local = t - clip.start;
        if (local >= 0 && local < clip.duration + this.tailOf(track, clip)) out.push({ clip, track });
      }
    }
    return out;
  }

  waiting(state: ProjectState, t: number): boolean {
    for (const { clip } of this.activeVideos(state, t)) {
      const el = this.slots.get(clip.id)?.el;
      if (el && !el.error && (el.seeking || el.readyState < 2)) return true;
    }
    return false;
  }

  syncVideos(state: ProjectState, t: number, playing: boolean): void {
    const live = new Set<string>();
    for (const { clip } of this.activeVideos(state, t)) {
      const el = this.video(clip);
      if (!el) continue;
      live.add(clip.id);
      const target = sourceTime(clip, t - clip.start);
      if (playing) {
        if (el.paused) {
          el.currentTime = target;
          void el.play().catch(() => {});
        } else if (Math.abs(el.currentTime - target) > 0.3) el.currentTime = target;
      } else {
        if (!el.paused) el.pause();
        if (Math.abs(el.currentTime - target) > 0.02) el.currentTime = target;
      }
    }
    for (const [id, slot] of this.slots) if (!live.has(id) && !slot.el.paused) slot.el.pause();
  }

  private signatureOf(state: ProjectState): string {
    const tracks = state.timelines[state.activeTimeline].tracks;
    return JSON.stringify([this.trim, tracks.map((track) => [track.muted, track.clips.filter((c) => c.kind === "audio").map((c) => [c.id, c.start, c.duration, c.sourceIn, c.volume, c.muted, c.fadeIn, c.fadeOut, c.keyframes])])]);
  }

  changed(state: ProjectState): boolean {
    return this.signatureOf(state) !== this.signature;
  }

  async start(state: ProjectState, from: number): Promise<void> {
    const ctx = this.ensure();
    this.stopNodes();
    this.signature = this.signatureOf(state);
    this.origin = from;
    this.running = false;
    if (ctx.state !== "running") await ctx.resume().catch(() => {});
    this.ctxStart = ctx.currentTime + LEAD;
    this.running = ctx.state === "running";
    const graph = buildGraph(ctx, ctx.destination, state, from, this.ctxStart, true);
    graph.master.gain.value = this.trim;
    graph.master.connect(this.tapNode!);
    this.graph = graph;
  }

  private stopNodes(): void {
    if (!this.graph) return;
    for (const node of this.graph.nodes) {
      try {
        node.stop();
      } catch {
        continue;
      }
    }
    this.graph.master.disconnect();
    this.graph = undefined;
  }

  stop(): void {
    this.stopNodes();
    this.running = false;
    for (const slot of this.slots.values()) if (!slot.el.paused) slot.el.pause();
  }

  position(): number | null {
    if (!this.ctx || !this.running || this.ctx.state !== "running") return null;
    return this.origin + Math.max(0, this.ctx.currentTime - this.ctxStart);
  }
}

export interface Rendered {
  left: Float32Array;
  right: Float32Array;
  rate: number;
}

export async function renderMix(state: ProjectState, length: number, trim: number): Promise<Rendered> {
  const rate = 44100;
  const ctx = new OfflineAudioContext(2, Math.ceil(length * rate), rate);
  const graph = buildGraph(ctx, ctx.destination, state, 0, 0, false);
  graph.master.gain.value = trim;
  const buffer = await ctx.startRendering();
  return { left: buffer.getChannelData(0), right: buffer.getChannelData(1), rate };
}

interface Biquad {
  b: [number, number, number];
  a: [number, number];
}

function kWeights(rate: number): Biquad[] {
  const g = 3.999843853973347;
  const q1 = 0.7071752369554196;
  const f1 = 1681.974450955533;
  const A = 10 ** (g / 40);
  const w1 = (2 * Math.PI * f1) / rate;
  const alpha = Math.sin(w1) / (2 * q1);
  const c = Math.cos(w1);
  const s = 2 * Math.sqrt(A) * alpha;
  const a0 = A + 1 - (A - 1) * c + s;
  const shelf: Biquad = {
    b: [(A * (A + 1 + (A - 1) * c + s)) / a0, (-2 * A * (A - 1 + (A + 1) * c)) / a0, (A * (A + 1 + (A - 1) * c - s)) / a0],
    a: [(2 * (A - 1 - (A + 1) * c)) / a0, (A + 1 - (A - 1) * c - s) / a0],
  };
  const f2 = 38.13547087602444;
  const q2 = 0.5003270373238773;
  const w2 = (2 * Math.PI * f2) / rate;
  const al = Math.sin(w2) / (2 * q2);
  const c2 = Math.cos(w2);
  const h0 = 1 + al;
  const high: Biquad = { b: [(1 + c2) / 2 / h0, -(1 + c2) / h0, (1 + c2) / 2 / h0], a: [(-2 * c2) / h0, (1 - al) / h0] };
  return [shelf, high];
}

function filtered(samples: Float32Array, stages: Biquad[]): Float64Array {
  let x: Float64Array = Float64Array.from(samples);
  for (const stage of stages) {
    const y = new Float64Array(x.length);
    let x1 = 0;
    let x2 = 0;
    let y1 = 0;
    let y2 = 0;
    const [b0, b1, b2] = stage.b;
    const [a1, a2] = stage.a;
    for (let i = 0; i < x.length; i += 1) {
      const out = b0 * x[i] + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2;
      x2 = x1;
      x1 = x[i];
      y2 = y1;
      y1 = out;
      y[i] = out;
    }
    x = y;
  }
  return x;
}

export interface Loudness {
  integrated: number;
  truePeak: number;
  samplePeak: number;
  range: number;
}

export function measure(mix: Rendered): Loudness {
  const stages = kWeights(mix.rate);
  const channels = [filtered(mix.left, stages), filtered(mix.right, stages)];
  const block = Math.round(0.4 * mix.rate);
  const hop = Math.round(0.1 * mix.rate);
  const energies: number[] = [];
  for (let at = 0; at + block <= channels[0].length; at += hop) {
    let sum = 0;
    for (const channel of channels) {
      let acc = 0;
      for (let i = at; i < at + block; i += 1) acc += channel[i] * channel[i];
      sum += acc / block;
    }
    energies.push(sum);
  }
  const lufs = (energy: number): number => -0.691 + 10 * Math.log10(Math.max(energy, 1e-12));
  const absolute = energies.filter((e) => lufs(e) > -70);
  const mean = (list: number[]): number => list.reduce((a, b) => a + b, 0) / Math.max(1, list.length);
  const relativeGate = lufs(mean(absolute)) - 10;
  const gated = absolute.filter((e) => lufs(e) > relativeGate);
  const integrated = gated.length ? lufs(mean(gated)) : -70;
  const shortTerm: number[] = [];
  const shortBlock = Math.round(3 * mix.rate);
  for (let at = 0; at + shortBlock <= channels[0].length; at += mix.rate) {
    let sum = 0;
    for (const channel of channels) {
      let acc = 0;
      for (let i = at; i < at + shortBlock; i += 8) acc += channel[i] * channel[i];
      sum += acc / (shortBlock / 8);
    }
    shortTerm.push(lufs(sum));
  }
  const gate = shortTerm.filter((v) => v > -70);
  const rel = gate.length ? lufs(mean(gate.map((v) => 10 ** ((v + 0.691) / 10)))) - 20 : -70;
  const kept = gate.filter((v) => v > rel).sort((a, b) => a - b);
  const range = kept.length > 2 ? kept[Math.floor(kept.length * 0.95)] - kept[Math.floor(kept.length * 0.1)] : 0;
  let samplePeak = 0;
  let truePeak = 0;
  for (const channel of [mix.left, mix.right]) {
    for (let i = 0; i < channel.length; i += 1) {
      const v = Math.abs(channel[i]);
      if (v > samplePeak) samplePeak = v;
      if (v > truePeak) truePeak = v;
      if (i > 0 && i < channel.length - 2 && v > samplePeak * 0.5) {
        const p0 = channel[i - 1];
        const p1 = channel[i];
        const p2 = channel[i + 1];
        const p3 = channel[i + 2];
        for (const f of [0.25, 0.5, 0.75]) {
          const f2 = f * f;
          const f3 = f2 * f;
          const y = 0.5 * (2 * p1 + (-p0 + p2) * f + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f2 + (-p0 + 3 * p1 - 3 * p2 + p3) * f3);
          if (Math.abs(y) > truePeak) truePeak = Math.abs(y);
        }
      }
    }
  }
  return { integrated, truePeak: toDb(truePeak), samplePeak: toDb(samplePeak), range };
}

export const gainFor = (target: number, ceiling: number, loudness: Loudness): number => Math.min(target - loudness.integrated, ceiling - loudness.truePeak);

export interface Duck {
  keyframes: Array<{ t: number; props: Record<string, number> }>;
  regions: Array<{ start: number; duration: number }>;
}

export function ducking(speech: AudioBuffer, from: number, length: number, depth: number, attack: number, release: number, threshold: number): Duck {
  const data = speech.getChannelData(0);
  const rate = speech.sampleRate;
  const step = Math.max(1, Math.round(rate * 0.01));
  const hop = step / rate;
  const first = Math.floor((from * rate) / step);
  const count = Math.floor(Math.min(length * rate, data.length - from * rate) / step);
  const level: number[] = [];
  for (let b = 0; b < count; b += 1) {
    let sum = 0;
    const base = (first + b) * step;
    for (let i = 0; i < step; i += 1) sum += data[base + i] * data[base + i];
    level.push(Math.sqrt(sum / step));
  }
  const speaking = level.map((v) => v > threshold);
  const gap = Math.max(1, Math.floor(release / hop));
  const filled = speaking.slice();
  let run = 0;
  speaking.forEach((value, index) => {
    if (value) {
      if (run > 0 && run <= gap) for (let k = index - run; k < index; k += 1) filled[k] = true;
      run = 0;
    } else run += 1;
  });
  const regions: Array<[number, number]> = [];
  let begin = -1;
  filled.forEach((value, index) => {
    if (value && begin < 0) begin = index * hop;
    else if (!value && begin >= 0) {
      regions.push([begin, index * hop]);
      begin = -1;
    }
  });
  if (begin >= 0) regions.push([begin, filled.length * hop]);
  const kept = regions.filter(([a, b]) => b - a > attack);
  const d = Math.max(0, Math.min(1, depth));
  const round = (v: number): number => Math.round(v * 1000) / 1000;
  const keyframes: Duck["keyframes"] = [];
  for (const [a, b] of kept) {
    keyframes.push({ t: round(Math.max(0, a - attack)), props: { volume: 1 } });
    keyframes.push({ t: round(a), props: { volume: d } });
    keyframes.push({ t: round(b), props: { volume: d } });
    keyframes.push({ t: round(b + release), props: { volume: 1 } });
  }
  return { keyframes, regions: kept.map(([a, b]) => ({ start: round(a), duration: round(b - a) })) };
}

export function wavOf(mix: Rendered): Blob {
  const frames = mix.left.length;
  const bytes = new ArrayBuffer(44 + frames * 4);
  const view = new DataView(bytes);
  const text = (at: number, value: string) => {
    for (let i = 0; i < value.length; i += 1) view.setUint8(at + i, value.charCodeAt(i));
  };
  text(0, "RIFF");
  view.setUint32(4, 36 + frames * 4, true);
  text(8, "WAVE");
  text(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 2, true);
  view.setUint32(24, mix.rate, true);
  view.setUint32(28, mix.rate * 4, true);
  view.setUint16(32, 4, true);
  view.setUint16(34, 16, true);
  text(36, "data");
  view.setUint32(40, frames * 4, true);
  const clip = (v: number): number => Math.max(-1, Math.min(1, v));
  for (let i = 0; i < frames; i += 1) {
    view.setInt16(44 + i * 4, Math.round(clip(mix.left[i]) * 32767), true);
    view.setInt16(46 + i * 4, Math.round(clip(mix.right[i]) * 32767), true);
  }
  return new Blob([bytes], { type: "audio/wav" });
}
