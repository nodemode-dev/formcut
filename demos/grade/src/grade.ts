import { pchip } from "../../../frontend/src/ui/color-section";
import { COLOUR_NEUTRAL } from "../../../frontend/src/engine/types";
import type { Clip, ColorGrade, ColourPanel } from "../../../frontend/src/engine/types";
import { lookById } from "./looks";
import type { GradeParams } from "./looks";

const N = 33;
const LUMA = [0.2126, 0.7152, 0.0722];
const CURVE_SIZE = 1024;
const WHEELS = ["offset", "gain", "lift", "gamma"] as const;

type Stage = (c: Float64Array) => void;

interface Cube {
  name: string;
  size: number;
  low: number;
  high: number;
  table: Float32Array;
}

const cubes = new Map<string, Cube>();
const lattices = new Map<string, Float32Array>();
const falloffs = new Map<string, Float32Array>();

const clamp01 = (v: number): number => (v < 0 ? 0 : v > 1 ? 1 : v);
const lumaOf = (c: Float64Array): number => LUMA[0] * c[0] + LUMA[1] * c[1] + LUMA[2] * c[2];

export function parseCube(text: string): Omit<Cube, "name"> {
  let size = 0;
  let low = 0;
  let high = 1;
  const values: number[] = [];
  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line || line.startsWith("#") || line.startsWith("TITLE")) continue;
    const parts = line.split(/\s+/);
    if (parts[0] === "LUT_3D_SIZE") size = Number(parts[1]);
    else if (parts[0] === "LUT_1D_SIZE") throw new Error("Only 3D .cube LUTs are supported");
    else if (parts[0] === "DOMAIN_MIN") low = Number(parts[1]);
    else if (parts[0] === "DOMAIN_MAX") high = Number(parts[1]);
    else if (parts.length === 3 && parts.every((p) => Number.isFinite(Number(p)))) values.push(Number(parts[0]), Number(parts[1]), Number(parts[2]));
  }
  if (size < 2 || size > 65 || values.length !== size ** 3 * 3) throw new Error("That .cube file is not a valid 3D LUT");
  if (!(high > low)) throw new Error("LUT color domain is invalid");
  return { size, low, high, table: Float32Array.from(values) };
}

export function registerCube(name: string, text: string): string {
  const parsed = parseCube(text);
  const id = `cube-${cubes.size + 1}-${name.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}`;
  cubes.set(id, { name, ...parsed });
  return id;
}

export const cubeName = (id: string | undefined): string | undefined => (id ? cubes.get(id)?.name : undefined);

function sampleCube(cube: Cube, c: Float64Array): void {
  const n = cube.size;
  const span = cube.high - cube.low;
  const pos = [0, 1, 2].map((i) => clamp01((c[i] - cube.low) / span) * (n - 1));
  const base = pos.map((p) => Math.min(n - 2, Math.floor(p)));
  const frac = pos.map((p, i) => p - base[i]);
  const out = [0, 0, 0];
  for (let k = 0; k < 8; k += 1) {
    const dr = k & 1;
    const dg = (k >> 1) & 1;
    const db = (k >> 2) & 1;
    const w = (dr ? frac[0] : 1 - frac[0]) * (dg ? frac[1] : 1 - frac[1]) * (db ? frac[2] : 1 - frac[2]);
    if (w === 0) continue;
    const at = (((base[2] + db) * n + base[1] + dg) * n + base[0] + dr) * 3;
    out[0] += cube.table[at] * w;
    out[1] += cube.table[at + 1] * w;
    out[2] += cube.table[at + 2] * w;
  }
  c[0] = out[0];
  c[1] = out[1];
  c[2] = out[2];
}

function panelStage(panel: ColourPanel | undefined): Stage | null {
  if (!panel) return null;
  const v = (key: keyof ColourPanel): number => panel[key] ?? COLOUR_NEUTRAL[key];
  const temperature = v("temperature");
  const tint = v("tint") / 100;
  const exposure = v("exposure");
  const brightness = v("brightness") / 100;
  const contrast = 1 + v("contrast") / 100;
  const highlights = v("highlights") / 100;
  const shadows = v("shadows") / 100;
  const whites = v("whites") / 100;
  const blacks = v("blacks") / 100;
  const saturationValue = v("saturation");
  const fade = v("fade") / 100;
  const active = temperature !== 6500 || tint || exposure || brightness || contrast !== 1 || highlights || shadows || whites || blacks || saturationValue || fade;
  if (!active) return null;
  const shift = (6500 - Math.max(2000, Math.min(11000, temperature))) / 4500;
  const gains = [1 + 0.22 * shift, 1, 1 - 0.22 * shift];
  const gain = 2 ** exposure;
  const saturation = 1 + saturationValue / 100;
  const needsLuma = Boolean(highlights || shadows || whites || blacks || saturationValue);
  return (c) => {
    for (let i = 0; i < 3; i += 1) c[i] *= gains[i];
    if (tint) {
      c[1] *= 1 + 0.25 * tint;
      c[0] *= 1 - 0.1 * tint;
      c[2] *= 1 - 0.1 * tint;
    }
    for (let i = 0; i < 3; i += 1) {
      c[i] *= gain;
      c[i] += brightness;
      if (contrast !== 1) c[i] = (c[i] - 0.5) * contrast + 0.5;
    }
    let lum = 0;
    if (needsLuma) {
      lum = LUMA[0] * Math.min(4, Math.max(0, c[0])) + LUMA[1] * Math.min(4, Math.max(0, c[1])) + LUMA[2] * Math.min(4, Math.max(0, c[2]));
      const high = Math.max(0, lum - 0.5) * 2;
      const low = Math.max(0, 0.5 - lum) * 2;
      const dark = 1 - lum;
      const add = high * highlights + low * shadows + lum * lum * lum * whites + dark * dark * dark * blacks;
      c[0] += add;
      c[1] += add;
      c[2] += add;
      if (saturation !== 1) for (let i = 0; i < 3; i += 1) c[i] = lum + (c[i] - lum) * saturation;
    }
    if (fade) for (let i = 0; i < 3; i += 1) c[i] = c[i] * (1 - 0.35 * fade) + 0.12 * fade;
  };
}

const curveActive = (points: number[][] | undefined, neutral?: number): boolean =>
  Boolean(points && points.length >= 2 && points.some((p) => Math.abs(neutral === undefined ? p[0] - p[1] : p[1] - neutral) > 1e-9));

function curveTable(points: number[][], periodic: boolean): Float32Array {
  const sorted = points.map((p) => [...p]).sort((a, b) => a[0] - b[0]);
  const grid = Array.from({ length: CURVE_SIZE }, (_, i) => i / (CURVE_SIZE - 1));
  return Float32Array.from(pchip(sorted, grid, periodic));
}

const lookup = (table: Float32Array, x: number): number => {
  const at = clamp01(x) * (CURVE_SIZE - 1);
  const i = Math.min(CURVE_SIZE - 2, Math.floor(at));
  return table[i] + (table[i + 1] - table[i]) * (at - i);
};

function rgbToHsv(r: number, g: number, b: number): [number, number, number] {
  const max = Math.max(r, g, b);
  const min = Math.min(r, g, b);
  const d = max - min;
  let h = 0;
  if (d > 0) {
    if (max === r) h = ((g - b) / d) % 6;
    else if (max === g) h = (b - r) / d + 2;
    else h = (r - g) / d + 4;
    h *= 60;
    if (h < 0) h += 360;
  }
  return [h, max > 0 ? d / max : 0, max];
}

function hsvToRgb(h: number, s: number, v: number): [number, number, number] {
  const k = (n: number) => (n + h / 60) % 6;
  const f = (n: number) => v - v * s * Math.max(0, Math.min(k(n), 4 - k(n), 1));
  return [f(5), f(3), f(1)];
}

function gradeStage(grade: ColorGrade | undefined): Stage | null {
  if (!grade) return null;
  const level = WHEELS.map((w) => {
    const l = grade[w] ?? {};
    const y = l.y ?? 0;
    return [(l.r ?? 0) + y, (l.g ?? 0) + y, (l.b ?? 0) + y];
  });
  const [offset, gain, lift, gamma] = level;
  const has = (v: number[]) => v.some((x) => Math.abs(x) > 1e-9);
  const contrast = grade.contrast ?? 1;
  const pivot = grade.pivot ?? 0.435;
  const boost = grade.boost ?? 0;
  const hue = grade.hue ?? 0;
  const curves = grade.curves ?? {};
  const master = curveActive(curves.y) ? curveTable(curves.y!, false) : null;
  const channel = (["r", "g", "b"] as const).map((key) => (curveActive(curves[key]) ? curveTable(curves[key]!, false) : null));
  const hueHue = curveActive(grade.hueHue, 0) ? curveTable(grade.hueHue!, true) : null;
  const hueSat = curveActive(grade.hueSat, 1) ? curveTable(grade.hueSat!, true) : null;
  const lumSat = curveActive(grade.lumSat, 1) ? curveTable(grade.lumSat!, false) : null;
  const anything = has(offset) || has(gain) || has(lift) || has(gamma) || Math.abs(contrast - 1) > 1e-9 || Math.abs(boost) > 1e-9 || Math.abs(hue) > 1e-9 || master || channel.some(Boolean) || hueHue || hueSat || lumSat;
  if (!anything) return null;
  const gammaPower = gamma.map((g) => 2 ** (-g * 1.2));
  const angle = (hue * Math.PI) / 180;
  return (c) => {
    if (has(gain)) for (let i = 0; i < 3; i += 1) c[i] *= 1 + gain[i];
    if (has(lift)) for (let i = 0; i < 3; i += 1) c[i] += lift[i] * 0.5 * (1 - c[i]);
    if (has(gamma)) for (let i = 0; i < 3; i += 1) c[i] = Math.max(c[i], 0) ** gammaPower[i];
    if (has(offset)) for (let i = 0; i < 3; i += 1) c[i] += offset[i] * 0.5;
    if (Math.abs(contrast - 1) > 1e-9) for (let i = 0; i < 3; i += 1) c[i] = (c[i] - pivot) * contrast + pivot;
    if (Math.abs(boost) > 1e-9) {
      const luma = lumaOf(c);
      const spread = Math.max(clamp01(c[0]), clamp01(c[1]), clamp01(c[2])) - Math.min(clamp01(c[0]), clamp01(c[1]), clamp01(c[2]));
      const k = 1 + boost * (1 - spread);
      for (let i = 0; i < 3; i += 1) c[i] = luma + (c[i] - luma) * k;
    }
    if (Math.abs(hue) > 1e-9) {
      const luma = lumaOf(c);
      let cb = (c[2] - luma) / 1.8556;
      let cr = (c[0] - luma) / 1.5748;
      const rotated = [cb * Math.cos(angle) - cr * Math.sin(angle), cb * Math.sin(angle) + cr * Math.cos(angle)];
      cb = rotated[0];
      cr = rotated[1];
      const red = luma + 1.5748 * cr;
      const blue = luma + 1.8556 * cb;
      c[0] = red;
      c[1] = (luma - LUMA[0] * red - LUMA[2] * blue) / LUMA[1];
      c[2] = blue;
    }
    if (master) for (let i = 0; i < 3; i += 1) c[i] = lookup(master, c[i]);
    for (let i = 0; i < 3; i += 1) if (channel[i]) c[i] = lookup(channel[i]!, c[i]);
    if (hueHue || hueSat || lumSat) {
      const luma = clamp01(lumaOf(c));
      const [h, s, v] = rgbToHsv(clamp01(c[0]), clamp01(c[1]), clamp01(c[2]));
      const position = h / 360;
      let nh = h;
      let ns = s;
      if (hueHue) nh = (h + lookup(hueHue, position) * 360 + 720) % 360;
      if (hueSat) ns *= lookup(hueSat, position);
      if (lumSat) ns *= lookup(lumSat, luma);
      const rgb = hsvToRgb(nh, clamp01(ns), v);
      c[0] = rgb[0];
      c[1] = rgb[1];
      c[2] = rgb[2];
    }
  };
}

function lookStage(params: GradeParams): Stage {
  const p = params;
  const exposure = 2 ** (p.exposure ?? 0);
  const contrast = p.contrast ?? 1;
  const lift = p.lift ?? 0;
  const gamma = p.gamma ?? 1;
  const saturation = p.saturation ?? 1;
  const vibrance = p.vibrance ?? 0;
  const warm = (p.temperature ?? 0) * 0.35;
  const tint = (p.tint ?? 0) * 0.35;
  const sepia = p.sepia ?? 0;
  const shadows = [p.shadows_r ?? 0, p.shadows_g ?? 0, p.shadows_b ?? 0];
  const highlights = [p.highlights_r ?? 0, p.highlights_g ?? 0, p.highlights_b ?? 0];
  return (c) => {
    for (let i = 0; i < 3; i += 1) c[i] = Math.max((c[i] * exposure - 0.5) * contrast + 0.5 + lift, 0) ** gamma;
    const lum = lumaOf(c);
    const spread = Math.max(clamp01(c[0]), clamp01(c[1]), clamp01(c[2])) - Math.min(clamp01(c[0]), clamp01(c[1]), clamp01(c[2]));
    const k = saturation + vibrance * (1 - spread);
    for (let i = 0; i < 3; i += 1) c[i] = lum + (c[i] - lum) * k;
    c[0] += warm;
    c[1] -= tint;
    c[2] -= warm;
    const dark = (1 - lum) ** 2;
    const bright = lum ** 2;
    for (let i = 0; i < 3; i += 1) c[i] += shadows[i] * dark + highlights[i] * bright;
    if (sepia) {
      const r = c[0] * 0.393 + c[1] * 0.769 + c[2] * 0.189;
      const g = c[0] * 0.349 + c[1] * 0.686 + c[2] * 0.168;
      const b = c[0] * 0.272 + c[1] * 0.534 + c[2] * 0.131;
      c[0] = c[0] * (1 - sepia) + r * sepia;
      c[1] = c[1] * (1 - sepia) + g * sepia;
      c[2] = c[2] * (1 - sepia) + b * sepia;
    }
  };
}

export interface GradeFrame {
  lattice: Float32Array | null;
  panelVignette: number;
  vignette: number;
}

export function gradeKey(clip: Clip): string {
  return JSON.stringify([clip.colour, clip.colorGrade, clip.effectId, clip.lutId, clip.lutIntensity]);
}

function buildLattice(clip: Clip): Float32Array | null {
  const panelOnly = clip.colour ? { ...clip.colour, vignette: 0, sharpen: 0 } : undefined;
  const panel = panelStage(panelOnly);
  const grade = gradeStage(clip.colorGrade);
  const look = lookById(clip.effectId);
  const cube = clip.lutId ? cubes.get(clip.lutId) : undefined;
  if (!panel && !grade && !look && !cube) return null;
  const strength = clip.lutIntensity ?? 1;
  const lookRun = look ? lookStage(look.params) : null;
  const table = new Float32Array(N * N * N * 3);
  const c = new Float64Array(3);
  const before = new Float64Array(3);
  let at = 0;
  for (let b = 0; b < N; b += 1) {
    for (let g = 0; g < N; g += 1) {
      for (let r = 0; r < N; r += 1) {
        c[0] = r / (N - 1);
        c[1] = g / (N - 1);
        c[2] = b / (N - 1);
        if (panel) {
          panel(c);
          for (let i = 0; i < 3; i += 1) c[i] = clamp01(c[i]);
        }
        if (grade) {
          grade(c);
          for (let i = 0; i < 3; i += 1) c[i] = clamp01(c[i]);
        }
        if (lookRun || cube) {
          before.set(c);
          if (lookRun) {
            lookRun(c);
            for (let i = 0; i < 3; i += 1) c[i] = clamp01(c[i]);
          }
          if (cube) sampleCube(cube, c);
          for (let i = 0; i < 3; i += 1) c[i] = before[i] + (clamp01(c[i]) - before[i]) * strength;
        }
        table[at] = clamp01(c[0]);
        table[at + 1] = clamp01(c[1]);
        table[at + 2] = clamp01(c[2]);
        at += 3;
      }
    }
  }
  return table;
}

export function latticeFor(clip: Clip): Float32Array | null {
  const key = gradeKey(clip);
  if (lattices.has(key)) {
    const hit = lattices.get(key)!;
    lattices.delete(key);
    lattices.set(key, hit);
    return hit.length ? hit : null;
  }
  const built = buildLattice(clip);
  lattices.set(key, built ?? new Float32Array(0));
  if (lattices.size > 64) lattices.delete(lattices.keys().next().value as string);
  return built;
}

export function applyLattice(data: Uint8ClampedArray, table: Float32Array): void {
  const scale = (N - 1) / 255;
  const n2 = N * N;
  for (let i = 0; i < data.length; i += 4) {
    if (data[i + 3] === 0) continue;
    const fr = data[i] * scale;
    const fg = data[i + 1] * scale;
    const fb = data[i + 2] * scale;
    const r0 = fr >= N - 1 ? N - 2 : fr | 0;
    const g0 = fg >= N - 1 ? N - 2 : fg | 0;
    const b0 = fb >= N - 1 ? N - 2 : fb | 0;
    const dr = fr - r0;
    const dg = fg - g0;
    const db = fb - b0;
    const o = (b0 * n2 + g0 * N + r0) * 3;
    const o1 = o + 3;
    const o2 = o + N * 3;
    const o3 = o2 + 3;
    const o4 = o + n2 * 3;
    const o5 = o4 + 3;
    const o6 = o4 + N * 3;
    const o7 = o6 + 3;
    for (let ch = 0; ch < 3; ch += 1) {
      const a0 = table[o + ch] + (table[o1 + ch] - table[o + ch]) * dr;
      const a1 = table[o2 + ch] + (table[o3 + ch] - table[o2 + ch]) * dr;
      const a2 = table[o4 + ch] + (table[o5 + ch] - table[o4 + ch]) * dr;
      const a3 = table[o6 + ch] + (table[o7 + ch] - table[o6 + ch]) * dr;
      const b0v = a0 + (a1 - a0) * dg;
      const b1v = a2 + (a3 - a2) * dg;
      data[i + ch] = (b0v + (b1v - b0v) * db) * 255 + 0.5;
    }
  }
}

function falloffBase(w: number, h: number): Float32Array {
  const key = `${w}x${h}`;
  let q = falloffs.get(key);
  if (!q) {
    q = new Float32Array(w * h);
    for (let y = 0; y < h; y += 1) {
      const v = (y + 0.5) / h - 0.5;
      for (let x = 0; x < w; x += 1) {
        const u = (x + 0.5) / w - 0.5;
        q[y * w + x] = u * u + v * v;
      }
    }
    if (falloffs.size > 4) falloffs.clear();
    falloffs.set(key, q);
  }
  return q;
}

export function applyVignette(data: Uint8ClampedArray, w: number, h: number, panel: number, effect: number): void {
  if (panel <= 0 && effect <= 0) return;
  const q = falloffBase(w, h);
  for (let p = 0, i = 0; p < q.length; p += 1, i += 4) {
    let m = 1;
    if (panel > 0) m *= Math.min(1, Math.max(0, 1 - 4 * q[p] * panel));
    if (effect > 0) m *= 1 - effect * (1 - Math.min(1, Math.max(0, 1 - 2.2 * q[p])));
    data[i] *= m;
    data[i + 1] *= m;
    data[i + 2] *= m;
  }
}
