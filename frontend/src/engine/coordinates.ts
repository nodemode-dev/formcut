import type { Clip } from "./types";
import { sourceTime } from "./timing";

export function timelineTime(clip: Clip, source: number): number {
  let low = 0, high = clip.duration;
  for (let i = 0; i < 48; i++) {
    const mid = (low + high) / 2;
    if (sourceTime(clip, mid) < source) low = mid; else high = mid;
  }
  return (low + high) / 2;
}
