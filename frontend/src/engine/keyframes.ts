// Interpolation model: linear, ease variants and hold. formcut ships linear and hold, the two shapes the
// export can express as ffmpeg piecewise expressions; eases are a recorded
// follow-up. Keyframe times are clip-local timeline seconds.
import {
  defaultTransform,
  type Clip,
  type ClipTransform,
  KEYFRAME_INTERPS,
  type Keyframe,
  type KeyframeInterp,
  type KeyframeProp,
} from "./types";

export function easeProgress(p: number, interp: KeyframeInterp): number {
  switch (interp) {
    case "easeIn":
      return p * p;
    case "easeOut":
      return 1 - (1 - p) * (1 - p);
    case "ease":
      return p * p * (3 - 2 * p);
    default:
      return p;
  }
}

export function propPoints(
  clip: Clip,
  prop: KeyframeProp,
): Array<{ t: number; v: number; interp: KeyframeInterp; handles?: [number, number, number, number] }> {
  return (clip.keyframes ?? [])
    .filter((k) => k.props[prop] !== undefined)
    .map((k) => ({ t: k.t, v: k.props[prop]!, interp: k.interp ?? "linear", handles: k.handles }))
    .sort((a, b) => a.t - b.t);
}

export function samplePoints(
  points: Array<{ t: number; v: number; interp: KeyframeInterp; handles?: [number, number, number, number] }>,
  local: number,
): number | undefined {
  if (points.length === 0) return undefined;
  if (local <= points[0].t) return points[0].v;
  const last = points[points.length - 1];
  if (local >= last.t) return last.v;
  for (let i = 0; i < points.length - 1; i += 1) {
    const a = points[i];
    const b = points[i + 1];
    if (local >= a.t && local < b.t) {
      if (a.interp === "hold" || b.t === a.t) return a.v;
      const p = easeProgress((local - a.t) / (b.t - a.t), a.interp);
      return a.v + (b.v - a.v) * p;
    }
  }
  return last.v;
}

export function sampledTransform(clip: Clip, local: number): ClipTransform {
  const base: ClipTransform = { ...defaultTransform(), ...clip.transform };
  if (!clip.keyframes || clip.keyframes.length === 0) return base;
  for (const prop of ["posX", "posY", "scale", "rotation", "opacity"] as KeyframeProp[]) {
    const value = samplePoints(propPoints(clip, prop), local);
    if (value !== undefined) base[prop] = value;
  }
  return base;
}

export function upsertKeyframe(clip: Clip, t: number, set: Partial<Record<KeyframeProp, number>>): void {
  const frames: Keyframe[] = clip.keyframes ?? [];
  const rounded = Math.round(t * 100) / 100;
  const existing = frames.find((k) => Math.abs(k.t - rounded) < 0.02);
  if (existing) {
    Object.assign(existing.props, set);
  } else {
    frames.push({ t: rounded, props: { ...set } });
  }
  frames.sort((a, b) => a.t - b.t);
  clip.keyframes = frames;
}

export function removeKeyframeProp(clip: Clip, t: number, prop: KeyframeProp): boolean {
  const frames = clip.keyframes ?? [];
  const hit = frames.find((k) => Math.abs(k.t - t) < 0.02 && k.props[prop] !== undefined);
  if (!hit) return false;
  delete hit.props[prop];
  clip.keyframes = frames.filter((k) => Object.keys(k.props).length > 0);
  if (clip.keyframes.length === 0) clip.keyframes = undefined;
  return true;
}

export function cycleKeyframeInterp(clip: Clip, t: number): KeyframeInterp | null {
  const hit = (clip.keyframes ?? []).find((k) => Math.abs(k.t - t) < 0.02);
  if (!hit) return null;
  const current = hit.interp ?? "linear";
  const next = KEYFRAME_INTERPS[(KEYFRAME_INTERPS.indexOf(current) + 1) % KEYFRAME_INTERPS.length];
  hit.interp = next;
  return next;
}
