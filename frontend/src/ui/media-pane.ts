import { titleSpeech } from "./title-speech";
import { escapeHtml } from "./safe-text";
import { reconcilePresets } from "./preset-grid";
import { thumbUrl, type MediaBin, type MediaItem } from "../engine/media";
import type { ProjectEngine } from "../engine/project";
import type { MediaKind } from "../engine/types";
import { defaultTextStyle, defaultTransform, type Clip } from "../engine/types";
import { transcribeClip } from "../engine/captions";
import { t } from "../i18n";
import { text } from "../i18n/text";
import { icon } from "./icons";

const TABS: Array<[string, string]> = [
  ["Media", "tab.media"],
  ["Text", "tab.text"],
  ["Transitions", "tab.transitions"],
  ["Effects", "tab.effects"],
  ["Filters", "tab.filters"],
  ["Templates", "tab.templates"],
];
const EFFECT_GROUPS: Array<[string, string[]]> = [
  ["Video effects", ["Blur", "Stylize", "Distort", "Texture", "Mask", "Cutout"]],
  ["Audio effects", ["Voice", "Tone", "Space", "Clean"]],
];
const FILTER_GROUPS = ["Adjust", "Film", "Warm", "Cool", "Split"];
const MASKS: Array<[string, string]> = [["rect", t("fx.mask.rect")], ["ellipse", t("fx.mask.ellipse")]];
const CUTOUTS: Array<[string, string]> = [["object-cutout", t("fx.cutout.object")], ["person-cutout", t("fx.cutout.person")]];

export function buildMediaPane(bin: MediaBin, engine: ProjectEngine): HTMLElement {
  const el = document.createElement("section");
  el.className = "pane pane-media";
  el.innerHTML = `
    <div class="pane-tabs" data-ref="tabs">
      ${TABS.map(([key, label]) => `<button class="pane-tab${key === "Effects" ? " is-active" : ""}" data-tab="${key}">${t(label)}</button>`).join("")}
      <span class="spacer"></span>
      <button class="select-chip">${icon("grid")}</button>
    </div>
    <div class="media-body" data-view="effects">
      <nav class="media-cats" data-ref="cats">
        ${EFFECT_GROUPS.map(([group, cats]) => `<div class="cat-group" data-mode="effect">${icon("chevD")}${group}</div>${cats.map((c) => `<button class="cat-item${c === "Blur" ? " is-active" : ""}" data-mode="effect" data-cat="${c}">${c}</button>`).join("")}`).join("")}
        <div class="cat-group" data-mode="filter" hidden>${icon("chevD")}Filters</div>
        ${FILTER_GROUPS.map((c) => `<button class="cat-item" data-mode="filter" data-cat="${c}" hidden>${c}</button>`).join("")}
      </nav>
      <div class="media-main">
        <div class="search-field">${icon("search")}<input data-ref="fx-search" placeholder="${t("fx.search")}" /></div>
        <div class="fx-status" data-ref="fx-status" role="status"></div>
        <div class="card-grid" data-ref="fx-grid"></div>
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
          <button class="tool-chip" data-ref="transcribe">${icon("search")}${t("cap.transcribe")}</button>
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
          <input type="file" data-ref="file" multiple hidden
            accept="video/*,audio/*,image/*" />
        </div>
        <div class="relink-banner" data-ref="relink" hidden>
          <span data-ref="relink-text"></span>
          <button class="tool-chip" data-ref="relink-btn">${icon("detach")}Relink</button>
          <input type="file" data-ref="relink-file" multiple hidden
            accept="video/*,audio/*,image/*" />
        </div>
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
    for (const card of fxGrid.querySelectorAll<HTMLElement>(".fx-card")) {
      const visible = card.dataset.mode === fxMode && (query ? card.dataset.name!.includes(query) : card.dataset.cat === activeCats[fxMode]);
      if (card.hidden === visible) card.hidden = !visible;
    }
  };
  const syncFxActive = () => {
    const clip = selectedClip();
    const video = new Set((clip?.effects ?? []).map((e) => e.id));
    const audio = new Set((clip?.audioEffects ?? []).map((e) => e.id));
    for (const card of fxGrid.querySelectorAll<HTMLElement>(".fx-card")) {
      const value = card.dataset.id!;
      const kind = card.dataset.kind;
      const on = !!clip && (kind === "audio" ? audio.has(value) : kind === "mask" ? clip.mask?.shape === value : kind === "cutout" ? clip.cutout?.model === value : video.has(value));
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
  const thumb = (kind: string, id: string) =>
    `<div class="effect-thumb has-image"><img src="/api/catalogue/preview/${kind}/${encodeURIComponent(id)}" alt="" loading="lazy" draggable="false" /></div>`;
  const fxCard = (mode: string, kind: string, cat: string, id: string, label: string, visual: string) =>
    `<div class="effect-card fx-card" data-mode="${mode}" data-kind="${kind}" data-cat="${escapeHtml(cat)}" data-id="${escapeHtml(id)}" data-label="${escapeHtml(label)}" data-name="${escapeHtml(label.toLowerCase())}" hidden>${visual}<div class="effect-name">${escapeHtml(label)}</div></div>`;
  const transitionName = (type: string) =>
    type === "crossfade" ? t("trans.crossfade") : type === "dip" ? t("trans.dip") : text(type.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()));
  type CatalogueEntry = { id: string; name: string; category?: string; group?: string };
  void fetch("/api/catalogue")
    .then((res) => (res.ok ? res.json() : Promise.reject(new Error(String(res.status)))))
    .then((data: { video: CatalogueEntry[]; audio: CatalogueEntry[]; transitions: string[] }) => {
      const grouped = (entry: CatalogueEntry) => entry.group !== undefined && entry.group !== "Other";
      const glyph = `<div class="effect-thumb has-glyph">${icon("speaker")}</div>`;
      fxGrid.insertAdjacentHTML(
        "beforeend",
        [
          ...data.video.filter(grouped).map((v) => fxCard(v.category === "Color" ? "filter" : "effect", "video", v.group!, v.id, text(v.name), thumb("effect", v.id))),
          ...MASKS.map(([shape, label]) => fxCard("effect", "mask", "Mask", shape, label, thumb("mask", shape))),
          ...CUTOUTS.map(([model, label]) => fxCard("effect", "cutout", "Cutout", model, label, thumb("source", "cutout"))),
          ...data.audio.filter(grouped).map((a) => fxCard("effect", "audio", a.group!, a.id, text(a.name), glyph)),
        ].join(""),
      );
      transGrid.insertAdjacentHTML(
        "beforeend",
        data.transitions.map((type) => `<div class="effect-card trans-card" data-trans="${escapeHtml(type)}">${thumb("transition", type)}<div class="effect-name">${escapeHtml(transitionName(type))}</div></div>`).join(""),
      );
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
  fxGrid.addEventListener("click", async (ev) => {
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
        if (clip.cutout?.model === value) {
          engine.dispatch("clip.creator", { clipId: clip.id, patch: { cutout: undefined } });
          say(`${t("fx.removed")}: ${label}`);
          return;
        }
        const models = (await (await fetch("/api/models")).json()) as Array<{ id: string; ready: boolean }>;
        if (!models.find((m) => m.id === value)?.ready) {
          say(t("fx.needmodel"));
          return;
        }
        const target = engine.findClip(clip.id)?.clip;
        if (!target) return;
        engine.dispatch("clip.creator", { clipId: target.id, patch: { cutout: { model: value, threshold: 0.5, feather: 0.1, strokes: target.cutout?.strokes ?? [] } } });
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
  const textView = el.querySelector<HTMLElement>('[data-view="text"]')!;
  const transView = el.querySelector<HTMLElement>('[data-view="transitions"]')!;
  const tmplView = el.querySelector<HTMLElement>('[data-view="templates"]')!;
  tabs.addEventListener("click", (ev) => {
    const hit = (ev.target as HTMLElement).closest<HTMLElement>(".pane-tab");
    if (!hit) return;
    const tab = hit.dataset.tab;
    const wantMedia = tab === "Media";
    const wantText = tab === "Text";
    const wantTrans = tab === "Transitions";
    const wantTmpl = tab === "Templates";
    const wantEffects = !wantMedia && !wantText && !wantTrans && !wantTmpl;
    if (mediaView.hidden !== !wantMedia) mediaView.hidden = !wantMedia;
    if (textView.hidden !== !wantText) textView.hidden = !wantText;
    if (transView.hidden !== !wantTrans) transView.hidden = !wantTrans;
    if (tmplView.hidden !== !wantTmpl) tmplView.hidden = !wantTmpl;
    if (effectsView.hidden !== !wantEffects) effectsView.hidden = !wantEffects;
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
      await transcribeClip(engine, bin, clipId, show, lang, track);
    } catch (err) {
      show(`${t("cap.failed")}: ${err instanceof Error ? err.message : "?"}`);
    }
    transcribing = false;
  });

  const grid = el.querySelector<HTMLElement>('[data-ref="bingrid"]')!;
  const empty = el.querySelector<HTMLElement>('[data-ref="empty"]')!;
  const filters = el.querySelector<HTMLElement>('[data-ref="filters"]')!;
  const fileInput = el.querySelector<HTMLInputElement>('[data-ref="file"]')!;
  let activeKind: MediaKind | "" = "";

  const cardFor = (item: MediaItem): HTMLElement => {
    const card = document.createElement("div");
    card.className = `effect-card bin-card k-${item.kind}`;
    card.addEventListener("click", () => {
      // Touch layouts have no HTML5 drag and drop; a tap appends the media
      // at the playhead on the matching lane instead.
      if (window.innerWidth > 768) return;
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
    card.innerHTML = `
      <div class="effect-thumb bin-thumb">
        ${item.thumb ? `<img src="${thumbUrl(item)}" alt="" loading="lazy" draggable="false" />` : `<span class="bin-glyph">${icon(item.kind === "audio" ? "speaker" : "pip")}</span>`}
        <span class="dur-chip">${mm}:${ss}</span>
      </div>
      <div class="effect-name">${escapeHtml(item.name)}</div>`;
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

  bin.subscribe((items, added) => {
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
  const stockModal = document.createElement("div");
  stockModal.className = "modal-scrim";
  stockModal.hidden = true;
  stockModal.innerHTML = `
    <div class="modal-panel stock-panel">
      <div class="modal-title">${t("stock.title")}
        <a class="stock-attrib" href="https://www.pexels.com" target="_blank" rel="noreferrer">Photos provided by Pexels</a>
      </div>
      <div class="stock-row">
        <input data-ref="stock-url" placeholder="Paste a video link (yt-dlp)" />
        <button class="tool-chip" data-ref="stock-url-go">${t("stock.urlgo")}</button>
      </div>
      <div class="stock-row">
        <div class="seg" data-ref="stock-kind">
          <button class="is-active" data-val="video">${t("stock.video")}</button>
          <button data-val="photo">${t("stock.photos")}</button>
        </div>
        <input data-ref="stock-q" placeholder="Search Pexels" />
        <button class="tool-chip" data-ref="stock-go">${t("stock.search")}</button>
      </div>
      <div class="stock-note" data-ref="stock-note" hidden></div>
      <div class="card-grid stock-grid" data-ref="stock-grid"></div>
      <div class="stock-row stock-pager">
        <button class="tool-chip" data-ref="stock-prev" disabled>${t("stock.prev")}</button>
        <span class="stock-note" data-ref="stock-page">1</span>
        <button class="tool-chip" data-ref="stock-next" disabled>${t("stock.next")}</button>
      </div>
      <div class="modal-actions"><button class="tool-chip" data-ref="stock-close">${t("stock.close")}</button></div>
    </div>`;
  document.body.append(stockModal);
  const stockGrid = stockModal.querySelector<HTMLElement>('[data-ref="stock-grid"]')!;
  const stockNote = stockModal.querySelector<HTMLElement>('[data-ref="stock-note"]')!;
  const stockQ = stockModal.querySelector<HTMLInputElement>('[data-ref="stock-q"]')!;
  const stockUrl = stockModal.querySelector<HTMLInputElement>('[data-ref="stock-url"]')!;
  const note = (msg: string) => {
    stockNote.hidden = msg === "";
    if (stockNote.textContent !== msg) stockNote.textContent = msg;
  };
  for (const seg of stockModal.querySelectorAll<HTMLElement>(".seg")) {
    seg.addEventListener("click", (ev) => {
      const hit = (ev.target as HTMLElement).closest("button");
      if (!hit || !seg.contains(hit)) return;
      seg.querySelector(".is-active")?.classList.remove("is-active");
      hit.classList.add("is-active");
    });
  }
  el.querySelector('[data-ref="stock"]')!.addEventListener("click", () => {
    stockModal.hidden = false;
  });
  stockModal.querySelector('[data-ref="stock-close"]')!.addEventListener("click", () => {
    stockModal.hidden = true;
  });
  stockModal.addEventListener("pointerdown", (ev) => {
    if (ev.target === stockModal) stockModal.hidden = true;
  });
  let stockPage = 1;
  const pagerPrev = stockModal.querySelector<HTMLButtonElement>('[data-ref="stock-prev"]')!;
  const pagerNext = stockModal.querySelector<HTMLButtonElement>('[data-ref="stock-next"]')!;
  const pagerLabel = stockModal.querySelector<HTMLElement>('[data-ref="stock-page"]')!;
  const runSearch = async () => {
    const kind = stockModal.querySelector<HTMLElement>('[data-ref="stock-kind"] .is-active')!.dataset.val!;
    note(t("stock.searching"));
    try {
      const res = await fetch("/api/stock/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: stockQ.value, kind, per_page: 18, page: stockPage }),
      });
      if (!res.ok) {
        const detail = ((await res.json()) as { detail?: string }).detail;
        note(detail ?? `Search failed (${res.status})`);
        return;
      }
      const data = (await res.json()) as {
        items: Array<{
          preview: string | null; full: string | null; type: string;
          credit: string | null; page_url: string | null; alt?: string | null;
        }>;
        has_next?: boolean;
        page?: number;
      };
      pagerPrev.disabled = stockPage <= 1;
      pagerNext.disabled = !data.has_next;
      if (pagerLabel.textContent !== String(stockPage)) pagerLabel.textContent = String(stockPage);
      note(data.items.length === 0 ? t("stock.noresults") : "");
      stockGrid.innerHTML = data.items
        .filter((i) => i.full)
        .map(
          (i, n) => `
        <div class="effect-card stock-card" data-n="${n}">
          <div class="effect-thumb stock-thumb" style="background-image:url('${i.preview ?? ""}')"></div>
          <div class="effect-name">${i.credit ?? "Pexels"}</div>
        </div>`,
        )
        .join("");
      stockGrid.dataset.payload = JSON.stringify(data.items.filter((i) => i.full));
    } catch {
      note(t("stock.netfail"));
    }
  };
  stockModal.querySelector('[data-ref="stock-go"]')!.addEventListener("click", () => {
    stockPage = 1;
    void runSearch();
  });
  pagerPrev.addEventListener("click", () => {
    if (stockPage > 1) {
      stockPage -= 1;
      void runSearch();
    }
  });
  pagerNext.addEventListener("click", () => {
    stockPage += 1;
    void runSearch();
  });
  stockQ.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") void runSearch();
  });
  stockGrid.addEventListener("click", async (ev) => {
    const card = (ev.target as HTMLElement).closest<HTMLElement>(".stock-card");
    if (!card) return;
    const items = JSON.parse(stockGrid.dataset.payload ?? "[]") as Array<{
      full: string; type: string; credit: string | null; page_url: string | null; alt?: string | null;
    }>;
    const item = items[Number(card.dataset.n)];
    if (!item) return;
    note(t("stock.importing"));
    const res = await fetch("/api/stock/import", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: item.full,
        kind: item.type,
        name: item.alt || item.credit || "pexels",
        credit: item.credit,
        page_url: item.page_url,
      }),
    });
    note(res.ok ? t("stock.imported") : t("stock.importfail"));
    if (res.ok) await bin.load();
  });
  stockModal.querySelector('[data-ref="stock-url-go"]')!.addEventListener("click", async () => {
    const url = stockUrl.value.trim();
    if (!url) return;
    note(t("stock.downloading"));
    try {
      const res = await fetch("/api/stock/url", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      if (!res.ok) {
        note(t("stock.importfail"));
        return;
      }
      const { job_id: jobId } = (await res.json()) as { job_id: string };
      const poll = async () => {
        const status = (await (await fetch(`/api/stock/url/${jobId}`)).json()) as {
          status: string; error?: string;
        };
        if (status.status === "done") {
          note(t("stock.imported"));
          stockUrl.value = "";
          await bin.load();
          return;
        }
        if (status.status === "error") {
          note(`${t("stock.importfail")}: ${status.error ?? "?"}`);
          return;
        }
        window.setTimeout(() => void poll(), 800);
      };
      void poll();
    } catch {
      note(t("stock.netfail"));
    }
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
