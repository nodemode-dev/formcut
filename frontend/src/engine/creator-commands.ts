import type { Clip, ProjectState } from "./types";
import { motionKeys } from "./motion";
import { SPEED_PRESETS, speedPoints } from "./timing";

export const CREATOR_COMMANDS = new Set(["clip.speed-curve", "clip.motion", "clip.creator", "clip.detach", "clip.ripple-delete", "track.add", "track.remove", "track.update", "timeline.add", "timeline.remove", "project.settings"]);

export function creatorCommand(state: ProjectState, command: string, data: unknown): void {
  const p = data as Record<string, unknown>;
  const timeline = state.timelines[state.activeTimeline];
  const clip = timeline.tracks.flatMap(t => t.clips).find(c => c.id === p.clipId);
  if (command.startsWith("clip.") && !clip) throw new Error("Select a clip first");
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
    const allowed = ["effects", "lutId", "shaderId", "expressions", "cutout", "volume", "pan", "audioEffects", "sourceIn"] as const;
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
