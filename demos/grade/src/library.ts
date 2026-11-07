import type { ProjectEngine } from "../../../frontend/src/engine/project";
import { icon } from "../../../frontend/src/ui/icons";
import { allSources, getSource, onSources } from "../../../demo/src/media";
import type { Source } from "../../../demo/src/media";
import { applyLattice, latticeFor } from "./grade";
import { LOOKS } from "./looks";
import { TRANSITION_KINDS, drawSwatch } from "./render";

export interface LibraryHooks {
  openFiles: () => void;
  place: (id: string) => void;
  dragMime: string;
  say: (text: string) => void;
}

const TABS: Array<[string, string]> = [["media", "Media"], ["looks", "Looks"], ["transitions", "Transitions"]];
const STILL_W = 160;
const STILL_H = 90;
const title = (id: string): string => id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

export function buildLibrary(engine: ProjectEngine, hooks: LibraryHooks): HTMLElement {
  const element = document.createElement("section");
  element.className = "pane pane-media";
  element.innerHTML = `
    <div class="pane-tabs"><div class="pane-tab-strip">${TABS.map(([key, label], index) => `<button class="pane-tab${index === 0 ? " is-active" : ""}" data-tab="${key}">${label}</button>`).join("")}</div></div>
    <div class="media-body" data-view="media"><div class="media-main">
      <div class="bin-toolbar"><button class="tool-chip" data-ref="open">${icon("plus")}Add files</button><span class="fx-status" data-ref="count"></span></div>
      <div class="card-grid bin-grid" data-ref="bin"></div>
      <p class="demo-hint">Drop a video, image, audio file, .cube LUT or .srt anywhere on this page. Files are read in the browser and never uploaded. The film's clips were encoded flat on purpose, so the grade has room.</p>
    </div></div>
    <div class="media-body" data-view="looks" hidden><div class="media-main">
      <div class="fx-status" data-ref="look-status">Select a clip, then pick a look. Each card shows that clip's frame with the look applied.</div>
      <div class="card-grid" data-ref="look-grid"></div>
    </div></div>
    <div class="media-body" data-view="transitions" hidden><div class="media-main">
      <div class="fx-status" data-ref="tr-status">Select a clip that follows another on its track, then pick how it comes in.</div>
      <div class="card-grid" data-ref="tr-grid"></div>
    </div></div>`;
  const ref = <T extends HTMLElement>(name: string) => element.querySelector<T>(`[data-ref="${name}"]`)!;
  const bin = ref("bin");
  const count = ref("count");
  const lookGrid = ref("look-grid");
  const trGrid = ref("tr-grid");
  const cards = new Map<string, HTMLElement>();
  const setText = (node: HTMLElement, value: string) => {
    if (node.textContent !== value) node.textContent = value;
  };
  const duration = (value: number) => `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;

  const makeCard = (source: Source): HTMLElement => {
    const card = document.createElement("div");
    card.className = "effect-card bin-card";
    card.dataset.media = source.id;
    card.draggable = true;
    card.tabIndex = 0;
    const thumb = source.thumb ? `<img src="${source.thumb}" alt="" draggable="false" />` : `<span class="bin-glyph">${icon(source.kind === "audio" ? "speaker" : "pip")}</span>`;
    card.innerHTML = `<div class="effect-thumb bin-thumb">${thumb}<span class="dur-chip"></span></div><div class="effect-name"></div>`;
    setText(card.querySelector(".dur-chip")!, duration(source.duration));
    setText(card.querySelector(".effect-name")!, source.name);
    card.title = `${source.name}: double-click to add at the playhead, or drag onto the timeline`;
    card.addEventListener("dblclick", () => hooks.place(source.id));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter") hooks.place(source.id);
    });
    card.addEventListener("dragstart", (event) => {
      event.dataTransfer?.setData(hooks.dragMime, source.id);
      if (event.dataTransfer) event.dataTransfer.effectAllowed = "copy";
    });
    return card;
  };

  const syncBin = () => {
    const sources = allSources();
    for (const source of sources) {
      let card = cards.get(source.id);
      if (!card) {
        card = makeCard(source);
        cards.set(source.id, card);
        bin.append(card);
      }
      card.classList.toggle("is-loading", !!source.pending);
    }
    setText(count, `${sources.length} items`);
  };

  const selectedClip = () => {
    const id = engine.snapshot.selectedClipId;
    return id ? engine.findClip(id)?.clip ?? null : null;
  };
  const picture = (clip: ReturnType<typeof selectedClip>) => !!clip && (clip.kind === "video" || clip.kind === "image");

  const lookCards = new Map<string, HTMLElement>();
  const stills = new Map<string, ImageData>();
  let stillFor = "";
  const scratch = document.createElement("canvas");
  scratch.width = STILL_W;
  scratch.height = STILL_H;
  const sctx = scratch.getContext("2d", { willReadFrequently: true })!;
  for (const look of LOOKS) {
    const card = document.createElement("button");
    card.className = "effect-card fx-card";
    card.dataset.look = look.id;
    card.innerHTML = `<div class="effect-thumb bin-thumb"><canvas width="${STILL_W}" height="${STILL_H}"></canvas></div><div class="effect-name">${look.name}</div>`;
    card.addEventListener("click", () => {
      const clip = selectedClip();
      if (!picture(clip)) {
        hooks.say("Select a video or image clip first");
        return;
      }
      engine.dispatch("clip.effect", { clipId: clip!.id, effectId: clip!.effectId === look.id ? null : look.id });
    });
    lookCards.set(look.id, card);
    lookGrid.append(card);
  }

  const paintLooks = (still: ImageData) => {
    for (const look of LOOKS) {
      const lattice = latticeFor({ id: "", kind: "video", label: "", start: 0, duration: 1, effectId: look.id });
      const copy = new ImageData(new Uint8ClampedArray(still.data), STILL_W, STILL_H);
      if (lattice) applyLattice(copy.data, lattice);
      lookCards.get(look.id)!.querySelector("canvas")!.getContext("2d")!.putImageData(copy, 0, 0);
    }
  };

  const loadStill = (source: Source) => {
    if (stillFor === source.id || !source.thumb) return;
    stillFor = source.id;
    const cached = stills.get(source.id);
    if (cached) {
      paintLooks(cached);
      return;
    }
    const image = new Image();
    image.addEventListener("load", () => {
      sctx.drawImage(image, 0, 0, STILL_W, STILL_H);
      const data = sctx.getImageData(0, 0, STILL_W, STILL_H);
      stills.set(source.id, data);
      if (stillFor === source.id) paintLooks(data);
    }, { once: true });
    image.src = source.thumb;
  };

  const syncLooks = () => {
    const clip = selectedClip();
    const source = picture(clip) ? getSource(clip!.mediaId) : allSources().find((s) => s.kind === "video" && s.thumb);
    if (source) loadStill(source);
    for (const [id, card] of lookCards) card.classList.toggle("is-active", clip?.effectId === id);
  };

  const trCards = new Map<string, HTMLElement>();
  const swatch = (card: HTMLElement) => {
    const style = getComputedStyle(document.documentElement);
    const canvas = card.querySelector("canvas")!;
    drawSwatch(canvas.getContext("2d")!, card.dataset.tr!, canvas.width, canvas.height, style.getPropertyValue("--tag-video").trim() || "gray", style.getPropertyValue("--tag-text").trim() || "white");
  };
  for (const kind of TRANSITION_KINDS) {
    const card = document.createElement("button");
    card.className = "effect-card trans-card";
    card.dataset.tr = kind;
    card.innerHTML = `<div class="effect-thumb has-glyph"><canvas width="${STILL_W}" height="${STILL_H}"></canvas></div><div class="effect-name">${kind === "dip" ? "Dip to black" : title(kind)}</div>`;
    card.addEventListener("click", () => {
      const clip = selectedClip();
      if (!picture(clip)) {
        hooks.say("Select a video or image clip first");
        return;
      }
      engine.dispatch("clip.transition", { clipId: clip!.id, transition: clip!.transitionIn?.type === kind ? null : { type: kind, duration: clip!.transitionIn?.duration ?? 1 } });
    });
    trCards.set(kind, card);
    trGrid.append(card);
    swatch(card);
  }
  const syncTransitions = () => {
    const clip = selectedClip();
    for (const [id, card] of trCards) card.classList.toggle("is-active", clip?.transitionIn?.type === id);
  };
  const repaintSwatches = () => {
    for (const card of trCards.values()) swatch(card);
  };

  element.querySelector(".pane-tab-strip")!.addEventListener("click", (event) => {
    const tab = (event.target as HTMLElement).closest<HTMLElement>("[data-tab]");
    if (!tab) return;
    for (const node of element.querySelectorAll<HTMLElement>(".pane-tab")) node.classList.toggle("is-active", node === tab);
    for (const view of element.querySelectorAll<HTMLElement>(".media-body")) {
      const hidden = view.dataset.view !== tab.dataset.tab;
      if (view.hidden !== hidden) view.hidden = hidden;
    }
  });
  ref("open").addEventListener("click", hooks.openFiles);

  onSources(() => {
    syncBin();
    syncLooks();
  });
  engine.subscribe((_s, changed) => {
    if (changed === "clips" || changed === "clip-selection") {
      syncLooks();
      syncTransitions();
    }
  });
  document.addEventListener("grade-demo:theme", repaintSwatches);
  syncBin();
  syncLooks();
  syncTransitions();
  return element;
}
