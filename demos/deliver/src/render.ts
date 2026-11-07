import type { Clip, ProjectState } from "../../../frontend/src/engine/types";
import { wordTimes } from "./captions";
import { drawFrame } from "../../grade/src/render";
import type { FrameEnv } from "../../grade/src/render";

export const CAPTIONS_TRACK = "Captions";

interface Placed {
  text: string;
  x: number;
  y: number;
  width: number;
  index: number;
}

function layout(ctx: CanvasRenderingContext2D, words: string[], maxWidth: number, lineH: number): { placed: Placed[]; lines: number } {
  const space = ctx.measureText(" ").width;
  const rows: Array<Array<{ text: string; width: number; index: number }>> = [[]];
  let used = 0;
  words.forEach((text, index) => {
    const width = ctx.measureText(text).width;
    const row = rows[rows.length - 1];
    if (row.length && used + space + width > maxWidth) {
      rows.push([]);
      used = 0;
    }
    rows[rows.length - 1].push({ text, width, index });
    used += (used ? space : 0) + width;
  });
  const placed: Placed[] = [];
  rows.forEach((row, r) => {
    const total = row.reduce((sum, item) => sum + item.width, 0) + space * (row.length - 1);
    let x = -total / 2;
    for (const item of row) {
      placed.push({ text: item.text, x: x + item.width / 2, y: (r - (rows.length - 1) / 2) * lineH, width: item.width, index: item.index });
      x += item.width + space;
    }
  });
  return { placed, lines: rows.length };
}

function drawCaption(ctx: CanvasRenderingContext2D, clip: Clip, local: number, w: number, h: number): void {
  const style = clip.textStyle;
  if (!style) return;
  const content = style.content || clip.label;
  const words = clip.words?.length ? clip.words : wordTimes(content, clip.duration);
  const px = (style.size / 100) * h;
  const lineH = px * 1.28;
  const posX = clip.transform?.posX ?? 0;
  const posY = clip.transform?.posY ?? 0;
  ctx.save();
  ctx.translate(w / 2 + (posX / 100) * w, h / 2 + (posY / 100) * h);
  ctx.font = `${style.bold ? 700 : 500} ${px}px system-ui, -apple-system, "Segoe UI", sans-serif`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.lineJoin = "round";
  const { placed } = layout(ctx, words.map((word) => word.text), w * 0.86, lineH);
  const mode = style.wordStyle?.mode;
  const accent = style.wordStyle?.colour ?? "#ffd23f";
  const fade = Math.min(1, local / 0.18, (clip.duration - local) / 0.18);
  ctx.globalAlpha = Math.max(0, fade);
  placed.forEach((item) => {
    const word = words[item.index];
    const active = local >= word.t && local < word.t + word.d;
    const spoken = local >= word.t;
    if (mode === "reveal" && !spoken) return;
    const x = item.x;
    let y = item.y;
    let size = 1;
    if (mode === "pop" && active) size = 1.2;
    if (mode === "rise" && active) y -= px * 0.12;
    if (mode === "box" && active) {
      ctx.fillStyle = accent;
      ctx.beginPath();
      ctx.roundRect(x - item.width / 2 - px * 0.18, y - lineH * 0.46, item.width + px * 0.36, lineH * 0.92, px * 0.22);
      ctx.fill();
    }
    ctx.save();
    ctx.translate(x, y);
    ctx.scale(size, size);
    if (style.outlineWidth && !(mode === "box" && active)) {
      ctx.lineWidth = style.outlineWidth * (h / 720);
      ctx.strokeStyle = style.outlineColor ?? "black";
      ctx.strokeText(item.text, 0, 0);
    }
    ctx.shadowColor = "rgba(0,0,0,0.6)";
    ctx.shadowBlur = (style.shadowBlur ?? 0) * (h / 720);
    ctx.fillStyle = mode === "highlight" && active ? accent : mode === "box" && active ? "#101010" : (word as { colour?: string }).colour ?? style.color;
    ctx.fillText(item.text, 0, 0);
    ctx.restore();
  });
  ctx.restore();
}

export function drawDeliver(ctx: CanvasRenderingContext2D, state: ProjectState, t: number, env: FrameEnv, captions: boolean): void {
  const timeline = state.timelines[state.activeTimeline];
  const hidden = { ...state, timelines: state.timelines.map((tl, i) => (i === state.activeTimeline ? { ...tl, tracks: tl.tracks.map((track) => (track.name === CAPTIONS_TRACK ? { ...track, hidden: true } : track)) } : tl)) };
  drawFrame(ctx, hidden, t, env);
  if (!captions) return;
  const track = timeline.tracks.find((entry) => entry.name === CAPTIONS_TRACK);
  if (!track || track.hidden) return;
  const w = ctx.canvas.width;
  const h = ctx.canvas.height;
  for (const clip of track.clips) {
    const local = t - clip.start;
    if (local >= 0 && local < clip.duration) drawCaption(ctx, clip, local, w, h);
  }
}
