import { t } from "../i18n";
import type { ProjectEngine } from "../engine/project";
import { COLOUR_NEUTRAL, type Clip, type ColorGrade, type ColourPanel, type WheelLevels } from "../engine/types";
import { icon } from "./icons";

/**
 * The Color section: scopes, the four wheels, primaries, curves and the basic
 * panel for the selected video or image clip. The engine renders the grade
 * (backend/app/color_grade.py), so preview and export match; this draws the
 * controls, reads the preview frame for the scopes, and sends clip.colour.
 */

type Wheel = "lift" | "gamma" | "gain" | "offset";
type Curve = "y" | "r" | "g" | "b" | "hueHue" | "hueSat" | "lumSat";
type Scope = "waveform" | "parade" | "vectorscope" | "histogram";

const WHEELS: Wheel[] = ["lift", "gamma", "gain", "offset"];
const CURVES: Curve[] = ["y", "r", "g", "b", "hueHue", "hueSat", "lumSat"];
const SCOPES: Scope[] = ["waveform", "parade", "vectorscope", "histogram"];
const WHEEL_REACH = 0.25; // the channel offset at the wheel's rim
const PRIMARIES: Array<["contrast" | "pivot" | "boost" | "hue", number, number, number, number]> = [
  ["contrast", 0, 2, 0.01, 1],
  ["pivot", 0, 1, 0.005, 0.435],
  ["boost", -1, 1, 0.01, 0],
  ["hue", -180, 180, 1, 0],
];
const BASIC: Array<[keyof ColourPanel, number, number, number]> = [
  ["exposure", -5, 5, 0.01],
  ["contrast", -100, 100, 1],
  ["highlights", -100, 100, 1],
  ["shadows", -100, 100, 1],
  ["whites", -100, 100, 1],
  ["blacks", -100, 100, 1],
  ["brightness", -100, 100, 1],
  ["temperature", 2000, 11000, 50],
  ["tint", -100, 100, 1],
  ["saturation", -100, 100, 1],
  ["fade", 0, 100, 1],
  ["sharpen", 0, 100, 1],
  ["vignette", -100, 100, 1],
];
/** Each curve's value range and neutral value; the channel curves are identity by default. */
const RANGES: Record<Curve, [number, number, number | null]> = {
  y: [0, 1, null],
  r: [0, 1, null],
  g: [0, 1, null],
  b: [0, 1, null],
  hueHue: [-0.5, 0.5, 0],
  hueSat: [0, 2, 1],
  lumSat: [0, 2, 1],
};
const STROKE: Record<Curve, string> = { y: "var(--ink)", r: "#ff5a5a", g: "#4fd37a", b: "#5a8cff", hueHue: "var(--cue)", hueSat: "var(--cue)", lumSat: "var(--cue)" };

let copied: { colour?: ColourPanel; grade?: ColorGrade } | null = null;

/** Monotone cubic interpolation, the engine's own (Fritsch and Carlson), so the drawn curve is the applied one. */
export function pchip(points: number[][], at: number[], periodic: boolean): number[] {
  let xs = points.map((p) => p[0]);
  let ys = points.map((p) => p[1]);
  if (periodic) {
    xs = [...xs.map((x) => x - 1), ...xs, ...xs.map((x) => x + 1)];
    ys = [...ys, ...ys, ...ys];
  }
  const n = xs.length;
  const h = xs.slice(1).map((x, i) => x - xs[i]);
  const delta = h.map((w, i) => (ys[i + 1] - ys[i]) / w);
  const slopes = new Array<number>(n).fill(0);
  for (let i = 1; i < n - 1; i++) {
    if (delta[i - 1] * delta[i] > 0) {
      const w1 = 2 * h[i] + h[i - 1];
      const w2 = h[i] + 2 * h[i - 1];
      slopes[i] = (w1 + w2) / (w1 / delta[i - 1] + w2 / delta[i]);
    }
  }
  slopes[0] = delta[0];
  slopes[n - 1] = delta[n - 2];
  return at.map((x) => {
    let i = 0;
    while (i < n - 2 && xs[i + 1] < x) i++;
    const t = (x - xs[i]) / h[i];
    const t2 = t * t;
    const t3 = t2 * t;
    return (2 * t3 - 3 * t2 + 1) * ys[i] + (t3 - 2 * t2 + t) * h[i] * slopes[i] + (-2 * t3 + 3 * t2) * ys[i + 1] + (t3 - t2) * h[i] * slopes[i + 1];
  });
}

function defaultPoints(curve: Curve): number[][] {
  if (curve === "hueHue" || curve === "hueSat") return [0, 1, 2, 3, 4, 5].map((i) => [i / 6, RANGES[curve][2] as number]);
  if (curve === "lumSat") return [0, 0.25, 0.5, 0.75, 1].map((x) => [x, 1]);
  return [
    [0, 0],
    [1, 1],
  ];
}

export function buildColorSection(engine: ProjectEngine): HTMLElement {
  const section = document.createElement("div");
  section.className = "section color-section";
  section.dataset.section = "color";
  section.dataset.feature = "section.color";
  section.innerHTML = `
    <div class="section-head">${t("sec.color")} ${icon("chevD")}</div>
    <p class="color-hint" data-ref="empty">${t("color.noClip")}</p>
    <div data-ref="tools">
      <div class="color-sub">${t("color.scopes")}</div>
      <div class="color-scope-wrap">
        <select class="mini-select" data-ref="scope-mode">${SCOPES.map((s) => `<option value="${s}">${t(`color.${s}`)}</option>`).join("")}</select>
        <canvas class="color-scope" data-ref="scope" width="320" height="180"></canvas>
      </div>
      <div class="color-sub">${t("color.wheels")}</div>
      <div class="color-wheels">${WHEELS.map(
        (w) => `<div class="color-wheel" data-wheel="${w}"><canvas width="232" height="232" title="${t("color.wheelHint")}"></canvas>
          <span class="wheel-name">${t(`color.${w}`)}</span>
          <input type="range" min="-1" max="1" step="0.005" value="0" data-master="${w}" aria-label="${t(`color.${w}`)}" /><output data-readout="${w}"></output></div>`,
      ).join("")}</div>
      <div class="color-sub">${t("color.primaries")}</div>
      ${PRIMARIES.map(
        ([key, min, max, step, neutral]) =>
          `<div class="prop-row"><span>${t(`color.${key}`)}</span><input type="range" min="${min}" max="${max}" step="${step}" value="${neutral}" data-primary="${key}" /><output class="prop-aux" data-primary-out="${key}"></output></div>`,
      ).join("")}
      <div class="color-sub">${t("color.curves")}</div>
      <div class="color-curve-tabs" data-ref="curve-tabs">${CURVES.map((c) => `<button type="button" data-curve="${c}" aria-pressed="${c === "y"}">${t(`color.curve.${c}`)}</button>`).join("")}</div>
      <svg class="color-curve" data-ref="curve" viewBox="0 0 200 200"></svg>
      <p class="color-hint">${t("color.curveHint")}</p>
      <div class="color-sub">${t("color.basic")}</div>
      ${BASIC.map(
        ([key, min, max, step]) =>
          `<div class="prop-row"><span>${t(`color.${key}`)}</span><input type="range" min="${min}" max="${max}" step="${step}" value="${COLOUR_NEUTRAL[key]}" data-basic="${key}" /><output class="prop-aux" data-basic-out="${key}"></output></div>`,
      ).join("")}
      <div class="color-actions">
        <button type="button" class="tool-chip" data-ref="reset">${t("color.reset")}</button>
        <button type="button" class="tool-chip" data-ref="copy">${t("color.copy")}</button>
        <button type="button" class="tool-chip" data-ref="paste">${t("color.paste")}</button>
      </div>
    </div>`;
  const ref = <T extends Element>(name: string) => section.querySelector<T>(`[data-ref="${name}"]`)!;
  const tools = ref<HTMLElement>("tools");
  const empty = ref<HTMLElement>("empty");
  let grade: ColorGrade = {};
  let curve: Curve = "y";
  let dragging = false;

  const clip = (): Clip | undefined => {
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id)?.clip : undefined;
    return found && (found.kind === "video" || found.kind === "image") ? found : undefined;
  };
  const sendGrade = () => {
    const target = clip();
    if (target) engine.dispatch("clip.colour", { clipId: target.id, grade: structuredClone(grade) });
  };

  // Wheels -------------------------------------------------------------------
  const drawWheel = (w: Wheel) => {
    const canvas = section.querySelector<HTMLCanvasElement>(`[data-wheel="${w}"] canvas`)!;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const size = canvas.width;
    const centre = size / 2;
    const rim = size / 2 - 6;
    ctx.clearRect(0, 0, size, size);
    for (let step = 0; step < 72; step++) {
      const from = (-step * 5 * Math.PI) / 180;
      ctx.beginPath();
      ctx.arc(centre, centre, rim, from, from - (5.5 * Math.PI) / 180, true);
      ctx.strokeStyle = `hsl(${step * 5}, 80%, 55%)`;
      ctx.lineWidth = 6;
      ctx.stroke();
    }
    ctx.beginPath();
    ctx.arc(centre, centre, rim - 5, 0, Math.PI * 2);
    ctx.fillStyle = "rgba(20, 20, 24, 0.92)";
    ctx.fill();
    ctx.strokeStyle = "rgba(255, 255, 255, 0.12)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(centre - rim + 8, centre);
    ctx.lineTo(centre + rim - 8, centre);
    ctx.moveTo(centre, centre - rim + 8);
    ctx.lineTo(centre, centre + rim - 8);
    ctx.stroke();
    const level = grade[w] ?? {};
    const r = level.r ?? 0;
    const g = level.g ?? 0;
    const b = level.b ?? 0;
    const x = (1.5 * r) / WHEEL_REACH;
    const y = ((g - b) * Math.sqrt(3)) / (2 * WHEEL_REACH);
    const radius = Math.min(1, Math.hypot(x, y));
    const angle = Math.atan2(y, x);
    const px = centre + Math.cos(angle) * radius * (rim - 10);
    const py = centre - Math.sin(angle) * radius * (rim - 10);
    ctx.beginPath();
    ctx.arc(px, py, 7, 0, Math.PI * 2);
    ctx.fillStyle = radius > 0.001 ? `hsl(${((angle * 180) / Math.PI + 360) % 360}, 80%, 60%)` : "#ddd";
    ctx.fill();
    ctx.strokeStyle = "#fff";
    ctx.lineWidth = 2;
    ctx.stroke();
    const master = section.querySelector<HTMLInputElement>(`[data-master="${w}"]`)!;
    if (!dragging) master.value = String(level.y ?? 0);
    section.querySelector<HTMLOutputElement>(`[data-readout="${w}"]`)!.value = [r, g, b, level.y ?? 0].map((v) => v.toFixed(2)).join(" ");
  };
  const setWheelFromPointer = (w: Wheel, canvas: HTMLCanvasElement, ev: PointerEvent) => {
    const box = canvas.getBoundingClientRect();
    let x = ((ev.clientX - box.left) / box.width) * 2 - 1;
    let y = -(((ev.clientY - box.top) / box.height) * 2 - 1);
    const length = Math.hypot(x, y) / 0.9;
    if (length > 1) {
      x /= length;
      y /= length;
    }
    x /= 0.9;
    y /= 0.9;
    // A point in the chroma plane as three channel offsets that sum to zero, so
    // the wheel shifts the balance and the master level stays where it is.
    const level: WheelLevels = {
      ...(grade[w] ?? {}),
      r: ((2 * x) / 3) * WHEEL_REACH,
      g: (-x / 3 + y / Math.sqrt(3)) * WHEEL_REACH,
      b: (-x / 3 - y / Math.sqrt(3)) * WHEEL_REACH,
    };
    grade = { ...grade, [w]: level };
    drawWheel(w);
    sendGrade();
  };
  for (const w of WHEELS) {
    const canvas = section.querySelector<HTMLCanvasElement>(`[data-wheel="${w}"] canvas`)!;
    canvas.addEventListener("pointerdown", (ev) => {
      if (!clip()) return;
      dragging = true;
      canvas.setPointerCapture(ev.pointerId);
      setWheelFromPointer(w, canvas, ev);
    });
    canvas.addEventListener("pointermove", (ev) => {
      if (dragging && canvas.hasPointerCapture(ev.pointerId)) setWheelFromPointer(w, canvas, ev);
    });
    canvas.addEventListener("pointerup", () => {
      dragging = false;
    });
    canvas.addEventListener("dblclick", () => {
      grade = { ...grade, [w]: { y: grade[w]?.y ?? 0 } };
      drawWheel(w);
      sendGrade();
    });
    section.querySelector<HTMLInputElement>(`[data-master="${w}"]`)!.addEventListener("input", (ev) => {
      grade = { ...grade, [w]: { ...(grade[w] ?? {}), y: Number((ev.target as HTMLInputElement).value) } };
      drawWheel(w);
      sendGrade();
    });
  }

  // Primaries ----------------------------------------------------------------
  for (const [key] of PRIMARIES) {
    section.querySelector<HTMLInputElement>(`[data-primary="${key}"]`)!.addEventListener("input", (ev) => {
      grade = { ...grade, [key]: Number((ev.target as HTMLInputElement).value) };
      section.querySelector<HTMLOutputElement>(`[data-primary-out="${key}"]`)!.value = String(grade[key]);
      sendGrade();
    });
  }

  // Curves ------------------------------------------------------------------
  const svg = ref<SVGSVGElement>("curve");
  const pointsOf = (c: Curve): number[][] => {
    const stored = c === "y" || c === "r" || c === "g" || c === "b" ? grade.curves?.[c] : grade[c];
    return stored && stored.length >= 2 ? stored.map((p) => [...p]) : defaultPoints(c);
  };
  const storePoints = (c: Curve, points: number[][]) => {
    const sorted = [...points].sort((a, b) => a[0] - b[0]);
    if (c === "y" || c === "r" || c === "g" || c === "b") grade = { ...grade, curves: { ...(grade.curves ?? {}), [c]: sorted } };
    else grade = { ...grade, [c]: sorted };
  };
  const toSvg = (c: Curve, x: number, y: number): [number, number] => {
    const [low, high] = RANGES[c];
    return [5 + x * 190, 195 - ((y - low) / (high - low)) * 190];
  };
  const fromSvg = (c: Curve, sx: number, sy: number): [number, number] => {
    const [low, high] = RANGES[c];
    const x = Math.min(1, Math.max(0, (sx - 5) / 190));
    const y = Math.min(high, Math.max(low, low + ((195 - sy) / 190) * (high - low)));
    return [x, y];
  };
  const drawCurve = () => {
    const points = pointsOf(curve);
    const periodic = curve === "hueHue" || curve === "hueSat";
    const samples = Array.from({ length: 97 }, (_, i) => i / 96);
    const values = pchip(points, samples, periodic);
    const [low, high, neutral] = RANGES[curve];
    const clampY = (v: number) => Math.min(high, Math.max(low, v));
    const line = samples.map((x, i) => toSvg(curve, x, clampY(values[i])).map((v) => v.toFixed(1)).join(",")).join(" ");
    const grid = [0.25, 0.5, 0.75]
      .map((f) => `<line x1="${5 + f * 190}" y1="5" x2="${5 + f * 190}" y2="195"/><line x1="5" y1="${5 + f * 190}" x2="195" y2="${5 + f * 190}"/>`)
      .join("");
    const baseline = neutral === null ? `<line x1="5" y1="195" x2="195" y2="5"/>` : (() => {
      const y = toSvg(curve, 0, neutral)[1];
      return `<line x1="5" y1="${y}" x2="195" y2="${y}"/>`;
    })();
    const band = periodic || curve === "lumSat"
      ? Array.from({ length: 24 }, (_, i) => `<rect x="${5 + (i / 24) * 190}" y="191" width="${190 / 24 + 0.5}" height="4" fill="${curve === "lumSat" ? `hsl(0, 0%, ${(i / 23) * 100}%)` : `hsl(${(i / 24) * 360}, 80%, 55%)`}"/>`).join("")
      : "";
    const dots = points.map((p, i) => {
      const [sx, sy] = toSvg(curve, p[0], p[1]);
      return `<circle class="point" data-index="${i}" cx="${sx}" cy="${sy}" r="4.5"/>`;
    }).join("");
    svg.innerHTML = `<g class="grid">${grid}${baseline}</g>${band}<polyline class="curve" stroke="${STROKE[curve]}" points="${line}"/>${dots}`;
  };
  let held: number | null = null;
  const svgPoint = (ev: PointerEvent): [number, number] => {
    const box = svg.getBoundingClientRect();
    return [((ev.clientX - box.left) / box.width) * 200, ((ev.clientY - box.top) / box.height) * 200];
  };
  svg.addEventListener("pointerdown", (ev) => {
    if (!clip()) return;
    const target = ev.target as SVGElement;
    const points = pointsOf(curve);
    if (target.classList.contains("point")) {
      held = Number(target.dataset.index);
    } else {
      const [x, y] = fromSvg(curve, ...svgPoint(ev));
      if (points.some((p) => Math.abs(p[0] - x) < 0.01) || points.length >= 16) return;
      points.push([x, y]);
      points.sort((a, b) => a[0] - b[0]);
      held = points.findIndex((p) => p[0] === x);
      storePoints(curve, points);
      sendGrade();
    }
    dragging = true;
    svg.setPointerCapture(ev.pointerId);
    drawCurve();
  });
  svg.addEventListener("pointermove", (ev) => {
    if (held === null || !svg.hasPointerCapture(ev.pointerId)) return;
    const points = pointsOf(curve);
    let [x, y] = fromSvg(curve, ...svgPoint(ev));
    const fixedEnds = !(curve === "hueHue" || curve === "hueSat");
    if (fixedEnds && (held === 0 || held === points.length - 1)) x = points[held][0];
    else {
      const before = held > 0 ? points[held - 1][0] + 0.01 : 0;
      const after = held < points.length - 1 ? points[held + 1][0] - 0.01 : 1;
      x = Math.min(after, Math.max(before, x));
    }
    points[held] = [x, y];
    storePoints(curve, points);
    drawCurve();
    sendGrade();
  });
  svg.addEventListener("pointerup", () => {
    held = null;
    dragging = false;
  });
  svg.addEventListener("dblclick", (ev) => {
    const target = ev.target as SVGElement;
    if (!target.classList.contains("point")) return;
    const points = pointsOf(curve);
    const index = Number(target.dataset.index);
    const fixedEnds = !(curve === "hueHue" || curve === "hueSat");
    if (points.length <= 2 || (fixedEnds && (index === 0 || index === points.length - 1))) return;
    points.splice(index, 1);
    storePoints(curve, points);
    drawCurve();
    sendGrade();
  });
  ref<HTMLElement>("curve-tabs").addEventListener("click", (ev) => {
    const button = (ev.target as HTMLElement).closest<HTMLButtonElement>("[data-curve]");
    if (!button) return;
    curve = button.dataset.curve as Curve;
    for (const other of ref<HTMLElement>("curve-tabs").querySelectorAll<HTMLButtonElement>("[data-curve]")) other.setAttribute("aria-pressed", String(other === button));
    drawCurve();
  });

  // Basic --------------------------------------------------------------------
  for (const [key] of BASIC) {
    section.querySelector<HTMLInputElement>(`[data-basic="${key}"]`)!.addEventListener("input", (ev) => {
      const target = clip();
      if (!target) return;
      const value = Number((ev.target as HTMLInputElement).value);
      section.querySelector<HTMLOutputElement>(`[data-basic-out="${key}"]`)!.value = String(value);
      engine.dispatch("clip.colour", { clipId: target.id, colour: { [key]: value } });
    });
  }

  // Actions ------------------------------------------------------------------
  ref<HTMLButtonElement>("reset").addEventListener("click", () => {
    const target = clip();
    if (target) engine.dispatch("clip.colour", { clipId: target.id, colour: null, grade: null });
  });
  ref<HTMLButtonElement>("copy").addEventListener("click", () => {
    const target = clip();
    if (target) copied = { colour: structuredClone(target.colour), grade: structuredClone(target.colorGrade) };
  });
  ref<HTMLButtonElement>("paste").addEventListener("click", () => {
    const target = clip();
    if (target && copied) engine.dispatch("clip.colour", { clipId: target.id, colour: copied.colour ?? null, grade: copied.grade ?? null });
  });

  // Scopes -------------------------------------------------------------------
  const scope = ref<HTMLCanvasElement>("scope");
  const sampler = document.createElement("canvas");
  sampler.width = 240;
  sampler.height = 135;
  const drawScope = () => {
    if (section.dataset.tabHidden === "true" || tools.hidden) return;
    const source = document.querySelector<HTMLCanvasElement>("canvas.render-canvas");
    const sctx = sampler.getContext("2d", { willReadFrequently: true });
    const ctx = scope.getContext("2d");
    if (!source || !sctx || !ctx || !source.width) return;
    sctx.drawImage(source, 0, 0, sampler.width, sampler.height);
    const pixels = sctx.getImageData(0, 0, sampler.width, sampler.height).data;
    const w = scope.width;
    const h = scope.height;
    const out = ctx.createImageData(w, h);
    const add = (x: number, y: number, r: number, g: number, b: number) => {
      if (x < 0 || y < 0 || x >= w || y >= h) return;
      const i = (Math.floor(y) * w + Math.floor(x)) * 4;
      out.data[i] = Math.min(255, out.data[i] + r);
      out.data[i + 1] = Math.min(255, out.data[i + 1] + g);
      out.data[i + 2] = Math.min(255, out.data[i + 2] + b);
      out.data[i + 3] = 255;
    };
    const mode = ref<HTMLSelectElement>("scope-mode").value as Scope;
    const sw = sampler.width;
    for (let i = 0; i < pixels.length; i += 4) {
      const r = pixels[i] / 255;
      const g = pixels[i + 1] / 255;
      const b = pixels[i + 2] / 255;
      const column = (i / 4) % sw;
      const luma = 0.2126 * r + 0.7152 * g + 0.0722 * b;
      if (mode === "waveform") add((column / sw) * w, (1 - luma) * (h - 1), 22, 34, 22);
      else if (mode === "parade") {
        const third = w / 3;
        add((column / sw) * third, (1 - r) * (h - 1), 48, 10, 10);
        add(third + (column / sw) * third, (1 - g) * (h - 1), 10, 48, 10);
        add(2 * third + (column / sw) * third, (1 - b) * (h - 1), 12, 12, 52);
      } else if (mode === "vectorscope") {
        const cb = (b - luma) / 1.8556;
        const cr = (r - luma) / 1.5748;
        add(w / 2 + cb * h * 1.6, h / 2 - cr * h * 1.6, 30, 34, 30);
      }
    }
    if (mode === "histogram") {
      const counts = [new Uint32Array(256), new Uint32Array(256), new Uint32Array(256)];
      for (let i = 0; i < pixels.length; i += 4) for (let c = 0; c < 3; c++) counts[c][pixels[i + c]]++;
      const peak = Math.max(1, ...counts.flatMap((row) => Array.from(row.subarray(2, 254))));
      counts.forEach((row, c) => {
        for (let v = 0; v < 256; v++) {
          const x = (v / 255) * (w - 1);
          const top = h - Math.min(h, (row[v] / peak) * h);
          for (let y = h - 1; y >= top; y--) add(x, y, c === 0 ? 90 : 0, c === 1 ? 90 : 0, c === 2 ? 110 : 0);
        }
      });
    }
    ctx.putImageData(out, 0, 0);
    ctx.strokeStyle = "rgba(255, 255, 255, 0.14)";
    ctx.lineWidth = 1;
    ctx.beginPath();
    if (mode === "vectorscope") {
      ctx.arc(w / 2, h / 2, h * 0.45, 0, Math.PI * 2);
      // The skin tone line, where faces of every complexion fall.
      ctx.moveTo(w / 2, h / 2);
      const angle = (123 * Math.PI) / 180;
      ctx.lineTo(w / 2 + Math.cos(angle) * h * 0.45, h / 2 - Math.sin(angle) * h * 0.45);
    } else if (mode !== "histogram") {
      for (const level of [0.25, 0.5, 0.75]) {
        ctx.moveTo(0, level * h);
        ctx.lineTo(w, level * h);
      }
    }
    ctx.stroke();
  };
  const hookScope = () => {
    const source = document.querySelector<HTMLCanvasElement>("canvas.render-canvas");
    if (source && !source.dataset.colorScope) {
      source.dataset.colorScope = "1";
      source.addEventListener("frame", drawScope);
    }
  };
  ref<HTMLSelectElement>("scope-mode").addEventListener("change", drawScope);
  // Hidden, the scope skips frames; shown, it draws the one on screen at once.
  new MutationObserver(() => {
    if (section.dataset.tabHidden !== "true") drawScope();
  }).observe(section, { attributes: true, attributeFilter: ["data-tab-hidden", "class", "hidden"] });

  // Filling the controls from the clip -----------------------------------------
  const refill = () => {
    hookScope();
    const target = clip();
    tools.hidden = !target;
    empty.hidden = Boolean(target);
    if (!target || dragging) return;
    grade = structuredClone(target.colorGrade ?? {});
    for (const w of WHEELS) drawWheel(w);
    for (const [key, , , , neutral] of PRIMARIES) {
      const input = section.querySelector<HTMLInputElement>(`[data-primary="${key}"]`)!;
      input.value = String(grade[key] ?? neutral);
      section.querySelector<HTMLOutputElement>(`[data-primary-out="${key}"]`)!.value = String(grade[key] ?? neutral);
    }
    for (const [key] of BASIC) {
      const value = target.colour?.[key] ?? COLOUR_NEUTRAL[key];
      section.querySelector<HTMLInputElement>(`[data-basic="${key}"]`)!.value = String(value);
      section.querySelector<HTMLOutputElement>(`[data-basic-out="${key}"]`)!.value = String(value);
    }
    drawCurve();
    drawScope();
  };
  engine.subscribe((_state, changed) => {
    if (changed === "clip-selection" || changed === "clips") refill();
  });
  requestAnimationFrame(refill);
  return section;
}
