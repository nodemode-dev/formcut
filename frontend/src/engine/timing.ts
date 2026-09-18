import type { Clip, Keyframe } from "./types";

export interface SpeedPoint { t: number; speed: number }
export const SPEED_PRESETS: Record<string, [number, number][]> = {
  uniform: [[0, 1], [1, 1]],
  accelerate: [[0, 0.25], [1, 3]],
  decelerate: [[0, 3], [1, 0.25]],
  valley: [[0, 2], [0.35, 0.4], [0.65, 0.4], [1, 2]],
  peak: [[0, 0.5], [0.5, 3], [1, 0.5]],
  pulse: [[0, 1], [0.25, 3], [0.5, 0.25], [0.75, 3], [1, 1]],
};

export function speedPoints(clip: Clip): SpeedPoint[] {
  const points = new Map<number, number>();
  for (const p of clip.speedCurve ?? []) {
    if (Number.isFinite(p.t) && Number.isFinite(p.speed)) {
      points.set(Math.max(0, p.t), Math.max(0.05, Math.min(16, p.speed)));
    }
  }
  if (!points.size) return [{ t: 0, speed: clip.speed ?? 1 }];
  return [...points].sort((a, b) => a[0] - b[0]).map(([t, speed]) => ({ t, speed }));
}

export function speedAt(clip: Clip, time: number): number {
  const points = speedPoints(clip);
  if (time <= points[0].t) return points[0].speed;
  for (let i = 1; i < points.length; i++) {
    const a = points[i - 1], b = points[i];
    if (time <= b.t) return a.speed + (b.speed - a.speed) * (time - a.t) / (b.t - a.t);
  }
  return points[points.length - 1].speed;
}

export function sourceDelta(clip: Clip, time: number): number {
  if (time <= 0) return time * speedAt(clip, 0);
  const breaks = [0, ...speedPoints(clip).map(p => p.t).filter(t => t > 0 && t < time), time];
  let value = 0;
  for (let i = 1; i < breaks.length; i++) {
    const a = breaks[i - 1], b = breaks[i];
    value += (b - a) * (speedAt(clip, a) + speedAt(clip, b)) / 2;
  }
  return value;
}

export function sourceTime(clip: Clip, local: number): number {
  return Math.max(0, (clip.sourceIn ?? 0) + sourceDelta(clip, local));
}

export function shiftedCurve(clip: Clip, offset: number, duration: number): SpeedPoint[] | undefined {
  if (!clip.speedCurve?.length) return undefined;
  return [{ t: 0, speed: speedAt(clip, offset) },
    ...speedPoints(clip).filter(p => p.t > offset && p.t < offset + duration)
      .map(p => ({ t: p.t - offset, speed: p.speed })),
    { t: duration, speed: speedAt(clip, offset + duration) }];
}

export function retimedKeys(keys: Keyframe[] | undefined, offset: number, duration: number): Keyframe[] | undefined {
  if (!keys?.length) return undefined;
  void duration;
  return keys.map(k => ({ ...structuredClone(k), t: k.t - offset }));
}
