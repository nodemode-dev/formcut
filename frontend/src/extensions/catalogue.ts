import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { api } from "../engine/api";
import { captionLook, wordTimes } from "../engine/captions";
import { defaultTextStyle, defaultTransform, type Clip, type ClipTransition, type ProjectState } from "../engine/types";
import { ERR, HostError } from "./host-bridge";

type Args = Record<string, unknown>;
type Kind = "edit" | "view" | "analysis";
interface Entry {
  id: string;
  title: string;
  args: string;
  kind: Kind;
  run: (engine: ProjectEngine, bin: MediaBin, a: Args) => unknown;
}

const TRANSITIONS = new Set<ClipTransition["type"]>(["crossfade", "dip", "wipe-left", "wipe-right", "wipe-up", "wipe-down", "slide-left", "slide-right", "zoom", "iris", "dissolve", "push-up", "push-down", "cover-left", "cover-up", "clock-wipe", "blinds", "diagonal-wipe", "pixel-dissolve", "blur-fade", "spin", "diamond", "barn-door"]);
const COLOUR_KEYS = ["temperature", "tint", "saturation", "exposure", "brightness", "contrast", "highlights", "shadows", "whites", "blacks", "sharpen", "fade", "vignette"];
const TRANSFORM_KEYS = ["scale", "posX", "posY", "rotation", "opacity", "width", "height"];
const TEXT_KEYS = ["content", "size", "color", "bold", "align"];

const invalid = (message: string) => new HostError(ERR.INVALID, message);
const refused = (message: string) => new HostError(ERR.REFUSED, message);

function num(a: Args, key: string, fallback?: number): number {
  const v = a[key];
  if (v === undefined && fallback !== undefined) return fallback;
  if (typeof v !== "number" || !Number.isFinite(v)) throw invalid(`${key} must be a number`);
  return v;
}

function str(a: Args, key: string, optional = false): string | undefined {
  const v = a[key];
  if (v === undefined && optional) return undefined;
  if (typeof v !== "string" || !v) throw invalid(`${key} must be text`);
  return v;
}

function ids(a: Args, key: string): string[] {
  const v = a[key];
  if (!Array.isArray(v) || !v.length || v.some((x) => typeof x !== "string")) throw invalid(`${key} must be a list of ids`);
  return v as string[];
}

function pick(source: unknown, keys: string[]): Record<string, unknown> {
  if (!source || typeof source !== "object") throw invalid("patch must be an object");
  const out: Record<string, unknown> = {};
  for (const k of keys) if (k in (source as Record<string, unknown>)) out[k] = (source as Record<string, unknown>)[k];
  return out;
}

function tracks(engine: ProjectEngine) {
  const s = engine.snapshot;
  return s.timelines[s.activeTimeline].tracks;
}

function track(engine: ProjectEngine, index: number) {
  const target = tracks(engine)[index];
  if (!target) throw refused(`there is no track ${index}`);
  if (target.locked) throw refused(`track ${index + 1} (${target.name}) is locked`);
  return target;
}

function clip(engine: ProjectEngine, id: string) {
  const found = engine.findClip(id);
  if (!found) throw refused(`there is no clip ${id} on the open timeline`);
  if (tracks(engine)[found.trackIndex].locked) throw refused(`clip ${id} is on a locked track`);
  return found;
}

function changed(engine: ProjectEngine, touched: () => number, before: number, what: string) {
  if (touched() === before) throw refused(`formcut could not ${what}`);
}

const ENTRIES: Entry[] = [
  { id: "marker.add", title: "Add a marker", args: "{ t, note?, colour? }", kind: "edit", run: (engine, _b, a) => {
    const t = num(a, "t");
    const timeline = engine.snapshot.timelines[engine.snapshot.activeTimeline];
    const had = new Set((timeline.markers ?? []).map((m) => m.id));
    engine.dispatch("marker.add", { t, note: str(a, "note", true), colour: str(a, "colour", true) });
    return { markerId: (timeline.markers ?? []).find((m) => !had.has(m.id))?.id ?? null };
  } },
  { id: "marker.update", title: "Change a marker", args: "{ id, t?, note?, colour? }", kind: "edit", run: (engine, _b, a) => {
    engine.dispatch("marker.update", { id: str(a, "id"), t: a.t === undefined ? undefined : num(a, "t"), note: str(a, "note", true), colour: str(a, "colour", true) });
    return {};
  } },
  { id: "marker.remove", title: "Remove a marker", args: "{ id }", kind: "edit", run: (engine, _b, a) => {
    engine.dispatch("marker.remove", { id: str(a, "id") });
    return {};
  } },
  { id: "clip.add", title: "Add a library item to a track", args: "{ trackIndex, mediaId, start, duration?, sourceIn?, label? }", kind: "edit", run: (engine, bin, a) => {
    const trackIndex = num(a, "trackIndex");
    track(engine, trackIndex);
    const item = bin.find(str(a, "mediaId")!);
    if (!item) throw refused(`there is no media ${String(a.mediaId)} in the library`);
    const sourceIn = Math.max(0, num(a, "sourceIn", 0));
    const length = item.duration > 0 ? item.duration - sourceIn : 5;
    const duration = num(a, "duration", length);
    if (!(duration >= 0.1)) throw invalid("duration must be at least 0.1 s");
    const id = crypto.randomUUID();
    const added: Clip = { id, kind: item.kind, label: str(a, "label", true) ?? item.name, start: Math.max(0, num(a, "start")), duration, mediaId: item.id, sourceIn };
    if (item.kind === "video" || item.kind === "image") added.transform = defaultTransform();
    engine.dispatch("clip.add", { trackIndex, clip: added });
    return { clipId: id };
  } },
  { id: "text.add", title: "Add a title", args: "{ trackIndex, start, duration, text }", kind: "edit", run: (engine, _b, a) => {
    const trackIndex = num(a, "trackIndex");
    track(engine, trackIndex);
    const text = str(a, "text")!.slice(0, 2000);
    const id = crypto.randomUUID();
    engine.dispatch("clip.add", { trackIndex, clip: { id, kind: "text", label: text, start: Math.max(0, num(a, "start")), duration: Math.max(0.1, num(a, "duration")), textStyle: defaultTextStyle(text) } });
    return { clipId: id };
  } },
  { id: "captions.add", title: "Add captions", args: "{ trackIndex, cues: [{ start, end, text }] }", kind: "edit", run: (engine, _b, a) => {
    const trackIndex = num(a, "trackIndex");
    track(engine, trackIndex);
    if (!Array.isArray(a.cues) || a.cues.length > 5000) throw invalid("cues must be a list of at most 5000 { start, end, text }");
    const look = captionLook({ placement: "bottom", scale: "medium" });
    const clips: Clip[] = (a.cues as Args[]).map((cue) => {
      const start = Math.max(0, num(cue, "start"));
      const end = num(cue, "end");
      const text = str(cue, "text")!.slice(0, 2000);
      return { id: crypto.randomUUID(), kind: "text", label: text.split("\n")[0], start, duration: Math.max(0.1, Math.round((end - start) * 1000) / 1000), words: wordTimes({ text, start, end }), textStyle: { ...defaultTextStyle(text), size: look.size }, transform: { ...defaultTransform(), posY: look.posY } };
    });
    engine.dispatch("captions.add", { trackIndex, clips });
    return { clipIds: clips.map((c) => c.id) };
  } },
  { id: "clip.remove", title: "Remove a clip", args: "{ clipId }", kind: "edit", run: (engine, _b, a) => {
    engine.dispatch("clip.remove", clip(engine, str(a, "clipId")!).clip.id);
    return {};
  } },
  { id: "clips.remove", title: "Remove clips", args: "{ clipIds }", kind: "edit", run: (engine, _b, a) => {
    const list = ids(a, "clipIds");
    for (const id of list) clip(engine, id);
    engine.dispatch("clips.remove", list);
    return {};
  } },
  { id: "clip.split", title: "Split a clip", args: "{ clipId, time }", kind: "edit", run: (engine, _b, a) => {
    clip(engine, str(a, "clipId")!);
    engine.dispatch("clip.split", { clipId: a.clipId, time: num(a, "time") });
    return { clipId: engine.snapshot.selectedClipId };
  } },
  { id: "clips.split", title: "Split clips", args: "{ clipIds, time }", kind: "edit", run: (engine, _b, a) => {
    const list = ids(a, "clipIds");
    for (const id of list) clip(engine, id);
    engine.dispatch("clips.split", { clipIds: list, time: num(a, "time") });
    return { clipIds: [...engine.snapshot.selection] };
  } },
  { id: "clip.move", title: "Move a clip", args: "{ clipId, start, trackIndex? }", kind: "edit", run: (engine, _b, a) => {
    clip(engine, str(a, "clipId")!);
    if (a.trackIndex !== undefined) track(engine, num(a, "trackIndex"));
    engine.dispatch("clip.move", { clipId: a.clipId, start: num(a, "start"), trackIndex: a.trackIndex });
    return {};
  } },
  { id: "clips.move", title: "Move clips", args: "{ clipIds, deltaStart, deltaTrack? }", kind: "edit", run: (engine, _b, a) => {
    const list = ids(a, "clipIds");
    for (const id of list) clip(engine, id);
    engine.dispatch("clips.move", { clipIds: list, deltaStart: num(a, "deltaStart"), deltaTrack: num(a, "deltaTrack", 0) });
    return {};
  } },
  { id: "clip.trim", title: "Trim a clip", args: "{ clipId, start, duration }", kind: "edit", run: (engine, _b, a) => {
    clip(engine, str(a, "clipId")!);
    if (num(a, "duration") < 0.1) throw invalid("duration must be at least 0.1 s");
    engine.dispatch("clip.trim", { clipId: a.clipId, start: num(a, "start"), duration: num(a, "duration") });
    return {};
  } },
  { id: "clip.mute", title: "Mute or unmute a clip", args: "{ clipId, muted }", kind: "edit", run: (engine, _b, a) => {
    clip(engine, str(a, "clipId")!);
    engine.dispatch("clip.mute", { clipId: a.clipId, muted: Boolean(a.muted) });
    return {};
  } },
  { id: "clip.transition", title: "Set a clip's transition in", args: "{ clipId, type, duration } or { clipId, type: null }", kind: "edit", run: (engine, _b, a) => {
    clip(engine, str(a, "clipId")!);
    if (a.type === null) { engine.dispatch("clip.transition", { clipId: a.clipId, transition: null }); return {}; }
    if (!TRANSITIONS.has(a.type as ClipTransition["type"])) throw invalid(`type must be one of ${[...TRANSITIONS].join(", ")}`);
    engine.dispatch("clip.transition", { clipId: a.clipId, transition: { type: a.type, duration: num(a, "duration", 0.6) } });
    return {};
  } },
  { id: "clip.transform", title: "Change a clip's place, size or opacity", args: "{ clipId, patch: { scale?, posX?, posY?, rotation?, opacity? } }", kind: "edit", run: (engine, _b, a) => {
    clip(engine, str(a, "clipId")!);
    engine.dispatch("clip.transform", { clipId: a.clipId, patch: pick(a.patch, TRANSFORM_KEYS) });
    return {};
  } },
  { id: "clip.colour", title: "Change a clip's colour", args: "{ clipId, colour: { exposure?, contrast?, saturation?, temperature?, ... } } or colour: null", kind: "edit", run: (engine, _b, a) => {
    clip(engine, str(a, "clipId")!);
    engine.dispatch("clip.colour", { clipId: a.clipId, colour: a.colour === null ? null : pick(a.colour, COLOUR_KEYS) });
    return {};
  } },
  { id: "clip.text", title: "Change a title's text or style", args: "{ clipId, patch: { content?, size?, color?, bold?, align? } }", kind: "edit", run: (engine, _b, a) => {
    const found = clip(engine, str(a, "clipId")!);
    if (found.clip.kind !== "text") throw refused(`clip ${found.clip.id} is not a title or caption`);
    engine.dispatch("clip.text", { clipId: a.clipId, patch: pick(a.patch, TEXT_KEYS) });
    return {};
  } },
  { id: "track.add", title: "Add a track", args: "{ name? }", kind: "edit", run: (engine, _b, a) => {
    engine.dispatch("track.add", { name: str(a, "name", true) });
    return { trackIndex: tracks(engine).length - 1 };
  } },
  { id: "track.update", title: "Rename, lock, hide or mute a track", args: "{ index, patch: { name?, locked?, hidden?, muted?, magnetic? } }", kind: "edit", run: (engine, _b, a) => {
    const index = num(a, "index");
    if (!tracks(engine)[index]) throw refused(`there is no track ${index}`);
    engine.dispatch("track.update", { index, patch: pick(a.patch, ["name", "locked", "hidden", "muted", "magnetic"]) });
    return {};
  } },
  { id: "timeline.cut-range", title: "Remove a span from every track", args: "{ start, end }", kind: "edit", run: (engine, _b, a) => {
    engine.dispatch("timeline.cut-range", { start: num(a, "start"), end: num(a, "end") });
    return {};
  } },
  { id: "project.rename", title: "Rename the project", args: "{ title }", kind: "edit", run: (engine, _b, a) => {
    engine.dispatch("project.rename", str(a, "title")!.slice(0, 200));
    return {};
  } },
  { id: "transport.seek", title: "Move the playhead", args: "{ time }", kind: "view", run: (engine, _b, a) => { engine.dispatch("transport.seek", num(a, "time")); return {}; } },
  { id: "transport.play", title: "Play", args: "{}", kind: "view", run: (engine) => { engine.play(); return {}; } },
  { id: "transport.pause", title: "Pause", args: "{}", kind: "view", run: (engine) => { engine.pause(); return {}; } },
  { id: "clip.select", title: "Select a clip", args: "{ clipId } (null clears)", kind: "view", run: (engine, _b, a) => {
    if (a.clipId !== null) clip(engine, str(a, "clipId")!);
    engine.dispatch("clip.select", a.clipId ?? null);
    return {};
  } },
  { id: "clips.select", title: "Select clips", args: "{ clipIds }", kind: "view", run: (engine, _b, a) => {
    engine.dispatch("clip.select-set", Array.isArray(a.clipIds) ? a.clipIds.filter((x) => typeof x === "string") : []);
    return {};
  } },
  { id: "range.set", title: "Mark a range", args: "{ start, end }", kind: "view", run: (engine, _b, a) => { engine.dispatch("range.set", { start: num(a, "start"), end: num(a, "end") }); return {}; } },
  { id: "range.clear", title: "Clear the range", args: "{}", kind: "view", run: (engine) => { engine.dispatch("range.clear"); return {}; } },
  { id: "media.beats", title: "Find the beats in a library item", args: "{ mediaId, sensitivity? }", kind: "analysis", run: (_e, _b, a) => rpc("media.beats", { id: str(a, "mediaId"), sensitivity: a.sensitivity }) },
  { id: "media.scenes", title: "Find the scene cuts in a library item", args: "{ mediaId, sensitivity? }", kind: "analysis", run: (_e, _b, a) => rpc("media.scenes", { id: str(a, "mediaId"), sensitivity: a.sensitivity }) },
  { id: "media.ducking", title: "Work out a ducking envelope for a library item", args: "{ mediaId, depth? }", kind: "analysis", run: (_e, _b, a) => rpc("media.ducking", { id: str(a, "mediaId"), depth: a.depth }) },
];
const BY_ID = new Map(ENTRIES.map((entry) => [entry.id, entry]));

async function rpc(method: string, params: Args): Promise<unknown> {
  const reply = await api<{ result?: unknown; error?: { message: string } }>("/api/rpc", { jsonrpc: "2.0", id: 1, method, params });
  if (reply.error) throw refused(reply.error.message);
  return reply.result;
}

function args(raw: unknown): Args {
  if (raw === undefined || raw === null) return {};
  if (typeof raw !== "object" || Array.isArray(raw)) throw invalid("args must be an object");
  return raw as Args;
}

function wrap(error: unknown): never {
  if (error instanceof HostError) throw error;
  throw refused(error instanceof Error ? error.message : String(error));
}

export function commandList(): Array<{ id: string; title: string; args: string; kind: Kind }> {
  return ENTRIES.map(({ id, title, args: a, kind }) => ({ id, title, args: a, kind }));
}

export function applyOps(engine: ProjectEngine, bin: MediaBin, ops: { command: string; args?: unknown }[]): { applied: number; results: unknown[] } {
  for (const op of ops) {
    const entry = BY_ID.get(op.command);
    if (!entry) throw invalid(`${op.command} is not a formcut command`);
    if (entry.kind !== "edit") throw invalid(`${op.command} does not change the document; run it with app.run`);
  }
  const results: unknown[] = [];
  try {
    engine.transaction((touched) => {
      ops.forEach((op, index) => {
        const entry = BY_ID.get(op.command)!;
        const before = touched();
        try {
          results.push(entry.run(engine, bin, args(op.args)));
        } catch (error) {
          const e = error as { code?: number; message?: string };
          throw new HostError(typeof e.code === "number" ? e.code : ERR.REFUSED, `op ${index + 1} (${op.command}): ${e.message ?? String(error)}`);
        }
        if (op.command !== "project.rename") changed(engine, touched, before, `${op.command} with those args (op ${index + 1})`);
      });
    });
  } catch (error) {
    wrap(error);
  }
  return { applied: ops.length, results };
}

export async function runCommand(engine: ProjectEngine, bin: MediaBin, command: string, raw: unknown): Promise<unknown> {
  const entry = BY_ID.get(command);
  if (!entry) throw invalid(`${command} is not a formcut command`);
  if (entry.kind === "edit") return applyOps(engine, bin, [{ command, args: raw }]).results[0];
  try {
    return await entry.run(engine, bin, args(raw));
  } catch (error) {
    wrap(error);
  }
}

type ClipSummary = { id: string; kind: string; label: string; start: number; duration: number; mediaId: string | null; sourceIn: number; speed: number; muted: boolean; volume: number; text?: string };

function summary(c: Clip): ClipSummary {
  const out: ClipSummary = { id: c.id, kind: c.kind, label: c.label, start: c.start, duration: c.duration, mediaId: c.mediaId ?? null, sourceIn: c.sourceIn ?? 0, speed: c.speed ?? 1, muted: Boolean(c.muted), volume: c.volume ?? 1 };
  if (c.kind === "text") out.text = c.textStyle?.content ?? c.label;
  return out;
}

function timelineOf(s: ProjectState) {
  const tl = s.timelines[s.activeTimeline];
  return {
    index: s.activeTimeline,
    count: s.timelines.length,
    id: tl.id,
    name: tl.name,
    width: tl.width ?? s.width,
    height: tl.height ?? s.height,
    fps: tl.fps ?? s.fps,
    tracks: tl.tracks.map((tr, index) => ({ index, id: tr.id, name: tr.name, locked: Boolean(tr.locked), hidden: Boolean(tr.hidden), muted: Boolean(tr.muted), magnetic: Boolean(tr.magnetic), clips: tr.clips.map(summary) })),
    markers: (tl.markers ?? []).map((m) => ({ id: m.id, t: m.t, note: m.note ?? null, colour: m.colour ?? null })),
  };
}

export function readDocument(engine: ProjectEngine, bin: MediaBin, what = "project"): unknown {
  const s = engine.snapshot;
  const range = engine.range ? { start: engine.range.start, end: engine.range.end } : null;
  const selection = { clipId: s.selectedClipId, clipIds: [...s.selection], range };
  const media = bin.all.map((m) => ({ id: m.id, name: m.name, kind: m.kind, duration: m.duration, width: m.width, height: m.height, fps: m.fps }));
  switch (what) {
    case "project":
      return {
        product: "formcut",
        what,
        project: { id: s.projectId, title: s.title, revision: s.revision ?? null, saved: s.saved, width: s.width, height: s.height, fps: s.fps, aspect: s.aspect, duration: s.duration, playhead: s.playhead, playing: s.playing },
        timeline: timelineOf(s),
        selection,
        media,
      };
    case "timeline":
      return { product: "formcut", what, timeline: timelineOf(s) };
    case "selection":
      return { product: "formcut", what, selection, clips: selection.clipIds.map((id) => engine.findClip(id)).filter((f) => !!f).map((f) => summary(f!.clip)) };
    case "media":
      return { product: "formcut", what, media };
    case "markers":
      return { product: "formcut", what, markers: timelineOf(s).markers };
    case "full":
      return { product: "formcut", what, state: JSON.parse(JSON.stringify(s)), media };
  }
  throw invalid("what must be project, timeline, selection, media, markers or full");
}
