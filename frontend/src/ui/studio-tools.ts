import { localizeElement, text } from "../i18n/text";
import { t } from "../i18n";
import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { api, waitJob } from "../engine/api";
import { buildCreatorPanel } from "./creator-panel";
import { icon } from "./icons";

export function installStudioTools(engine: ProjectEngine, bin: MediaBin): void {
  const inspector = buildCreatorPanel(engine);
  document.querySelector(".inspector-body")!.append(inspector);
  const opener = document.createElement("button"); opener.className = "tool-chip"; opener.textContent = "Studio";
  document.querySelector(".titlebar-right")!.prepend(opener);
  const modal = document.createElement("div"); modal.className = "set-scrim studio-modal"; modal.hidden = true;
  const tab = (page: string, glyph: string, label: string, active = false) => `<button class="set-tab${active ? " is-active" : ""}" data-page="${page}">${icon(glyph)}<span>${label}</span></button>`;
  modal.innerHTML = `<div class="set-pair studio-pair">
    <nav class="set-rail" aria-label="Studio"><div class="set-rail-head"><strong>Studio</strong></div>
      <div class="set-tabs">${tab("project", "clapperboard", "Project", true)}${tab("stock", "image", t("stock.title"))}${tab("templates", "template", "Timeline templates")}${tab("speech", "mic", "Local speech")}${tab("models", "box", "Local models")}</div>
    </nav>
    <section class="set-window studio-panel" role="dialog" aria-modal="true" aria-label="Studio tools">
    <header class="set-head"><strong data-page-title>Project</strong><button class="iconbtn" data-close title="Close" aria-label="Close">${icon("close")}</button></header>
    <div class="set-body studio-content">
    <section data-view="project" class="set-view">
      <div class="panel-section"><div class="panel-section-head"><span>Project settings</span></div><div class="panel-rows"><label>Width <input data-width type="number" min="16" max="7680"></label><label>Height <input data-height type="number" min="16" max="7680"></label><label>Frame rate <input data-fps type="number" min="1" max="120"></label><div class="studio-actions"><button class="tool-chip is-primary" data-settings>Apply settings</button></div></div></div>
      <div class="panel-section"><div class="panel-section-head"><span>Timeline structure</span><small>All settings and structure changes support Undo.</small></div><div class="panel-rows"><label>Name <input data-structure-name value="New track"></label><label>Active timeline <select data-timeline></select></label><div class="studio-actions"><button class="tool-chip" data-track-add>${icon("addTrack")}Add track</button><button class="tool-chip" data-timeline-add>${icon("plus")}Add timeline</button><button class="tool-chip" data-timeline-remove>${icon("trash")}Remove active timeline</button></div></div></div>
    </section>
    <section data-view="stock" class="set-view" hidden>
      <div class="panel-section"><div class="panel-section-head"><span>Pexels</span><small><a class="stock-attrib" href="https://www.pexels.com" target="_blank" rel="noreferrer">Photos and videos provided by Pexels</a></small></div><div class="panel-rows">
        <div class="stock-row"><div class="seg" data-stock-kind><button class="is-active" data-val="video">${icon("video")}${t("stock.video")}</button><button data-val="photo">${icon("image")}${t("stock.photos")}</button></div><input data-stock-q type="search" placeholder="Search Pexels" aria-label="Search Pexels"><button class="tool-chip is-primary" data-stock-go>${icon("search")}${t("stock.search")}</button></div>
        <div class="stock-row stock-filters"><label>Orientation <select data-stock-orientation><option value="">Any</option><option value="landscape">Landscape</option><option value="portrait">Portrait</option><option value="square">Square</option></select></label><label>Size <select data-stock-size><option value="">Any</option><option value="large">Large</option><option value="medium">Medium</option><option value="small">Small</option></select></label><label data-stock-color-row>Colour <select data-stock-color><option value="">Any</option><option value="red">Red</option><option value="orange">Orange</option><option value="yellow">Yellow</option><option value="green">Green</option><option value="turquoise">Turquoise</option><option value="blue">Blue</option><option value="violet">Violet</option><option value="pink">Pink</option><option value="brown">Brown</option><option value="black">Black</option><option value="gray">Gray</option><option value="white">White</option></select></label></div>
        <p class="stock-note" data-stock-note></p>
      </div></div>
      <div class="panel-section"><div class="panel-section-head"><span>Import from a link</span><small>yt-dlp, any site it supports</small></div><div class="panel-rows"><div class="stock-row"><input data-stock-url type="url" placeholder="Paste a video link" aria-label="Video link"><button class="tool-chip" data-stock-url-go>${icon("download")}${t("stock.urlgo")}</button></div><p class="stock-note" data-stock-url-note></p></div></div>
      <div class="panel-section stock-results"><div class="panel-section-head"><span>Results</span><small data-stock-page></small></div><div class="card-grid stock-grid" data-stock-grid></div><div class="stock-row stock-pager"><button class="tool-chip" data-stock-prev disabled>${icon("chevL")}${t("stock.prev")}</button><button class="tool-chip" data-stock-next disabled>${t("stock.next")}${icon("chevR")}</button></div></div>
    </section>
    <section data-view="templates" class="set-view" hidden>
      <div class="panel-section"><div class="panel-section-head"><span>Reusable timeline templates</span></div><div class="panel-rows"><label>Name <input data-template-name placeholder="Template name"></label><label>Import template <input type="file" accept=".fctemplate,.json" data-template-import></label><div class="studio-actions"><button class="tool-chip is-primary" data-template-save>${icon("download")}Save current project as template</button></div><div data-template-list></div></div></div>
      <div class="panel-section" data-template-fill hidden><div class="panel-section-head"><span>Fill media slots</span></div><div class="panel-rows"><div data-template-slots></div><label>New project title <input data-template-title value="Untitled from template"></label><label><input type="checkbox" data-template-fit checked> Fit replacement duration to each slot</label><div class="studio-actions"><button class="tool-chip is-primary" data-template-create>Create project</button></div></div></div>
    </section>
    <section data-view="speech" class="set-view" hidden>
      <div class="panel-section"><div class="panel-section-head"><span>Local speech</span><small>Install the local speech runtime once with backend/setup_local_ai.py. Download Kokoro under Local models. Synthesis then runs offline.</small></div><div class="panel-rows"><textarea data-speech-text rows="6" placeholder="Text to speak"></textarea><label>Voice <select data-speech-voice></select></label><label>Language <select data-speech-language><option value="en-us">English (US)</option><option value="en-gb">English (UK)</option><option value="es">Español</option><option value="fr-fr">Français</option><option value="it">Italiano</option><option value="pt-br">Português</option><option value="ja">日本語</option><option value="cmn">中文</option></select></label><label>Speed <input data-speech-speed type="number" min="0.5" max="2" step="0.1" value="1"></label><div class="studio-actions"><button class="tool-chip is-primary" data-speech-create>${icon("speak")}Generate and add to timeline</button></div></div></div>
    </section>
    <section data-view="models" class="set-view" hidden>
      <div class="panel-section"><div class="panel-section-head"><span>Local models</span><small>Download once, then process media locally. You can also import model files acquired separately.</small></div><div class="panel-rows"><div data-model-list></div></div></div>
    </section>
    </div><footer class="set-foot studio-footer"><span role="status" data-status></span><button class="tool-chip" data-cancel hidden>Cancel job</button></footer></section></div>`;
  localizeElement(modal);
  document.body.append(modal);
  const q = <T extends HTMLElement = HTMLInputElement>(name: string) => modal.querySelector<T>(`[data-${name}]`)!;
  let activePage = "project", template: any, controller: AbortController | undefined;
  const say = (text: string) => { if (q("status").textContent !== text) q("status").textContent = text; };
  const run = async (work: () => unknown) => { try { await work(); } catch (error) { say(error instanceof Error ? error.message : String(error)); } };
  const job = async (path: string, data?: unknown) => {
    if (controller) throw new Error("Wait for the current job or cancel it");
    controller = new AbortController(); q("cancel").hidden = false;
    try {
      const started = await api(path, data ?? {});
      return await waitJob(started.job_id, say, controller.signal);
    } finally { q("cancel").hidden = true; controller = undefined; }
  };
  q("cancel").addEventListener("click", () => controller?.abort());
  const reconcileOptions = (select: HTMLSelectElement, entries: Array<{ id: string; name: string }>) => {
    const values = new Set(entries.map(e => e.id));
    for (const option of [...select.options]) if (!values.has(option.value)) option.remove();
    for (const entry of entries) {
      let option = [...select.options].find(o => o.value === entry.id);
      if (!option) { option = document.createElement("option"); option.value = entry.id; select.append(option); }
      if (option.textContent !== entry.name) option.textContent = entry.name;
    }
  };
  const structure = () => {
    const s = engine.snapshot;
    for (const key of ["width", "height", "fps"] as const) if (document.activeElement !== q(key)) q(key).value = String(s[key]);
    reconcileOptions(q<HTMLSelectElement>("timeline"), s.timelines.map((t, i) => ({ id: String(i), name: t.name })));
    q<HTMLSelectElement>("timeline").value = String(s.activeTimeline);
  };
  const templateRows = new Map<string, HTMLElement>();
  const refreshTemplates = async () => {
    const entries = await api<any[]>("/api/templates");
    for (const [id, row] of templateRows) if (!entries.some(e => e.id === id)) { row.remove(); templateRows.delete(id); }
    for (const entry of entries) {
      let row = templateRows.get(entry.id);
      if (!row) {
        row = document.createElement("div"); row.className = "studio-item";
        const label = document.createElement("span"); row.append(label);
        const fill = document.createElement("button"); fill.className = "tool-chip"; fill.textContent = "Fill slots";
        fill.addEventListener("click", () => void run(async () => {
          template = await api(`/api/templates/${entry.id}`);
          const root = q<HTMLElement>("template-slots");
          const live = new Set(template.slots.map((s: any) => s.id));
          for (const item of root.querySelectorAll<HTMLElement>("[data-slot]")) if (!live.has(item.dataset.slot)) item.remove();
          for (const slot of template.slots) {
            let label = [...root.querySelectorAll<HTMLLabelElement>("label")].find(l => l.dataset.slot === slot.id);
            if (!label) { label = document.createElement("label"); label.dataset.slot = slot.id; const name = document.createElement("span"); name.textContent = slot.name; label.append(name, document.createElement("select")); root.append(label); }
            reconcileOptions(label.querySelector("select")!, bin.all.filter(m => m.kind === slot.kind).map(m => ({ id: m.id, name: m.name })));
          }
          q("template-fill").hidden = false;
        }));
        const download = document.createElement("a"); download.className = "tool-chip"; download.textContent = "Export"; download.href = `/api/templates/${entry.id}/file`; download.download = "template.fctemplate";
        const remove = document.createElement("button"); remove.className = "tool-chip"; remove.textContent = "Delete"; remove.addEventListener("click", () => void run(async () => { await api(`/api/templates/${entry.id}`, undefined, "DELETE"); await refreshTemplates(); }));
        row.append(fill, download, remove); templateRows.set(entry.id, row); q("template-list").append(row);
      }
      row.querySelector("span")!.textContent = `${entry.name} · ${entry.slots.length} slots`;
    }
  };
  const modelRows = new Map<string, HTMLElement>();
  const refreshModels = async () => {
    const models = await api<any[]>("/api/models");
    for (const model of models) {
      let row = modelRows.get(model.id);
      if (!row) {
        row = document.createElement("div"); row.className = "studio-model";
        const name = document.createElement("strong"); name.textContent = text(model.name);
        const status = document.createElement("span"); status.dataset.ready = "";
        const download = document.createElement("button"); download.className = "tool-chip"; download.textContent = text("Download");
        download.addEventListener("click", () => void run(async () => { await job(`/api/models/${model.id}/download`); await refreshModels(); say(model.id === "local-speech" ? t("models.readyspeech") : t("models.ready")); }));
        const files = document.createElement("span"); files.textContent = model.files.join(", ");
        const importer = document.createElement("input"); importer.type = "file"; importer.setAttribute("aria-label", text(`Import ${model.name}`));
        importer.addEventListener("change", () => void run(async () => { if (!importer.files?.[0]) return; const body = new FormData(); body.append("file", importer.files[0]); await api(`/api/models/${model.id}/import`, body); await refreshModels(); }));
        row.append(name, status, download, files, importer); modelRows.set(model.id, row); q("model-list").append(row);
        if (model.id === "local-speech") { const note = document.createElement("span"); note.className = "text-add-hint"; note.textContent = t("models.speechsetup"); row.append(note); }
      }
      row.querySelector<HTMLElement>("[data-ready]")!.textContent = model.ready ? "Ready offline" : "Not installed";
      row.querySelector("button")!.disabled = model.ready;
    }
  };
  interface StockItem { id: number; type: string; preview: string | null; full: string | null; width?: number; height?: number; duration?: number; alt?: string | null; page_url: string | null; credit: string | null; credit_url?: string | null }
  const stockGrid = q<HTMLElement>("stock-grid");
  const stockNote = (message: string) => { const node = q<HTMLElement>("stock-note"); if (node.textContent !== message) node.textContent = message; };
  const stockCards = new Map<string, HTMLElement>();
  const stock = {
    loaded: false,
    page: 1,
    kind: "video",
    items: new Map<string, StockItem>(),
    async search(page: number) {
      stock.page = page;
      stockNote(t("stock.searching"));
      try {
        const data = await api<{ items: StockItem[]; page: number; has_next: boolean }>("/api/stock/search", {
          query: q("stock-q").value, kind: stock.kind, page, per_page: 24,
          orientation: q<HTMLSelectElement>("stock-orientation").value, size: q<HTMLSelectElement>("stock-size").value,
          color: stock.kind === "photo" ? q<HTMLSelectElement>("stock-color").value : "", locale: "",
        });
        stock.loaded = true;
        const items = data.items.filter(item => item.full && item.preview);
        stock.items = new Map(items.map(item => [`${item.type}-${item.id}`, item]));
        for (const [key, card] of stockCards) if (!stock.items.has(key)) { card.remove(); stockCards.delete(key); }
        let cursor: Element | null = null;
        for (const [key, item] of stock.items) {
          let card = stockCards.get(key);
          if (!card) {
            card = document.createElement("div"); card.className = "effect-card stock-card"; card.dataset.stock = key;
            card.innerHTML = `<div class="effect-thumb stock-thumb has-image"><img alt="" loading="lazy" draggable="false"><span class="stock-badge"></span></div><div class="effect-name stock-credit"></div><div class="stock-actions"><button class="iconbtn" data-stock-act="media" title="${text("Add to media")}">${icon("plus")}</button><button class="iconbtn" data-stock-act="track" title="${text("Place on a new track at the playhead")}">${icon("addToTrack")}</button><button class="iconbtn" data-stock-act="download" title="${text("Download")}">${icon("download")}</button><a class="iconbtn" data-stock-act="open" target="_blank" rel="noreferrer" title="${text("Open on Pexels")}">${icon("open")}</a></div>`;
            stockCards.set(key, card);
          }
          const img = card.querySelector<HTMLImageElement>("img")!;
          if (img.getAttribute("src") !== item.preview) img.src = item.preview!;
          const badge = card.querySelector<HTMLElement>(".stock-badge")!;
          const badgeText = item.type === "video" ? `${Math.round(item.duration ?? 0)}s` : `${item.width}x${item.height}`;
          if (badge.textContent !== badgeText) badge.textContent = badgeText;
          const credit = card.querySelector<HTMLElement>(".stock-credit")!;
          if (credit.textContent !== (item.credit ?? "Pexels")) credit.textContent = item.credit ?? "Pexels";
          const open = card.querySelector<HTMLAnchorElement>("[data-stock-act=open]")!;
          if (open.href !== (item.page_url ?? "")) open.href = item.page_url ?? "";
          if (cursor ? card.previousElementSibling !== cursor : stockGrid.firstElementChild !== card) stockGrid.insertBefore(card, cursor ? cursor.nextElementSibling : stockGrid.firstElementChild);
          cursor = card;
        }
        q<HTMLButtonElement>("stock-prev").disabled = page <= 1;
        q<HTMLButtonElement>("stock-next").disabled = !data.has_next;
        const pageLabel = `${text("Page")} ${page}`; if (q<HTMLElement>("stock-page").textContent !== pageLabel) q<HTMLElement>("stock-page").textContent = pageLabel;
        stockNote(items.length ? "" : t("stock.noresults"));
      } catch (error) {
        stockNote(error instanceof Error ? error.message : String(error));
      }
    },
    async import(item: StockItem) {
      stockNote(t("stock.importing"));
      const media = await api<{ id: string; name: string; duration: number; kind: string }>("/api/stock/import", { url: item.full, kind: item.type, name: item.alt || item.credit || "pexels", credit: item.credit, page_url: item.page_url });
      await bin.load();
      stockNote(`${t("stock.imported")}: ${media.name}`);
      return media;
    },
  };
  q<HTMLElement>("stock-kind").addEventListener("click", event => {
    const hit = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-val]"); if (!hit) return;
    for (const other of q<HTMLElement>("stock-kind").querySelectorAll("button")) other.classList.toggle("is-active", other === hit);
    stock.kind = hit.dataset.val!;
    q<HTMLElement>("stock-color-row").hidden = stock.kind !== "photo";
    void stock.search(1);
  });
  q("stock-go").addEventListener("click", () => void stock.search(1));
  q("stock-q").addEventListener("keydown", event => { if (event.key === "Enter") void stock.search(1); });
  for (const name of ["stock-orientation", "stock-size", "stock-color"]) q<HTMLSelectElement>(name).addEventListener("change", () => void stock.search(1));
  q("stock-prev").addEventListener("click", () => { if (stock.page > 1) void stock.search(stock.page - 1); });
  q("stock-next").addEventListener("click", () => void stock.search(stock.page + 1));
  const urlNote = (message: string) => { const node = q<HTMLElement>("stock-url-note"); if (node.textContent !== message) node.textContent = message; };
  q("stock-url-go").addEventListener("click", () => void run(async () => {
    const url = q("stock-url").value.trim(); if (!url) return;
    urlNote(t("stock.downloading"));
    const started = await api<{ job_id: string }>("/api/stock/url", { url });
    const poll = async (): Promise<void> => {
      const status = await api<{ status: string; error?: string; media?: { name: string } }>(`/api/stock/url/${started.job_id}`, undefined, "GET");
      if (status.status === "done") { q("stock-url").value = ""; await bin.load(); urlNote(`${t("stock.imported")}: ${status.media?.name ?? ""}`); return; }
      if (status.status === "error") { urlNote(`${t("stock.importfail")}: ${status.error ?? "?"}`); return; }
      window.setTimeout(() => void poll(), 800);
    };
    await poll();
  }));
  stockGrid.addEventListener("click", event => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-stock-act]");
    const card = (event.target as HTMLElement).closest<HTMLElement>("[data-stock]");
    if (!button || !card || button.dataset.stockAct === "open") return;
    const item = stock.items.get(card.dataset.stock!); if (!item) return;
    void run(async () => {
      const media = await stock.import(item);
      if (button.dataset.stockAct === "download") {
        const link = document.createElement("a"); link.href = `/api/media/${media.id}/file`; link.download = media.name; link.click();
      }
      if (button.dataset.stockAct === "track") {
        const timeline = engine.snapshot.timelines[engine.snapshot.activeTimeline];
        engine.dispatch("track.add", { name: item.type === "video" ? text("Stock video") : text("Stock image") });
        const trackIndex = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks.length - 1;
        if (engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timeline.id) return;
        engine.dispatch("clip.add", { trackIndex, clip: { id: crypto.randomUUID(), kind: media.kind, label: media.name, mediaId: media.id, start: engine.snapshot.playhead, duration: Math.max(0.5, media.duration || 5), filmstrip: media.kind === "video" } });
        stockNote(`${text("Placed on the timeline")}: ${media.name}`);
      }
    });
  });
  const showPage = async () => {
    for (const section of modal.querySelectorAll<HTMLElement>("[data-view]")) section.hidden = section.dataset.view !== activePage;
    for (const button of modal.querySelectorAll<HTMLElement>("[data-page]")) {
      button.classList.toggle("is-active", button.dataset.page === activePage);
      if (button.dataset.page === activePage) { const title = button.querySelector("span")?.textContent ?? ""; const slot = q<HTMLElement>("page-title"); if (slot.textContent !== title) slot.textContent = title; }
    }
    if (activePage === "project") structure();
    if (activePage === "stock" && !stock.loaded) await stock.search(1);
    if (activePage === "templates") await refreshTemplates();
    if (activePage === "models") await refreshModels();
    if (activePage === "speech") {
      const voices = await api("/api/speech/voices"); reconcileOptions(q<HTMLSelectElement>("speech-voice"), voices.voices);
      if (!voices.ready) say(t("speech.needmodel"));
      else if (!voices.runtime) say(t("speech.needsetup"));
    }
  };
  opener.addEventListener("click", () => { modal.hidden = false; void run(showPage); q("close").focus(); });
  document.addEventListener("formcut:studio", event => {
    const page = (event as CustomEvent<{ page?: string }>).detail?.page;
    if (page && modal.querySelector(`[data-view="${page}"]`)) activePage = page;
    say(""); modal.hidden = false; void run(showPage); q("close").focus();
  });
  q("close").addEventListener("click", () => { modal.hidden = true; opener.focus(); });
  modal.addEventListener("keydown", event => { if (event.key === "Escape") { modal.hidden = true; opener.focus(); } });
  for (const button of modal.querySelectorAll<HTMLElement>("[data-page]")) button.addEventListener("click", () => { activePage = button.dataset.page!; say(""); void run(showPage); });
  q("settings").addEventListener("click", () => void run(() => { engine.dispatch("project.settings", { width: Number(q("width").value), height: Number(q("height").value), fps: Number(q("fps").value) }); say("Settings updated"); }));
  q("track-add").addEventListener("click", () => void run(() => { engine.dispatch("track.add", { name: q("structure-name").value }); say("Track added"); }));
  q("timeline-add").addEventListener("click", () => void run(() => { engine.dispatch("timeline.add", { name: q("structure-name").value }); structure(); }));
  q("timeline").addEventListener("change", () => engine.dispatch("timeline.activate", Number(q<HTMLSelectElement>("timeline").value)));
  q("timeline-remove").addEventListener("click", () => void run(() => { engine.dispatch("timeline.remove", { index: engine.snapshot.activeTimeline }); structure(); }));
  q("template-save").addEventListener("click", () => void run(async () => { await api("/api/templates", { name: q("template-name").value, project: engine.snapshot }); await refreshTemplates(); say("Template saved"); }));
  q("template-import").addEventListener("change", () => void run(async () => { const file = q("template-import").files?.[0]; if (!file) return; const body = new FormData(); body.append("file", file); await api("/api/templates/import", body); await refreshTemplates(); say("Template imported"); }));
  q("template-create").addEventListener("click", () => void run(async () => {
    const bindings = Object.fromEntries([...q("template-slots").querySelectorAll<HTMLElement>("[data-slot]")].map(row => [row.dataset.slot, row.querySelector("select")!.value]));
    const project = await api(`/api/templates/${template.id}/fill`, { bindings, title: q("template-title").value, fit: q("template-fit").checked });
    engine.dispatch("project.load", project); modal.hidden = true;
  }));
  q("speech-create").addEventListener("click", () => void run(async () => {
    const start = engine.snapshot.playhead;
    const timelineId = engine.snapshot.timelines[engine.snapshot.activeTimeline].id;
    const result = await job("/api/speech", { text: q<HTMLTextAreaElement>("speech-text").value, voice: q<HTMLSelectElement>("speech-voice").value, language: q<HTMLSelectElement>("speech-language").value, speed: Number(q("speech-speed").value) });
    await bin.load();
    if (engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timelineId) { say("Speech saved in Media; the active timeline changed"); return; }
    const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
    const trackIndex = Math.max(0, tracks.findIndex(t => /audio/i.test(t.name)));
    engine.dispatch("clip.add", { trackIndex, clip: { id: crypto.randomUUID(), kind: "audio", label: result.media.name, mediaId: result.media.id, start, duration: result.media.duration } });
    say("Speech added to the timeline");
  }));
  document.addEventListener("pointerdown", event => {
    const canvas = (event.target as HTMLElement).closest<HTMLCanvasElement>(".render-canvas");
    const mode = inspector.dataset.brush;
    const clip = engine.snapshot.selectedClipId ? engine.findClip(engine.snapshot.selectedClipId)?.clip : undefined;
    if (!canvas || (mode !== "keep" && mode !== "erase") || !clip?.cutout) return;
    engine.pause();
    const project = structuredClone(engine.snapshot), timelineId = project.timelines[project.activeTimeline].id;
    const radius = Number(inspector.querySelector<HTMLInputElement>("[data-brush-radius]")!.value);
    canvas.setPointerCapture(event.pointerId);
    const points: number[][] = [];
    const move = (ev: PointerEvent) => { const box = canvas.getBoundingClientRect(); if (points.length < 4096) points.push([(ev.clientX - box.left) / box.width, (ev.clientY - box.top) / box.height]); };
    const cleanup = () => { canvas.removeEventListener("pointermove", move); canvas.removeEventListener("pointerup", end); canvas.removeEventListener("pointercancel", cleanup); };
    const end = () => {
      cleanup();
      void run(async () => {
        const result = await api("/api/render/brush", { project, clipId: clip.id, time: project.playhead, points });
        const current = engine.findClip(clip.id)?.clip;
        if (!current?.cutout || current.mediaId !== clip.mediaId || engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timelineId) throw new Error("The brush target changed.");
        engine.dispatch("clip.creator", { clipId: clip.id, patch: { cutout: { ...current.cutout, strokes: [...current.cutout.strokes, { mode, radius, points: result.points }] } } });
      });
    };
    move(event);
    canvas.addEventListener("pointermove", move); canvas.addEventListener("pointerup", end, { once: true }); canvas.addEventListener("pointercancel", cleanup, { once: true });
  });
}
