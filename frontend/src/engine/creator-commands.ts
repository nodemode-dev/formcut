import type { Clip, ProjectState } from "./types";
import { motionKeys } from "./motion";
import { SPEED_PRESETS, speedPoints, sourceTime, shiftedCurve, retimedKeys } from "./timing";

export const CREATOR_COMMANDS = new Set(["clip.speed-curve", "clip.motion", "clip.creator", "clip.detach", "clip.ripple-delete", "clip.rejoin", "clip.freeze-insert", "track.add", "track.remove", "track.update", "timeline.add", "timeline.remove", "project.settings"]);

/** Whether the given clips form a rejoinable chain; the reason key names why not. */
export function rejoinEligibility(state: ProjectState, clipIds: string[]): { ok: true; ordered: Clip[]; trackIndex: number } | { ok: false, reason: string } {
  if (clipIds.length < 2) return { ok: false, reason: "rejoin.need-two" };
  const timeline = state.timelines[state.activeTimeline];
  const spots = clipIds.map((id) => {
    const trackIndex = timeline.tracks.findIndex((track) => track.clips.some((c) => c.id === id));
    return trackIndex < 0 ? null : { trackIndex, clip: timeline.tracks[trackIndex].clips.find((c) => c.id === id)! };
  });
  if (spots.some((s) => !s)) return { ok: false, reason: "rejoin.need-two" };
  const trackIndex = spots[0]!.trackIndex;
  if (spots.some((s) => s!.trackIndex !== trackIndex)) return { ok: false, reason: "rejoin.one-track" };
  if (timeline.tracks[trackIndex].locked) return { ok: false, reason: "rejoin.locked" };
  const ordered = spots.map((s) => s!.clip).sort((a, b) => a.start - b.start);
  const media = ordered[0].mediaId;
  if (ordered.some((c) => c.mediaId !== media)) return { ok: false, reason: "rejoin.same-media" };
  const shape = JSON.stringify([ordered[0].speed ?? 1]);
  if (ordered.some((c) => c.speedCurve?.length || JSON.stringify([c.speed ?? 1]) !== shape)) return { ok: false, reason: "rejoin.same-speed" };
  for (let i = 1; i < ordered.length; i += 1) {
    const prev = ordered[i - 1], next = ordered[i];
    if (Math.abs(prev.start + prev.duration - next.start) > 0.02) return { ok: false, reason: "rejoin.adjacent" };
    if (Math.abs(sourceTime(prev, prev.duration) - (next.sourceIn ?? 0)) > 0.02) return { ok: false, reason: "rejoin.contiguous" };
  }
  return { ok: true, ordered, trackIndex };
}

export function creatorCommand(state: ProjectState, command: string, data: unknown): void {
  const p = data as Record<string, unknown>;
  const timeline = state.timelines[state.activeTimeline];
  if (command === "clip.rejoin") {
    const verdict = rejoinEligibility(state, p.clipIds as string[]);
    if (!verdict.ok) throw new Error(verdict.reason);
    const { ordered, trackIndex } = verdict;
    const first = ordered[0];
    const last = ordered[ordered.length - 1];
    let at = first.duration;
    const merged = [...(first.keyframes ?? [])];
    for (const piece of ordered.slice(1)) {
      for (const key of piece.keyframes ?? []) merged.push({ ...structuredClone(key), t: key.t + at });
      at += piece.duration;
    }
    first.duration = Math.round((last.start + last.duration - first.start) * 100) / 100;
    first.keyframes = merged.length ? merged.sort((a, b) => a.t - b.t) : undefined;
    first.fadeOut = last.fadeOut;
    const track = timeline.tracks[trackIndex];
    const gone = new Set(ordered.slice(1).map((c) => c.id));
    track.clips = track.clips.filter((c) => !gone.has(c.id));
    state.selection = [first.id];
    state.selectedClipId = first.id;
    state.saved = false;
    return;
  }
  const clip = timeline.tracks.flatMap(t => t.clips).find(c => c.id === p.clipId);
  if (command.startsWith("clip.") && !clip) throw new Error("Select a clip first");
  if (command === "clip.freeze-insert") {
    const source = clip!;
    const track = timeline.tracks.find((t) => t.clips.includes(source))!;
    if (track.locked) throw new Error("The track is locked");
    const hold = Math.max(0.1, Number(p.hold ?? 3));
    const at = Number(p.time);
    const offset = Math.round((at - source.start) * 100) / 100;
    if (offset < 0.1 || offset > source.duration - 0.1) throw new Error("Place the playhead inside the clip");
    const tail = {
      ...structuredClone(source),
      sourceIn: sourceTime(source, offset),
      speedCurve: shiftedCurve(source, offset, source.duration - offset),
      keyframes: retimedKeys(source.keyframes, offset, source.duration - offset),
      transitionIn: undefined,
      fadeIn: 0,
      id: crypto.randomUUID(),
      start: Math.round((source.start + offset + hold) * 100) / 100,
      duration: Math.round((source.duration - offset) * 100) / 100,
    };
    source.duration = Math.round(offset * 100) / 100;
    source.fadeOut = 0;
    const cut = source.start + source.duration;
    for (const other of track.clips) if (other !== source && other.start >= cut - 0.005) other.start = Math.round((other.start + hold) * 100) / 100;
    const still: Clip = {
      id: crypto.randomUUID(),
      kind: "image",
      label: String(p.label || "Freeze frame"),
      mediaId: String(p.mediaId),
      start: cut,
      duration: hold,
      transform: structuredClone(source.transform),
    };
    track.clips.splice(track.clips.indexOf(source) + 1, 0, tail);
    track.clips.splice(track.clips.indexOf(source) + 1, 0, still);
    state.selection = [still.id];
    state.selectedClipId = still.id;
    state.saved = false;
    return;
  }
  if (command === "clip.ripple-delete") {
    const item = clip!, track = timeline.tracks.find(track => track.clips.includes(item))!;
    const end = item.start + item.duration;
    track.clips = track.clips.filter(other => other !== item);
    for (const other of track.clips) if (other.start >= end) other.start -= item.duration;
    state.selectedClipId = null; state.saved = false;
    return;
  }
  if (command === "clip.speed-curve") {
    const c = clip!;
    if (p.preset) {
      const preset = SPEED_PRESETS[String(p.preset)];
      if (!preset) throw new Error("Unknown speed preset");
      c.speedCurve = preset.map(([t, speed]) => ({ t: t * c.duration, speed }));
    } else {
      const points = p.points as Clip["speedCurve"];
      if (!Array.isArray(points) || points.length > 256 || points.some(k => !Number.isFinite(k.t) || !Number.isFinite(k.speed) || k.t < 0 || k.t > c.duration || k.speed < 0.05 || k.speed > 16)) throw new Error("Speed points need valid times and rates from 0.05 to 16");
      c.speedCurve = points.length ? speedPoints({ ...c, speedCurve: points }) : undefined;
    }
  } else if (command === "clip.motion") {
    const keys = motionKeys(clip!, String(p.preset), Number(p.duration ?? 1));
    const props = new Set(keys.flatMap(k => Object.keys(k.props)));
    const retained = (clip!.keyframes ?? []).map(k => ({ ...k, props: Object.fromEntries(Object.entries(k.props).filter(([key]) => !props.has(key))) })).filter(k => Object.keys(k.props).length);
    clip!.keyframes = [...retained, ...keys].sort((a, b) => a.t - b.t);
  } else if (command === "clip.creator") {
    const values = p.patch as Partial<Clip>;
    const allowed = ["effects", "lutId", "shaderId", "expressions", "cutout", "volume", "pan", "audioEffects", "sourceIn", "reversed"] as const;
    for (const key of allowed) if (key in values) Object.assign(clip!, { [key]: structuredClone(values[key]) });
  } else if (command === "clip.detach") {
    const audio = structuredClone(clip!);
    audio.id = crypto.randomUUID(); audio.kind = "audio"; audio.mediaId = String(p.mediaId); audio.label = String(p.label);
    audio.muted = false; audio.effects = undefined; audio.effectId = undefined; audio.cutout = undefined; audio.shaderId = undefined; audio.lutId = undefined;
    let target = timeline.tracks.find(t => /audio/i.test(t.name) && !t.locked);
    if (!target) { target = { id: crypto.randomUUID(), name: "Audio", clips: [] }; timeline.tracks.push(target); }
    target.clips.push(audio); clip!.muted = true;
  } else if (command === "track.update") {
    const target = timeline.tracks[Number(p.index)]; if (!target) throw new Error("Track not found");
    const patch = p.patch as { name?: string; locked?: boolean; hidden?: boolean; muted?: boolean };
    if (patch.name !== undefined) target.name = patch.name.trim().slice(0, 120) || "Track";
    for (const key of ["locked", "hidden", "muted"] as const) if (key in patch) target[key] = Boolean(patch[key]);
  } else if (command === "track.add") {
    timeline.tracks.push({ id: crypto.randomUUID(), name: String(p.name || `Track ${timeline.tracks.length + 1}`), clips: [] });
  } else if (command === "track.remove") {
    const index = Number(p.index);
    if (timeline.tracks.length < 2 || !timeline.tracks[index]) throw new Error("Keep at least one track");
    timeline.tracks.splice(index, 1);
  } else if (command === "timeline.add") {
    state.timelines.push({ id: crypto.randomUUID(), name: String(p.name || `Timeline ${state.timelines.length + 1}`), tracks: [{ id: crypto.randomUUID(), name: "Video", clips: [] }, { id: crypto.randomUUID(), name: "Audio", clips: [] }] });
    state.activeTimeline = state.timelines.length - 1;
    state.selectedClipId = null;
  } else if (command === "timeline.remove") {
    const index = Number(p.index);
    if (state.timelines.length < 2 || !state.timelines[index]) throw new Error("Keep at least one timeline");
    state.timelines.splice(index, 1);
    state.activeTimeline = Math.min(state.activeTimeline, state.timelines.length - 1);
    state.selectedClipId = null;
  } else if (command === "project.settings") {
    for (const key of ["width", "height", "fps"] as const) {
      if (p[key] === undefined) continue;
      const value = Number(p[key]);
      const low = key === "fps" ? 1 : 16, high = key === "fps" ? 120 : 7680;
      if (!Number.isInteger(value) || value < low || value > high) throw new Error(`Invalid ${key}`);
      state[key] = value;
    }
    state.aspect = `${state.width}:${state.height}`;
  }
  state.saved = false;
}
