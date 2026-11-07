import "../../../frontend/src/styles/tokens.css";
import "../../../frontend/src/styles/themes.css";
import "../../../frontend/src/styles/app.css";
import "../../../frontend/src/styles/containers.css";
import "../../../frontend/src/styles/creator.css";
import "../../../demo/src/demo.css";
import "./deliver.css";
import { ProjectEngine } from "../../../frontend/src/engine/project";
import { blankProject } from "../../../frontend/src/engine/seed";
import type { Clip } from "../../../frontend/src/engine/types";
import { icon } from "../../../frontend/src/ui/icons";
import { allSources, getSource, installFilm, loadFile, loadFilmItem } from "../../../demo/src/media";
import { parseCaptions } from "../../../demo/src/captions";
import { download, pickMime } from "../../../demo/src/exporter";
import { buildTimeline } from "../../../demo/src/timeline";
import { DeliverMixer } from "./audio";
import { captionsOf, chapterList, chapterVtt, toSrt, toVtt } from "./captions";
import { SRT } from "./data";
import { buildExporter } from "./exporter";
import { CAPTION_STYLE, LANDSCAPE, captionClips, filmTimelines } from "./film";
import { buildInspector } from "./inspector";
import { buildLeft } from "./left";
import type { CaptionLook } from "./left";
import { buildPreview } from "./preview";

const THEMES: Array<[string, string]> = [
  ["studio", "Studio"], ["formcut-dark", "FormCut Dark"], ["obsidian", "Obsidian"], ["graphite", "Graphite"],
  ["github-dark", "Slate Code"], ["midnight-blue", "Midnight Blue"], ["indigo", "Indigo"], ["forest", "Forest"],
  ["ember", "Ember"], ["high-contrast", "High Contrast"], ["light", "Light"], ["sand", "Sand"],
];
const STORAGE_KEY = "formcut.demo.theme";
const OPEN_AT = 18;

const engine = new ProjectEngine(blankProject(LANDSCAPE));
const mixer = new DeliverMixer();
let status: HTMLElement;
let defaultStatus = "loading media";
let statusTimer = 0;

const say = (text: string) => {
  if (status.textContent !== text) status.textContent = text;
  window.clearTimeout(statusTimer);
  statusTimer = window.setTimeout(() => {
    if (status.textContent !== defaultStatus) status.textContent = defaultStatus;
  }, 7000);
};

const preview = buildPreview(engine, mixer);
const timeline = buildTimeline(engine, say);

const active = () => engine.snapshot.timelines[engine.snapshot.activeTimeline];
const isVertical = () => engine.snapshot.height > engine.snapshot.width;

function loadFilm(): void {
  const timelines = filmTimelines();
  engine.dispatch("project.load", { ...blankProject(LANDSCAPE), title: "Why I went to the woods", timelines, saved: true });
  engine.dispatch("timeline.activate", 0);
  engine.dispatch("transport.seek", OPEN_AT);
  defaultStatus = "talk edit";
  say(defaultStatus);
}

function activate(index: number): void {
  if (engine.snapshot.activeTimeline === index) return;
  engine.dispatch("timeline.activate", index);
  timeline.fit();
}

function place(id: string, time?: number, trackIndex?: number | null): void {
  const source = getSource(id);
  if (!source) return;
  const tracks = active().tracks;
  const wanted = source.kind === "audio" ? "Music" : "Video";
  const index = trackIndex ?? tracks.findIndex((track) => track.name === wanted);
  const lane = tracks[index]?.name;
  if ((source.kind === "audio") !== (lane === "Voice" || lane === "Music")) {
    say(source.kind === "audio" ? "Audio goes on the Voice or Music track" : "Pictures and video go on the Video track");
    return;
  }
  const length = source.kind === "image" ? 4 : source.duration;
  const end = Math.max(0, ...(tracks[index]?.clips ?? []).map((c) => c.start + c.duration));
  const clip: Clip = { id: crypto.randomUUID(), kind: source.kind, label: source.name, mediaId: source.id, start: Math.round((time ?? end) * 100) / 100, duration: Math.round(length * 100) / 100 };
  engine.dispatch("clips.add", { entries: [{ trackIndex: index, clip }] });
  say(`Added ${source.name}`);
}

const captionsTrack = () => active().tracks.findIndex((track) => track.name === "Captions");

function swapCaptions(next: Clip[], note: string): void {
  const index = captionsTrack();
  if (index < 0) return;
  const old = captionsOf(engine.snapshot).map((clip) => clip.id);
  if (old.length) engine.dispatch("clips.remove", old);
  engine.dispatch("captions.add", { trackIndex: index, clips: next });
  say(note);
}

function importCaptions(text: string): void {
  const cues = parseCaptions(text);
  if (!cues.length) {
    say("No captions found in that text");
    return;
  }
  swapCaptions(captionClips(text, isVertical()), `${cues.length} captions from the file replace the talk captions`);
}

function restyle(look: CaptionLook): void {
  const vertical = isVertical();
  const base = vertical ? 3.4 : CAPTION_STYLE.size;
  const size = base * (look.size === "small" ? 0.78 : look.size === "large" ? 1.32 : 1);
  const posY = look.place === "top" ? (vertical ? -30 : -35) : look.place === "centre" ? 0 : vertical ? 21 : 35;
  const next = captionsOf(engine.snapshot).map((clip) => ({
    ...structuredClone(clip), id: crypto.randomUUID(),
    transform: { ...(clip.transform ?? { scale: 100, posX: 0, posY: 0, rotation: 0, width: 100, height: 100, opacity: 100, blendMode: "Normal", flipH: false }), posY },
    textStyle: { ...clip.textStyle!, size, wordStyle: { mode: look.mode, colour: clip.textStyle?.wordStyle?.colour ?? "#ffd23f" } },
  }));
  swapCaptions(next, `Captions restyled: ${look.mode}, ${look.size}, ${look.place}`);
}

async function handleFiles(files: FileList | File[]): Promise<void> {
  for (const file of Array.from(files)) {
    const name = file.name.toLowerCase();
    try {
      if (name.endsWith(".srt") || name.endsWith(".vtt")) importCaptions(await file.text());
      else {
        say(`Reading ${file.name}`);
        const source = await loadFile(file);
        place(source.id, engine.snapshot.playhead);
      }
    } catch (error) {
      say(error instanceof Error ? error.message : `Could not open ${file.name}`);
    }
  }
}

const app = document.getElementById("app")!;
const bar = document.createElement("header");
bar.className = "titlebar";
bar.innerHTML = `
  <div class="titlebar-left">
    <span class="titlebar-logo" aria-hidden="true">${icon("logo")}</span>
    <button class="menu-item" data-act="open">Open files</button>
    <button class="menu-item" data-act="sample">Talk edit</button>
    <button class="menu-item" data-act="undo">Undo</button>
    <button class="menu-item" data-act="redo">Redo</button>
  </div>
  <div class="titlebar-center">
    <span class="project-title" data-ref="title">Why I went to the woods</span>
    <span class="save-state" data-ref="status" role="status">loading media</span>
  </div>
  <div class="titlebar-right">
    <nav class="demo-links" aria-label="The three demos"><a href="../../demo/index.html">Edit</a><a href="../grade/index.html">Grade</a><a href="./index.html" aria-current="page">Deliver</a></nav>
    <select class="mini-select" data-ref="theme" aria-label="Theme">${THEMES.map(([id, name]) => `<option value="${id}">${name}</option>`).join("")}</select>
    <button class="btn-export" data-ref="export">${icon("export")}<span>Export</span></button>
  </div>`;
status = bar.querySelector<HTMLElement>('[data-ref="status"]')!;
const titleEl = bar.querySelector<HTMLElement>('[data-ref="title"]')!;
const themeSelect = bar.querySelector<HTMLSelectElement>('[data-ref="theme"]')!;

const mediaInput = document.createElement("input");
mediaInput.type = "file";
mediaInput.multiple = true;
mediaInput.accept = "video/*,audio/*,image/*,.srt,.vtt";
mediaInput.hidden = true;
const captionInput = document.createElement("input");
captionInput.type = "file";
captionInput.accept = ".srt,.vtt,text/vtt,text/plain";
captionInput.hidden = true;
for (const input of [mediaInput, captionInput]) {
  input.addEventListener("change", () => {
    if (input.files) void handleFiles(input.files);
    input.value = "";
  });
}

const stamp = () => titleEl.textContent?.replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "talk";

const left = buildLeft(engine, {
  openFiles: () => mediaInput.click(),
  openCaptions: () => captionInput.click(),
  place: (id) => place(id, engine.snapshot.playhead),
  restyle,
  resetCaptions: () => swapCaptions(captionClips(SRT, isVertical()), "Talk captions restored"),
  exportCaptions: (kind) => {
    const clips = captionsOf(engine.snapshot);
    if (!clips.length) {
      say("There are no captions on this timeline");
      return;
    }
    download(new Blob([kind === "srt" ? toSrt(clips) : toVtt(clips)], { type: "text/plain" }), `${stamp()}.${kind}`);
    say(`Saved ${clips.length} captions as .${kind}`);
  },
  exportChapters: (kind) => {
    const marks = active().markers ?? [];
    if (!marks.length) {
      say("Add a chapter first");
      return;
    }
    if (kind === "list") download(new Blob([chapterList(marks)], { type: "text/plain" }), `${stamp()}-chapters.txt`);
    else download(new Blob([chapterVtt(marks, engine.snapshot.duration)], { type: "text/vtt" }), `${stamp()}-chapters.vtt`);
    say(`Saved ${marks.length} chapters`);
  },
  addChapter: () => {
    const at = Math.round(engine.snapshot.playhead * 100) / 100;
    engine.dispatch("marker.add", { t: at, note: `Chapter ${(active().markers ?? []).length + 1}`, colour: "accent" });
    say("Chapter added at the playhead");
  },
  dragMime: timeline.dragMime,
});
const mix = buildInspector(engine, { mixer, say, activate });
const exporter = buildExporter(engine, { mixer, preview, mix, activate, say, mime: pickMime });

const workspace = document.createElement("main");
workspace.className = "workspace";
workspace.append(left, preview.element, mix.element, timeline.element);

const dropVeil = document.createElement("div");
dropVeil.className = "demo-drop";
dropVeil.hidden = true;
dropVeil.textContent = "Drop video, audio, pictures, or captions (.srt, .vtt)";

app.append(bar, workspace, dropVeil, exporter.element, mediaInput, captionInput);

const strip = timeline.element.querySelector<HTMLElement>(".tl-tab-strip")!;
strip.innerHTML = `<button class="tl-tab is-active" data-timeline="0" title="Talk 16:9">Talk 16:9</button><button class="tl-tab" data-timeline="1" title="Vertical 9:16">Vertical 9:16</button>`;
strip.addEventListener("click", (event) => {
  const tab = (event.target as HTMLElement).closest<HTMLElement>("[data-timeline]");
  if (tab) activate(Number(tab.dataset.timeline));
});
const paintTabs = () => {
  const index = engine.snapshot.activeTimeline;
  strip.querySelectorAll<HTMLElement>("[data-timeline]").forEach((node) => node.classList.toggle("is-active", Number(node.dataset.timeline) === index));
};

const ruler = timeline.element.querySelector<HTMLElement>('[data-ref="ruler"]')!;
const holder = document.createElement("div");
holder.className = "tl-markers";
ruler.append(holder);
const flags = new Map<string, { el: HTMLButtonElement; label: HTMLElement }>();
const pixelsPerSecond = (): number => {
  const tick = ruler.querySelectorAll<HTMLElement>(".tick")[1];
  if (!tick || !tick.textContent) return 0;
  const [m, s] = tick.textContent.split(":").map(Number);
  const seconds = m * 60 + s;
  return seconds > 0 ? parseFloat(tick.style.left) / seconds : 0;
};
const paintMarkers = () => {
  const pps = pixelsPerSecond();
  const marks = active().markers ?? [];
  const seen = new Set<string>();
  for (const mark of marks) {
    seen.add(mark.id);
    let flag = flags.get(mark.id);
    if (!flag) {
      const el = document.createElement("button");
      el.className = "tl-marker";
      el.type = "button";
      el.innerHTML = `<span class="tl-marker-label"></span>`;
      el.addEventListener("pointerdown", (event) => event.stopPropagation());
      el.addEventListener("click", () => engine.dispatch("transport.seek", mark.t));
      holder.append(el);
      flag = { el, label: el.children[0] as HTMLElement };
      flags.set(mark.id, flag);
    }
    const x = `${(mark.t * pps).toFixed(1)}px`;
    if (flag.el.style.left !== x) flag.el.style.left = x;
    const note = mark.note ?? "Chapter";
    if (flag.label.textContent !== note) flag.label.textContent = note;
    flag.el.title = `${note}: go to ${mark.t.toFixed(1)} s`;
  }
  for (const [id, flag] of flags) {
    if (seen.has(id)) continue;
    flag.el.remove();
    flags.delete(id);
  }
};
new MutationObserver(paintMarkers).observe(ruler, { attributes: true, attributeFilter: ["style"] });
engine.subscribe((_s, changed) => {
  if (changed === "timeline" || changed === "clips" || changed === "project") {
    paintMarkers();
    paintTabs();
  }
});

let defaultDone = false;
bar.querySelector('[data-ref="export"]')!.addEventListener("click", () => exporter.open());
bar.addEventListener("click", (event) => {
  const act = (event.target as HTMLElement).closest<HTMLElement>("[data-act]")?.dataset.act;
  if (act === "open") mediaInput.click();
  else if (act === "sample") loadFilm();
  else if (act === "undo") engine.dispatch("history.undo");
  else if (act === "redo") engine.dispatch("history.redo");
});

themeSelect.value = document.documentElement.dataset.theme ?? "studio";
if (themeSelect.value !== document.documentElement.dataset.theme) themeSelect.value = "studio";
themeSelect.addEventListener("change", () => {
  document.documentElement.dataset.theme = themeSelect.value;
  try {
    localStorage.setItem(STORAGE_KEY, themeSelect.value);
  } catch {
    return;
  } finally {
    document.dispatchEvent(new Event("deliver-demo:theme"));
    preview.redraw();
  }
});

let dragDepth = 0;
const hasFiles = (event: DragEvent) => !!event.dataTransfer?.types.includes("Files");
window.addEventListener("dragenter", (event) => {
  if (!hasFiles(event)) return;
  dragDepth += 1;
  dropVeil.hidden = false;
});
window.addEventListener("dragleave", (event) => {
  if (!hasFiles(event)) return;
  dragDepth = Math.max(0, dragDepth - 1);
  if (!dragDepth) dropVeil.hidden = true;
});
window.addEventListener("dragover", (event) => {
  if (hasFiles(event)) event.preventDefault();
});
window.addEventListener("drop", (event) => {
  dragDepth = 0;
  dropVeil.hidden = true;
  if (!event.dataTransfer?.files.length) return;
  event.preventDefault();
  void handleFiles(event.dataTransfer.files);
});

document.addEventListener("formcut-demo:place", (event) => {
  const detail = (event as CustomEvent<{ id: string; time: number; track: number | null }>).detail;
  place(detail.id, detail.time, detail.track);
});

document.addEventListener("keydown", (event) => {
  const target = event.target as HTMLElement;
  if (target.closest("input, select, textarea, [role='slider']")) return;
  const mod = event.metaKey || event.ctrlKey;
  const key = event.key.toLowerCase();
  if (event.key === " ") {
    event.preventDefault();
    engine.dispatch("transport.toggle");
  } else if (mod && key === "z") {
    event.preventDefault();
    engine.dispatch(event.shiftKey ? "history.redo" : "history.undo");
  } else if (mod && key === "y") {
    event.preventDefault();
    engine.dispatch("history.redo");
  } else if (!mod && key === "s") timeline.split();
  else if (!mod && key === "b") timeline.setBlade(true);
  else if (!mod && key === "v") timeline.setBlade(false);
  else if (!mod && key === "m") engine.dispatch("marker.add", { t: Math.round(engine.snapshot.playhead * 100) / 100, note: `Chapter ${(active().markers ?? []).length + 1}`, colour: "accent" });
  else if (event.key === "Delete" || event.key === "Backspace") {
    event.preventDefault();
    timeline.removeSelected(event.shiftKey);
  } else if (event.key === "ArrowLeft") engine.dispatch("transport.step", -1);
  else if (event.key === "ArrowRight") engine.dispatch("transport.step", 1);
  else if (event.key === "Home") engine.dispatch("transport.home");
  else if (event.key === "End") engine.dispatch("transport.end");
});

engine.subscribe((state, changed) => {
  if ((changed === "project" || changed === "clips") && titleEl.textContent !== state.title) titleEl.textContent = state.title;
  if (changed === "clips" && !state.saved && defaultStatus !== "edited" && defaultDone) {
    defaultStatus = "edited";
    if (status.textContent === "talk edit") status.textContent = "edited";
  }
});

Object.defineProperty(window, "formcutDeliver", { value: { engine, mixer, sources: allSources, mix, exporter } });

async function openFilm(): Promise<void> {
  const items = await installFilm();
  if (!items) {
    defaultStatus = "the talk's media did not load";
    say(defaultStatus);
    return;
  }
  loadFilm();
  timeline.fit();
  const first = ["talk-01", "talk-voice", "talk-music"];
  const wanted = [...items.filter((item) => first.includes(item.id)), ...items.filter((item) => !first.includes(item.id))];
  let done = 0;
  let failed = 0;
  for (const item of wanted) {
    preview.setNote(`Loading media ${done + 1} of ${wanted.length}`);
    say(`Loading ${item.name}`);
    try {
      await loadFilmItem(item);
    } catch {
      failed += 1;
    }
    done += 1;
    mixer.onFrame();
  }
  preview.setNote("");
  if (!failed) {
    mix.duck();
    engine.dispatch("timeline.activate", 1);
    mix.duck();
    engine.dispatch("timeline.activate", 0);
  }
  defaultStatus = failed ? `${failed} media files did not load` : "talk edit";
  defaultDone = true;
  say(defaultStatus);
  preview.redraw();
  paintMarkers();
}

void openFilm();
