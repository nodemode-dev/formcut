import type { Clip, Keyframe, KeyframeProp } from "./types";
import { defaultTransform } from "./types";

export const MOTION_PRESETS = ["fade-in", "fade-out", "slide-left", "slide-right", "slide-up", "slide-down", "zoom-in", "zoom-out", "spin-in", "pulse", "float", "shake"] as const;

export function motionKeys(clip: Clip, preset: string, seconds: number): Keyframe[] {
  const base = { ...defaultTransform(), ...clip.transform };
  const duration = Math.min(clip.duration, Math.max(0.1, seconds));
  const point = (t: number, props: Partial<Record<KeyframeProp, number>>): Keyframe => ({ t, props, interp: "ease" });
  switch (preset) {
    case "fade-in": return [point(0, { opacity: 0 }), point(duration, { opacity: base.opacity })];
    case "fade-out": return [point(clip.duration - duration, { opacity: base.opacity }), point(clip.duration, { opacity: 0 })];
    case "slide-left": return [point(0, { posX: base.posX - 100 }), point(duration, { posX: base.posX })];
    case "slide-right": return [point(0, { posX: base.posX + 100 }), point(duration, { posX: base.posX })];
    case "slide-up": return [point(0, { posY: base.posY + 100 }), point(duration, { posY: base.posY })];
    case "slide-down": return [point(0, { posY: base.posY - 100 }), point(duration, { posY: base.posY })];
    case "zoom-in": return [point(0, { scale: base.scale * 0.1 }), point(duration, { scale: base.scale })];
    case "zoom-out": return [point(0, { scale: base.scale * 1.5 }), point(duration, { scale: base.scale })];
    case "spin-in": return [point(0, { rotation: base.rotation - 180, scale: 0 }), point(duration, { rotation: base.rotation, scale: base.scale })];
    case "pulse": return [point(0, { scale: base.scale }), point(duration / 2, { scale: base.scale * 1.15 }), point(duration, { scale: base.scale })];
    case "float": return [point(0, { posY: base.posY }), point(duration / 2, { posY: base.posY - 8 }), point(duration, { posY: base.posY })];
    case "shake": return Array.from({ length: 9 }, (_, i) => point(duration * i / 8, { posX: base.posX + (i === 0 || i === 8 ? 0 : i % 2 ? 3 : -3) }));
    default: throw new Error("Unknown motion preset");
  }
}
