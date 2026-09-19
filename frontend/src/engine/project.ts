import {
  defaultTextStyle,
  defaultTransform,
  type Clip,
  type ClipTransition,
  type ProjectState,
  type TextStyle,
} from "./types";
import { seedProject } from "./seed";
import { sourceTime, shiftedCurve, retimedKeys } from "./timing";
import { CREATOR_COMMANDS, creatorCommand } from "./creator-commands";
import { cycleKeyframeInterp, removeKeyframeProp, upsertKeyframe } from "./keyframes";
import { apply, diff, deltaSize, type Delta } from "./json-delta";

type DocumentSlice = Pick<ProjectState, "timelines" | "duration" | "selectedClipId" | "activeTimeline" | "width" | "height" | "fps" | "aspect">;
const HISTORY_LIMIT = 200;
const FOLD_MS = 500;
import type { ClipKey, ClipMask, KeyframeProp } from "./types";

type Listener = (state: ProjectState, changed: string) => void;

export class ProjectEngine {
  private state: ProjectState;
  private listeners = new Set<Listener>();
  private raf = 0;
  private lastTick = 0;
  private clockSource?: () => number | null;
  private undoStack: Delta[] = [];
  private redoStack: Delta[] = [];
  private pendingBefore: DocumentSlice | null = null;
  private foldKey: string | null = null;
  private foldAt = 0;

  private snapshotObj(): DocumentSlice {
    return structuredClone({
      timelines: this.state.timelines,
      duration: this.state.duration,
      selectedClipId: this.state.selectedClipId,
      activeTimeline: this.state.activeTimeline,
      width: this.state.width,
      height: this.state.height,
      fps: this.state.fps,
      aspect: this.state.aspect,
    }) as DocumentSlice;
  }

  private snapshotClips(): string {
    return JSON.stringify(this.snapshotObj());
  }

  private restoreClips(snap: string) {
    const data = JSON.parse(snap) as Partial<ProjectState>;
    Object.assign(this.state, data);
    this.state.playhead = Math.min(this.state.playhead, this.state.duration);
  }

  private currentSlice(): DocumentSlice {
    const s = this.state;
    return { timelines: s.timelines, duration: s.duration, selectedClipId: s.selectedClipId, activeTimeline: s.activeTimeline, width: s.width, height: s.height, fps: s.fps, aspect: s.aspect } as DocumentSlice;
  }

  /** Turns the step in flight into an undo delta (after -> before) and drops the copy. */
  private settlePending() {
    if (!this.pendingBefore) return;
    const delta = diff(this.currentSlice(), this.pendingBefore);
    this.pendingBefore = null;
    if (delta.length === 0) return;
    this.undoStack.push(delta);
    if (this.undoStack.length > HISTORY_LIMIT) this.undoStack.shift();
  }

  private pushHistory(foldKey?: string) {
    const now = performance.now();
    if (foldKey && this.pendingBefore && this.foldKey === foldKey && now - this.foldAt < FOLD_MS) {
      this.foldAt = now;
      return;
    }
    this.settlePending();
    this.pendingBefore = this.snapshotObj();
    this.foldKey = foldKey ?? null;
    this.foldAt = now;
    this.redoStack.length = 0;
  }

  /** Undoes the step in flight without recording it (a command that found nothing to do or threw). */
  private dropPending(restore: boolean) {
    if (!this.pendingBefore) return;
    if (restore) Object.assign(this.state, this.pendingBefore);
    this.pendingBefore = null;
    this.foldKey = null;
  }

  private stepBack(from: Delta[], to: Delta[]): boolean {
    this.settlePending();
    this.foldKey = null;
    const delta = from.pop();
    if (!delta) return false;
    const before = this.currentSlice();
    const target = structuredClone(before);
    apply(target, delta);
    to.push(diff(target, before));
    Object.assign(this.state, target);
    this.state.playhead = Math.min(this.state.playhead, this.state.duration);
    return true;
  }

  /** Steps held and approximate bytes, for the memory report. */
  historyStats(): { undo: number; redo: number; bytes: number } {
    let bytes = 0;
    for (const delta of this.undoStack) bytes += deltaSize(delta);
    for (const delta of this.redoStack) bytes += deltaSize(delta);
    return { undo: this.undoStack.length, redo: this.redoStack.length, bytes };
  }

  findClip(clipId: string): { clip: import("./types").Clip; trackIndex: number } | null {
    const timeline = this.state.timelines[this.state.activeTimeline];
    for (const [trackIndex, track] of timeline.tracks.entries()) {
      const clip = track.clips.find((c) => c.id === clipId);
      if (clip) return { clip, trackIndex };
    }
    return null;
  }

  constructor(initial?: ProjectState) {
    this.state = initial ?? seedProject();
  }

  get snapshot(): ProjectState {
    return this.state;
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit(changed: string) {
    if (changed === "clips" || changed === "timeline") {
      this.state.duration = Math.max(0.1, ...this.state.timelines[this.state.activeTimeline].tracks.flatMap(t => t.clips.map(c => c.start + c.duration)));
      this.state.playhead = Math.min(this.state.playhead, this.state.duration);
    }
    for (const fn of this.listeners) fn(this.state, changed);
  }

  dispatch(command: string, payload?: unknown): void {
    const s = this.state;
    if (command.startsWith("clip.") && command !== "clip.select") {
      const data = payload as { clipId?: string; trackIndex?: number } | undefined;
      const id = typeof payload === "string" ? payload : data?.clipId;
      const found = id ? this.findClip(id) : null;
      const tracks = s.timelines[s.activeTimeline].tracks;
      if ((found && tracks[found.trackIndex].locked) || (data?.trackIndex !== undefined && tracks[data.trackIndex]?.locked)) return;
    }
    if (CREATOR_COMMANDS.has(command)) {
      this.pushHistory();
      try { creatorCommand(s, command, payload); }
      catch (error) { this.dropPending(true); throw error; }
      s.duration = Math.max(0.1, ...s.timelines[s.activeTimeline].tracks.flatMap(t => t.clips.map(c => c.start + c.duration)));
      this.emit("clips");
      this.emit("timeline");
      this.emit("project");
      return;
    }
    switch (command) {
      case "transport.toggle":
        s.playing ? this.pause() : this.play();
        break;
      case "transport.seek":
        s.playhead = Math.min(Math.max(payload as number, 0), s.duration);
        this.emit("playhead");
        break;
      case "transport.home":
        s.playhead = 0;
        this.emit("playhead");
        break;
      case "transport.end":
        s.playhead = s.duration;
        this.emit("playhead");
        break;
      case "transport.step":
        s.playhead = Math.min(Math.max(s.playhead + (payload as number) / s.fps, 0), s.duration);
        this.emit("playhead");
        break;
      case "timeline.activate":
        if (!s.timelines[Number(payload)]) break;
        this.pause();
        s.activeTimeline = Number(payload);
        s.duration = Math.max(0.1, ...s.timelines[s.activeTimeline].tracks.flatMap(t => t.clips.map(c => c.start + c.duration)));
        s.playhead = Math.min(s.playhead, s.duration);
        s.selectedClipId = null;
        this.emit("timeline");
        this.emit("clip-selection");
        this.emit("playhead");
        break;
      case "clip.transform": {
        const p = payload as { clipId: string; patch: Partial<import("./types").ClipTransform> };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory(`clip.transform:${p.clipId}:${Object.keys(p.patch).sort().join(",")}`);
        found.clip.transform = { ...defaultTransform(), ...found.clip.transform, ...p.patch };
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.add": {
        const p = payload as { trackIndex: number; clip: import("./types").Clip };
        const timeline = s.timelines[s.activeTimeline];
        const track = timeline?.tracks[p.trackIndex];
        if (!track) break;
        this.pushHistory();
        track.clips.push(p.clip);
        s.duration = Math.max(s.duration, p.clip.start + p.clip.duration);
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.select": {
        const next = (payload as string | null) ?? null;
        if (s.selectedClipId === next) break;
        s.selectedClipId = next;
        this.emit("clip-selection");
        break;
      }
      case "clip.move": {
        const p = payload as { clipId: string; start: number; trackIndex?: number };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        const tracks = s.timelines[s.activeTimeline].tracks;
        if (p.trackIndex !== undefined && p.trackIndex !== found.trackIndex && tracks[p.trackIndex]) {
          const from = tracks[found.trackIndex].clips;
          from.splice(from.indexOf(found.clip), 1);
          tracks[p.trackIndex].clips.push(found.clip);
        }
        found.clip.start = Math.max(0, Math.round(p.start * 100) / 100);
        s.duration = Math.max(s.duration, found.clip.start + found.clip.duration);
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.trim": {
        const p = payload as { clipId: string; start: number; duration: number };
        const found = this.findClip(p.clipId);
        if (!found || p.duration < 0.1) break;
        this.pushHistory();
        const offset = p.start - found.clip.start;
        const previous = structuredClone(found.clip);
        found.clip.start = Math.max(0, Math.round(p.start * 100) / 100);
        found.clip.sourceIn = sourceTime(previous, offset);
        found.clip.speedCurve = shiftedCurve(previous, offset, p.duration);
        found.clip.keyframes = retimedKeys(previous.keyframes, offset, p.duration);
        found.clip.duration = Math.round(p.duration * 100) / 100;
        s.duration = Math.max(s.duration, found.clip.start + found.clip.duration);
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.split": {
        const p = payload as { clipId: string; time: number };
        const found = this.findClip(p.clipId);
        if (!found) break;
        const { clip, trackIndex } = found;
        const offset = Math.round((p.time - clip.start) * 100) / 100;
        if (offset < 0.1 || offset > clip.duration - 0.1) break;
        this.pushHistory();
        const tail = {
          ...structuredClone(clip),
          sourceIn: sourceTime(clip, offset),
          speedCurve: shiftedCurve(clip, offset, clip.duration - offset),
          keyframes: retimedKeys(clip.keyframes, offset, clip.duration - offset),
          transitionIn: undefined,
          fadeIn: 0,
          id: `${clip.id}s${Date.now() % 100000}`,
          start: Math.round((clip.start + offset) * 100) / 100,
          duration: Math.round((clip.duration - offset) * 100) / 100,
        };
        clip.duration = Math.round(offset * 100) / 100;
        clip.fadeOut = 0;
        const clips = s.timelines[s.activeTimeline].tracks[trackIndex].clips;
        clips.splice(clips.indexOf(clip) + 1, 0, tail);
        s.selectedClipId = tail.id;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.remove": {
        const clipId = payload as string;
        const found = this.findClip(clipId);
        if (!found) break;
        this.pushHistory();
        const clips = s.timelines[s.activeTimeline].tracks[found.trackIndex].clips;
        clips.splice(clips.indexOf(found.clip), 1);
        if (s.selectedClipId === clipId) s.selectedClipId = null;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.effect": {
        const p = payload as { clipId: string; effectId: string | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        found.clip.effectId = p.effectId ?? undefined;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "project.load": {
        const p = payload as Partial<ProjectState>;
        Object.assign(s, structuredClone(p));
        s.revision = p.revision ?? 0;
        s.activeTimeline = s.timelines[p.activeTimeline ?? 0] ? (p.activeTimeline ?? 0) : 0;
        s.duration = Math.max(0.1, ...s.timelines[s.activeTimeline].tracks.flatMap(t => t.clips.map(c => c.start + c.duration)));
        s.playhead = 0;
        s.playing = false;
        s.selectedClipId = null;
        s.saved = p.saved ?? true;
        this.undoStack.length = 0;
        this.redoStack.length = 0;
        this.pendingBefore = null;
        this.foldKey = null;
        cancelAnimationFrame(this.raf);
        this.emit("clips");
        this.emit("timeline");
        this.emit("clip-selection");
        this.emit("playhead");
        this.emit("transport");
        break;
      }
      case "clip.timing": {
        const p = payload as { clipId: string; speed?: number; fadeIn?: number; fadeOut?: number };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.speed !== undefined) {
          found.clip.speed = Math.min(4, Math.max(0.25, p.speed)) || 1;
        }
        const half = found.clip.duration / 2;
        if (p.fadeIn !== undefined) found.clip.fadeIn = Math.min(half, Math.max(0, p.fadeIn));
        if (p.fadeOut !== undefined) found.clip.fadeOut = Math.min(half, Math.max(0, p.fadeOut));
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.text": {
        const p = payload as { clipId: string; patch: Partial<TextStyle> };
        const found = this.findClip(p.clipId);
        if (!found || found.clip.kind !== "text") break;
        this.pushHistory();
        found.clip.textStyle = { ...defaultTextStyle(found.clip.label), ...found.clip.textStyle, ...p.patch };
        if (p.patch.content !== undefined) found.clip.label = p.patch.content;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.transition": {
        const p = payload as { clipId: string; transition: ClipTransition | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.transition) {
          const dur = Math.min(found.clip.duration / 2, Math.max(0.1, p.transition.duration));
          found.clip.transitionIn = { type: p.transition.type, duration: Math.round(dur * 100) / 100 };
        } else {
          found.clip.transitionIn = undefined;
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.style": {
        const p = payload as { clipId: string; style: Partial<Clip> };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        const st = p.style;
        const c = found.clip;
        if (st.transform) c.transform = { ...defaultTransform(), ...st.transform };
        c.effectId = st.effectId ?? undefined;
        Object.assign(c, structuredClone({ effects: st.effects, audioEffects: st.audioEffects, speedCurve: st.speedCurve, keyframes: st.keyframes, expressions: st.expressions, lutId: st.lutId, shaderId: st.shaderId, volume: st.volume, pan: st.pan }));
        c.key = st.key ?? undefined;
        c.mask = st.mask ?? undefined;
        c.audioFx = st.audioFx ?? undefined;
        c.speed = st.speed ?? undefined;
        c.fadeIn = st.fadeIn ?? undefined;
        c.fadeOut = st.fadeOut ?? undefined;
        c.transitionIn = st.transitionIn ?? undefined;
        if (c.kind === "text" && st.textStyle) {
          c.textStyle = { ...defaultTextStyle(c.label), ...st.textStyle };
        }
        s.saved = false;
        this.emit("clips");
        this.emit("clip-selection");
        break;
      }
      case "clip.audiofx": {
        const p = payload as { clipId: string; fx: string | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        found.clip.audioFx = p.fx || undefined;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.mask": {
        const p = payload as { clipId: string; mask: ClipMask | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.mask) {
          const cl = (v: number, lo: number, hi: number) => Math.min(hi, Math.max(lo, v));
          found.clip.mask = {
            shape: p.mask.shape === "ellipse" ? "ellipse" : "rect",
            x: cl(p.mask.x, 0, 100),
            y: cl(p.mask.y, 0, 100),
            w: cl(p.mask.w, 1, 100),
            h: cl(p.mask.h, 1, 100),
            feather: cl(p.mask.feather, 0, 50),
          };
        } else {
          found.clip.mask = undefined;
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.key": {
        const p = payload as { clipId: string; key: ClipKey | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.key && /^#[0-9a-fA-F]{6}$/.test(p.key.color)) {
          found.clip.key = {
            color: p.key.color.toLowerCase(),
            similarity: Math.min(1, Math.max(0.01, p.key.similarity)),
            blend: Math.min(1, Math.max(0, p.key.blend)),
          };
        } else {
          found.clip.key = undefined;
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.mute": {
        const p = payload as { clipId: string; muted: boolean };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        found.clip.muted = p.muted || undefined;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.interp": {
        const p = payload as { clipId: string; t: number };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        const next = cycleKeyframeInterp(found.clip, p.t);
        if (!next) {
          this.dropPending(false);
          break;
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.keyframes.set": {
        const p = payload as { clipId: string; keyframes: Array<{ t: number; props: Partial<Record<KeyframeProp, number>> }> };
        const found = this.findClip(p.clipId);
        if (!found || p.keyframes.length === 0) break;
        this.pushHistory();
        for (const kf of p.keyframes) {
          const local = Math.max(0, Math.min(found.clip.duration, kf.t));
          upsertKeyframe(found.clip, local, kf.props);
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.keyframe": {
        const p = payload as {
          clipId: string;
          t: number;
          set?: Partial<Record<KeyframeProp, number>>;
          remove?: KeyframeProp;
        };
        const found = this.findClip(p.clipId);
        if (!found) break;
        const local = Math.max(0, Math.min(found.clip.duration, p.t));
        this.pushHistory();
        if (p.remove) {
          removeKeyframeProp(found.clip, local, p.remove);
        } else if (p.set) {
          upsertKeyframe(found.clip, local, p.set);
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "captions.add": {
        const p = payload as { trackIndex: number; clips: Clip[] };
        const track = s.timelines[s.activeTimeline].tracks[p.trackIndex];
        if (!track || track.locked) throw new Error("Choose an unlocked caption track");
        if (p.clips.length === 0) break;
        this.pushHistory();
        for (const clip of p.clips) {
          track.clips.push(clip);
          s.duration = Math.max(s.duration, clip.start + clip.duration);
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "project.rename": {
        const next = (payload as string).trim();
        if (!next || next === s.title) break;
        s.title = next;
        s.saved = false;
        this.emit("project");
        break;
      }
      case "media.relink": {
        const map = payload as Record<string, string>;
        let changed = false;
        for (const timeline of s.timelines) {
          for (const track of timeline.tracks) {
            for (const clip of track.clips) {
              if (clip.mediaId && map[clip.mediaId]) {
                clip.mediaId = map[clip.mediaId];
                changed = true;
              }
            }
          }
        }
        if (!changed) break;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "project.saved": {
        const record = typeof payload === "string" ? { id: payload, revision: s.revision, unchanged: true } : payload as { id: string; revision: number; unchanged: boolean };
        s.projectId = record.id;
        s.revision = record.revision;
        s.saved = record.unchanged;
        this.emit("project");
        break;
      }
      case "history.undo": {
        if (!this.stepBack(this.undoStack, this.redoStack)) break;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "history.redo": {
        if (!this.stepBack(this.redoStack, this.undoStack)) break;
        s.saved = false;
        this.emit("clips");
        break;
      }
      default:
        this.emit("noop");
    }
  }

  previewTransform(clipId: string, patch: Partial<import("./types").ClipTransform>) {
    const found = this.findClip(clipId); if (!found) return;
    found.clip.transform = { ...defaultTransform(), ...found.clip.transform, ...patch };
    const local = this.state.playhead - found.clip.start;
    for (const prop of ["posX", "posY", "scale", "rotation", "opacity"] as KeyframeProp[]) {
      if (patch[prop] !== undefined && found.clip.keyframes?.some(k => prop in k.props)) upsertKeyframe(found.clip, local, { [prop]: patch[prop] });
    }
    this.emit("clips");
  }

  finishTransform(clipId: string, before: Pick<Clip, "transform" | "keyframes">, commit: boolean) {
    const found = this.findClip(clipId); if (!found) return;
    const after = structuredClone({ transform: found.clip.transform, keyframes: found.clip.keyframes });
    Object.assign(found.clip, structuredClone(before));
    if (commit) { this.pushHistory(); Object.assign(found.clip, after); this.state.saved = false; }
    this.emit("clips");
  }

  // While something with a better clock than a frame timer is playing (audio
  // scheduled on the audio context), the playhead follows it, so picture and
  // sound cannot drift apart. Without it, wall-clock deltas remain the source.
  setClockSource(source: (() => number | null) | null) {
    this.clockSource = source ?? undefined;
  }

  workArea: { start: number; end: number } | null = null;

  setWorkArea(area: { start: number; end: number } | null) {
    this.workArea = area && area.end - area.start > 0.05 ? { start: Math.max(0, area.start), end: area.end } : null;
    this.emit("transport");
  }

  play() {
    if (this.state.playing) return;
    this.state.playing = true;
    const area = this.workArea;
    if (area && (this.state.playhead < area.start || this.state.playhead >= area.end)) this.state.playhead = area.start;
    this.lastTick = performance.now();
    const tick = (now: number) => {
      if (!this.state.playing) return;
      const dt = (now - this.lastTick) / 1000;
      this.lastTick = now;
      const external = this.clockSource?.() ?? null;
      this.state.playhead = external === null ? this.state.playhead + dt : external;
      if (this.workArea && external === null && this.state.playhead >= this.workArea.end) {
        this.state.playhead = this.workArea.start;
      } else if (this.state.playhead >= this.state.duration) {
        this.state.playhead = this.state.duration;
        this.pause();
      }
      this.emit("playhead");
      this.raf = requestAnimationFrame(tick);
    };
    this.raf = requestAnimationFrame(tick);
    this.emit("transport");
  }

  pause() {
    this.state.playing = false;
    cancelAnimationFrame(this.raf);
    this.emit("transport");
  }
}

export function formatTimecode(seconds: number, fps: number): string {
  const total = Math.max(0, seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = Math.floor(total % 60);
  const f = Math.floor((total - Math.floor(total)) * fps);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(h)}:${p(m)}:${p(s)}:${p(f)}`;
}
