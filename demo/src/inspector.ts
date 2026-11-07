import type { ProjectEngine } from "../../frontend/src/engine/project";
import { defaultTransform, COLOUR_NEUTRAL } from "../../frontend/src/engine/types";
import type { Clip, ColourPanel } from "../../frontend/src/engine/types";
import { icon } from "../../frontend/src/ui/icons";
import { getSource, onSources } from "./media";
import { BLEND_NAMES, EFFECTS, TRANSITIONS } from "./render";
import type { LumaScope } from "./scope";

interface Control {
  rows: HTMLElement[];
  sync: (clip: Clip) => void;
}

interface SliderSpec {
  label: string;
  min: number;
  max: number;
  step: number;
  unit?: string;
  read: (clip: Clip) => number;
  write: (clip: Clip, value: number) => void;
}

const TABS: Array<[string, string]> = [["clip", "Clip"], ["color", "Color"], ["effects", "Effects"], ["media", "Media"]];
const FACT_ROWS = 10;

export function buildInspector(engine: ProjectEngine, scope: LumaScope): HTMLElement {
  const element = document.createElement("section");
  element.className = "pane pane-inspector";
  element.dataset.empty = "true";
  element.innerHTML = `
    <div class="inspector-head"><div class="seg">${TABS.map(([key, label], i) => `<button class="${i === 0 ? "is-active" : ""}" data-tab="${key}">${label}</button>`).join("")}</div></div>
    <div class="inspector-body">
      <div class="inspector-empty">Select a clip on the timeline to edit it.</div>
      <div class="section" data-tab="clip" data-section="text"><div class="section-head">Title</div></div>
      <div class="section" data-tab="clip" data-section="transform"><div class="section-head">Transform</div></div>
      <div class="section" data-tab="clip" data-section="timing"><div class="section-head">Timing and sound</div></div>
      <div class="section" data-tab="color" data-section="color"><div class="section-head">Color<span class="spacer"></span><button class="iconbtn" data-ref="reset-colour" title="Reset color" aria-label="Reset color">${icon("reset")}</button></div></div>
      <div class="section" data-tab="color" data-section="scope"><div class="section-head">Luma waveform</div><div class="scope-host" data-ref="scope"></div></div>
      <div class="section" data-tab="effects" data-section="effects"><div class="section-head">Effects on this clip</div></div>
      <div class="section" data-tab="effects" data-section="transition"><div class="section-head">Transition in</div></div>
      <div class="section" data-tab="media" data-section="media"><div class="section-head" data-ref="media-title">Media</div>
        <dl class="facts" data-ref="facts">${Array.from({ length: FACT_ROWS }, () => "<dt></dt><dd></dd>").join("")}</dl>
        <div class="demo-hint" data-ref="media-hint">Pick an item in the Media tab or a clip on the timeline to probe its source.</div>
      </div>
    </div>`;
  const body = element.querySelector<HTMLElement>(".inspector-body")!;
  const section = (name: string) => element.querySelector<HTMLElement>(`[data-section="${name}"]`)!;
  const ref = <T extends HTMLElement>(name: string) => element.querySelector<T>(`[data-ref="${name}"]`)!;
  ref("scope").append(scope.canvas);
  const controls: Control[] = [];
  let tab = "clip";
  let sourceId: string | null = null;

  const current = (): Clip | null => {
    const id = engine.snapshot.selectedClipId;
    return id ? engine.findClip(id)?.clip ?? null : null;
  };

  const addSlider = (host: HTMLElement, spec: SliderSpec): Control => {
    const row = document.createElement("div");
    row.className = "prop-row has-slide";
    row.innerHTML = `<span></span><div class="num-field"><input type="number" /><span class="unit"></span></div><span class="prop-aux"></span><input class="prop-slide" type="range" />`;
    const label = row.children[0] as HTMLElement;
    const number = row.querySelector<HTMLInputElement>('input[type="number"]')!;
    const range = row.querySelector<HTMLInputElement>('input[type="range"]')!;
    label.textContent = spec.label;
    row.querySelector<HTMLElement>(".unit")!.textContent = spec.unit ?? "";
    for (const input of [number, range]) {
      input.min = String(spec.min);
      input.max = String(spec.max);
      input.step = String(spec.step);
    }
    const commit = (raw: string) => {
      const clip = current();
      const value = Number(raw);
      if (!clip || !Number.isFinite(value)) return;
      const clamped = Math.min(spec.max, Math.max(spec.min, value));
      spec.write(clip, clamped);
    };
    range.addEventListener("input", () => commit(range.value));
    number.addEventListener("change", () => commit(number.value));
    host.append(row);
    const control: Control = {
      rows: [row],
      sync: (clip) => {
        const value = String(Math.round(spec.read(clip) * 1000) / 1000);
        if (range.value !== value) range.value = value;
        if (document.activeElement !== number && number.value !== value) number.value = value;
      },
    };
    controls.push(control);
    return control;
  };

  const patchTransform = (clip: Clip, patch: Record<string, unknown>) => engine.dispatch("clip.transform", { clipId: clip.id, patch });
  const transformOf = (clip: Clip) => ({ ...defaultTransform(), ...clip.transform });

  const hideFor = (control: Control, kinds: Array<Clip["kind"]>, clip: Clip) => {
    const hidden = !kinds.includes(clip.kind);
    for (const row of control.rows) if (row.hidden !== hidden) row.hidden = hidden;
  };
  const visibility: Array<(clip: Clip) => void> = [];
  const only = (control: Control, kinds: Array<Clip["kind"]>) => visibility.push((clip) => hideFor(control, kinds, clip));

  const textHost = section("text");
  const textRow = document.createElement("div");
  textRow.className = "prop-row";
  textRow.innerHTML = `<span>Text</span><input class="demo-input" type="text" aria-label="Title text" /><span class="prop-aux"></span>`;
  const textInput = textRow.querySelector<HTMLInputElement>("input")!;
  textInput.addEventListener("input", () => {
    const clip = current();
    if (clip) engine.dispatch("clip.text", { clipId: clip.id, patch: { content: textInput.value } });
  });
  textHost.append(textRow);
  const colourRow = document.createElement("div");
  colourRow.className = "prop-row";
  colourRow.innerHTML = `<span>Color</span><input class="demo-color" type="color" aria-label="Title color" /><span class="prop-aux"></span>`;
  const colourInput = colourRow.querySelector<HTMLInputElement>("input")!;
  colourInput.addEventListener("input", () => {
    const clip = current();
    if (clip) engine.dispatch("clip.text", { clipId: clip.id, patch: { color: colourInput.value } });
  });
  textHost.append(colourRow);
  addSlider(textHost, {
    label: "Size", min: 1, max: 24, step: 0.2, unit: "%",
    read: (c) => c.textStyle?.size ?? 8,
    write: (c, v) => engine.dispatch("clip.text", { clipId: c.id, patch: { size: v } }),
  });

  const transformHost = section("transform");
  const t = (label: string, min: number, max: number, step: number, unit: string, key: "scale" | "posX" | "posY" | "rotation" | "opacity") => {
    const control = addSlider(transformHost, { label, min, max, step, unit, read: (c) => transformOf(c)[key], write: (c, v) => patchTransform(c, { [key]: v }) });
    only(control, ["video", "image", "text"]);
  };
  t("Scale", 5, 300, 1, "%", "scale");
  t("Position X", -100, 100, 0.5, "%", "posX");
  t("Position Y", -100, 100, 0.5, "%", "posY");
  t("Rotation", -180, 180, 1, "deg", "rotation");
  t("Opacity", 0, 100, 1, "%", "opacity");
  const blendRow = document.createElement("div");
  blendRow.className = "prop-row";
  blendRow.innerHTML = `<span>Blend</span><select class="mini-select" aria-label="Blend mode">${BLEND_NAMES.map((name) => `<option>${name}</option>`).join("")}</select><span class="prop-aux"></span>`;
  const blendSelect = blendRow.querySelector("select")!;
  blendSelect.addEventListener("change", () => {
    const clip = current();
    if (clip) patchTransform(clip, { blendMode: blendSelect.value });
  });
  transformHost.append(blendRow);
  const flipRow = document.createElement("div");
  flipRow.className = "prop-row";
  flipRow.innerHTML = `<span>Flip</span><label class="demo-check"><input type="checkbox" /> Horizontal</label><span class="prop-aux"></span>`;
  const flipInput = flipRow.querySelector("input")!;
  flipInput.addEventListener("change", () => {
    const clip = current();
    if (clip) patchTransform(clip, { flipH: flipInput.checked });
  });
  transformHost.append(flipRow);
  visibility.push((clip) => {
    const hidden = clip.kind === "audio";
    if (blendRow.hidden !== hidden) blendRow.hidden = hidden;
    if (flipRow.hidden !== hidden) flipRow.hidden = hidden;
    const text = clip.kind !== "text";
    if (textRow.hidden !== text) textRow.hidden = text;
    if (colourRow.hidden !== text) colourRow.hidden = text;
    if (textHost.hidden !== text) textHost.hidden = text;
    if (transformHost.hidden !== hidden) transformHost.hidden = hidden;
  });

  const timingHost = section("timing");
  const speed = addSlider(timingHost, {
    label: "Speed", min: 0.25, max: 4, step: 0.05, unit: "x",
    read: (c) => c.speed ?? 1,
    write: (c, v) => engine.dispatch("clip.timing", { clipId: c.id, speed: v }),
  });
  only(speed, ["video", "audio"]);
  addSlider(timingHost, {
    label: "Fade in", min: 0, max: 5, step: 0.05, unit: "s",
    read: (c) => c.fadeIn ?? 0,
    write: (c, v) => engine.dispatch("clip.timing", { clipId: c.id, fadeIn: v }),
  });
  addSlider(timingHost, {
    label: "Fade out", min: 0, max: 5, step: 0.05, unit: "s",
    read: (c) => c.fadeOut ?? 0,
    write: (c, v) => engine.dispatch("clip.timing", { clipId: c.id, fadeOut: v }),
  });
  const volume = addSlider(timingHost, {
    label: "Volume", min: 0, max: 2, step: 0.01, unit: "x",
    read: (c) => c.volume ?? 1,
    write: (c, v) => engine.dispatch("clip.style", { clipId: c.id, style: { ...structuredClone(c), volume: v } }),
  });
  only(volume, ["video", "audio"]);

  const colourHost = section("color");
  const colourSpecs: Array<[string, keyof ColourPanel, number, number, number, string]> = [
    ["Exposure", "exposure", -2, 2, 0.05, "ev"],
    ["Brightness", "brightness", -100, 100, 1, ""],
    ["Contrast", "contrast", -100, 100, 1, ""],
    ["Saturation", "saturation", -100, 100, 1, ""],
    ["Temperature", "temperature", 2500, 10500, 50, "K"],
    ["Tint", "tint", -100, 100, 1, ""],
    ["Fade", "fade", 0, 100, 1, ""],
    ["Vignette", "vignette", 0, 100, 1, ""],
  ];
  for (const [label, key, min, max, step, unit] of colourSpecs) {
    const control = addSlider(colourHost, {
      label, min, max, step, unit,
      read: (c) => c.colour?.[key] ?? COLOUR_NEUTRAL[key],
      write: (c, v) => engine.dispatch("clip.colour", { clipId: c.id, colour: { [key]: v } }),
    });
    only(control, ["video", "image", "text"]);
  }
  ref("reset-colour").addEventListener("click", () => {
    const clip = current();
    if (clip) engine.dispatch("clip.colour", { clipId: clip.id, colour: null });
  });

  const fxHost = section("effects");
  const fxToggles = new Map<string, HTMLInputElement>();
  const writeEffects = (clip: Clip, id: string, change: { amount?: number; on?: boolean }) => {
    const list = (clip.effects ?? []).map((entry) => ({ ...entry }));
    const at = list.findIndex((entry) => entry.id === id);
    if (change.on === false && at >= 0) list.splice(at, 1);
    else if (at >= 0 && change.amount !== undefined) list[at].amount = change.amount;
    else if (at < 0 && change.on) list.push({ id, amount: change.amount ?? 60 });
    engine.dispatch("clip.effects", { clipId: clip.id, effects: list });
  };
  for (const fx of EFFECTS) {
    const toggleRow = document.createElement("div");
    toggleRow.className = "prop-row";
    toggleRow.innerHTML = `<span>${fx.name}</span><label class="demo-check"><input type="checkbox" /> On</label><span class="prop-aux"></span>`;
    const input = toggleRow.querySelector("input")!;
    input.addEventListener("change", () => {
      const clip = current();
      if (clip) writeEffects(clip, fx.id, { on: input.checked });
    });
    fxToggles.set(fx.id, input);
    fxHost.append(toggleRow);
    const control = addSlider(fxHost, {
      label: "Amount", min: 0, max: 100, step: 1, unit: "%",
      read: (c) => c.effects?.find((e) => e.id === fx.id)?.amount ?? 0,
      write: (c, v) => writeEffects(c, fx.id, { amount: v, on: true }),
    });
    only(control, ["video", "image", "text"]);
    visibility.push((clip) => {
      const hidden = clip.kind === "audio";
      if (toggleRow.hidden !== hidden) toggleRow.hidden = hidden;
    });
  }

  const transHost = section("transition");
  const transRow = document.createElement("div");
  transRow.className = "prop-row";
  transRow.innerHTML = `<span>Type</span><select class="mini-select" aria-label="Transition type"><option value="">None</option>${TRANSITIONS.map((tr) => `<option value="${tr.id}">${tr.name}</option>`).join("")}</select><span class="prop-aux"></span>`;
  const transSelect = transRow.querySelector("select")!;
  transHost.append(transRow);
  const transLength = addSlider(transHost, {
    label: "Length", min: 0.1, max: 3, step: 0.05, unit: "s",
    read: (c) => c.transitionIn?.duration ?? 1,
    write: (c, v) => c.transitionIn && engine.dispatch("clip.transition", { clipId: c.id, transition: { type: c.transitionIn.type, duration: v } }),
  });
  transSelect.addEventListener("change", () => {
    const clip = current();
    if (!clip) return;
    engine.dispatch("clip.transition", { clipId: clip.id, transition: transSelect.value ? { type: transSelect.value, duration: clip.transitionIn?.duration ?? 1 } : null });
  });
  visibility.push((clip) => {
    const hidden = clip.kind === "audio";
    if (transHost.hidden !== hidden) transHost.hidden = hidden;
    if (transLength.rows[0].hidden !== hidden) transLength.rows[0].hidden = hidden;
  });

  const facts = ref<HTMLElement>("facts");
  const dts = [...facts.querySelectorAll("dt")];
  const dds = [...facts.querySelectorAll("dd")];
  const paintFacts = () => {
    const clip = current();
    const id = sourceId ?? clip?.mediaId ?? null;
    const source = getSource(id ?? undefined);
    const title = ref("media-title");
    const next = source ? source.name : "Media";
    if (title.textContent !== next) title.textContent = next;
    const hint = ref("media-hint");
    if (hint.hidden !== !!source) hint.hidden = !!source;
    for (let i = 0; i < FACT_ROWS; i += 1) {
      const entry = source?.facts[i];
      const dt = dts[i];
      const dd = dds[i];
      if (dt.hidden !== !entry) dt.hidden = !entry;
      if (dd.hidden !== !entry) dd.hidden = !entry;
      if (entry) {
        if (dt.textContent !== entry[0]) dt.textContent = entry[0];
        if (dd.textContent !== entry[1]) dd.textContent = entry[1];
      }
    }
  };

  const showTab = () => {
    const clip = current();
    const empty = !clip && tab !== "media";
    const flag = String(empty);
    if (element.dataset.empty !== flag) element.dataset.empty = flag;
    const colourless = clip?.kind === "audio" && tab === "color";
    for (const node of body.querySelectorAll<HTMLElement>("[data-tab]")) {
      const hide = node.dataset.tab !== tab || (colourless && node.dataset.tab === "color");
      const value = String(hide);
      if (node.dataset.tabHidden !== value) node.dataset.tabHidden = value;
    }
    const empties = body.querySelector<HTMLElement>(".inspector-empty")!;
    const text = clip?.kind === "audio" && tab === "color" ? "Audio clips carry no picture to color." : "Select a clip on the timeline to edit it.";
    if (empties.textContent !== text) empties.textContent = text;
    if (colourless && element.dataset.empty !== "true") element.dataset.empty = "true";
  };

  const sync = () => {
    const clip = current();
    if (clip) {
      for (const apply of visibility) apply(clip);
      for (const control of controls) control.sync(clip);
      if (document.activeElement !== textInput && textInput.value !== (clip.textStyle?.content ?? "")) textInput.value = clip.textStyle?.content ?? "";
      const color = clip.textStyle?.color ?? "#ffffff";
      if (colourInput.value !== color && /^#[0-9a-f]{6}$/i.test(color)) colourInput.value = color;
      const blend = transformOf(clip).blendMode;
      if (blendSelect.value !== blend) blendSelect.value = blend;
      if (flipInput.checked !== !!transformOf(clip).flipH) flipInput.checked = !!transformOf(clip).flipH;
      for (const [id, input] of fxToggles) {
        const on = !!clip.effects?.some((e) => e.id === id && e.enabled !== false);
        if (input.checked !== on) input.checked = on;
      }
      const type = clip.transitionIn?.type ?? "";
      if (transSelect.value !== type) transSelect.value = type;
    }
    showTab();
    paintFacts();
  };

  element.querySelector(".seg")!.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-tab]");
    if (!button) return;
    tab = button.dataset.tab!;
    for (const node of element.querySelectorAll<HTMLElement>(".seg > button")) node.classList.toggle("is-active", node === button);
    sync();
  });
  document.addEventListener("formcut-demo:source", (event) => {
    sourceId = (event as CustomEvent<string>).detail;
    const media = element.querySelector<HTMLElement>('.seg [data-tab="media"]')!;
    media.click();
  });
  engine.subscribe((_s, changed) => {
    if (changed === "clip-selection") sourceId = null;
    if (changed === "clips" || changed === "clip-selection" || changed === "timeline") sync();
  });
  onSources(paintFacts);
  sync();
  return element;
}
