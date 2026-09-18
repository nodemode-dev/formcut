import type { Clip, Track } from "./types";

const EPSILON = 0.05;

export interface TransitionPlan {
  rampIn: number;
  rampOut: number;
  extendOut: number;
}

export function transitionPlans(tracks: Track[]): Map<string, TransitionPlan> {
  const plans = new Map<string, TransitionPlan>();
  const plan = (clip: Clip): TransitionPlan => {
    let p = plans.get(clip.id);
    if (!p) {
      p = { rampIn: 0, rampOut: 0, extendOut: 0 };
      plans.set(clip.id, p);
    }
    return p;
  };
  for (const track of tracks) {
    const sorted = [...track.clips].sort((a, b) => a.start - b.start);
    for (let i = 0; i < sorted.length; i += 1) {
      const clip = sorted[i];
      const t = clip.transitionIn;
      if (!t) continue;
      const prev = i > 0 ? sorted[i - 1] : null;
      const adjacent = prev && Math.abs(prev.start + prev.duration - clip.start) < EPSILON ? prev : null;
      if (t.type === "crossfade") {
        plan(clip).rampIn = Math.max(plan(clip).rampIn, t.duration);
        if (adjacent) plan(adjacent).extendOut = Math.max(plan(adjacent).extendOut, t.duration);
      } else {
        const half = t.duration / 2;
        plan(clip).rampIn = Math.max(plan(clip).rampIn, half);
        if (adjacent) plan(adjacent).rampOut = Math.max(plan(adjacent).rampOut, half);
      }
    }
  }
  return plans;
}
