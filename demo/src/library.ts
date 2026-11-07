import type { ProjectEngine } from "../../frontend/src/engine/project";
import { icon } from "../../frontend/src/ui/icons";
import { allSources, onSources } from "./media";
import type { Source } from "./media";
import { EFFECTS, TRANSITIONS } from "./render";
import { SAMPLE_CAPTIONS } from "./captions";

export interface LibraryHooks {
  openFiles: () => void;
  place: (id: string) => void;
  addTitle: (text: string) => void;
  importCaptions: (text: string) => void;
  openCaptionFile: () => void;
  exportCaptions: () => void;
  dragMime: string;
}

const TABS: Array<[string, string]> = [["media", "Media"], ["effects", "Effects"], ["transitions", "Transitions"], ["titles", "Titles"]];

export function buildLibrary(engine: ProjectEngine, hooks: LibraryHooks, say: (text: string) => void): HTMLElement {
  const element = document.createElement("section");
  element.className = "pane pane-media";
  element.innerHTML = `
    <div class="pane-tabs">
      <div class="pane-tab-strip">${TABS.map(([key, label], index) => `<button class="pane-tab${index === 0 ? " is-active" : ""}" data-tab="${key}">${label}</button>`).join("")}</div>
    </div>
    <div class="media-body" data-view="media">
      <div class="media-main">
        <div class="bin-toolbar">
          <button class="tool-chip" data-ref="open">${icon("plus")}Add files</button>
          <span class="fx-status" data-ref="count"></span>
        </div>
        <div class="card-grid bin-grid" data-ref="bin"></div>
        <p class="demo-hint">Drop a video, audio or image file anywhere on this page. Files are read in the browser and never uploaded.</p>
      </div>
    </div>
    <div class="media-body" data-view="effects" hidden>
      <div class="media-main">
        <div class="fx-status" data-ref="fx-status">Select a clip, then pick an effect to switch it on or off.</div>
        <div class="card-grid" data-ref="fx-grid"></div>
      </div>
    </div>
    <div class="media-body" data-view="transitions" hidden>
      <div class="media-main">
        <div class="fx-status" data-ref="tr-status">Select a clip that follows another on its track, then pick how it comes in.</div>
        <div class="card-grid" data-ref="tr-grid"></div>
      </div>
    </div>
    <div class="media-body" data-view="titles" hidden>
      <div class="media-main">
        <div class="text-add-panel">
          <div class="text-add-hint">Add a title at the playhead on the Titles track.</div>
          <div class="search-field"><input data-ref="title-text" value="Your title" aria-label="Title text" /></div>
          <button class="tool-chip" data-ref="add-title">${icon("plus")}Add title</button>
          <div class="text-add-hint">Captions: import an .srt or .vtt file, try the sample, or export the text clips as .srt.</div>
          <div class="demo-row">
            <button class="tool-chip" data-ref="cap-open">${icon("captions")}Import file</button>
            <button class="tool-chip" data-ref="cap-sample">Sample captions</button>
            <button class="tool-chip" data-ref="cap-export">${icon("export")}Export .srt</button>
          </div>
        </div>
      </div>
    </div>`;
  const ref = <T extends HTMLElement>(name: string) => element.querySelector<T>(`[data-ref="${name}"]`)!;
  const bin = ref("bin");
  const count = ref("count");
  const fxGrid = ref("fx-grid");
  const trGrid = ref("tr-grid");
  const cards = new Map<string, HTMLElement>();
  let activeSource: string | null = null;

  const setText = (node: HTMLElement, value: string) => {
    if (node.textContent !== value) node.textContent = value;
  };
  const duration = (value: number, kind: string) => (kind === "video" && value >= 60 ? "live" : `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`);

  const makeCard = (source: Source): HTMLElement => {
    const card = document.createElement("div");
    card.className = "effect-card bin-card";
    card.dataset.media = source.id;
    card.draggable = true;
    card.tabIndex = 0;
    const thumb = source.thumb
      ? `<img src="${source.thumb}" alt="" draggable="false" />`
      : `<span class="bin-glyph">${icon(source.kind === "audio" ? "speaker" : "pip")}</span>`;
    card.innerHTML = `<div class="effect-thumb bin-thumb">${thumb}<span class="dur-chip"></span></div><div class="effect-name"></div>`;
    setText(card.querySelector(".dur-chip")!, duration(source.duration, source.kind));
    setText(card.querySelector(".effect-name")!, source.name);
    card.title = `${source.name}: double-click to add at the playhead, or drag onto the timeline`;
    card.addEventListener("click", () => {
      activeSource = source.id;
      for (const [id, node] of cards) node.classList.toggle("is-active", id === source.id);
      document.dispatchEvent(new CustomEvent("formcut-demo:source", { detail: source.id }));
    });
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
      card.classList.toggle("is-active", source.id === activeSource);
    }
    setText(count, `${sources.length} items`);
  };

  const selectedClip = () => {
    const id = engine.snapshot.selectedClipId;
    return id ? engine.findClip(id)?.clip ?? null : null;
  };

  const fxCards = new Map<string, HTMLElement>();
  const sample = () => allSources().find((s) => s.kind === "video" && s.thumb)?.thumb ?? "";
  for (const fx of EFFECTS) {
    const card = document.createElement("button");
    card.className = "effect-card fx-card";
    card.dataset.fx = fx.id;
    card.innerHTML = `<div class="effect-thumb bin-thumb"><img alt="" draggable="false" /></div><div class="effect-name">${fx.name}</div>`;
    card.addEventListener("click", () => {
      const clip = selectedClip();
      if (!clip || clip.kind === "audio") {
        say("Select a picture, video or title clip first");
        return;
      }
      const list = (clip.effects ?? []).map((entry) => ({ ...entry }));
      const at = list.findIndex((entry) => entry.id === fx.id);
      if (at >= 0) list.splice(at, 1);
      else list.push({ id: fx.id, amount: fx.id === "hue" ? 25 : 60 });
      engine.dispatch("clip.effects", { clipId: clip.id, effects: list });
    });
    fxCards.set(fx.id, card);
    fxGrid.append(card);
  }
  const previewFilter: Record<string, string> = {
    blur: "blur(3px)", grayscale: "grayscale(1)", sepia: "sepia(1)", invert: "invert(1)", hue: "hue-rotate(120deg)", pixelate: "contrast(1.4) saturate(1.5)",
  };
  const syncFx = () => {
    const clip = selectedClip();
    const on = new Set((clip?.effects ?? []).filter((e) => e.enabled !== false).map((e) => e.id));
    for (const [id, card] of fxCards) {
      card.classList.toggle("is-active", on.has(id));
      const img = card.querySelector("img")!;
      const url = sample();
      if (url && img.getAttribute("src") !== url) img.setAttribute("src", url);
      if (img.style.filter !== previewFilter[id]) img.style.filter = previewFilter[id];
    }
  };

  const trCards = new Map<string, HTMLElement>();
  for (const tr of TRANSITIONS) {
    const card = document.createElement("button");
    card.className = "effect-card trans-card";
    card.dataset.tr = tr.id;
    card.innerHTML = `<div class="effect-thumb has-glyph"><span class="trans-demo" data-kind="${tr.id}"></span></div><div class="effect-name">${tr.name}</div>`;
    card.addEventListener("click", () => {
      const clip = selectedClip();
      if (!clip || clip.kind === "audio") {
        say("Select a picture, video or title clip first");
        return;
      }
      const same = clip.transitionIn?.type === tr.id;
      engine.dispatch("clip.transition", { clipId: clip.id, transition: same ? null : { type: tr.id, duration: 1 } });
    });
    trCards.set(tr.id, card);
    trGrid.append(card);
  }
  const syncTransitions = () => {
    const clip = selectedClip();
    for (const [id, card] of trCards) card.classList.toggle("is-active", clip?.transitionIn?.type === id);
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
  ref("add-title").addEventListener("click", () => hooks.addTitle(ref<HTMLInputElement>("title-text").value || "Title"));
  ref("cap-open").addEventListener("click", hooks.openCaptionFile);
  ref("cap-sample").addEventListener("click", () => hooks.importCaptions(SAMPLE_CAPTIONS));
  ref("cap-export").addEventListener("click", hooks.exportCaptions);

  onSources(() => {
    syncBin();
    syncFx();
  });
  engine.subscribe((_s, changed) => {
    if (changed === "clips" || changed === "clip-selection") {
      syncFx();
      syncTransitions();
    }
  });
  syncBin();
  syncFx();
  syncTransitions();
  return element;
}
