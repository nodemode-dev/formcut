import "../../frontend/src/styles/tokens.css";
import "../../frontend/src/styles/themes.css";
import "../../frontend/src/styles/app.css";
import "../../frontend/src/styles/containers.css";
import "../../frontend/src/styles/creator.css";
import "./demo.css";
import { ProjectEngine } from "../../frontend/src/engine/project";
import { blankProject } from "../../frontend/src/engine/seed";
import { defaultTextStyle } from "../../frontend/src/engine/types";
import type { Clip, ProjectState, Track } from "../../frontend/src/engine/types";
import { icon } from "../../frontend/src/ui/icons";
import { allSources, getSource, installSamples, loadFile } from "./media";
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
  engine.dispatch("project.load", { ...blankProject(FORMAT), title: "Sample project", timelines: sampleTimelines(), saved: true });
  engine.dispatch("transport.seek", 2);
  defaultStatus = "sample project";
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
    <button class="menu-item" data-act="sample">Sample project</button>
    <button class="menu-item" data-act="undo">Undo</button>
    <button class="menu-item" data-act="redo">Redo</button>
  </div>
  <div class="titlebar-center">
    <span class="project-title" data-ref="title">Sample project</span>
    <span class="save-state" data-ref="status" role="status">sample project</span>
  </div>
  <div class="titlebar-right">
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
    if (status.textContent === "sample project" || status.textContent === "project opened") status.textContent = "edited";
  }
});

Object.defineProperty(window, "formcutDemo", { value: { engine, mixer, sources: allSources, place, importCaptions, loadSample } });

void installSamples().then(() => {
  loadSample();
  timeline.fit();
});
