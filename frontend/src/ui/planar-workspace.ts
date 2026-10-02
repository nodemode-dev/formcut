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
import type { ClipPlanar, PlanarLayer } from "../engine/types";
import { api } from "../engine/api";
import { t } from "../i18n";
import { icon } from "./icons";

type Track = { frames: Map<number, number[]>; confidence: Map<number, number> };
type Media = { fps: number; width: number; height: number; frames: number };
const COLORS = ["#4b82f0", "#e25085", "#50e2a5", "#ffae2b", "#9e50e2", "#50cae2", "#e2a050", "#c9e250"];
const MOTIONS = ["translation", "scale", "rotation", "shear", "perspective"] as const;
const DEFAULTS: Record<string, unknown> = { translation: true, scale: true, rotation: true, shear: false, perspective: false, channel: "luminance", min_pixels: null, smoothing: 0, motion: "large", search_x: null, search_y: null, angle: 0, zoom: 0 };
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
  let tool: "select" | "draw" | "rect" = "draw";
  let mode: "add" | "subtract" = "add";
  const views = { surface: true, grid: false, trace: false, matte: false, stabilise: false };
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
          </div>
          <div class="pw-seg" data-ref="mode" role="group">
            <button data-mode="add">${t("planar.add")}</button><button data-mode="subtract">${t("planar.subtract")}</button>
          </div>
          <button class="tool-chip" data-ref="delete-shape">${icon("trash")}${t("planar.deleteShape")}</button>
        </section>
        <section class="pw-panel" data-ref="settings"></section>
        <section class="pw-panel">
          <div class="pw-head"><span>${t("planar.apply")}</span></div>
          <div class="pw-row"><span>${t("planar.applyTo")}</span><select data-ref="target"></select></div>
          <div class="pw-row"><span>${t("planar.kind")}</span><select data-ref="kind"><option value="corner-pin">${t("planar.kind.pin")}</option><option value="transform">${t("planar.kind.transform")}</option><option value="matte">${t("planar.kind.matte")}</option></select></div>
          <div class="pw-row" data-ref="matte-row" hidden><span>${t("planar.feather")}</span><span class="pw-pair"><input type="number" data-ref="feather" min="0" max="100" step="0.5" value="2"><label class="pw-check"><input type="checkbox" data-ref="invert">${t("planar.invert")}</label></span></div>
          <button class="tool-chip" data-ref="apply">${icon("link")}${t("planar.applyBtn")}</button>
        </section>
      </aside>
      <main class="pw-main">
        <div class="pw-views" data-ref="views">
          ${(["surface", "grid", "trace", "matte", "stabilise"] as const).map((v) => `<button class="tool-chip" data-view="${v}">${t(`planar.view.${v}`)}</button>`).join("")}
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
  const homography = (l: PlanarLayer, index: number): number[] | null => {
    const tr = tracks.get(l.id);
    const h = tr?.frames.get(index);
    if (h) return h;
    return index === refFrame(l) ? [1, 0, 0, 0, 1, 0, 0, 0, 1] : null;
  };
  const px = (p: number[]) => [p[0] * media!.width, p[1] * media!.height];
  const unit = (p: number[]) => [p[0] / media!.width, p[1] / media!.height];

  // ---- drawing the frame and its overlays ----
  function render(): void {
    if (!media) return;
    const { width: W, height: H } = media;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    let out = "";
    layers.forEach((l, li) => {
      if (!l.visible) return;
      const h = homography(l, frame);
      const carried = (p: number[]) => (h ? apply(h, ...(px(p) as [number, number])) : px(p));
      const active = li === current;
      const faint = !h;  // not tracked at this frame: shown where drawn, dashed
      l.shapes.forEach((shape, si) => {
        const pts = shape.points.map((p) => carried(p).join(",")).join(" ");
        const fill = views.matte ? `${l.color}${shape.mode === "subtract" ? "00" : "55"}` : "none";
        out += `<polygon points="${pts}" fill="${fill}" stroke="${l.color}" stroke-width="${active && si === shapeIndex ? 3 : 2}" vector-effect="non-scaling-stroke"${faint ? ' stroke-dasharray="6 5"' : ""}${shape.mode === "subtract" ? ' class="is-subtract"' : ""} data-layer="${li}" data-shape="${si}"/>`;
        if (active && tool === "select" && !l.locked) {
          shape.points.forEach((p, pi) => { const [x, y] = carried(p); out += `<circle class="pw-handle" cx="${x}" cy="${y}" r="5" data-point="${si}:${pi}" vector-effect="non-scaling-stroke"/>`; });
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
    });
    if (drawing.length) out += `<polyline class="pw-drawing" points="${drawing.map((p) => p.join(",")).join(" ")}" vector-effect="non-scaling-stroke"/>`;
    svg.innerHTML = out;
    // the stabilised view: the picture moved so the current layer's tracked plane holds still
    const l = layer(), h = l ? homography(l, frame) : null;
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
    const tr = l ? tracks.get(l.id) : undefined;
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
      <button class="icon-btn${l.visible ? " is-on" : ""}" data-act="visible" title="${t("planar.visible")}" aria-label="${t("planar.visible")}">${icon(l.visible ? "eye" : "eyeOff")}</button>
      <button class="icon-btn${l.tracking ? " is-on" : ""}" data-act="tracking" title="${t("planar.tracking")}" aria-label="${t("planar.tracking")}">${icon("settings")}</button>
      <button class="icon-btn${l.locked ? " is-on" : ""}" data-act="locked" title="${t("planar.locked")}" aria-label="${t("planar.locked")}">${icon("lock")}</button>
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
    if (act === "visible" || act === "tracking" || act === "locked") { l[act as "visible" | "tracking" | "locked"] = !l[act as "visible" | "tracking" | "locked"]; changed = true; }
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
  });
  $("add-layer").addEventListener("click", () => { newLayer(); render(); });

  // ---- track settings, as Mocha names them ----
  function paintSettings(): void {
    const l = layer(), box = $("settings");
    if (!l) { box.innerHTML = ""; return; }
    const s = { ...DEFAULTS, ...l.settings } as Record<string, unknown>;
    const num = (key: string, step: number, min: number, max: number, autoable = false) => `<input type="number" data-key="${key}" step="${step}" min="${min}" max="${max}" value="${s[key] ?? ""}" placeholder="${autoable ? t("planar.auto") : ""}">`;
    box.innerHTML = `<div class="pw-head"><span>${t("planar.trackSettings")}</span></div>
      <div class="pw-motions">${MOTIONS.map((m) => `<label><input type="checkbox" data-key="${m}" ${s[m] ? "checked" : ""}>${t(`planar.motion.${m}`)}</label>`).join("")}</div>
      <div class="pw-row"><span>${t("planar.channel")}</span><select data-key="channel"><option value="luminance" ${s.channel === "luminance" ? "selected" : ""}>${t("planar.luminance")}</option><option value="auto" ${s.channel === "auto" ? "selected" : ""}>${t("planar.autoChannel")}</option></select></div>
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
    if (!l || !key) return;
    if (!(await invalidate(l))) { paintSettings(); return; }
    const value = input.type === "checkbox" ? input.checked : input.type === "number" ? (input.value === "" ? null : Number(input.value)) : input.value;
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
    if (b) { const v = b.dataset.view as keyof typeof views; views[v] = !views[v]; render(); }
  });
  $("align").addEventListener("click", () => {
    // the surface fitted to the whole frame on the current frame, kept in the reference's coordinates
    const l = layer(), h = l ? homography(l, frame) : null;
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
    const h = homography(l, frame);
    return h ? unit(apply(invert(h), x, y)) : null;
  };

  async function addShape(points: number[][]): Promise<void> {
    let l = layer();
    if (!l || l.locked) l = newLayer();
    if (!l.shapes.length) l.reference = frame / media!.fps;  // the first shape sets the frame it is drawn on
    const mapped = points.map((p) => toReference(l!, p[0], p[1]));
    if (mapped.some((p) => !p)) { say(t("planar.needTracked")); return; }
    if (!(await invalidate(l))) return;
    l.shapes.push({ points: (mapped as number[][]).map((p) => [Number(p[0].toFixed(6)), Number(p[1].toFixed(6))]), mode });
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

  let drag: { kind: "point" | "corner" | "rect"; a: number; b: number; start: [number, number] } | null = null;
  svg.addEventListener("pointerdown", (event) => {
    if (job) return;
    const [x, y] = pointer(event);
    const target = event.target as SVGElement;
    const l = layer();
    if (target.dataset.corner !== undefined && l) { drag = { kind: "corner", a: Number(target.dataset.corner), b: 0, start: [x, y] }; svg.setPointerCapture(event.pointerId); return; }
    if (tool === "select") {
      if (target.dataset.point && l) { const [si, pi] = target.dataset.point.split(":").map(Number); drag = { kind: "point", a: si, b: pi, start: [x, y] }; svg.setPointerCapture(event.pointerId); return; }
      if (target.dataset.shape !== undefined) { current = Number(target.dataset.layer); shapeIndex = Number(target.dataset.shape); paintSettings(); render(); }
      return;
    }
    if (tool === "rect") { drag = { kind: "rect", a: 0, b: 0, start: [x, y] }; drawing = [[x, y], [x, y], [x, y], [x, y], [x, y]]; svg.setPointerCapture(event.pointerId); return; }
    drawing.push([x, y]);
    render();
  });
  // a double click closes the shape (its second press added the same point again: dropped)
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
      drawing = [[x0, y0], [x, y0], [x, y], [x0, y], [x0, y0]];
    } else if (l && drag.kind === "corner" && l.surface) {
      const p = toReference(l, x, y);
      if (p) { l.surface[drag.a] = p; changed = true; }
    } else if (l && drag.kind === "point") {
      const p = toReference(l, x, y);
      if (p) { l.shapes[drag.a].points[drag.b] = p; changed = true; }
    }
    render();
  });
  svg.addEventListener("pointerup", () => void (async () => {
    if (!drag) return;
    const was = drag;
    drag = null;
    if (was.kind === "rect") {
      const box = drawing.slice(0, 4);
      drawing = [];
      if (Math.abs(box[2][0] - box[0][0]) > 4 && Math.abs(box[2][1] - box[0][1]) > 4) await addShape(box);
    } else if (was.kind === "point") {
      const l = layer();
      if (l && !(await invalidate(l))) await loadTracks();  // kept the track: the shape goes back
    }
    render();
  })());

  // ---- tracking: the engine's jobs ----
  const apiLayer = (l: PlanarLayer) => ({ id: l.id, shapes: l.shapes.map((s) => ({ points: s.points, mode: s.mode })), reference: l.reference, settings: l.settings });

  async function loadTrack(l: PlanarLayer): Promise<void> {
    const reply = await fetch(`/api/planar/track/${l.id}`);
    if (!reply.ok) { tracks.delete(l.id); return; }
    const data = await reply.json() as { frames: number[]; matrices: number[][]; confidence: number[] };
    tracks.set(l.id, { frames: new Map(data.frames.map((f, i) => [f, data.matrices[i]])), confidence: new Map(data.frames.map((f, i) => [f, data.confidence[i]])) });
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

  // ---- applying a layer's track to a clip (P3): a corner pin, or position, scale and rotation keyframes ----
  function paintTargets(): void {
    const timeline = engine.snapshot.timelines[engine.snapshot.activeTimeline];
    const clips = timeline.tracks.flatMap((tr) => tr.clips).filter((c) => c.id !== clipId && (c.kind === "video" || c.kind === "image" || c.kind === "text"));
    $<HTMLSelectElement>("target").innerHTML = clips.map((c) => `<option value="${c.id}">${esc(c.label)}</option>`).join("") || `<option value="">${t("planar.noTarget")}</option>`;
  }
  $("kind").addEventListener("change", () => { $("matte-row").hidden = $<HTMLSelectElement>("kind").value !== "matte"; });
  $("apply").addEventListener("click", () => void (async () => {
    const l = layer(), target = $<HTMLSelectElement>("target").value, kind = $<HTMLSelectElement>("kind").value;
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
