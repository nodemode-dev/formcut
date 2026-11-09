import "../../../frontend/src/styles/tokens.css";
import "../../../frontend/src/styles/themes.css";
import "../../../frontend/src/styles/app.css";
import "../../../frontend/src/styles/containers.css";
import "../../../frontend/src/styles/creator.css";
import "../../../demo/src/demo.css";
import "./grade.css";
import { ProjectEngine } from "../../../frontend/src/engine/project";
import { blankProject } from "../../../frontend/src/engine/seed";
import type { Clip, ProjectState } from "../../../frontend/src/engine/types";
import { icon } from "../../../frontend/src/ui/icons";
import { allSources, getSource, installFilm, loadFile, loadFilmItem } from "../../../demo/src/media";
import { buildTimeline } from "../../../demo/src/timeline";
import { captionClips, parseCaptions } from "../../../demo/src/captions";
import { download, exportPng, exportProject, pickMime, renderVideo } from "../../../demo/src/exporter";
import type { RenderControl } from "../../../demo/src/exporter";
import { GradeMixer } from "./mixer";
import { buildPreview } from "./preview";
import { buildLibrary } from "./library";
import { buildInspector } from "./inspector";
import { cubeName, latticeFor, parseCube, registerCube } from "./grade";
import { defaultMask } from "./render";
import { FILM_LENGTH, FILM_OPEN_AT, filmTimelines } from "../../../frontend/src/demos/last-light";

const THEMES: Array<[string, string]> = [
  ["studio", "Studio"], ["formcut-dark", "FormCut Dark"], ["obsidian", "Obsidian"], ["graphite", "Graphite"],
  ["github-dark", "Slate Code"], ["midnight-blue", "Midnight Blue"], ["indigo", "Indigo"], ["forest", "Forest"],
  ["ember", "Ember"], ["high-contrast", "High Contrast"], ["light", "Light"], ["sand", "Sand"],
];

const FORMAT = { width: 1280, height: 720, fps: 30 };
const STORAGE_KEY = "formcut.demo.theme";

const engine = new ProjectEngine(blankProject(FORMAT));
const mixer = new GradeMixer();
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

function loadFilm(): void {
  const timelines = filmTimelines();
  engine.dispatch("project.load", { ...blankProject(FORMAT), title: "Last Light", timelines, saved: true });
  engine.dispatch("transport.seek", FILM_OPEN_AT);
  engine.dispatch("clip.select", timelines[0].tracks[2].clips[0].id);
  defaultStatus = "graded film";
  say(defaultStatus);
}

const endOf = (trackIndex: number): number => {
  const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
  return Math.max(0, ...(tracks[trackIndex]?.clips ?? []).map((c) => c.start + c.duration));
};

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
  const length = kind === "video" ? Math.min(source.duration, 600) : kind === "image" ? 4 : source.duration;
  const clip: Clip = {
    id: crypto.randomUUID(), kind, label: source.name, mediaId: source.id,
    start: Math.round((time ?? endOf(index)) * 100) / 100, duration: Math.round(length * 100) / 100,
  };
  engine.dispatch("clips.add", { entries: [{ trackIndex: index, clip }] });
  say(`Added ${source.name}`);
}

function windowOnOverlay(clipId: string): void {
  const found = engine.findClip(clipId);
  if (!found || (found.clip.kind !== "video" && found.clip.kind !== "image")) return;
  const original = found.clip;
  const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
  const overlay = tracks.findIndex((track) => track.name === "Overlay");
  if (overlay < 0) return;
  const head = engine.snapshot.playhead;
  const start = Math.round(Math.min(Math.max(head, original.start), original.start + Math.max(0, original.duration - 2)) * 100) / 100;
  const length = Math.round(Math.min(original.duration - (start - original.start), 4) * 100) / 100;
  const copy: Clip = structuredClone(original);
  copy.id = crypto.randomUUID();
  copy.label = `${original.label} window`;
  copy.start = start;
  copy.duration = length;
  copy.sourceIn = (original.sourceIn ?? 0) + (start - original.start) * (original.speed ?? 1);
  copy.transitionIn = undefined;
  copy.speedCurve = undefined;
  copy.keyframes = undefined;
  copy.fadeIn = 0.4;
  copy.fadeOut = 0.4;
  copy.mask = defaultMask("ellipse");
  copy.colour = { ...(original.colour ?? {}), exposure: (original.colour?.exposure ?? 0) + 0.5, contrast: (original.colour?.contrast ?? 0) + 8 };
  engine.dispatch("clips.add", { entries: [{ trackIndex: overlay, clip: copy }] });
  engine.dispatch("clip.select", copy.id);
  say("Window added on the Overlay track: reshape it in the Mask tab");
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

function applyCube(name: string, text: string): void {
  const id = engine.snapshot.selectedClipId;
  const clip = id ? engine.findClip(id)?.clip : null;
  if (!clip || (clip.kind !== "video" && clip.kind !== "image")) {
    say("Select a video or image clip first, then drop the .cube file");
    return;
  }
  parseCube(text);
  engine.dispatch("clip.creator", { clipId: clip.id, patch: { lutId: registerCube(name, text) } });
  say(`LUT ${name} applied to ${clip.label}`);
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
      else if (name.endsWith(".cube")) applyCube(file.name.replace(/\.cube$/i, ""), await file.text());
      else if (name.endsWith(".json")) loadProjectText(await file.text());
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

function exportCube(): void {
  const id = engine.snapshot.selectedClipId;
  const clip = id ? engine.findClip(id)?.clip : null;
  if (!clip || (clip.kind !== "video" && clip.kind !== "image")) {
    say("Select a video or image clip to bake its grade");
    return;
  }
  const table = latticeFor(clip);
  if (!table) {
    say("This clip has no grade to bake");
    return;
  }
  const rows: string[] = [`TITLE "${clip.label} grade"`, "LUT_3D_SIZE 33", "DOMAIN_MIN 0 0 0", "DOMAIN_MAX 1 1 1"];
  for (let i = 0; i < table.length; i += 3) rows.push(`${table[i].toFixed(6)} ${table[i + 1].toFixed(6)} ${table[i + 2].toFixed(6)}`);
  download(new Blob([`${rows.join("\n")}\n`], { type: "text/plain" }), `${clip.label.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-grade.cube`);
  say(`Baked ${clip.label} into a 33 point 3D LUT`);
}

const app = document.getElementById("app")!;
const bar = document.createElement("header");
bar.className = "titlebar";
bar.innerHTML = `
  <div class="titlebar-left">
    <span class="titlebar-logo" aria-hidden="true">${icon("logo")}</span>
    <button class="menu-item" data-act="open">Open files</button>
    <button class="menu-item" data-act="project">Open project</button>
    <button class="menu-item" data-act="sample">Graded film</button>
    <button class="menu-item" data-act="undo">Undo</button>
    <button class="menu-item" data-act="redo">Redo</button>
  </div>
  <div class="titlebar-center">
    <span class="project-title" data-ref="title">Last Light</span>
    <span class="save-state" data-ref="status" role="status">loading media</span>
  </div>
  <div class="titlebar-right">
    <nav class="demo-links" aria-label="The three demos"><a href="../../demo/index.html">Edit</a><a href="./index.html" aria-current="page">Grade</a><a href="../deliver/index.html">Deliver</a></nav>
    <select class="mini-select" data-ref="theme" aria-label="Theme">${THEMES.map(([id, name]) => `<option value="${id}">${name}</option>`).join("")}</select>
    <div class="export-wrap">
      <button class="btn-export" data-ref="export" aria-haspopup="true" aria-expanded="false">${icon("export")}<span data-ref="export-label">Export</span></button>
      <div class="export-menu" data-ref="export-menu" hidden>
        <button data-export="video">Video, WebM (real time)</button>
        <button data-export="png">Current frame, PNG</button>
        <button data-export="cube">Selected clip grade, 3D LUT (.cube)</button>
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

const library = buildLibrary(engine, { openFiles: () => mediaInput.click(), place: (id) => place(id, engine.snapshot.playhead), dragMime: timeline.dragMime, say });
const inspector = buildInspector(engine, { windowOnOverlay, say });

const workspace = document.createElement("main");
workspace.className = "workspace";
workspace.append(library, preview.element, inspector, timeline.element);

const dropVeil = document.createElement("div");
dropVeil.className = "demo-drop";
dropVeil.hidden = true;
dropVeil.textContent = "Drop video, audio, images, a .cube LUT, captions or a project";

const mediaInput = document.createElement("input");
mediaInput.type = "file";
mediaInput.multiple = true;
mediaInput.accept = "video/*,audio/*,image/*,.cube,.srt,.vtt";
mediaInput.hidden = true;
const projectInput = document.createElement("input");
projectInput.type = "file";
projectInput.accept = ".json,application/json";
projectInput.hidden = true;
for (const input of [mediaInput, projectInput]) {
  input.addEventListener("change", () => {
    if (input.files) void handleFiles(input.files);
    input.value = "";
  });
}

app.append(bar, workspace, dropVeil, mediaInput, projectInput);

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
    download(blob, `${titleEl.textContent?.replace(/[^a-z0-9]+/gi, "-").toLowerCase() || "formcut-grade"}.webm`);
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
  } else if (kind === "cube") exportCube();
  else if (kind === "json") {
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
    document.dispatchEvent(new Event("grade-demo:theme"));
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
    if (["graded film", "project opened"].includes(status.textContent ?? "")) status.textContent = "edited";
  }
});

Object.defineProperty(window, "formcutGrade", { value: { engine, mixer, sources: allSources, cubeName, FILM_LENGTH } });

async function openFilm(): Promise<void> {
  const items = await installFilm();
  if (!items) {
    defaultStatus = "the film's media did not load";
    say(defaultStatus);
    return;
  }
  loadFilm();
  timeline.fit();
  const first = ["grade-01", "grade-music"];
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
  defaultStatus = failed ? `${failed} media files did not load` : "graded film";
  say(defaultStatus);
  preview.redraw();
}

void openFilm();
