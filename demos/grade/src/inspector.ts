import type { ProjectEngine } from "../../../frontend/src/engine/project";
import { buildColorSection } from "../../../frontend/src/ui/color-section";
import { propPoints, propValue } from "../../../frontend/src/engine/keyframes";
import { SPEED_PRESETS, speedAt } from "../../../frontend/src/engine/timing";
import { MOTION_PRESETS } from "../../../frontend/src/engine/motion";
import type { Clip, ClipMask, KeyframeProp } from "../../../frontend/src/engine/types";
import { icon } from "../../../frontend/src/ui/icons";
import { LOOKS } from "./looks";
import { cubeName, parseCube, registerCube } from "./grade";
import { MASK_SHAPE_NAMES, TRANSITION_KINDS, defaultMask } from "./render";

interface SliderSpec {
  label: string;
  min: number;
  max: number;
  step: number;
  unit?: string;
  read: (clip: Clip) => number;
  write: (clip: Clip, value: number) => void;
  keyProp?: (clip: Clip) => KeyframeProp | null;
}

interface Control {
  row: HTMLElement;
  sync: (clip: Clip) => void;
}

const TABS: Array<[string, string]> = [["color", "Color"], ["look", "Look"], ["mask", "Mask"], ["motion", "Motion"]];
const SVG = "http://www.w3.org/2000/svg";
const title = (id: string): string => id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export interface InspectorHooks {
  windowOnOverlay: (clipId: string) => void;
  say: (text: string) => void;
}

export function buildInspector(engine: ProjectEngine, hooks: InspectorHooks): HTMLElement {
  const element = document.createElement("section");
  element.className = "pane pane-inspector";
  element.dataset.empty = "true";
  element.innerHTML = `
    <div class="inspector-head"><div class="seg">${TABS.map(([key, label], i) => `<button class="${i === 0 ? "is-active" : ""}" data-tab="${key}">${label}</button>`).join("")}</div></div>
    <div class="inspector-body">
      <div class="inspector-empty">Select a picture clip on the timeline to grade it.</div>
      <div class="section" data-tab="look" data-section="look"><div class="section-head">Look</div></div>
      <div class="section" data-tab="look" data-section="finish"><div class="section-head">Finishing</div></div>
      <div class="section" data-tab="mask" data-section="mask"><div class="section-head">Mask</div></div>
      <div class="section" data-tab="motion" data-section="keys"><div class="section-head">Keyframes</div></div>
      <div class="section" data-tab="motion" data-section="speed"><div class="section-head">Speed ramp</div></div>
      <div class="section" data-tab="motion" data-section="transition"><div class="section-head">Transition in</div></div>
    </div>`;
  const body = element.querySelector<HTMLElement>(".inspector-body")!;
  const section = (name: string) => element.querySelector<HTMLElement>(`[data-section="${name}"]`)!;
  const colour = buildColorSection(engine);
  colour.dataset.tab = "color";
  body.insertBefore(colour, section("look"));
  const controls: Control[] = [];
  const syncs: Array<(clip: Clip) => void> = [];
  let tab = "color";

  const current = (): Clip | null => {
    const id = engine.snapshot.selectedClipId;
    return id ? engine.findClip(id)?.clip ?? null : null;
  };
  const picture = (clip: Clip | null): clip is Clip => !!clip && (clip.kind === "video" || clip.kind === "image");
  const localTime = (clip: Clip): number => Math.round(Math.max(0, Math.min(clip.duration, engine.snapshot.playhead - clip.start)) * 100) / 100;

  const fxIndex = (clip: Clip, id: string): number => (clip.effects ?? []).findIndex((entry) => entry.id === id);
  const ensureFx = (clip: Clip, id: string): number => {
    const found = fxIndex(clip, id);
    if (found >= 0) return found;
    const list = (clip.effects ?? []).map((entry) => ({ ...entry }));
    list.push({ id, amount: 0 });
    engine.dispatch("clip.effects", { clipId: clip.id, effects: list });
    return list.length - 1;
  };
  const writeFx = (clip: Clip, id: string, amount: number) => {
    const index = ensureFx(clip, id);
    const fresh = current() ?? clip;
    const prop = `fx.${index}.amount` as KeyframeProp;
    if (propPoints(fresh, prop).length) engine.dispatch("clip.keyframe", { clipId: clip.id, t: localTime(fresh), set: { [prop]: amount } });
    else {
      const list = (fresh.effects ?? []).map((entry) => ({ ...entry }));
      list[index].amount = amount;
      engine.dispatch("clip.effects", { clipId: clip.id, effects: list });
    }
  };

  const addSlider = (host: HTMLElement, spec: SliderSpec): Control => {
    const row = document.createElement("div");
    row.className = "prop-row has-slide" + (spec.keyProp ? " has-key" : "");
    row.innerHTML = `<span></span><div class="num-field"><input type="number" /><span class="unit"></span></div><span class="prop-aux"></span><input class="prop-slide" type="range" />`;
    const label = row.children[0] as HTMLElement;
    const number = row.querySelector<HTMLInputElement>('input[type="number"]')!;
    const range = row.querySelector<HTMLInputElement>('input[type="range"]')!;
    const aux = row.querySelector<HTMLElement>(".prop-aux")!;
    label.textContent = spec.label;
    row.querySelector<HTMLElement>(".unit")!.textContent = spec.unit ?? "";
    for (const input of [number, range]) {
      input.min = String(spec.min);
      input.max = String(spec.max);
      input.step = String(spec.step);
    }
    let key: HTMLButtonElement | null = null;
    if (spec.keyProp) {
      key = document.createElement("button");
      key.className = "key-btn";
      key.type = "button";
      key.setAttribute("aria-label", `Keyframe ${spec.label}`);
      key.innerHTML = icon("diamond");
      aux.append(key);
      key.addEventListener("click", () => {
        const clip = current();
        const prop = clip ? spec.keyProp!(clip) : null;
        if (!clip || !prop) return;
        const local = localTime(clip);
        const here = propPoints(clip, prop).some((point) => Math.abs(point.t - local) < 0.02);
        if (here) engine.dispatch("clip.keyframe", { clipId: clip.id, t: local, remove: prop });
        else engine.dispatch("clip.keyframe", { clipId: clip.id, t: local, set: { [prop]: spec.read(clip) } });
      });
    }
    const commit = (raw: string) => {
      const clip = current();
      const value = Number(raw);
      if (!clip || !Number.isFinite(value)) return;
      spec.write(clip, Math.min(spec.max, Math.max(spec.min, value)));
    };
    range.addEventListener("input", () => commit(range.value));
    number.addEventListener("change", () => commit(number.value));
    host.append(row);
    const control: Control = {
      row,
      sync: (clip) => {
        const value = String(Math.round(spec.read(clip) * 1000) / 1000);
        if (range.value !== value) range.value = value;
        if (document.activeElement !== number && number.value !== value) number.value = value;
        if (key && spec.keyProp) {
          const prop = spec.keyProp(clip);
          const points = prop ? propPoints(clip, prop) : [];
          const local = engine.snapshot.playhead - clip.start;
          const state = !points.length ? "none" : points.some((point) => Math.abs(point.t - local) < 0.02) ? "here" : "keyed";
          if (key.dataset.state !== state) key.dataset.state = state;
        }
      },
    };
    controls.push(control);
    return control;
  };

  const addSelect = (host: HTMLElement, label: string, options: Array<[string, string]>, onChange: (value: string) => void): HTMLSelectElement => {
    const row = document.createElement("div");
    row.className = "prop-row";
    row.innerHTML = `<span></span><select class="mini-select"></select><span class="prop-aux"></span>`;
    (row.children[0] as HTMLElement).textContent = label;
    const select = row.querySelector("select")!;
    select.setAttribute("aria-label", label);
    select.innerHTML = options.map(([value, text]) => `<option value="${value}">${text}</option>`).join("");
    select.addEventListener("change", () => onChange(select.value));
    host.append(row);
    return select;
  };

  const addButtons = (host: HTMLElement, buttons: Array<[string, string, () => void]>): HTMLButtonElement[] => {
    const row = document.createElement("div");
    row.className = "demo-row grade-actions";
    const made = buttons.map(([text, hint, act]) => {
      const button = document.createElement("button");
      button.className = "tool-chip";
      button.type = "button";
      button.textContent = text;
      button.title = hint;
      button.addEventListener("click", act);
      row.append(button);
      return button;
    });
    host.append(row);
    return made;
  };

  const note = (host: HTMLElement, text: string): HTMLElement => {
    const p = document.createElement("p");
    p.className = "demo-hint";
    p.textContent = text;
    host.append(p);
    return p;
  };

  const lookHost = section("look");
  const lookSelect = addSelect(lookHost, "Look", [["", "None"], ...LOOKS.map((look): [string, string] => [look.id, look.name])], (value) => {
    const clip = current();
    if (clip) engine.dispatch("clip.effect", { clipId: clip.id, effectId: value || null });
  });
  syncs.push((clip) => {
    const id = clip.effectId ?? "";
    if (lookSelect.value !== id) lookSelect.value = id;
  });
  addSlider(lookHost, {
    label: "Strength", min: 0, max: 1, step: 0.01,
    read: (c) => c.lutIntensity ?? 1,
    write: (c, v) => engine.dispatch("clip.creator", { clipId: c.id, patch: { lutIntensity: v } }),
  });
  const lutInput = document.createElement("input");
  lutInput.type = "file";
  lutInput.accept = ".cube";
  lutInput.hidden = true;
  lookHost.append(lutInput);
  const lutName = document.createElement("span");
  const [lutPick, lutClear] = addButtons(lookHost, [
    ["Load .cube LUT", "Apply a 3D LUT file from your computer, read in this page only", () => lutInput.click()],
    ["Remove LUT", "Take the LUT off this clip", () => {
      const clip = current();
      if (clip) engine.dispatch("clip.creator", { clipId: clip.id, patch: { lutId: undefined } });
    }],
  ]);
  void lutPick;
  lutName.className = "demo-hint lut-name";
  lookHost.append(lutName);
  syncs.push((clip) => {
    const name = cubeName(clip.lutId);
    const text = name ? `LUT: ${name}` : "No LUT on this clip";
    if (lutName.textContent !== text) lutName.textContent = text;
    if (lutClear.disabled !== !name) lutClear.disabled = !name;
  });
  lutInput.addEventListener("change", async () => {
    const file = lutInput.files?.[0];
    lutInput.value = "";
    const clip = current();
    if (!file || !clip) return;
    try {
      const text = await file.text();
      parseCube(text);
      engine.dispatch("clip.creator", { clipId: clip.id, patch: { lutId: registerCube(file.name.replace(/\.cube$/i, ""), text) } });
      hooks.say(`LUT ${file.name} applied`);
    } catch (error) {
      hooks.say(error instanceof Error ? error.message : "That file is not a 3D LUT");
    }
  });
  note(lookHost, "Looks are the engine's own grade stacks. Strength blends the look and any LUT with the graded picture.");

  const finishHost = section("finish");
  addSlider(finishHost, {
    label: "Vignette", min: 0, max: 1, step: 0.01,
    read: (c) => {
      const index = fxIndex(c, "vignette");
      return index < 0 ? 0 : propValue(c, `fx.${index}.amount` as KeyframeProp, engine.snapshot.playhead - c.start);
    },
    write: (c, v) => writeFx(c, "vignette", v),
    keyProp: (c) => (fxIndex(c, "vignette") < 0 ? null : (`fx.${fxIndex(c, "vignette")}.amount` as KeyframeProp)),
  });
  addSlider(finishHost, {
    label: "Grain", min: 0, max: 1, step: 0.01,
    read: (c) => {
      const index = fxIndex(c, "grain");
      return index < 0 ? 0 : propValue(c, `fx.${index}.amount` as KeyframeProp, engine.snapshot.playhead - c.start);
    },
    write: (c, v) => writeFx(c, "grain", v),
    keyProp: (c) => (fxIndex(c, "grain") < 0 ? null : (`fx.${fxIndex(c, "grain")}.amount` as KeyframeProp)),
  });

  const maskHost = section("mask");
  const maskPatch = (patch: Partial<ClipMask>) => {
    const clip = current();
    if (!clip) return;
    engine.dispatch("clip.mask", { clipId: clip.id, mask: { ...(clip.mask ?? defaultMask()), ...patch } });
  };
  const maskShape = addSelect(maskHost, "Shape", [["", "None"], ...MASK_SHAPE_NAMES.map((name): [string, string] => [name, title(name)])], (value) => {
    const clip = current();
    if (!clip) return;
    if (!value) engine.dispatch("clip.mask", { clipId: clip.id, mask: null });
    else maskPatch({ shape: value as ClipMask["shape"] });
  });
  const maskSliders = (
    [["Left", "x", 0, 100, 1], ["Top", "y", 0, 100, 1], ["Width", "w", 1, 100, 1], ["Height", "h", 1, 100, 1], ["Feather", "feather", 0, 50, 0.5], ["Angle", "angle", -180, 180, 1]] as const
  ).map(([label, key, min, max, step]) => addSlider(maskHost, {
    label, min, max, step, unit: key === "angle" ? "deg" : "%",
    read: (c) => (c.mask ? (c.mask[key] ?? 0) : 0),
    write: (c, v) => c.mask && engine.dispatch("clip.mask", { clipId: c.id, mask: { ...c.mask, [key]: v } }),
  }));
  const invertRow = document.createElement("div");
  invertRow.className = "prop-row";
  invertRow.innerHTML = `<span>Invert</span><label class="demo-check"><input type="checkbox" /> Show outside</label><span class="prop-aux"></span>`;
  const invert = invertRow.querySelector("input")!;
  invert.addEventListener("change", () => {
    const clip = current();
    if (clip?.mask) engine.dispatch("clip.mask", { clipId: clip.id, mask: { ...clip.mask, invert: invert.checked } });
  });
  maskHost.append(invertRow);
  addButtons(maskHost, [["Window on Overlay", "Copy this clip to the Overlay track with a feathered window, to grade a part of the picture", () => {
    const clip = current();
    if (clip) hooks.windowOnOverlay(clip.id);
  }]]);
  note(maskHost, "A mask keeps the clip only inside its shape. Stacking a graded copy with a mask over the original is how a part of the picture is graded.");
  syncs.push((clip) => {
    const shape = clip.mask?.shape ?? "";
    if (maskShape.value !== shape) maskShape.value = shape;
    for (const control of maskSliders) control.row.hidden = !clip.mask;
    if (invertRow.hidden !== !clip.mask) invertRow.hidden = !clip.mask;
    if (invert.checked !== !!clip.mask?.invert) invert.checked = !!clip.mask?.invert;
  });

  const keysHost = section("keys");
  const transformKey = (prop: "scale" | "posX" | "posY" | "opacity") => (): KeyframeProp => prop;
  const tf = (label: string, prop: "scale" | "posX" | "posY" | "opacity", min: number, max: number, step: number, unit: string) =>
    addSlider(keysHost, {
      label, min, max, step, unit,
      read: (c) => propValue(c, prop, engine.snapshot.playhead - c.start),
      write: (c, v) => {
        if (propPoints(c, prop).length) engine.dispatch("clip.keyframe", { clipId: c.id, t: localTime(c), set: { [prop]: v } });
        else engine.dispatch("clip.transform", { clipId: c.id, patch: { [prop]: v } });
      },
      keyProp: transformKey(prop),
    });
  tf("Scale", "scale", 20, 300, 1, "%");
  tf("Position X", "posX", -100, 100, 0.5, "%");
  tf("Position Y", "posY", -100, 100, 0.5, "%");
  tf("Opacity", "opacity", 0, 100, 1, "%");
  const lane = document.createElementNS(SVG, "svg");
  lane.setAttribute("class", "key-lane");
  lane.setAttribute("viewBox", "0 0 240 22");
  lane.setAttribute("aria-label", "Keyframes of this clip");
  keysHost.append(lane);
  const laneDraw = (clip: Clip) => {
    const times = [...new Set((clip.keyframes ?? []).map((k) => k.t))].sort((a, b) => a - b);
    const local = Math.max(0, Math.min(clip.duration, engine.snapshot.playhead - clip.start));
    const signature = `${clip.id}|${clip.duration}|${times.join(",")}|${Math.round((local / clip.duration) * 240)}`;
    if (lane.dataset.sig === signature) return;
    lane.dataset.sig = signature;
    const x = (t: number) => 8 + (t / clip.duration) * 224;
    lane.innerHTML = `<line class="lane-base" x1="0" y1="11" x2="240" y2="11"/>${times
      .map((t) => `<path class="lane-key" data-t="${t}" d="M${x(t)} 5 l5 6 l-5 6 l-5 -6 z"/>`)
      .join("")}<line class="lane-head" x1="${x(local)}" y1="0" x2="${x(local)}" y2="22"/>`;
  };
  lane.addEventListener("click", (event) => {
    const clip = current();
    const target = (event.target as SVGElement).closest<SVGElement>("[data-t]");
    if (clip && target) engine.dispatch("transport.seek", clip.start + Number(target.dataset.t));
  });
  syncs.push(laneDraw);
  const motionSelect = addSelect(keysHost, "Motion", MOTION_PRESETS.map((name): [string, string] => [name, title(name)]), () => undefined);
  addButtons(keysHost, [
    ["Apply motion", "Add the preset's keyframes to this clip", () => {
      const clip = current();
      if (clip) engine.dispatch("clip.motion", { clipId: clip.id, preset: motionSelect.value, duration: Math.min(1.5, clip.duration) });
    }],
    ["Next ease", "Cycle the easing of the key at the playhead", () => {
      const clip = current();
      if (!clip) return;
      const local = localTime(clip);
      if ((clip.keyframes ?? []).some((k) => Math.abs(k.t - local) < 0.02)) engine.dispatch("clip.interp", { clipId: clip.id, t: local });
      else hooks.say("Move the playhead onto a keyframe to change its ease");
    }],
    ["Clear keys", "Remove every keyframe from this clip", () => {
      const clip = current();
      if (clip) engine.dispatch("clip.keyframes.replace", { clipId: clip.id, keyframes: [] });
    }],
  ]);
  note(keysHost, "The diamond keys a value at the playhead. Keyed values ease between keys; the Look tab's vignette and grain amounts key the same way.");

  const speedHost = section("speed");
  const graph = document.createElementNS(SVG, "svg");
  graph.setAttribute("class", "speed-graph");
  graph.setAttribute("viewBox", "0 0 240 90");
  graph.setAttribute("aria-label", "Speed over the clip, drag points to reshape");
  speedHost.append(graph);
  const speedMax = 4;
  const speedSelect = addSelect(speedHost, "Preset", Object.keys(SPEED_PRESETS).map((name): [string, string] => [name, title(name)]), () => undefined);
  const speedRead = document.createElement("span");
  speedRead.className = "demo-hint speed-read";
  addButtons(speedHost, [
    ["Apply ramp", "Shape this clip's speed with the preset", () => {
      const clip = current();
      if (clip) engine.dispatch("clip.speed-curve", { clipId: clip.id, preset: speedSelect.value });
    }],
    ["Constant", "Back to one steady speed", () => {
      const clip = current();
      if (clip) engine.dispatch("clip.speed-curve", { clipId: clip.id, points: [] });
    }],
  ]);
  speedHost.append(speedRead);
  let dragging: { index: number; points: Array<{ t: number; speed: number }> } | null = null;
  const pointsOf = (clip: Clip): Array<{ t: number; speed: number }> => (clip.speedCurve ?? []).map((p) => ({ ...p }));
  const drawSpeed = (clip: Clip, override?: Array<{ t: number; speed: number }>) => {
    const points = override ?? pointsOf(clip);
    const sx = (t: number) => (t / clip.duration) * 240;
    const sy = (s: number) => 85 - (Math.min(speedMax, s) / speedMax) * 80;
    const flat = points.length ? points : [{ t: 0, speed: clip.speed ?? 1 }, { t: clip.duration, speed: clip.speed ?? 1 }];
    const path = flat.map((p, i) => `${i ? "L" : "M"}${sx(p.t).toFixed(1)},${sy(p.speed).toFixed(1)}`).join(" ");
    const local = Math.max(0, Math.min(clip.duration, engine.snapshot.playhead - clip.start));
    const dots = points.map((p, i) => `<circle class="speed-point" data-i="${i}" cx="${sx(p.t).toFixed(1)}" cy="${sy(p.speed).toFixed(1)}" r="4.5"/>`).join("");
    const grid = [1, 2, 3].map((s) => `<line class="speed-grid" x1="0" x2="240" y1="${sy(s)}" y2="${sy(s)}"/>`).join("");
    const html = `${grid}<path class="speed-line" d="${path}"/>${dots}<line class="lane-head" x1="${sx(local)}" y1="0" x2="${sx(local)}" y2="90"/>`;
    if (graph.dataset.html !== html) {
      graph.dataset.html = html;
      graph.innerHTML = html;
    }
    const text = `Speed at the playhead: ${speedAt(clip, local).toFixed(2)}x`;
    if (speedRead.textContent !== text) speedRead.textContent = text;
  };
  const graphPoint = (event: PointerEvent, clip: Clip): { t: number; speed: number } => {
    const box = graph.getBoundingClientRect();
    const t = Math.min(clip.duration, Math.max(0, ((event.clientX - box.left) / box.width) * clip.duration));
    const speed = Math.min(speedMax, Math.max(0.1, ((85 - ((event.clientY - box.top) / box.height) * 90) / 80) * speedMax));
    return { t: Math.round(t * 100) / 100, speed: Math.round(speed * 20) / 20 };
  };
  graph.addEventListener("pointerdown", (event) => {
    const clip = current();
    if (!clip) return;
    const hit = (event.target as SVGElement).closest<SVGElement>("[data-i]");
    let points = pointsOf(clip);
    if (!points.length) points = [{ t: 0, speed: clip.speed ?? 1 }, { t: clip.duration, speed: clip.speed ?? 1 }];
    let index: number;
    if (hit) index = Number(hit.dataset.i);
    else {
      const point = graphPoint(event, clip);
      if (points.some((p) => Math.abs(p.t - point.t) < 0.1)) return;
      points.push(point);
      points.sort((a, b) => a.t - b.t);
      index = points.findIndex((p) => p === point);
    }
    dragging = { index, points };
    graph.setPointerCapture(event.pointerId);
    drawSpeed(clip, points);
  });
  graph.addEventListener("pointermove", (event) => {
    const clip = current();
    if (!clip || !dragging || !graph.hasPointerCapture(event.pointerId)) return;
    const { index, points } = dragging;
    const point = graphPoint(event, clip);
    const before = index > 0 ? points[index - 1].t + 0.05 : 0;
    const after = index < points.length - 1 ? points[index + 1].t - 0.05 : clip.duration;
    points[index] = { t: index === 0 ? 0 : index === points.length - 1 ? clip.duration : Math.min(after, Math.max(before, point.t)), speed: point.speed };
    drawSpeed(clip, points);
  });
  graph.addEventListener("pointerup", () => {
    const clip = current();
    if (clip && dragging) engine.dispatch("clip.speed-curve", { clipId: clip.id, points: dragging.points });
    dragging = null;
  });
  graph.addEventListener("dblclick", (event) => {
    const clip = current();
    const hit = (event.target as SVGElement).closest<SVGElement>("[data-i]");
    if (!clip || !hit) return;
    const points = pointsOf(clip);
    points.splice(Number(hit.dataset.i), 1);
    engine.dispatch("clip.speed-curve", { clipId: clip.id, points });
  });
  syncs.push((clip) => {
    if (!dragging) drawSpeed(clip);
  });
  note(speedHost, "Drag a point to change speed, click to add one, double-click to remove it. The picture follows the curve; the music does not.");

  const transHost = section("transition");
  const transSelect = addSelect(transHost, "Type", [["", "None"], ...TRANSITION_KINDS.map((kind): [string, string] => [kind, kind === "dip" ? "Dip to black" : title(kind)])], (value) => {
    const clip = current();
    if (!clip) return;
    engine.dispatch("clip.transition", { clipId: clip.id, transition: value ? { type: value, duration: clip.transitionIn?.duration ?? 1 } : null });
  });
  const transLength = addSlider(transHost, {
    label: "Length", min: 0.1, max: 3, step: 0.05, unit: "s",
    read: (c) => c.transitionIn?.duration ?? 1,
    write: (c, v) => c.transitionIn && engine.dispatch("clip.transition", { clipId: c.id, transition: { type: c.transitionIn.type, duration: v } }),
  });
  syncs.push((clip) => {
    const type = clip.transitionIn?.type ?? "";
    if (transSelect.value !== type) transSelect.value = type;
    if (transLength.row.hidden !== !clip.transitionIn) transLength.row.hidden = !clip.transitionIn;
  });

  const showTab = () => {
    const clip = current();
    const usable = picture(clip);
    const flag = String(!usable);
    if (element.dataset.empty !== flag) element.dataset.empty = flag;
    for (const node of body.querySelectorAll<HTMLElement>(":scope > [data-tab]")) {
      const value = String(node.dataset.tab !== tab);
      if (node.dataset.tabHidden !== value) node.dataset.tabHidden = value;
    }
    const empties = body.querySelector<HTMLElement>(".inspector-empty")!;
    const text = clip && !usable ? "Titles and audio carry no picture to grade. Select a video or image clip." : "Select a picture clip on the timeline to grade it.";
    if (empties.textContent !== text) empties.textContent = text;
  };

  const sync = () => {
    const clip = current();
    if (picture(clip)) {
      for (const apply of syncs) apply(clip);
      for (const control of controls) control.sync(clip);
    }
    showTab();
  };

  element.querySelector(".seg")!.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-tab]");
    if (!button) return;
    tab = button.dataset.tab!;
    for (const node of element.querySelectorAll<HTMLElement>(".seg > button")) node.classList.toggle("is-active", node === button);
    sync();
  });
  engine.subscribe((_s, changed) => {
    if (changed === "clips" || changed === "clip-selection" || changed === "timeline" || changed === "playhead") sync();
  });
  sync();
  return element;
}
