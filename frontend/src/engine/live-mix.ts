import type { Clip, ProjectState } from "./types";

/** What changes a clip's *buffer* (as opposed to its live gain). */
export function clipAudioSignature(clip: Clip): string {
  return JSON.stringify([
    clip.mediaId ?? "", clip.sourceIn ?? 0, clip.duration, clip.extendOut ?? 0,
    clip.speed ?? 1, clip.speedCurve ?? null, clip.reversed ?? false,
    clip.audioEffects ?? null, clip.audioFx ?? null,
  ]);
}

/** The export's gain law, evaluated at a clip-local time. */
export function fadeGain(clip: Clip, local: number): number {
  const total = clip.duration + (clip.extendOut ?? 0);
  const inLength = clip.fadeIn ?? 0;
  const outLength = clip.fadeOut ?? 0;
  let gain = 1;
  if (inLength > 0 && local < inLength) gain *= Math.max(0, local / inLength);
  if (outLength > 0 && local > total - outLength) gain *= Math.max(0, (total - local) / outLength);
  return gain * Math.max(0, Math.min(4, clip.volume ?? 1));
}

interface Voice {
  source: AudioBufferSourceNode;
  gain: GainNode;
  clipId: string;
}

/**
 * R2: per-clip buffers mixed live.
 *
 * Each audible clip's processed sound is fetched once from the engine cache and
 * kept; playback schedules one source per clip against the audio context clock
 * and writes gain, fades and pan as automation, so a volume edit is heard on the
 * next scheduling tick instead of waiting for a whole-timeline render.
 */
export class LiveMixer {
  private ctx?: AudioContext;
  private buffers = new Map<string, AudioBuffer>();
  private voices: Voice[] = [];
  private loading = new Set<string>();

  context(): AudioContext {
    if (!this.ctx) this.ctx = new AudioContext();
    return this.ctx;
  }

  audible(project: ProjectState): Clip[] {
    const timeline = project.timelines[project.activeTimeline];
    return timeline.tracks
      .filter((track) => !track.muted)
      .flatMap((track) => track.clips)
      .filter((clip) => (clip.kind === "audio" || clip.kind === "video") && !clip.muted && clip.mediaId);
  }

  /** Fetch any missing clip buffers; returns how many were newly loaded. */
  async warm(project: ProjectState): Promise<number> {
    let loaded = 0;
    for (const clip of this.audible(project)) {
      const key = clipAudioSignature(clip);
      if (this.buffers.has(key) || this.loading.has(key)) continue;
      this.loading.add(key);
      try {
        const response = await fetch("/api/render/clip-audio", {
          method: "POST",
          headers: { "Content-Type": "application/json", "x-formcut-local": "1" },
          body: JSON.stringify({ clip }),
        });
        if (!response.ok) continue;
        const rate = Number(response.headers.get("x-formcut-rate")) || 48000;
        const raw = new Float32Array(await response.arrayBuffer());
        const frames = Math.floor(raw.length / 2);
        if (!frames) continue;
        const buffer = this.context().createBuffer(2, frames, rate);
        const left = buffer.getChannelData(0), right = buffer.getChannelData(1);
        for (let i = 0; i < frames; i += 1) { left[i] = raw[i * 2]; right[i] = raw[i * 2 + 1]; }
        this.buffers.set(key, buffer);
        loaded += 1;
      } catch {
        /* a clip that will not load simply stays silent */
      } finally {
        this.loading.delete(key);
      }
    }
    return loaded;
  }

  /** Schedule every clip that plays from `at`, with its gain curve written in. */
  play(project: ProjectState, at: number): number {
    const ctx = this.context();
    void ctx.resume();
    this.stop();
    const base = ctx.currentTime + 0.12;
    let scheduled = 0;
    for (const clip of this.audible(project)) {
      const buffer = this.buffers.get(clipAudioSignature(clip));
      if (!buffer) continue;
      const total = clip.duration + (clip.extendOut ?? 0);
      const end = clip.start + total;
      if (end <= at) continue;
      const localStart = Math.max(0, at - clip.start);
      const when = base + Math.max(0, clip.start - at);
      const gain = ctx.createGain();
      const pan = ctx.createStereoPanner();
      pan.pan.value = Math.max(-1, Math.min(1, clip.pan ?? 0));
      const source = ctx.createBufferSource();
      source.buffer = buffer;
      source.connect(gain).connect(pan).connect(ctx.destination);
      // Write the fade and volume curve as automation at 50 Hz, the same law
      // the exported mix applies from clip_envelope.
      const steps = Math.max(2, Math.ceil((total - localStart) * 50));
      gain.gain.cancelScheduledValues(when);
      for (let i = 0; i < steps; i += 1) {
        const local = localStart + (total - localStart) * (i / (steps - 1));
        gain.gain.linearRampToValueAtTime(fadeGain(clip, local), when + (local - localStart));
      }
      source.start(when, localStart, total - localStart);
      this.voices.push({ source, gain, clipId: clip.id });
      scheduled += 1;
    }
    return scheduled;
  }

  /** A gain edit during playback: rewrite that clip's curve, no re-render. */
  retune(project: ProjectState, at: number): number {
    const ctx = this.context();
    let touched = 0;
    for (const voice of this.voices) {
      const clip = this.audible(project).find((c) => c.id === voice.clipId);
      if (!clip) continue;
      const local = Math.max(0, at - clip.start);
      voice.gain.gain.cancelScheduledValues(ctx.currentTime);
      voice.gain.gain.setValueAtTime(fadeGain(clip, local), ctx.currentTime);
      const total = clip.duration + (clip.extendOut ?? 0);
      const steps = Math.max(2, Math.ceil((total - local) * 50));
      for (let i = 1; i < steps; i += 1) {
        const t = local + (total - local) * (i / (steps - 1));
        voice.gain.gain.linearRampToValueAtTime(fadeGain(clip, t), ctx.currentTime + (t - local));
      }
      touched += 1;
    }
    return touched;
  }

  stop(): void {
    for (const voice of this.voices) {
      try { voice.source.stop(); } catch { /* already finished */ }
      voice.source.disconnect();
    }
    this.voices = [];
  }

  get voiceCount(): number {
    return this.voices.length;
  }
}
