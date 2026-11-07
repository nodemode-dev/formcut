import "../../frontend/src/styles/tokens.css";
import "../../frontend/src/styles/themes.css";
import "../../frontend/src/styles/app.css";
import "../../frontend/src/styles/containers.css";
import "../../frontend/src/styles/creator.css";
import "./demo.css";
import { ProjectEngine } from "../../frontend/src/engine/project";
import { blankProject } from "../../frontend/src/engine/seed";
import { defaultTextStyle } from "../../frontend/src/engine/types";
import type { Clip, ProjectState, TextStyle, Track } from "../../frontend/src/engine/types";
import { icon } from "../../frontend/src/ui/icons";
import { allSources, getSource, installFilm, installSamples, loadFile, loadFilmItem } from "./media";
import type { FilmItem } from "./media";
import { Mixer } from "./mixer";
import { LumaScope } from "./scope";
import { buildPreview } from "./preview";
import { buildTimeline } from "./timeline";
import { buildLibrary } from "./library";
import { buildInspector } from "./inspector";
import { captionClips, parseCaptions } from "./captions";
import { exportPng, exportProject, exportSrt, download, pickMime, renderVideo } from "./exporter";
import type { RenderControl } from "./exporter";

const THEMES: Array<[string, string]> = [
  ["studio", "Studio"], ["formcut-dark", "FormCut Dark"], ["obsidian", "Obsidian"], ["graphite", "Graphite"],
  ["github-dark", "Slate Code"], ["midnight-blue", "Midnight Blue"], ["indigo", "Indigo"], ["forest", "Forest"],
  ["ember", "Ember"], ["high-contrast", "High Contrast"], ["light", "Light"], ["sand", "Sand"],
];

const FORMAT = { width: 1280, height: 720, fps: 30 };
const TRACK_NAMES = ["Titles", "Overlay", "Video", "Audio"];

const newTracks = (): Track[] => TRACK_NAMES.map((name) => ({ id: crypto.randomUUID(), name, clips: [] }));

function sampleTimelines(): ProjectState["timelines"] {
  const make = (kind: Clip["kind"], label: string, mediaId: string | undefined, start: number, duration: number, extra: Partial<Clip> = {}): Clip =>
    ({ id: crypto.randomUUID(), kind, label, mediaId, start, duration, ...extra });
  const tracks = newTracks();
  tracks[0].clips.push(
    make("text", "FormCut", undefined, 0.5, 3.6, { fadeIn: 0.4, fadeOut: 0.5, textStyle: { ...defaultTextStyle("FormCut"), size: 13, outlineColor: "black", outlineWidth: 6, shadowBlur: 10, shadowColor: "black" } }),
    make("text", "Cut, grade, caption, export.", undefined, 5.9, 3.6, { fadeIn: 0.3, fadeOut: 0.4, transform: { scale: 100, posX: 0, posY: 30, rotation: 0, width: 100, height: 100, opacity: 100, blendMode: "Normal", flipH: false }, textStyle: { ...defaultTextStyle("Cut, grade, caption, export."), size: 6, outlineColor: "black", outlineWidth: 5 } }),
  );
  tracks[1].clips.push(make("image", "Gradient plate", "gen-plate", 8.6, 5.2, {
    fadeIn: 0.5, fadeOut: 0.5,
    transform: { scale: 34, posX: 30, posY: -26, rotation: 0, width: 100, height: 100, opacity: 92, blendMode: "Normal", flipH: false },
  }));
  tracks[2].clips.push(
    make("video", "Aurora waves", "gen-waves", 0, 5.5, { sourceIn: 2 }),
    make("video", "Rising embers", "gen-embers", 5.5, 5, { sourceIn: 10, transitionIn: { type: "crossfade", duration: 0.9 }, colour: { contrast: 12, saturation: 18 } }),
    make("video", "Test pattern", "gen-pattern", 10.5, 4, { transitionIn: { type: "dip", duration: 0.8 }, colour: { temperature: 7800, vignette: 35 } }),
  );
  tracks[3].clips.push(
    make("audio", "Chord loop", "gen-tone", 0, 8),
    make("audio", "Chord loop", "gen-tone", 8, 6.5, { fadeOut: 1.2 }),
  );
  return [{ id: crypto.randomUUID(), name: "Timeline 1", tracks }];
}

const FILM_TRACKS = ["Captions", "Titles", "Video", "Audio"];
const FILM_LENGTH = 48;
const FILM_MUSIC_IN = 0;
const FILM_OPEN_AT = 8.2;

function filmTimelines(): ProjectState["timelines"] {
  const make = (kind: Clip["kind"], label: string, mediaId: string | undefined, start: number, duration: number, extra: Partial<Clip> = {}): Clip =>
    ({ id: crypto.randomUUID(), kind, label, mediaId, start, duration, ...extra });
  const pos = (posX: number, posY: number): NonNullable<Clip["transform"]> =>
    ({ scale: 100, posX, posY, rotation: 0, width: 100, height: 100, opacity: 100, blendMode: "Normal", flipH: false });
  const style = (content: string, size: number, extra: Partial<TextStyle> = {}): TextStyle =>
    ({ ...defaultTextStyle(content), size, shadowColor: "black", shadowBlur: 14, ...extra });
  const caption = (text: string, start: number, duration: number): Clip =>
    make("text", text, undefined, start, duration, {
      fadeIn: 0.5, fadeOut: 0.5, transform: pos(0,38),
      textStyle: style(text, 5, { bold: false, outlineColor: "black", outlineWidth: 6, shadowBlur: 8 }),
    });
  const tag = (heading: string, detail: string, start: number): Clip =>
    make("text", heading, undefined, start, 3.6, {
      fadeIn: 0.4, fadeOut: 0.5, transform: pos(0,27),
      textStyle: style(`${heading}\n${detail}`, 3.3, { align: "left", bold: false, shadowBlur: 0, plateColor: "black", plateOpacity: 0.5 }),
    });
  const tracks: Track[] = FILM_TRACKS.map((name) => ({ id: crypto.randomUUID(), name, clips: [] }));
  tracks[0].clips.push(
    make("text", "A day, dark to dark", undefined, 7.2, 3.6, {
      fadeIn: 0.8, fadeOut: 0.8, transform: pos(0,7),
      textStyle: style("A day in the mountains, from dark to dark", 3.6, { bold: false, shadowBlur: 12 }),
    }),
    caption("Before the light, the sky is crowded.", 1.2, 3.6),
    caption("The first warm light finds the ridges.", 13, 3.6),
    caption("Fog fills the valleys like water.", 17.8, 3.8),
    caption("Snowmelt takes the long way down.", 23.2, 3.8),
    caption("Above it all, a sea of cloud.", 29.2, 4.4),
    caption("A fire to hold the dark back.", 35.8, 3.6),
    caption("And then the sky lights up.", 41.4, 4.4),
  );
  tracks[1].clips.push(
    tag("BEFORE DAWN", "Milky Way over the ridge", 0.9),
    make("text", "High Country", undefined, 6.2, 4.6, {
      fadeIn: 0.9, fadeOut: 0.9, transform: pos(0,-6),
      textStyle: style("HIGH COUNTRY", 11, { shadowBlur: 26 }),
    }),
    tag("MORNING LIGHT", "Snow peaks in amber haze", 12.6),
    tag("ABOVE THE FOG", "Forest ridge, early blue", 17.6),
    tag("MELTWATER", "A stream down a bare slope", 23),
    tag("CLOUD SEA", "Sun over the cloud tops", 28.8),
    tag("NIGHT FIRE", "Embers and flame", 35.6),
    tag("AURORA", "Southern lights over a lake town", 41.1),
    make("text", "Credits", undefined, 45.4, 2.6, {
      fadeIn: 0.5, fadeOut: 0.6, transform: pos(0,0),
      textStyle: style("Footage: Pexels creators. Music: Bach, Goldberg Aria, played by Kimiko Ishizaka (CC0).", 3, { bold: false, shadowBlur: 10 }),
    }),
  );
  tracks[2].clips.push(
    make("video", "Milky Way", "film-01", 0, 5.5, { fadeIn: 1, colour: { exposure: 0.55, contrast: 14, saturation: 14, temperature: 6000, vignette: 28 } }),
    make("video", "Sunrise ridge", "film-02", 5.5, 6.5, { transitionIn: { type: "crossfade", duration: 1.4 }, colour: { contrast: 8, saturation: 12, temperature: 7000, vignette: 22 } }),
    make("video", "Snow peaks", "film-03", 12, 5, { transitionIn: { type: "wipe-right", duration: 0.9 }, colour: { contrast: 6, saturation: 10, vignette: 25 } }),
    make("video", "Fog and forest", "film-04", 17, 5.5, { transitionIn: { type: "crossfade", duration: 1 }, colour: { contrast: 10, saturation: 8, temperature: 6200, vignette: 18 } }),
    make("video", "Waterfall slope", "film-05", 22.5, 5.5, { transitionIn: { type: "zoom", duration: 0.9 }, colour: { contrast: 10, saturation: 12, vignette: 20 } }),
    make("video", "Cloud sea", "film-06", 28, 7, { transitionIn: { type: "crossfade", duration: 1.2 }, colour: { exposure: 0.25, contrast: 10, saturation: 14, vignette: 25 } }),
    make("video", "Campfire", "film-07", 35, 5.5, { transitionIn: { type: "dip", duration: 1 }, colour: { exposure: 0.5, contrast: 6, saturation: 8, vignette: 30 } }),
    make("video", "Aurora", "film-08", 40.5, 7.5, { fadeOut: 1.5, transitionIn: { type: "crossfade", duration: 1.2 }, colour: { contrast: 6, saturation: 8, vignette: 20 } }),
  );
  tracks[3].clips.push(make("audio", "Goldberg Aria (Bach)", "film-music", 0, FILM_LENGTH, { sourceIn: FILM_MUSIC_IN, fadeIn: 1.5, fadeOut: 3.5, volume: 0.9 }));
  return [{ id: crypto.randomUUID(), name: "High Country", tracks }];
}

let film: FilmItem[] | null = null;

const engine = new ProjectEngine(blankProject(FORMAT));
const mixer = new Mixer();
const scope = new LumaScope();
let status: HTMLElement;
let defaultStatus = "sample project";
let statusTimer = 0;

const say = (text: string) => {
  if (status.textContent !== text) status.textContent = text;
  window.clearTimeout(statusTimer);
  statusTimer = window.setTimeout(() => {
    if (status.textContent !== defaultStatus) status.textContent = defaultStatus;
  }, 7000);
};

function loadSample(): void {
  if (film) {
    const timelines = filmTimelines();
    engine.dispatch("project.load", { ...blankProject(FORMAT), title: "High Country", timelines, saved: true });
    engine.dispatch("transport.seek", FILM_OPEN_AT);
    engine.dispatch("clip.select", timelines[0].tracks[2].clips[1].id);
    defaultStatus = "demo film";
  } else {
    engine.dispatch("project.load", { ...blankProject(FORMAT), title: "Sample project", timelines: sampleTimelines(), saved: true });
    engine.dispatch("transport.seek", 2);
    defaultStatus = "sample project";
  }
  say(defaultStatus);
}

const preview = buildPreview(engine, mixer, scope);
const timeline = buildTimeline(engine, say);

function endOf(trackIndex: number): number {
  const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
  return Math.max(0, ...(tracks[trackIndex]?.clips ?? []).map((c) => c.start + c.duration));
}

function place(id: string, time?: number, trackIndex?: number | null): void {
  const source = getSource(id);
  if (!source) return;
  const kind = source.kind;
  const index = trackIndex ?? timeline.trackFor(kind);
  const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
  const audioLane = tracks[index]?.name === "Audio";
  if ((kind === "audio") !== audioLane) {
    say(kind === "audio" ? "Audio goes on the Audio track" : "Pictures and video go above the Audio track");
    return;
  }
  const duration = kind === "video" ? Math.min(source.duration, source.origin === "generated" ? 6 : 600) : kind === "image" ? 4 : source.duration;
  const clip: Clip = {
    id: crypto.randomUUID(), kind, label: source.name, mediaId: source.id,
    start: Math.round((time ?? endOf(index)) * 100) / 100, duration: Math.round(duration * 100) / 100,
  };
  engine.dispatch("clips.add", { entries: [{ trackIndex: index, clip }] });
  say(`Added ${source.name}`);
}

function addTitle(text: string): void {
  const clip: Clip = {
    id: crypto.randomUUID(), kind: "text", label: text, start: Math.round(engine.snapshot.playhead * 100) / 100, duration: 3,
    fadeIn: 0.3, fadeOut: 0.3,
    textStyle: { ...defaultTextStyle(text), size: 9, outlineColor: "black", outlineWidth: 5 },
  };
  engine.dispatch("clips.add", { entries: [{ trackIndex: timeline.trackFor("text"), clip }] });
}

function importCaptions(text: string): void {
  const cues = parseCaptions(text);
  if (!cues.length) {
    say("No captions found in that text");
    return;
  }
  engine.dispatch("captions.add", { trackIndex: timeline.trackFor("text"), clips: captionClips(cues) });
  say(`${cues.length} captions added to the Titles track`);
}

function loadProjectText(text: string): void {
  let doc: { format?: string; title?: string; width?: number; height?: number; fps?: number; timelines?: ProjectState["timelines"] };
  try {
    doc = JSON.parse(text);
  } catch {
    say("That file is not valid JSON");
    return;
  }
  if (doc.format !== "formcut-demo-project" || !Array.isArray(doc.timelines) || !doc.timelines.length) {
    say("That is not a project saved from this demo");
    return;
  }
  engine.dispatch("project.load", {
    ...blankProject({ width: doc.width ?? FORMAT.width, height: doc.height ?? FORMAT.height, fps: doc.fps ?? FORMAT.fps }),
    title: doc.title ?? "Project", timelines: doc.timelines, saved: true,
  });
  const missing = doc.timelines.flatMap((t) => t.tracks.flatMap((tr) => tr.clips)).filter((c) => c.mediaId && !getSource(c.mediaId)).length;
  defaultStatus = missing ? `${missing} clips lack their files` : "project opened";
  say(defaultStatus);
}

async function handleFiles(files: FileList | File[]): Promise<void> {
  for (const file of Array.from(files)) {
    const name = file.name.toLowerCase();
    try {
      if (name.endsWith(".srt") || name.endsWith(".vtt")) importCaptions(await file.text());
      else if (name.endsWith(".json")) loadProjectText(await file.text());
      else {
        say(`Reading ${file.name}`);
        const source = await loadFile(file);
        place(source.id);
        document.dispatchEvent(new CustomEvent("formcut-demo:source", { detail: source.id }));
      }
    } catch (error) {
      say(error instanceof Error ? error.message : `Could not open ${file.name}`);
    }
  }
}

const library = buildLibrary(engine, {
  openFiles: () => mediaInput.click(),
  place: (id) => place(id, engine.snapshot.playhead),
  addTitle,
  importCaptions,
  openCaptionFile: () => captionInput.click(),
  exportCaptions: () => {
    const count = exportSrt(engine);
    say(count ? `Exported ${count} captions` : "No title clips to export");
  },
  dragMime: timeline.dragMime,
}, say);
const inspector = buildInspector(engine, scope);

const app = document.getElementById("app")!;
const bar = document.createElement("header");
bar.className = "titlebar";
bar.innerHTML = `
  <div class="titlebar-left">
    <span class="titlebar-logo" aria-hidden="true">${icon("logo")}</span>
    <button class="menu-item" data-act="open">Open files</button>
    <button class="menu-item" data-act="project">Open project</button>
    <button class="menu-item" data-act="sample">Demo film</button>
    <button class="menu-item" data-act="undo">Undo</button>
    <button class="menu-item" data-act="redo">Redo</button>
  </div>
  <div class="titlebar-center">
    <span class="project-title" data-ref="title">High Country</span>
    <span class="save-state" data-ref="status" role="status">loading media</span>
  </div>
  <div class="titlebar-right">
    <nav class="demo-links" aria-label="The three demos"><a href="./index.html" aria-current="page">Edit</a><a href="../demos/grade/index.html">Grade</a><a href="../demos/deliver/index.html">Deliver</a></nav>
    <select class="mini-select" data-ref="theme" aria-label="Theme">${THEMES.map(([id, name]) => `<option value="${id}">${name}</option>`).join("")}</select>
    <div class="export-wrap">
      <button class="btn-export" data-ref="export" aria-haspopup="true" aria-expanded="false">${icon("export")}<span data-ref="export-label">Export</span></button>
      <div class="export-menu" data-ref="export-menu" hidden>
        <button data-export="video">Video, WebM (real time)</button>
        <button data-export="png">Current frame, PNG</button>
        <button data-export="srt">Captions, SRT</button>
        <button data-export="json">Project, JSON</button>
      </div>
    </div>
  </div>`;
status = bar.querySelector<HTMLElement>('[data-ref="status"]')!;
const titleEl = bar.querySelector<HTMLElement>('[data-ref="title"]')!;
const themeSelect = bar.querySelector<HTMLSelectElement>('[data-ref="theme"]')!;
const exportButton = bar.querySelector<HTMLButtonElement>('[data-ref="export"]')!;
const exportLabel = bar.querySelector<HTMLElement>('[data-ref="export-label"]')!;
const exportMenu = bar.querySelector<HTMLElement>('[data-ref="export-menu"]')!;

const workspace = document.createElement("main");
workspace.className = "workspace";
workspace.append(library, preview.element, inspector, timeline.element);

const dropVeil = document.createElement("div");
dropVeil.className = "demo-drop";
dropVeil.hidden = true;
dropVeil.textContent = "Drop video, audio, images, captions or a project";

const mediaInput = document.createElement("input");
mediaInput.type = "file";
mediaInput.multiple = true;
mediaInput.accept = "video/*,audio/*,image/*";
mediaInput.hidden = true;
const captionInput = document.createElement("input");
captionInput.type = "file";
captionInput.accept = ".srt,.vtt,text/vtt";
captionInput.hidden = true;
const projectInput = document.createElement("input");
projectInput.type = "file";
projectInput.accept = ".json,application/json";
projectInput.hidden = true;
mediaInput.addEventListener("change", () => {
  if (mediaInput.files) void handleFiles(mediaInput.files);
  mediaInput.value = "";
});
captionInput.addEventListener("change", () => {
  if (captionInput.files) void handleFiles(captionInput.files);
  captionInput.value = "";
});
projectInput.addEventListener("change", () => {
  if (projectInput.files) void handleFiles(projectInput.files);
  projectInput.value = "";
});

app.append(bar, workspace, dropVeil, mediaInput, captionInput, projectInput);

let render: RenderControl | null = null;

async function exportVideo(): Promise<void> {
  const mime = pickMime();
  if (!mime) {
    say("This browser has no MediaRecorder with WebM support");
    return;
  }
  if (engine.snapshot.duration < 0.2) {
    say("The timeline is empty");
    return;
  }
  preview.setFull(true);
  exportLabel.textContent = "Cancel render";
  say("Rendering at full size, in real time");
  render = renderVideo(engine, mixer, preview.canvas, mime, (fraction) => say(`Rendering ${Math.round(fraction * 100)}%`));
  const blob = await render.done;
  render = null;
  preview.setFull(false);
  exportLabel.textContent = "Export";
  if (blob && blob.size) {
    download(blob, `${titleEl.textContent?.replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "formcut-demo"}.webm`);
    say(`Exported ${(blob.size / 1048576).toFixed(1)} MB WebM`);
  } else say("Render cancelled");
}

const closeMenu = () => {
  if (!exportMenu.hidden) exportMenu.hidden = true;
  exportButton.setAttribute("aria-expanded", "false");
};

exportButton.addEventListener("click", () => {
  if (render) {
    render.cancel();
    return;
  }
  const open = exportMenu.hidden;
  exportMenu.hidden = !open;
  exportButton.setAttribute("aria-expanded", String(open));
});
exportMenu.addEventListener("click", (event) => {
  const item = (event.target as HTMLElement).closest<HTMLElement>("[data-export]");
  if (!item) return;
  closeMenu();
  const kind = item.dataset.export;
  if (kind === "video") void exportVideo();
  else if (kind === "png") {
    preview.redraw();
    requestAnimationFrame(() => void exportPng(preview.canvas, engine.snapshot.title).then(() => say("Saved the current frame")));
  } else if (kind === "srt") {
    const count = exportSrt(engine);
    say(count ? `Exported ${count} captions` : "No title clips to export");
  } else if (kind === "json") {
    exportProject(engine);
    say("Saved the project file");
  }
});
document.addEventListener("pointerdown", (event) => {
  if (!(event.target as HTMLElement).closest(".export-wrap")) closeMenu();
});

bar.addEventListener("click", (event) => {
  const act = (event.target as HTMLElement).closest<HTMLElement>("[data-act]")?.dataset.act;
  if (act === "open") mediaInput.click();
  else if (act === "project") projectInput.click();
  else if (act === "sample") loadSample();
  else if (act === "undo") engine.dispatch("history.undo");
  else if (act === "redo") engine.dispatch("history.redo");
});

themeSelect.value = document.documentElement.dataset.theme ?? "studio";
if (themeSelect.value !== document.documentElement.dataset.theme) themeSelect.value = "studio";
themeSelect.addEventListener("change", () => {
  document.documentElement.dataset.theme = themeSelect.value;
  try {
    localStorage.setItem("formcut.demo.theme", themeSelect.value);
  } catch {
    return;
  }
  scope.refreshColours();
  preview.redraw();
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
  if (target.closest("input, select, textarea")) return;
  const mod = event.metaKey || event.ctrlKey;
  const key = event.key.toLowerCase();
  if (event.key === "Escape" && render) render.cancel();
  else if (event.key === " ") {
    event.preventDefault();
    engine.dispatch("transport.toggle");
  } else if (mod && key === "z") {
    event.preventDefault();
    engine.dispatch(event.shiftKey ? "history.redo" : "history.undo");
  } else if (mod && key === "y") {
    event.preventDefault();
    engine.dispatch("history.redo");
  } else if (mod && key === "a") {
    event.preventDefault();
    engine.dispatch("clip.select-all");
  } else if (!mod && key === "s") timeline.split();
  else if (!mod && key === "b") timeline.setBlade(true);
  else if (!mod && key === "v") timeline.setBlade(false);
  else if (!mod && key === "i") timeline.markIn();
  else if (!mod && key === "o") timeline.markOut();
  else if (event.key === "Delete" || event.key === "Backspace") {
    event.preventDefault();
    timeline.removeSelected(event.shiftKey);
  } else if (event.key === "ArrowLeft") engine.dispatch("transport.step", -1);
  else if (event.key === "ArrowRight") engine.dispatch("transport.step", 1);
  else if (event.key === "Home") engine.dispatch("transport.home");
  else if (event.key === "End") engine.dispatch("transport.end");
});

engine.subscribe((state, changed) => {
  if (changed === "project" || changed === "clips") {
    if (titleEl.textContent !== state.title) titleEl.textContent = state.title;
  }
  if (changed === "clips" && !state.saved && defaultStatus !== "edited") {
    defaultStatus = "edited";
    if (["sample project", "demo film", "project opened"].includes(status.textContent ?? "")) status.textContent = "edited";
  }
});

Object.defineProperty(window, "formcutDemo", { value: { engine, mixer, sources: allSources, place, importCaptions, loadSample } });

async function openFilm(): Promise<void> {
  const items = await installFilm();
  if (!items) {
    await installSamples();
    loadSample();
    timeline.fit();
    return;
  }
  film = items;
  loadSample();
  timeline.fit();
  const first = ["film-02", "film-music"];
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
  defaultStatus = failed ? `${failed} media files did not load` : "demo film";
  say(defaultStatus);
  preview.redraw();
}

void openFilm();
