import { installFontTools } from "./font-tools";
import { installTracking } from "./tracking";
import type { ProjectEngine } from "../engine/project";
import { defaultTextStyle, defaultTransform, type ClipTransform } from "../engine/types";
import { icon } from "./icons";
import type { MediaBin } from "../engine/media";
import { t } from "../i18n";
import { api } from "../engine/api";
import { sourceTime } from "../engine/timing";
import { activeProfile, onInterfaceMode } from "./interface-mode";
import { text } from "../i18n/text";
import { sampledTransform } from "../engine/keyframes";

const BLEND_MODES = ["Normal", "Multiply", "Screen", "Overlay", "Darken", "Lighten", "Difference", "Add", "Subtract", "Soft Light"];

function selectedTransform(engine: ProjectEngine): ClipTransform {
  const id = engine.snapshot.selectedClipId;
  const found = id ? engine.findClip(id) : null;
  const base = { ...defaultTransform(), ...found?.clip.transform };
  // With keyframes on a property, the number a person needs to see is the one
  // being rendered at the playhead, not the clip's base value. Reading the base
  // here left the fields disagreeing with both the lanes and the picture.
  if (!found?.clip.keyframes?.length) return base;
  const local = Math.max(0, Math.min(found.clip.duration, engine.snapshot.playhead - found.clip.start));
  return { ...base, ...sampledTransform(found.clip, local) };
}

const SLIDE: Record<string, [number, number, number]> = { scale: [0, 400, 1], posX: [-100, 100, 0.5], posY: [-100, 100, 0.5], rotation: [-180, 180, 0.5] };

function propRow(label: string, key: string, value: number, unit: string): string {
  const [min, max, step] = SLIDE[key] ?? [0, 100, 1];
  return `
    <div class="prop-row has-slide">
      <span>${label}</span>
      <span class="num-field"><input data-key="${key}" value="${value}" /><span class="unit">${unit}</span></span>
      <span class="prop-aux">
        <button class="iconbtn" data-kf-step="-1" data-kf-prop="${key}" title="${t("kf.prev")}">${icon("chevL")}</button>
        <button class="iconbtn kf-btn" data-kf="${key}" title="${t("kf.at")}">${icon("diamond")}</button>
        <button class="iconbtn" data-kf-step="1" data-kf-prop="${key}" title="${t("kf.next")}">${icon("chevR")}</button>
      </span>
      <input class="prop-slide" type="range" data-slide="${key}" min="${min}" max="${max}" step="${step}" value="${value}" aria-label="${label}" />
    </div>`;
}

function bareRow(label: string, key: string, value: number, unit: string): string {
  return `
    <div class="prop-row">
      <span>${label}</span>
      <span class="num-field"><input data-key="${key}" value="${value}" /><span class="unit">${unit}</span></span>
      <span class="prop-aux"></span>
    </div>`;
}

export function buildInspectorPane(engine: ProjectEngine, bin: MediaBin): HTMLElement {
  const sel = selectedTransform(engine);
  const el = document.createElement("section");
  el.className = "pane pane-inspector";
  el.dataset.empty = String(!engine.snapshot.selectedClipId);
  el.innerHTML = `
    <div class="inspector-head">
      <div class="seg" data-ref="group">
        <button class="is-active" data-group="video" data-feature="group.video">Video</button><button data-group="audio" data-feature="group.audio">Audio</button><button data-group="effects" data-feature="group.effects">Effects</button>
      </div>
      <button class="select-chip" data-ref="show-all" data-feature="insp.showall" title="${t("insp.showall")}" aria-pressed="false">${icon("sliders")}</button>
    </div>
    <div class="inspector-subtabs">
      <div class="seg" data-ref="subtabs">
        <button class="is-active" data-tab="basic" data-feature="subtab.basic">Basic</button><button data-tab="speed" data-feature="subtab.speed">Speed</button><button data-tab="animation" data-feature="subtab.animation">Animation</button><button data-tab="adjust" data-feature="subtab.adjust">Adjust</button>
      </div>
    </div>
    <div class="inspector-body">
      <div class="inspector-empty" role="status">${t("insp.empty")}</div>
      <div class="section" data-section="transform" data-feature="section.transform">
        <div class="section-head">${t("sec.transform")} ${icon("chevD")}<span class="spacer"></span><button class="iconbtn" data-ref="reset-transform" title="${t("insp.reset")}">${icon("reset")}</button></div>
        ${propRow(t("row.scale"), "scale", sel.scale, "%")}
        ${propRow(t("row.posx"), "posX", sel.posX, "%")}
        ${propRow(t("row.posy"), "posY", sel.posY, "%")}
        ${propRow(t("row.rotation"), "rotation", sel.rotation, "\u00B0")}
        ${bareRow("Width", "width", sel.width, "%")}
        ${bareRow("Height", "height", sel.height, "%")}
      </div>
      <div class="section" data-ref="text-section" hidden>
        <div class="section-head">${t("sec.text")} ${icon("chevD")}</div>
        <div class="prop-row">
          <span>Content</span>
          <span class="num-field text-field"><input type="text" data-xkey="content" value="" /></span>
          <span class="prop-aux"></span>
        </div>
        <div class="prop-row">
          <span>Size</span>
          <span class="num-field"><input data-xkey="size" value="8" /><span class="unit">%</span></span>
          <span class="prop-aux"></span>
        </div>
        <div class="prop-row">
          <span>Color</span>
          <input type="color" class="color-field" data-xkey="color" value="#ffffff" />
          <span class="prop-aux"></span>
        </div>
        <div class="prop-row">
          <span>Bold</span>
          <span></span>
          <button class="toggle is-on" data-ref="bold" aria-label="Bold"></button>
        </div>
        <div class="prop-row">
          <span>Align</span>
          <button class="wide-select" data-ref="align"><span data-ref="align-label">center</span>${icon("chevD")}</button>
          <span class="prop-aux"></span>
        </div>
      </div>
      <div class="section" data-section="timing" data-feature="section.timing">
        <div class="section-head">${t("sec.timing")} ${icon("chevD")}</div>
        <div class="prop-row">
          <span>Speed</span>
          <span class="num-field"><input data-tkey="speed" value="1" /><span class="unit">x</span></span>
          <span class="prop-aux"></span>
        </div>
        <div class="prop-row">
          <span>Fade in</span>
          <span class="num-field"><input data-tkey="fadeIn" value="0" /><span class="unit">s</span></span>
          <span class="prop-aux"></span>
        </div>
        <div class="prop-row">
          <span>Fade out</span>
          <span class="num-field"><input data-tkey="fadeOut" value="0" /><span class="unit">s</span></span>
          <span class="prop-aux"></span>
        </div>
      </div>
      <div class="section" data-section="audio" data-feature="section.audio">
        <div class="prop-row">
          <span>${t("row.audiofx")}</span>
          <select class="mini-select" data-ref="audiofx">
            <option value="">${t("afx.none")}</option>
            <option value="pitch_up">${t("afx.pitchup")}</option>
            <option value="pitch_down">${t("afx.pitchdown")}</option>
            <option value="echo">${t("afx.echo")}</option>
            <option value="radio">${t("afx.radio")}</option>
          </select>
          <span class="prop-aux"></span>
        </div>
        <div class="text-add-hint">${t("afx.note")}</div>
        <div class="prop-row">
          <span>${t("row.mute")}</span>
          <span></span>
          <button class="toggle" data-ref="mute" aria-label="Mute clip"></button>
        </div>
        <div class="prop-row" data-feature="row.reverse">
          <span>${t("row.reverse")}</span>
          <span class="prop-aux" data-ref="reverse-state"></span>
          <button class="toggle" data-ref="reverse" aria-label="Reverse clip"></button>
        </div>
        <div class="prop-row" data-feature="row.crop">
          <span>${t("row.crop")}</span>
          <span></span>
          <button class="toggle" data-ref="crop-mode" aria-label="Crop clip"></button>
        </div>
      </div>
      <div class="section" data-section="blend" data-feature="section.blend">
        <div class="section-head">${t("sec.blend")} ${icon("chevD")}</div>
        ${propRow(t("row.opacity"), "opacity", sel.opacity, "%")}
        <div class="prop-row">
          <span>${t("row.mode")}</span>
          <button class="wide-select" data-ref="blend" aria-haspopup="menu" aria-expanded="false"><span data-ref="blend-label" data-mode="${sel.blendMode}">${sel.blendMode}</span>${icon("chevD")}</button>
          <span class="prop-aux"></span>
        </div>
        <div class="prop-row">
          <span>${t("row.flip")}</span>
          <span></span>
          <button class="toggle${sel.flipH ? " is-on" : ""}" data-ref="flip" aria-label="Flip horizontal"></button>
        </div>
        <div class="prop-row" data-feature="row.flipv">
          <span>${t("row.flipv")}</span>
          <span></span>
          <button class="toggle${sel.flipV ? " is-on" : ""}" data-ref="flipv" aria-label="Flip vertical"></button>
        </div>
      </div>
      <div class="section" data-section="track" data-feature="section.track">
        <div class="section-head">${t("sec.track")} ${icon("chevD")}</div>
        <button class="tool-chip" data-ref="track-btn">${icon("search")}${t("track.btn")}</button>
        <div class="text-add-hint" data-ref="track-hint">${t("track.hint")}</div>
      </div>
      <div class="section" data-section="mask" data-feature="section.mask">
        <div class="section-head">${t("sec.mask")} ${icon("chevD")}</div>
        <div class="prop-row">
          <span>${t("row.maskshape")}</span>
          <select class="mini-select" data-ref="mask-shape">
            <option value="">${t("mask.none")}</option>
            <option value="rect">${t("mask.rect")}</option>
            <option value="ellipse">${t("mask.ellipse")}</option>
          </select>
          <span class="prop-aux"></span>
        </div>
        ${propRow(t("row.maskx"), "maskX", 10, "%")}
        ${propRow(t("row.masky"), "maskY", 10, "%")}
        ${propRow(t("row.maskw"), "maskW", 80, "%")}
        ${propRow(t("row.maskh"), "maskH", 80, "%")}
        ${propRow(t("row.feather"), "maskF", 0, "%")}
        <div class="text-add-hint">${t("mask.note")}</div>
      </div>
      <div class="section" data-section="key" data-feature="section.key">
        <div class="section-head">${t("sec.key")} ${icon("chevD")}</div>
        <div class="prop-row">
          <span>${t("row.screencolor")}</span>
          <input type="color" class="color-field" data-ref="key-color" value="#00d000" />
          <span class="prop-aux"><button class="toggle" data-ref="key-on" aria-label="Chroma key"></button></span>
        </div>
        ${propRow(t("row.similarity"), "keySim", 25, "%")}
        ${propRow(t("row.keyblend"), "keyBlend", 5, "%")}
        <div class="text-add-hint">${t("key.note")}</div>
      </div>
    </div>`;

  const TAB_VIEWS: Record<string, { sections: string[]; pages: string[] }> = {
    "video:basic": { sections: ["transform", "text", "blend"], pages: [] },
    "video:speed": { sections: ["timing"], pages: ["speed"] },
    "video:animation": { sections: ["track"], pages: ["motion"] },
    "video:adjust": { sections: ["mask", "key"], pages: ["cutout", "advanced"] },
    audio: { sections: ["audio"], pages: ["audio"] },
    effects: { sections: [], pages: ["effects", "transition"] },
  };
  const groupSeg = el.querySelector<HTMLElement>('[data-ref="group"]')!;
  const subtabSeg = el.querySelector<HTMLElement>('[data-ref="subtabs"]')!;
  const inspectorBody = el.querySelector<HTMLElement>(".inspector-body")!;
  let activeGroup = "video";
  let activeSubtab = "basic";
  let showAll = false;
  const everything = {
    sections: ["transform", "text", "blend", "timing", "track", "mask", "key", "audio"],
    pages: ["speed", "motion", "effects", "audio", "transition", "cutout", "advanced"],
  };
  const showAllChip = el.querySelector<HTMLButtonElement>('[data-ref="show-all"]')!;
  showAllChip.addEventListener("click", () => {
    showAll = !showAll;
    showAllChip.setAttribute("aria-pressed", String(showAll));
    applyTab();
  });
  const applyTab = () => {
    const view = showAll ? everything : TAB_VIEWS[activeGroup === "video" ? `video:${activeSubtab}` : activeGroup];
    for (const button of groupSeg.querySelectorAll<HTMLButtonElement>("button[data-group]")) button.classList.toggle("is-active", button.dataset.group === activeGroup);
    for (const button of subtabSeg.querySelectorAll<HTMLButtonElement>("button[data-tab]")) {
      button.classList.toggle("is-active", activeGroup === "video" && button.dataset.tab === activeSubtab);
      if (button.disabled !== (activeGroup !== "video")) button.disabled = activeGroup !== "video";
    }
    for (const node of inspectorBody.querySelectorAll<HTMLElement>(":scope > [data-section], :scope > [data-ref='text-section'], :scope > .creator-panel")) {
      const creator = node.classList.contains("creator-panel");
      const shown = creator ? view.pages.length > 0 : view.sections.includes(node.dataset.section ?? "text");
      const hidden = String(!shown);
      if (node.dataset.tabHidden !== hidden) node.dataset.tabHidden = hidden;
    }
    const page = inspectorBody.querySelector<HTMLSelectElement>(".creator-panel select[data-page]");
    if (page && view.pages.length) {
      for (const option of page.options) {
        const outside = !view.pages.includes(option.value) || option.dataset.featureOff === "true";
        if (option.hidden !== outside) option.hidden = outside;
      }
      if (!view.pages.includes(page.value)) {
        page.value = view.pages[0];
        page.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }
  };
  groupSeg.addEventListener("click", (ev) => {
    const hit = (ev.target as HTMLElement).closest<HTMLButtonElement>("button[data-group]");
    if (!hit) return;
    activeGroup = hit.dataset.group!;
    applyTab();
  });
  subtabSeg.addEventListener("click", (ev) => {
    const hit = (ev.target as HTMLElement).closest<HTMLButtonElement>("button[data-tab]");
    if (!hit || hit.disabled) return;
    activeSubtab = hit.dataset.tab!;
    applyTab();
  });
  applyTab();
  const flip = el.querySelector<HTMLElement>('[data-ref="flip"]')!;
  const blendBtn = el.querySelector<HTMLElement>('[data-ref="blend"]')!;
  const blendLabel = el.querySelector<HTMLElement>('[data-ref="blend-label"]')!;
  const inputs = new Map<string, HTMLInputElement>();
  for (const input of el.querySelectorAll<HTMLInputElement>("input[data-key]")) {
    inputs.set(input.dataset.key!, input);
  }
  const sliders = new Map<string, HTMLInputElement>();
  for (const slider of el.querySelectorAll<HTMLInputElement>("input[data-slide]")) {
    sliders.set(slider.dataset.slide!, slider);
  }

  const patchSelected = (patch: Partial<ClipTransform>) => {
    const clipId = engine.snapshot.selectedClipId;
    if (clipId) engine.dispatch("clip.transform", { clipId, patch });
  };

  const textSection = el.querySelector<HTMLElement>('[data-ref="text-section"]')!;
  const boldBtn = el.querySelector<HTMLElement>('[data-ref="bold"]')!;
  const alignBtn = el.querySelector<HTMLElement>('[data-ref="align"]')!;
  const alignLabel = el.querySelector<HTMLElement>('[data-ref="align-label"]')!;
  const ALIGNS = ["left", "center", "right"] as const;
  const selectedTextClip = () => {
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id) : null;
    return found && found.clip.kind === "text" ? found.clip : null;
  };
  const patchText = (patch: Record<string, unknown>) => {
    const clip = selectedTextClip();
    if (clip) engine.dispatch("clip.text", { clipId: clip.id, patch });
  };
  boldBtn.addEventListener("click", () => {
    patchText({ bold: boldBtn.classList.toggle("is-on") });
  });
  alignBtn.addEventListener("click", () => {
    const current = alignLabel.textContent ?? "center";
    const next = ALIGNS[(ALIGNS.indexOf(current as (typeof ALIGNS)[number]) + 1) % ALIGNS.length];
    alignLabel.textContent = next;
    patchText({ align: next });
  });

  el.addEventListener("input", (ev) => {
    const slider = ev.target as HTMLInputElement;
    const key = slider.dataset.slide;
    if (!key) return;
    const value = Number(slider.value);
    if (Number.isNaN(value)) return;
    const field = inputs.get(key);
    if (field && field.value !== slider.value) field.value = slider.value;
    patchSelected({ [key]: value });
  });
  el.addEventListener("change", (ev) => {
    const input = ev.target as HTMLInputElement;
    if (input.dataset.slide) return;
    if (input.dataset.xkey) {
      const key = input.dataset.xkey;
      if (key === "content") patchText({ content: input.value });
      else if (key === "size") {
        const value = Number(input.value);
        if (!Number.isNaN(value)) patchText({ size: Math.min(50, Math.max(1, value)) });
      } else if (key === "color") patchText({ color: input.value });
      return;
    }
    if (input.dataset.tkey) {
      const clipId = engine.snapshot.selectedClipId;
      const value = Number(input.value);
      if (clipId && !Number.isNaN(value)) {
        engine.dispatch("clip.timing", { clipId, [input.dataset.tkey]: value });
      }
      return;
    }
    const key = input.dataset.key;
    if (!key) return;
    const value = Number(input.value);
    if (!Number.isNaN(value)) patchSelected({ [key]: value });
  });
  flip.addEventListener("click", () => {
    const on = flip.classList.toggle("is-on");
    patchSelected({ flipH: on });
  });
  const flipV = el.querySelector<HTMLElement>('[data-ref="flipv"]')!;
  flipV.addEventListener("click", () => {
    const on = flipV.classList.toggle("is-on");
    patchSelected({ flipV: on });
  });
  const blendMenu = document.createElement("div"); blendMenu.className = "dropdown"; blendMenu.hidden = true; blendMenu.setAttribute("role", "menu");
  for (const mode of BLEND_MODES) {
    const item = document.createElement("button"); item.className = "dropdown-item"; item.dataset.mode = mode; item.textContent = text(mode); item.setAttribute("role", "menuitemradio");
    item.addEventListener("click", () => { blendMenu.hidden = true; blendBtn.setAttribute("aria-expanded", "false"); blendLabel.dataset.mode = mode; blendLabel.textContent = text(mode); patchSelected({ blendMode: mode }); });
    blendMenu.append(item);
  }
  document.body.append(blendMenu);
  blendBtn.addEventListener("click", () => {
    const box = blendBtn.getBoundingClientRect(); blendMenu.style.left = `${box.left}px`; blendMenu.style.top = `${box.bottom + 4}px`; blendMenu.style.minWidth = `${box.width}px`;
    for (const item of blendMenu.querySelectorAll<HTMLElement>("[data-mode]")) item.setAttribute("aria-pressed", String(item.dataset.mode === (blendLabel.dataset.mode ?? "Normal")));
    blendMenu.hidden = !blendMenu.hidden; blendBtn.setAttribute("aria-expanded", String(!blendMenu.hidden));
  });
  document.addEventListener("pointerdown", (event) => { if (!blendMenu.hidden && !blendMenu.contains(event.target as Node) && !blendBtn.contains(event.target as Node)) { blendMenu.hidden = true; blendBtn.setAttribute("aria-expanded", "false"); } }, true);
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && !blendMenu.hidden) { blendMenu.hidden = true; blendBtn.setAttribute("aria-expanded", "false"); } });

  el.querySelector('[data-ref="mute"]')!.addEventListener("click", () => {
    const state = engine.snapshot;
    const found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    if (!found) return;
    engine.dispatch("clip.mute", { clipId: found.clip.id, muted: !found.clip.muted });
  });

  const reverseState = el.querySelector<HTMLElement>('[data-ref="reverse-state"]')!;
  el.querySelector('[data-ref="crop-mode"]')!.addEventListener("click", () => {
    const preview = document.querySelector<HTMLElement>(".stage");
    if (!preview) return;
    const on = preview.dataset.crop === "on";
    if (on) delete preview.dataset.crop; else preview.dataset.crop = "on";
    el.querySelector('[data-ref="crop-mode"]')!.classList.toggle("is-on", !on);
    preview.dispatchEvent(new CustomEvent("formcut:crop-mode"));
  });
  el.querySelector('[data-ref="reverse"]')!.addEventListener("click", () => void (async () => {
    const state = engine.snapshot;
    const found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    const clip = found?.clip;
    if (!clip || clip.kind !== "video" || !clip.mediaId) return;
    const item = bin.find(clip.mediaId);
    const total = item?.duration ?? 0;
    if (!total) return;
    const span = sourceTime(clip, clip.duration) - (clip.sourceIn ?? 0);
    const flipped = Math.max(0, Math.round((total - (clip.sourceIn ?? 0) - span) * 100) / 100);
    if (!clip.reversed) {
      reverseState.textContent = t("row.reverse.preparing");
      const reply = await api(`/api/media/${clip.mediaId}/reverse`, {});
      if (reply.job_id) {
        for (let waited = 0; waited < 600; waited += 1) {
          const status = await fetch(`/api/jobs/${reply.job_id}`).then((r) => r.json());
          if (status.status === "done") break;
          if (status.status === "error" || status.status === "failed") { reverseState.textContent = t("row.reverse.failed"); return; }
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      }
      reverseState.textContent = "";
    }
    if (!engine.findClip(clip.id)) return;
    engine.dispatch("clip.creator", { clipId: clip.id, patch: { reversed: !clip.reversed || undefined, sourceIn: flipped } });
  })().catch(() => { reverseState.textContent = t("row.reverse.failed"); }));

  el.addEventListener("contextmenu", (ev) => {
    const kfBtn = (ev.target as HTMLElement).closest<HTMLElement>(".kf-btn");
    if (!kfBtn) return;
    ev.preventDefault();
    const state = engine.snapshot;
    const found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    if (!found) return;
    const local = Math.round((state.playhead - found.clip.start) * 100) / 100;
    engine.dispatch("clip.interp", { clipId: found.clip.id, t: local });
  });

  el.addEventListener("click", (ev) => {
    const stepBtn = (ev.target as HTMLElement).closest<HTMLElement>("[data-kf-step]");
    if (stepBtn) {
      const state = engine.snapshot;
      const found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
      if (!found) return;
      const prop = stepBtn.dataset.kfProp as "posX" | "posY" | "scale" | "rotation" | "opacity";
      const times = (found.clip.keyframes ?? []).filter((k) => k.props[prop] !== undefined).map((k) => found.clip.start + k.t);
      const destination = stepBtn.dataset.kfStep === "1"
        ? Math.min(...times.filter((at) => at > state.playhead + 0.01))
        : Math.max(...times.filter((at) => at < state.playhead - 0.01));
      if (Number.isFinite(destination)) engine.dispatch("transport.seek", destination);
      return;
    }
    if ((ev.target as HTMLElement).closest('[data-ref="reset-transform"]')) {
      const clipId = engine.snapshot.selectedClipId;
      if (clipId) engine.dispatch("clip.transform", { clipId, patch: defaultTransform() });
      return;
    }
    const kfBtn = (ev.target as HTMLElement).closest<HTMLElement>(".kf-btn");
    if (!kfBtn) return;
    const prop = kfBtn.dataset.kf as
      | "posX" | "posY" | "scale" | "rotation" | "opacity";
    if (!["posX", "posY", "scale", "rotation", "opacity"].includes(prop)) return;
    const state = engine.snapshot;
    const found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    if (!found) return;
    const local = Math.round((state.playhead - found.clip.start) * 100) / 100;
    if (local < 0 || local > found.clip.duration) return;
    const existing = (found.clip.keyframes ?? []).some(
      (k) => Math.abs(k.t - local) < 0.02 && k.props[prop] !== undefined,
    );
    if (existing) {
      engine.dispatch("clip.keyframe", { clipId: found.clip.id, t: local, remove: prop });
      kfBtn.classList.remove("is-accent");
    } else {
      const value = Number(inputs.get(prop)?.value ?? NaN);
      if (Number.isNaN(value)) return;
      engine.dispatch("clip.keyframe", { clipId: found.clip.id, t: local, set: { [prop]: value } });
      kfBtn.classList.add("is-accent");
    }
  });

  installTracking(el, engine);

  const audioFxSel = el.querySelector<HTMLSelectElement>('[data-ref="audiofx"]')!;
  audioFxSel.addEventListener("change", () => {
    const clipId = engine.snapshot.selectedClipId;
    if (!clipId) return;
    engine.dispatch("clip.audiofx", { clipId, fx: audioFxSel.value || null });
  });

  const maskShape = el.querySelector<HTMLSelectElement>('[data-ref="mask-shape"]')!;
  const MASK_FIELDS = ["maskX", "maskY", "maskW", "maskH", "maskF"] as const;
  const dispatchMask = () => {
    const state = engine.snapshot;
    if (!state.selectedClipId) return;
    const shape = maskShape.value as "" | "rect" | "ellipse";
    const num = (ref: string, fb: number) => Number(inputs.get(ref)?.value ?? fb) || fb;
    engine.dispatch("clip.mask", {
      clipId: state.selectedClipId,
      mask: shape
        ? { shape, x: num("maskX", 10), y: num("maskY", 10), w: num("maskW", 80), h: num("maskH", 80), feather: num("maskF", 0) }
        : null,
    });
  };
  maskShape.addEventListener("change", dispatchMask);
  for (const ref of MASK_FIELDS) {
    inputs.get(ref)?.addEventListener("change", () => {
      if (maskShape.value) dispatchMask();
    });
  }

  const keyOn = el.querySelector<HTMLElement>('[data-ref="key-on"]')!;
  const keyColor = el.querySelector<HTMLInputElement>('[data-ref="key-color"]')!;
  const dispatchKey = (enabled: boolean) => {
    const state = engine.snapshot;
    if (!state.selectedClipId) return;
    const sim = Number(inputs.get("keySim")?.value ?? 25) / 100;
    const kb = Number(inputs.get("keyBlend")?.value ?? 5) / 100;
    engine.dispatch("clip.key", {
      clipId: state.selectedClipId,
      key: enabled ? { color: keyColor.value, similarity: sim || 0.25, blend: kb } : null,
    });
    keyOn.classList.toggle("is-on", enabled);
  };
  keyOn.addEventListener("click", () => dispatchKey(!keyOn.classList.contains("is-on")));
  keyColor.addEventListener("change", () => {
    if (keyOn.classList.contains("is-on")) dispatchKey(true);
  });
  for (const ref of ["keySim", "keyBlend"]) {
    inputs.get(ref)?.addEventListener("change", () => {
      if (keyOn.classList.contains("is-on")) dispatchKey(true);
    });
  }

  const refill = () => {
    const empty = String(!engine.snapshot.selectedClipId);
    if (el.dataset.empty !== empty) el.dataset.empty = empty;
    applyTab();
    const t = selectedTransform(engine);
    for (const [key, input] of inputs) {
      if (key === "keySim" || key === "keyBlend" || key.startsWith("mask")) continue;
      const next = String(t[key as keyof ClipTransform]);
      if (document.activeElement !== input && input.value !== next) input.value = next;
      const slider = sliders.get(key);
      if (slider && document.activeElement !== slider && slider.value !== next) slider.value = next;
    }
    const id = engine.snapshot.selectedClipId;
    const clip = id ? engine.findClip(id)?.clip : undefined;
    const wantFx = clip?.audioFx ?? "";
    if (document.activeElement !== audioFxSel && audioFxSel.value !== wantFx) audioFxSel.value = wantFx;
    const wantShape = clip?.mask?.shape ?? "";
    if (document.activeElement !== maskShape && maskShape.value !== wantShape) maskShape.value = wantShape;
    if (clip?.mask) {
      const mv: Record<string, number> = { maskX: clip.mask.x, maskY: clip.mask.y, maskW: clip.mask.w, maskH: clip.mask.h, maskF: clip.mask.feather };
      for (const [ref, val] of Object.entries(mv)) {
        const input = inputs.get(ref);
        const next = String(val);
        if (input && document.activeElement !== input && input.value !== next) input.value = next;
      }
    }
    keyOn.classList.toggle("is-on", Boolean(clip?.key));
    el.querySelector('[data-ref="mute"]')!.classList.toggle("is-on", Boolean(clip?.muted));
    el.querySelector('[data-ref="reverse"]')!.classList.toggle("is-on", Boolean(clip?.reversed));
    if (clip?.key) {
      if (document.activeElement !== keyColor && keyColor.value !== clip.key.color) {
        keyColor.value = clip.key.color;
      }
      const simInput = inputs.get("keySim");
      const next = String(Math.round(clip.key.similarity * 100));
      if (simInput && document.activeElement !== simInput && simInput.value !== next) {
        simInput.value = next;
      }
      const blInput = inputs.get("keyBlend");
      const bNext = String(Math.round(clip.key.blend * 100));
      if (blInput && document.activeElement !== blInput && blInput.value !== bNext) {
        blInput.value = bNext;
      }
    }
    for (const input of el.querySelectorAll<HTMLInputElement>("input[data-tkey]")) {
      const key = input.dataset.tkey as "speed" | "fadeIn" | "fadeOut";
      const next = String(clip?.[key] ?? (key === "speed" ? 1 : 0));
      if (document.activeElement !== input && input.value !== next) input.value = next;
    }
    const isText = clip?.kind === "text";
    if (textSection.hidden === isText) textSection.hidden = !isText;
    if (isText && clip) {
      const ts = { ...defaultTextStyle(clip.label), ...clip.textStyle };
      for (const input of el.querySelectorAll<HTMLInputElement>("input[data-xkey]")) {
        const key = input.dataset.xkey as "content" | "size" | "color";
        const next = String(ts[key]);
        if (document.activeElement !== input && input.value !== next) input.value = next;
      }
      boldBtn.classList.toggle("is-on", ts.bold);
      if (alignLabel.textContent !== ts.align) alignLabel.textContent = ts.align;
    }
    flip.classList.toggle("is-on", t.flipH);
    flipV.classList.toggle("is-on", Boolean(t.flipV));
    const blendMode = t.blendMode ?? "Normal";
    if (blendLabel.dataset.mode !== blendMode) { blendLabel.dataset.mode = blendMode; blendLabel.textContent = text(blendMode); }
  };
  engine.subscribe((_state, changed) => {
    if (changed === "clip-selection" || changed === "clips") refill();
    else if (changed === "playhead") {
      // The fields show the animated value, so they have to follow the
      // playhead. Without keyframes nothing would change, so the work is
      // skipped rather than run sixty times a second for no reason.
      const id = engine.snapshot.selectedClipId;
      const clip = id ? engine.findClip(id)?.clip : undefined;
      if (clip?.keyframes?.length) refill();
    }
  });
  installFontTools(el, engine);
  const sections = [...el.querySelectorAll<HTMLElement>("[data-section]")];
  const applyEasyViews = () => {
    const profile = activeProfile();
    const views = profile.inspector?.views;
    if (!views || profile.id === "advanced") {
      for (const section of sections) section.classList.remove("easy-hidden");
      el.classList.remove("easy-column");
      return;
    }
    const state = engine.snapshot;
    const found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    const kind = found?.clip.kind ?? "none";
    let shown: string[];
    if (kind === "audio") shown = views["audio"] ?? ["audio"];
    else if (kind === "text") shown = ["transform", "timing", "blend"];
    else {
      shown = (profile.inspector.subtabs ?? []).flatMap((subtab) => views[`video:${subtab}`] ?? []);
      if (!shown.length) shown = ["transform", "timing"];
    }
    const wanted = new Set(shown.filter((name) => !name.includes(":")));
    el.classList.add("easy-column");
    for (const section of sections) section.classList.toggle("easy-hidden", !wanted.has(section.dataset.section!));
  };
  onInterfaceMode(applyEasyViews);
  engine.subscribe((_state, event) => { if (event === "clip-selection") applyEasyViews(); });
  applyEasyViews();

  return el;
}
