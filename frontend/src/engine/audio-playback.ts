// Audio playback. The old path pointed an <audio> element at a freshly rendered
// mix and corrected it by assigning currentTime whenever it drifted past 120 ms,
// which both re-rendered the mix on every edit and made the element re-seek
// while playing. Neither is survivable for monitoring.
//
// This module instead:
//   - renders the mix only when the project's audio actually changed, keyed by a
//     signature over the fields that can reach the mix,
//   - decodes it once into an AudioBuffer, so playback is scheduled from memory
//     and cannot underrun on a slow machine,
//   - starts a buffer source at the playhead with a small lead so the first
//     samples are already queued when they are due,
//   - and reports its own position, so the engine's playhead can follow the
//     audio clock instead of drifting against it.
import { api, waitJob } from "./api";
import type { ProjectState } from "./types";

const LEAD = 0.06;

// Only these fields can change what the mix sounds like. Anything else (a
// transform, a colour grade, a text style, the preview size) must not cost a
// re-render, which is what let the old path interrupt playback on any edit.
export function audioSignature(project: ProjectState): string {
  const parts: unknown[] = [];
  for (const timeline of project.timelines) {
    for (const track of timeline.tracks) {
      parts.push([track.id, track.muted ?? false]);
      for (const clip of track.clips) {
        if (clip.kind !== "audio" && clip.kind !== "video") continue;
        parts.push([
          clip.id, clip.mediaId ?? "", clip.start, clip.duration, clip.sourceIn ?? 0,
          clip.speed ?? 1, clip.speedCurve ?? null, clip.volume ?? 1, clip.muted ?? false,
          clip.fadeIn ?? 0, clip.fadeOut ?? 0, clip.audioEffects ?? null,
        ]);
      }
    }
  }
  return JSON.stringify([project.activeTimeline, Math.round(project.duration * 1000), parts]);
}

export class AudioPlayback {
  private ctx?: AudioContext;
  private buffer?: AudioBuffer;
  private source?: AudioBufferSourceNode;
  private signature = "";
  private pending = "";
  private controller?: AbortController;
  private anchorCtx = 0;
  private anchorHead = 0;
  private running = false;
  private silent = false;

  constructor(private readonly onStatus: (text: string) => void) {}

  // A mix is needed when the audio signature moved, not when the project did.
  needsMix(project: ProjectState): boolean {
    return audioSignature(project) !== this.signature;
  }

  ready(): boolean {
    return !!this.buffer && !this.silent;
  }

  // Position on the audio clock, or null when this module is not the authority.
  position(): number | null {
    if (!this.running || !this.ctx) return null;
    return this.anchorHead + (this.ctx.currentTime - this.anchorCtx);
  }

  // resumeAt is a getter, not a number: a mix render takes seconds and the
  // transport keeps moving while it runs, so capturing the position when the
  // render was requested would rewind the playhead on resume.
  async prepare(project: ProjectState, resumeAt?: () => number | null): Promise<void> {
    const signature = audioSignature(project);
    if (signature === this.signature || signature === this.pending) return;
    this.pending = signature;
    this.controller?.abort();
    const controller = new AbortController();
    this.controller = controller;
    try {
      const created = await api("/api/render/audio", { project });
      await waitJob(created.job_id, undefined, controller.signal);
      const response = await fetch(`/api/jobs/${created.job_id}/file`, { signal: controller.signal });
      const bytes = await response.arrayBuffer();
      const ctx = this.context();
      const decoded = await ctx.decodeAudioData(bytes);
      if (controller.signal.aborted || this.pending !== signature) return;
      this.buffer = decoded;
      this.signature = signature;
      // A mix of pure silence is worth knowing about: it means nothing audible
      // is on the timeline, so playback should not pretend to be the clock.
      this.silent = isSilent(decoded);
      const resume = resumeAt?.();
      if (resume !== undefined && resume !== null) this.play(resume);
    } catch (error) {
      if (!controller.signal.aborted) {
        this.buffer = undefined;
        this.signature = "";
        this.onStatus(error instanceof Error ? error.message : "Audio failed");
      }
    } finally {
      if (this.pending === signature) this.pending = "";
    }
  }

  play(at: number): void {
    const ctx = this.context();
    if (!this.buffer || this.silent) return;
    void ctx.resume();
    this.stopSource();
    const offset = Math.max(0, Math.min(at, this.buffer.duration));
    const source = ctx.createBufferSource();
    source.buffer = this.buffer;
    source.connect(ctx.destination);
    const startAt = ctx.currentTime + LEAD;
    source.start(startAt, offset);
    source.onended = () => {
      if (this.source === source) this.running = false;
    };
    this.source = source;
    this.anchorCtx = startAt;
    this.anchorHead = offset;
    this.running = true;
  }

  pause(): void {
    this.stopSource();
    this.running = false;
  }

  // Seeking is a restart: a buffer source cannot be moved, and restarting from
  // memory costs one scheduling call rather than an element seek and reload.
  seek(at: number): void {
    if (this.running) this.play(at);
  }

  private stopSource(): void {
    if (!this.source) return;
    this.source.onended = null;
    try {
      this.source.stop();
    } catch {
      // Already finished; stopping twice is not an error worth surfacing.
    }
    this.source.disconnect();
    this.source = undefined;
  }

  private context(): AudioContext {
    if (!this.ctx) this.ctx = new AudioContext();
    return this.ctx;
  }
}

function isSilent(buffer: AudioBuffer): boolean {
  for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
    const data = buffer.getChannelData(channel);
    const step = Math.max(1, Math.floor(data.length / 4000));
    for (let index = 0; index < data.length; index += step) {
      if (Math.abs(data[index]) > 0.0005) return false;
    }
  }
  return true;
}
