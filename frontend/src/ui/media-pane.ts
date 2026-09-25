import { titleSpeech } from "./title-speech";
import { escapeHtml } from "./safe-text";
import { reconcilePresets } from "./preset-grid";
import { thumbUrl, type MediaBin, type MediaItem } from "../engine/media";
import { formatTimecode, type ProjectEngine } from "../engine/project";
import type { MediaKind } from "../engine/types";
import { MASK_SHAPES, defaultTextStyle, defaultTransform, type Clip, type TextStyle } from "../engine/types";
import { captionLook, transcribeClip, typedCaptions, wordTimes } from "../engine/captions";
import { locale, t } from "../i18n";
import { text } from "../i18n/text";
import { icon } from "./icons";
import { reconcile as orderNodes } from "./keyed-list";
import { categoryIcon } from "./category-icons";
import { api } from "../engine/api";
import { buildLibraryView } from "./library-view";
import { openUpscale } from "./upscale-dialog";
import { openTikTok } from "./tiktok-dialog";
import { openInstagram } from "./instagram";
import { openCloudBrowser } from "./cloud";
import { compact } from "./compact";

const TABS: Array<[string, string]> = [
  ["Media", "tab.media"],
  ["Text", "tab.text"],
  ["Transitions", "tab.transitions"],
  ["Effects", "tab.effects"],
  ["Filters", "tab.filters"],
  ["Templates", "tab.templates"],
  ["Stickers", "tab.stickers"],
  ["Music", "tab.music"],
  ["Sounds", "tab.sounds"],
];
const EFFECT_GROUPS: Array<[string, string[]]> = [
  ["Video effects", ["Blur", "Stylize", "Distort", "Texture", "Looks", "Packages", "Mask", "Cutout"]],
  ["Audio effects", ["Voice", "Tone", "Space", "Clean"]],
];
const FILTER_GROUPS = ["Adjust", "Film", "Warm", "Cool", "Split"];
// Every mask shape the renderer draws, except the pen path, which is drawn by hand.
const MASKS: Array<[string, string]> = MASK_SHAPES.filter((shape) => shape !== "path").map((shape) => [shape, t(`mask.${shape}`)]);
/** A cutout preset from the catalogue: a model at given edge settings, or a colour key. */
type CutoutPreset = { id: string; name: string; model?: string; threshold?: number; feather?: number; key?: { color: string; similarity: number; blend: number } };
const cutoutPresets = new Map<string, CutoutPreset>();
const presetLabel = (name: string) => name.split(" · ").map((part) => text(part)).join(" · ");
const presetOn = (clip: Clip, preset: CutoutPreset) =>
  preset.key
    ? clip.key?.color === preset.key.color
    : clip.cutout?.model === preset.model && clip.cutout?.threshold === preset.threshold && clip.cutout?.feather === preset.feather;

export function buildMediaPane(bin: MediaBin, engine: ProjectEngine): HTMLElement {
  const el = document.createElement("section");
  el.className = "pane pane-media";
  el.innerHTML = `
    <div class="pane-tabs" data-ref="tabs">
      <div class="pane-tab-strip" data-ref="tab-strip">
        ${TABS.map(([key, label]) => `<button class="pane-tab${key === "Effects" ? " is-active" : ""}" data-tab="${key}" data-feature="tab.${key}">${t(label)}</button>`).join("")}
      </div>
      <button class="select-chip">${icon("grid")}</button>
    </div>
    <div class="media-body" data-view="effects">
      <nav class="media-cats" data-ref="cats">
        ${EFFECT_GROUPS.map(([group, cats]) => `<div class="cat-group" data-mode="effect">${icon("chevD")}${group}</div>${cats.map((c) => `<button class="cat-item${c === "Blur" ? " is-active" : ""}" data-mode="effect" data-cat="${c}">${categoryIcon(c)}<span>${c}</span></button>`).join("")}`).join("")}
        <div class="cat-group" data-mode="filter" hidden>${icon("chevD")}Filters</div>
        ${FILTER_GROUPS.map((c) => `<button class="cat-item" data-mode="filter" data-cat="${c}" hidden>${categoryIcon(c)}<span>${c}</span></button>`).join("")}
      </nav>
      <div class="media-main">
        <div class="search-field">${icon("search")}<input data-ref="fx-search" placeholder="${t("fx.search")}" /></div>
        <div class="cap-files"><button type="button" class="tool-chip" data-ref="fx-adjust" title="${t("fx.adjust.hint")}">${icon("sliders")}${t("fx.adjust.add")}</button></div>
        <div class="fx-status" data-ref="fx-status" role="status"></div>
        <div class="fx-package-bar" data-ref="fx-package-bar" hidden><button type="button" class="tool-chip" data-ref="fx-import">${t("fx.importPackage")}</button><input type="file" accept=".zip,.json,application/zip,application/json" data-ref="fx-import-file" hidden /></div>
        <div class="card-grid" data-ref="fx-grid"></div>
        <p class="fx-empty" data-ref="fx-empty" hidden></p>
      </div>
    </div>
    <div class="media-body text-body" data-view="text" hidden>
      <div class="media-main">
        <div class="text-add-panel">
          <div class="text-add-hint">${t("text.hint")}</div>
          <button class="tool-chip" data-ref="add-title">${icon("plus")}${t("text.add")}</button>
          <div class="text-add-hint">${t("cap.hint")}</div>
          <div class="prop-row">
            <span>${t("cap.language")}</span>
            <select class="mini-select" data-ref="cap-lang">
              <option value="en" selected>${t("cap.lang.en")}</option>
              <option value="auto">${t("cap.lang.auto")}</option>
            </select>
            <span>${t("cap.track")}</span>
            <select class="mini-select" data-ref="cap-track">
              <option value="0" selected>1</option><option value="1">2</option>
              <option value="2">3</option><option value="3">4</option>
            </select>
          </div>
          <div class="prop-row">
            <span>${t("cap.model")}</span>
            <select class="mini-select" data-ref="cap-size">
              <option value="tiny" selected>${t("cap.model.tiny")}</option>
              <option value="base">${t("cap.model.base")}</option>
              <option value="small">${t("cap.model.small")}</option>
              <option value="medium">${t("cap.model.medium")}</option>
              <option value="large">${t("cap.model.large")}</option>
            </select>
            <span>${t("cap.words")}</span>
            <select class="mini-select" data-ref="cap-words">
              <option value="">${t("cap.words.auto")}</option>
              <option value="3">3</option><option value="5">5</option><option value="7">7</option>
            </select>
          </div>
          <div class="prop-row">
            <span>${t("cap.placement")}</span>
            <select class="mini-select" data-ref="cap-place">
              <option value="bottom" selected>${t("cap.place.bottom")}</option>
              <option value="centre">${t("cap.place.centre")}</option>
              <option value="top">${t("cap.place.top")}</option>
            </select>
            <span>${t("cap.size")}</span>
            <select class="mini-select" data-ref="cap-scale">
              <option value="small">${t("cap.size.small")}</option>
              <option value="medium" selected>${t("cap.size.medium")}</option>
              <option value="large">${t("cap.size.large")}</option>
            </select>
          </div>
          <div class="prop-row">
            <span>${t("cap.wordStyle")}</span>
            <select class="mini-select" data-ref="cap-word-style">
              <option value="plain" selected>${t("cap.wordStyle.plain")}</option>
              <option value="highlight">${t("cap.wordStyle.highlight")}</option>
              <option value="pop">${t("cap.wordStyle.pop")}</option>
              <option value="box">${t("cap.wordStyle.box")}</option>
            </select>
            <span>${t("cap.wordColour")}</span>
            <input type="color" class="mini-select" data-ref="cap-word-colour" value="#ffd633" aria-label="${t("cap.wordColour")}" />
          </div>
          <div class="prop-row">
            <span>${t("cap.emphasis")}</span>
            <input type="text" class="mini-select" data-ref="cap-emphasis-words" placeholder="${t("cap.emphasis.placeholder")}" aria-label="${t("cap.emphasis")}" />
            <input type="color" class="mini-select" data-ref="cap-emphasis-colour" value="#ff5a36" aria-label="${t("cap.emphasis.colour")}" />
            <button class="tool-chip" data-ref="cap-emphasis-apply">${t("cap.emphasis.apply")}</button>
            <button class="tool-chip" data-ref="cap-emphasis-clear">${t("cap.emphasis.clear")}</button>
          </div>
          <button class="tool-chip" data-ref="transcribe">${icon("search")}${t("cap.transcribe")}</button>
          <button class="tool-chip" data-ref="cap-cancel" hidden>${t("cap.cancel")}</button>
          <div class="text-add-hint">${t("cap.typed.hint")}</div>
          <textarea class="typed-captions" data-ref="typed-lines" rows="3" placeholder="${t("cap.typed.placeholder")}"></textarea>
          <button class="tool-chip" data-ref="typed-add">${icon("plus")}${t("cap.typed.add")}</button>
          <div class="text-add-hint">${t("cap.files")}</div>
          <div class="cap-files">
            <button class="tool-chip" data-ref="cap-import">${icon("plus")}${t("cap.import")}</button>
            <button class="tool-chip" data-ref="cap-export-srt">${icon("export")}${t("cap.exportSrt")}</button>
            <button class="tool-chip" data-ref="cap-export-vtt">${icon("export")}${t("cap.exportVtt")}</button>
          </div>
          <input type="file" data-ref="cap-file" accept=".srt,.vtt,text/vtt,application/x-subrip" hidden />
          <div class="text-add-hint">${t("cap.transcript")}</div>
          <div class="cap-transcript" data-ref="cap-transcript"></div>
          <div class="text-add-hint">${t("title.gallery")}</div>
          <div class="card-grid title-grid" data-ref="title-grid"></div>
          <div class="text-add-hint">${t("tt.section")}: ${t("tt.hint")}</div>
          <div class="card-grid title-grid" data-ref="text-template-grid"></div>
          <div class="prop-row">
            <span>${t("cap.voice")}</span>
            <select class="mini-select" data-ref="tts-voice">
              <option value="">${t("cap.voice.default")}</option>
            </select>
          </div>
          <button class="tool-chip" data-ref="speak">${icon("play")}${t("cap.speak")}</button>
          <div class="stock-note" data-ref="cap-status" hidden></div>
        </div>
      </div>
    </div>
    <div class="media-body trans-body" data-view="transitions" hidden>
      <div class="media-main">
        <div class="text-add-panel">
          <div class="text-add-hint">${t("trans.hint")}</div>
          <div class="prop-row trans-dur">
            <span>${t("trans.duration")}</span>
            <span class="num-field"><input data-ref="trans-dur" value="0.6" /><span class="unit">s</span></span>
          </div>
          <div class="card-grid trans-grid" data-ref="trans-grid"></div>
        </div>
      </div>
    </div>
    <div class="media-body preset-body" data-view="templates" hidden>
      <div class="media-main">
        <div class="text-add-panel">
          <div class="stock-row">
            <input data-ref="preset-name" placeholder="${t("preset.nameph")}" />
            <button class="tool-chip" data-ref="preset-save">${icon("plus")}${t("preset.save")}</button>
          </div>
          <div class="stock-row">
            <label class="tool-chip preset-import-label">${t("preset.import")}<input type="file" data-ref="preset-import" accept=".fcpreset,application/json" hidden /></label>
          </div>
          <div class="stock-note" data-ref="preset-status" hidden></div>
          <div class="card-grid preset-grid" data-ref="preset-grid"></div>
        </div>
      </div>
    </div>
    <div class="media-body bin-body" data-view="media" hidden>
      <div class="media-main">
        <div class="bin-toolbar">
          <div class="seg" data-ref="filters">
            <button class="is-active" data-kind="">All <span data-count=""></span></button>
            <button data-kind="video">Video <span data-count="video"></span></button>
            <button data-kind="audio">Audio <span data-count="audio"></span></button>
            <button data-kind="image">Images <span data-count="image"></span></button>
          </div>
          <span class="spacer"></span>
          <button class="tool-chip" data-ref="stock">${icon("search")}${t("chip.stock")}</button>
          <button class="tool-chip" data-ref="import">${icon("plus")}${t("chip.import")}</button>
          <button class="tool-chip" data-ref="cloud">${icon("grid")}${t("cloud.import")}</button>
          <input type="file" data-ref="file" multiple hidden
            accept="video/*,audio/*,image/*" />
        </div>
        <div class="relink-banner" data-ref="relink" hidden>
          <span data-ref="relink-text"></span>
          <button class="tool-chip" data-ref="relink-btn">${icon("detach")}Relink</button>
          <input type="file" data-ref="relink-file" multiple hidden
            accept="video/*,audio/*,image/*" />
        </div>
        <div class="text-add-hint" data-ref="nest-hint" hidden>${t("media.timelines")}</div>
        <div class="cap-files" data-ref="nest-list" hidden></div>
        <div class="card-grid bin-grid" data-ref="bingrid">
          <div class="bin-empty" data-ref="empty">Import media to start editing</div>
        </div>
      </div>
    </div>`;

  const single = (root: HTMLElement, selector: string) => {
    root.addEventListener("click", (ev) => {
      const hit = (ev.target as HTMLElement).closest<HTMLElement>(selector);
      if (!hit || !root.contains(hit)) return;
      root.querySelector(`${selector}.is-active`)?.classList.remove("is-active");
      hit.classList.add("is-active");
    });
  };
  const tabs = el.querySelector<HTMLElement>('[data-ref="tabs"]')!;
  single(tabs, ".pane-tab");

  const cats = el.querySelector<HTMLElement>('[data-ref="cats"]')!;
  const fxGrid = el.querySelector<HTMLElement>('[data-ref="fx-grid"]')!;
  const fxSearch = el.querySelector<HTMLInputElement>('[data-ref="fx-search"]')!;
  const fxStatus = el.querySelector<HTMLElement>('[data-ref="fx-status"]')!;
  const fxEmpty = el.querySelector<HTMLElement>('[data-ref="fx-empty"]')!;
  const fxPackageBar = el.querySelector<HTMLElement>('[data-ref="fx-package-bar"]')!;
  el.querySelector('[data-ref="fx-adjust"]')!.addEventListener("click", () => {
    const at = engine.snapshot.playhead;
    engine.dispatch("track.insert", { index: 0, name: t("fx.adjust.label") });
    const clip = { id: crypto.randomUUID(), kind: "filter" as const, label: t("fx.adjust.label"), start: at, duration: 5, effects: [] } as unknown as Clip;
    engine.dispatch("clips.add", { entries: [{ trackIndex: 0, clip }] });
    engine.dispatch("clip.select", clip.id);
    fxStatus.hidden = false;
    fxStatus.textContent = `${t("fx.adjust.label")}: ${t("fx.added")}`;
  });
  const fxImportFile = el.querySelector<HTMLInputElement>('[data-ref="fx-import-file"]')!;
  let fxLoaded = false;
  const transGrid = el.querySelector<HTMLElement>('[data-ref="trans-grid"]')!;
  const capTrack = el.querySelector<HTMLSelectElement>('[data-ref="cap-track"]')!;
  let fxMode: "effect" | "filter" = "effect";
  const activeCats: Record<"effect" | "filter", string> = { effect: "Blur", filter: "Adjust" };
  const say = (text: string) => {
    if (fxStatus.textContent !== text) fxStatus.textContent = text;
  };
  const selectedClip = () => {
    const id = engine.snapshot.selectedClipId;
    return id ? engine.findClip(id)?.clip : undefined;
  };
  const applyFxFilter = () => {
    const query = fxSearch.value.trim().toLowerCase();
    for (const node of cats.querySelectorAll<HTMLElement>("[data-mode]")) {
      const shown = node.dataset.mode === fxMode;
      if (node.hidden === shown) node.hidden = !shown;
      if (node.classList.contains("cat-item")) node.classList.toggle("is-active", shown && node.dataset.cat === activeCats[fxMode]);
    }
    let any = false;
    for (const card of fxGrid.querySelectorAll<HTMLElement>(".fx-card")) {
      const visible = card.dataset.mode === fxMode && (query ? card.dataset.name!.includes(query) : card.dataset.cat === activeCats[fxMode]);
      if (card.hidden === visible) card.hidden = !visible;
      any ||= visible;
    }
    const packagesOpen = fxMode === "effect" && !query && activeCats[fxMode] === "Packages";
    if (fxPackageBar.hidden === packagesOpen) fxPackageBar.hidden = !packagesOpen;
    // Say why a category is empty rather than show nothing at all.
    const message = !fxLoaded || any ? "" : query ? t("fx.noMatch") : activeCats[fxMode] === "Packages" ? t("fx.packagesEmpty") : t("fx.categoryEmpty");
    if (fxEmpty.textContent !== message) fxEmpty.textContent = message;
    const hide = !message;
    if (fxEmpty.hidden !== hide) fxEmpty.hidden = hide;
  };
  const syncFxActive = () => {
    const clip = selectedClip();
    const video = new Set((clip?.effects ?? []).map((e) => e.id));
    const audio = new Set((clip?.audioEffects ?? []).map((e) => e.id));
    for (const card of fxGrid.querySelectorAll<HTMLElement>(".fx-card")) {
      const value = card.dataset.id!;
      const kind = card.dataset.kind;
      const on = !!clip && (kind === "audio" ? audio.has(value) : kind === "mask" ? clip.mask?.shape === value : kind === "cutout" ? cutoutPresets.has(value) && presetOn(clip, cutoutPresets.get(value)!) : video.has(value));
      card.classList.toggle("is-active", on);
    }
    for (const card of transGrid.querySelectorAll<HTMLElement>(".trans-card")) {
      card.classList.toggle("is-active", !!clip && clip.transitionIn?.type === card.dataset.trans);
    }
  };
  const syncCaptionTracks = () => {
    const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline]?.tracks ?? [];
    while (capTrack.options.length > Math.max(1, tracks.length)) capTrack.remove(capTrack.options.length - 1);
    tracks.forEach((track, index) => {
      let option = capTrack.options[index];
      if (!option) {
        option = document.createElement("option");
        option.value = String(index);
        capTrack.append(option);
      }
      if (option.textContent !== track.name) option.textContent = track.name;
    });
  };
  let previewVersion = "";
  const thumb = (kind: string, id: string) =>
    `<div class="effect-thumb has-image"><img src="/api/catalogue/preview/${kind}/${encodeURIComponent(id)}?v=${previewVersion}" alt="" loading="eager" fetchpriority="low" decoding="async" draggable="false" /></div>`;
  const favourites = new Set<string>(JSON.parse(localStorage.getItem("formcut.favourites") ?? "[]"));
  const favKey = (kind: string, id: string) => `${kind}:${id}`;
  const fxCard = (mode: string, kind: string, cat: string, id: string, label: string, visual: string) =>
    `<div class="effect-card fx-card${favourites.has(favKey(kind, id)) ? " is-fav" : ""}" data-mode="${mode}" data-kind="${kind}" data-cat="${escapeHtml(cat)}" data-id="${escapeHtml(id)}" data-label="${escapeHtml(label)}" data-name="${escapeHtml(label.toLowerCase())}" hidden><button class="fav-star" data-star aria-label="Favourite" aria-pressed="${favourites.has(favKey(kind, id))}">${"\u2605"}</button>${visual}<div class="effect-name">${escapeHtml(label)}</div></div>`;
  const transitionName = (type: string) =>
    type === "crossfade" ? t("trans.crossfade") : type === "dip" ? t("trans.dip") : text(type.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()));
  type CatalogueEntry = { id: string; name: string; category?: string; group?: string; names?: Record<string, string> };
  // An effect's, look's or package's name comes from the catalogue, in every
  // language it has; a change of language relabels the cards from these, since
  // the general rewrite knows only the interface's own strings.
  const catalogueNames = new Map<string, CatalogueEntry>();
  const relabelEffects = () => {
    for (const card of el.querySelectorAll<HTMLElement>(".fx-card[data-kind]")) {
      const entry = catalogueNames.get(`${card.dataset.kind}:${card.dataset.id}`);
      if (!entry) continue;
      const label = entry.names?.[locale] ?? text(entry.name);
      const name = card.querySelector<HTMLElement>(".effect-name");
      if (name && name.textContent !== label) name.textContent = label;
      if (card.dataset.label !== label) card.dataset.label = label;
    }
  };
  document.addEventListener("formcut:locale", relabelEffects);
  document.addEventListener("formcut:locales", relabelEffects);
  void fetch("/api/catalogue")
    .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
    .then((data: { video: CatalogueEntry[]; audio: CatalogueEntry[]; transitions: string[]; cutouts?: CutoutPreset[]; previewVersion?: string }) => {
      for (const preset of data.cutouts ?? []) cutoutPresets.set(preset.id, preset);
      for (const entry of data.video) catalogueNames.set(`video:${entry.id}`, entry);
      for (const entry of data.audio) catalogueNames.set(`audio:${entry.id}`, entry);
      previewVersion = data.previewVersion ?? "";
      const grouped = (entry: CatalogueEntry) => entry.group !== undefined && entry.group !== "Other";
      const glyph = `<div class="effect-thumb has-glyph">${icon("speaker")}</div>`;
      fxGrid.insertAdjacentHTML(
        "beforeend",
        [
          ...data.video.filter(grouped).map((v) => fxCard(v.category === "Color" ? "filter" : "effect", "video", v.group!, v.id, v.names?.[locale] ?? text(v.name), thumb("effect", v.id))),
          ...MASKS.map(([shape, label]) => fxCard("effect", "mask", "Mask", shape, label, thumb("mask", shape))),
          ...[...cutoutPresets.values()].map((preset) => fxCard("effect", "cutout", "Cutout", preset.id, presetLabel(preset.name), thumb("cutout", preset.id))),
          ...data.audio.filter(grouped).map((a) => fxCard("effect", "audio", a.group!, a.id, text(a.name), glyph)),
        ].join(""),
      );
      transGrid.insertAdjacentHTML(
        "beforeend",
        data.transitions.map((type) => `<div class="effect-card trans-card" data-trans="${escapeHtml(type)}">${thumb("transition", type)}<div class="effect-name">${escapeHtml(transitionName(type))}</div></div>`).join(""),
      );
      fxLoaded = true;
      markPackages();
      applyFxFilter();
      syncFxActive();
    })
    .catch(() => say(t("fx.offline")));
  cats.addEventListener("click", (ev) => {
    const hit = (ev.target as HTMLElement).closest<HTMLElement>(".cat-item");
    if (!hit) return;
    activeCats[fxMode] = hit.dataset.cat ?? activeCats[fxMode];
    if (fxSearch.value !== "") fxSearch.value = "";
    applyFxFilter();
  });
  fxSearch.addEventListener("input", applyFxFilter);
  // A person's own packages: imported here, removable here, never formcut's looks.
  const markPackages = () => {
    for (const card of fxGrid.querySelectorAll<HTMLElement>('.fx-card[data-cat="Packages"]')) {
      if (card.querySelector("[data-remove]")) continue;
      const remove = document.createElement("button");
      remove.type = "button";
      remove.className = "fx-remove";
      remove.dataset.remove = card.dataset.id!;
      remove.title = t("fx.removePackage");
      remove.setAttribute("aria-label", t("fx.removePackage"));
      remove.textContent = "\u00d7";
      card.prepend(remove);
    }
  };
  const refreshPackages = async () => {
    const res = await fetch("/api/catalogue");
    if (!res.ok) return;
    type Listed = { id: string; name: string; group?: string; names?: Record<string, string> };
    const data = (await res.json()) as { video: Listed[]; audio: Listed[] };
    for (const card of fxGrid.querySelectorAll('.fx-card[data-cat="Packages"]')) card.remove();
    const glyph = `<div class="effect-thumb has-glyph">${icon("speaker")}</div>`;
    fxGrid.insertAdjacentHTML(
      "beforeend",
      [
        ...data.video.filter((v) => v.group === "Packages").map((v) => fxCard("effect", "video", "Packages", v.id, v.names?.[locale] ?? text(v.name), thumb("effect", v.id))),
        ...data.audio.filter((a) => a.group === "Packages").map((a) => fxCard("effect", "audio", "Packages", a.id, a.names?.[locale] ?? text(a.name), glyph)),
      ].join(""),
    );
    markPackages();
    applyFxFilter();
    syncFxActive();
  };
  const usedInProject = (id: string) =>
    engine.snapshot.timelines.some((timeline) =>
      timeline.tracks.some((track) => track.clips.some((clip) => clip.effects?.some((e) => e.id === id) || clip.audioEffects?.some((e) => e.id === id))),
    );
  el.querySelector<HTMLButtonElement>('[data-ref="fx-import"]')!.addEventListener("click", () => fxImportFile.click());
  fxImportFile.addEventListener("change", async () => {
    const file = fxImportFile.files?.[0];
    fxImportFile.value = "";
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/packages/import", { method: "POST", body: form });
    const body = await res.json().catch(() => ({}));
    if (!res.ok) {
      say(t("fx.importFailed").replace("{reason}", String(body.detail ?? res.status)));
      return;
    }
    say(t("fx.imported").replace("{name}", body.name));
    await refreshPackages();
  });
  fxGrid.addEventListener(
    "click",
    async (ev) => {
      const button = (ev.target as HTMLElement).closest<HTMLButtonElement>("[data-remove]");
      if (!button) return;
      // Before the grid's own click, which would apply the package to the clip.
      ev.preventDefault();
      ev.stopImmediatePropagation();
      const id = button.dataset.remove!;
      if (usedInProject(id)) {
        say(t("fx.inUseHere"));
        return;
      }
      if (!window.confirm(t("fx.removeConfirm"))) return;
      const res = await fetch(`/api/packages/${encodeURIComponent(id)}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        say(String(body.detail ?? res.status));
        return;
      }
      say(t("fx.packageRemoved"));
      await refreshPackages();
    },
    true,
  );
  let auditionTimer = 0;
  let auditionToken = 0;
  const auditionFrame = (() => {
    const img = document.createElement("img");
    img.className = "audition-frame";
    img.hidden = true;
    img.alt = "";
    return img;
  })();
  const stageFor = () => document.querySelector<HTMLElement>(".stage");
  const endAudition = () => {
    window.clearTimeout(auditionTimer);
    auditionToken += 1;
    auditionFrame.hidden = true;
  };
  const startAudition = (card: HTMLElement) => {
    if (card.dataset.kind !== "video") return;
    const clip = selectedClip();
    if (!clip || (clip.kind !== "video" && clip.kind !== "image") ) return;
    window.clearTimeout(auditionTimer);
    auditionTimer = window.setTimeout(async () => {
      const token = ++auditionToken;
      const s = engine.snapshot;
      const local = Math.min(Math.max(s.playhead - clip.start, 0), clip.duration - 0.01);
      const probe = structuredClone(clip);
      probe.start = 0;
      probe.effects = [...(probe.effects ?? []), { id: card.dataset.id!, amount: 1 }];
      const project = { title: "audition", width: s.width, height: s.height, fps: s.fps, duration: clip.duration, activeTimeline: 0,
        timelines: [{ id: "aud", name: "aud", tracks: [{ id: "t", name: "V", clips: [probe] }] }] };
      try {
        const session = await api("/api/render/sessions", { project, width: 480 });
        if (token !== auditionToken) { void api(`/api/render/sessions/${session.id}`, undefined, "DELETE").catch(() => {}); return; }
        const stage = stageFor();
        if (stage && auditionFrame.parentElement !== stage) stage.append(auditionFrame);
        auditionFrame.src = `/api/render/sessions/${session.id}/frame?time=${local.toFixed(3)}&v=${Date.now()}`;
        auditionFrame.onload = () => { if (token === auditionToken) auditionFrame.hidden = false; };
        window.setTimeout(() => void api(`/api/render/sessions/${session.id}`, undefined, "DELETE").catch(() => {}), 5000);
      } catch { /* audition is best-effort */ }
    }, 300);
  };
  fxGrid.addEventListener("mouseover", (ev) => {
    const card = (ev.target as HTMLElement).closest<HTMLElement>(".fx-card");
    if (card) startAudition(card);
  });
  fxGrid.addEventListener("mouseout", (ev) => {
    const card = (ev.target as HTMLElement).closest<HTMLElement>(".fx-card");
    const next = (ev as MouseEvent).relatedTarget as HTMLElement | null;
    if (card && (!next || !card.contains(next))) endAudition();
  });
  fxGrid.addEventListener("click", async (ev) => {
    const star = (ev.target as HTMLElement).closest<HTMLElement>("[data-star]");
    if (star) {
      ev.stopPropagation();
      const card = star.closest<HTMLElement>(".fx-card")!;
      const key = favKey(card.dataset.kind!, card.dataset.id!);
      const on = !favourites.has(key);
      if (on) favourites.add(key); else favourites.delete(key);
      localStorage.setItem("formcut.favourites", JSON.stringify([...favourites]));
      card.classList.toggle("is-fav", on);
      star.setAttribute("aria-pressed", String(on));
      return;
    }
    const card = (ev.target as HTMLElement).closest<HTMLElement>(".fx-card");
    if (!card) return;
    const clip = selectedClip();
    if (!clip) {
      say(t("fx.select"));
      return;
    }
    const value = card.dataset.id!;
    const label = card.dataset.label!;
    const toggle = <T extends { id: string }>(stack: T[] | undefined, entry: T): T[] =>
      (stack ?? []).some((e) => e.id === entry.id) ? (stack ?? []).filter((e) => e.id !== entry.id) : [...(stack ?? []), entry];
    try {
      if (card.dataset.kind === "audio") {
        if (clip.kind !== "video" && clip.kind !== "audio") {
          say(t("fx.needsound"));
          return;
        }
        const on = (clip.audioEffects ?? []).some((e) => e.id === value);
        engine.dispatch("clip.creator", { clipId: clip.id, patch: { audioEffects: toggle(clip.audioEffects, { id: value, amount: 1 }) } });
        say(`${on ? t("fx.removed") : t("fx.added")}: ${label}`);
      } else if (card.dataset.kind === "mask") {
        const on = clip.mask?.shape === value;
        engine.dispatch("clip.mask", { clipId: clip.id, mask: on ? null : { shape: value, x: 15, y: 15, w: 70, h: 70, feather: 6 } });
        say(on ? `${t("fx.removed")}: ${label}` : t("fx.maskadded"));
      } else if (card.dataset.kind === "cutout") {
        if (clip.kind !== "video" && clip.kind !== "image") {
          say(t("fx.cutoutkind"));
          return;
        }
        const preset = cutoutPresets.get(value);
        if (!preset) return;
        // A second click on the preset in use takes it off again.
        if (presetOn(clip, preset)) {
          if (preset.key) engine.dispatch("clip.key", { clipId: clip.id, key: null });
          else engine.dispatch("clip.creator", { clipId: clip.id, patch: { cutout: undefined } });
          say(`${t("fx.removed")}: ${label}`);
          return;
        }
        if (preset.key) {
          engine.dispatch("clip.key", { clipId: clip.id, key: { ...preset.key } });
          say(`${t("fx.added")}: ${label}`);
          return;
        }
        const models = (await (await fetch("/api/models")).json()) as Array<{ id: string; ready: boolean }>;
        if (!models.find((m) => m.id === preset.model)?.ready) {
          say(t("fx.needmodel"));
          return;
        }
        const target = engine.findClip(clip.id)?.clip;
        if (!target) return;
        engine.dispatch("clip.creator", {
          clipId: target.id,
          patch: { cutout: { model: preset.model!, threshold: preset.threshold!, feather: preset.feather!, strokes: target.cutout?.strokes ?? [] } },
        });
        say(`${t("fx.added")}: ${label}`);
      } else {
        const on = (clip.effects ?? []).some((e) => e.id === value);
        engine.dispatch("clip.creator", { clipId: clip.id, patch: { effects: toggle(clip.effects, { id: value, amount: 1 }) } });
        say(`${on ? t("fx.removed") : t("fx.added")}: ${label}`);
      }
    } catch (error) {
      say(error instanceof Error ? error.message : t("fx.failed"));
    }
  });

  const effectsView = el.querySelector<HTMLElement>('[data-view="effects"]')!;
  const mediaView = el.querySelector<HTMLElement>('[data-view="media"]')!;
  const nestHint = el.querySelector<HTMLElement>('[data-ref="nest-hint"]')!;
  const nestList = el.querySelector<HTMLElement>('[data-ref="nest-list"]')!;
  const nestChips = new Map<string, HTMLButtonElement>();
  const paintTimelines = () => {
    const state = engine.snapshot;
    const others = state.timelines.filter((_, index) => index !== state.activeTimeline);
    const wanted = new Set(others.map((timeline) => timeline.id));
    for (const id of nestChips.keys()) if (!wanted.has(id)) nestChips.delete(id);
    const ordered = others.map((timeline) => {
      let chip = nestChips.get(timeline.id);
      if (!chip) {
        chip = document.createElement("button");
        chip.type = "button";
        chip.className = "tool-chip";
        chip.dataset.nest = timeline.id;
        chip.innerHTML = icon("layers");
        chip.append(document.createTextNode(""));
        nestChips.set(timeline.id, chip);
      }
      const label = chip.lastChild as Text;
      if (label.textContent !== timeline.name) label.textContent = timeline.name;
      return chip;
    });
    orderNodes(nestList, ordered);
    if (nestHint.hidden !== !others.length) nestHint.hidden = nestList.hidden = !others.length;
  };
  nestList.addEventListener("click", (ev) => {
    const chip = (ev.target as HTMLElement).closest<HTMLElement>("[data-nest]");
    const timeline = chip && engine.snapshot.timelines.find((entry) => entry.id === chip.dataset.nest);
    if (!timeline) return;
    const length = Math.max(...timeline.tracks.flatMap((track) => track.clips.map((clip) => clip.start + clip.duration)), 0);
    const clip = { id: crypto.randomUUID(), kind: "timeline" as const, timelineId: timeline.id, label: timeline.name, start: engine.snapshot.playhead, duration: Math.round((length || 5) * 100) / 100 } as unknown as Clip;
    engine.dispatch("track.insert", { index: 0, name: timeline.name });
    engine.dispatch("clips.add", { entries: [{ trackIndex: 0, clip }] });
    engine.dispatch("clip.select", clip.id);
  });
  paintTimelines();
  engine.subscribe((_state, changed) => { if (changed === "timeline" || changed === "project") paintTimelines(); });
  const textView = el.querySelector<HTMLElement>('[data-view="text"]')!;
  const transView = el.querySelector<HTMLElement>('[data-view="transitions"]')!;
  const tmplView = el.querySelector<HTMLElement>('[data-view="templates"]')!;
  const libraries = (["stickers", "music", "sounds"] as const).map((kind) => buildLibraryView(kind, bin));
  tmplView.after(...libraries.map((library) => library.el));
  tabs.addEventListener("click", (ev) => {
    const hit = (ev.target as HTMLElement).closest<HTMLElement>(".pane-tab");
    if (!hit) return;
    const tab = hit.dataset.tab;
    const wantMedia = tab === "Media";
    const wantText = tab === "Text";
    const wantTrans = tab === "Transitions";
    const wantTmpl = tab === "Templates";
    const wantLibrary = libraries.find((library) => library.tab === tab);
    const wantEffects = !wantMedia && !wantText && !wantTrans && !wantTmpl && !wantLibrary;
    if (mediaView.hidden !== !wantMedia) mediaView.hidden = !wantMedia;
    if (textView.hidden !== !wantText) textView.hidden = !wantText;
    if (transView.hidden !== !wantTrans) transView.hidden = !wantTrans;
    if (tmplView.hidden !== !wantTmpl) tmplView.hidden = !wantTmpl;
    if (effectsView.hidden !== !wantEffects) effectsView.hidden = !wantEffects;
    for (const library of libraries) {
      const hide = library !== wantLibrary;
      if (library.el.hidden !== hide) library.el.hidden = hide;
      if (hide) library.pause();
    }
    if (wantLibrary) void wantLibrary.load();
    if (wantTmpl) void loadPresets();
    if (wantEffects) {
      const next = tab === "Filters" ? "filter" : "effect";
      if (fxMode !== next) {
        fxMode = next;
        if (fxSearch.value !== "") fxSearch.value = "";
      }
      applyFxFilter();
    }
  });
  const densityChip = tabs.querySelector<HTMLButtonElement>(".select-chip")!;
  densityChip.title = t("fx.density");
  const applyDensity = (value: "large" | "compact") => {
    if (el.dataset.density !== value) el.dataset.density = value;
    densityChip.setAttribute("aria-pressed", String(value === "compact"));
  };
  let storedDensity: string | null = null;
  try {
    storedDensity = localStorage.getItem("formcut.cards");
  } catch {
    storedDensity = null;
  }
  applyDensity(storedDensity === "compact" ? "compact" : "large");
  densityChip.addEventListener("click", () => {
    const next = el.dataset.density === "compact" ? "large" : "compact";
    applyDensity(next);
    try {
      localStorage.setItem("formcut.cards", next);
    } catch {
      densityChip.dataset.unsaved = "true";
    }
  });

  const transDur = el.querySelector<HTMLInputElement>('[data-ref="trans-dur"]')!;
  transView.addEventListener("click", (ev) => {
    const card = (ev.target as HTMLElement).closest<HTMLElement>(".trans-card");
    if (!card) return;
    const clipId = engine.snapshot.selectedClipId;
    if (!clipId) return;
    const type = card.dataset.trans as NonNullable<Clip["transitionIn"]>["type"];
    const current = engine.findClip(clipId)?.clip.transitionIn;
    const duration = Number(transDur.value) || 0.6;
    engine.dispatch("clip.transition", {
      clipId,
      transition: current?.type === type ? null : { type, duration },
    });
  });
  engine.subscribe((_state, changed) => {
    if (changed === "clips" || changed === "clip-selection" || changed === "timeline") syncFxActive();
    if (changed === "clips" || changed === "timeline" || changed === "project") syncCaptionTracks();
  });
  syncCaptionTracks();

  let titleSeq = 0;
  el.querySelector('[data-ref="add-title"]')!.addEventListener("click", () => {
    const state = engine.snapshot;
    titleSeq += 1;
    const id = `title${Date.now()}${titleSeq}`;
    engine.dispatch("clip.add", {
      trackIndex: 0,
      clip: {
        id,
        kind: "text",
        label: "Title",
        start: state.playhead,
        duration: 3,
        textStyle: defaultTextStyle(),
      },
    });
    engine.dispatch("clip.select", id);
  });

  const capStatus = el.querySelector<HTMLElement>('[data-ref="cap-status"]')!;
  titleSpeech(el, engine, bin);
  let transcribing = false;
  let captionAbort: AbortController | null = null;
  const cancelChip = el.querySelector<HTMLElement>('[data-ref="cap-cancel"]')!;
  let captionStyle: Partial<TextStyle> = {};
  const styled = (): Partial<TextStyle> => {
    const mode = el.querySelector<HTMLSelectElement>('[data-ref="cap-word-style"]')!.value as "plain" | "highlight" | "pop" | "box";
    const colour = el.querySelector<HTMLInputElement>('[data-ref="cap-word-colour"]')!.value;
    return mode === "plain" ? captionStyle : { ...captionStyle, wordStyle: { mode, colour } };
  };
  // Per-word emphasis: the words listed take the colour on the selected
  // caption, or on every caption of the chosen track when none is selected.
  const emphasisTargets = (): string[] => {
    const selected = engine.snapshot.selectedClipId;
    const found = selected ? engine.findClip(selected) : null;
    if (found?.clip.kind === "text") return [found.clip.id];
    const snapshot = engine.snapshot;
    const track = snapshot.timelines[snapshot.activeTimeline]?.tracks[Number(el.querySelector<HTMLSelectElement>('[data-ref="cap-track"]')!.value) || 0];
    return (track?.clips ?? []).filter((clip) => clip.kind === "text" && clip.words?.length).map((clip) => clip.id);
  };
  el.querySelector('[data-ref="cap-emphasis-apply"]')!.addEventListener("click", () => {
    const words = el.querySelector<HTMLInputElement>('[data-ref="cap-emphasis-words"]')!.value.split(/[,\s]+/).filter(Boolean);
    const colour = el.querySelector<HTMLInputElement>('[data-ref="cap-emphasis-colour"]')!.value;
    if (words.length) engine.dispatch("captions.emphasise", { clipIds: emphasisTargets(), words, colour });
  });
  el.querySelector('[data-ref="cap-emphasis-clear"]')!.addEventListener("click", () => {
    engine.dispatch("captions.emphasise", { clipIds: emphasisTargets(), words: [], colour: null });
  });
  let titleStyles: Array<{ id: string; name: string; style: Record<string, unknown> }> = [];
  el.querySelector('[data-ref="transcribe"]')!.addEventListener("click", async () => {
    if (transcribing) return;
    const clipId = engine.snapshot.selectedClipId;
    const show = (msg: string) => {
      capStatus.hidden = false;
      if (capStatus.textContent !== msg) capStatus.textContent = msg;
    };
    if (!clipId) {
      show(t("cap.needmedia"));
      return;
    }
    transcribing = true;
    try {
      const lang = el.querySelector<HTMLSelectElement>('[data-ref="cap-lang"]')!.value === "auto" ? "auto" as const : "en" as const;
      const track = Number(el.querySelector<HTMLSelectElement>('[data-ref="cap-track"]')!.value) || 0;
      const pick = (ref: string) => el.querySelector<HTMLSelectElement>(`[data-ref="${ref}"]`)!.value;
      const words = Number(pick("cap-words")) || undefined;
      captionAbort = new AbortController();
      cancelChip.hidden = false;
      await transcribeClip(engine, bin, clipId, show, lang, track, {
        size: pick("cap-size") as "tiny" | "base" | "small" | "medium" | "large",
        placement: pick("cap-place") as "top" | "centre" | "bottom",
        scale: pick("cap-scale") as "small" | "medium" | "large",
        style: styled(),
        wordsPerCaption: words,
        signal: captionAbort.signal,
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "?";
      show(message === "cancelled" ? t("cap.cancelled") : `${t("cap.failed")}: ${message}`);
    }
    cancelChip.hidden = true;
    captionAbort = null;
    transcribing = false;
  });
  cancelChip.addEventListener("click", () => captionAbort?.abort());

  // C4: typed or pasted lines become captions across the selected clip
  el.querySelector('[data-ref="typed-add"]')!.addEventListener("click", () => {
    const box = el.querySelector<HTMLTextAreaElement>('[data-ref="typed-lines"]')!;
    const pick = (ref: string) => el.querySelector<HTMLSelectElement>(`[data-ref="${ref}"]`)!.value;
    const selected = engine.snapshot.selectedClipId;
    const over = selected && engine.findClip(selected)?.clip.kind !== "text" ? selected : undefined;
    const made = typedCaptions(engine, box.value.split("\n"), {
      placement: pick("cap-place") as "top" | "centre" | "bottom",
      scale: pick("cap-scale") as "small" | "medium" | "large",
      style: styled(),
      spreadOverClipId: over,
    });
    if (!made.length) { capStatus.hidden = false; capStatus.textContent = t("cap.typed.empty"); return; }
    const track = Number(pick("cap-track")) || 0;
    engine.dispatch("captions.add", { trackIndex: track, clips: made });
    box.value = "";
    capStatus.hidden = false;
    capStatus.textContent = `${t("cap.added")}: ${made.length}`;
  });

  const capPick = (ref: string) => el.querySelector<HTMLSelectElement>(`[data-ref="${ref}"]`)!.value;
  const capFile = el.querySelector<HTMLInputElement>('[data-ref="cap-file"]')!;
  const capSay = (text: string) => { capStatus.hidden = false; capStatus.textContent = text; };
  el.querySelector('[data-ref="cap-import"]')!.addEventListener("click", () => capFile.click());
  capFile.addEventListener("change", async () => {
    const file = capFile.files?.[0];
    capFile.value = "";
    if (!file) return;
    const body = new FormData();
    body.append("file", file);
    const res = await fetch("/api/subtitles/parse", { method: "POST", body, headers: { "x-formcut-local": "1" } });
    if (!res.ok) { capSay(t("cap.import.none")); return; }
    const { cues } = (await res.json()) as { cues: Array<{ start: number; end: number; text: string }> };
    const look = captionLook({ placement: capPick("cap-place") as "top" | "centre" | "bottom", scale: capPick("cap-scale") as "small" | "medium" | "large" });
    const stamp = Date.now();
    const clips = cues.map((cue, index) => ({
      id: `cap${stamp}${index}`,
      kind: "text" as const,
      label: cue.text.split("\n")[0],
      start: cue.start,
      duration: Math.max(0.1, Math.round((cue.end - cue.start) * 1000) / 1000),
      words: wordTimes({ text: cue.text, start: cue.start, end: cue.end }),
      textStyle: { ...defaultTextStyle(cue.text), size: look.size, ...styled(), content: cue.text },
      transform: { ...defaultTransform(), posY: look.posY },
    }));
    engine.dispatch("captions.add", { trackIndex: Number(capPick("cap-track")) || 0, clips });
    capSay(`${t("cap.added")}: ${clips.length}`);
  });
  const exportCaptions = async (format: "srt" | "vtt") => {
    const snapshot = engine.snapshot;
    const track = snapshot.timelines[snapshot.activeTimeline]?.tracks[Number(capPick("cap-track")) || 0];
    const cues = (track?.clips ?? [])
      .filter((clip) => clip.kind === "text" && clip.textStyle?.content)
      .map((clip) => ({ start: clip.start, end: clip.start + clip.duration, text: clip.textStyle!.content }));
    if (!cues.length) { capSay(t("cap.export.none")); return; }
    const res = await fetch("/api/subtitles/write", { method: "POST", headers: { "content-type": "application/json", "x-formcut-local": "1" }, body: JSON.stringify({ cues, format }) });
    if (!res.ok) { capSay(t("cap.export.none")); return; }
    const link = document.createElement("a");
    link.href = URL.createObjectURL(await res.blob());
    link.download = `captions.${format}`;
    link.click();
    URL.revokeObjectURL(link.href);
    capSay(`${t("cap.exported")}: ${cues.length}`);
  };
  el.querySelector('[data-ref="cap-export-srt"]')!.addEventListener("click", () => void exportCaptions("srt"));
  el.querySelector('[data-ref="cap-export-vtt"]')!.addEventListener("click", () => void exportCaptions("vtt"));

  // Phase 9: the caption track's text as an editable transcript. Rows are
  // keyed by clip id and patched in place, and a focused input is never
  // rewritten, so typing survives the engine's own clips emits; the time
  // button seeks there and selects the caption. A commit goes through
  // clip.text, which refits the caption's word times to the new text.
  const transcript = el.querySelector<HTMLElement>('[data-ref="cap-transcript"]')!;
  const transcriptRows = new Map<string, HTMLElement>();
  const paintTranscript = () => {
    const snapshot = engine.snapshot;
    const track = snapshot.timelines[snapshot.activeTimeline]?.tracks[Number(capPick("cap-track")) || 0];
    const clips = (track?.clips ?? [])
      .filter((clip) => clip.kind === "text" && clip.textStyle?.content !== undefined)
      .slice()
      .sort((a, b) => a.start - b.start);
    const ordered: HTMLElement[] = [];
    const wanted = new Set<string>();
    for (const clip of clips) {
      wanted.add(clip.id);
      let row = transcriptRows.get(clip.id);
      if (!row) {
        row = document.createElement("div");
        row.className = "cap-line";
        row.dataset.clip = clip.id;
        row.innerHTML = `<button type="button" class="cap-tc"></button><input class="cap-text" type="text" /><button type="button" class="iconbtn cap-cut" title="${t("cap.cutFootage")}" aria-label="${t("cap.cutFootage")}">${icon("blade")}</button>`;
        const id = clip.id;
        row.querySelector("button")!.addEventListener("click", () => {
          const found = engine.findClip(id);
          if (!found) return;
          engine.dispatch("transport.seek", found.clip.start);
          engine.dispatch("clip.select", id);
        });
        // Text-based editing: the sentence goes and so does the footage under
        // it, on every track, with everything after moved back.
        row.querySelector<HTMLButtonElement>(".cap-cut")!.addEventListener("click", () => {
          const found = engine.findClip(id);
          if (!found) return;
          engine.dispatch("timeline.cut-range", { start: found.clip.start, end: found.clip.start + found.clip.duration });
        });
        const field = row.querySelector<HTMLInputElement>("input")!;
        field.addEventListener("change", () => {
          const found = engine.findClip(id);
          const current = found?.clip.textStyle?.content ?? "";
          if (found && field.value !== current) engine.dispatch("clip.text", { clipId: id, patch: { content: field.value } });
        });
        field.addEventListener("keydown", (event) => {
          if (event.key === "Enter") field.blur();
        });
        transcriptRows.set(clip.id, row);
      }
      const stamp = formatTimecode(clip.start, snapshot.fps);
      const button = row.querySelector<HTMLButtonElement>("button")!;
      if (button.textContent !== stamp) button.textContent = stamp;
      const field = row.querySelector<HTMLInputElement>("input")!;
      const content = clip.textStyle!.content;
      if (document.activeElement !== field && field.value !== content) field.value = content;
      if (field.getAttribute("aria-label") !== stamp) field.setAttribute("aria-label", stamp);
      ordered.push(row);
    }
    for (const [id] of transcriptRows) {
      if (!wanted.has(id)) transcriptRows.delete(id);
    }
    orderNodes(transcript, ordered);
  };
  paintTranscript();
  engine.subscribe((_state, changed) => {
    if (changed === "clips" || changed === "timeline" || changed === "project") paintTranscript();
  });
  el.querySelector('[data-ref="cap-track"]')!.addEventListener("change", paintTranscript);

  // Animated titles (text_templates.py): finished designs added at the playhead on
  // a new track at the top, so they draw above the footage.
  const textTemplateGrid = el.querySelector<HTMLElement>('[data-ref="text-template-grid"]')!;
  let textTemplates: Array<{ id: string; name: string; nameKey: string; clips: Array<Record<string, unknown>> }> = [];
  void fetch("/api/presets/texttemplates")
    .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
    .then((entries: typeof textTemplates) => {
      textTemplates = entries;
      textTemplateGrid.insertAdjacentHTML("beforeend", entries.map((entry) =>
        `<div class="effect-card title-card" data-text-template="${escapeHtml(entry.id)}">` +
        `<div class="effect-thumb has-image"><img src="/api/catalogue/preview/texttemplate/${encodeURIComponent(entry.id)}" alt="" loading="lazy" draggable="false" /></div>` +
        `<div class="effect-name">${escapeHtml(t(entry.nameKey))}</div></div>`).join(""));
    })
    .catch(() => { /* the gallery is optional if the engine is offline */ });
  textTemplateGrid.addEventListener("click", (ev) => {
    const card = (ev.target as HTMLElement).closest<HTMLElement>("[data-text-template]");
    const entry = card && textTemplates.find((e) => e.id === card.dataset.textTemplate);
    if (!entry) return;
    const at = engine.snapshot.playhead;
    engine.dispatch("track.insert", { index: 0, name: t("tt.track") });
    const clips = entry.clips.map((source) => {
      const { offset, ...clip } = structuredClone(source) as Record<string, unknown> & { offset: number };
      return { ...clip, id: crypto.randomUUID(), start: at + offset } as unknown as Clip;
    });
    engine.dispatch("clips.add", { entries: clips.map((clip) => ({ trackIndex: 0, clip })) });
    capStatus.hidden = false;
    capStatus.textContent = `${t("tt.added")}: ${t(entry.nameKey)}`;
  });

  // TI3: the built-in style gallery, thumbnails rendered by the engine
  const titleGrid = el.querySelector<HTMLElement>('[data-ref="title-grid"]')!;
  void fetch("/api/presets/titles")
    .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
    .then((styles: Array<{ id: string; name: string; style: Record<string, unknown> }>) => {
      titleStyles = styles;
      titleGrid.insertAdjacentHTML("beforeend", styles.map((entry) =>
        `<div class="effect-card title-card" data-title-style="${escapeHtml(entry.id)}">` +
        `<div class="effect-thumb has-image"><img src="/api/catalogue/preview/title/${encodeURIComponent(entry.id)}" alt="" loading="lazy" draggable="false" /></div>` +
        `<div class="effect-name">${escapeHtml(entry.name)}</div></div>`).join(""));
    })
    .catch(() => { /* the gallery is optional if the engine is offline */ });
  // A style card is a toggle: clicking the applied one takes it off again,
  // which means clearing exactly the properties that style set rather than
  // resetting the whole title, so a hand-made size or colour survives.
  let appliedStyle: string | null = null;
  const clearPatch = (style: Record<string, unknown>): Record<string, unknown> => {
    const base = defaultTextStyle("") as unknown as Record<string, unknown>;
    const patch: Record<string, unknown> = {};
    for (const key of Object.keys(style)) {
      patch[key] = key in base ? base[key] : undefined;
    }
    return patch;
  };
  titleGrid.addEventListener("click", (ev) => {
    const card = (ev.target as HTMLElement).closest<HTMLElement>("[data-title-style]");
    if (!card) return;
    const entry = titleStyles.find((e) => e.id === card.dataset.titleStyle);
    if (!entry) return;
    const clipId = engine.snapshot.selectedClipId;
    const found = clipId ? engine.findClip(clipId) : null;
    const isText = !!found && found.clip.kind === "text";
    const already = appliedStyle === entry.id && card.classList.contains("is-active");
    if (already) {
      appliedStyle = null;
      captionStyle = {};
      if (isText) engine.dispatch("clip.text", { clipId: found!.clip.id, patch: clearPatch(entry.style) });
      card.classList.remove("is-active");
      capStatus.hidden = false;
      capStatus.textContent = t("title.gallery.removed");
      return;
    }
    appliedStyle = entry.id;
    captionStyle = entry.style as Partial<TextStyle>;
    if (isText) engine.dispatch("clip.text", { clipId: found!.clip.id, patch: entry.style });
    else { capStatus.hidden = false; capStatus.textContent = t("title.gallery.stored"); }
    for (const other of titleGrid.querySelectorAll(".title-card")) other.classList.toggle("is-active", other === card);
  });

  const grid = el.querySelector<HTMLElement>('[data-ref="bingrid"]')!;
  const empty = el.querySelector<HTMLElement>('[data-ref="empty"]')!;
  const filters = el.querySelector<HTMLElement>('[data-ref="filters"]')!;
  const fileInput = el.querySelector<HTMLInputElement>('[data-ref="file"]')!;
  let activeKind: MediaKind | "" = "";

  const cardFor = (item: MediaItem): HTMLElement => {
    const card = document.createElement("div");
    card.className = `effect-card bin-card k-${item.kind}`;
    // P9: video cards carry their proxy's state, so a person can see what is
    // queued, building or ready without opening anything.
    if (item.kind === "video") {
      const badge = document.createElement("span");
      badge.className = "proxy-badge";
      badge.dataset.proxy = item.id;
      card.append(badge);
    }
    card.addEventListener("click", () => {
      // Touch layouts have no HTML5 drag and drop; a tap appends the media
      // at the playhead on the matching lane instead.
      if (!compact()) return;
      const state = engine.snapshot;
      const timeline = state.timelines[state.activeTimeline];
      const trackIndex = Math.min(item.kind === "audio" ? 3 : 2, timeline.tracks.length - 1);
      engine.dispatch("clip.add", {
        trackIndex,
        clip: {
          id: `m${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`,
          kind: item.kind,
          label: item.name,
          start: Math.round(state.playhead * 10) / 10,
          duration: Math.max(item.duration, 0.5),
          mediaId: item.id,
          filmstrip: item.kind === "video",
        },
      });
    });
    card.draggable = true;
    card.dataset.media = item.id;
    const mm = Math.floor(item.duration / 60);
    const ss = String(Math.floor(item.duration % 60)).padStart(2, "0");
    const upscalable = item.kind === "video" || item.kind === "image";
    card.innerHTML = `
      <div class="effect-thumb bin-thumb">
        ${item.thumb ? `<img src="${thumbUrl(item)}" alt="" loading="lazy" draggable="false" />` : `<span class="bin-glyph">${icon(item.kind === "audio" ? "speaker" : "pip")}</span>`}
        <span class="dur-chip">${mm}:${ss}</span>
        ${upscalable ? `<button type="button" class="bin-upscale" title="${escapeHtml(t("upscale.action"))}" aria-label="${escapeHtml(t("upscale.action"))}">${icon("fullscreen")}</button>` : ""}
        ${item.kind === "video" ? `<button type="button" class="bin-post" title="${escapeHtml(t("tiktok.action"))}" aria-label="${escapeHtml(t("tiktok.action"))}">${icon("export")}</button>` : ""}
        ${item.kind === "video" ? `<button type="button" class="bin-ig" title="${escapeHtml(t("instagram.action"))}" aria-label="${escapeHtml(t("instagram.action"))}">${icon("pip")}</button>` : ""}
      </div>
      <div class="effect-name">${escapeHtml(item.name)}</div>`;
    card.querySelector(".bin-upscale")?.addEventListener("click", (ev) => {
      // The card's own click adds it to the timeline on touch layouts.
      ev.stopPropagation();
      openUpscale(item, bin);
    });
    card.querySelector(".bin-post")?.addEventListener("click", (ev) => {
      ev.stopPropagation();
      openTikTok({ mediaId: item.id, name: item.name });
    });
    card.querySelector(".bin-ig")?.addEventListener("click", (ev) => {
      ev.stopPropagation();
      openInstagram({ mediaId: item.id, name: item.name });
    });
    card.addEventListener("dragstart", (ev) => {
      ev.dataTransfer?.setData("application/x-formcut-media", item.id);
      ev.dataTransfer!.effectAllowed = "copy";
    });
    return card;
  };

  const applyFilter = () => {
    for (const card of grid.querySelectorAll<HTMLElement>(".bin-card")) {
      card.hidden = activeKind !== "" && !card.classList.contains(`k-${activeKind}`);
    }
  };
  const syncCounts = () => {
    for (const span of filters.querySelectorAll<HTMLElement>("[data-count]")) {
      const kind = span.dataset.count as MediaKind | "";
      const next = String(bin.count(kind || undefined));
      if (span.textContent !== next) span.textContent = next;
    }
    empty.hidden = bin.count() > 0;
  };

  // One poll refreshes every visible badge; it only runs while video cards are
  // on screen and something is still being built.
  const paintProxies = async () => {
    const badges = [...el.querySelectorAll<HTMLElement>("[data-proxy]")];
    if (!badges.length) return;
    for (const badge of badges) {
      try {
        const state = await fetch(`/api/media/${badge.dataset.proxy}/proxy`).then((r) => r.json());
        const label: Record<string, string> = {
          missing: "", stale: t("proxy.stale"), queued: t("proxy.queued"),
          building: `${t("proxy.building")} ${Math.round((state.progress ?? 0) * 100)}%`,
          ready: t("proxy.ready"), failed: t("proxy.failed"),
        };
        badge.textContent = label[state.state] ?? "";
        badge.dataset.state = state.state;
        badge.hidden = !badge.textContent;
      } catch { badge.hidden = true; }
    }
  };
  window.setInterval(() => void paintProxies(), 4000);
  bin.subscribe((items, added) => {
    void paintProxies();
    if (added) {
      grid.append(cardFor(added));
    } else {
      for (const card of grid.querySelectorAll(".bin-card")) card.remove();
      for (const item of items) grid.append(cardFor(item));
    }
    applyFilter();
    syncCounts();
  });
  syncCounts();

  filters.addEventListener("click", (ev) => {
    const hit = (ev.target as HTMLElement).closest<HTMLElement>("button");
    if (!hit) return;
    activeKind = (hit.dataset.kind ?? "") as MediaKind | "";
    applyFilter();
  });
  el.querySelector('[data-ref="import"]')!.addEventListener("click", () => fileInput.click());
  el.querySelector('[data-ref="cloud"]')!.addEventListener("click", () => openCloudBrowser(bin));
  fileInput.addEventListener("change", async () => {
    const files = Array.from(fileInput.files ?? []);
    fileInput.value = "";
    for (const file of files) await bin.upload(file);
  });

  const relinkBanner = el.querySelector<HTMLElement>('[data-ref="relink"]')!;
  const relinkText = el.querySelector<HTMLElement>('[data-ref="relink-text"]')!;
  const relinkFile = el.querySelector<HTMLInputElement>('[data-ref="relink-file"]')!;

  const missingMedia = (): Map<string, string> => {
    const missing = new Map<string, string>();
    for (const timeline of engine.snapshot.timelines) {
      for (const track of timeline.tracks) {
        for (const clip of track.clips) {
          if (clip.mediaId && !bin.find(clip.mediaId)) missing.set(clip.mediaId, clip.label);
        }
      }
    }
    return missing;
  };
  const syncRelink = () => {
    const missing = missingMedia();
    const show = missing.size > 0;
    if (relinkBanner.hidden === show) relinkBanner.hidden = !show;
    if (!show) return;
    const next = `${missing.size} missing media file${missing.size === 1 ? "" : "s"}`;
    if (relinkText.textContent !== next) relinkText.textContent = next;
  };
  bin.subscribe(() => syncRelink());
  engine.subscribe((_state, changed) => {
    if (changed === "clips" || changed === "timeline") syncRelink();
  });

  el.querySelector('[data-ref="relink-btn"]')!.addEventListener("click", () => relinkFile.click());
  relinkFile.addEventListener("change", async () => {
    const files = Array.from(relinkFile.files ?? []);
    relinkFile.value = "";
    const missing = missingMedia();
    const map: Record<string, string> = {};
    for (const file of files) {
      const item = await bin.upload(file);
      if (!item) continue;
      for (const [oldId, label] of missing) {
        if (!map[oldId] && label === item.name) map[oldId] = item.id;
      }
    }
    if (Object.keys(map).length > 0) engine.dispatch("media.relink", map);
    syncRelink();
  });
  el.querySelector('[data-ref="stock"]')!.addEventListener("click", () => {
    document.dispatchEvent(new CustomEvent("formcut:studio", { detail: { page: "stock" } }));
  });
  const presetGrid = el.querySelector<HTMLElement>('[data-ref="preset-grid"]')!;
  const presetStatus = el.querySelector<HTMLElement>('[data-ref="preset-status"]')!;
  const presetName = el.querySelector<HTMLInputElement>('[data-ref="preset-name"]')!;
  const pnote = (msg: string) => {
    presetStatus.hidden = msg === "";
    if (presetStatus.textContent !== msg) presetStatus.textContent = msg;
  };
  const styleOf = (clip: Clip): Record<string, unknown> => ({
    transform: { ...defaultTransform(), ...clip.transform },
    effectId: clip.effectId ?? null,
    effects: clip.effects,
    audioEffects: clip.audioEffects,
    speedCurve: clip.speedCurve,
    keyframes: clip.keyframes,
    expressions: clip.expressions,
    lutId: clip.lutId,
    shaderId: clip.shaderId,
    volume: clip.volume,
    pan: clip.pan,
    key: clip.key ?? null,
    mask: clip.mask ?? null,
    audioFx: clip.audioFx ?? null,
    speed: clip.speed ?? null,
    fadeIn: clip.fadeIn ?? null,
    fadeOut: clip.fadeOut ?? null,
    transitionIn: clip.transitionIn ?? null,
    textStyle: clip.kind === "text" ? { ...defaultTextStyle(clip.label), ...clip.textStyle } : null,
  });
  const loadPresets = async () => {
    try {
      const res = await fetch("/api/presets");
      if (!res.ok) return;
      const items = (await res.json()) as Array<{ id: string; name: string }>;
      reconcilePresets(presetGrid, items);
    } catch {
      /* offline engine: leave the grid as is */
    }
  };
  el.querySelector('[data-ref="preset-save"]')!.addEventListener("click", async () => {
    const clipId = engine.snapshot.selectedClipId;
    const found = clipId ? engine.findClip(clipId) : null;
    if (!found) {
      pnote(t("preset.needclip"));
      return;
    }
    const res = await fetch("/api/presets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name: presetName.value || found.clip.label, style: styleOf(found.clip) }),
    });
    pnote(res.ok ? t("preset.saved") : t("preset.savefail"));
    if (res.ok) {
      presetName.value = "";
      await loadPresets();
    }
  });
  presetGrid.addEventListener("click", async (ev) => {
    const target = ev.target as HTMLElement;
    const card = target.closest<HTMLElement>(".preset-card");
    if (!card) return;
    if (target.closest("a")) return;
    const id = card.dataset.preset!;
    if (target.closest(".preset-del")) {
      await fetch(`/api/presets/${id}`, { method: "DELETE" });
      await loadPresets();
      return;
    }
    const clipId = engine.snapshot.selectedClipId;
    if (!clipId) {
      pnote(t("preset.needclip"));
      return;
    }
    const items = (await (await fetch("/api/presets")).json()) as Array<{ id: string; style: object }>;
    const preset = items.find((p) => p.id === id);
    if (!preset) return;
    engine.dispatch("clip.style", { clipId, style: preset.style });
    pnote(t("preset.applied"));
  });
  el.querySelector<HTMLInputElement>('[data-ref="preset-import"]')!.addEventListener("change", async (ev) => {
    const input = ev.target as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    const res = await fetch("/api/presets/import", { method: "POST", body: form });
    pnote(res.ok ? t("preset.imported") : t("preset.importfail"));
    if (res.ok) await loadPresets();
  });

  return el;
}
