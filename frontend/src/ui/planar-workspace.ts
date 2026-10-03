// The Track workspace (P2 of the planar tracking plan): a clip's planar layers drawn, set and tracked.
//
// A layer is shapes drawn on one frame of the clip's media (its reference), track settings, and a surface (four
// corners, the corner pin). The engine tracks a layer as a job (POST /api/planar/track) and keeps each frame's
// homography from the reference (GET /api/planar/track/<layer>); this page draws the shapes and the surface carried
// by it on every frame. Shapes are search areas, as in Mocha: drawn and edited in the reference's coordinates, so
// changing a tracked layer's shapes or settings starts its track afresh (asked first). The surface does not affect
// the track; it is the four corners the outputs use (P3). Layers higher in the list are in front: what they cover
// is left out of the layers below them while tracking.
import type { ProjectEngine } from "../engine/project";
import type { ClipPlanar, PlanarLayer, PlanarShape } from "../engine/types";
import { api } from "../engine/api";
import { t } from "../i18n";
import { icon } from "./icons";

type Track = { frames: Map<number, number[]>; confidence: Map<number, number>; adjusted: Map<number, number[]> };
type AdjustPoint = { master: number; home: number[]; keys: Record<string, number[]> };
type Media = { fps: number; width: number; height: number; frames: number };
const COLORS = ["#4b82f0", "#e25085", "#50e2a5", "#ffae2b", "#9e50e2", "#50cae2", "#e2a050", "#c9e250"];
const MOTIONS = ["translation", "scale", "rotation", "shear", "perspective"] as const;
const DEFAULTS: Record<string, unknown> = { screen: null, translation: true, scale: true, rotation: true, shear: false, perspective: false, channel: "luminance", min_pixels: null, smoothing: 0, motion: "large", search_x: null, search_y: null, angle: 0, zoom: 0 };
const VIEW_WIDTH = 1600;  // frames are fetched no wider than this for the viewer

// 3 x 3 homographies, row-major, as the engine writes them (pixels of the media to pixels of the media)
const apply = (h: number[], x: number, y: number): [number, number] => {
  const w = h[6] * x + h[7] * y + h[8];
  return [(h[0] * x + h[1] * y + h[2]) / w, (h[3] * x + h[4] * y + h[5]) / w];
};
const invert = (m: number[]): number[] => {
  const [a, b, c, d, e, f, g, h, i] = m;
  const A = e * i - f * h, B = -(d * i - f * g), C = d * h - e * g;
  const det = a * A + b * B + c * C;
  return [A, -(b * i - c * h), b * f - c * e, B, a * i - c * g, -(a * f - c * d), C, -(a * h - b * g), a * e - b * d].map((v) => v / det);
};
// a shape's points on a frame and its outline: the twin of backend/app/planar_shapes.py (keyframes run linearly and
// hold beyond; an X-Spline is a Hermite curve whose tangent at each point is the Catmull-Rom tangent times its tension)
const SAMPLES = 48;
const ellipseIn = (a: number[], b: number[], n: number): number[][] => {
  const [cx, cy, rx, ry] = [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2, Math.abs(b[0] - a[0]) / 2, Math.abs(b[1] - a[1]) / 2];
  return Array.from({ length: n }, (_, k) => [cx + rx * Math.cos((2 * Math.PI * k) / n), cy + ry * Math.sin((2 * Math.PI * k) / n)]);
};
const offAt = (shape: PlanarShape, index: number): Set<number> => {
  const off = shape.off ?? {};
  const order = Object.keys(off).map(Number).filter((k) => k <= index).sort((a, b) => a - b);
  return new Set(order.length ? off[String(order[order.length - 1])] : []);
};
const pointsAt = (shape: PlanarShape, index: number): number[][] => {
  const keys = shape.keys ?? {};
  const order = Object.keys(keys).map(Number).sort((a, b) => a - b);
  if (!order.length) return shape.points;
  if (index <= order[0]) return keys[String(order[0])];
  if (index >= order[order.length - 1]) return keys[String(order[order.length - 1])];
  const after = order.findIndex((k) => k > index), a = order[after - 1], b = order[after];
  const f = (index - a) / (b - a), pa = keys[String(a)], pb = keys[String(b)];
  return pa.length === pb.length ? pa.map((p, i) => [p[0] + (pb[i][0] - p[0]) * f, p[1] + (pb[i][1] - p[1]) * f]) : pa;
};
const outlineOf = (points: number[][], shape: PlanarShape): number[][] => {
  const n = points.length;
  if (shape.kind === "bezier" && n >= 2) {
    const hs = shape.handles ?? [];
    const out: number[][] = [];
    for (let i = 0; i < n; i += 1) {
      const p0 = points[i], p3 = points[(i + 1) % n], h0 = hs[i] ?? [0, 0, 0, 0], h3 = hs[(i + 1) % n] ?? [0, 0, 0, 0];
      const p1 = [p0[0] + h0[2], p0[1] + h0[3]], p2 = [p3[0] + h3[0], p3[1] + h3[1]];
      for (let k = 0; k < SAMPLES; k += 1) {
        const t = k / SAMPLES, u = 1 - t, a = u ** 3, b = 3 * u * u * t, c = 3 * u * t * t, d = t ** 3;
        out.push([a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]]);
      }
    }
    return out;
  }
  if (shape.kind !== "xspline" || n < 3) return points;
  const tension = shape.tension ?? [];
  const out: number[][] = [];
  for (let i = 0; i < n; i += 1) {
    const p0 = points[i], p1 = points[(i + 1) % n], prev = points[(i - 1 + n) % n], next = points[(i + 2) % n];
    const t0 = tension[i] ?? 1, t1 = tension[(i + 1) % n] ?? 1;
    const m0 = [((p1[0] - prev[0]) / 2) * t0, ((p1[1] - prev[1]) / 2) * t0];
    const m1 = [((next[0] - p0[0]) / 2) * t1, ((next[1] - p0[1]) / 2) * t1];
    for (let k = 0; k < SAMPLES; k += 1) {
      const t = k / SAMPLES, h00 = 2 * t ** 3 - 3 * t ** 2 + 1, h10 = t ** 3 - 2 * t ** 2 + t, h01 = -2 * t ** 3 + 3 * t ** 2, h11 = t ** 3 - t ** 2;
      out.push([h00 * p0[0] + h10 * m0[0] + h01 * p1[0] + h11 * m1[0], h00 * p0[1] + h10 * m0[1] + h01 * p1[1] + h11 * m1[1]]);
    }
  }
  return out;
};
const esc = (text: string) => text.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]!);

export function openPlanarWorkspace(engine: ProjectEngine, clipId: string): void {
  const found = engine.findClip(clipId);
  if (!found || !found.clip.mediaId) return;
  const clip = found.clip;
  const mediaId = clip.mediaId!;
  let layers: PlanarLayer[] = structuredClone(clip.planar?.layers ?? []);
  let current = layers.length ? 0 : -1;
  let shapeIndex = -1;
  let media: Media | null = null;
  let frame = 0, first = 0, last = 0;
  let tool: "select" | "draw" | "rect" | "ellipse" | "segment" = "draw";
  let mode: "add" | "subtract" = "add";
  const views = { surface: true, grid: false, trace: false, matte: false, stabilise: false, adjust: false };
  let pointIndex = 0;  // the reference point selected in AdjustTrack
  let picked: { shape: number; point: number } | null = null;  // the shape point selected (its tension and feather)
  let uberkey = false;  // a dragged point moves the same on every keyframe of its shape
  let smooth = false;  // new shapes drawn as X-Splines
  let placing = false;  // the next click on the frame places a new reference point
  let adjustTimer = 0;
  const tracks = new Map<string, Track>();
  let drawing: number[][] = [];  // points being drawn, in the current frame's pixels
  let job: string | null = null;
  let changed = false;

  const root = document.createElement("div");
  root.className = "pw";
  root.setAttribute("role", "dialog");
  root.setAttribute("aria-label", t("planar.title"));
  root.innerHTML = `
    <header class="pw-bar">
      <h2>${icon("layers")}<span>${t("planar.title")}: ${esc(clip.label)}</span></h2>
      <span class="pw-status" data-ref="status" aria-live="polite"></span>
      <button class="tool-chip is-primary" data-ref="done">${t("planar.done")}</button>
    </header>
    <div class="pw-body">
      <aside class="pw-side">
        <section class="pw-panel">
          <div class="pw-head"><span>${t("planar.layers")}</span><button class="icon-btn" data-ref="add-layer" title="${t("planar.newLayer")}" aria-label="${t("planar.newLayer")}">${icon("plus")}</button></div>
          <ul class="pw-layers" data-ref="layers"></ul>
        </section>
        <section class="pw-panel">
          <div class="pw-head"><span>${t("planar.shapes")}</span></div>
          <div class="pw-seg" data-ref="tools" role="group" aria-label="${t("planar.shapes")}">
            <button data-tool="select" title="${t("planar.select")}" aria-label="${t("planar.select")}">${icon("pointer")}</button>
            <button data-tool="draw" title="${t("planar.draw")}" aria-label="${t("planar.draw")}">${icon("curve")}</button>
            <button data-tool="rect" title="${t("planar.rect")}" aria-label="${t("planar.rect")}">${icon("fit")}</button>
            <button data-tool="ellipse" title="${t("mask.ellipse")}" aria-label="${t("mask.ellipse")}">${icon("ellipse")}</button>
            <button data-tool="segment" title="${t("planar.tool.segment")}" aria-label="${t("planar.tool.segment")}">${icon("sparkles")}</button>
          </div>
          <div class="pw-seg" data-ref="mode" role="group">
            <button data-mode="add">${t("planar.add")}</button><button data-mode="subtract">${t("planar.subtract")}</button>
          </div>
          <div class="pw-buttons-row">
            <button class="tool-chip" data-ref="smooth">${t("planar.smooth")}</button>
            <button class="tool-chip" data-ref="uberkey">${t("planar.uberkey")}</button>
            <button class="tool-chip" data-ref="delete-shape">${icon("trash")}${t("planar.deleteShape")}</button>
          </div>
          <div class="pw-buttons-row" data-ref="keys-row">
            <button class="icon-btn" data-ref="key-prev" title="${t("planar.keyPrev")}" aria-label="${t("planar.keyPrev")}">${icon("chevL")}</button>
            <button class="tool-chip" data-ref="key-add">${icon("diamond")}${t("planar.keyAdd")}</button>
            <button class="tool-chip" data-ref="key-delete">${t("planar.keyDelete")}</button>
            <button class="icon-btn" data-ref="key-next" title="${t("planar.keyNext")}" aria-label="${t("planar.keyNext")}">${icon("chevR")}</button>
          </div>
          <div data-ref="point-panel" hidden>
            <p class="pw-hint">${t("planar.edgeHint")}</p>
            <button class="tool-chip" data-ref="delete-point">${icon("trash")}${t("planar.adjust.delete")}</button>
            <button class="tool-chip" data-ref="toggle-point">${t("planar.pointActive")}</button>
            <button class="tool-chip" data-ref="make-bezier">${t("planar.makeBezier")}</button>
            <div class="pw-row"><span>${t("planar.tension")}</span><input type="range" data-ref="tension" min="0" max="1" step="0.05"></div>
            <div class="pw-row"><span>${t("planar.edge")}</span><input type="number" data-ref="edge" min="-500" max="500" step="1"></div>
          </div>
          <p class="pw-hint" data-ref="roto-hint" hidden>${t("planar.rotoHint")}</p>
        </section>
        <section class="pw-panel" data-ref="adjust-panel" hidden>
          <div class="pw-head"><span>${t("planar.adjust.title")}</span></div>
          <p class="pw-hint">${t("planar.adjust.hint")}</p>
          <div class="pw-buttons-row">
            <button class="tool-chip" data-ref="adj-new">${icon("plus")}${t("planar.adjust.new")}</button>
            <button class="tool-chip" data-ref="adj-next">${t("planar.adjust.next")}</button>
            <button class="tool-chip" data-ref="adj-master">${t("planar.adjust.master")}</button>
            <button class="tool-chip" data-ref="adj-delete">${icon("trash")}${t("planar.adjust.delete")}</button>
          </div>
          <div class="pw-row"><span>${t("planar.adjust.nudge")}</span><span class="pw-nudge">
            <button class="icon-btn" data-nudge="-1,0" aria-label="${t("planar.adjust.nudge")}">${icon("chevL")}</button><button class="icon-btn pw-up" data-nudge="0,-1" aria-label="${t("planar.adjust.nudge")}">${icon("chevD")}</button><button class="icon-btn" data-nudge="0,1" aria-label="${t("planar.adjust.nudge")}">${icon("chevD")}</button><button class="icon-btn" data-nudge="1,0" aria-label="${t("planar.adjust.nudge")}">${icon("chevR")}</button>
          </span></div>
          <div class="pw-row"><span>${t("planar.adjust.patch")}</span><input type="number" data-ref="adj-patch" min="7" max="101" step="2" value="21"></div>
          <div class="pw-row"><span>${t("planar.adjust.motion")}</span><input type="number" data-ref="adj-motion" min="1" max="200" value="16"></div>
          <button class="tool-chip" data-ref="adj-auto">${icon("search")}${t("planar.adjust.auto")}</button>
        </section>
        <section class="pw-panel" data-ref="settings"></section>
        <section class="pw-panel">
          <div class="pw-head"><span>${t("planar.apply")}</span></div>
          <div class="pw-row"><span>${t("planar.applyTo")}</span><select data-ref="target"></select></div>
          <div class="pw-row"><span>${t("planar.kind")}</span><select data-ref="kind"><option value="corner-pin">${t("planar.kind.pin")}</option><option value="transform">${t("planar.kind.transform")}</option><option value="matte">${t("planar.kind.matte")}</option><option value="holdout">${t("planar.kind.holdout")}</option></select></div>
          <div class="pw-row" data-ref="matte-row" hidden><span>${t("planar.feather")}</span><span class="pw-pair"><input type="number" data-ref="feather" min="0" max="100" step="0.5" value="2"><label class="pw-check"><input type="checkbox" data-ref="invert">${t("planar.invert")}</label></span></div>
          <button class="tool-chip" data-ref="apply">${icon("link")}${t("planar.applyBtn")}</button>
        </section>
      </aside>
      <main class="pw-main">
        <div class="pw-views" data-ref="views">
          ${(["surface", "grid", "trace", "matte", "stabilise", "adjust"] as const).map((v) => `<button class="tool-chip" data-view="${v}">${t(`planar.view.${v}`)}</button>`).join("")}
          <button class="tool-chip" data-ref="align">${t("planar.align")}</button>
        </div>
        <div class="pw-view" data-ref="view"><div class="pw-stage" data-ref="stage"><div class="pw-inner" data-ref="inner">
          <img data-ref="img" alt="" draggable="false"><svg data-ref="svg" xmlns="http://www.w3.org/2000/svg"></svg>
        </div></div></div>
        <div class="pw-transport">
          <div class="pw-scrub"><input type="range" data-ref="scrub" min="0" max="0" value="0" aria-label="${t("planar.frame")}"><canvas data-ref="strip" height="6" aria-hidden="true"></canvas></div>
          <div class="pw-buttons">
            <button class="icon-btn" data-ref="back-all" title="${t("planar.trackBack")}" aria-label="${t("planar.trackBack")}">${icon("toStart")}</button>
            <button class="icon-btn" data-ref="back-one" title="${t("planar.stepBack")}" aria-label="${t("planar.stepBack")}">${icon("stepBack")}</button>
            <button class="icon-btn" data-ref="stop" title="${t("planar.stop")}" aria-label="${t("planar.stop")}" disabled>${icon("close")}</button>
            <button class="icon-btn" data-ref="fwd-one" title="${t("planar.stepFwd")}" aria-label="${t("planar.stepFwd")}">${icon("stepFwd")}</button>
            <button class="icon-btn" data-ref="fwd-all" title="${t("planar.trackFwd")}" aria-label="${t("planar.trackFwd")}">${icon("toEnd")}</button>
            <span class="pw-frame" data-ref="frame"></span>
            <progress data-ref="progress" max="1" value="0" hidden></progress>
          </div>
        </div>
      </main>
    </div>`;
  document.body.append(root);
  const $ = <T extends Element = HTMLElement>(ref: string) => root.querySelector<T>(`[data-ref="${ref}"]`)!;
  const img = $<HTMLImageElement>("img"), svg = $<SVGSVGElement>("svg"), scrub = $<HTMLInputElement>("scrub");
  const say = (text: string) => { $("status").textContent = text; };

  const layer = () => (current >= 0 ? layers[current] : undefined);
  const refFrame = (l: PlanarLayer) => Math.round(l.reference * (media?.fps ?? 30));
  const rawHomography = (l: PlanarLayer, index: number): number[] | null => {
    const h = tracks.get(l.id)?.frames.get(index);
    if (h) return h;
    return index === refFrame(l) ? [1, 0, 0, 0, 1, 0, 0, 0, 1] : null;
  };
  const homography = (l: PlanarLayer, index: number): number[] | null => {
    const tr = tracks.get(l.id);
    const h = tr?.adjusted.get(index) ?? tr?.frames.get(index);
    if (h) return h;
    return index === refFrame(l) ? [1, 0, 0, 0, 1, 0, 0, 0, 1] : null;
  };
  const px = (p: number[]) => [p[0] * media!.width, p[1] * media!.height];
  // Link to Track: the layer whose track carries a layer's shapes (itself, unless linked to another)
  const carrierOf = (l: PlanarLayer): PlanarLayer => (l.link ? layers.find((one) => one.id === l.link) ?? l : l);
  const unit = (p: number[]) => [p[0] / media!.width, p[1] / media!.height];

  // ---- drawing the frame and its overlays ----
  function render(): void {
    if (!media) return;
    const { width: W, height: H } = media;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    let out = "";
    let on_top = "";
    layers.forEach((l, li) => {
      if (!l.visible) return;
      const h = homography(carrierOf(l), frame);
      const carried = (p: number[]) => (h ? apply(h, ...(px(p) as [number, number])) : px(p));
      const active = li === current;
      let handles = "";  // the shape's points, drawn last so they sit above the surface's corners where they meet
      const faint = !h;  // not tracked at this frame: shown where drawn, dashed
      l.shapes.forEach((shape, si) => {
        const now = pointsAt(shape, frame);
        const off = offAt(shape, frame);
        const keep = (_: unknown, pi: number) => !off.has(pi);
        const trimmed = off.size > 0 && now.length - off.size >= 3;
        const liveShape = trimmed ? { ...shape, tension: shape.tension?.filter(keep), feather: shape.feather?.filter(keep) } : shape;
        const pts = outlineOf(trimmed ? now.filter(keep) : now, liveShape).map((p) => carried(p).join(",")).join(" ");
        const fill = views.matte ? `${l.color}${shape.mode === "subtract" ? "00" : "99"}` : "none";
        out += `<polygon points="${pts}" fill="${fill}" stroke="${l.color}" stroke-width="${active && si === shapeIndex ? 3 : 2}" vector-effect="non-scaling-stroke"${faint ? ' stroke-dasharray="6 5"' : ""}${shape.mode === "subtract" ? ' class="is-subtract"' : ""} data-layer="${li}" data-shape="${si}"/>`;
        if (active && tool === "select" && !l.locked) {
          const offNow = offAt(shape, frame);
          now.forEach((p, pi) => { const [x, y] = carried(p); handles += `<circle class="pw-handle${offNow.has(pi) ? " is-off" : ""}" cx="${x}" cy="${y}" r="5" data-point="${si}:${pi}" vector-effect="non-scaling-stroke"/>`; });
          if (shape.kind === "bezier" && picked && picked.shape === si && now[picked.point]) {
            const p = now[picked.point], hh = shape.handles?.[picked.point] ?? [0, 0, 0, 0];
            const [px, py] = carried(p);
            for (const [side, dx, dy] of [["in", hh[0], hh[1]], ["out", hh[2], hh[3]]] as [string, number, number][]) {
              const [hx, hy] = carried([p[0] + dx, p[1] + dy]);
              handles += `<line class="pw-bline" x1="${px}" y1="${py}" x2="${hx}" y2="${hy}" vector-effect="non-scaling-stroke"/><circle class="pw-bhandle" cx="${hx}" cy="${hy}" r="4" data-bh="${si}:${picked.point}:${side}" vector-effect="non-scaling-stroke"/>`;
            }
          }
        }
      });
      if (views.surface && l.surface && h) {
        const corners = l.surface.map((p) => apply(h, ...(px(p) as [number, number])));
        out += `<polygon class="pw-surface" points="${corners.map((c) => c.join(",")).join(" ")}" vector-effect="non-scaling-stroke"/>`;
        if (views.grid) {
          for (let k = 1; k < 8; k += 1) {
            const f = k / 8;
            const lerp = (a: number[], b: number[]) => [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
            const [s0, s1, s2, s3] = l.surface.map(px);
            for (const [a, b] of [[lerp(s0, s1), lerp(s3, s2)], [lerp(s0, s3), lerp(s1, s2)]]) {
              const [x1, y1] = apply(h, a[0], a[1]), [x2, y2] = apply(h, b[0], b[1]);
              out += `<line class="pw-grid" x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" vector-effect="non-scaling-stroke"/>`;
            }
          }
        }
        if (active) corners.forEach((c, ci) => { out += `<rect class="pw-corner" x="${c[0] - 6}" y="${c[1] - 6}" width="12" height="12" data-corner="${ci}" vector-effect="non-scaling-stroke"/>`; });
        if (views.trace && active) {
          for (let ci = 0; ci < 4; ci += 1) {
            const path: string[] = [];
            for (let i = Math.max(first, frame - 30); i <= Math.min(last, frame + 30); i += 1) {
              const hi = homography(l, i);
              if (hi) path.push(apply(hi, ...(px(l.surface[ci]) as [number, number])).join(","));
            }
            out += `<polyline class="pw-trace" points="${path.join(" ")}" vector-effect="non-scaling-stroke"/>`;
          }
        }
      }
      on_top += handles;
    });
    out += on_top;  // the active layer's points above every layer, so another layer's surface never covers them
    if (views.adjust) out += paintPoints();
    if (drawing.length) out += `<polyline class="pw-drawing" points="${drawing.map((p) => p.join(",")).join(" ")}" vector-effect="non-scaling-stroke"/>`;
    svg.innerHTML = out;
    // the stabilised view: the picture moved so the current layer's tracked plane holds still
    const l = layer(), h = l ? homography(carrierOf(l), frame) : null;  // a linked layer stabilises by its carrier
    const inner = $("inner");
    if (views.stabilise && h) {
      const s = inner.clientWidth / W;
      const m = invert(h);
      const d = [m[0], m[1], m[2] * s, m[3], m[4], m[5] * s, m[6] / s, m[7] / s, m[8]];
      inner.style.transform = `matrix3d(${d[0]},${d[3]},0,${d[6]},${d[1]},${d[4]},0,${d[7]},0,0,1,0,${d[2]},${d[5]},0,${d[8]})`;
    } else inner.style.transform = "";
    $("frame").textContent = `${t("planar.frame")} ${frame}`;
    paintLayers();
    paintStrip();
  }

  function showFrame(index: number): void {
    frame = Math.max(first, Math.min(last, index));
    scrub.value = String(frame);
    img.src = `/api/planar/frame/${mediaId}?index=${frame}&width=${Math.min(media!.width, VIEW_WIDTH)}`;
    render();
  }

  function paintStrip(): void {
    const canvas = $<HTMLCanvasElement>("strip"), l = layer();
    const span = last - first + 1;
    canvas.width = Math.max(1, Math.min(2000, span));
    const g = canvas.getContext("2d")!;
    g.clearRect(0, 0, canvas.width, canvas.height);
    const keyed = l && shapeIndex >= 0 ? Object.keys(l.shapes[shapeIndex]?.keys ?? {}).map(Number) : [];
    g.fillStyle = "#ffffff";
    for (const k of keyed) g.fillRect(((k - first) / span) * canvas.width, 0, Math.max(2, canvas.width / span), canvas.height);
    const tr = l ? tracks.get(carrierOf(l).id) : undefined;
    if (!tr) return;
    for (const [i, c] of tr.confidence) {
      g.fillStyle = c >= 0.6 ? "#3fb950" : c >= 0.3 ? "#ffae2b" : "#ff475a";
      g.fillRect(((i - first) / span) * canvas.width, 0, Math.max(1, canvas.width / span), canvas.height);
    }
  }

  // ---- layers ----
  function paintLayers(): void {
    $("layers").innerHTML = layers.map((l, i) => `<li class="pw-layer${i === current ? " is-current" : ""}" data-index="${i}" style="--layer:${l.color}">
      <span class="pw-swatch"></span>
      <input class="pw-name" value="${esc(l.name)}" aria-label="${t("planar.layerName")}" data-act="name">
      <input type="color" class="pw-colour" value="${l.color}" aria-label="${t("canvas.colour")}" title="${t("canvas.colour")}" data-act="colour">
      <input class="pw-group" value="${esc(l.group ?? "")}" placeholder="${t("planar.group")}" aria-label="${t("planar.group")}" data-act="group">
      <button class="icon-btn${l.visible ? " is-on" : ""}" data-act="visible" title="${t("planar.visible")}" aria-label="${t("planar.visible")}">${icon(l.visible ? "eye" : "eyeOff")}</button>
      <button class="icon-btn${l.tracking ? " is-on" : ""}" data-act="tracking" title="${t("planar.tracking")}" aria-label="${t("planar.tracking")}">${icon("settings")}</button>
      <button class="icon-btn${l.locked ? " is-on" : ""}" data-act="locked" title="${t("planar.locked")}" aria-label="${t("planar.locked")}">${icon("lock")}</button>
      <button class="tool-chip${l.blend === "subtract" ? " is-on" : ""}" data-act="blend" aria-pressed="${l.blend === "subtract"}" title="${t("planar.blendSubtract")}">${t("planar.blendSubtract")}</button>
      <button class="tool-chip${l.invert ? " is-on" : ""}" data-act="invert" aria-pressed="${!!l.invert}" title="${t("planar.invertLayer")}">${t("planar.invertLayer")}</button>
      <button class="tool-chip" data-act="duplicate" title="${t("tray.duplicate")}">${t("tray.duplicate")}</button>
      <button class="tool-chip${l.inTime !== undefined ? " is-on" : ""}" data-act="in" title="${t("planar.layerIn")}">${t("planar.layerIn")}${l.inTime !== undefined ? ` ${Math.round(l.inTime * media!.fps)}` : ""}</button>
      <button class="tool-chip${l.outTime !== undefined ? " is-on" : ""}" data-act="out" title="${t("planar.layerOut")}">${t("planar.layerOut")}${l.outTime !== undefined ? ` ${Math.round(l.outTime * media!.fps)}` : ""}</button>
      <button class="icon-btn pw-up" data-act="up" title="${t("planar.forward")}" aria-label="${t("planar.forward")}">${icon("chevD")}</button>
      <button class="icon-btn" data-act="delete" title="${t("planar.deleteLayer")}" aria-label="${t("planar.deleteLayer")}">${icon("trash")}</button>
    </li>`).join("") || `<li class="pw-empty">${t("planar.hint")}</li>`;
    for (const b of $("tools").querySelectorAll<HTMLElement>("[data-tool]")) b.classList.toggle("is-active", b.dataset.tool === tool);
    for (const b of $("mode").querySelectorAll<HTMLElement>("[data-mode]")) b.classList.toggle("is-active", b.dataset.mode === mode);
    for (const b of $("views").querySelectorAll<HTMLElement>("[data-view]")) b.classList.toggle("is-on", views[b.dataset.view as keyof typeof views]);
  }

  function newLayer(): PlanarLayer {
    const l: PlanarLayer = { id: `pl${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, name: `${t("planar.layer")} ${layers.length + 1}`, color: COLORS[layers.length % COLORS.length], shapes: [], reference: frame / media!.fps, settings: { ...DEFAULTS }, visible: true, tracking: true, locked: false };
    layers.unshift(l);  // a new layer goes in front
    current = 0;
    changed = true;
    paintSettings();
    return l;
  }

  // a tracked layer's shapes or settings changed: its track no longer holds (asked once per change)
  async function invalidate(l: PlanarLayer): Promise<boolean> {
    const tr = tracks.get(l.id);
    if (!tr || tr.frames.size <= 1) return true;
    if (!window.confirm(t("planar.resetAsk"))) return false;
    tracks.delete(l.id);
    await fetch(`/api/planar/track/${l.id}`, { method: "DELETE" }).catch(() => undefined);
    return true;
  }

  $("layers").addEventListener("click", (event) => {
    const target = event.target as HTMLElement;
    const row = target.closest<HTMLElement>("[data-index]");
    if (!row) return;
    const i = Number(row.dataset.index);
    const act = target.closest<HTMLElement>("[data-act]")?.dataset.act;
    const l = layers[i];
    if (act === "visible" || act === "tracking" || act === "locked") {
      const key = act as "visible" | "tracking" | "locked", value = !l[key];
      for (const one of (event as MouseEvent).shiftKey && l.group ? layers.filter((x) => x.group === l.group) : [l]) one[key] = value;
      changed = true;
    }
    else if (act === "blend") { l.blend = l.blend === "subtract" ? "add" : "subtract"; changed = true; }
    else if (act === "duplicate") {
      const copy: PlanarLayer = { ...structuredClone(l), id: `pl${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, name: `${l.name} 2`, link: l.link ?? l.id, tracking: false };
      layers.splice(i, 0, copy);
      current = i;
      changed = true;
    }
    else if (act === "in" || act === "out") {
      const at = frame / media!.fps, key = act === "in" ? "inTime" : "outTime";
      l[key] = l[key] !== undefined && Math.abs(l[key]! - at) < 1e-6 ? undefined : at;
      changed = true;
    }
    else if (act === "invert") { l.invert = !l.invert; changed = true; }
    else if (act === "up" && i > 0) { [layers[i - 1], layers[i]] = [layers[i], layers[i - 1]]; current = i - 1; changed = true; }
    else if (act === "delete") {
      if (!window.confirm(t("planar.deleteAsk"))) return;
      layers.splice(i, 1);
      tracks.delete(l.id);
      void fetch(`/api/planar/track/${l.id}`, { method: "DELETE" }).catch(() => undefined);
      current = Math.min(current, layers.length - 1);
      changed = true;
    } else if (act !== "name") { current = i; shapeIndex = -1; }
    paintSettings();
    render();
  });
  $("layers").addEventListener("change", (event) => {
    const input = event.target as HTMLInputElement;
    const row = input.closest<HTMLElement>("[data-index]");
    if (row && input.dataset.act === "name") { layers[Number(row.dataset.index)].name = input.value.trim() || layers[Number(row.dataset.index)].name; changed = true; }
    if (row && input.dataset.act === "colour") { layers[Number(row.dataset.index)].color = input.value; changed = true; paintLayers(); render(); }
    if (row && input.dataset.act === "group") { layers[Number(row.dataset.index)].group = input.value.trim() || undefined; changed = true; }
  });
  $("add-layer").addEventListener("click", () => { newLayer(); render(); });

  // ---- track settings, as Mocha names them ----
  function paintSettings(): void {
    const l = layer(), box = $("settings");
    if (!l) { box.innerHTML = ""; return; }
    const s = { ...DEFAULTS, ...l.settings } as Record<string, unknown>;
    const num = (key: string, step: number, min: number, max: number, autoable = false) => `<input type="number" data-key="${key}" step="${step}" min="${min}" max="${max}" value="${s[key] ?? ""}" placeholder="${autoable ? t("planar.auto") : ""}">`;
    box.innerHTML = `<div class="pw-head"><span>${t("planar.trackSettings")}</span></div>
      <div class="pw-row"><span>${t("planar.link")}</span><select data-ref="link">${[`<option value="">${t("planar.ownTrack")}</option>`, ...layers.filter((o) => o.id !== l.id).map((o) => `<option value="${o.id}" ${l.link === o.id ? "selected" : ""}>${esc(o.name)}</option>`)].join("")}</select></div>
      <div class="pw-row"><span>${t("planar.method")}</span><select data-key="screen">${([["", "planar.method.planar"], ["green", "planar.method.green"], ["blue", "planar.method.blue"]] as const).map(([v, k]) => `<option value="${v}" ${(s.screen ?? "") === v ? "selected" : ""}>${t(k)}</option>`).join("")}</select></div>
      <div class="pw-motions">${MOTIONS.map((m) => `<label><input type="checkbox" data-key="${m}" ${s[m] ? "checked" : ""}>${t(`planar.motion.${m}`)}</label>`).join("")}</div>
      <div class="pw-row"><span>${t("planar.channel")}</span><select data-key="channel"><option value="luminance" ${s.channel === "luminance" ? "selected" : ""}>${t("planar.luminance")}</option><option value="auto" ${s.channel === "auto" ? "selected" : ""}>${t("planar.autoChannel")}</option><option value="max" ${s.channel === "max" ? "selected" : ""}>${t("planar.maxChannel")}</option></select></div>
      <div class="pw-row"><span>${t("planar.minPixels")}</span>${num("min_pixels", 1, 1, 100, true)}</div>
      <div class="pw-row"><span>${t("planar.smoothing")}</span>${num("smoothing", 0.5, 0, 10)}</div>
      <div class="pw-row"><span>${t("planar.motionMode")}</span><select data-key="motion">${(["large", "small", "manual"] as const).map((m) => `<option value="${m}" ${s.motion === m ? "selected" : ""}>${t(`planar.mode.${m}`)}</option>`).join("")}</select></div>
      <div class="pw-row"><span>${t("planar.search")}</span><span class="pw-pair">${num("search_x", 1, 0, 2000, true)}${num("search_y", 1, 0, 2000, true)}</span></div>
      <div class="pw-row"><span>${t("planar.angle")}</span>${num("angle", 1, 0, 90)}</div>
      <div class="pw-row"><span>${t("planar.zoom")}</span>${num("zoom", 1, 0, 100)}</div>`;
  }
  $("settings").addEventListener("change", (event) => void (async () => {
    const input = event.target as HTMLInputElement;
    const l = layer(), key = input.dataset.key;
    if (l && input.dataset.ref === "link") {
      // Link to Track: the shapes ride the chosen layer's track (adjusted where it has one), its own without
      l.link = input.value || undefined;
      changed = true;
      render();
      return;
    }
    if (!l || !key) return;
    if (!(await invalidate(l))) { paintSettings(); return; }
    const value = input.type === "checkbox" ? input.checked : input.type === "number" ? (input.value === "" ? null : Number(input.value)) : key === "screen" ? input.value || null : input.value;
    l.settings = { ...DEFAULTS, ...l.settings, [key]: value };
    // rotation brings scale, shear brings rotation, perspective brings all, as in Mocha
    const order = MOTIONS as readonly string[];
    if (input.type === "checkbox" && order.includes(key) && value) for (const k of order.slice(1, order.indexOf(key))) l.settings[k] = true;
    changed = true;
    paintSettings();
    render();
  })());

  // ---- tools, shapes and the surface on the viewer ----
  $("tools").addEventListener("click", (event) => { const b = (event.target as HTMLElement).closest<HTMLElement>("[data-tool]"); if (b) { tool = b.dataset.tool as typeof tool; drawing = []; render(); } });
  $("mode").addEventListener("click", (event) => { const b = (event.target as HTMLElement).closest<HTMLElement>("[data-mode]"); if (b) { mode = b.dataset.mode as typeof mode; paintLayers(); } });
  $("views").addEventListener("click", (event) => {
    const b = (event.target as HTMLElement).closest<HTMLElement>("[data-view]");
    if (b) {
      const v = b.dataset.view as keyof typeof views;
      views[v] = !views[v];
      $("stage").classList.toggle("is-matte", views.matte);
      if (v === "adjust") startAdjust();
      render();
    }
  });
  $("align").addEventListener("click", () => {
    // the surface fitted to the whole frame on the current frame, kept in the reference's coordinates
    const l = layer(), h = l ? homography(carrierOf(l), frame) : null;
    if (!l || !h) { say(t("planar.needTracked")); return; }
    const back = invert(h);
    l.surface = [[0, 0], [1, 0], [1, 1], [0, 1]].map((p) => unit(apply(back, ...(px(p) as [number, number]))));
    changed = true;
    render();
  });
  $("delete-shape").addEventListener("click", () => void (async () => {
    const l = layer();
    if (!l || shapeIndex < 0 || l.locked || !(await invalidate(l))) return;
    l.shapes.splice(shapeIndex, 1);
    shapeIndex = -1;
    changed = true;
    render();
  })());

  const pointer = (event: PointerEvent): [number, number] => {
    const p = svg.createSVGPoint();
    p.x = event.clientX; p.y = event.clientY;
    const q = p.matrixTransform(svg.getScreenCTM()!.inverse());
    return [q.x, q.y];
  };
  // a point on the current frame, in the layer's reference: the shapes and surface are kept there
  const toReference = (l: PlanarLayer, x: number, y: number): number[] | null => {
    const h = homography(carrierOf(l), frame);
    return h ? unit(apply(invert(h), x, y)) : null;
  };

  async function addShape(points: number[][], spline?: number): Promise<void> {
    let l = layer();
    if (!l || l.locked) l = newLayer();
    if (!l.shapes.length) l.reference = frame / media!.fps;  // the first shape sets the frame it is drawn on
    const mapped = points.map((p) => toReference(l!, p[0], p[1]));
    if (mapped.some((p) => !p)) { say(t("planar.needTracked")); return; }
    if (!(await invalidate(l))) return;
    const placed = (mapped as number[][]).map((p) => [Number(p[0].toFixed(6)), Number(p[1].toFixed(6))]);
    const curved = spline ?? (smooth ? 1 : undefined);  // an X-Spline at this tension, or straight sides
    l.shapes.push(curved !== undefined ? { points: placed, mode, kind: "xspline", tension: placed.map(() => curved) } : { points: placed, mode });
    if (!l.surface) {
      // the surface starts at the first shape's bounds, as a place to put the corners from
      const xs = l.shapes[0].points.map((p) => p[0]), ys = l.shapes[0].points.map((p) => p[1]);
      const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
      l.surface = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]];
    }
    shapeIndex = l.shapes.length - 1;
    changed = true;
    say("");
  }

  let drag: { kind: "point" | "corner" | "rect" | "ref" | "handle"; a: number; b: number; start: [number, number] } | null = null;
  let dragEnd: [number, number] = [0, 0];
  let handleSide: "in" | "out" = "out";
  let handleBroken = false;
  svg.addEventListener("pointerdown", (event) => {
    if (job) return;
    const [x, y] = pointer(event);
    const target = event.target as SVGElement;
    const l = layer();
    if (views.adjust && placing && l) { placePoint(l, x, y); return; }
    if (views.adjust && target.dataset.refpoint !== undefined && l) {
      pointIndex = Number(target.dataset.refpoint);
      drag = { kind: "ref", a: pointIndex, b: 0, start: [x, y] };
      svg.setPointerCapture(event.pointerId);
      render();
      return;
    }
    if (target.dataset.corner !== undefined && l) { drag = { kind: "corner", a: Number(target.dataset.corner), b: 0, start: [x, y] }; svg.setPointerCapture(event.pointerId); return; }
    if (tool === "select") {
      const now = performance.now();
      if (!target.dataset.point && lastPress && now - lastPress.at < 400 && Math.hypot(event.clientX - lastPress.x, event.clientY - lastPress.y) < 6) {
        lastPress = null;
        void addPointAt(x, y);
        return;
      }
      lastPress = { at: now, x: event.clientX, y: event.clientY };
      if (target.dataset.bh && l) { const [si, pi, side] = target.dataset.bh.split(":"); handleSide = side === "in" ? "in" : "out"; handleBroken = event.altKey; drag = { kind: "handle", a: Number(si), b: Number(pi), start: [x, y] }; svg.setPointerCapture(event.pointerId); return; }
      if (target.dataset.point && l) { const [si, pi] = target.dataset.point.split(":").map(Number); picked = { shape: si, point: pi }; shapeIndex = si; paintPoint(); drag = { kind: "point", a: si, b: pi, start: [x, y] }; svg.setPointerCapture(event.pointerId); return; }
      if (target.dataset.shape !== undefined) { current = Number(target.dataset.layer); shapeIndex = Number(target.dataset.shape); paintSettings(); render(); }
      return;
    }
    if (tool === "segment") {
      say(t("planar.segmenting"));
      void (async () => {
        try {
          const found = await api<{ points: number[][] }>("/api/planar/segment", { media_id: mediaId, frame, points: [{ x: x / media!.width, y: y / media!.height }] });
          await addShape(found.points.map(px), 0.5);  // SAM's traced outline, as an X-Spline at half tension
          render();
        } catch (error) { say(error instanceof Error ? error.message : String(error)); }
      })();
      return;
    }
    if (tool === "rect" || tool === "ellipse") { drag = { kind: "rect", a: 0, b: 0, start: [x, y] }; drawing = [[x, y], [x, y], [x, y], [x, y], [x, y]]; svg.setPointerCapture(event.pointerId); return; }
    drawing.push([x, y]);
    render();
  });
  // a double click closes the shape (its second press added the same point again: dropped)
  // a double press in the select tool adds a point on the nearest shape's edge. It is told here from two presses
  // (400 ms, 6 px) rather than from the browser's double click: a press re-draws the overlay, the element it began
  // on is gone, and Chromium then sends no click and no double click at all.
  let lastPress: { at: number; x: number; y: number } | null = null;
  async function addPointAt(x: number, y: number): Promise<void> {
    const l = layer();
    if (!l || l.locked) return;
    // the shape whose drawn outline passes nearest the pointer, within 8 screen pixels
    const h = homography(carrierOf(l), frame);
    if (!h) return;
    const reach = 8 * (media!.width / Math.max(1, svg.getBoundingClientRect().width));
    let nearest = -1, closest = reach;
    l.shapes.forEach((shape, si) => {
      const drawn = outlineOf(pointsAt(shape, frame), shape).map((p) => apply(h, ...(px(p) as [number, number])));
      drawn.forEach((a, i) => {
        const b = drawn[(i + 1) % drawn.length], dx = b[0] - a[0], dy = b[1] - a[1];
        const f = Math.max(0, Math.min(1, ((x - a[0]) * dx + (y - a[1]) * dy) / Math.max(1e-9, dx * dx + dy * dy)));
        const distance = Math.hypot(a[0] + dx * f - x, a[1] + dy * f - y);
        if (distance < closest) { closest = distance; nearest = si; }
      });
    });
    const ref = toReference(l, x, y);
    if (nearest < 0 || !ref || (l.tracking && !(await invalidate(l)))) return;
    shapeIndex = nearest;
    insertPoint(l.shapes[nearest], ref);
    changed = true;
    render();
  }
  svg.addEventListener("dblclick", () => {
    if (tool !== "draw" || job) return;
    drawing = drawing.slice(0, -1);
    if (drawing.length >= 3) void addShape(drawing).then(() => { drawing = []; render(); });
  });
  svg.addEventListener("pointermove", (event) => {
    if (!drag) return;
    const [x, y] = pointer(event);
    const l = layer();
    if (drag.kind === "rect") {
      const [x0, y0] = drag.start;
      dragEnd = [x, y];
      drawing = tool === "ellipse" ? [...ellipseIn([x0, y0], [x, y], 48), ellipseIn([x0, y0], [x, y], 48)[0]] : [[x0, y0], [x, y0], [x, y], [x0, y], [x0, y0]];
    } else if (l && drag.kind === "corner" && l.surface) {
      const p = toReference(l, x, y);
      if (p) { l.surface[drag.a] = p; changed = true; }
    } else if (l && drag.kind === "ref") {
      movePoint(l, drag.a, x, y);
    } else if (l && drag.kind === "handle") {
      const shape = l.shapes[drag.a], at = toReference(l, x, y), p = pointsAt(shape, frame)[drag.b];
      if (at && p) {
        const hs = (shape.handles ??= shape.points.map(() => [0, 0, 0, 0]));
        const h = hs[drag.b] ?? (hs[drag.b] = [0, 0, 0, 0]);
        const dx = at[0] - p[0], dy = at[1] - p[1];
        const [mine, other] = handleSide === "in" ? [0, 2] : [2, 0];
        h[mine] = dx; h[mine + 1] = dy;
        if (!handleBroken) {
          const len = Math.hypot(h[other], h[other + 1]) || Math.hypot(dx, dy), d = Math.hypot(dx, dy) || 1;
          h[other] = (-dx / d) * len; h[other + 1] = (-dy / d) * len;
        }
        changed = true;
      }
    } else if (l && drag.kind === "point") {
      const p = toReference(l, x, y);
      if (p) {
        const shape = l.shapes[drag.a];
        const keyedArea = l.tracking && (tracks.get(l.id)?.frames.size ?? 0) > 1;
        if (l.tracking && !keyedArea) shape.points[drag.b] = p;
        else keyPoint(shape, drag.b, p);
        changed = true;
      }
    }
    render();
  });
  svg.addEventListener("pointerup", () => void (async () => {
    if (!drag) return;
    const was = drag;
    drag = null;
    if (was.kind === "rect") {
      const [a, b] = [was.start, dragEnd];
      const box = drawing.slice(0, 4);
      drawing = [];
      if (Math.abs(b[0] - a[0]) > 4 && Math.abs(b[1] - a[1]) > 4) await addShape(tool === "ellipse" ? ellipseIn(a, b, 12) : box, tool === "ellipse" ? 1 : undefined);
    } else if (was.kind === "point" || was.kind === "handle") {
      const l = layer();
      const keyedArea = !!l && l.tracking && was.kind === "point" && (tracks.get(l.id)?.frames.size ?? 0) > 1;
      if (l && !keyedArea && !(await invalidate(l))) await loadTracks();
    }
    render();
  })());

  // ---- tracking: the engine's jobs ----
  const apiLayer = (l: PlanarLayer) => ({ id: l.id, shapes: l.shapes.map((s) => ({ points: s.points, mode: s.mode, kind: s.kind ?? "polygon", tension: s.tension ?? null, feather: s.feather ?? null, keys: s.keys ?? null, handles: s.handles ?? null, off: s.off ?? null })), reference: l.reference, settings: l.settings, link: l.link ?? null });

  async function loadTrack(l: PlanarLayer): Promise<void> {
    const reply = await fetch(`/api/planar/track/${l.id}`);
    if (!reply.ok) { tracks.delete(l.id); return; }
    const data = await reply.json() as { frames: number[]; matrices: number[][]; confidence: number[]; adjusted?: number[][] };
    tracks.set(l.id, {
      frames: new Map(data.frames.map((f, i) => [f, data.matrices[i]])),
      confidence: new Map(data.frames.map((f, i) => [f, data.confidence[i]])),
      adjusted: new Map((data.adjusted ?? []).map((m, i) => [data.frames[i], m])),
    });
  }
  const loadTracks = () => Promise.all(layers.map((l) => loadTrack(l)));

  async function track(direction: 1 | -1, step: boolean): Promise<void> {
    if (job) return;  // one track at a time: the buttons wait for the running one
    const l = layer();
    if (!l || !l.shapes.length) { say(t("planar.needShape")); return; }
    if (!homography(l, frame)) { say(t("planar.needTracked")); return; }
    const stop = step ? frame + direction : direction > 0 ? last : first;
    if (stop < first || stop > last || stop === frame) return;
    const above = layers.slice(0, current).filter((a) => a.visible && a.shapes.length).map(apiLayer);
    try {
      const started = await api<{ job_id: string }>("/api/planar/track", { media_id: mediaId, layer: apiLayer(l), start: frame / media!.fps, stop: stop / media!.fps, above });
      job = started.job_id;
    } catch (error) { say(error instanceof Error ? error.message : String(error)); return; }
    changed = true;
    const progress = $<HTMLProgressElement>("progress");
    progress.hidden = false;
    ($("stop") as HTMLButtonElement).disabled = false;
    let lastLoad = 0;
    for (;;) {
      await new Promise((r) => setTimeout(r, 250));
      const status = await fetch(`/api/jobs/${job}`).then((r) => r.json()).catch(() => ({ status: "error" }));
      progress.value = status.progress ?? 0;
      if (typeof status.frame === "number") {
        if (Date.now() - lastLoad > 700) { lastLoad = Date.now(); await loadTrack(l); }
        frame = status.frame;
        showFrame(frame);
        say(`${t("planar.tracking.frame")} ${status.frame}`);
      } else if (status.message) say(status.message);
      if (status.status !== "queued" && status.status !== "running") {
        await loadTrack(l);
        if (status.status === "error") say(status.error ?? t("planar.failed"));
        else if (status.status === "cancelled") say(`${t("planar.stopped")} ${frame}`);  // its frames are kept
        else if (typeof status.result?.lost === "number") say(`${t("planar.lost")} ${status.result.lost}`);
        else say(`${t("planar.tracked")} ${status.result?.tracked ?? 0}`);
        if (typeof status.result?.to === "number") showFrame(status.result.to);
        break;
      }
    }
    job = null;
    progress.hidden = true;
    ($("stop") as HTMLButtonElement).disabled = true;
    render();
  }
  $("fwd-all").addEventListener("click", () => void track(1, false));
  $("back-all").addEventListener("click", () => void track(-1, false));
  $("fwd-one").addEventListener("click", () => void track(1, true));
  $("back-one").addEventListener("click", () => void track(-1, true));
  $("stop").addEventListener("click", () => { if (job) void fetch(`/api/jobs/${job}`, { method: "DELETE" }); });
  scrub.addEventListener("input", () => { if (!job) showFrame(Number(scrub.value)); });

  // ---- roto (P5): Autokey on layers that are not tracked, Überkey, a point's tension and feather ----
  function keyPoint(shape: PlanarShape, i: number, place: number[]): void {
    // a roto layer: the shape keyed on this frame as it now is (the first key holds over the whole clip); with Überkey
    // the point moves by the same amount on every key, and on the base shape
    const now = pointsAt(shape, frame).map((p) => [...p]);
    const dx = place[0] - now[i][0], dy = place[1] - now[i][1];
    if (uberkey) {
      for (const pts of [shape.points, ...Object.values(shape.keys ?? {})]) pts[i] = [pts[i][0] + dx, pts[i][1] + dy];
      return;
    }
    now[i] = place;
    (shape.keys ??= {})[String(frame)] = now;
  }
  function paintPoint(): void {
    const l = layer(), shape = picked && l ? l.shapes[picked.shape] : undefined;
    $("point-panel").hidden = !shape;
    $("roto-hint").hidden = !l || l.tracking;
    $("smooth").classList.toggle("is-on", smooth);
    $("uberkey").classList.toggle("is-on", uberkey);
    if (!shape || !picked) return;
    const tension = $<HTMLInputElement>("tension");
    tension.disabled = shape.kind !== "xspline";
    tension.value = String(shape.tension?.[picked.point] ?? (shape.kind === "xspline" ? 1 : 0));
    $<HTMLInputElement>("edge").value = String(shape.feather?.[picked.point] ?? 0);
  }
  // a point added on a shape's edge, on every keyframe and the base shape alike (where it lies along that side now)
  function insertPoint(shape: PlanarShape, ref: number[]): void {
    const now = pointsAt(shape, frame), n = now.length;
    let best = 0, bestDistance = Infinity, along = 0;
    for (let i = 0; i < n; i += 1) {
      const a = now[i], b = now[(i + 1) % n], dx = b[0] - a[0], dy = b[1] - a[1];
      const f = Math.max(0, Math.min(1, ((ref[0] - a[0]) * dx + (ref[1] - a[1]) * dy) / Math.max(1e-12, dx * dx + dy * dy)));
      const distance = Math.hypot(a[0] + dx * f - ref[0], a[1] + dy * f - ref[1]);
      if (distance < bestDistance) { bestDistance = distance; best = i; along = f; }
    }
    const at = best + 1, next = (best + 1) % n;
    for (const pts of [shape.points, ...Object.values(shape.keys ?? {})]) {
      const placed = [pts[best][0] + (pts[next][0] - pts[best][0]) * along, pts[best][1] + (pts[next][1] - pts[best][1]) * along];
      pts.splice(at, 0, placed);
    }
    for (const values of [shape.tension, shape.feather]) if (values) values.splice(at, 0, (values[best] + values[next]) / 2);
    picked = { shape: shape === layer()?.shapes[shapeIndex] ? shapeIndex : picked?.shape ?? 0, point: at };
  }
  $("delete-point").addEventListener("click", () => void (async () => {
    // a point taken off the shape on every keyframe (a shape keeps three at least)
    const l = layer(), shape = picked && l ? l.shapes[picked.shape] : undefined;
    if (!l || !shape || !picked || shape.points.length <= 3) return;
    if (l.tracking && !(await invalidate(l))) return;
    for (const pts of [shape.points, ...Object.values(shape.keys ?? {})]) pts.splice(picked.point, 1);
    for (const values of [shape.tension, shape.feather]) values?.splice(picked.point, 1);
    const gone = picked.point;
    for (const [k, set] of Object.entries(shape.off ?? {})) shape.off![k] = set.filter((i) => i !== gone).map((i) => (i > gone ? i - 1 : i));
    picked = null;
    changed = true;
    paintPoint();
    render();
  })());
  $("make-bezier").addEventListener("click", () => {
    const shape = shapeIndex >= 0 ? layer()?.shapes[shapeIndex] : undefined;
    if (!shape || shape.kind === "bezier") return;
    const pts = shape.points, n = pts.length, tension = shape.tension ?? [];
    shape.handles = pts.map((_, i) => {
      if (shape.kind !== "xspline") return [0, 0, 0, 0];
      const prev = pts[(i - 1 + n) % n], next = pts[(i + 1) % n], k = (tension[i] ?? 1) / 6;
      const mx = (next[0] - prev[0]) * k, my = (next[1] - prev[1]) * k;
      return [-mx, -my, mx, my];
    });
    shape.kind = "bezier";
    delete shape.tension;
    changed = true;
    render();
  });
  $("toggle-point").addEventListener("click", () => {
    const l = layer(), shape = picked && l ? l.shapes[picked.shape] : undefined;
    if (!l || !shape || !picked) return;
    const now = offAt(shape, frame);
    if (now.has(picked.point)) now.delete(picked.point);
    else if (shape.points.length - now.size > 3) now.add(picked.point);
    (shape.off ??= {})[String(frame)] = [...now].sort((a, b) => a - b);
    changed = true;
    render();
  });
  // the selected shape's keyframes: to the one before or after, one added here as the shape now is, this one taken off
  const keyFrames = (): number[] => {
    const shape = shapeIndex >= 0 ? layer()?.shapes[shapeIndex] : undefined;
    return Object.keys(shape?.keys ?? {}).map(Number).sort((a, b) => a - b);
  };
  $("key-prev").addEventListener("click", () => { const before = keyFrames().filter((k) => k < frame); if (before.length) showFrame(before[before.length - 1]); });
  $("key-next").addEventListener("click", () => { const after = keyFrames().find((k) => k > frame); if (after !== undefined) showFrame(after); });
  $("key-add").addEventListener("click", () => {
    const shape = shapeIndex >= 0 ? layer()?.shapes[shapeIndex] : undefined;
    if (!shape) { say(t("planar.needShape")); return; }
    (shape.keys ??= {})[String(frame)] = pointsAt(shape, frame).map((p) => [...p]);
    changed = true;
    render();
  });
  $("key-delete").addEventListener("click", () => {
    const shape = shapeIndex >= 0 ? layer()?.shapes[shapeIndex] : undefined;
    if (!shape?.keys?.[String(frame)]) return;
    const left = Object.keys(shape.keys).length;
    if (left === 1) shape.points = shape.keys[String(frame)];  // the last key: the shape stays as it was keyed
    delete shape.keys[String(frame)];
    if (left === 1) delete shape.keys;
    changed = true;
    render();
  });
  $("smooth").addEventListener("click", () => { smooth = !smooth; paintPoint(); });
  $("uberkey").addEventListener("click", () => { uberkey = !uberkey; paintPoint(); });
  $("tension").addEventListener("change", () => void (async () => {
    const l = layer(), shape = picked && l ? l.shapes[picked.shape] : undefined;
    if (!l || !shape || !picked || shape.kind !== "xspline") return;
    if (l.tracking && !(await invalidate(l))) { paintPoint(); return; }  // a tracked layer's search area changes
    (shape.tension ??= shape.points.map(() => 1))[picked.point] = Number($<HTMLInputElement>("tension").value);
    changed = true;
    render();
  })());
  $("edge").addEventListener("change", () => {
    // the matte's feather only: the tracker ignores it, so no track starts afresh
    const l = layer(), shape = picked && l ? l.shapes[picked.shape] : undefined;
    if (!l || !shape || !picked) return;
    (shape.feather ??= shape.points.map(() => 0))[picked.point] = Math.min(500, Math.max(-500, Number($<HTMLInputElement>("edge").value) || 0));
    changed = true;
  });

  // ---- AdjustTrack (P4): reference points that remove drift, as Mocha's ----
  // A point's place on a frame is the raw track carrying it from its master frame plus its correction there, linear
  // between the frames it is keyed on (nothing at the master, held past the last key): the engine's own arithmetic
  // (planar_api.adjusted_track), so the point is drawn where the engine will put it.
  const carry = (l: PlanarLayer, p: AdjustPoint, index: number): number[] | null => {
    const at = rawHomography(l, index), from = rawHomography(l, p.master);
    if (!at || !from) return null;
    const [mx, my] = px(p.home);
    const [rx, ry] = apply(invert(from), mx, my);
    return apply(at, rx, ry);
  };
  function placeOf(l: PlanarLayer, p: AdjustPoint, index: number): number[] | null {
    const carried = carry(l, p, index);
    if (!carried) return null;
    const keys = new Map<number, number[]>([[p.master, [0, 0]]]);
    for (const [k, place] of Object.entries(p.keys)) {
      const c = carry(l, p, Number(k));
      if (c && Number(k) !== p.master) { const [x, y] = px(place); keys.set(Number(k), [x - c[0], y - c[1]]); }
    }
    const order = [...keys.keys()].sort((a, b) => a - b);
    let d = keys.get(order[0])!;
    if (index >= order[order.length - 1]) d = keys.get(order[order.length - 1])!;
    else if (index > order[0]) {
      const after = order.findIndex((k) => k > index), a = order[after - 1], b = order[after];
      const f = (index - a) / (b - a), da = keys.get(a)!, db = keys.get(b)!;
      d = [da[0] + (db[0] - da[0]) * f, da[1] + (db[1] - da[1]) * f];
    }
    return [carried[0] + d[0], carried[1] + d[1]];
  }
  function paintPoints(): string {
    const l = layer();
    if (!l?.adjust?.length) return "";
    const places = l.adjust.map((p) => placeOf(l, p, frame));
    const shown = places.filter((q): q is number[] => !!q);
    // the points' spread: the nearer the closest two against the farthest two, the worse a correction is conditioned
    let quality = "pw-q-red";
    if (shown.length >= 2) {
      let near = Infinity, far = 0;
      for (let i = 0; i < shown.length; i += 1) for (let j = i + 1; j < shown.length; j += 1) {
        const dist = Math.hypot(shown[i][0] - shown[j][0], shown[i][1] - shown[j][1]);
        near = Math.min(near, dist); far = Math.max(far, dist);
      }
      const ratio = far ? near / far : 0;
      quality = ratio >= 0.35 ? "pw-q-green" : ratio >= 0.15 ? "pw-q-yellow" : "pw-q-red";
    }
    let out = shown.length >= 2 ? `<polygon class="pw-refline ${quality}" points="${shown.map((q) => q.join(",")).join(" ")}" vector-effect="non-scaling-stroke"/>` : "";
    l.adjust.forEach((p, i) => {
      const q = places[i];
      if (!q) return;
      const chosen = i === pointIndex ? " is-chosen" : "";
      out += p.master === frame
        ? `<path class="pw-refx${chosen}" d="M${q[0] - 7},${q[1] - 7}L${q[0] + 7},${q[1] + 7}M${q[0] + 7},${q[1] - 7}L${q[0] - 7},${q[1] + 7}" vector-effect="non-scaling-stroke"/>`
        : "";
      out += `<circle class="pw-refpoint${chosen}" cx="${q[0]}" cy="${q[1]}" r="${p.master === frame ? 9 : 5}" data-refpoint="${i}" vector-effect="non-scaling-stroke"/>`;
    });
    return out;
  }
  function startAdjust(): void {
    ($("adjust-panel") as HTMLElement).hidden = !views.adjust;
    const l = layer();
    if (!views.adjust || !l) return;
    if (!l.adjust?.length && l.surface) {
      // the first time: four points on the surface's corners, this frame their master
      const h = homography(l, frame);
      if (!h) { say(t("planar.needTracked")); return; }
      l.adjust = l.surface.map((corner) => ({ master: frame, home: unit(apply(h, ...(px(corner) as [number, number]))), keys: {} }));
      pointIndex = 0;
      changed = true;
      sendAdjust(l);
    }
  }
  function sendAdjust(l: PlanarLayer): void {
    // the engine makes the adjusted track a moment after the last change, then the overlays follow it
    window.clearTimeout(adjustTimer);
    adjustTimer = window.setTimeout(() => void (async () => {
      try {
        await api(`/api/planar/adjust/${l.id}`, { points: l.adjust ?? [] });
        await loadTrack(l);
        render();
      } catch (error) { say(error instanceof Error ? error.message : String(error)); }
    })(), 250);
  }
  function movePoint(l: PlanarLayer, i: number, x: number, y: number): void {
    const p = l.adjust?.[i];
    if (!p) return;
    if (p.master === frame) p.home = unit([x, y]);  // on its master frame: where it is, no correction
    else p.keys[String(frame)] = unit([x, y]);  // anywhere else: a correction keyed on this frame
    changed = true;
    sendAdjust(l);
  }
  function placePoint(l: PlanarLayer, x: number, y: number): void {
    placing = false;
    if (!rawHomography(l, frame)) { say(t("planar.needTracked")); return; }
    (l.adjust ??= []).push({ master: frame, home: unit([x, y]), keys: {} });
    pointIndex = l.adjust.length - 1;
    changed = true;
    say("");
    sendAdjust(l);
    render();
  }
  $("adj-new").addEventListener("click", () => { placing = true; say(t("planar.adjust.placing")); });
  $("adj-next").addEventListener("click", () => { const n = layer()?.adjust?.length ?? 0; if (n) { pointIndex = (pointIndex + 1) % n; render(); } });
  $("adj-master").addEventListener("click", () => {
    const l = layer(), p = l?.adjust?.[pointIndex];
    if (!l || !p) return;
    const q = placeOf(l, p, frame);
    if (!q) { say(t("planar.needTracked")); return; }
    p.home = unit(q);
    p.master = frame;
    delete p.keys[String(frame)];
    changed = true;
    sendAdjust(l);
    render();
  });
  $("adj-delete").addEventListener("click", () => {
    const l = layer();
    if (!l?.adjust?.length) return;
    l.adjust.splice(pointIndex, 1);
    pointIndex = Math.max(0, Math.min(pointIndex, l.adjust.length - 1));
    changed = true;
    sendAdjust(l);
    render();
  });
  $("adjust-panel").addEventListener("click", (event) => {
    // a tenth of a media pixel a press, as Mocha's nudge
    const b = (event.target as HTMLElement).closest<HTMLElement>("[data-nudge]");
    const l = layer(), p = l?.adjust?.[pointIndex];
    if (!b || !l || !p) return;
    const q = placeOf(l, p, frame);
    if (!q) return;
    const [dx, dy] = b.dataset.nudge!.split(",").map(Number);
    movePoint(l, pointIndex, q[0] + dx * 0.1, q[1] + dy * 0.1);
    render();
  });
  $("adj-auto").addEventListener("click", () => void (async () => {
    const l = layer(), p = l?.adjust?.[pointIndex];
    if (!l || !p || p.master === frame) return;
    try {
      const found = await api<{ at: number[]; score: number }>("/api/planar/nudge", { media_id: mediaId, layer_id: l.id, master: p.master, home: p.home, frame, patch: Number($<HTMLInputElement>("adj-patch").value) || 21, motion: Number($<HTMLInputElement>("adj-motion").value) || 16 });
      p.keys[String(frame)] = found.at;
      changed = true;
      sendAdjust(l);
      say(`${t("planar.adjust.auto")}: ${found.score.toFixed(2)}`);
      render();
    } catch (error) { say(error instanceof Error ? error.message : String(error)); }
  })());

  // ---- applying a layer's track to a clip (P3): a corner pin, or position, scale and rotation keyframes ----
  function paintTargets(): void {
    const timeline = engine.snapshot.timelines[engine.snapshot.activeTimeline];
    const clips = timeline.tracks.flatMap((tr) => tr.clips).filter((c) => c.id !== clipId && (c.kind === "video" || c.kind === "image" || c.kind === "text"));
    $<HTMLSelectElement>("target").innerHTML = clips.map((c) => `<option value="${c.id}">${esc(c.label)}</option>`).join("") || `<option value="">${t("planar.noTarget")}</option>`;
  }
  $("kind").addEventListener("change", () => { $("matte-row").hidden = $<HTMLSelectElement>("kind").value !== "matte"; });
  $("apply").addEventListener("click", () => void (async () => {
    const l = layer(), target = $<HTMLSelectElement>("target").value, kind = $<HTMLSelectElement>("kind").value;
    if (kind === "holdout") {
      // this clip's layers as its key's hold-out (P7): inside them the chroma key takes nothing away
      const key = engine.findClip(clipId)?.clip.key;
      if (!key) { say(t("planar.needKey")); return; }
      const chosen = layers.filter((one) => one.visible && one.shapes.length).map((one) => one.id);
      if (!chosen.length) { say(t("planar.needShape")); return; }
      engine.dispatch("clip.planar", { clipId, planar: { version: 1, layers } });
      engine.dispatch("clip.key", { clipId, key: { ...key, holdout: chosen } });
      changed = false;
      say(t("planar.holdoutApplied"));
      return;
    }
    if (kind === "matte") {
      // this clip's own layers as its matte, carried by their tracks (Mocha's Apply Matte); the target is this clip
      const chosen = layers.filter((one) => one.visible && one.shapes.length).map((one) => one.id);
      if (!chosen.length) { say(t("planar.needShape")); return; }
      engine.dispatch("clip.planar", { clipId, planar: { version: 1, layers } });
      engine.dispatch("clip.planarMatte", { clipId, planarMatte: { layers: chosen, feather: Math.max(0, Number($<HTMLInputElement>("feather").value) || 0), invert: $<HTMLInputElement>("invert").checked } });
      changed = false;
      say(t("planar.matteApplied"));
      return;
    }
    if (!l || !l.surface) { say(t("planar.needSurface")); return; }
    if (!target) { say(t("planar.noTarget")); return; }
    // the layers go on the clip first: the engine reads the surface from the project
    engine.dispatch("clip.planar", { clipId, planar: { version: 1, layers } });
    changed = false;
    try {
      const out = await api<{ cornerPin?: { points: number[][]; times: number[] }; keyframes?: Array<{ t: number; interp: string; props: Record<string, number> }>; frames: number }>("/api/planar/apply", { project: engine.snapshot, tracked_clip: clipId, layer_id: l.id, target_clip: target, kind });
      if (out.cornerPin) engine.dispatch("clip.cornerPin", { clipId: target, cornerPin: out.cornerPin });
      else if (out.keyframes) {
        // the target's other keyframes kept; its position, scale and rotation keys replaced by the track's
        const moved = new Set(["posX", "posY", "scale", "rotation"]);
        const kept = (engine.findClip(target)?.clip.keyframes ?? []).map((k) => ({ ...k, props: Object.fromEntries(Object.entries(k.props).filter(([p]) => !moved.has(p))) })).filter((k) => Object.keys(k.props).length);
        engine.dispatch("clip.keyframes.replace", { clipId: target, keyframes: [...kept, ...out.keyframes].sort((a, b) => a.t - b.t) });
      }
      const name = engine.findClip(target)?.clip.label ?? "";
      say(t("planar.applied").replace("{clip}", name).replace("{n}", String(out.frames)));
    } catch (error) { say(error instanceof Error ? error.message : String(error)); }
  })());

  // ---- closing: the layers saved on the clip ----
  function close(): void {
    if (job) void fetch(`/api/jobs/${job}`, { method: "DELETE" });
    if (changed) {
      const planar: ClipPlanar = { version: 1, layers };
      engine.dispatch("clip.planar", { clipId, planar });
    }
    document.removeEventListener("keydown", keys, true);
    root.remove();
  }
  $("done").addEventListener("click", close);
  function keys(event: KeyboardEvent): void {
    if ((event.target as HTMLElement).matches?.("input, select, textarea")) return;
    if (event.key === "Escape") { event.preventDefault(); if (drawing.length) { drawing = []; render(); } else close(); }
    else if (event.key === "Enter" && drawing.length >= 3) { event.preventDefault(); void addShape(drawing).then(() => { drawing = []; render(); }); }
    else if (event.key === "ArrowRight" && !job) { event.preventDefault(); showFrame(frame + 1); }
    else if (event.key === "ArrowLeft" && !job) { event.preventDefault(); showFrame(frame - 1); }
    else if ((event.key === "Delete" || event.key === "Backspace") && picked) { event.preventDefault(); $("delete-point").click(); }
    else if ((event.key === "Delete" || event.key === "Backspace") && shapeIndex >= 0) { event.preventDefault(); $("delete-shape").click(); }
    else return;
    event.stopPropagation();
  }
  document.addEventListener("keydown", keys, true);

  // ---- opening ----
  void (async () => {
    try {
      media = await fetch(`/api/planar/media/${mediaId}`).then((r) => { if (!r.ok) throw new Error(t("planar.noMedia")); return r.json(); });
    } catch (error) { say(error instanceof Error ? error.message : String(error)); return; }
    const speed = clip.speed ?? 1;
    first = Math.max(0, Math.floor((clip.sourceIn ?? 0) * media!.fps));
    last = Math.min(media!.frames - 1, Math.max(first, Math.floor(((clip.sourceIn ?? 0) + clip.duration * speed) * media!.fps) - 1));
    scrub.min = String(first);
    scrub.max = String(last);
    $("stage").style.setProperty("--ar", `${media!.width} / ${media!.height}`);
    await loadTracks();
    paintSettings();
    paintTargets();
    say(layers.length ? "" : t("planar.hint"));
    showFrame(layers.length ? refFrame(layers[0]) : first);
  })();
}
