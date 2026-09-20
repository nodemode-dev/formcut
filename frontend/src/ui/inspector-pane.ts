import { installFontTools } from "./font-tools";
import { installTracking } from "./tracking";
import type { ProjectEngine } from "../engine/project";
import { defaultTextStyle, defaultTransform, MASK_SHAPES, type Clip, type ClipTransform, type MaskShape } from "../engine/types";
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
        <button class="is-active" data-tab="basic" data-feature="subtab.basic">Basic</button><button data-tab="speed" data-feature="subtab.speed">Speed</button><button data-tab="animation" data-feature="subtab.animation">Animation</button><button data-tab="adjust" data-feature="subtab.adjust">${t("subtab.adjust")}</button><button data-tab="repair" data-feature="subtab.repair">${t("subtab.repair")}</button>
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
        <div class="prop-row"><span>${t("title.weight")}</span><span class="num-field"><input data-xkey="weight" value="" placeholder="400" /></span><span class="prop-aux"></span></div>
        <div class="prop-row"><span>${t("title.italic")}</span><span></span><button class="toggle" data-ref="italic" aria-label="Italic"></button></div>
        <div class="prop-row"><span>${t("title.outline")}</span><input type="color" class="color-field" data-xkey="outlineColor" value="#000000" /><span class="num-field"><input data-xkey="outlineWidth" value="" placeholder="3" /></span></div>
        <div class="prop-row"><span>${t("title.shadow")}</span><input type="color" class="color-field" data-xkey="shadowColor" value="#000000" /><span class="num-field"><input data-xkey="shadowBlur" value="" placeholder="0" /></span></div>
        <div class="prop-row"><span>${t("title.shadowoffset")}</span><span class="num-field"><input data-xkey="shadowX" value="" placeholder="0" /></span><span class="num-field"><input data-xkey="shadowY" value="" placeholder="0" /></span></div>
        <div class="prop-row"><span>${t("title.plate")}</span><input type="color" class="color-field" data-xkey="plateColor" value="#101416" /><span class="num-field"><input data-xkey="plateOpacity" value="" placeholder="0.8" /></span></div>
        <div class="prop-row"><span>${t("title.platebox")}</span><span class="num-field"><input data-xkey="platePadding" value="" placeholder="12" /></span><span class="num-field"><input data-xkey="plateRadius" value="" placeholder="8" /></span></div>
        <div class="prop-row"><span>${t("title.lineheight")}</span><span class="num-field"><input data-xkey="lineHeight" value="" placeholder="1.2" /></span><span class="prop-aux"></span></div>
        <div class="prop-row"><span>${t("title.tracking")}</span><span class="num-field"><input data-xkey="letterSpacing" value="" placeholder="0" /></span><span class="prop-aux"></span></div>
        <div class="prop-row"><span>${t("title.wrap")}</span><span class="num-field"><input data-xkey="wrapWidth" value="" placeholder="100" /><span class="unit">%</span></span><span class="prop-aux"></span></div>
        <div class="prop-row"><span>${t("title.opacity")}</span><span class="num-field"><input data-xkey="textOpacity" value="" placeholder="1" /></span><span class="prop-aux"></span></div>
      </div>
      <div class="section" data-section="timing" data-feature="section.timing">
        <div class="section-head">${t("sec.timing")} ${icon("chevD")}</div>
        <div class="prop-row">
          <span>Speed</span>
          <span class="num-field"><input data-tkey="speed" value="1" /><span class="unit">x</span></span>
          <span class="prop-aux"></span>
        </div>
        <div class="prop-row">
          <span>${t("time.smooth")}</span>
          <button class="toggle" data-ref="smooth-slow" aria-pressed="false" aria-label="${t("time.smooth")}"></button>
          <span class="prop-aux">${t("time.smooth.hint")}</span>
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
            ${MASK_SHAPES.map((shape) => `<option value="${shape}">${t(`mask.${shape}`)}</option>`).join("")}
          </select>
          <span class="prop-aux"></span>
        </div>
        <div class="prop-row" data-mask-pen>
          <span>${t("mask.pen")}</span>
          <button class="tool-chip" data-ref="mask-draw" aria-pressed="false">${icon("pointer")}${t("mask.draw")}</button>
          <span class="prop-aux" data-ref="mask-points"></span>
        </div>
        <div class="prop-row">
          <span>${t("mask.auto")}</span>
          <button class="tool-chip" data-ref="mask-lasso" aria-pressed="false">${t("mask.lasso")}</button>
          <button class="tool-chip is-primary" data-ref="mask-subject">${t("mask.subject")}</button>
        </div>
        <p class="prop-note" data-ref="mask-pen-help" hidden>${t("mask.penhelp")}</p>
        <div class="prop-row">
          <span>${t("mask.track")}</span>
          <button class="tool-chip is-primary" data-ref="mask-track">${t("mask.trackgo")}</button>
          <span class="prop-aux" data-ref="mask-track-state"></span>
        </div>
        <p class="prop-note" data-ref="mask-auto-note"></p>
        <div class="prop-row">
          <span>${t("mask.brush")}</span>
          <button class="tool-chip" data-ref="brush-keep" aria-pressed="false">${t("mask.keep")}</button>
          <button class="tool-chip" data-ref="brush-erase" aria-pressed="false">${t("mask.erase")}</button>
          <button class="iconbtn" data-ref="brush-clear" title="${t("mask.clearstrokes")}">${icon("reset")}</button>
        </div>
        <div class="prop-row">
          <span>${t("mask.brushsize")}</span>
          <input type="range" class="slider" data-ref="brush-size" min="1" max="30" step="1" value="8" />
          <span class="prop-aux" data-ref="brush-size-value">8</span>
        </div>
        ${propRow(t("row.maskangle"), "maskA", 0, "°")}
        ${propRow(t("row.maskx"), "maskX", 10, "%")}
        ${propRow(t("row.masky"), "maskY", 10, "%")}
        ${propRow(t("row.maskw"), "maskW", 80, "%")}
        ${propRow(t("row.maskh"), "maskH", 80, "%")}
        ${propRow(t("row.feather"), "maskF", 0, "%")}
        <div class="text-add-hint">${t("mask.note")}</div>
      </div>
      <div class="section" data-section="removebg" data-feature="section.removebg">
        <div class="section-head">${t("bg.title")} ${icon("chevD")}</div>
        <!-- A cutout is three questions in order: is the model here, what did
             it find, and is that the thing you meant. The controls used to be
             a flat pile that answered none of them. -->
        <ol class="cut-steps" data-ref="cut-steps">
          <li class="cut-step" data-step="model">
            <span class="cut-num">1</span>
            <div class="cut-body">
              <strong>${t("cut.step1")}</strong>
              <span class="cut-note" data-ref="cut-model-state">${t("bg.checking")}</span>
              <button class="tool-chip" data-ref="cut-model-get" hidden>${t("bg.download")}</button>
            </div>
          </li>
          <li class="cut-step" data-step="run">
            <span class="cut-num">2</span>
            <div class="cut-body">
              <strong>${t("cut.step2")}</strong>
              <span class="cut-note" data-ref="cut-run-state">${t("cut.notrun")}</span>
              <button class="tool-chip is-primary" data-ref="cut-run">${t("cut.remove")}</button>
            </div>
          </li>
          <li class="cut-step" data-step="pick">
            <span class="cut-num">3</span>
            <div class="cut-body">
              <strong>${t("cut.step3")}</strong>
              <span class="cut-note" data-ref="cut-pick-state">${t("cut.pickhint")}</span>
              <button class="tool-chip" data-ref="cut-pick" aria-pressed="false">${t("cut.pick")}</button>
              <button class="tool-chip" data-ref="cut-clear-point" hidden>${t("cut.whole")}</button>
            </div>
          </li>
        </ol>
        <div class="prop-row">
          <span>${t("bg.mode")}</span>
          <select class="mini-select" data-ref="bg-mode">
            <option value="off" selected>${t("bg.off")}</option>
            <option value="auto">${t("bg.auto")}</option>
            <option value="brush">${t("bg.brush")}</option>
            <option value="chroma">${t("bg.chroma")}</option>
          </select>
          <span class="prop-aux" data-ref="bg-progress"></span>
        </div>
        <div class="prop-row" data-ref="bg-model-row">
          <span>${t("bg.model")}</span>
          <span class="prop-aux" data-ref="bg-model-state">${t("bg.checking")}</span>
          <button class="tool-chip" data-ref="bg-model-get" hidden>${t("bg.download")}</button>
        </div>
        <div class="prop-row">
          <span>${t("bg.feather")}</span>
          <input type="range" class="slider" data-ref="bg-feather" min="1" max="60" step="1" value="10" />
          <span class="prop-aux" data-ref="bg-feather-value">10</span>
        </div>
        <div class="prop-row">
          <span>${t("bg.brushsize")}</span>
          <input type="range" class="slider" data-ref="bg-brush" min="1" max="20" step="1" value="4" />
          <span class="prop-aux" data-ref="bg-brush-value">4</span>
        </div>
      </div>
      <div class="section" data-section="rhythm" data-feature="section.rhythm">
        <div class="section-head">${t("beat.title")} ${icon("chevD")}</div>
        <div class="prop-row">
          <span>${t("frame.auto")}</span>
          <select class="mini-select" data-ref="reframe-aspect">
            <option value="0.5625">9:16</option>
            <option value="1">1:1</option>
            <option value="0.8">4:5</option>
          </select>
          <button class="tool-chip" data-ref="reframe-go">${t("frame.apply")}</button>
        </div>
        <div class="prop-row">
          <button class="tool-chip" data-ref="filler-find">${t("filler.find")}</button>
          <button class="tool-chip is-primary" data-ref="filler-cut" hidden>${t("filler.cut")}</button>
          <span class="prop-aux" data-ref="filler-state"></span>
        </div>
        <div class="prop-row">
          <button class="tool-chip" data-ref="beat-find">${t("beat.find")}</button>
          <span class="prop-aux" data-ref="beat-state"></span>
        </div>
        <div class="prop-row">
          <span>${t("beat.duck")}</span>
          <input type="range" class="slider" data-ref="duck-depth" min="5" max="80" step="5" value="25">
          <button class="tool-chip is-primary" data-ref="duck-apply">${t("beat.apply")}</button>
        </div>
      </div>
      <div class="section" data-section="scenes" data-feature="section.scenes">
        <div class="section-head">${t("scene.title")} ${icon("chevD")}</div>
        <div class="prop-row">
          <span>${t("scene.sensitivity")}</span>
          <input type="range" class="slider" data-ref="scene-sens" min="0" max="100" step="5" value="50" />
          <span class="prop-aux" data-ref="scene-sens-value">50</span>
        </div>
        <div class="prop-row">
          <button class="tool-chip" data-ref="scene-find">${t("scene.find")}</button>
          <button class="tool-chip is-primary" data-ref="scene-split" hidden>${t("scene.split")}</button>
          <span class="prop-aux" data-ref="scene-state"></span>
        </div>
      </div>
      <div class="section" data-section="canvas" data-feature="section.canvas">
        <div class="section-head">${t("canvas.title")} ${icon("chevD")}</div>
        <div class="prop-row">
          <span>${t("canvas.kind")}</span>
          <select class="mini-select" data-ref="canvas-kind">
            <option value="">${t("canvas.none")}</option>
            <option value="colour">${t("canvas.colour")}</option>
            <option value="gradient">${t("canvas.gradient")}</option>
            <option value="blur">${t("canvas.blur")}</option>
          </select>
          <span class="prop-aux"></span>
        </div>
        <div class="prop-row" data-ref="canvas-colours" hidden>
          <span>${t("canvas.colours")}</span>
          <input type="color" data-ref="canvas-from" value="#101418">
          <input type="color" data-ref="canvas-to" value="#2b3440">
        </div>
        <div class="prop-row" data-ref="canvas-amount-row" hidden>
          <span>${t("canvas.amount")}</span>
          <input type="range" class="slider" data-ref="canvas-amount" min="5" max="120" step="5" value="40">
          <span class="prop-aux" data-ref="canvas-amount-value">40</span>
        </div>
      </div>
      <div class="section" data-section="repair" data-feature="section.repair">
        <div class="section-head">${t("rep.title")} ${icon("chevD")}</div>
        <div class="prop-row">
          <span>${t("rep.stabilise")}</span>
          <button class="toggle" data-ref="rep-stab" aria-pressed="false" aria-label="${t("rep.stabilise")}"></button>
          <span class="prop-aux" data-ref="rep-stab-state"></span>
        </div>
        <div class="prop-row" data-ref="rep-stab-rows" hidden>
          <span>${t("rep.smoothing")}</span>
          <input type="range" class="slider" data-ref="rep-smooth" min="0" max="100" step="5" value="60" />
          <span class="prop-aux" data-ref="rep-smooth-value">60</span>
        </div>
        <div class="prop-row" data-ref="rep-crop-rows" hidden>
          <span>${t("rep.crop")}</span>
          <input type="range" class="slider" data-ref="rep-crop" min="0" max="30" step="1" value="6" />
          <span class="prop-aux" data-ref="rep-crop-value">6%</span>
        </div>
        <div class="prop-row">
          <span>${t("rep.deflicker")}</span>
          <button class="toggle" data-ref="rep-flick" aria-pressed="false" aria-label="${t("rep.deflicker")}"></button>
          <input type="range" class="slider" data-ref="rep-flick-amt" min="0" max="100" step="5" value="80" />
        </div>
        <div class="prop-row">
          <span>${t("rep.denoise")}</span>
          <button class="toggle" data-ref="rep-noise" aria-pressed="false" aria-label="${t("rep.denoise")}"></button>
          <input type="range" class="slider" data-ref="rep-noise-amt" min="0" max="100" step="5" value="50" />
        </div>
        <div class="prop-row">
          <span>${t("rep.match")}</span>
          <button class="tool-chip" data-ref="rep-match-sample">${t("rep.sample")}</button>
          <span class="prop-aux" data-ref="rep-match-state"></span>
        </div>
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
    "video:basic": { sections: ["transform", "text", "blend", "canvas"], pages: [] },
    "video:speed": { sections: ["timing"], pages: ["speed"] },
    "video:animation": { sections: ["track"], pages: ["motion"] },
    // Repair is a subtab of its own: stabilisation, flicker, noise, colour match
    // and scene detection are things done TO footage, not ways of styling it,
    // and they were invisible because they were in no view at all.
    "video:adjust": { sections: ["mask", "key", "removebg"], pages: ["cutout", "advanced"] },
    "video:repair": { sections: ["repair", "scenes", "rhythm"], pages: [] },
    audio: { sections: ["audio", "rhythm"], pages: ["audio"] },
    effects: { sections: [], pages: ["effects", "transition"] },
  };
  const groupSeg = el.querySelector<HTMLElement>('[data-ref="group"]')!;
  const subtabSeg = el.querySelector<HTMLElement>('[data-ref="subtabs"]')!;
  const inspectorBody = el.querySelector<HTMLElement>(".inspector-body")!;
  let activeGroup = "video";
  let activeSubtab = "basic";
  let showAll = false;
  const everything = {
    sections: ["transform", "text", "blend", "timing", "track", "mask", "key", "audio", "repair", "scenes", "removebg", "canvas", "rhythm"],
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
  const italicBtn = el.querySelector<HTMLElement>('[data-ref="italic"]')!;
  italicBtn.addEventListener("click", () => patchText({ italic: !italicBtn.classList.contains("is-on") }));
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
      else if (input.type === "color") patchText({ [key]: input.value });
      else {
        const bounds: Record<string, [number, number]> = {
          weight: [100, 900], outlineWidth: [0, 50], shadowBlur: [0, 100], shadowX: [-200, 200], shadowY: [-200, 200],
          plateOpacity: [0, 1], platePadding: [0, 200], plateRadius: [0, 200], lineHeight: [0.5, 4],
          letterSpacing: [-50, 200], wrapWidth: [5, 100], textOpacity: [0, 1],
        };
        const span = bounds[key];
        if (!span) return;
        if (input.value.trim() === "") { patchText({ [key]: undefined }); return; }
        const value = Number(input.value);
        if (!Number.isNaN(value)) patchText({ [key]: Math.min(span[1], Math.max(span[0], value)) });
      }
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

  // F8: the repairs as a panel of their own. Each writes to the clip the same
  // way the effect list did, so nothing about the render changes; what changes
  // is that a person can find them, and that the ones with parameters have
  // somewhere to put them.
  const repairClip = () => {
    const id = engine.snapshot.selectedClipId;
    return id ? engine.findClip(id) : null;
  };
  const effectsOf = (clip: { effects?: Array<{ id: string; amount?: number; params?: Record<string, number> }> }) =>
    (clip.effects ?? []).map((entry) => ({ ...entry }));
  const setRepairEffect = (name: string, on: boolean, params: Record<string, number>) => {
    const found = repairClip();
    if (!found) return;
    const list = effectsOf(found.clip).filter((entry) => entry.id !== name);
    if (on) list.push({ id: name, amount: 100, params });
    engine.dispatch("clip.effects", { clipId: found.clip.id, effects: list });
  };
  const repairRef = <T extends HTMLElement>(name: string) => el.querySelector<T>(`[data-ref="${name}"]`);
  const stabToggle = repairRef<HTMLButtonElement>("rep-stab");
  const stabState = repairRef<HTMLElement>("rep-stab-state");
  const writeStabilise = (on: boolean) => {
    const found = repairClip();
    if (!found) return;
    const smoothing = Number(repairRef<HTMLInputElement>("rep-smooth")?.value ?? 60) / 100;
    const crop = Number(repairRef<HTMLInputElement>("rep-crop")?.value ?? 6) / 100;
    engine.dispatch("clip.stabilise", { clipId: found.clip.id, stabilise: on ? { smoothing, crop } : null });
    repairRef<HTMLElement>("rep-stab-rows")!.hidden = !on;
    repairRef<HTMLElement>("rep-crop-rows")!.hidden = !on;
    if (on) void analyseMotion(found.clip.mediaId);
  };
  const analyseMotion = async (mediaId?: string) => {
    if (!mediaId || !stabState) return;
    try {
      const started = await fetch(`/api/media/${mediaId}/motion`, {
        method: "POST", headers: { "x-formcut-local": "1" },
      }).then((r) => r.json());
      stabState.textContent = started.state === "ready" ? t("rep.ready") : t("rep.analysing");
      // The path is measured once; polling stops as soon as it is there.
      const tick = window.setInterval(async () => {
        const state = await fetch(`/api/media/${mediaId}/motion`).then((r) => r.json());
        stabState.textContent = state.state === "ready"
          ? `${t("rep.ready")} · ${state.frames ?? 0}`
          : `${t("rep.analysing")} ${Math.round((state.progress ?? 0) * 100)}%`;
        if (state.state === "ready" || state.state === "missing") window.clearInterval(tick);
      }, 1200);
    } catch {
      stabState.textContent = t("rep.failed");
    }
  };
  stabToggle?.addEventListener("click", () => {
    const on = stabToggle.getAttribute("aria-pressed") !== "true";
    stabToggle.setAttribute("aria-pressed", String(on));
    stabToggle.classList.toggle("is-on", on);
    writeStabilise(on);
  });
  for (const ref of ["rep-smooth", "rep-crop"]) {
    repairRef<HTMLInputElement>(ref)?.addEventListener("input", (event) => {
      const input = event.target as HTMLInputElement;
      const label = repairRef<HTMLElement>(`${ref}-value`);
      if (label) label.textContent = ref === "rep-crop" ? `${input.value}%` : input.value;
      if (stabToggle?.getAttribute("aria-pressed") === "true") writeStabilise(true);
    });
  }
  for (const [ref, name, param] of [["rep-flick", "deflicker", "strength"], ["rep-noise", "denoise-picture", "strength"]] as const) {
    const button = repairRef<HTMLButtonElement>(ref);
    const amount = repairRef<HTMLInputElement>(`${ref}-amt`);
    const write = () => {
      const on = button?.getAttribute("aria-pressed") === "true";
      setRepairEffect(name, on, { [param]: Number(amount?.value ?? 50) / 100 });
    };
    button?.addEventListener("click", () => {
      const on = button.getAttribute("aria-pressed") !== "true";
      button.setAttribute("aria-pressed", String(on));
      button.classList.toggle("is-on", on);
      write();
    });
    amount?.addEventListener("change", write);
  }
  repairRef<HTMLButtonElement>("rep-match-sample")?.addEventListener("click", () => void (async () => {
    // Colour matching needs numbers from a reference frame, and the frame a
    // person means is the one they are looking at, so the playhead is the pick.
    const state = repairRef<HTMLElement>("rep-match-state");
    const found = repairClip();
    if (!found || !state) return;
    state.textContent = t("rep.sampling");
    try {
      const stats = await fetch("/api/render/sample", {
        method: "POST", headers: { "Content-Type": "application/json", "x-formcut-local": "1" },
        body: JSON.stringify({ project: engine.snapshot, time: engine.snapshot.playhead }),
      }).then((r) => r.json());
      setRepairEffect("colour-match", true, { strength: 1, ...stats });
      state.textContent = t("rep.matched");
    } catch {
      state.textContent = t("rep.failed");
    }
  })());

  // F11: making the frames between rather than repeating them is a property of
  // the clip's speed, so it sits with speed rather than in a document field.
  const smoothToggle = el.querySelector<HTMLButtonElement>('[data-ref="smooth-slow"]');
  smoothToggle?.addEventListener("click", () => {
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id) : null;
    if (!found) return;
    const on = smoothToggle.getAttribute("aria-pressed") !== "true";
    smoothToggle.setAttribute("aria-pressed", String(on));
    smoothToggle.classList.toggle("is-on", on);
    engine.dispatch("clip.smooth-slow", { clipId: found.clip.id, on });
  });

  // F10: scene detection as something a person does to a clip, rather than an
  // endpoint nobody can reach. Finding the cuts and acting on them are two
  // steps, because a person should see how many were found before a long clip
  // is chopped into pieces.
  let foundCuts: number[] = [];
  const sceneState = el.querySelector<HTMLElement>('[data-ref="scene-state"]');
  const sceneSplit = el.querySelector<HTMLButtonElement>('[data-ref="scene-split"]');
  el.querySelector('[data-ref="scene-sens"]')?.addEventListener("input", (event) => {
    const label = el.querySelector<HTMLElement>('[data-ref="scene-sens-value"]');
    if (label) label.textContent = (event.target as HTMLInputElement).value;
  });
  el.querySelector('[data-ref="scene-find"]')?.addEventListener("click", () => void (async () => {
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id) : null;
    if (!found?.clip.mediaId || !sceneState) return;
    const sensitivity = Number(el.querySelector<HTMLInputElement>('[data-ref="scene-sens"]')?.value ?? 50) / 100;
    sceneState.textContent = t("scene.looking");
    try {
      const reply = await fetch(`/api/media/${found.clip.mediaId}/scenes?sensitivity=${sensitivity}`)
        .then((r) => r.json());
      // Only cuts inside what this clip actually uses are worth offering.
      const from = found.clip.sourceIn ?? 0;
      foundCuts = (reply.cuts ?? [])
        .map((cut: { at: number }) => cut.at - from)
        .filter((at: number) => at > 0.2 && at < found.clip.duration - 0.2);
      sceneState.textContent = `${foundCuts.length} ${t("scene.found")}`;
      if (sceneSplit) sceneSplit.hidden = foundCuts.length === 0;
    } catch {
      sceneState.textContent = t("scene.failed");
    }
  })());
  sceneSplit?.addEventListener("click", () => {
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id) : null;
    if (!found || !foundCuts.length) return;
    // Split from the end backwards, so each cut's time still means what it
    // meant when it was measured. The command takes `time`, not `at`: passing
    // the wrong name made every split a silent no-op.
    for (const at of [...foundCuts].sort((a, b) => b - a)) {
      const current = engine.findClip(found.clip.id);
      if (!current) break;
      engine.dispatch("clips.split", { time: current.clip.start + at, clipIds: [current.clip.id] });
    }
    if (sceneState) sceneState.textContent = `${foundCuts.length} ${t("scene.done")}`;
    sceneSplit.hidden = true;
    foundCuts = [];
  });

  // Cutout and background removal need a model on disk. Without one they do
  // nothing at all and say nothing about why, which is exactly what happened.
  const modelState = el.querySelector<HTMLElement>('[data-ref="bg-model-state"]');
  const modelGet = el.querySelector<HTMLButtonElement>('[data-ref="bg-model-get"]');
  const CUTOUT_MODELS = ["object-cutout", "person-cutout"];
  const refreshModels = async () => {
    if (!modelState) return;
    try {
      const listed = await fetch("/api/models").then((r) => r.json());
      const wanted = listed.filter((m: { id: string }) => CUTOUT_MODELS.includes(m.id));
      const missing = wanted.filter((m: { ready?: boolean }) => !m.ready);
      modelState.textContent = missing.length
        ? `${missing.length} ${t("bg.missing")}`
        : t("bg.ready");
      if (modelGet) modelGet.hidden = missing.length === 0;
    } catch {
      modelState.textContent = t("bg.offline");
    }
  };
  modelGet?.addEventListener("click", () => void (async () => {
    if (!modelState) return;
    modelGet.disabled = true;
    modelState.textContent = t("bg.getting");
    try {
      for (const id of CUTOUT_MODELS) {
        const started = await fetch(`/api/models/${id}/download`, {
          method: "POST", headers: { "x-formcut-local": "1" },
        }).then((r) => r.json());
        // The download is a job, so it reports progress like any other.
        if (started.job_id) {
          for (let waited = 0; waited < 900; waited += 1) {
            const state = await fetch(`/api/jobs/${started.job_id}`).then((r) => r.json());
            if (["done", "error", "failed"].includes(state.status)) break;
            modelState.textContent = `${t("bg.getting")} ${Math.round((state.progress ?? 0) * 100)}%`;
            await new Promise((resolve) => setTimeout(resolve, 1000));
          }
        }
      }
    } catch {
      modelState.textContent = t("bg.failed");
    } finally {
      modelGet.disabled = false;
      await refreshModels();
    }
  })());
  void refreshModels();

  // The renderer has drawn colour, gradient, image and blurred backgrounds
  // since 0.70.0 with no way to choose one; this is that way.
  const canvasKind = el.querySelector<HTMLSelectElement>('[data-ref="canvas-kind"]');
  const writeCanvas = () => {
    const kind = canvasKind?.value ?? "";
    const rows = {
      colours: el.querySelector<HTMLElement>('[data-ref="canvas-colours"]'),
      amount: el.querySelector<HTMLElement>('[data-ref="canvas-amount-row"]'),
    };
    if (rows.colours) rows.colours.hidden = !(kind === "colour" || kind === "gradient");
    if (rows.amount) rows.amount.hidden = kind !== "blur";
    const from = el.querySelector<HTMLInputElement>('[data-ref="canvas-from"]')?.value ?? "#101418";
    const to = el.querySelector<HTMLInputElement>('[data-ref="canvas-to"]')?.value ?? "#2b3440";
    const amount = Number(el.querySelector<HTMLInputElement>('[data-ref="canvas-amount"]')?.value ?? 40);
    const background = kind === "colour" ? { type: "colour", colour: from }
      : kind === "gradient" ? { type: "gradient", from, to }
      : kind === "blur" ? { type: "blur", amount }
      : null;
    engine.dispatch("project.background", { background });
  };
  canvasKind?.addEventListener("change", writeCanvas);
  for (const ref of ["canvas-from", "canvas-to", "canvas-amount"]) {
    el.querySelector(`[data-ref="${ref}"]`)?.addEventListener("input", (event) => {
      if (ref === "canvas-amount") {
        const label = el.querySelector<HTMLElement>('[data-ref="canvas-amount-value"]');
        if (label) label.textContent = (event.target as HTMLInputElement).value;
      }
      writeCanvas();
    });
  }

  // Beats and ducking: both read the clip's own audio and write something a
  // person can see and move, rather than processing the sound behind their back.
  el.querySelector('[data-ref="beat-find"]')?.addEventListener("click", () => void (async () => {
    const note = el.querySelector<HTMLElement>('[data-ref="beat-state"]');
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id) : null;
    if (!found?.clip.mediaId || !note) return;
    note.textContent = t("beat.listening");
    try {
      const reply = await fetch(`/api/media/${found.clip.mediaId}/beats`).then((r) => r.json());
      note.textContent = reply.bpm ? `${reply.count} · ${reply.bpm} bpm` : `${reply.count}`;
      // Beats become snap points on the timeline, which is what they are for.
      document.dispatchEvent(new CustomEvent("formcut:beats", {
        detail: { clipId: found.clip.id, start: found.clip.start, beats: reply.beats ?? [] },
      }));
    } catch {
      note.textContent = t("beat.failed");
    }
  })());
  el.querySelector('[data-ref="duck-apply"]')?.addEventListener("click", () => void (async () => {
    const note = el.querySelector<HTMLElement>('[data-ref="beat-state"]');
    const state = engine.snapshot;
    const music = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    if (!music || !note) return;
    // The speech is whatever is on another track: ducking needs two things.
    const timeline = state.timelines[state.activeTimeline];
    const speech = timeline.tracks
      .flatMap((track) => track.clips)
      .find((clip) => clip.id !== music.clip.id && clip.mediaId && (clip.kind === "audio" || clip.kind === "video"));
    if (!speech?.mediaId) { note.textContent = t("beat.nospeech"); return; }
    note.textContent = t("beat.working");
    try {
      const depth = Number(el.querySelector<HTMLInputElement>('[data-ref="duck-depth"]')?.value ?? 25) / 100;
      const reply = await fetch(`/api/media/${speech.mediaId}/ducking`, {
        method: "POST", headers: { "Content-Type": "application/json", "x-formcut-local": "1" },
        body: JSON.stringify({ depth }),
      }).then((r) => r.json());
      const shifted = (reply.keyframes ?? []).map((frame: { t: number; props: Record<string, number> }) => ({
        ...frame, t: Math.max(0, frame.t + speech.start - music.clip.start),
      }));
      engine.dispatch("clip.keyframes.replace", { clipId: music.clip.id, keyframes: shifted });
      note.textContent = `${reply.regions?.length ?? 0} ${t("beat.ducked")}`;
    } catch {
      note.textContent = t("beat.failed");
    }
  })());

  const clipNow = () => {
    const id = engine.snapshot.selectedClipId;
    return id ? engine.findClip(id) : null;
  };
  const post = async (path: string, body: unknown) =>
    fetch(path, { method: "POST", headers: { "Content-Type": "application/json", "x-formcut-local": "1" },
                  body: JSON.stringify(body) }).then((r) => r.json());

  el.querySelector('[data-ref="mask-track"]')?.addEventListener("click", () => void (async () => {
    const note = el.querySelector<HTMLElement>('[data-ref="mask-track-state"]');
    const found = clipNow();
    if (!found?.clip.mediaId || !note) return;
    const points = found.clip.mask?.points ?? [];
    if (points.length < 3) { note.textContent = t("mask.needpath"); return; }
    note.textContent = t("mask.following");
    try {
      const reply = await post(`/api/media/${found.clip.mediaId}/track`, {
        project: engine.snapshot, points, start: found.clip.start, duration: found.clip.duration,
      });
      // The mask becomes keyframed anchors, which is what makes it editable
      // afterwards rather than a black box that moved something.
      const frames = (reply.path ?? []).map((entry: { t: number; points: unknown }) => ({
        t: entry.t, props: {}, mask: entry.points,
      }));
      engine.dispatch("clip.mask-track", { clipId: found.clip.id, path: frames });
      note.textContent = `${reply.frames} ${t("mask.tracked")}`;
    } catch { note.textContent = t("mask.failed"); }
  })());

  el.querySelector('[data-ref="reframe-go"]')?.addEventListener("click", () => void (async () => {
    const found = clipNow();
    if (!found?.clip.mediaId) return;
    const aspect = Number(el.querySelector<HTMLSelectElement>('[data-ref="reframe-aspect"]')?.value ?? 0.5625);
    const reply = await post(`/api/media/${found.clip.mediaId}/reframe`, {
      project: engine.snapshot, start: found.clip.start, duration: found.clip.duration, aspect,
    });
    const frames = (reply.crops ?? []).map((crop: { t: number; x: number; w: number }) => ({
      t: crop.t, props: { posX: Math.round((0.5 - (crop.x + crop.w / 2)) * 200) },
    }));
    engine.dispatch("clip.keyframes.replace", { clipId: found.clip.id, keyframes: frames });
  })());

  let fillerRanges: Array<{ start: number; end: number; word: string }> = [];
  el.querySelector('[data-ref="filler-find"]')?.addEventListener("click", () => void (async () => {
    const note = el.querySelector<HTMLElement>('[data-ref="filler-state"]');
    const found = clipNow();
    const captions = (found?.clip as { captions?: Array<{ start: number; end: number; text: string }> })?.captions;
    if (!note) return;
    if (!captions?.length) { note.textContent = t("filler.nocaptions"); return; }
    const reply = await post("/api/media/fillers", { segments: captions, language: (document.documentElement.lang || "en").slice(0, 2) });
    fillerRanges = reply.ranges ?? [];
    note.textContent = `${reply.count} · ${reply.seconds}s`;
    const cut = el.querySelector<HTMLElement>('[data-ref="filler-cut"]');
    if (cut) cut.hidden = fillerRanges.length === 0;
  })());
  el.querySelector('[data-ref="filler-cut"]')?.addEventListener("click", () => {
    const found = clipNow();
    if (!found || !fillerRanges.length) return;
    // Cut from the end backwards so each range still means what it meant.
    for (const range of [...fillerRanges].sort((a, b) => b.start - a.start)) {
      engine.dispatch("clip.remove-range", {
        clipId: found.clip.id, start: found.clip.start + range.start, end: found.clip.start + range.end,
      });
    }
    fillerRanges = [];
    const cut = el.querySelector<HTMLElement>('[data-ref="filler-cut"]');
    if (cut) cut.hidden = true;
  });

  // The cutout flow. Each step reports what actually happened rather than
  // leaving a person to infer it from the picture.
  const cut = <T extends HTMLElement>(name: string) => el.querySelector<T>(`[data-ref="${name}"]`);
  const cutClip = () => {
    const id = engine.snapshot.selectedClipId;
    return id ? engine.findClip(id) : null;
  };
  const chosenModel = () => el.querySelector<HTMLSelectElement>('[data-ref="bg-model"]')?.value
    ?? cut<HTMLSelectElement>("cut-model")?.value ?? "person-cutout";

  const refreshCutModels = async () => {
    const state = cut<HTMLElement>("cut-model-state");
    const get = cut<HTMLButtonElement>("cut-model-get");
    if (!state) return;
    try {
      const listed = await fetch("/api/models").then((r) => r.json());
      const wanted = listed.filter((m: { id: string }) => ["object-cutout", "person-cutout"].includes(m.id));
      const missing = wanted.filter((m: { ready?: boolean }) => !m.ready);
      state.textContent = missing.length ? `${missing.length} ${t("bg.missing")}` : t("bg.ready");
      if (get) get.hidden = missing.length === 0;
      el.querySelector('[data-step="model"]')?.classList.toggle("is-done", missing.length === 0);
    } catch {
      state.textContent = t("bg.offline");
    }
  };
  cut<HTMLButtonElement>("cut-model-get")?.addEventListener("click", () => void (async () => {
    const state = cut<HTMLElement>("cut-model-state");
    if (!state) return;
    state.textContent = t("bg.getting");
    for (const id of ["object-cutout", "person-cutout"]) {
      try {
        const started = await fetch(`/api/models/${id}/download`, {
          method: "POST", headers: { "x-formcut-local": "1" },
        }).then((r) => r.json());
        if (started.job_id) {
          for (let waited = 0; waited < 900; waited += 1) {
            const job = await fetch(`/api/jobs/${started.job_id}`).then((r) => r.json());
            if (["done", "error", "failed"].includes(job.status)) break;
            state.textContent = `${t("bg.getting")} ${Math.round((job.progress ?? 0) * 100)}%`;
            await new Promise((resolve) => setTimeout(resolve, 1000));
          }
        }
      } catch { /* reported by the refresh below */ }
    }
    await refreshCutModels();
  })());

  cut<HTMLButtonElement>("cut-run")?.addEventListener("click", () => void (async () => {
    const state = cut<HTMLElement>("cut-run-state");
    const found = cutClip();
    if (!found?.clip.mediaId || !state) return;
    const model = chosenModel();
    state.textContent = t("cut.working");
    try {
      const reply = await fetch(`/api/media/${found.clip.mediaId}/cutout-preview`, {
        method: "POST", headers: { "Content-Type": "application/json", "x-formcut-local": "1" },
        body: JSON.stringify({ project: engine.snapshot, time: engine.snapshot.playhead, model }),
      }).then(async (r) => (r.ok ? r.json() : Promise.reject(new Error((await r.json()).detail))));
      if (reply.empty) {
        state.textContent = t("cut.nothing");
        return;
      }
      engine.dispatch("clip.cutout", {
        clipId: found.clip.id,
        cutout: { ...(found.clip.cutout ?? {}), model, threshold: 0.5, feather: 0.1,
                  strokes: found.clip.cutout?.strokes ?? [] },
      });
      const percent = Math.round(reply.kept * 100);
      state.textContent = `${percent}% ${t("cut.kept")} · ${reply.seconds}s`;
      el.querySelector('[data-step="run"]')?.classList.add("is-done");
      const pick = cut<HTMLElement>("cut-pick-state");
      if (pick) {
        pick.textContent = reply.regions > 1
          ? `${reply.regions} ${t("cut.several")}`
          : t("cut.justone");
      }
    } catch (error) {
      state.textContent = error instanceof Error ? error.message : t("cut.failed");
    }
  })());

  const pickButton = cut<HTMLButtonElement>("cut-pick");
  pickButton?.addEventListener("click", () => {
    const stage = document.querySelector<HTMLElement>(".stage");
    if (!stage) return;
    const on = stage.dataset.pickCutout !== "on";
    if (on) stage.dataset.pickCutout = "on"; else delete stage.dataset.pickCutout;
    pickButton.classList.toggle("is-on", on);
    pickButton.setAttribute("aria-pressed", String(on));
    const note = cut<HTMLElement>("cut-pick-state");
    if (note && on) note.textContent = t("cut.clicknow");
  });
  // Clicking the preview while picking chooses which thing to keep.
  document.addEventListener("formcut:stage-click", (event) => {
    const stage = document.querySelector<HTMLElement>(".stage");
    if (stage?.dataset.pickCutout !== "on") return;
    const at = (event as CustomEvent).detail as { x: number; y: number };
    const found = cutClip();
    if (!found?.clip.cutout) return;
    engine.dispatch("clip.cutout", {
      clipId: found.clip.id, cutout: { ...found.clip.cutout, point: { x: at.x, y: at.y } },
    });
    const note = cut<HTMLElement>("cut-pick-state");
    if (note) note.textContent = t("cut.picked");
    cut<HTMLElement>("cut-clear-point")!.hidden = false;
    el.querySelector('[data-step="pick"]')?.classList.add("is-done");
    delete stage!.dataset.pickCutout;
    pickButton?.classList.remove("is-on");
  });
  cut<HTMLButtonElement>("cut-clear-point")?.addEventListener("click", () => {
    const found = cutClip();
    if (!found?.clip.cutout) return;
    const next = { ...found.clip.cutout };
    delete (next as { point?: unknown }).point;
    engine.dispatch("clip.cutout", { clipId: found.clip.id, cutout: next });
    const note = cut<HTMLElement>("cut-pick-state");
    if (note) note.textContent = t("cut.pickhint");
    cut<HTMLElement>("cut-clear-point")!.hidden = true;
  });
  void refreshCutModels();

  const drawToggle = el.querySelector<HTMLElement>('[data-ref="mask-draw"]');
  drawToggle?.addEventListener("click", () => {
    const stage = document.querySelector<HTMLElement>(".stage");
    if (!stage) return;
    const wasOn = stage.dataset.pen === "on";
    // Drawing needs a path mask to draw into. Turning the pen on when the clip
    // has some other shape would have done nothing visible, which is most of
    // why the tool was impossible to find.
    if (!wasOn) {
      const shape = el.querySelector<HTMLSelectElement>('[data-ref="mask-shape"]');
      if (shape && shape.value !== "path") {
        shape.value = "path";
        shape.dispatchEvent(new Event("change", { bubbles: true }));
      }
      stage.dataset.pen = "on";
    } else {
      delete stage.dataset.pen;
    }
    drawToggle.classList.toggle("is-on", !wasOn);
    drawToggle.setAttribute("aria-pressed", String(!wasOn));
    const help = el.querySelector<HTMLElement>('[data-ref="mask-pen-help"]');
    if (help) help.hidden = wasOn;
    stage.dispatchEvent(new CustomEvent("formcut:pen-mode"));
  });
  const lassoButton = el.querySelector<HTMLButtonElement>('[data-ref="mask-lasso"]');
  lassoButton?.addEventListener("click", () => {
    const stage = document.querySelector<HTMLElement>(".stage");
    if (!stage) return;
    const on = stage.dataset.pen !== "lasso";
    const shape = el.querySelector<HTMLSelectElement>('[data-ref="mask-shape"]');
    if (on && shape && shape.value !== "path") {
      shape.value = "path";
      shape.dispatchEvent(new Event("change", { bubbles: true }));
    }
    if (on) stage.dataset.pen = "lasso"; else delete stage.dataset.pen;
    lassoButton.classList.toggle("is-on", on);
    lassoButton.setAttribute("aria-pressed", String(on));
    drawToggle?.classList.remove("is-on");
    stage.dispatchEvent(new CustomEvent("formcut:pen-mode"));
  });
  el.querySelector('[data-ref="mask-subject"]')?.addEventListener("click", () => void (async () => {
    const note = el.querySelector<HTMLElement>('[data-ref="mask-auto-note"]');
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id) : null;
    if (!found?.clip.mediaId || !note) return;
    note.textContent = t("mask.looking");
    try {
      const reply = await fetch(`/api/media/${found.clip.mediaId}/subject`, {
        method: "POST",
        headers: { "Content-Type": "application/json", "x-formcut-local": "1" },
        body: JSON.stringify({ project: engine.snapshot, time: engine.snapshot.playhead, model: "person-cutout" }),
      }).then(async (r) => (r.ok ? r.json() : Promise.reject(new Error((await r.json()).detail))));
      engine.dispatch("clip.mask", {
        clipId: found.clip.id,
        mask: { ...(found.clip.mask ?? { x: 0, y: 0, w: 100, h: 100, feather: 0 }), shape: "path", points: reply.points },
      });
      note.textContent = `${t("mask.traced")} ${reply.points.length}`;
    } catch (error) {
      note.textContent = error instanceof Error ? error.message : t("mask.failed");
    }
  })());

  // Brush strokes go into the cutout, which is where the renderer reads them.
  const brushState = { mode: "" as "" | "keep" | "erase" };
  const setBrush = (mode: "keep" | "erase") => {
    brushState.mode = brushState.mode === mode ? "" : mode;
    for (const [ref, name] of [["brush-keep", "keep"], ["brush-erase", "erase"]] as const) {
      const button = el.querySelector<HTMLButtonElement>(`[data-ref="${ref}"]`);
      button?.classList.toggle("is-on", brushState.mode === name);
      button?.setAttribute("aria-pressed", String(brushState.mode === name));
    }
    const stage = document.querySelector<HTMLElement>(".stage");
    if (!stage) return;
    if (brushState.mode) stage.dataset.brush = brushState.mode;
    else delete stage.dataset.brush;
    stage.dataset.brushSize = String(Number(el.querySelector<HTMLInputElement>('[data-ref="brush-size"]')?.value ?? 8) / 100);
    stage.dispatchEvent(new CustomEvent("formcut:brush-mode"));
  };
  el.querySelector('[data-ref="brush-keep"]')?.addEventListener("click", () => setBrush("keep"));
  el.querySelector('[data-ref="brush-erase"]')?.addEventListener("click", () => setBrush("erase"));
  el.querySelector('[data-ref="brush-size"]')?.addEventListener("input", (event) => {
    const value = (event.target as HTMLInputElement).value;
    const label = el.querySelector<HTMLElement>('[data-ref="brush-size-value"]');
    if (label) label.textContent = value;
    const stage = document.querySelector<HTMLElement>(".stage");
    if (stage) stage.dataset.brushSize = String(Number(value) / 100);
  });
  el.querySelector('[data-ref="brush-clear"]')?.addEventListener("click", () => {
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id) : null;
    if (!found?.clip.cutout) return;
    engine.dispatch("clip.cutout", { clipId: found.clip.id, cutout: { ...found.clip.cutout, strokes: [] } });
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
  const MASK_FIELDS = ["maskX", "maskY", "maskW", "maskH", "maskF", "maskA"] as const;
  const currentMaskPoints = () => {
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id) : null;
    return found?.clip.mask?.points ?? [
      { x: 0.3, y: 0.3 }, { x: 0.7, y: 0.35 }, { x: 0.55, y: 0.72 },
    ];
  };
  const dispatchMask = () => {
    const state = engine.snapshot;
    if (!state.selectedClipId) return;
    const shape = maskShape.value as "" | MaskShape;
    const num = (ref: string, fb: number) => Number(inputs.get(ref)?.value ?? fb) || fb;
    engine.dispatch("clip.mask", {
      clipId: state.selectedClipId,
      mask: shape
        ? {
            shape, x: num("maskX", 10), y: num("maskY", 10), w: num("maskW", 80), h: num("maskH", 80),
            feather: num("maskF", 0), angle: num("maskA", 0),
            // A drawn path keeps the anchors it already has; the pen tool on the
            // canvas is what edits them.
            ...(shape === "path" ? { points: currentMaskPoints() } : {}),
          }
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
        const key = input.dataset.xkey as keyof typeof ts;
        const raw = ts[key];
        const next = raw === undefined || raw === null ? (input.type === "color" ? input.defaultValue : "") : String(raw);
        if (document.activeElement !== input && input.value !== next) input.value = next;
      }
      italicBtn.classList.toggle("is-on", Boolean(ts.italic));
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

  // BG7: the Easy background section drives the same cutout and key fields the
  // Advanced creator panel writes, and asks the engine for the matte job.
  const bgMode = el.querySelector<HTMLSelectElement>('[data-ref="bg-mode"]')!;
  const bgProgress = el.querySelector<HTMLElement>('[data-ref="bg-progress"]')!;
  const bgFeather = el.querySelector<HTMLInputElement>('[data-ref="bg-feather"]')!;
  const bgBrush = el.querySelector<HTMLInputElement>('[data-ref="bg-brush"]')!;
  const selectedClip = () => {
    const id = engine.snapshot.selectedClipId;
    return id ? engine.findClip(id)?.clip ?? null : null;
  };
  bgMode.addEventListener("change", () => {
    const clip = selectedClip();
    if (!clip) return;
    const feather = Number(bgFeather.value) / 100;
    if (bgMode.value === "off") {
      engine.dispatch("clip.creator", { clipId: clip.id, patch: { cutout: undefined } });
      engine.dispatch("clip.key", { clipId: clip.id, key: null });
      bgProgress.textContent = "";
      return;
    }
    if (bgMode.value === "chroma") {
      engine.dispatch("clip.creator", { clipId: clip.id, patch: { cutout: undefined } });
      engine.dispatch("clip.key", { clipId: clip.id, key: { color: "#00d000", similarity: 0.25, blend: 0.05 } });
      return;
    }
    const cutout = { model: "person-cutout", threshold: 0.5, feather, strokes: clip.cutout?.strokes ?? [] };
    engine.dispatch("clip.creator", { clipId: clip.id, patch: { cutout } });
    bgProgress.textContent = t("bg.working");
    void api("/api/render/mattes", { clip: { ...clip, cutout }, fps: engine.snapshot.fps })
      .then(async (reply) => {
        if (reply.status === "ready") { bgProgress.textContent = t("bg.ready"); return; }
        for (let waited = 0; waited < 900; waited += 1) {
          const status = await fetch(`/api/jobs/${reply.job_id}`).then((r) => r.json());
          if (status.status === "done") { bgProgress.textContent = t("bg.ready"); return; }
          if (status.status === "error" || status.status === "failed") { bgProgress.textContent = t("bg.failed"); return; }
          bgProgress.textContent = `${t("bg.working")} ${Math.round((status.progress ?? 0) * 100)}%`;
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      })
      .catch(() => { bgProgress.textContent = t("bg.failed"); });
  });
  const bgSlider = (input: HTMLInputElement, readout: string, apply: (value: number, clip: Clip) => void) => {
    const label = el.querySelector<HTMLElement>(`[data-ref="${readout}"]`)!;
    input.addEventListener("input", () => { label.textContent = input.value; });
    input.addEventListener("change", () => {
      const clip = selectedClip();
      if (clip) apply(Number(input.value), clip);
    });
  };
  bgSlider(bgFeather, "bg-feather-value", (value, clip) => {
    if (!clip.cutout) return;
    engine.dispatch("clip.creator", { clipId: clip.id, patch: { cutout: { ...clip.cutout, feather: value / 100 } } });
  });
  bgSlider(bgBrush, "bg-brush-value", (value) => {
    const panel = document.querySelector<HTMLElement>(".creator-panel");
    if (panel) panel.dataset.brushRadius = String(value / 100);
  });

  // A longer language needs a wider panel. When the tab rows do not fit, the
  // pane asks the layout for exactly the width they need (the layout clamps it
  // to its own maximum), and the active tab is kept in view either way, so a
  // label is never half-cut.
  const fitTabs = () => {
    const rows = [...el.querySelectorAll<HTMLElement>(".seg")];
    let needed = 0;
    for (const row of rows) {
      const overflow = row.scrollWidth - row.clientWidth;
      if (overflow > 1) needed = Math.max(needed, overflow);
      const active = row.querySelector<HTMLElement>(".is-active");
      if (active) {
        const left = active.offsetLeft, right = left + active.offsetWidth;
        if (left < row.scrollLeft) row.scrollLeft = left;
        else if (right > row.scrollLeft + row.clientWidth) row.scrollLeft = right - row.clientWidth;
      }
    }
    if (needed > 1) {
      const width = Math.ceil(el.getBoundingClientRect().width + needed + 8);
      document.dispatchEvent(new CustomEvent("formcut:layout", { detail: { right: width } }));
    }
  };
  new ResizeObserver(() => fitTabs()).observe(el);
  engine.subscribe((_state, event) => { if (event === "clip-selection") fitTabs(); });
  window.setTimeout(fitTabs, 0);

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
