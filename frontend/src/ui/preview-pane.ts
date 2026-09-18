import { formatTimecode, type ProjectEngine } from "../engine/project";
import { fileUrl, type MediaBin } from "../engine/media";
import { findEffect } from "../engine/registry";
import { transitionPlans } from "../engine/transitions";
import { sampledTransform } from "../engine/keyframes";
import { defaultTextStyle, defaultTransform, type Clip, type ClipTransform } from "../engine/types";
import { icon } from "./icons";

const HANDLES = [
  ["0%", "0%"], ["50%", "0%"], ["100%", "0%"],
  ["0%", "50%"], ["100%", "50%"],
  ["0%", "100%"], ["50%", "100%"], ["100%", "100%"],
];

export function buildPreviewPane(engine: ProjectEngine, bin: MediaBin): HTMLElement {
  const s = engine.snapshot;
  const el = document.createElement("section");
  el.className = "pane pane-preview";
  el.innerHTML = `
    <div class="pane-header">
      <div class="title">Preview</div>
      <div class="meta">${s.width} x ${s.height} \u00B7 ${s.fps} fps</div>
      <div class="end"><button class="select-chip">${icon("pip")}${icon("chevD")}</button></div>
    </div>
    <div class="stage-wrap">
      <div class="stage">
        <div class="stage-art" data-ref="placeholder">NO MEDIA</div>
        <div class="stage-layers" data-ref="layers"></div>
        <div class="stage-frame">
          ${HANDLES.map(([x, y]) => `<span class="handle" style="left:${x};top:${y}"></span>`).join("")}
          <div class="stage-badge" data-ref="badge">100% \u00B7 0\u00B0</div>
        </div>
      </div>
    </div>
    <div class="transport">
      <span class="tc-field" data-ref="tc">${formatTimecode(s.playhead, s.fps)}</span>
      <span class="tc-total">/ ${formatTimecode(s.duration, s.fps)}</span>
      <div class="transport-btns">
        <button class="iconbtn" data-cmd="transport.home">${icon("toStart")}</button>
        <button class="iconbtn" data-cmd="step-back">${icon("stepBack")}</button>
        <button class="iconbtn play" data-ref="play">${icon("play")}</button>
        <button class="iconbtn" data-cmd="step-fwd">${icon("stepFwd")}</button>
        <button class="iconbtn" data-cmd="transport.end">${icon("toEnd")}</button>
      </div>
      <button class="select-chip">${icon("phone")}${s.aspect}${icon("chevD")}</button>
      <button class="select-chip">Full${icon("chevD")}</button>
    </div>`;

  const tc = el.querySelector<HTMLElement>('[data-ref="tc"]')!;
  const play = el.querySelector<HTMLElement>('[data-ref="play"]')!;
  const badge = el.querySelector<HTMLElement>('[data-ref="badge"]')!;

  play.addEventListener("click", () => engine.dispatch("transport.toggle"));
  el.querySelector('[data-cmd="transport.home"]')!.addEventListener("click", () => engine.dispatch("transport.home"));
  el.querySelector('[data-cmd="transport.end"]')!.addEventListener("click", () => engine.dispatch("transport.end"));
  el.querySelector('[data-cmd="step-back"]')!.addEventListener("click", () => engine.dispatch("transport.step", -1));
  el.querySelector('[data-cmd="step-fwd"]')!.addEventListener("click", () => engine.dispatch("transport.step", 1));

  const layersRoot = el.querySelector<HTMLElement>('[data-ref="layers"]')!;
  const placeholder = el.querySelector<HTMLElement>('[data-ref="placeholder"]')!;
  const trackHosts: HTMLElement[] = [];
  const layerEls = new Map<string, HTMLMediaElement | HTMLElement>();

  const hostFor = (trackIndex: number): HTMLElement => {
    while (trackHosts.length <= trackIndex) {
      const host = document.createElement("div");
      host.className = "layer-host";
      layersRoot.prepend(host);
      trackHosts.push(host);
    }
    return trackHosts[trackIndex];
  };

  const layerFor = (clip: Clip, trackIndex: number): HTMLMediaElement | HTMLElement | null => {
    const existing = layerEls.get(clip.id);
    if (existing) return existing;
    let node: HTMLMediaElement | HTMLElement;
    if (clip.kind === "video" && clip.mediaId) {
      const video = document.createElement("video");
      video.src = fileUrl(clip.mediaId);
      video.preload = "auto";
      video.playsInline = true;
      video.className = "layer layer-video";
      node = video;
    } else if (clip.kind === "image" && clip.mediaId) {
      const img = document.createElement("img");
      img.src = fileUrl(clip.mediaId);
      img.className = "layer layer-image";
      node = img;
    } else if (clip.kind === "audio" && clip.mediaId) {
      const audio = document.createElement("audio");
      audio.src = fileUrl(clip.mediaId);
      audio.preload = "auto";
      audio.className = "layer-audio";
      node = audio;
    } else if (clip.kind === "text") {
      const text = document.createElement("div");
      text.className = "layer layer-text";
      text.textContent = clip.label;
      node = text;
    } else {
      return null;
    }
    node.hidden = true;
    if (node instanceof HTMLMediaElement) {
      node.addEventListener("loadedmetadata", () => syncStage());
    }
    layerEls.set(clip.id, node);
    hostFor(trackIndex).append(node);
    return node;
  };

  const syncMedia = (mediaEl: HTMLMediaElement, wanted: number, playing: boolean, speed: number) => {
    if (mediaEl.readyState === 0 || mediaEl.seeking) return;
    if (mediaEl.playbackRate !== speed) mediaEl.playbackRate = speed;
    const drift = Math.abs(mediaEl.currentTime - wanted);
    if ((playing && drift > 0.25) || (!playing && drift > 0.03)) {
      mediaEl.currentTime = wanted;
    }
    if (playing && mediaEl.paused) {
      mediaEl.play().catch(() => {
        if (mediaEl instanceof HTMLVideoElement) {
          mediaEl.muted = true;
          mediaEl.play().catch(() => {});
        }
      });
    } else if (!playing && !mediaEl.paused) {
      mediaEl.pause();
    }
  };

  const fadeFactor = (clip: Clip, local: number): number => {
    let factor = 1;
    const fin = clip.fadeIn ?? 0;
    const fout = clip.fadeOut ?? 0;
    if (fin > 0 && local < fin) factor = Math.min(factor, local / fin);
    if (fout > 0 && local > clip.duration - fout) {
      factor = Math.min(factor, Math.max(0, (clip.duration - local) / fout));
    }
    return Math.max(0, Math.min(1, factor));
  };

  // Stage keying is a declared approximation: a feColorMatrix whose alpha row
  // suppresses the key color's dominant channel. The export's chromakey is the
  // ground truth; this gives live feedback without per-frame canvas work.
  const keyDefs = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  keyDefs.setAttribute("width", "0");
  keyDefs.setAttribute("height", "0");
  keyDefs.style.position = "absolute";
  el.append(keyDefs);
  const keyState = new Map<string, string>();
  const syncKeyFilter = (clip: Clip): string => {
    const key = clip.key!;
    const id = `fc-key-${clip.id}`;
    const sig = `${key.color}:${key.similarity}`;
    if (keyState.get(id) === sig) return id;
    const r = parseInt(key.color.slice(1, 3), 16) / 255;
    const g = parseInt(key.color.slice(3, 5), 16) / 255;
    const bch = parseInt(key.color.slice(5, 7), 16) / 255;
    const channels = [r, g, bch];
    const dom = channels.indexOf(Math.max(...channels));
    const strength = 1 + key.similarity * 3;
    const row = [strength / 2, strength / 2, strength / 2, 1, 0];
    row[dom] = -strength;
    const matrix = `1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  ${row.join(" ")}`;
    let filter = keyDefs.querySelector<SVGElement>(`#${id}`);
    if (!filter) {
      filter = document.createElementNS("http://www.w3.org/2000/svg", "filter");
      filter.setAttribute("id", id);
      filter.innerHTML = `<feColorMatrix type="matrix" values=""/>`;
      keyDefs.append(filter);
    }
    filter.querySelector("feColorMatrix")!.setAttribute("values", matrix);
    keyState.set(id, sig);
    return id;
  };
  const dropKeyFilter = (clipId: string) => {
    const id = `fc-key-${clipId}`;
    if (!keyState.has(id)) return;
    keyDefs.querySelector(`#${id}`)?.remove();
    keyState.delete(id);
  };

  const applyTransform = (node: HTMLElement, clip: Clip, fade = 1, local = 0) => {
    const t: ClipTransform = sampledTransform(clip, local);
    const sx = (t.scale / 100) * (t.width / 100) * (t.flipH ? -1 : 1);
    const sy = (t.scale / 100) * (t.height / 100);
    const css = `translate(${t.posX}%, ${t.posY}%) rotate(${t.rotation}deg) scale(${sx}, ${sy})`;
    if (node.style.transform !== css) node.style.transform = css;
    const opacity = String(Math.round((t.opacity / 100) * fade * 1000) / 1000);
    if (node.style.opacity !== opacity) node.style.opacity = opacity;
    const blend = t.blendMode.toLowerCase().replace(" ", "-");
    if (node.style.mixBlendMode !== blend) node.style.mixBlendMode = blend;
    // Mask preview is a declared approximation: hard-edged clip-path; the
    // export renders the true feathered mask via alphamerge.
    let clipPath = "";
    if (clip.mask) {
      const m = clip.mask;
      clipPath =
        m.shape === "ellipse"
          ? `ellipse(${m.w / 2}% ${m.h / 2}% at ${m.x + m.w / 2}% ${m.y + m.h / 2}%)`
          : `inset(${m.y}% ${100 - m.x - m.w}% ${100 - m.y - m.h}% ${m.x}%)`;
    }
    if (node.style.clipPath !== clipPath) node.style.clipPath = clipPath;
    const effectCss = clip.effectId ? (findEffect(clip.effectId)?.css ?? "") : "";
    const keyCss = clip.key ? `url(#${syncKeyFilter(clip)})` : "";
    if (!clip.key) dropKeyFilter(clip.id);
    const filter = [keyCss, effectCss].filter(Boolean).join(" ");
    if (node.style.filter !== filter) node.style.filter = filter;
    if (clip.kind === "text") {
      const ts = { ...defaultTextStyle(clip.label), ...clip.textStyle };
      if (node.textContent !== ts.content) node.textContent = ts.content;
      const size = `${ts.size}cqh`;
      if (node.style.fontSize !== size) node.style.fontSize = size;
      if (node.style.color !== ts.color) node.style.color = ts.color;
      const weight = ts.bold ? "700" : "400";
      if (node.style.fontWeight !== weight) node.style.fontWeight = weight;
      if (node.style.textAlign !== ts.align) node.style.textAlign = ts.align;
    }
  };

  const syncBadge = () => {
    const state = engine.snapshot;
    const found = state.selectedClipId ? engine.findClip(state.selectedClipId) : null;
    const t = { ...defaultTransform(), ...found?.clip.transform };
    const next = `${t.scale}% \u00B7 ${t.rotation}\u00B0`;
    if (badge.textContent !== next) badge.textContent = next;
  };

  const syncStage = () => {
    const state = engine.snapshot;
    const timeline = state.timelines[state.activeTimeline];
    const t = state.playhead;
    const plans = transitionPlans(timeline.tracks);
    const live = new Set<string>();
    let visual = false;
    for (const [trackIndex, track] of timeline.tracks.entries()) {
      for (const clip of track.clips) {
        const plan = plans.get(clip.id);
        const end = clip.start + clip.duration + (plan?.extendOut ?? 0);
        const active = clip.start <= t && t < end;
        if (!active) continue;
        const node = layerFor(clip, trackIndex);
        if (!node) continue;
        live.add(clip.id);
        if (node.hidden) node.hidden = false;
        if (node instanceof HTMLMediaElement) {
          const wantMuted = Boolean(clip.muted);
          if (node.muted !== wantMuted) node.muted = wantMuted;
          syncMedia(node, (t - clip.start) * (clip.speed ?? 1), state.playing, clip.speed ?? 1);
        }
        if (clip.kind !== "audio") {
          const local = t - clip.start;
          let factor = fadeFactor(clip, local);
          if (plan) {
            if (plan.rampIn > 0 && local < plan.rampIn) {
              factor = Math.min(factor, local / plan.rampIn);
            }
            if (plan.extendOut > 0 && local > clip.duration) {
              factor = Math.min(factor, Math.max(0, 1 - (local - clip.duration) / plan.extendOut));
            }
            if (plan.rampOut > 0 && local > clip.duration - plan.rampOut) {
              factor = Math.min(factor, Math.max(0, (clip.duration - local) / plan.rampOut));
            }
          }
          applyTransform(node, clip, factor, local);
          visual = true;
        }
      }
    }
    for (const [clipId, node] of layerEls) {
      if (live.has(clipId)) continue;
      if (!node.hidden) {
        node.hidden = true;
        if (node instanceof HTMLMediaElement && !node.paused) node.pause();
      }
      if (!engine.findClip(clipId)) {
        node.remove();
        layerEls.delete(clipId);
      }
    }
    if (placeholder.hidden !== visual) placeholder.hidden = visual;
  };

  engine.subscribe((state, changed) => {
    if (changed === "playhead") {
      const next = formatTimecode(state.playhead, state.fps);
      if (tc.textContent !== next) tc.textContent = next;
      syncStage();
    }
    if (changed === "transport") {
      play.innerHTML = icon(state.playing ? "pause" : "play");
      syncStage();
    }
    if (changed === "clips" || changed === "timeline") {
      syncStage();
      syncBadge();
    }
    if (changed === "clip-selection") {
      syncBadge();
    }
  });
  syncStage();
  syncBadge();
  return el;
}
