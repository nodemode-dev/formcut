import { formatTimecode } from "../../../frontend/src/engine/project";
import type { ProjectEngine } from "../../../frontend/src/engine/project";
import type { TextStyle } from "../../../frontend/src/engine/types";
import { icon } from "../../../frontend/src/ui/icons";
import { allSources, onSources } from "../../../demo/src/media";
import type { Source } from "../../../demo/src/media";
import { captionsOf } from "./captions";

export interface CaptionLook {
  mode: NonNullable<TextStyle["wordStyle"]>["mode"];
  size: "small" | "medium" | "large";
  place: "top" | "centre" | "bottom";
}

export interface LeftHooks {
  openFiles: () => void;
  openCaptions: () => void;
  place: (id: string) => void;
  restyle: (look: CaptionLook) => void;
  resetCaptions: () => void;
  exportCaptions: (kind: "srt" | "vtt") => void;
  exportChapters: (kind: "list" | "vtt") => void;
  addChapter: () => void;
  dragMime: string;
}

const TABS: Array<[string, string]> = [["media", "Media"], ["captions", "Captions"], ["chapters", "Chapters"]];
const MODES: Array<[string, string]> = [["highlight", "Highlight"], ["pop", "Pop"], ["box", "Box"], ["reveal", "Reveal"], ["rise", "Rise"]];

export function buildLeft(engine: ProjectEngine, hooks: LeftHooks): HTMLElement {
  const element = document.createElement("section");
  element.className = "pane pane-media";
  element.innerHTML = `
    <div class="pane-tabs"><div class="pane-tab-strip">${TABS.map(([key, label], i) => `<button class="pane-tab${i === 0 ? " is-active" : ""}" data-tab="${key}">${label}</button>`).join("")}</div></div>
    <div class="media-body" data-view="media"><div class="media-main">
      <div class="bin-toolbar"><button class="tool-chip" data-ref="open">${icon("plus")}Add files</button><span class="fx-status" data-ref="count"></span></div>
      <div class="card-grid bin-grid" data-ref="bin"></div>
      <p class="demo-hint">Drop a video, audio file, picture, .srt or .vtt anywhere on this page. Files are read in the browser and never uploaded.</p>
    </div></div>
    <div class="media-body" data-view="captions" hidden><div class="media-main">
      <div class="demo-row">
        <button class="tool-chip" data-ref="cap-import">${icon("captions")}Import .srt or .vtt</button>
        <button class="tool-chip" data-ref="cap-reset">Talk captions</button>
      </div>
      <div class="dl-fields">
        <label class="dl-field"><span>Word style</span><select class="mini-select" data-ref="cap-mode" aria-label="Word style">${MODES.map(([id, name]) => `<option value="${id}">${name}</option>`).join("")}</select></label>
        <label class="dl-field"><span>Size</span><select class="mini-select" data-ref="cap-size" aria-label="Caption size"><option value="small">Small</option><option value="medium" selected>Medium</option><option value="large">Large</option></select></label>
        <label class="dl-field"><span>Placement</span><select class="mini-select" data-ref="cap-place" aria-label="Caption placement"><option value="top">Top</option><option value="centre">Centre</option><option value="bottom" selected>Bottom</option></select></label>
      </div>
      <div class="demo-row">
        <button class="tool-chip" data-ref="cap-srt">${icon("export")}Export .srt</button>
        <button class="tool-chip" data-ref="cap-vtt">${icon("export")}Export .vtt</button>
      </div>
      <div class="fx-status" data-ref="cap-count"></div>
      <div class="dl-list" data-ref="cap-list"></div>
    </div></div>
    <div class="media-body" data-view="chapters" hidden><div class="media-main">
      <div class="demo-row">
        <button class="tool-chip" data-ref="ch-add">${icon("plus")}Add at playhead</button>
        <button class="tool-chip" data-ref="ch-list">${icon("export")}Chapter list</button>
        <button class="tool-chip" data-ref="ch-vtt">${icon("export")}Chapters .vtt</button>
      </div>
      <p class="demo-hint">Chapters are markers on the timeline ruler. The list and the .vtt are written from them by this demo.</p>
      <div class="dl-list" data-ref="ch-rows"></div>
    </div></div>`;
  const ref = <T extends HTMLElement>(name: string) => element.querySelector<T>(`[data-ref="${name}"]`)!;
  const setText = (node: HTMLElement, value: string) => {
    if (node.textContent !== value) node.textContent = value;
  };

  const bin = ref("bin");
  const cards = new Map<string, HTMLElement>();
  const duration = (value: number) => `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;
  const makeCard = (source: Source): HTMLElement => {
    const card = document.createElement("div");
    card.className = "effect-card bin-card";
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
    setText(ref("count"), `${sources.length} items`);
  };
  onSources(syncBin);
  syncBin();

  const capRows = new Map<string, { row: HTMLButtonElement; time: HTMLElement; text: HTMLElement }>();
  const capList = ref("cap-list");
  const syncCaptions = () => {
    const state = engine.snapshot;
    const clips = captionsOf(state);
    const seen = new Set<string>();
    clips.forEach((clip, index) => {
      seen.add(clip.id);
      let entry = capRows.get(clip.id);
      if (!entry) {
        const row = document.createElement("button");
        row.className = "dl-row";
        row.type = "button";
        row.innerHTML = `<span class="dl-time"></span><span class="dl-text"></span>`;
        row.addEventListener("click", () => {
          engine.dispatch("transport.seek", clip.start + 0.05);
          engine.dispatch("clip.select", clip.id);
        });
        entry = { row, time: row.children[0] as HTMLElement, text: row.children[1] as HTMLElement };
        capRows.set(clip.id, entry);
        capList.append(row);
      }
      setText(entry.time, formatTimecode(clip.start, state.fps).slice(3, 8));
      setText(entry.text, clip.textStyle?.content ?? clip.label);
      const here = state.playhead >= clip.start && state.playhead < clip.start + clip.duration;
      entry.row.classList.toggle("is-active", here);
      entry.row.classList.toggle("is-selected", state.selection.includes(clip.id));
      if (capList.children[index] !== entry.row) capList.insertBefore(entry.row, capList.children[index] ?? null);
    });
    for (const [id, entry] of capRows) {
      if (seen.has(id)) continue;
      entry.row.remove();
      capRows.delete(id);
    }
    setText(ref("cap-count"), `${clips.length} captions on this timeline`);
  };

  const chRows = ref("ch-rows");
  const chapterEntries = new Map<string, { row: HTMLElement; time: HTMLElement; text: HTMLElement }>();
  const syncChapters = () => {
    const state = engine.snapshot;
    const marks = state.timelines[state.activeTimeline].markers ?? [];
    const seen = new Set<string>();
    marks.forEach((mark, index) => {
      seen.add(mark.id);
      let entry = chapterEntries.get(mark.id);
      if (!entry) {
        const row = document.createElement("div");
        row.className = "dl-row dl-chapter";
        row.innerHTML = `<button class="dl-go" type="button"><span class="dl-time"></span><span class="dl-text"></span></button><button class="iconbtn" type="button" aria-label="Remove chapter" title="Remove chapter">${icon("close")}</button>`;
        const go = row.children[0] as HTMLElement;
        go.addEventListener("click", () => engine.dispatch("transport.seek", mark.t));
        row.children[1].addEventListener("click", () => engine.dispatch("marker.remove", { id: mark.id }));
        entry = { row, time: go.children[0] as HTMLElement, text: go.children[1] as HTMLElement };
        chapterEntries.set(mark.id, entry);
        chRows.append(row);
      }
      setText(entry.time, formatTimecode(mark.t, state.fps).slice(3, 8));
      setText(entry.text, mark.note ?? "Chapter");
      const next = marks[index + 1]?.t ?? Infinity;
      entry.row.classList.toggle("is-active", state.playhead >= mark.t && state.playhead < next);
      if (chRows.children[index] !== entry.row) chRows.insertBefore(entry.row, chRows.children[index] ?? null);
    });
    for (const [id, entry] of chapterEntries) {
      if (seen.has(id)) continue;
      entry.row.remove();
      chapterEntries.delete(id);
    }
  };

  engine.subscribe((_s, changed) => {
    if (changed === "playhead") {
      syncCaptions();
      syncChapters();
    } else if (changed === "clips" || changed === "timeline" || changed === "project" || changed === "clip-selection") {
      syncCaptions();
      syncChapters();
    }
  });
  syncCaptions();
  syncChapters();

  const look = (): CaptionLook => ({
    mode: ref<HTMLSelectElement>("cap-mode").value as CaptionLook["mode"],
    size: ref<HTMLSelectElement>("cap-size").value as CaptionLook["size"],
    place: ref<HTMLSelectElement>("cap-place").value as CaptionLook["place"],
  });
  for (const name of ["cap-mode", "cap-size", "cap-place"]) ref(name).addEventListener("change", () => hooks.restyle(look()));

  const views = element.querySelectorAll<HTMLElement>(".media-body");
  element.querySelector(".pane-tab-strip")!.addEventListener("click", (event) => {
    const tab = (event.target as HTMLElement).closest<HTMLElement>("[data-tab]");
    if (!tab) return;
    element.querySelectorAll<HTMLElement>(".pane-tab").forEach((node) => node.classList.toggle("is-active", node === tab));
    views.forEach((view) => {
      view.hidden = view.dataset.view !== tab.dataset.tab;
    });
  });
  ref("open").addEventListener("click", hooks.openFiles);
  ref("cap-import").addEventListener("click", hooks.openCaptions);
  ref("cap-reset").addEventListener("click", hooks.resetCaptions);
  ref("cap-srt").addEventListener("click", () => hooks.exportCaptions("srt"));
  ref("cap-vtt").addEventListener("click", () => hooks.exportCaptions("vtt"));
  ref("ch-add").addEventListener("click", hooks.addChapter);
  ref("ch-list").addEventListener("click", () => hooks.exportChapters("list"));
  ref("ch-vtt").addEventListener("click", () => hooks.exportChapters("vtt"));
  return element;
}
