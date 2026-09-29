// The home screen. It used to be a panel with two buttons and a list of recent
// projects; a local editor's home is also where its library lives, so this is a
// surface with a sidebar: projects, media, templates, models and storage.
//
// Everything here reads the engine's own endpoints, and every action is one that
// works: import, rename, reveal and delete for media, open for projects, and a
// measured storage breakdown that says which parts are derived and so can be
// deleted without losing anything.
import { escapeHtml } from "./safe-text";
import { mediaView, openViewer, type ViewItem } from "./viewer";
import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { loadDemoProject } from "../engine/demo";
import { listProjects, newProject, openProject, listJournals, restoreJournal, clearJournal } from "../engine/persistence";
import { api } from "../engine/api";
import { icon } from "./icons";
import { reconcile } from "./keyed-list";
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
  const panels = new Map<string, HTMLElement>();
  const panel = (name: string) => {
    let node = panels.get(name);
    if (!node) {
      node = document.createElement("div");
      node.className = "home-view";
      node.dataset.panel = name;
      node.hidden = true;
      panels.set(name, node);
      body.append(node);
    }
    return node;
  };
  const emptyNote = (host: HTMLElement, message: string | null) => {
    let note = host.querySelector<HTMLElement>(":scope > .panel-note");
    if (!note) {
      note = document.createElement("p");
      note.className = "panel-note";
      host.append(note);
    }
    if (message === null) {
      if (!note.hidden) note.hidden = true;
      return;
    }
    if (note.textContent !== message) note.textContent = message;
    if (note.hidden) note.hidden = false;
  };
  const child = (host: HTMLElement, className: string, tag = "div") => {
    let node = host.querySelector<HTMLElement>(`:scope > .${className.split(" ")[0]}`);
    if (!node) {
      node = document.createElement(tag);
      node.className = className;
      host.append(node);
    }
    return node;
  };

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

  const projectCards = new Map<string, HTMLElement>();
  const projectRecords = new Map<string, Record<string, number | string | boolean>>();
  const renderProjects = async () => {
    const host = panel("projects");
    const grid = child(host, "home-grid");
    const journalsPending = listJournals();
    let projects: Array<{ id: string; title: string }> = [];
    try {
      projects = await fetch("/api/projects/summaries").then((r) => r.json());
    } catch {
      say(t("home.offline"));
    }
    const journals = await journalsPending;
    const newest = journals.length ? journals.sort((a, b) => b.written - a.written)[0] : null;
    const bar = host.querySelector<HTMLElement>(":scope > .restore-bar");
    if (!newest && bar) bar.remove();
    if (newest && bar?.dataset.key !== newest.key) {
      bar?.remove();
      const fresh = document.createElement("div");
      fresh.className = "restore-bar";
      fresh.dataset.ref = "restore";
      fresh.dataset.key = newest.key;
      fresh.innerHTML = `<span>${t("save.recover")}: ${newest.title || t("start.new")}</span><button class="tool-chip is-primary" data-restore="${newest.key}">${t("save.restore")}</button><button class="tool-chip" data-discard="${newest.key}">${t("save.discard")}</button>`;
      fresh.querySelector("[data-restore]")!.addEventListener("click", () => void (async () => {
        if (await restoreJournal(engine, newest.key)) {
          void clearJournal(newest.key);
          dismiss();
        }
      })());
      fresh.querySelector("[data-discard]")!.addEventListener("click", () => void (async () => {
        await clearJournal(newest.key);
        fresh.remove();
      })());
      host.prepend(fresh);
    }
    count(projects.length, t("home.projects").toLowerCase());
    emptyNote(host, projects.length ? null : t("home.noprojects"));
    if (!projects.length) {
      reconcile(grid, []);
      projectCards.clear();
      projectRecords.clear();
      return;
    }
    // F14: a card a person can recognise. The cover is a frame from the project
    // itself, and what is written on it is what tells two projects apart: when
    // it was last touched, how long it runs, how much is in it.
    const when = (stamp: number) => {
      if (!stamp) return t("home.never");
      const ago = Date.now() / 1000 - stamp;
      if (ago < 3600) return `${Math.max(1, Math.round(ago / 60))} ${t("home.minutes")}`;
      if (ago < 86400) return `${Math.round(ago / 3600)} ${t("home.hours")}`;
      return new Date(stamp * 1000).toLocaleDateString();
    };
    const runtime = (seconds: number) => {
      const whole = Math.round(seconds);
      return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
    };
    const ordered: HTMLElement[] = [];
    for (const project of projects as Array<Record<string, number | string | boolean>>) {
      const id = String(project.id);
      projectRecords.set(id, project);
      const facts =
        `<span>${when(Number(project.updated) || 0)}</span>` +
        `<span>${runtime(Number(project.duration) || 0)}</span>` +
        `<span>${Number(project.clips) || 0} ${t("home.clips")}</span>`;
      const format = `${project.width ?? ""}${project.width ? "x" : ""}${project.height ?? ""}`;
      const art = project.cover
        ? `<img src="/api/projects/${id}/cover" alt="" loading="lazy">`
        : icon("film");
      const known = projectCards.get(id);
      if (known) {
        const label = known.querySelector<HTMLElement>("[data-name]")!;
        const title = String(project.title || t("start.new"));
        if (!label.querySelector("input") && label.textContent !== title) label.textContent = title;
        const factsNode = known.querySelector<HTMLElement>(".home-card-facts")!;
        if (factsNode.innerHTML !== facts) factsNode.innerHTML = facts;
        const formatNode = known.querySelector<HTMLElement>(".home-card-format")!;
        if (formatNode.textContent !== format) formatNode.textContent = format;
        const artNode = known.querySelector<HTMLElement>(".home-card-art")!;
        if ((artNode.dataset.cover === "1") !== Boolean(project.cover)) {
          artNode.innerHTML = art;
          artNode.dataset.cover = project.cover ? "1" : "0";
        }
        ordered.push(known);
        continue;
      }
      const card = document.createElement("div");
      card.className = "home-card is-project";
      card.dataset.open = id;
      card.innerHTML =
        `<div class="home-card-open" role="button" tabindex="0" data-open-project="${id}">` +
        `<span class="home-card-art" data-cover="${project.cover ? "1" : "0"}">${art}</span>` +
        `<span class="home-card-name" data-name>${escapeHtml(String(project.title || t("start.new")))}</span>` +
        `<span class="home-card-facts">` +
        facts +
        `</span>` +
        `<span class="home-card-format">${format}</span>` +
        `</div>` +
        `<span class="home-card-tools">` +
        `<button class="iconbtn" data-rename="${id}" title="${t("home.rename")}">${icon("text")}</button>` +
        `<button class="iconbtn" data-export="${id}" title="${t("home.exportProject")}" aria-label="${t("home.exportProject")}">${icon("export")}</button>` +
        `<button class="iconbtn" data-delete="${id}" title="${t("home.delete")}" aria-label="${t("home.delete")}">${icon("trash")}</button>` +
        `</span>`;
      const opener = card.querySelector<HTMLElement>("[data-open-project]")!;
      const open = () => void (async () => {
        await openProject(engine, id);
        dismiss();
      })();
      // A project travels as one .fc file: the document, its media, fonts,
      // LUTs and shaders. The download comes from the engine, which streams it.
      card.querySelector("[data-export]")!.addEventListener("click", (event) => {
        event.stopPropagation();
        const link = document.createElement("a");
        link.href = `/api/projects/${id}/package`;
        link.download = `${String((projectRecords.get(id) ?? project).title || "project")}.fc`;
        link.click();
        say(t("home.exporting"));
      });
      card.querySelector("[data-delete]")!.addEventListener("click", (event) => {
        event.stopPropagation();
        const title = String((projectRecords.get(id) ?? project).title || t("start.new"));
        if (!window.confirm(`${t("home.delete")}: ${title}`)) return;
        void (async () => {
          try {
            const response = await fetch(`/api/projects/${id}`, { method: "DELETE", headers: { "x-formcut-local": "1" } });
            if (!response.ok) throw new Error(String(response.status));
            say(t("home.deleted"));
            await renderProjects();
          } catch (error) {
            say(error instanceof Error ? error.message : t("home.failed"));
          }
        })();
      });
      opener.addEventListener("click", (event) => {
        if ((event.target as HTMLElement).closest(".home-rename")) return;
        open();
      });
      opener.addEventListener("keydown", (event) => {
        if (event.target !== opener || (event.key !== "Enter" && event.key !== " ")) return;
        event.preventDefault();
        open();
      });
      card.querySelector("[data-rename]")!.addEventListener("click", (event) => {
        event.stopPropagation();
        const record = projectRecords.get(id) ?? project;
        const label = card.querySelector<HTMLElement>("[data-name]")!;
        const field = document.createElement("input");
        field.className = "home-rename";
        field.value = String(record.title || "");
        field.maxLength = 120;
        label.replaceChildren(field);
        field.focus();
        field.select();
        let finished = false;
        const finish = async (commit: boolean) => {
          if (finished) return;
          finished = true;
          const next = field.value.trim();
          label.textContent = commit && next ? next : String(record.title || "");
          if (!commit || !next || next === record.title) return;
          await fetch(`/api/projects/${id}`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json", "x-formcut-local": "1" },
            body: JSON.stringify({ title: next }),
          });
          record.title = next;
        };
        field.addEventListener("keydown", (key) => {
          key.stopPropagation();
          if (key.key === "Enter") { key.preventDefault(); void finish(true); }
          if (key.key === "Escape") void finish(false);
        });
        field.addEventListener("click", (press) => press.stopPropagation());
        field.addEventListener("blur", () => void finish(true));
      });
      projectCards.set(id, card);
      ordered.push(card);
    }
    const wantedIds = new Set(projects.map((project) => String(project.id)));
    for (const id of projectCards.keys()) {
      if (!wantedIds.has(id)) {
        projectCards.delete(id);
        projectRecords.delete(id);
      }
    }
    reconcile(grid, ordered);
    await renderSynced(host);
  };
  // Synced projects: the .fc packages found in every sync folder a project names
  // (a folder the person's own Drive, Dropbox or iCloud client carries). A row
  // per package with an Import chip; the list is patched in place and hidden
  // when there is nothing to show, so a person with no sync folder never sees it.
  const syncedNodes = new Map<string, HTMLElement>();
  const renderSynced = async (host: HTMLElement) => {
    let found: Array<{ path: string; title: string; exported?: number; media?: number; folder: string }> = [];
    try {
      found = await fetch("/api/projects/synced").then((r) => (r.ok ? r.json() : []));
    } catch {
      found = [];
    }
    let block = host.querySelector<HTMLElement>(":scope > .home-synced");
    if (!found.length) {
      if (block) block.remove();
      return;
    }
    if (!block) {
      block = document.createElement("div");
      block.className = "home-synced";
      block.innerHTML = `<h3>${text("Synced projects")}</h3><p class="set-note">${text("Packages in the folders your projects sync to; import one to open it on this machine.")}</p><div class="home-synced-list"></div>`;
      host.append(block);
    }
    const list = block.querySelector<HTMLElement>(".home-synced-list")!;
    const wanted = new Set(found.map((entry) => entry.path));
    for (const [path, node] of syncedNodes) if (!wanted.has(path)) { node.remove(); syncedNodes.delete(path); }
    const ordered: HTMLElement[] = [];
    for (const entry of found) {
      let node = syncedNodes.get(entry.path);
      if (!node) {
        node = document.createElement("div");
        node.className = "home-synced-row";
        node.innerHTML = `<span class="home-synced-title"></span><span class="home-synced-meta"></span><button type="button" class="tool-chip is-primary" data-import-synced>${icon("import")}${text("Import")}</button>`;
        node.querySelector("[data-import-synced]")!.addEventListener("click", () => void (async () => {
          try {
            const response = await fetch("/api/projects/synced/import", { method: "POST", headers: { "Content-Type": "application/json", "x-formcut-local": "1" }, body: JSON.stringify({ path: entry.path }) });
            if (!response.ok) throw new Error(String(response.status));
            say(text("Imported"));
            await renderProjects();
          } catch (error) {
            say(error instanceof Error ? error.message : String(error));
          }
        })());
        syncedNodes.set(entry.path, node);
      }
      const title = node.querySelector<HTMLElement>(".home-synced-title")!;
      if (title.textContent !== entry.title) title.textContent = entry.title;
      const meta = `${entry.folder}${entry.media ? ` · ${entry.media} media` : ""}`;
      const metaNode = node.querySelector<HTMLElement>(".home-synced-meta")!;
      if (metaNode.textContent !== meta) metaNode.textContent = meta;
      ordered.push(node);
    }
    reconcile(list, ordered);
  };

  // --- media ----------------------------------------------------------------

  const mediaCards = new Map<string, HTMLElement>();
  const mediaRecords = new Map<string, MediaItem>();
  const renderMedia = () => {
    const host = panel("media");
    const filters = child(host, "home-filters seg");
    if (!filters.children.length) {
      for (const name of KINDS) {
        const button = document.createElement("button");
        button.textContent = t(`home.kind.${name}`);
        button.dataset.kind = name;
        button.addEventListener("click", () => {
          kind = name;
          renderMedia();
        });
        filters.append(button);
      }
    }
    for (const button of filters.children) {
      button.classList.toggle("is-active", (button as HTMLElement).dataset.kind === kind);
    }
    const grid = child(host, "home-grid");

    const term = search.value.trim().toLowerCase();
    const shown = media.filter((item) => (kind === "all" || item.kind === kind) && (!term || item.name.toLowerCase().includes(term)));
    count(shown.length, t("home.items"));
    emptyNote(host, shown.length ? null : media.length ? t("home.nomatch") : t("home.nomedia"));
    if (!shown.length) {
      reconcile(grid, []);
      return;
    }
    const ordered: HTMLElement[] = [];
    for (const item of shown) {
      mediaRecords.set(item.id, item);
      const meta = `${item.kind}${item.duration ? ` · ${clock(item.duration)}` : ""}${item.width ? ` · ${item.width}x${item.height}` : ""}`;
      const known = mediaCards.get(item.id);
      if (known) {
        const name = known.querySelector<HTMLElement>(".home-card-name")!;
        if (name.textContent !== item.name) name.textContent = item.name;
        const metaNode = known.querySelector<HTMLElement>(".home-card-meta")!;
        if (metaNode.textContent !== meta) metaNode.textContent = meta;
        ordered.push(known);
        continue;
      }
      const current = () => mediaRecords.get(item.id) ?? item;
      const card = document.createElement("div");
      card.className = "home-card";
      card.dataset.media = item.id;
      card.innerHTML = `
        <span class="home-card-art">${item.thumb ? `<img src="/api/media/${item.id}/thumb" alt="" loading="lazy" />` : icon(item.kind === "audio" ? "wave" : item.kind === "image" ? "picture" : "film")}</span>
        <span class="home-card-name">${escapeHtml(item.name)}</span>
        <span class="home-card-meta">${meta}</span>
        <span class="home-card-tools"></span>`;
      const tools = card.querySelector<HTMLElement>(".home-card-tools")!;
      const rename = chip(t("home.rename"), () => void (async () => {
        const next = window.prompt(t("home.rename"), current().name);
        if (!next || !next.trim() || next.trim() === current().name) return;
        try {
          await api(`/api/media/${item.id}`, { name: next.trim() }, "PATCH");
          await refreshMedia();
          say(t("home.renamed"));
        } catch (error) {
          say(error instanceof Error ? error.message : t("home.failed"));
        }
      })());
      rename.dataset.act = "rename";
      // View: the picture or video full screen, on its own, the home's other media one arrow away
      const shown = mediaView(item);
      if (shown) {
        const view = chip(t("view.open"), () => {
          const list = [...mediaRecords.values()].map(mediaView).filter((v): v is ViewItem => !!v);
          openViewer(list, Math.max(0, list.findIndex((v) => v.src === shown.src)));
        });
        view.dataset.act = "view";
        tools.append(view);
      }
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
        if (!window.confirm(`${t("home.delete")}: ${current().name}`)) return;
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
      mediaCards.set(item.id, card);
      ordered.push(card);
    }
    const present = new Set(media.map((item) => item.id));
    for (const id of mediaCards.keys()) {
      if (!present.has(id)) {
        mediaCards.delete(id);
        mediaRecords.delete(id);
      }
    }
    reconcile(grid, ordered);
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

  const rowsOf = (host: HTMLElement, lines: string[]) => {
    const rows = child(host, "panel-rows home-rows");
    const existing = Array.from(rows.children) as HTMLElement[];
    lines.forEach((html, index) => {
      let row = existing[index];
      if (!row) {
        row = document.createElement("div");
        row.className = "panel-row";
        rows.append(row);
      }
      if (row.innerHTML !== html) row.innerHTML = html;
    });
    for (const extra of existing.slice(lines.length)) extra.remove();
    if (rows.hidden !== !lines.length) rows.hidden = !lines.length;
  };

  const renderList = async (endpoint: string, line: (entry: Record<string, unknown>) => string, emptyKey: string) => {
    const host = panel(view);
    let entries: Array<Record<string, unknown>> = [];
    try {
      entries = await api(endpoint, undefined, "GET") as Array<Record<string, unknown>>;
    } catch {
      say(t("home.offline"));
    }
    rowsOf(host, entries.map((entry) => `<span>${line(entry)}</span>`));
    emptyNote(host, entries.length ? null : t(emptyKey));
  };

  const renderStorage = async () => {
    const host = panel("storage");
    try {
      const usage = await api("/api/storage", undefined, "GET") as {
        root: string; total: number; reclaimable: number; free: number;
        areas: Array<{ label: string; bytes: number; files: number; derived: boolean }>;
      };
      emptyNote(host, `${usage.root} · ${size(usage.total)} ${t("home.used")} · ${size(usage.reclaimable)} ${t("home.reclaimable")} · ${size(usage.free)} ${t("home.free")}`);
      rowsOf(host, usage.areas.map((area) => `<span>${text(area.label)}${area.derived ? ` · ${t("home.derived")}` : ""}</span><span>${size(area.bytes)} · ${area.files}</span>`));
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
    panel(view);
    for (const [name, node] of panels) {
      if (node.hidden !== (name !== view)) node.hidden = name !== view;
    }
    actions.replaceChildren();
    say("");
    if (view !== "projects" && view !== "media") count(0, "");
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
      picker.addEventListener("change", () => {
        const chosen = Array.from(picker.files ?? []);
        const packages = chosen.filter((file) => file.name.toLowerCase().endsWith(".fc"));
        if (packages.length) void importPackages(packages);
        const others = chosen.filter((file) => !file.name.toLowerCase().endsWith(".fc"));
        if (others.length) void importFiles(others);
      });
      const importChip = chip(t("home.import"), () => picker.click(), "plus");
      importChip.dataset.act = "import";
      actions.append(importChip, picker);
      void refreshMedia();
      return;
    }
    if (view === "templates") {
      void renderList("/api/templates", (entry) => `${entry.nameKey ? t(String(entry.nameKey)) : String(entry.name)} · ${(entry.slots as unknown[] | undefined)?.length ?? 0} ${t("home.slots")}`, "home.notemplates");
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
  const languageMenu = el.querySelector<HTMLSelectElement>('[data-ref="lang"]')!;
  languageMenu.addEventListener("change", (event) => {
    setLocale((event.target as HTMLSelectElement).value);
  });
  // The locales that ship as files (and any a person drops in) arrive after this
  // menu is built; rebuild it when they do, or they can never be chosen.
  document.addEventListener("formcut:locales", () => {
    languageMenu.replaceChildren(...LOCALE_NAMES.map((entry) => {
      const option = document.createElement("option");
      option.value = entry.code;
      option.textContent = entry.name;
      option.dataset.noI18n = "";
      option.selected = entry.code === locale;
      return option;
    }));
  });

  const importPackages = async (files: File[]) => {
    say(t("home.importingProject"));
    let added = 0;
    for (const file of files) {
      const form = new FormData();
      form.append("file", file);
      try {
        const response = await fetch("/api/projects/import", { method: "POST", body: form, headers: { "x-formcut-local": "1" } });
        if (response.ok) added += 1;
        else say((await response.json().catch(() => ({}))).detail ?? t("home.failed"));
      } catch {
        // Keep going: one bad package should not abandon the rest of a drop.
      }
    }
    view = "projects";
    show();
    await renderProjects();
    say(`${t("home.importedProject")}: ${added}/${files.length}`);
  };

  // Dropping files anywhere on the home surface imports them, which is what a
  // person tries first; the media view is shown so the result is visible. A
  // dropped .fc is a project package and lands in the projects view instead.
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
    const packages = Array.from(files).filter((file) => file.name.toLowerCase().endsWith(".fc"));
    const others = Array.from(files).filter((file) => !file.name.toLowerCase().endsWith(".fc"));
    if (packages.length) void importPackages(packages);
    if (others.length) {
      view = "media";
      show();
      void importFiles(others);
    }
  });

  show();
  askInterfaceModeOnce(el);
  return el;
}
