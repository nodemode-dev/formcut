import { MASK_SHAPES } from "./types";
import type { Keyframe as ClipKeyframe, MaskPoint } from "./types";
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

type DocumentSlice = Pick<ProjectState, "timelines" | "duration" | "selectedClipId" | "selection" | "activeTimeline" | "width" | "height" | "fps" | "aspect">;
const HISTORY_LIMIT = 200;
const FOLD_MS = 500;
import type { ClipKey, ClipMask, KeyframeProp, TransformProp } from "./types";

type Listener = (state: ProjectState, changed: string) => void;

/**
 * The Pro tab's three-point edits (from FilmCraft's Premiere workflow): [start, end) taken out of one track in place.
 * A clip inside goes; one straddling an end keeps the part outside (cut into a head and a tail when it spans the whole
 * range, the tail's source moved on by the cut); nothing moves. Returns the clips kept, in order, and the ids removed.
 */
function carveRange(clips: Clip[], start: number, end: number): { kept: Clip[]; removed: string[] } {
  const kept: Clip[] = [];
  const removed: string[] = [];
  for (const clip of clips) {
    const clipEnd = clip.start + clip.duration;
    if (clipEnd <= start + 1e-6 || clip.start >= end - 1e-6) {
      kept.push(clip);
      continue;
    }
    if (clip.start >= start - 1e-6 && clipEnd <= end + 1e-6) {
      removed.push(clip.id);
      continue;
    }
    if (clip.start < start - 1e-6) {
      kept.push(clip);
      if (clipEnd > end + 1e-6) {
        kept.push({
          ...structuredClone(clip),
          id: crypto.randomUUID(),
          start: end,
          duration: clipEnd - end,
          sourceIn: (clip.sourceIn ?? 0) + (end - clip.start),
        } as Clip);
      }
      clip.duration = start - clip.start;
      continue;
    }
    clip.sourceIn = (clip.sourceIn ?? 0) + (end - clip.start);
    clip.duration = clipEnd - end;
    clip.start = end;
    kept.push(clip);
  }
  kept.sort((a, b) => a.start - b.start);
  return { kept, removed };
}

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
  /** The marked span on a timeline that Extract and Lift act on; not part of the document, so not saved or undone. */
  range: { start: number; end: number; timeline: number } | null = null;

  private snapshotObj(): DocumentSlice {
    return structuredClone({
      timelines: this.state.timelines,
      duration: this.state.duration,
      selectedClipId: this.state.selectedClipId,
      selection: this.state.selection,
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
    return { timelines: s.timelines, duration: s.duration, selectedClipId: s.selectedClipId, selection: s.selection, activeTimeline: s.activeTimeline, width: s.width, height: s.height, fps: s.fps, aspect: s.aspect } as DocumentSlice;
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

  private grouping = false;
  private groupTouched = 0;

  /** Runs fn as one undo step: every command inside records into one delta, and a throw puts the document back. */
  transaction<T>(fn: (touched: () => number) => T): T {
    if (this.grouping) return fn(() => this.groupTouched);
    this.settlePending();
    const before = this.snapshotObj();
    this.pendingBefore = before;
    this.foldKey = null;
    this.grouping = true;
    this.groupTouched = 0;
    try {
      const result = fn(() => this.groupTouched);
      this.grouping = false;
      if (this.groupTouched > 0 && this.pendingBefore) this.settlePending();
      else this.pendingBefore = null;
      return result;
    } catch (error) {
      this.grouping = false;
      this.pendingBefore = null;
      Object.assign(this.state, structuredClone(before));
      this.emit("clips");
      this.emit("timeline");
      this.emit("clip-selection");
      throw error;
    }
  }

  private pushHistory(foldKey?: string) {
    if (this.grouping) {
      this.groupTouched += 1;
      this.redoStack.length = 0;
      return;
    }
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

  /** Cuts one clip at a clip-relative offset; the shared tail math for clip.split and clips.split. */
  private splitOne(clip: import("./types").Clip, trackIndex: number, offset: number): import("./types").Clip {
    const tail = {
      ...structuredClone(clip),
      sourceIn: sourceTime(clip, offset),
      speedCurve: shiftedCurve(clip, offset, clip.duration - offset),
      keyframes: retimedKeys(clip.keyframes, offset, clip.duration - offset),
      transitionIn: undefined,
      fadeIn: 0,
      id: `${clip.id}s${(Date.now() + Math.floor(Math.random() * 997)) % 100000}`,
      start: Math.round((clip.start + offset) * 100) / 100,
      duration: Math.round((clip.duration - offset) * 100) / 100,
    };
    clip.duration = Math.round(offset * 100) / 100;
    clip.fadeOut = 0;
    const clips = this.state.timelines[this.state.activeTimeline].tracks[trackIndex].clips;
    clips.splice(clips.indexOf(clip) + 1, 0, tail);
    return tail;
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
    this.baseFormat = { width: this.state.width, height: this.state.height, fps: this.state.fps };
  }

  /** The project's own format; timelines without overrides inherit it, and saves record it. */
  baseFormat: { width: number; height: number; fps: number };

  get snapshot(): ProjectState {
    return this.state;
  }

  subscribe(fn: Listener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit(changed: string) {
    if (changed === "clips" || changed === "timeline") {
      for (const timeline of this.state.timelines) {
        for (const track of timeline.tracks) {
          if (!track.magnetic) continue;
          track.clips.sort((a, b) => a.start - b.start);
          let cursor = 0;
          for (const clip of track.clips) {
            if (clip.start !== cursor) clip.start = Math.round(cursor * 100) / 100;
            cursor = clip.start + clip.duration;
          }
        }
      }
      this.state.duration = Math.max(0.1, ...this.state.timelines[this.state.activeTimeline].tracks.flatMap(t => t.clips.map(c => c.start + c.duration)));
      this.state.playhead = Math.min(this.state.playhead, this.state.duration);
    }
    for (const fn of this.listeners) fn(this.state, changed);
  }

  dispatch(command: string, payload?: unknown): void {
    const s = this.state;
    if (command.startsWith("clip.") && !command.startsWith("clip.select")) {
      const data = payload as { clipId?: string; trackIndex?: number } | undefined;
      const id = typeof payload === "string" ? payload : data?.clipId;
      const found = id ? this.findClip(id) : null;
      const tracks = s.timelines[s.activeTimeline].tracks;
      if ((found && tracks[found.trackIndex].locked) || (data?.trackIndex !== undefined && tracks[data.trackIndex]?.locked)) return;
    }
    if (CREATOR_COMMANDS.has(command)) {
      // quiet: one history entry per gesture (a drag's later updates), as clip.keyframes.replace's quiet
      if (!(payload as { quiet?: boolean } | undefined)?.quiet) this.pushHistory();
      try { creatorCommand(s, command, payload); }
      catch (error) { this.dropPending(true); throw error; }
      if (command === "project.settings" && s.timelines.length === 1) this.baseFormat = { width: s.width, height: s.height, fps: s.fps };
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
      case "transport.skip":
        // The rewind and fast-forward buttons move in half seconds. Stepping a
        // single frame is still available on the arrow keys, where frame
        // accuracy is what a person is after.
        s.playhead = Math.min(Math.max(s.playhead + (payload as number), 0), s.duration);
        this.emit("playhead");
        break;
      case "transport.step":
        s.playhead = Math.min(Math.max(s.playhead + (payload as number) / s.fps, 0), s.duration);
        this.emit("playhead");
        break;
      case "clip.stabilise": {
        const p = payload as { clipId: string; stabilise: { smoothing: number; crop: number } | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.stabilise) {
          found.clip.stabilise = {
            smoothing: Math.min(1, Math.max(0, p.stabilise.smoothing)),
            crop: Math.min(0.3, Math.max(0, p.stabilise.crop)),
          };
        } else {
          delete found.clip.stabilise;
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "project.background": {
        const p = payload as { background: Record<string, unknown> | null };
        this.pushHistory();
        if (p.background) (s as unknown as Record<string, unknown>).background = p.background;
        else delete (s as unknown as Record<string, unknown>).background;
        s.saved = false;
        this.emit("project");
        this.emit("clips");
        break;
      }
      case "clip.planarMatte": {
        const p = payload as { clipId: string; planarMatte: { layers: string[]; feather: number; invert: boolean } | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.planarMatte && p.planarMatte.layers.length) found.clip.planarMatte = structuredClone(p.planarMatte);
        else delete found.clip.planarMatte;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.lens": {
        const p = payload as { clipId: string; lens: { k1: number; k2: number; mode: "undistort" | "redistort" } | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.lens) found.clip.lens = structuredClone(p.lens);
        else delete found.clip.lens;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.planarModule": {
        const p = payload as { clipId: string; planarStabilize?: { layer: string } | null; planarReorient?: { layer: string; surface: number[][] } | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.planarStabilize) found.clip.planarStabilize = structuredClone(p.planarStabilize);
        else if (p.planarStabilize === null) delete found.clip.planarStabilize;
        if (p.planarReorient) found.clip.planarReorient = structuredClone(p.planarReorient);
        else if (p.planarReorient === null) delete found.clip.planarReorient;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.cornerPin": {
        const p = payload as { clipId: string; cornerPin: { points: number[][]; times?: number[] } | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.cornerPin && p.cornerPin.points.length) found.clip.cornerPin = structuredClone(p.cornerPin);
        else delete found.clip.cornerPin;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.planar": {
        // the Track workspace's layers on the clip, kept with the project (the tracks themselves are the engine's)
        const p = payload as { clipId: string; planar: import("./types").ClipPlanar | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.planar && p.planar.layers.length) found.clip.planar = structuredClone(p.planar);
        else delete found.clip.planar;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.cutout": {
        // There was no such command. Everything that dispatched it, the brush
        // clear and the cutout flow, did nothing at all and said nothing, which
        // is the quietest way for a feature to be missing.
        const p = payload as { clipId: string; cutout: Record<string, unknown> | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.cutout) found.clip.cutout = p.cutout as never;
        else delete found.clip.cutout;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.mask-track": {
        // A tracked mask is stored as anchors over time, so it stays editable:
        // a person can move a point on any frame afterwards.
        const p = payload as { clipId: string; path: Array<{ t: number; mask: unknown }> };
        const found = this.findClip(p.clipId);
        if (!found || !p.path.length) break;
        this.pushHistory();
        found.clip.mask = {
          ...(found.clip.mask ?? { x: 0, y: 0, w: 100, h: 100, feather: 0 }),
          shape: "path",
          points: p.path[0].mask as MaskPoint[],
          track: p.path.map((entry) => ({ t: entry.t, points: entry.mask as MaskPoint[] })),
        };
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.remove-range": {
        // Cutting a range out of a clip: the part after it moves back by the
        // length removed, so nothing is left with a gap where a word was.
        const p = payload as { clipId: string; start: number; end: number };
        const found = this.findClip(p.clipId);
        if (!found) break;
        const length = Math.max(0, p.end - p.start);
        if (length <= 0.01) break;
        this.pushHistory();
        const track = s.timelines[s.activeTimeline].tracks[found.trackIndex];
        const clip = found.clip;
        const tail = {
          ...structuredClone(clip),
          id: crypto.randomUUID(),
          start: p.start,
          duration: Math.max(0.05, clip.start + clip.duration - p.end),
          sourceIn: (clip.sourceIn ?? 0) + (p.end - clip.start),
        };
        clip.duration = Math.max(0.05, p.start - clip.start);
        track.clips.splice(track.clips.indexOf(clip) + 1, 0, tail);
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "edit.roll":
      case "edit.slip":
      case "edit.slide": {
        // The Pro tab's trims on one clip, by delta seconds. Roll moves the edit point after it (it lengthens, the
        // next clip starts later and plays on from further in its source). Slip moves which part of its source plays
        // (same place, same length). Slide moves it between its neighbours (the one before meets it, the one after
        // starts with it, its source moved on). Refused, with nothing changed, if a clip would fall under 0.05 s or a
        // source would be read from before its start.
        const p = payload as { clipId: string; delta: number };
        const found = this.findClip(p.clipId);
        const delta = Number(p.delta) || 0;
        if (!found || Math.abs(delta) < 1e-6) break;
        const clips = [...s.timelines[s.activeTimeline].tracks[found.trackIndex].clips].sort((a, b) => a.start - b.start);
        const clip = found.clip;
        const at = clips.indexOf(clip);
        const touching = (a?: Clip, b?: Clip) => !!a && !!b && Math.abs(a.start + a.duration - b.start) < 0.01;
        const before = touching(clips[at - 1], clip) ? clips[at - 1] : undefined;
        const after = touching(clip, clips[at + 1]) ? clips[at + 1] : undefined;
        const MIN = 0.05;
        if (command === "edit.roll") {
          if (!after || clip.duration + delta < MIN || after.duration - delta < MIN || (after.sourceIn ?? 0) + delta < 0) break;
          this.pushHistory();
          clip.duration += delta;
          after.start += delta;
          after.duration -= delta;
          after.sourceIn = (after.sourceIn ?? 0) + delta;
        } else if (command === "edit.slip") {
          if ((clip.sourceIn ?? 0) + delta < 0) break;
          this.pushHistory();
          clip.sourceIn = (clip.sourceIn ?? 0) + delta;
        } else {
          const room = { start: clips[at - 1] && !before ? clips[at - 1].start + clips[at - 1].duration : 0, end: clips[at + 1] && !after ? clips[at + 1].start : Infinity };
          if (clip.start + delta < room.start - 1e-6 || clip.start + clip.duration + delta > room.end + 1e-6) break;
          if (before && before.duration + delta < MIN) break;
          if (after && (after.duration - delta < MIN || (after.sourceIn ?? 0) + delta < 0)) break;
          this.pushHistory();
          clip.start += delta;
          if (before) before.duration += delta;
          if (after) {
            after.start += delta;
            after.duration -= delta;
            after.sourceIn = (after.sourceIn ?? 0) + delta;
          }
        }
        for (const each of [clip, before, after]) {
          if (!each) continue;
          each.start = Math.round(each.start * 1000) / 1000;
          each.duration = Math.round(each.duration * 1000) / 1000;
          if (each.sourceIn !== undefined) each.sourceIn = Math.round(each.sourceIn * 1000) / 1000;
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "edit.lift":
      case "edit.overwrite":
      case "edit.insert": {
        // The Pro tab's three-point edits. Lift takes [start, end) out of every track (or the ones named) and leaves
        // the gap; overwrite replaces the target track's range with the source clip; insert cuts every track at the
        // edit point and moves what follows later by the source's length (tracks stay in sync), then places the clip.
        // Extract is timeline.cut-range.
        const p = payload as { start?: number; end?: number; tracks?: number[]; trackIndex?: number; clip?: Clip };
        const tracks = s.timelines[s.activeTimeline].tracks;
        const forget = (ids: string[]) => {
          for (const id of ids) {
            if (s.selectedClipId === id) s.selectedClipId = null;
            const at = s.selection.indexOf(id);
            if (at >= 0) s.selection.splice(at, 1);
          }
        };
        if (command === "edit.lift") {
          const start = Math.max(0, Math.min(p.start ?? 0, p.end ?? 0));
          const end = Math.max(p.start ?? 0, p.end ?? 0);
          if (end - start <= 0.01) break;
          this.pushHistory();
          tracks.forEach((track, index) => {
            if (track.locked || (p.tracks && !p.tracks.includes(index))) return;
            const { kept, removed } = carveRange(track.clips, start, end);
            track.clips = kept;
            forget(removed);
          });
          this.range = null;
          s.saved = false;
          this.emit("clips");
          break;
        }
        const target = tracks[p.trackIndex ?? -1];
        const clip = p.clip;
        if (!target || target.locked || !clip || clip.duration <= 0.01) break;
        this.pushHistory();
        if (command === "edit.overwrite") {
          const { kept, removed } = carveRange(target.clips, clip.start, clip.start + clip.duration);
          target.clips = kept;
          forget(removed);
        } else {
          const at = clip.start;
          const length = clip.duration;
          for (const track of tracks) {
            if (track.locked) continue;
            const next: Clip[] = [];
            for (const each of track.clips) {
              const eachEnd = each.start + each.duration;
              if (eachEnd <= at + 1e-6) {
                next.push(each);
              } else if (each.start >= at - 1e-6) {
                each.start = Math.round((each.start + length) * 1000) / 1000;
                next.push(each);
              } else {
                next.push(each, {
                  ...structuredClone(each),
                  id: crypto.randomUUID(),
                  start: Math.round((at + length) * 1000) / 1000,
                  duration: eachEnd - at,
                  sourceIn: (each.sourceIn ?? 0) + (at - each.start),
                } as Clip);
                each.duration = at - each.start;
              }
            }
            track.clips = next;
          }
        }
        target.clips.push(clip);
        target.clips.sort((a, b) => a.start - b.start);
        s.selectedClipId = clip.id;
        s.selection = [clip.id];
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "range.set": {
        const p = payload as { start: number; end: number };
        const start = Math.max(0, Math.min(p.start, p.end));
        const end = Math.min(s.duration, Math.max(p.start, p.end));
        if (!(end - start > 0.01)) break;
        this.range = { start: Math.round(start * 1000) / 1000, end: Math.round(end * 1000) / 1000, timeline: s.activeTimeline };
        this.emit("timeline");
        break;
      }
      case "range.clear":
        if (!this.range) break;
        this.range = null;
        this.emit("timeline");
        break;
      case "timeline.cut-range": {
        // Extract: a span of the timeline goes, on every track.
        // A clip inside the span is removed, one straddling it is cut into a
        // head and a tail, and everything after it moves back by the length.
        const p = payload as { start: number; end: number };
        const start = Math.max(0, Math.min(p.start, p.end));
        const length = Math.max(0, Math.max(p.start, p.end) - start);
        if (length <= 0.01) break;
        const end = start + length;
        this.pushHistory();
        for (const track of s.timelines[s.activeTimeline].tracks) {
          if (track.locked) continue;
          const kept: Clip[] = [];
          for (const clip of track.clips) {
            const clipEnd = clip.start + clip.duration;
            if (clipEnd <= start + 1e-6) { kept.push(clip); continue; }
            if (clip.start >= end - 1e-6) { clip.start = Math.round((clip.start - length) * 1000) / 1000; kept.push(clip); continue; }
            if (clip.start >= start - 1e-6 && clipEnd <= end + 1e-6) {
              if (s.selectedClipId === clip.id) s.selectedClipId = null;
              const inSet = s.selection.indexOf(clip.id);
              if (inSet >= 0) s.selection.splice(inSet, 1);
              continue;
            }
            if (clip.start < start && clipEnd > end) {
              const tail = {
                ...structuredClone(clip),
                id: crypto.randomUUID(),
                start,
                duration: Math.max(0.05, clipEnd - end),
                sourceIn: (clip.sourceIn ?? 0) + (end - clip.start),
              };
              clip.duration = Math.max(0.05, start - clip.start);
              kept.push(clip, tail);
              continue;
            }
            if (clip.start < start) {
              clip.duration = Math.max(0.05, start - clip.start);
              kept.push(clip);
              continue;
            }
            clip.sourceIn = (clip.sourceIn ?? 0) + (end - clip.start);
            clip.duration = Math.max(0.05, clipEnd - end);
            clip.start = start;
            kept.push(clip);
          }
          track.clips = kept;
        }
        if (s.playhead > start) s.playhead = Math.max(start, s.playhead - length);
        this.range = null;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.smooth-slow": {
        const p = payload as { clipId: string; on: boolean };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.on) found.clip.smoothSlow = true; else delete found.clip.smoothSlow;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.effects": {
        const p = payload as { clipId: string; effects: Array<{ id: string; amount?: number; params?: Record<string, number> }> };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        found.clip.effects = p.effects.slice(0, 24).map((entry) => ({ amount: 100, ...entry }));
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "timeline.move": {
        const p = payload as { from: number; to: number };
        const list = s.timelines;
        if (!list[p.from] || !list[p.to] || p.from === p.to) break;
        this.pushHistory();
        const [moved] = list.splice(p.from, 1);
        list.splice(p.to, 0, moved);
        // The active timeline follows the one the person is dragging.
        if (s.activeTimeline === p.from) s.activeTimeline = p.to;
        else if (p.from < s.activeTimeline && p.to >= s.activeTimeline) s.activeTimeline -= 1;
        else if (p.from > s.activeTimeline && p.to <= s.activeTimeline) s.activeTimeline += 1;
        s.saved = false;
        this.emit("timeline");
        this.emit("project");
        break;
      }
      case "timeline.rename": {
        const p = payload as { index: number; name: string };
        const target = s.timelines[p.index];
        if (!target) break;
        const next = String(p.name).trim().slice(0, 18);
        if (!next || next === target.name) break;
        this.pushHistory();
        target.name = next;
        s.saved = false;
        this.emit("timeline");
        this.emit("project");
        break;
      }
      case "timeline.activate":
        if (!s.timelines[Number(payload)]) break;
        this.pause();
        s.activeTimeline = Number(payload);
        {
          const active = s.timelines[s.activeTimeline];
          s.width = active.width ?? this.baseFormat.width;
          s.height = active.height ?? this.baseFormat.height;
          s.fps = active.fps ?? this.baseFormat.fps;
          s.aspect = `${s.width}:${s.height}`;
        }
        s.duration = Math.max(0.1, ...s.timelines[s.activeTimeline].tracks.flatMap(t => t.clips.map(c => c.start + c.duration)));
        s.playhead = Math.min(s.playhead, s.duration);
        s.selectedClipId = null;
        s.selection = [];
        this.emit("timeline");
        this.emit("clip-selection");
        this.emit("playhead");
        break;
      case "clip.colour": {
        // The Color section: a patch to the colour panel, a whole grade, or null to reset either.
        const p = payload as { clipId: string; colour?: Partial<import("./types").ColourPanel> | null; grade?: import("./types").ColorGrade | null };
        const found = this.findClip(p.clipId);
        if (!found) break;
        const parts = [p.colour ? Object.keys(p.colour).sort().join(",") : String(p.colour), p.grade === undefined ? "" : "grade"];
        this.pushHistory(`clip.colour:${p.clipId}:${parts.join(":")}`);
        if (p.colour === null) found.clip.colour = undefined;
        else if (p.colour) found.clip.colour = { ...(found.clip.colour ?? {}), ...p.colour };
        if (p.grade === null) found.clip.colorGrade = undefined;
        else if (p.grade) found.clip.colorGrade = structuredClone(p.grade);
        s.saved = false;
        this.emit("clips");
        break;
      }
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
        if (s.selectedClipId === next && s.selection.length <= 1) break;
        s.selectedClipId = next;
        s.selection = next ? [next] : [];
        this.emit("clip-selection");
        break;
      }
      case "clip.select-toggle": {
        const id = payload as string;
        if (!this.findClip(id)) break;
        const at = s.selection.indexOf(id);
        if (at >= 0) s.selection.splice(at, 1);
        else s.selection.push(id);
        s.selectedClipId = s.selection.length ? s.selection[s.selection.length - 1] : null;
        this.emit("clip-selection");
        break;
      }
      case "clip.select-set": {
        const ids = (payload as string[]).filter((id) => this.findClip(id));
        if (ids.length === s.selection.length && ids.every((id, i) => s.selection[i] === id)) break;
        s.selection = ids;
        s.selectedClipId = ids.length ? ids[ids.length - 1] : null;
        this.emit("clip-selection");
        break;
      }
      case "clip.select-all": {
        const tracks = s.timelines[s.activeTimeline].tracks;
        const ids = tracks.filter((track) => !track.locked).flatMap((track) => track.clips.map((clip) => clip.id));
        s.selection = ids;
        s.selectedClipId = ids.length ? ids[ids.length - 1] : null;
        this.emit("clip-selection");
        break;
      }
      case "clips.move": {
        const p = payload as { clipIds: string[]; deltaStart: number; deltaTrack?: number };
        const tracks = s.timelines[s.activeTimeline].tracks;
        const dTrack = p.deltaTrack ?? 0;
        const members = p.clipIds.map((id) => this.findClip(id)).filter((m): m is NonNullable<typeof m> => !!m);
        if (!members.length) break;
        const blocked = members.some((m) => {
          const target = m.trackIndex + dTrack;
          return tracks[m.trackIndex].locked || !tracks[target] || tracks[target].locked || m.clip.start + p.deltaStart < 0;
        });
        if (blocked) break;
        this.pushHistory();
        for (const m of members) {
          if (dTrack !== 0) {
            const from = tracks[m.trackIndex].clips;
            from.splice(from.indexOf(m.clip), 1);
            tracks[m.trackIndex + dTrack].clips.push(m.clip);
          }
          m.clip.start = Math.max(0, Math.round((m.clip.start + p.deltaStart) * 100) / 100);
          s.duration = Math.max(s.duration, m.clip.start + m.clip.duration);
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clips.remove": {
        const ids = payload as string[];
        const members = ids.map((id) => this.findClip(id)).filter((m): m is NonNullable<typeof m> => !!m);
        const tracks = s.timelines[s.activeTimeline].tracks;
        const doable = members.filter((m) => !tracks[m.trackIndex].locked);
        if (!doable.length) break;
        this.pushHistory();
        for (const m of doable) {
          const clips = tracks[m.trackIndex].clips;
          clips.splice(clips.indexOf(m.clip), 1);
        }
        s.selection = s.selection.filter((id) => !doable.some((m) => m.clip.id === id));
        if (s.selectedClipId && doable.some((m) => m.clip.id === s.selectedClipId)) s.selectedClipId = s.selection.length ? s.selection[s.selection.length - 1] : null;
        s.saved = false;
        this.emit("clips");
        this.emit("clip-selection");
        break;
      }
      case "clips.duplicate": {
        const ids = payload as string[];
        const tracks = s.timelines[s.activeTimeline].tracks;
        const members = ids.map((id) => this.findClip(id)).filter((m): m is NonNullable<typeof m> => !!m && !tracks[m.trackIndex].locked);
        if (!members.length) break;
        this.pushHistory();
        const made: string[] = [];
        for (const m of members) {
          const copy = structuredClone(m.clip);
          copy.id = crypto.randomUUID();
          copy.start = m.clip.start + m.clip.duration;
          tracks[m.trackIndex].clips.push(copy);
          s.duration = Math.max(s.duration, copy.start + copy.duration);
          made.push(copy.id);
        }
        s.selection = made;
        s.selectedClipId = made[made.length - 1];
        s.saved = false;
        this.emit("clips");
        this.emit("clip-selection");
        break;
      }
      case "clips.add": {
        const p = payload as { entries: Array<{ trackIndex: number; clip: import("./types").Clip }> };
        const tracks = s.timelines[s.activeTimeline].tracks;
        const doable = p.entries.filter((entry) => tracks[entry.trackIndex] && !tracks[entry.trackIndex].locked);
        if (!doable.length) break;
        this.pushHistory();
        const made: string[] = [];
        for (const entry of doable) {
          tracks[entry.trackIndex].clips.push(entry.clip);
          s.duration = Math.max(s.duration, entry.clip.start + entry.clip.duration);
          made.push(entry.clip.id);
        }
        s.selection = made;
        s.selectedClipId = made[made.length - 1];
        s.saved = false;
        this.emit("clips");
        this.emit("clip-selection");
        break;
      }
      case "clips.mute": {
        const p = payload as { clipIds: string[]; muted: boolean };
        const tracks = s.timelines[s.activeTimeline].tracks;
        const members = p.clipIds.map((id) => this.findClip(id)).filter((m): m is NonNullable<typeof m> => !!m && !tracks[m.trackIndex].locked);
        if (!members.length) break;
        this.pushHistory();
        for (const m of members) m.clip.muted = p.muted || undefined;
        s.saved = false;
        this.emit("clips");
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
        const offset = Math.round((p.time - found.clip.start) * 100) / 100;
        if (offset < 0.1 || offset > found.clip.duration - 0.1) break;
        this.pushHistory();
        const tail = this.splitOne(found.clip, found.trackIndex, offset);
        s.selectedClipId = tail.id;
        s.selection = [tail.id];
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clip.angle": {
        // Multicam: switch a compound clip to an angle. With the playhead
        // inside the clip the cut happens there and the tail takes the angle,
        // which is how an editor switches cameras while the take plays; at the
        // clip's edges, or when asked not to cut, the whole clip switches.
        const p = payload as { clipId: string; angle: number | null; audioAngle?: number | null; atPlayhead?: boolean };
        const found = this.findClip(p.clipId);
        if (!found || found.clip.kind !== "timeline") break;
        this.pushHistory();
        let target = found.clip;
        const offset = Math.round((s.playhead - found.clip.start) * 100) / 100;
        if (p.atPlayhead && offset >= 0.1 && offset <= found.clip.duration - 0.1) {
          target = this.splitOne(found.clip, found.trackIndex, offset);
          s.selectedClipId = target.id;
          s.selection = [target.id];
        }
        if (p.angle === null) delete target.angle;
        else if (p.angle !== undefined) target.angle = p.angle;
        if (p.audioAngle === null) delete target.audioAngle;
        else if (p.audioAngle !== undefined) target.audioAngle = p.audioAngle;
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "clips.split": {
        const p = payload as { clipIds: string[]; time: number };
        const tracks = s.timelines[s.activeTimeline].tracks;
        const cuttable = p.clipIds
          .map((id) => this.findClip(id))
          .filter((m): m is NonNullable<typeof m> => {
            if (!m || tracks[m.trackIndex].locked) return false;
            const offset = Math.round((p.time - m.clip.start) * 100) / 100;
            return offset >= 0.1 && offset <= m.clip.duration - 0.1;
          });
        if (!cuttable.length) break;
        this.pushHistory();
        const tails: string[] = [];
        for (const m of cuttable) {
          const offset = Math.round((p.time - m.clip.start) * 100) / 100;
          tails.push(this.splitOne(m.clip, m.trackIndex, offset).id);
        }
        s.selection = tails;
        s.selectedClipId = tails[tails.length - 1];
        s.saved = false;
        this.emit("clips");
        this.emit("clip-selection");
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
        const inSet = s.selection.indexOf(clipId);
        if (inSet >= 0) s.selection.splice(inSet, 1);
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
        delete (s as unknown as Record<string, unknown>).background;
        s.syncFolder = undefined;
        s.outputColour = undefined;
        this.range = null;
        Object.assign(s, structuredClone(p));
        s.revision = p.revision ?? 0;
        s.activeTimeline = s.timelines[p.activeTimeline ?? 0] ? (p.activeTimeline ?? 0) : 0;
        this.baseFormat = { width: s.width, height: s.height, fps: s.fps };
        {
          const active = s.timelines[s.activeTimeline];
          s.width = active.width ?? s.width;
          s.height = active.height ?? s.height;
          s.fps = active.fps ?? s.fps;
          s.aspect = `${s.width}:${s.height}`;
        }
        s.duration = Math.max(0.1, ...s.timelines[s.activeTimeline].tracks.flatMap(t => t.clips.map(c => c.start + c.duration)));
        s.playhead = 0;
        s.playing = false;
        s.selectedClipId = null;
        s.selection = [];
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
        this.emit("project");
        break;
      }
      case "clip.timing": {
        const p = payload as { clipId: string; speed?: number; fadeIn?: number; fadeOut?: number };
        const found = this.findClip(p.clipId);
        if (!found) break;
        this.pushHistory();
        if (p.speed !== undefined) {
          // The engine accepts 0.05x to 100x and the renderer honours it; the
          // interface was capping at 4x, so most of the range could not be
          // reached from the app at all.
          found.clip.speed = Math.min(100, Math.max(0.05, p.speed)) || 1;
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
        if (p.patch.content !== undefined) {
          found.clip.label = p.patch.content;
          // A caption's words follow its text (phase 9): the same token count
          // keeps the model's times word for word; a different count shares
          // the clip's span by character, the rule typed captions get.
          const words = found.clip.words;
          if (words?.length) {
            const tokens = p.patch.content.trim().split(/\s+/).filter(Boolean);
            if (tokens.length === words.length) {
              found.clip.words = words.map((word, i) => ({ ...word, text: tokens[i] }));
            } else {
              const total = tokens.reduce((sum, word) => sum + word.length + 1, 0) || 1;
              let at = 0;
              found.clip.words = tokens.map((text) => {
                const d = (found.clip.duration * (text.length + 1)) / total;
                const word = { text, t: Math.round(at * 1000) / 1000, d: Math.round(d * 1000) / 1000 };
                at += d;
                return word;
              });
            }
          }
        }
        s.saved = false;
        this.emit("clips");
        break;
      }
      case "captions.emphasise": {
        // Per-word emphasis: the listed words take a colour of their own on
        // every caption named; with no colour, every word gives its own up.
        const p = payload as { clipIds: string[]; words: string[]; colour: string | null };
        const wanted = new Set(p.words.map((w) => w.toLowerCase().replace(/[^\p{L}\p{N}']+/gu, "")).filter(Boolean));
        const targets = p.clipIds.map((id) => this.findClip(id)?.clip).filter((clip): clip is Clip => !!clip && clip.kind === "text" && !!clip.words?.length);
        if (!targets.length || (p.colour && !wanted.size)) break;
        this.pushHistory();
        for (const clip of targets) {
          clip.words = clip.words!.map((word) => {
            const key = word.text.toLowerCase().replace(/[^\p{L}\p{N}']+/gu, "");
            if (p.colour && wanted.has(key)) return { ...word, colour: p.colour };
            if (!p.colour && word.colour) { const { colour: _gone, ...rest } = word; return rest; }
            return word;
          });
        }
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
          // Every shape the renderer knows is accepted, including a drawn
          // path with its own anchors; the old clamp collapsed anything that
          // was not an ellipse into a rectangle.
          const shape = MASK_SHAPES.includes(p.mask.shape) ? p.mask.shape : "rect";
          found.clip.mask = {
            shape,
            x: cl(p.mask.x, 0, 100),
            y: cl(p.mask.y, 0, 100),
            w: cl(p.mask.w, 1, 100),
            h: cl(p.mask.h, 1, 100),
            feather: cl(p.mask.feather, 0, 50),
            angle: cl(p.mask.angle ?? 0, -360, 360),
            ...(p.mask.invert ? { invert: true } : {}),
            ...(shape === "path"
              ? { points: (p.mask.points ?? []).slice(0, 400).map((point) => ({
                  x: cl(point.x, -2, 3), y: cl(point.y, -2, 3),
                  ...(point.inX || point.inY ? { inX: cl(point.inX ?? 0, -3, 3), inY: cl(point.inY ?? 0, -3, 3) } : {}),
                  ...(point.outX || point.outY ? { outX: cl(point.outX ?? 0, -3, 3), outY: cl(point.outY ?? 0, -3, 3) } : {}),
                })) }
              : {}),
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
            ...(p.key.spill ? { spill: Math.min(1, Math.max(0, p.key.spill)) } : {}),
            ...(p.key.mode === "difference" ? { mode: "difference" as const } : {}),
            ...(p.key.holdout?.length ? { holdout: p.key.holdout.filter((id) => typeof id === "string") } : {}),
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
      case "clip.keyframes.replace": {
        // The whole set at once, for a drag. Replacing rather than removing and
        // re-adding is what stops a keyframe being destroyed because something
        // was dragged across it; `quiet` keeps one history entry per gesture
        // instead of one per pointer move.
        const p = payload as { clipId: string; keyframes: ClipKeyframe[]; quiet?: boolean };
        const found = this.findClip(p.clipId);
        if (!found) break;
        if (!p.quiet) this.pushHistory();
        found.clip.keyframes = p.keyframes
          .filter((frame) => frame && frame.props && Object.keys(frame.props).length)
          .map((frame) => ({ ...frame, t: Math.max(0, Math.min(found.clip.duration, frame.t)) }))
          .sort((a, b) => a.t - b.t);
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
      case "project.sync-folder": {
        // Opt-in sync: the folder this project's package is written to on every save, or none.
        const next = String(payload ?? "").trim();
        if ((s.syncFolder ?? "") === next) break;
        s.syncFolder = next || undefined;
        s.saved = false;
        this.emit("project");
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
        this.settlePending();
        this.foldKey = null;
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
    for (const prop of ["posX", "posY", "scale", "rotation", "opacity"] as TransformProp[]) {
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

  /** Playback wraps at the end until the person stops it. */
  looping = true;

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
      // Playback loops rather than stopping at the end: it runs until the person
      // stops it with the spacebar or the play button. A work area loops to its
      // own start; otherwise the whole timeline wraps to the beginning. The wrap
      // re-emits transport so anything driving the clock, the audio mixer in
      // particular, re-schedules from the new position instead of running on
      // past the end and dragging the playhead with it.
      const end = this.workArea ? this.workArea.end : this.state.duration;
      const start = this.workArea ? this.workArea.start : 0;
      if (this.state.playhead >= end) {
        if (this.looping) {
          this.state.playhead = start;
          this.lastTick = now;
          this.emit("transport");
        } else {
          this.state.playhead = end;
          this.pause();
        }
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
