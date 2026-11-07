import type { Clip, ProjectState, Track } from "../../frontend/src/engine/types";
import { sourceTime } from "../../frontend/src/engine/timing";
import { getSource } from "./media";

interface VideoSlot {
  el: HTMLVideoElement;
  gain?: GainNode;
}

const LEAD = 0.06;

export class Mixer {
  private ctx?: AudioContext;
  private master?: GainNode;
  private tapNode?: MediaStreamAudioDestinationNode;
  private nodes: AudioScheduledSourceNode[] = [];
  private slots = new Map<string, VideoSlot>();
  private origin = 0;
  private ctxStart = 0;
  private running = false;
  private signature = "";
  onFrame: () => void = () => {};

  get tap(): MediaStream {
    this.ensure();
    return this.tapNode!.stream;
  }

  private ensure(): AudioContext {
    if (!this.ctx) {
      this.ctx = new AudioContext();
      this.master = this.ctx.createGain();
      this.master.connect(this.ctx.destination);
      this.tapNode = this.ctx.createMediaStreamDestination();
      this.master.connect(this.tapNode);
      for (const slot of this.slots.values()) this.wire(slot);
    }
    return this.ctx;
  }

  private wire(slot: VideoSlot): void {
    if (slot.gain || !this.ctx || !this.master) return;
    try {
      const node = this.ctx.createMediaElementSource(slot.el);
      slot.gain = this.ctx.createGain();
      node.connect(slot.gain).connect(this.master);
    } catch {
      slot.gain = undefined;
    }
  }

  video(clip: Clip): HTMLVideoElement | null {
    return this.videoFor(clip);
  }

  videoFor(clip: Clip): HTMLVideoElement | null {
    const source = getSource(clip.mediaId);
    if (!source?.url) return null;
    let slot = this.slots.get(clip.id);
    if (!slot) {
      const el = document.createElement("video");
      el.preload = "auto";
      el.playsInline = true;
      el.src = source.url;
      el.addEventListener("seeked", () => this.onFrame());
      el.addEventListener("loadeddata", () => this.onFrame());
      slot = { el };
      this.slots.set(clip.id, slot);
      this.wire(slot);
    }
    return slot.el;
  }

  private tailOf(track: Track, clip: Clip): number {
    const end = clip.start + clip.duration;
    const next = track.clips.find((other) => other !== clip && other.transitionIn && Math.abs(other.start - end) < 0.06);
    return next?.transitionIn?.duration ?? 0;
  }

  waiting(state: ProjectState, t: number): boolean {
    for (const track of state.timelines[state.activeTimeline].tracks) {
      if (track.hidden) continue;
      for (const clip of track.clips) {
        if (clip.kind !== "video") continue;
        const local = t - clip.start;
        if (local < 0 || local >= clip.duration + this.tailOf(track, clip)) continue;
        const el = this.slots.get(clip.id)?.el;
        if (el && !el.error && (el.seeking || el.readyState < 2)) return true;
      }
    }
    return false;
  }

  syncVideos(state: ProjectState, t: number, playing: boolean): void {
    const tracks = state.timelines[state.activeTimeline].tracks;
    const live = new Set<string>();
    for (const track of tracks) {
      for (const clip of track.clips) {
        if (clip.kind !== "video" || !getSource(clip.mediaId)?.url) continue;
        const local = t - clip.start;
        const active = local >= 0 && local < clip.duration + this.tailOf(track, clip) && !track.hidden;
        const el = this.videoFor(clip);
        if (!el) continue;
        const slot = this.slots.get(clip.id)!;
        if (!active) {
          if (!el.paused) el.pause();
          continue;
        }
        live.add(clip.id);
        const target = sourceTime(clip, local);
        const speed = clip.speed ?? 1;
        if (playing) {
          if (el.playbackRate !== speed) el.playbackRate = Math.min(16, Math.max(0.0625, speed));
          if (el.paused) {
            el.currentTime = target;
            el.muted = !slot.gain && !!(clip.muted || track.muted);
            void el.play().catch(() => {});
          } else if (Math.abs(el.currentTime - target) > 0.3) el.currentTime = target;
        } else {
          if (!el.paused) el.pause();
          if (Math.abs(el.currentTime - target) > 0.02) el.currentTime = target;
        }
        const fadeIn = clip.fadeIn && local < clip.fadeIn ? local / clip.fadeIn : 1;
        const fadeOut = clip.fadeOut && clip.duration - local < clip.fadeOut ? Math.max(0, clip.duration - local) / clip.fadeOut : 1;
        const level = clip.muted || track.muted ? 0 : (clip.volume ?? 1) * Math.min(fadeIn, fadeOut);
        if (slot.gain) slot.gain.gain.value = level;
        else el.volume = Math.min(1, Math.max(0, level));
      }
    }
    for (const [id, slot] of this.slots) if (!live.has(id) && !slot.el.paused) slot.el.pause();
  }

  private audioSignature(state: ProjectState): string {
    const tracks = state.timelines[state.activeTimeline].tracks;
    return JSON.stringify(tracks.map((track) => [track.muted, track.clips.filter((c) => c.kind === "audio").map((c) => [c.id, c.start, c.duration, c.sourceIn, c.speed, c.volume, c.muted, c.fadeIn, c.fadeOut, c.mediaId])]));
  }

  changed(state: ProjectState): boolean {
    return this.audioSignature(state) !== this.signature;
  }

  async start(state: ProjectState, from: number): Promise<void> {
    const ctx = this.ensure();
    this.stopNodes();
    this.signature = this.audioSignature(state);
    this.origin = from;
    this.running = false;
    if (ctx.state !== "running") await ctx.resume().catch(() => {});
    this.ctxStart = ctx.currentTime + LEAD;
    this.running = ctx.state === "running";
    const tracks = state.timelines[state.activeTimeline].tracks;
    for (const track of tracks) {
      for (const clip of track.clips) {
        if (clip.kind !== "audio") continue;
        const source = getSource(clip.mediaId);
        if (!source?.buffer) continue;
        const local0 = from - clip.start;
        if (local0 >= clip.duration) continue;
        const into = Math.max(0, local0);
        const when = this.ctxStart + Math.max(0, -local0);
        const length = clip.duration - into;
        const speed = clip.speed ?? 1;
        const node = ctx.createBufferSource();
        node.buffer = source.buffer;
        node.playbackRate.value = speed;
        const gain = ctx.createGain();
        const level = clip.muted || track.muted ? 0 : (clip.volume ?? 1);
        const fadeIn = clip.fadeIn ?? 0;
        const fadeOut = clip.fadeOut ?? 0;
        const startLevel = fadeIn && into < fadeIn ? level * (into / fadeIn) : level;
        gain.gain.setValueAtTime(startLevel, when);
        if (fadeIn && into < fadeIn) gain.gain.linearRampToValueAtTime(level, when + (fadeIn - into));
        if (fadeOut) {
          const outAt = when + Math.max(0, length - fadeOut);
          gain.gain.setValueAtTime(level, Math.max(outAt, when + (fadeIn && into < fadeIn ? fadeIn - into : 0)));
          gain.gain.linearRampToValueAtTime(0, when + length);
        }
        node.connect(gain).connect(this.master!);
        const offset = sourceTime(clip, into) % Math.max(0.01, source.buffer.duration);
        node.start(when, offset);
        node.stop(when + length);
        this.nodes.push(node);
      }
    }
  }

  private stopNodes(): void {
    for (const node of this.nodes) {
      try {
        node.stop();
      } catch {
        continue;
      }
    }
    this.nodes = [];
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
