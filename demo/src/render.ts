import { defaultTransform } from "../../frontend/src/engine/types";
import type { Clip, ProjectState } from "../../frontend/src/engine/types";
import { sourceTime } from "../../frontend/src/engine/timing";
import { FRAME_W, getSource, sourceCanvas } from "./media";
import type { Source } from "./media";

const BLEND: Record<string, GlobalCompositeOperation> = {
  Normal: "source-over", Multiply: "multiply", Screen: "screen", Overlay: "overlay", Add: "lighter",
  Darken: "darken", Lighten: "lighten", "Soft Light": "soft-light",
};
export const BLEND_NAMES = Object.keys(BLEND);

export const EFFECTS: Array<{ id: string; name: string; unit: string }> = [
  { id: "blur", name: "Blur", unit: "px" },
  { id: "grayscale", name: "Grayscale", unit: "%" },
  { id: "sepia", name: "Sepia", unit: "%" },
  { id: "invert", name: "Invert", unit: "%" },
  { id: "hue", name: "Hue shift", unit: "deg" },
  { id: "pixelate", name: "Pixelate", unit: "%" },
];

export const TRANSITIONS: Array<{ id: string; name: string }> = [
  { id: "crossfade", name: "Crossfade" },
  { id: "dip", name: "Dip to black" },
  { id: "wipe-left", name: "Wipe left" },
  { id: "wipe-right", name: "Wipe right" },
  { id: "slide-left", name: "Slide" },
  { id: "zoom", name: "Zoom" },
];

export interface FrameEnv {
  video(clip: Clip): HTMLVideoElement | null;
}

let layer: HTMLCanvasElement | null = null;
let pixel: HTMLCanvasElement | null = null;

const scratch = (): { layer: CanvasRenderingContext2D; pixel: CanvasRenderingContext2D } => {
  layer ??= document.createElement("canvas");
  pixel ??= document.createElement("canvas");
  return { layer: layer.getContext("2d")!, pixel: pixel.getContext("2d")! };
};

const clamp01 = (value: number): number => Math.min(1, Math.max(0, value));

export function filterOf(clip: Clip, scale: number): string {
  const c = clip.colour ?? {};
  const parts: string[] = [];
  const brightness = (1 + (c.brightness ?? 0) / 100) * 2 ** (c.exposure ?? 0);
  if (Math.abs(brightness - 1) > 0.001) parts.push(`brightness(${brightness.toFixed(3)})`);
  if (c.contrast) parts.push(`contrast(${(1 + c.contrast / 100).toFixed(3)})`);
  if (c.saturation) parts.push(`saturate(${Math.max(0, 1 + c.saturation / 100).toFixed(3)})`);
  for (const fx of clip.effects ?? []) {
    if (fx.enabled === false) continue;
    const amount = fx.amount;
    if (fx.id === "blur") parts.push(`blur(${((amount / 100) * 14 * scale).toFixed(2)}px)`);
    else if (fx.id === "grayscale") parts.push(`grayscale(${amount}%)`);
    else if (fx.id === "sepia") parts.push(`sepia(${amount}%)`);
    else if (fx.id === "invert") parts.push(`invert(${amount}%)`);
    else if (fx.id === "hue") parts.push(`hue-rotate(${(amount / 100) * 360}deg)`);
  }
  return parts.join(" ");
}

function pixelAmount(clip: Clip): number {
  const fx = (clip.effects ?? []).find((entry) => entry.id === "pixelate" && entry.enabled !== false);
  return fx ? fx.amount : 0;
}

function wrapLines(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string[] {
  const lines: string[] = [];
  for (const raw of text.split("\n")) {
    let line = "";
    for (const word of raw.split(/\s+/)) {
      const next = line ? `${line} ${word}` : word;
      if (line && ctx.measureText(next).width > maxWidth) {
        lines.push(line);
        line = word;
      } else line = next;
    }
    lines.push(line);
  }
  return lines;
}

function drawText(ctx: CanvasRenderingContext2D, clip: Clip, w: number, h: number): void {
  const style = clip.textStyle;
  if (!style) return;
  const tf = { ...defaultTransform(), ...clip.transform };
  const px = (style.size / 100) * h * (tf.scale / 100);
  ctx.save();
  ctx.translate(w / 2 + (tf.posX / 100) * w, h / 2 + (tf.posY / 100) * h);
  ctx.rotate((tf.rotation * Math.PI) / 180);
  ctx.font = `${style.bold ? 700 : 500} ${px}px system-ui, -apple-system, "Segoe UI", sans-serif`;
  ctx.textAlign = style.align;
  ctx.textBaseline = "middle";
  const lines = wrapLines(ctx, style.content, w * 0.84);
  const lineH = px * 1.22;
  const top = (-(lines.length - 1) * lineH) / 2;
  const anchor = style.align === "left" ? -w * 0.42 : style.align === "right" ? w * 0.42 : 0;
  if (style.plateColor) {
    const widest = Math.max(...lines.map((line) => ctx.measureText(line).width));
    const pad = px * 0.35;
    ctx.fillStyle = style.plateColor;
    ctx.globalAlpha = style.plateOpacity ?? 0.6;
    const left = style.align === "left" ? anchor - pad : style.align === "right" ? anchor - widest - pad : anchor - widest / 2 - pad;
    ctx.beginPath();
    ctx.roundRect(left, top - lineH / 2 - pad / 2, widest + pad * 2, lines.length * lineH + pad, px * 0.2);
    ctx.fill();
    ctx.globalAlpha = 1;
  }
  if (style.shadowBlur) {
    ctx.shadowColor = style.shadowColor ?? "black";
    ctx.shadowBlur = style.shadowBlur * (h / 720);
    ctx.shadowOffsetY = (style.shadowY ?? 2) * (h / 720);
  }
  lines.forEach((line, index) => {
    const y = top + index * lineH;
    if (style.outlineWidth) {
      ctx.lineJoin = "round";
      ctx.lineWidth = style.outlineWidth * (h / 720);
      ctx.strokeStyle = style.outlineColor ?? "black";
      ctx.strokeText(line, anchor, y);
    }
    ctx.fillStyle = style.color;
    ctx.fillText(line, anchor, y);
  });
  ctx.restore();
}

interface Role {
  type: "none" | "in" | "out";
  kind: string;
  p: number;
}

function frameOf(clip: Clip, local: number, env: FrameEnv): { image: CanvasImageSource; iw: number; ih: number } | null {
  const source: Source | undefined = getSource(clip.mediaId);
  if (!source) return null;
  const at = sourceTime(clip, Math.max(0, local));
  if (source.kind === "image") {
    if (source.bitmap) return { image: source.bitmap, iw: source.width, ih: source.height };
    if (source.paint) {
      const canvas = sourceCanvas(source);
      source.paint(canvas.getContext("2d")!, 0, canvas.width, canvas.height);
      return { image: canvas, iw: canvas.width, ih: canvas.height };
    }
    return null;
  }
  if (source.kind === "video") {
    if (source.paint) {
      const canvas = sourceCanvas(source);
      source.paint(canvas.getContext("2d")!, at, canvas.width, canvas.height);
      return { image: canvas, iw: canvas.width, ih: canvas.height };
    }
    const video = env.video(clip);
    if (video && video.readyState >= 2) return { image: video, iw: video.videoWidth, ih: video.videoHeight };
  }
  return null;
}

function paintClip(main: CanvasRenderingContext2D, clip: Clip, local: number, w: number, h: number, env: FrameEnv, role: Role): void {
  const { layer: lctx, pixel: pctx } = scratch();
  const lc = lctx.canvas;
  if (lc.width !== w || lc.height !== h) {
    lc.width = w;
    lc.height = h;
  }
  lctx.setTransform(1, 0, 0, 1, 0, 0);
  lctx.globalAlpha = 1;
  lctx.globalCompositeOperation = "source-over";
  lctx.filter = "none";
  lctx.clearRect(0, 0, w, h);
  const tf = { ...defaultTransform(), ...clip.transform };
  const scale = w / FRAME_W;
  if (clip.kind === "text") {
    const filter = filterOf(clip, scale);
    if (filter) lctx.filter = filter;
    drawText(lctx, clip, w, h);
    lctx.filter = "none";
  } else {
    const frame = frameOf(clip, local, env);
    if (!frame || !frame.iw || !frame.ih) return;
    let image = frame.image;
    const iw = frame.iw;
    const ih = frame.ih;
    const pixelate = pixelAmount(clip);
    if (pixelate > 0) {
      const factor = Math.max(2, Math.round((pixelate / 100) * 48));
      const pc = pctx.canvas;
      pc.width = Math.max(1, Math.round(iw / factor));
      pc.height = Math.max(1, Math.round(ih / factor));
      pctx.imageSmoothingEnabled = true;
      pctx.drawImage(image, 0, 0, pc.width, pc.height);
      image = pc;
      lctx.imageSmoothingEnabled = false;
    } else lctx.imageSmoothingEnabled = true;
    const fit = Math.min(w / iw, h / ih) * (tf.scale / 100);
    const filter = filterOf(clip, scale);
    if (filter) lctx.filter = filter;
    lctx.save();
    lctx.translate(w / 2 + (tf.posX / 100) * w, h / 2 + (tf.posY / 100) * h);
    lctx.rotate((tf.rotation * Math.PI) / 180);
    lctx.scale(tf.flipH ? -1 : 1, tf.flipV ? -1 : 1);
    lctx.drawImage(image, (-iw * fit) / 2, (-ih * fit) / 2, iw * fit, ih * fit);
    lctx.restore();
    lctx.filter = "none";
  }
  const c = clip.colour ?? {};
  lctx.globalCompositeOperation = "source-atop";
  const warmth = Math.max(-1, Math.min(1, ((c.temperature ?? 6500) - 6500) / 4000));
  if (warmth !== 0) {
    lctx.fillStyle = warmth > 0 ? `rgb(255 150 40 / ${(warmth * 0.3).toFixed(3)})` : `rgb(40 120 255 / ${(-warmth * 0.3).toFixed(3)})`;
    lctx.fillRect(0, 0, w, h);
  }
  if (c.tint) {
    lctx.fillStyle = c.tint > 0 ? `rgb(255 40 200 / ${(c.tint / 100 * 0.22).toFixed(3)})` : `rgb(40 220 90 / ${(-c.tint / 100 * 0.22).toFixed(3)})`;
    lctx.fillRect(0, 0, w, h);
  }
  if (c.fade) {
    lctx.fillStyle = `rgb(150 150 150 / ${(c.fade / 100 * 0.45).toFixed(3)})`;
    lctx.fillRect(0, 0, w, h);
  }
  if (c.vignette) {
    const g = lctx.createRadialGradient(w / 2, h / 2, Math.min(w, h) * 0.25, w / 2, h / 2, Math.hypot(w, h) * 0.5);
    g.addColorStop(0, "rgb(0 0 0 / 0)");
    g.addColorStop(1, `rgb(0 0 0 / ${(c.vignette / 100).toFixed(3)})`);
    lctx.fillStyle = g;
    lctx.fillRect(0, 0, w, h);
  }
  lctx.globalCompositeOperation = "source-over";

  let alpha = (tf.opacity / 100);
  if (clip.fadeIn && local < clip.fadeIn) alpha *= clamp01(local / clip.fadeIn);
  if (role.type !== "out" && clip.fadeOut && clip.duration - local < clip.fadeOut) alpha *= clamp01((clip.duration - local) / clip.fadeOut);
  let offsetX = 0;
  let zoom = 1;
  let region: [number, number, number, number] | null = null;
  if (role.type !== "none") {
    const p = clamp01(role.p);
    if (role.kind === "crossfade") alpha *= role.type === "in" ? p : 1;
    else if (role.kind === "dip") alpha *= role.type === "in" ? clamp01((p - 0.5) * 2) : clamp01(1 - p * 2);
    else if (role.kind === "wipe-left" && role.type === "in") region = [w * (1 - p), 0, w * p, h];
    else if (role.kind === "wipe-right" && role.type === "in") region = [0, 0, w * p, h];
    else if (role.kind === "slide-left") offsetX = role.type === "in" ? w * (1 - p) : -w * p;
    else if (role.kind === "zoom" && role.type === "in") {
      zoom = 0.5 + 0.5 * p;
      alpha *= p;
    }
  }
  if (alpha <= 0.001) return;
  main.save();
  main.globalAlpha = clamp01(alpha);
  main.globalCompositeOperation = BLEND[tf.blendMode] ?? "source-over";
  if (region) {
    main.beginPath();
    main.rect(region[0], region[1], region[2], region[3]);
    main.clip();
  }
  if (zoom !== 1) {
    main.translate(w / 2, h / 2);
    main.scale(zoom, zoom);
    main.translate(-w / 2, -h / 2);
  }
  main.drawImage(lc, offsetX, 0);
  main.restore();
}

export function drawFrame(main: CanvasRenderingContext2D, state: ProjectState, t: number, env: FrameEnv): void {
  const w = main.canvas.width;
  const h = main.canvas.height;
  main.save();
  main.setTransform(1, 0, 0, 1, 0, 0);
  main.globalAlpha = 1;
  main.globalCompositeOperation = "source-over";
  main.fillStyle = "black";
  main.fillRect(0, 0, w, h);
  main.restore();
  const tracks = state.timelines[state.activeTimeline].tracks;
  for (let index = tracks.length - 1; index >= 0; index -= 1) {
    const track = tracks[index];
    if (track.hidden) continue;
    for (const clip of track.clips) {
      if (clip.kind === "audio") continue;
      const local = t - clip.start;
      if (local < 0 || local >= clip.duration) continue;
      const trans = clip.transitionIn;
      if (trans && local < trans.duration) {
        const before = track.clips.find((other) => other !== clip && other.kind !== "audio" && Math.abs(other.start + other.duration - clip.start) < 0.06);
        const p = local / trans.duration;
        if (before) paintClip(main, before, before.duration + local, w, h, env, { type: "out", kind: trans.type, p });
        paintClip(main, clip, local, w, h, env, { type: "in", kind: trans.type, p });
      } else paintClip(main, clip, local, w, h, env, { type: "none", kind: "", p: 1 });
    }
  }
}
