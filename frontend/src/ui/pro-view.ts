import type { ProjectEngine } from "../engine/project";
import type { MediaBin, MediaItem } from "../engine/media";
import { fileUrl } from "../engine/media";
import type { Clip } from "../engine/types";
import { t } from "../i18n";
import { LAYOUTS, chooseLayout, currentLayout, keyLabel } from "./keymap";

// The library panel's Pro tab (FilmCraft's Premiere workflow, which formcut lacked): a source monitor where a media
// item is played, marked In and Out (buttons, or I and O while the tab is open), and sent to the timeline at the
// playhead as an Insert (the timeline makes room) or an Overwrite (the target track's range is replaced); and a
// timeline range, marked from the playhead, that Lift removes leaving the gap or Extract removes closing it.
// Engine commands: edit.insert, edit.overwrite, edit.lift, timeline.cut-range.

const PLAYABLE = new Set(["video", "audio"]);

function clock(seconds: number): string {
  const s = Math.max(0, seconds);
  const minutes = Math.floor(s / 60);
  const rest = s - minutes * 60;
  return `${String(minutes).padStart(2, "0")}:${rest.toFixed(2).padStart(5, "0")}`;
}

export function buildProView(engine: ProjectEngine, bin: MediaBin) {
  const el = document.createElement("div");
  el.className = "pro-view";
  el.dataset.view = "pro";
  el.hidden = true;
  el.innerHTML = `
    <div class="pro-head">${t("pro.source")}</div>
    <select class="mini-select pro-pick" data-pro="pick" aria-label="${t("pro.source")}"></select>
    <div class="pro-monitor">
      <img data-pro="frame" alt="" draggable="false" hidden />
      <video data-pro="video" muted playsinline preload="metadata" hidden></video>
      <div class="pro-empty" data-pro="empty">${t("pro.empty")}</div>
    </div>
    <input type="range" class="pro-scrub" data-pro="scrub" min="0" max="1000" value="0" aria-label="${t("pro.scrub")}" />
    <div class="pro-row"><span class="pro-time" data-pro="time">00:00.00</span><span class="pro-marks" data-pro="marks"></span></div>
    <div class="pro-buttons">
      <button type="button" class="chip" data-act="in">${t("pro.markin")}</button>
      <button type="button" class="chip" data-act="out">${t("pro.markout")}</button>
      <button type="button" class="chip" data-act="play">${t("pro.play")}</button>
    </div>
    <div class="prop-row"><span>${t("pro.target")}</span><select class="mini-select" data-pro="track" aria-label="${t("pro.target")}"></select><span class="prop-aux"></span></div>
    <div class="pro-buttons">
      <button type="button" class="chip" data-act="insert">${t("pro.insert")}</button>
      <button type="button" class="chip" data-act="overwrite">${t("pro.overwrite")}</button>
    </div>
    <div class="pro-head">${t("pro.timeline")}</div>
    <div class="pro-row"><span class="pro-marks" data-pro="range"></span></div>
    <div class="pro-buttons">
      <button type="button" class="chip" data-act="tin">${t("pro.markin")}</button>
      <button type="button" class="chip" data-act="tout">${t("pro.markout")}</button>
      <button type="button" class="chip" data-act="lift">${t("pro.lift")}</button>
      <button type="button" class="chip" data-act="extract">${t("pro.extract")}</button>
    </div>
    <div class="pro-head">${t("pro.trim")}</div>
    <div class="prop-row"><span>${t("pro.step")}</span><select class="mini-select" data-pro="step" aria-label="${t("pro.step")}">
      <option value="frame">${t("pro.frame")}</option><option value="frames5">${t("pro.frames5")}</option><option value="second">${t("pro.second")}</option>
    </select><span class="prop-aux"></span></div>
    ${["roll", "slip", "slide"]
      .map(
        (name) => `<div class="pro-trim"><span>${t(`pro.${name}`)}</span><div class="pro-buttons">
          <button type="button" data-trim="${name}" data-dir="-1">${t("pro.earlier")}</button>
          <button type="button" data-trim="${name}" data-dir="1">${t("pro.later")}</button></div></div>`,
      )
      .join("")}
    <p class="pro-status" data-pro="trimstatus"></p>
    <div class="pro-head">${t("pro.interchange")}</div>
    <div class="prop-row"><span>${t("pro.format")}</span><select class="mini-select" data-pro="format" aria-label="${t("pro.format")}">
      <option value="otio">OpenTimelineIO (.otio)</option><option value="fcp7">Final Cut Pro 7 XML, Premiere (.xml)</option><option value="fcpxml">Final Cut Pro X (.fcpxml)</option><option value="edl">CMX 3600 EDL (.edl)</option>
    </select><span class="prop-aux"></span></div>
    <div class="prop-row" data-pro="edlrow" hidden><span>${t("pro.edltrack")}</span><select class="mini-select" data-pro="edltrack" aria-label="${t("pro.edltrack")}"></select><span class="prop-aux"></span></div>
    <div class="pro-buttons">
      <button type="button" data-act="export">${t("pro.export")}</button>
      <button type="button" data-act="import">${t("pro.import")}</button>
    </div>
    <input type="file" data-pro="file" accept=".otio,.xml,.fcpxml,.edl,.json,.txt" hidden />
    <ul class="pro-report" data-pro="report"></ul>
    <div class="pro-head">${t("pro.keys")}</div>
    <div class="prop-row"><span>${t("pro.layout")}</span><select class="mini-select" data-pro="layout" aria-label="${t("pro.layout")}">
      ${Object.entries(LAYOUTS).map(([id, layout]) => `<option value="${id}">${layout.name}</option>`).join("")}
    </select><span class="prop-aux"></span></div>
    <ul class="pro-keys" data-pro="keylist"></ul>
    <p class="devices-hint">${t("pro.hint")}</p>`;
  const pick = el.querySelector<HTMLSelectElement>('[data-pro="pick"]')!;
  const video = el.querySelector<HTMLVideoElement>('[data-pro="video"]')!;
  const empty = el.querySelector<HTMLElement>('[data-pro="empty"]')!;
  const scrub = el.querySelector<HTMLInputElement>('[data-pro="scrub"]')!;
  const time = el.querySelector<HTMLElement>('[data-pro="time"]')!;
  const marks = el.querySelector<HTMLElement>('[data-pro="marks"]')!;
  const range = el.querySelector<HTMLElement>('[data-pro="range"]')!;
  const trackPick = el.querySelector<HTMLSelectElement>('[data-pro="track"]')!;

  const frame = el.querySelector<HTMLImageElement>('[data-pro="frame"]')!;
  let source: MediaItem | null = null;
  let markIn = 0;
  let markOut = 0;
  let rangeIn: number | null = null;
  let rangeOut: number | null = null;
  // the source's position: shown as a frame the engine decodes (any codec it reads); the video element only plays,
  // and only once the window has shown it can (usable)
  let position = 0;
  let usable = false;
  let shown = "";

  const length = () => (source ? Math.max(source.duration, PLAYABLE.has(source.kind) ? 0 : 5) : 0);
  const now = () => (usable && !video.paused ? video.currentTime : position);

  function showFrame() {
    if (!source || source.kind === "audio") return;
    const url = `/api/media/${source.id}/frame?t=${position.toFixed(2)}&width=640`;
    if (url !== shown) {
      shown = url;
      frame.src = url;
    }
  }

  function showMarks() {
    const text = source ? `${t("pro.in")} ${clock(markIn)} · ${t("pro.out")} ${clock(markOut)} · ${(markOut - markIn).toFixed(2)} s` : "";
    if (marks.textContent !== text) marks.textContent = text;
    const span =
      rangeIn !== null && rangeOut !== null
        ? `${t("pro.in")} ${clock(Math.min(rangeIn, rangeOut))} · ${t("pro.out")} ${clock(Math.max(rangeIn, rangeOut))}`
        : `${t("pro.in")} ${rangeIn === null ? "--" : clock(rangeIn)} · ${t("pro.out")} ${rangeOut === null ? "--" : clock(rangeOut)}`;
    if (range.textContent !== span) range.textContent = span;
  }

  function showTime() {
    const at = now();
    const text = clock(at);
    if (time.textContent !== text) time.textContent = text;
    const total = length();
    if (document.activeElement !== scrub && total > 0) scrub.value = String(Math.round((at / total) * 1000));
  }

  function fillPick() {
    const items = bin.all.filter((item) => item.kind === "video" || item.kind === "audio" || item.kind === "image");
    const html = `<option value="">${t("pro.choose")}</option>${items.map((item) => `<option value="${item.id}">${item.name.replace(/</g, "&lt;")}</option>`).join("")}`;
    if (pick.dataset.html !== html) {
      pick.innerHTML = html;
      pick.dataset.html = html;
      pick.value = source && items.some((item) => item.id === source!.id) ? source.id : "";
    }
  }

  function fillTracks() {
    const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
    const html = tracks.map((track, index) => `<option value="${index}">${(track.name || String(index + 1)).replace(/</g, "&lt;")}</option>`).join("");
    if (trackPick.dataset.html !== html) {
      const kept = trackPick.value;
      trackPick.innerHTML = html;
      trackPick.dataset.html = html;
      if (kept && Number(kept) < tracks.length) trackPick.value = kept;
      const keptEdl = edlTrack.value;
      edlTrack.innerHTML = html;
      if (keptEdl && Number(keptEdl) < tracks.length) edlTrack.value = keptEdl;
    }
  }

  function choose(id: string) {
    source = bin.all.find((item) => item.id === id) ?? null;
    markIn = 0;
    markOut = length();
    position = 0;
    usable = false;
    shown = "";
    video.pause();
    video.hidden = true;
    empty.hidden = !!source && source.kind !== "audio";
    frame.hidden = !source || source.kind === "audio";
    if (source && PLAYABLE.has(source.kind)) video.src = fileUrl(source.id);
    else video.removeAttribute("src");
    showFrame();
    if (source) {
      const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
      trackPick.value = String(Math.min(source.kind === "audio" ? 3 : 2, tracks.length - 1));
    }
    showMarks();
    showTime();
  }

  function edit(kind: "edit.insert" | "edit.overwrite", at = engine.snapshot.playhead) {
    if (!source || markOut - markIn <= 0.01) return;
    const clip = {
      id: crypto.randomUUID(),
      kind: source.kind,
      label: source.name,
      start: Math.round(at * 1000) / 1000,
      duration: Math.round((markOut - markIn) * 1000) / 1000,
      mediaId: source.id,
      sourceIn: Math.round(markIn * 1000) / 1000,
      filmstrip: source.kind === "video",
    } as unknown as Clip;
    engine.dispatch(kind, { trackIndex: Number(trackPick.value), clip });
  }

  const formatPick = el.querySelector<HTMLSelectElement>('[data-pro="format"]')!;
  const edlRow = el.querySelector<HTMLElement>('[data-pro="edlrow"]')!;
  const edlTrack = el.querySelector<HTMLSelectElement>('[data-pro="edltrack"]')!;
  const fileInput = el.querySelector<HTMLInputElement>('[data-pro="file"]')!;
  const reportList = el.querySelector<HTMLElement>('[data-pro="report"]')!;
  const LOCAL = { "content-type": "application/json", "x-formcut-local": "1" };

  function showReport(done: string, lines: string[]) {
    reportList.innerHTML = [done, ...lines].map((line, i) => `<li${i ? "" : ' class="is-done"'}>${line.replace(/</g, "&lt;")}</li>`).join("");
  }

  async function exportTimeline() {
    const format = formatPick.value;
    const response = await fetch(`/api/interchange/export/${format}`, {
      method: "POST",
      headers: LOCAL,
      body: JSON.stringify({ project: engine.snapshot, timeline: engine.snapshot.activeTimeline, track: Number(edlTrack.value || 0) }),
    });
    if (!response.ok) {
      showReport(t("pro.failed"), []);
      return;
    }
    const name = /filename="([^"]+)"/.exec(response.headers.get("content-disposition") || "")?.[1] || `timeline.${format}`;
    let report: string[] = [];
    try {
      report = JSON.parse(response.headers.get("x-formcut-report") || "[]");
    } catch {
      report = [];
    }
    const link = document.createElement("a");
    link.href = URL.createObjectURL(await response.blob());
    link.download = name;
    link.click();
    URL.revokeObjectURL(link.href);
    showReport(`${t("pro.exported")} ${name}`, report);
  }

  async function importTimeline(file: File) {
    const format = /\.edl$/i.test(file.name) ? "edl" : /\.fcpxml$/i.test(file.name) ? "fcpxml" : /\.xml$/i.test(file.name) ? "fcp7" : "otio";
    const fps = (engine.snapshot as unknown as { fps?: number }).fps || 30;
    const response = await fetch(`/api/interchange/import/${format}`, { method: "POST", headers: LOCAL, body: JSON.stringify({ text: await file.text(), fps }) });
    const answer = await response.json().catch(() => ({}));
    if (!response.ok) {
      showReport(String(answer.detail || t("pro.failed")), []);
      return;
    }
    try {
      engine.dispatch("timeline.import", { timeline: answer.timeline });
    } catch (error) {
      showReport((error as Error).message, []);
      return;
    }
    showReport(`${t("pro.imported")} ${file.name}`, answer.report || []);
  }

  function act(name: string) {
    if (name === "in") markIn = Math.min(now(), markOut);
    else if (name === "out") markOut = Math.max(now(), markIn);
    else if (name === "play" && usable) {
      if (video.paused) {
        video.currentTime = position;
        video.hidden = false;
        frame.hidden = true;
        void video.play();
      } else {
        video.pause();
        position = video.currentTime;
        video.hidden = true;
        frame.hidden = source?.kind === "audio";
        showFrame();
      }
    }
    else if (name === "insert") edit("edit.insert");
    else if (name === "overwrite") edit("edit.overwrite");
    else if (name === "export") void exportTimeline();
    else if (name === "import") fileInput.click();
    else if (name === "tin") rangeIn = engine.snapshot.playhead;
    else if (name === "tout") rangeOut = engine.snapshot.playhead;
    else if ((name === "lift" || name === "extract") && rangeIn !== null && rangeOut !== null) {
      const start = Math.min(rangeIn, rangeOut);
      const end = Math.max(rangeIn, rangeOut);
      engine.dispatch(name === "lift" ? "edit.lift" : "timeline.cut-range", { start, end });
    }
    showMarks();
  }

  pick.addEventListener("change", () => choose(pick.value));
  formatPick.addEventListener("change", () => {
    edlRow.hidden = formatPick.value !== "edl";
  });
  fileInput.addEventListener("change", () => {
    const file = fileInput.files?.[0];
    if (file) void importTimeline(file);
    fileInput.value = "";
  });

  const layoutPick = el.querySelector<HTMLSelectElement>('[data-pro="layout"]')!;
  const keyList = el.querySelector<HTMLElement>('[data-pro="keylist"]')!;
  const ACTION_LABELS: Record<string, string> = {
    play: "key.play",
    markIn: "pro.markin",
    markOut: "pro.markout",
    insert: "pro.insert",
    overwrite: "pro.overwrite",
    append: "key.append",
    lift: "pro.lift",
    extract: "pro.extract",
    addEdit: "key.addedit",
    rippleDelete: "key.ripple",
    prevEdit: "key.prev",
    nextEdit: "key.next",
  };
  // formcut's own keys (editor-actions.ts), shown when its layout is chosen
  const FORMCUT_KEYS: Array<[string, string[]]> = [
    ["key.play", ["space", "k", "l"]],
    ["key.step", ["j", "arrowleft", "arrowright"]],
    ["key.split", ["s", "mod+b"]],
    ["key.freeze", ["f"]],
    ["pro.markin", ["i"]],
    ["pro.markout", ["o"]],
  ];

  function showKeys() {
    const id = currentLayout();
    if (layoutPick.value !== id) layoutPick.value = id;
    const rows: Array<[string, string[]]> =
      id === "formcut" ? FORMCUT_KEYS : Object.entries(LAYOUTS[id].keys).map(([action, keys]) => [ACTION_LABELS[action], keys ?? []]);
    const html = rows.map(([label, keys]) => `<li><span>${t(label)}</span><kbd>${keys.map(keyLabel).join(", ")}</kbd></li>`).join("");
    if (keyList.innerHTML !== html) keyList.innerHTML = html;
  }

  layoutPick.addEventListener("change", () => {
    chooseLayout(layoutPick.value);
    showKeys();
  });
  document.addEventListener("formcut:pro", (event) => {
    const action = (event as CustomEvent<string>).detail;
    const sourceReady = !el.hidden && !!source;
    if (action === "markIn") act(sourceReady ? "in" : "tin");
    else if (action === "markOut") act(sourceReady ? "out" : "tout");
    else if (action === "insert" || action === "overwrite" || action === "lift" || action === "extract") act(action);
    else if (action === "append") {
      const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
      edit("edit.overwrite", Math.max(0, ...tracks.flatMap((track) => track.clips.map((c) => c.start + c.duration))));
    }
  });
  scrub.addEventListener("input", () => {
    position = (Number(scrub.value) / 1000) * length();
    if (usable && !video.paused) video.currentTime = position;
    else showFrame();
    showTime();
  });
  video.addEventListener("loadeddata", () => {
    usable = true;
  });
  video.addEventListener("timeupdate", () => {
    if (!video.paused) position = video.currentTime;
    showTime();
  });
  const trimStatus = el.querySelector<HTMLElement>('[data-pro="trimstatus"]')!;
  const stepPick = el.querySelector<HTMLSelectElement>('[data-pro="step"]')!;

  function trim(name: string, direction: number) {
    const clipId = engine.snapshot.selectedClipId;
    const found = clipId ? engine.findClip(clipId) : null;
    if (!clipId || !found) {
      trimStatus.textContent = t("pro.select");
      return;
    }
    const fps = (engine.snapshot as unknown as { fps?: number }).fps || 30;
    const step = stepPick.value === "second" ? 1 : stepPick.value === "frames5" ? 5 / fps : 1 / fps;
    const track = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks[found.trackIndex];
    const was = JSON.stringify(track.clips);
    engine.dispatch(`edit.${name}`, { clipId, delta: direction * step });
    const changed = JSON.stringify(engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks[found.trackIndex].clips) !== was;
    const text = changed ? "" : t("pro.refused");
    if (trimStatus.textContent !== text) trimStatus.textContent = text;
  }

  el.addEventListener("click", (event) => {
    const target = event.target as HTMLElement;
    const trimButton = target.closest<HTMLElement>("[data-trim]");
    if (trimButton) {
      trim(trimButton.dataset.trim!, Number(trimButton.dataset.dir));
      return;
    }
    const button = target.closest<HTMLElement>("[data-act]");
    if (button) act(button.dataset.act!);
  });
  // I and O mark the source while the tab is open (Premiere's keys); the other edit keys wait for the Keys section,
  // where whole layouts are chosen, so they cannot clash with formcut's own shortcuts.
  document.addEventListener("keydown", (event) => {
    if (el.hidden || event.metaKey || event.ctrlKey || event.altKey) return;
    const focus = document.activeElement as HTMLElement | null;
    if (focus && (focus.tagName === "INPUT" || focus.tagName === "TEXTAREA" || focus.tagName === "SELECT" || focus.isContentEditable)) return;
    if (event.key === "i" || event.key === "I") act("in");
    else if (event.key === "o" || event.key === "O") act("out");
    else return;
    event.preventDefault();
  });
  bin.subscribe(() => {
    if (!el.hidden) fillPick();
  });
  engine.subscribe((_state, changed) => {
    if (!el.hidden && (changed === "timeline" || changed === "project" || changed === "clips")) fillTracks();
  });

  return {
    tab: "Pro",
    el,
    pause() {
      video.pause();
    },
    async load() {
      fillPick();
      fillTracks();
      showMarks();
      showTime();
      showKeys();
    },
  };
}
