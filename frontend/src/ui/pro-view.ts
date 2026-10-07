import type { ProjectEngine } from "../engine/project";
import type { MediaBin, MediaItem } from "../engine/media";
import { fileUrl } from "../engine/media";
import type { Clip } from "../engine/types";
import { t } from "../i18n";

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

  function edit(kind: "edit.insert" | "edit.overwrite") {
    if (!source || markOut - markIn <= 0.01) return;
    const clip = {
      id: crypto.randomUUID(),
      kind: source.kind,
      label: source.name,
      start: Math.round(engine.snapshot.playhead * 1000) / 1000,
      duration: Math.round((markOut - markIn) * 1000) / 1000,
      mediaId: source.id,
      sourceIn: Math.round(markIn * 1000) / 1000,
      filmstrip: source.kind === "video",
    } as unknown as Clip;
    engine.dispatch(kind, { trackIndex: Number(trackPick.value), clip });
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
  el.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-act]");
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
    },
  };
}
