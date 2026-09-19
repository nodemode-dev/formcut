// The home screen. It used to be a panel with two buttons and a list of recent
// projects; a local editor's home is also where its library lives, so this is a
// surface with a sidebar: projects, media, templates, models and storage.
//
// Everything here reads the engine's own endpoints, and every action is one that
// works: import, rename, reveal and delete for media, open for projects, and a
// measured storage breakdown that says which parts are derived and so can be
// deleted without losing anything.
import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { loadDemoProject } from "../engine/demo";
import { listProjects, newProject, openProject, listJournals, restoreJournal, clearJournal } from "../engine/persistence";
import { api } from "../engine/api";
import { icon } from "./icons";
import { activeProfile } from "./interface-mode";
import { LOCALE_NAMES, locale, setLocale, t } from "../i18n";
import { text } from "../i18n/text";
import { askInterfaceModeOnce } from "./mode-popout";

interface MediaItem {
  id: string;
  name: string;
  kind: string;
  duration?: number;
  thumb?: boolean;
  width?: number;
  height?: number;
}

const VIEWS = [
  ["projects", "home.projects", "film"],
  ["media", "home.media", "picture"],
  ["templates", "home.templates", "addTrack"],
  ["models", "home.models", "speak"],
  ["storage", "home.storage", "sliders"],
] as const;

const KINDS = ["all", "video", "audio", "image"] as const;

const size = (bytes: number): string => {
  if (bytes >= 1e9) return `${(bytes / 1e9).toFixed(1)} GB`;
  if (bytes >= 1e6) return `${Math.round(bytes / 1e6)} MB`;
  if (bytes >= 1e3) return `${Math.round(bytes / 1e3)} kB`;
  return `${bytes} B`;
};

const clock = (seconds?: number): string => {
  if (!seconds) return "";
  const total = Math.round(seconds);
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
};

export function buildStartScreen(engine: ProjectEngine, bin: MediaBin): HTMLElement {
  const el = document.createElement("div");
  el.className = "start-overlay";
  el.innerHTML = `
    <aside class="home-rail">
      <div class="start-brand">${icon("logo")}<span>formcut</span></div>
      <p class="home-title">${t("home.library")}</p>
      <nav class="home-nav" data-ref="nav">
        ${VIEWS.map(([id, label, glyph], index) => `<button class="home-tab${index === 0 ? " is-active" : ""}" data-view="${id}">${icon(glyph)}<span>${t(label)}</span></button>`).join("")}
      </nav>
      <div class="home-rail-foot">
        <select class="mini-select" data-ref="lang" aria-label="${t("home.language")}">
          ${LOCALE_NAMES.map((entry) => `<option data-no-i18n value="${entry.code}"${entry.code === locale ? " selected" : ""}>${entry.name}</option>`).join("")}
        </select>
        <div class="start-sub">v${__APP_VERSION__}</div>
      </div>
    </aside>
    <main class="home-main">
      <header class="home-head">
        <strong data-ref="title">${t("home.projects")}</strong>
        <span class="home-count" data-ref="count"></span>
        <input class="home-search" data-ref="search" type="search" placeholder="${t("home.search")}" hidden />
        <span class="spacer"></span>
        <div class="home-actions" data-ref="actions"></div>
      </header>
      <div class="home-body" data-ref="body"></div>
      <div class="home-status" data-ref="status" role="status"></div>
    </main>`;

  const q = <T extends HTMLElement = HTMLElement>(name: string) => el.querySelector<T>(`[data-ref="${name}"]`)!;
  const body = q("body");
  const search = q<HTMLInputElement>("search");
  const actions = q("actions");
  const status = q("status");
  let view: string = "projects";
  let kind: string = "all";
  let media: MediaItem[] = [];

  const dismiss = () => {
    if (!el.hidden) el.hidden = true;
  };
  // The logo in the titlebar brings the person back here, so the start screen
  // is a place they can return to rather than something seen once at launch.
  document.addEventListener("formcut:home", () => {
    el.hidden = false;
    void bin.load();
  });
  const say = (text: string) => {
    status.textContent = text;
  };
  const count = (n: number, unit: string) => {
    const label = n ? `${n} ${unit}` : "";
    if (q("count").textContent !== label) q("count").textContent = label;
  };

  const chip = (label: string, handler: (button: HTMLButtonElement) => void, glyph?: string) => {
    const button = document.createElement("button");
    button.className = "tool-chip";
    button.innerHTML = `${glyph ? icon(glyph) : ""}<span>${label}</span>`;
    button.addEventListener("click", () => handler(button));
    return button;
  };

  // --- new project format ------------------------------------------------------

  const ASPECTS: Array<[string, number, number, string]> = [["9:16", 1080, 1920, "format.vertical"], ["16:9", 1920, 1080, "format.wide"], ["1:1", 1080, 1080, "format.square"], ["4:5", 1080, 1350, "format.portrait"]];
  const RATES = [24, 25, 30, 50, 60];
  let format = { width: 1080, height: 1920, fps: 30 };
  const sheet = document.createElement("div");
  sheet.className = "mode-ask format-sheet";
  sheet.hidden = true;
  sheet.innerHTML = `<div class="mode-ask-card"><strong>${t("format.title")}</strong>
    <div class="mode-cards format-cards" data-ref="aspects">${ASPECTS.map(([ratio, w, h, key]) => `<button class="mode-card format-card${w === 1080 && h === 1920 ? " is-active" : ""}" data-w="${w}" data-h="${h}"><i class="format-shape" style="aspect-ratio:${w}/${h}"></i><strong>${ratio}</strong><span>${t(key)} · ${w}x${h}</span></button>`).join("")}</div>
    <div class="format-rates"><span>${t("format.rate")}</span><div class="seg" data-ref="rates">${RATES.map((rate) => `<button data-fps="${rate}"${rate === 30 ? ' class="is-active"' : ""}>${rate}</button>`).join("")}</div></div>
    <div class="mode-actions format-actions"><button class="tool-chip" data-ref="format-cancel">${t("export.cancel")}</button><button class="tool-chip is-primary" data-ref="format-create">${icon("plus")}${t("start.new")}</button></div></div>`;
  el.append(sheet);
  sheet.querySelector('[data-ref="aspects"]')!.addEventListener("click", (event) => {
    const hit = (event.target as HTMLElement).closest<HTMLElement>("[data-w]");
    if (!hit) return;
    format = { ...format, width: Number(hit.dataset.w), height: Number(hit.dataset.h) };
    for (const card of sheet.querySelectorAll<HTMLElement>("[data-w]")) card.classList.toggle("is-active", card === hit);
  });
  sheet.querySelector('[data-ref="rates"]')!.addEventListener("click", (event) => {
    const hit = (event.target as HTMLElement).closest<HTMLElement>("[data-fps]");
    if (!hit) return;
    format = { ...format, fps: Number(hit.dataset.fps) };
    for (const button of sheet.querySelectorAll<HTMLElement>("[data-fps]")) button.classList.toggle("is-active", button === hit);
  });
  sheet.querySelector('[data-ref="format-cancel"]')!.addEventListener("click", () => { sheet.hidden = true; });
  sheet.querySelector('[data-ref="format-create"]')!.addEventListener("click", () => {
    sheet.hidden = true;
    newProject(engine, format, activeProfile().behaviour.magneticMain);
    dismiss();
  });
  const openFormatSheet = () => { sheet.hidden = false; sheet.querySelector<HTMLElement>('[data-ref="format-create"]')!.focus(); };

  // --- projects --------------------------------------------------------------

  const openDemo = async (button: HTMLButtonElement) => {
    if (el.dataset.busy) return;
    el.dataset.busy = "demo";
    const label = button.querySelector("span")!;
    const idle = label.textContent;
    label.textContent = t("start.demo.loading");
    try {
      await loadDemoProject(engine, bin);
      dismiss();
    } catch (error) {
      say(error instanceof Error ? error.message : t("home.failed"));
    } finally {
      label.textContent = idle;
      delete el.dataset.busy;
    }
  };

  const renderProjects = async () => {
    body.replaceChildren();
    const grid = document.createElement("div");
    grid.className = "home-grid";
    body.append(grid);
    let projects: Array<{ id: string; title: string }> = [];
    try {
      projects = await listProjects();
    } catch {
      say(t("home.offline"));
    }
    count(projects.length, t("home.projects").toLowerCase());
    if (!projects.length) {
      const note = document.createElement("p");
      note.className = "panel-note";
      note.textContent = t("home.noprojects");
      grid.append(note);
      return;
    }
    for (const project of projects) {
      const card = document.createElement("button");
      card.className = "home-card is-project";
      card.dataset.open = project.id;
      card.innerHTML = `<span class="home-card-art">${icon("film")}</span><span class="home-card-name">${project.title}</span>`;
      card.addEventListener("click", () => void (async () => {
        await openProject(engine, project.id);
        dismiss();
      })());
      grid.append(card);
    }
    const journals = await listJournals();
    if (journals.length) {
      const bar = document.createElement("div");
      bar.className = "restore-bar";
      bar.dataset.ref = "restore";
      const newest = journals.sort((a, b) => b.written - a.written)[0];
      bar.innerHTML = `<span>${t("save.recover")}: ${newest.title || t("start.new")}</span><button class="tool-chip is-primary" data-restore="${newest.key}">${t("save.restore")}</button><button class="tool-chip" data-discard="${newest.key}">${t("save.discard")}</button>`;
      bar.querySelector("[data-restore]")!.addEventListener("click", () => void (async () => {
        if (await restoreJournal(engine, newest.key)) {
          void clearJournal(newest.key);
          dismiss();
        }
      })());
      bar.querySelector("[data-discard]")!.addEventListener("click", () => void (async () => {
        await clearJournal(newest.key);
        bar.remove();
      })());
      body.prepend(bar);
    }
  };

  // --- media ----------------------------------------------------------------

  const renderMedia = () => {
    body.replaceChildren();
    const filters = document.createElement("div");
    filters.className = "home-filters seg";
    for (const name of KINDS) {
      const button = document.createElement("button");
      button.textContent = t(`home.kind.${name}`);
      button.dataset.kind = name;
      button.className = name === kind ? "is-active" : "";
      button.addEventListener("click", () => {
        kind = name;
        renderMedia();
      });
      filters.append(button);
    }
    const grid = document.createElement("div");
    grid.className = "home-grid";
    body.append(filters, grid);

    const term = search.value.trim().toLowerCase();
    const shown = media.filter((item) => (kind === "all" || item.kind === kind) && (!term || item.name.toLowerCase().includes(term)));
    count(shown.length, t("home.items"));
    if (!shown.length) {
      const note = document.createElement("p");
      note.className = "panel-note";
      note.textContent = media.length ? t("home.nomatch") : t("home.nomedia");
      grid.append(note);
      return;
    }
    for (const item of shown) {
      const card = document.createElement("div");
      card.className = "home-card";
      card.dataset.media = item.id;
      card.innerHTML = `
        <span class="home-card-art">${item.thumb ? `<img src="/api/media/${item.id}/thumb" alt="" loading="lazy" />` : icon(item.kind === "audio" ? "wave" : item.kind === "image" ? "picture" : "film")}</span>
        <span class="home-card-name">${item.name}</span>
        <span class="home-card-meta">${item.kind}${item.duration ? ` · ${clock(item.duration)}` : ""}${item.width ? ` · ${item.width}x${item.height}` : ""}</span>
        <span class="home-card-tools"></span>`;
      const tools = card.querySelector<HTMLElement>(".home-card-tools")!;
      const rename = chip(t("home.rename"), () => void (async () => {
        const next = window.prompt(t("home.rename"), item.name);
        if (!next || !next.trim() || next.trim() === item.name) return;
        try {
          await api(`/api/media/${item.id}`, { name: next.trim() }, "PATCH");
          await refreshMedia();
          say(t("home.renamed"));
        } catch (error) {
          say(error instanceof Error ? error.message : t("home.failed"));
        }
      })());
      rename.dataset.act = "rename";
      const reveal = chip(t("home.reveal"), () => void (async () => {
        try {
          const result = await api(`/api/media/${item.id}/reveal`, {}) as { opened: boolean; path: string; detail?: string };
          say(result.opened ? result.path : result.detail ?? t("home.failed"));
        } catch (error) {
          say(error instanceof Error ? error.message : t("home.failed"));
        }
      })());
      reveal.dataset.act = "reveal";
      const remove = chip(t("home.delete"), () => void (async () => {
        if (!window.confirm(`${t("home.delete")}: ${item.name}`)) return;
        try {
          await api(`/api/media/${item.id}`, undefined, "DELETE");
          await refreshMedia();
          say(t("home.deleted"));
        } catch (error) {
          say(error instanceof Error ? error.message : t("home.failed"));
        }
      })());
      remove.dataset.act = "delete";
      tools.append(rename, reveal, remove);
      grid.append(card);
    }
  };

  const refreshMedia = async () => {
    try {
      media = await api("/api/media", undefined, "GET") as MediaItem[];
      await bin.load();
    } catch {
      say(t("home.offline"));
    }
    if (view === "media") renderMedia();
  };

  const importFiles = async (files: FileList | File[]) => {
    const list = Array.from(files);
    if (!list.length) return;
    say(t("home.importing"));
    let added = 0;
    for (const file of list) {
      const form = new FormData();
      form.append("file", file);
      try {
        const response = await fetch("/api/media", { method: "POST", body: form, headers: { "x-formcut-local": "1" } });
        if (response.ok) added += 1;
      } catch {
        // Keep going: one bad file should not abandon the rest of a drop.
      }
    }
    await refreshMedia();
    say(`${t("home.imported")}: ${added}/${list.length}`);
  };

  // --- templates, models, storage -------------------------------------------

  const renderList = async (endpoint: string, line: (entry: Record<string, unknown>) => string, emptyKey: string) => {
    body.replaceChildren();
    const rows = document.createElement("div");
    rows.className = "panel-rows home-rows";
    body.append(rows);
    let entries: Array<Record<string, unknown>> = [];
    try {
      entries = await api(endpoint, undefined, "GET") as Array<Record<string, unknown>>;
    } catch {
      say(t("home.offline"));
    }
    if (!entries.length) {
      const note = document.createElement("p");
      note.className = "panel-note";
      note.textContent = t(emptyKey);
      rows.append(note);
      return;
    }
    for (const entry of entries) {
      const row = document.createElement("div");
      row.className = "panel-row";
      row.innerHTML = `<span>${line(entry)}</span>`;
      rows.append(row);
    }
  };

  const renderStorage = async () => {
    body.replaceChildren();
    const rows = document.createElement("div");
    rows.className = "panel-rows home-rows";
    body.append(rows);
    try {
      const usage = await api("/api/storage", undefined, "GET") as {
        root: string; total: number; reclaimable: number; free: number;
        areas: Array<{ label: string; bytes: number; files: number; derived: boolean }>;
      };
      const head = document.createElement("p");
      head.className = "panel-note";
      head.textContent = `${usage.root} · ${size(usage.total)} ${t("home.used")} · ${size(usage.reclaimable)} ${t("home.reclaimable")} · ${size(usage.free)} ${t("home.free")}`;
      rows.append(head);
      for (const area of usage.areas) {
        const row = document.createElement("div");
        row.className = "panel-row";
        row.innerHTML = `<span>${text(area.label)}${area.derived ? ` · ${t("home.derived")}` : ""}</span><span>${size(area.bytes)} · ${area.files}</span>`;
        rows.append(row);
      }
    } catch {
      say(t("home.offline"));
    }
  };

  // --- view switching -------------------------------------------------------

  const show = () => {
    for (const tab of el.querySelectorAll<HTMLElement>("[data-view]")) {
      tab.classList.toggle("is-active", tab.dataset.view === view);
    }
    const entry = VIEWS.find(([id]) => id === view)!;
    q("title").textContent = t(entry[1]);
    search.hidden = view !== "media";
    actions.replaceChildren();
    say("");
    count(0, "");
    if (view === "projects") {
      const fresh = chip(t("start.new"), () => {
        openFormatSheet();
      }, "plus");
      fresh.dataset.act = "new";
      const demo = chip(t("start.demo"), (button) => void openDemo(button), "play");
      demo.dataset.act = "demo";
      actions.append(fresh, demo);
      void renderProjects();
      return;
    }
    if (view === "media") {
      const picker = document.createElement("input");
      picker.type = "file";
      picker.multiple = true;
      picker.hidden = true;
      picker.dataset.ref = "picker";
      picker.addEventListener("change", () => void importFiles(picker.files ?? []));
      const importChip = chip(t("home.import"), () => picker.click(), "plus");
      importChip.dataset.act = "import";
      actions.append(importChip, picker);
      void refreshMedia();
      return;
    }
    if (view === "templates") {
      void renderList("/api/templates", (entry) => `${String(entry.name)} · ${(entry.slots as unknown[] | undefined)?.length ?? 0} ${t("home.slots")}`, "home.notemplates");
      return;
    }
    if (view === "models") {
      void renderList("/api/models", (entry) => `${text(String(entry.name ?? entry.id))} · ${entry.ready ? t("home.ready") : t("home.missing")}`, "home.nomodels");
      return;
    }
    void renderStorage();
  };

  q("nav").addEventListener("click", (event) => {
    const tab = (event.target as HTMLElement).closest<HTMLElement>("[data-view]");
    if (!tab?.dataset.view) return;
    view = tab.dataset.view;
    show();
  });
  search.addEventListener("input", () => {
    if (view === "media") renderMedia();
  });
  el.querySelector<HTMLSelectElement>('[data-ref="lang"]')!.addEventListener("change", (event) => {
    setLocale((event.target as HTMLSelectElement).value);
  });

  // Dropping files anywhere on the home surface imports them, which is what a
  // person tries first; the media view is shown so the result is visible.
  el.addEventListener("dragover", (event) => {
    event.preventDefault();
    el.classList.add("is-dropping");
  });
  el.addEventListener("dragleave", () => el.classList.remove("is-dropping"));
  el.addEventListener("drop", (event) => {
    event.preventDefault();
    el.classList.remove("is-dropping");
    const files = event.dataTransfer?.files;
    if (!files?.length) return;
    view = "media";
    show();
    void importFiles(files);
  });

  show();
  askInterfaceModeOnce(el);
  return el;
}
