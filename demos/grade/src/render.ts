import type { Clip, ClipMask, ClipTransition, ProjectState } from "../../../frontend/src/engine/types";
import { propValue, sampledTransform } from "../../../frontend/src/engine/keyframes";
import { FRAME_W, getSource } from "../../../demo/src/media";
import { applyLattice, applyVignette, latticeFor } from "./grade";

export const TRANSITION_KINDS: ClipTransition["type"][] = [
  "crossfade", "dip", "wipe-left", "wipe-right", "wipe-up", "wipe-down", "slide-left", "slide-right", "zoom", "iris", "dissolve",
  "push-up", "push-down", "cover-left", "cover-up", "clock-wipe", "blinds", "diagonal-wipe", "pixel-dissolve", "blur-fade", "spin", "diamond", "barn-door",
];

export const MASK_SHAPE_NAMES = ["ellipse", "rect", "diamond", "triangle", "pentagon", "hexagon", "octagon", "star", "star6", "cross", "arrow", "chevron", "trapezoid", "linear"] as const;

export interface FrameEnv {
  video(clip: Clip): HTMLVideoElement | null;
}

export interface DrawOptions {
  bypass?: boolean;
}

interface Role {
  type: "none" | "in" | "out";
  kind: string;
  p: number;
}

type Pt = [number, number];

const clamp01 = (value: number): number => Math.min(1, Math.max(0, value));

const regular = (sides: number): Pt[] =>
  Array.from({ length: sides }, (_, i) => [0.5 + 0.5 * Math.cos(-Math.PI / 2 + (2 * Math.PI * i) / sides), 0.5 + 0.5 * Math.sin(-Math.PI / 2 + (2 * Math.PI * i) / sides)] as Pt);

const star = (points: number, inner: number): Pt[] =>
  Array.from({ length: points * 2 }, (_, i) => {
    const radius = i % 2 ? inner * 0.5 : 0.5;
    const angle = -Math.PI / 2 + (Math.PI * i) / points;
    return [0.5 + radius * Math.cos(angle), 0.5 + radius * Math.sin(angle)] as Pt;
  });

const SHAPES: Record<string, Pt[]> = {
  rect: [[0, 0], [1, 0], [1, 1], [0, 1]],
  ellipse: Array.from({ length: 64 }, (_, i) => [0.5 + 0.5 * Math.cos((2 * Math.PI * i) / 64), 0.5 + 0.5 * Math.sin((2 * Math.PI * i) / 64)] as Pt),
  triangle: [[0.5, 0], [1, 1], [0, 1]],
  diamond: [[0.5, 0], [1, 0.5], [0.5, 1], [0, 0.5]],
  pentagon: regular(5),
  hexagon: regular(6),
  octagon: regular(8),
  star: star(5, 0.42),
  star6: star(6, 0.55),
  cross: [[0.35, 0], [0.65, 0], [0.65, 0.35], [1, 0.35], [1, 0.65], [0.65, 0.65], [0.65, 1], [0.35, 1], [0.35, 0.65], [0, 0.65], [0, 0.35], [0.35, 0.35]],
  arrow: [[0, 0.3], [0.6, 0.3], [0.6, 0.05], [1, 0.5], [0.6, 0.95], [0.6, 0.7], [0, 0.7]],
  chevron: [[0, 0.1], [0.45, 0.5], [0, 0.9], [0.25, 0.9], [0.7, 0.5], [0.25, 0.1]],
  trapezoid: [[0.2, 0], [0.8, 0], [1, 1], [0, 1]],
};

let layer: HTMLCanvasElement | null = null;
const maskCache = new Map<string, HTMLCanvasElement>();

function paintMask(mask: ClipMask, w: number, h: number): HTMLCanvasElement {
  const key = JSON.stringify([mask, w, h]);
  const hit = maskCache.get(key);
  if (hit) return hit;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const g = canvas.getContext("2d")!;
  const x0 = (mask.x / 100) * w;
  const y0 = (mask.y / 100) * h;
  const bw = (mask.w / 100) * w;
  const bh = (mask.h / 100) * h;
  const cx = x0 + bw / 2;
  const cy = y0 + bh / 2;
  const feather = (Math.max(0, mask.feather) / 100) * Math.min(w, h);
  const outline = (): void => {
    g.beginPath();
    if (mask.shape === "linear") {
      const a = ((mask.angle ?? 0) * Math.PI) / 180;
      const far = Math.hypot(w, h) * 2;
      const dx = Math.cos(a);
      const dy = Math.sin(a);
      const nx = Math.sin(a);
      const ny = -Math.cos(a);
      g.moveTo(cx - dx * far, cy - dy * far);
      g.lineTo(cx + dx * far, cy + dy * far);
      g.lineTo(cx + dx * far + nx * far, cy + dy * far + ny * far);
      g.lineTo(cx - dx * far + nx * far, cy - dy * far + ny * far);
    } else {
      const turn = ((mask.angle ?? 0) * Math.PI) / 180;
      const cos = Math.cos(turn);
      const sin = Math.sin(turn);
      (SHAPES[mask.shape] ?? SHAPES.rect).forEach(([ux, uy], i) => {
        const px = x0 + ux * bw - cx;
        const py = y0 + uy * bh - cy;
        const x = cx + px * cos - py * sin;
        const y = cy + px * sin + py * cos;
        if (i) g.lineTo(x, y);
        else g.moveTo(x, y);
      });
    }
    g.closePath();
    g.fill();
  };
  g.fillStyle = "#fff";
  if (mask.invert) {
    g.fillRect(0, 0, w, h);
    g.globalCompositeOperation = "destination-out";
  }
  if (feather > 0.5) g.filter = `blur(${feather.toFixed(2)}px)`;
  outline();
  if (maskCache.size > 6) maskCache.clear();
  maskCache.set(key, canvas);
  return canvas;
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

function drawText(ctx: CanvasRenderingContext2D, clip: Clip, w: number, h: number, local: number): void {
  const style = clip.textStyle;
  if (!style) return;
  const tf = sampledTransform(clip, local);
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

function frameOf(clip: Clip, env: FrameEnv): { image: CanvasImageSource; iw: number; ih: number } | null {
  const source = getSource(clip.mediaId);
  if (!source) return null;
  if (source.kind === "image" && source.bitmap) return { image: source.bitmap, iw: source.width, ih: source.height };
  if (source.kind === "video") {
    const video = env.video(clip);
    if (video && video.readyState >= 2) return { image: video, iw: video.videoWidth, ih: video.videoHeight };
  }
  return null;
}

function effectIndex(clip: Clip, id: string): number {
  return (clip.effects ?? []).findIndex((entry) => entry.id === id && entry.enabled !== false);
}

function amountAt(clip: Clip, id: string, local: number): number {
  const index = effectIndex(clip, id);
  return index < 0 ? 0 : Math.max(0, propValue(clip, `fx.${index}.amount`, local));
}

function addGrain(data: Uint8ClampedArray, amount: number): void {
  const spread = amount * 46;
  for (let i = 0; i < data.length; i += 4) {
    const n = (Math.random() - 0.5) * spread;
    data[i] += n;
    data[i + 1] += n;
    data[i + 2] += n;
  }
}

function gradeLayer(lctx: CanvasRenderingContext2D, clip: Clip, local: number, w: number, h: number): void {
  const lattice = latticeFor(clip);
  const panelVignette = Math.max(0, (clip.colour?.vignette ?? 0) / 100);
  const vignette = amountAt(clip, "vignette", local);
  const grain = amountAt(clip, "grain", local);
  if (!lattice && !panelVignette && !vignette && !grain) return;
  const image = lctx.getImageData(0, 0, w, h);
  if (lattice) applyLattice(image.data, lattice);
  applyVignette(image.data, w, h, panelVignette, vignette);
  if (grain) addGrain(image.data, grain);
  lctx.putImageData(image, 0, 0);
}

function revealRegion(g: CanvasRenderingContext2D, kind: string, p: number, w: number, h: number): boolean {
  g.beginPath();
  if (kind === "wipe-left") g.rect(w * (1 - p), 0, w * p, h);
  else if (kind === "wipe-right") g.rect(0, 0, w * p, h);
  else if (kind === "wipe-up") g.rect(0, h * (1 - p), w, h * p);
  else if (kind === "wipe-down") g.rect(0, 0, w, h * p);
  else if (kind === "iris") g.arc(w / 2, h / 2, p * Math.hypot(w, h) * 0.5, 0, Math.PI * 2);
  else if (kind === "clock-wipe") {
    g.moveTo(w / 2, h / 2);
    g.arc(w / 2, h / 2, Math.hypot(w, h), -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.max(0.0001, p));
    g.closePath();
  } else if (kind === "blinds") for (let i = 0; i < 8; i += 1) g.rect(0, (h / 8) * i, w, (h / 8) * p);
  else if (kind === "diagonal-wipe") {
    const s = p * 2;
    if (s <= 1) {
      g.moveTo(0, 0);
      g.lineTo(s * w, 0);
      g.lineTo(0, s * h);
    } else {
      const t = s - 1;
      g.moveTo(0, 0);
      g.lineTo(w, 0);
      g.lineTo(w, t * h);
      g.lineTo(t * w, h);
      g.lineTo(0, h);
    }
    g.closePath();
  } else if (kind === "pixel-dissolve") {
    const cols = 16;
    const rows = 9;
    for (let r = 0; r < rows; r += 1) for (let c = 0; c < cols; c += 1) if ((((c * 7919 + r * 104729) % 97) / 97) < p) g.rect((w / cols) * c, (h / rows) * r, w / cols + 1, h / rows + 1);
  } else if (kind === "diamond") {
    g.moveTo(w / 2, h / 2 - h * p);
    g.lineTo(w / 2 + w * p, h / 2);
    g.lineTo(w / 2, h / 2 + h * p);
    g.lineTo(w / 2 - w * p, h / 2);
    g.closePath();
  } else if (kind === "barn-door") g.rect((w / 2) * (1 - p), 0, w * p, h);
  else return false;
  return true;
}

function paintClip(main: CanvasRenderingContext2D, clip: Clip, local: number, w: number, h: number, env: FrameEnv, role: Role, opts: DrawOptions): void {
  if (!layer) layer = document.createElement("canvas");
  if (layer.width !== w || layer.height !== h) {
    layer.width = w;
    layer.height = h;
  }
  const lctx = layer.getContext("2d", { willReadFrequently: true })!;
  lctx.setTransform(1, 0, 0, 1, 0, 0);
  lctx.globalAlpha = 1;
  lctx.globalCompositeOperation = "source-over";
  lctx.filter = "none";
  lctx.shadowColor = "transparent";
  lctx.clearRect(0, 0, w, h);
  const tf = sampledTransform(clip, local);
  if (clip.kind === "text") drawText(lctx, clip, w, h, local);
  else {
    const frame = frameOf(clip, env);
    if (!frame || !frame.iw || !frame.ih) return;
    const fit = Math.min(w / frame.iw, h / frame.ih) * (tf.scale / 100);
    lctx.save();
    lctx.translate(w / 2 + (tf.posX / 100) * w, h / 2 + (tf.posY / 100) * h);
    lctx.rotate((tf.rotation * Math.PI) / 180);
    lctx.scale(tf.flipH ? -1 : 1, tf.flipV ? -1 : 1);
    lctx.drawImage(frame.image, (-frame.iw * fit) / 2, (-frame.ih * fit) / 2, frame.iw * fit, frame.ih * fit);
    lctx.restore();
    if (!opts.bypass) gradeLayer(lctx, clip, local, w, h);
  }
  if (clip.mask && !opts.bypass) {
    lctx.globalCompositeOperation = "destination-in";
    lctx.drawImage(paintMask(clip.mask, w, h), 0, 0);
    lctx.globalCompositeOperation = "source-over";
  }
  let alpha = tf.opacity / 100;
  if (clip.fadeIn && local < clip.fadeIn) alpha *= clamp01(local / clip.fadeIn);
  if (role.type !== "out" && clip.fadeOut && clip.duration - local < clip.fadeOut) alpha *= clamp01((clip.duration - local) / clip.fadeOut);
  let dx = 0;
  let dy = 0;
  let zoom = 1;
  let spin = 0;
  let blur = 0;
  let region = false;
  if (role.type !== "none") {
    const p = clamp01(role.p);
    const kind = role.kind;
    const into = role.type === "in";
    if (kind === "crossfade" || kind === "dissolve") alpha *= into ? p : 1;
    else if (kind === "dip") alpha *= into ? clamp01((p - 0.5) * 2) : clamp01(1 - p * 2);
    else if (kind === "slide-left") dx = into ? w * (1 - p) : -w * p;
    else if (kind === "slide-right") dx = into ? -w * (1 - p) : w * p;
    else if (kind === "push-up") dy = into ? h * (1 - p) : -h * p;
    else if (kind === "push-down") dy = into ? -h * (1 - p) : h * p;
    else if (kind === "cover-left" && into) dx = w * (1 - p);
    else if (kind === "cover-up" && into) dy = h * (1 - p);
    else if (kind === "zoom" && into) {
      zoom = 0.5 + 0.5 * p;
      alpha *= p;
    } else if (kind === "spin" && into) {
      zoom = Math.max(0.01, p);
      spin = (1 - p) * -Math.PI;
      alpha *= p;
    } else if (kind === "blur-fade" && into) {
      alpha *= p;
      blur = (1 - p) * 14 * (w / FRAME_W);
    } else if (into) region = true;
  }
  if (alpha <= 0.001) return;
  main.save();
  main.globalAlpha = clamp01(alpha);
  if (region) {
    const drawn = revealRegion(main, role.kind, clamp01(role.p), w, h);
    if (drawn) main.clip();
  }
  if (zoom !== 1 || spin) {
    main.translate(w / 2, h / 2);
    main.rotate(spin);
    main.scale(zoom, zoom);
    main.translate(-w / 2, -h / 2);
  }
  if (blur > 0.2) main.filter = `blur(${blur.toFixed(2)}px)`;
  main.drawImage(layer, dx, dy);
  main.restore();
}

export function drawFrame(main: CanvasRenderingContext2D, state: ProjectState, t: number, env: FrameEnv, opts: DrawOptions = {}): void {
  const w = main.canvas.width;
  const h = main.canvas.height;
  main.save();
  main.setTransform(1, 0, 0, 1, 0, 0);
  main.globalAlpha = 1;
  main.globalCompositeOperation = "source-over";
  main.filter = "none";
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
        if (before) paintClip(main, before, before.duration + local, w, h, env, { type: "out", kind: trans.type, p }, opts);
        paintClip(main, clip, local, w, h, env, { type: "in", kind: trans.type, p }, opts);
      } else paintClip(main, clip, local, w, h, env, { type: "none", kind: "", p: 1 }, opts);
    }
  }
}

export function drawSwatch(g: CanvasRenderingContext2D, kind: string, w: number, h: number, from: string, to: string): void {
  const p = 0.5;
  g.fillStyle = from;
  g.fillRect(0, 0, w, h);
  g.save();
  let dx = 0;
  let dy = 0;
  let zoom = 1;
  let alpha = 1;
  if (kind === "crossfade" || kind === "dissolve" || kind === "blur-fade" || kind === "dip") alpha = p;
  else if (kind === "slide-left" || kind === "push-up" || kind === "slide-right" || kind === "push-down") {
    const horizontal = kind.startsWith("slide");
    const sign = kind === "slide-left" || kind === "push-up" ? 1 : -1;
    g.fillStyle = from;
    g.fillRect(horizontal ? -sign * w * p : 0, horizontal ? 0 : -sign * h * p, w, h);
    if (horizontal) dx = sign * w * (1 - p);
    else dy = sign * h * (1 - p);
  } else if (kind === "cover-left") dx = w * (1 - p);
  else if (kind === "cover-up") dy = h * (1 - p);
  else if (kind === "zoom" || kind === "spin") {
    zoom = 0.5 + 0.5 * p;
    alpha = p;
  } else if (revealRegion(g, kind, p, w, h)) g.clip();
  g.globalAlpha = alpha;
  g.translate(w / 2, h / 2);
  g.scale(zoom, zoom);
  if (kind === "spin") g.rotate(-Math.PI / 2);
  g.translate(-w / 2, -h / 2);
  g.fillStyle = to;
  g.fillRect(dx, dy, w, h);
  g.restore();
}

export function defaultMask(shape: ClipMask["shape"] = "ellipse"): ClipMask {
  return { shape, x: 22, y: 18, w: 56, h: 64, feather: 6, angle: 0 };
}
