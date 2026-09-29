// Missing media (v2.2.4): the files a project's clips use that are not where it last found them, each with Locate
// (the system's own file dialog, on this computer) and, for all of them, Search a folder: formcut looks through it and
// everything below it, by name and then by fingerprint (a renamed file too), as After Effects finds missing footage.
// A file of another length is asked about before it is used.

import { api } from "../engine/api";
import { t } from "../i18n";
import { escapeHtml } from "./safe-text";

export type MissingItem = { id: string; name?: string; kind?: string; path?: string; duration?: number };

let root: HTMLDivElement | null = null;

async function choose(kind: "open" | "folder", title: string): Promise<string | null> {
  const reply = await api<{ paths: string[] }>("/api/system/choose", { kind, title, multiple: false });
  return reply.paths[0] ?? null;
}

/** Shows the dialog for the items; done() is called once something was relinked and the dialog is closed. */
export function showMissingMedia(items: MissingItem[], done: () => void): void {
  if (!items.length) return;
  root?.remove();
  const dialog = document.createElement("div");
  dialog.className = "missing-media";
  dialog.setAttribute("role", "dialog");
  dialog.setAttribute("aria-modal", "true");
  dialog.innerHTML = `
    <div class="missing-media-panel">
      <h2>${t("missing.title")}</h2>
      <p>${t("missing.lede")}</p>
      <ul class="missing-media-list"></ul>
      <p class="missing-media-note" aria-live="polite"></p>
      <div class="missing-media-actions">
        <button type="button" class="tool-chip" data-act="search">${t("missing.search")}</button>
        <button type="button" class="tool-chip" data-act="close">${t("missing.close")}</button>
      </div>
    </div>`;
  document.body.append(dialog);
  root = dialog;
  let left = [...items];
  let changed = false;
  const list = dialog.querySelector<HTMLUListElement>(".missing-media-list")!;
  const note = dialog.querySelector<HTMLElement>(".missing-media-note")!;
  const paint = () => {
    list.replaceChildren();
    for (const item of left) {
      const row = document.createElement("li");
      row.innerHTML = `<div><strong>${escapeHtml(item.name ?? item.id)}</strong><small>${escapeHtml(item.path ?? "")}</small></div>`;
      const locate = document.createElement("button");
      locate.type = "button"; locate.className = "tool-chip"; locate.textContent = t("missing.locate");
      locate.onclick = () => void relinkOne(item);
      row.append(locate);
      list.append(row);
    }
    if (!left.length) note.textContent = t("missing.none");
  };
  const relinkOne = async (item: MissingItem, force = false, chosen?: string) => {
    try {
      const path = chosen ?? (await choose("open", `${t("missing.locate")} ${item.name ?? ""}`));
      if (!path) return;
      const res = await fetch(`/api/media/${item.id}/relink`, {
        method: "POST",
        headers: { "content-type": "application/json", "x-formcut-local": "1" },
        body: JSON.stringify({ path, force }),
      });
      const reply = await res.json().catch(() => ({}));
      if (res.status === 409 && window.confirm(`${reply.detail}. ${t("missing.useAnyway")}`)) return void relinkOne(item, true, path);
      if (!res.ok) { note.textContent = String(reply.detail ?? res.status); return; }
      changed = true;
      left = left.filter((entry) => entry.id !== item.id);
      paint();
      // one found: the rest are looked for beside it and below
      if (left.length) await searchIn(path.replace(/[\\/][^\\/]*$/, ""));
    } catch (error) {
      note.textContent = error instanceof Error ? error.message : String(error);
    }
  };
  const searchIn = async (folder: string) => {
    note.textContent = t("missing.searching");
    const reply = await api<{ relinked: Array<{ id: string }>; missing: MissingItem[] }>("/api/media/relink-search", { folder, ids: left.map((item) => item.id) });
    if (reply.relinked.length) changed = true;
    left = left.filter((item) => !reply.relinked.some((found) => found.id === item.id));
    paint();
    note.textContent = left.length ? t("missing.found").replace("{n}", String(reply.relinked.length)) : t("missing.none");
  };
  const close = () => {
    dialog.remove();
    if (root === dialog) root = null;
    if (changed) done();
  };
  dialog.querySelector<HTMLButtonElement>('[data-act="search"]')!.addEventListener("click", () => void (async () => {
    try {
      const folder = await choose("folder", t("missing.search"));
      if (folder) await searchIn(folder);
    } catch (error) {
      note.textContent = error instanceof Error ? error.message : String(error);
    }
  })());
  dialog.querySelector<HTMLButtonElement>('[data-act="close"]')!.addEventListener("click", close);
  dialog.addEventListener("keydown", (event) => { if (event.key === "Escape") { event.stopPropagation(); close(); } });
  paint();
  dialog.querySelector<HTMLButtonElement>('[data-act="search"]')!.focus();
}
