import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { api } from "../engine/api";
import { t } from "../i18n";
import { icon } from "./icons";
import { ERR, ExtensionHost, HostError, PERMISSION_WORDS, type ExtensionRecord, type Frame, type Permission, type Theme } from "../extensions/host-bridge";
import { applyOps, commandList, readDocument, runCommand } from "../extensions/catalogue";

type Row = ExtensionRecord & { kind?: string };
type Listing = { stamp: number[]; root: string; extensions: Row[] };
type Dock = { key: string; ext: Row; panel: string; frame: Frame; wrap: HTMLElement; tab: HTMLButtonElement; title: HTMLElement };

const POLL_MS = 2000;
const MANAGE_URL = "formai://extensions?product=formcut";
const SOURCE_KEYS: Record<string, string> = { catalogue: "ext.source.catalogue", sideload: "ext.source.file", development: "ext.source.development" };
const TOKEN_MAP: Array<[string, string]> = [
  ["--bg", "--ground"], ["--panel", "--pane"], ["--text", "--ink"], ["--muted", "--ink-soft"], ["--accent", "--cue"],
  ["--border", "--edge-strong"], ["--radius", "--radius-m"], ["--accent-text", "--on-cue"], ["--danger", "--fault"],
  ["--float", "--float"], ["--control", "--control"], ["--font-ui", "--font-ui"], ["--font-mono", "--font-mono"],
];

let engineRef: ProjectEngine;
let binRef: MediaBin;
let host: ExtensionHost;
const rows = new Map<string, Row>();
const rowNodes = new Map<string, HTMLElement>();
const docks = new Map<string, Dock>();
let activeDock: string | null = null;
let stamp = "";
let root = "";
let view: HTMLElement;
let sandbox: HTMLElement;
let menu: HTMLElement | null = null;
let dialogsAvailable: boolean | null = null;

const toast = (message: string) => document.dispatchEvent(new CustomEvent("formcut:toast", { detail: { message } }));

function theme(): Theme {
  const style = getComputedStyle(document.documentElement);
  const tokens: Record<string, string> = {};
  for (const [name, source] of TOKEN_MAP) {
    const value = style.getPropertyValue(source).trim();
    if (value) tokens[name] = value;
  }
  return { mode: style.colorScheme.includes("light") && !style.colorScheme.includes("dark") ? "light" : "dark", tokens };
}

function stateOf(ext: Row): "ready" | "needs-permission" | "refused" {
  if (ext.state === "refused") return "refused";
  return host.isGranted(ext) ? "ready" : "needs-permission";
}

async function engineDialogs(): Promise<boolean> {
  if (dialogsAvailable === null) dialogsAvailable = await api<{ available: boolean }>("/api/system/dialogs").then((r) => r.available, () => false);
  return dialogsAvailable;
}

function browserOpen(accept: string[], multiple: boolean): Promise<{ name: string; type: string; size: number; data: string }[]> {
  return new Promise((resolve, reject) => {
    const input = document.createElement("input");
    input.type = "file";
    input.accept = accept.join(",");
    input.multiple = multiple;
    input.addEventListener("cancel", () => reject(new HostError(ERR.CANCELLED, t("ext.cancelled"))));
    input.addEventListener("change", async () => {
      const files = [...(input.files ?? [])];
      if (!files.length) { reject(new HostError(ERR.CANCELLED, t("ext.cancelled"))); return; }
      if (files.reduce((sum, f) => sum + f.size, 0) > 200 * 1024 * 1024) { reject(new HostError(ERR.REFUSED, t("ext.tooLarge"))); return; }
      const out = [];
      for (const file of files) {
        const bytes = new Uint8Array(await file.arrayBuffer());
        let text = "";
        for (let i = 0; i < bytes.length; i += 0x8000) text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
        out.push({ name: file.name, type: file.type || "application/octet-stream", size: file.size, data: btoa(text) });
      }
      resolve(out);
    });
    input.click();
  });
}

function confirmSave(ext: ExtensionRecord, name: string): Promise<string | null> {
  return new Promise((resolve) => {
    const scrim = document.createElement("div");
    scrim.className = "modal-scrim ext-consent ext-save";
    const panel = document.createElement("div");
    panel.className = "modal-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    panel.innerHTML = `<div class="modal-title"></div><p class="modal-note"></p><span class="num-field text-field"><input type="text" spellcheck="false" /></span><div class="modal-actions"><button class="tool-chip" data-act="cancel"></button><button class="tool-chip is-primary" data-act="save"></button></div>`;
    panel.querySelector(".modal-title")!.textContent = t("ext.save.title");
    panel.querySelector(".modal-note")!.textContent = t("ext.save.note").replace("{name}", ext.name);
    const input = panel.querySelector<HTMLInputElement>("input")!;
    input.value = name;
    input.setAttribute("aria-label", t("ext.save.title"));
    panel.querySelector('[data-act="cancel"]')!.textContent = t("ext.save.cancel");
    panel.querySelector('[data-act="save"]')!.textContent = t("ext.save.ok");
    scrim.append(panel);
    const done = (value: string | null) => {
      scrim.remove();
      document.removeEventListener("keydown", onKey, true);
      resolve(value);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") { event.stopPropagation(); done(null); }
      else if (event.key === "Enter" && input.value.trim()) { event.stopPropagation(); done(input.value.trim()); }
    };
    panel.querySelector('[data-act="cancel"]')!.addEventListener("click", () => done(null));
    panel.querySelector('[data-act="save"]')!.addEventListener("click", () => { if (input.value.trim()) done(input.value.trim()); });
    document.addEventListener("keydown", onKey, true);
    document.body.append(scrim);
    input.focus();
    input.setSelectionRange(0, Math.max(0, input.value.lastIndexOf(".")) || input.value.length);
  });
}

function engineError(error: unknown): never {
  throw new HostError(ERR.REFUSED, error instanceof Error ? error.message : String(error));
}

const pendingConsent = new Map<string, Promise<boolean>>();

function consent(ext: ExtensionRecord): Promise<boolean> {
  const key = `${ext.id}@${ext.version}`;
  const waiting = pendingConsent.get(key);
  if (waiting) return waiting;
  const asked = new Promise<boolean>((resolve) => {
    const scrim = document.createElement("div");
    scrim.className = "modal-scrim ext-consent";
    const panel = document.createElement("div");
    panel.className = "modal-panel";
    panel.setAttribute("role", "dialog");
    panel.setAttribute("aria-modal", "true");
    const title = document.createElement("div");
    title.className = "modal-title";
    title.textContent = t("ext.consent.title").replace("{name}", ext.name);
    const note = document.createElement("p");
    note.className = "modal-note";
    note.textContent = t("ext.consent.note").replace("{name}", ext.name).replace("{version}", ext.version).replace("{source}", t(SOURCE_KEYS[ext.source] ?? ext.source));
    const list = document.createElement("ul");
    list.className = "ext-consent-list";
    for (const p of ext.permissions) {
      const item = document.createElement("li");
      item.textContent = PERMISSION_WORDS[p as Permission] ?? p;
      list.append(item);
    }
    const actions = document.createElement("div");
    actions.className = "modal-actions";
    const later = document.createElement("button");
    later.className = "tool-chip";
    later.textContent = t("ext.consent.later");
    const allow = document.createElement("button");
    allow.className = "tool-chip is-primary";
    allow.textContent = t("ext.consent.allow");
    actions.append(later, allow);
    panel.append(title, note, list, actions);
    scrim.append(panel);
    const done = (ok: boolean) => {
      scrim.remove();
      document.removeEventListener("keydown", onKey, true);
      pendingConsent.delete(key);
      resolve(ok);
      paintRows();
    };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { event.stopPropagation(); done(false); } };
    later.addEventListener("click", () => done(false));
    allow.addEventListener("click", () => done(true));
    document.addEventListener("keydown", onKey, true);
    document.body.append(scrim);
    allow.focus();
  });
  pendingConsent.set(key, asked);
  return asked;
}

function makeHost(): ExtensionHost {
  return new ExtensionHost({
    product: "formcut",
    app: "formcut",
    appVersion: __APP_VERSION__,
    locale: () => document.documentElement.lang || "en",
    theme,
    notify: (ext, message) => toast(`${ext.name}: ${message}`),
    setTitle: (ext, frame, title) => {
      for (const dock of docks.values()) if (dock.frame.frame === frame) dock.title.textContent = `${ext.name}: ${title}`;
      const dialog = frame.closest(".ext-dialog")?.querySelector(".modal-title");
      if (dialog) dialog.textContent = `${ext.name}: ${title}`;
    },
    readDocument: (_ext, params) => readDocument(engineRef, binRef, params.what ?? "project"),
    applyDocument: async (_ext, _label, ops) => applyOps(engineRef, binRef, ops),
    commands: () => commandList(),
    run: (_ext, command, args) => runCommand(engineRef, binRef, command, args),
    openFiles: async (_ext, accept, multiple) => {
      if (!(await engineDialogs())) return browserOpen(accept, multiple);
      const files = await api<{ name: string; type: string; size: number; data: string }[]>("/api/extensions/open", { accept, multiple }).catch(engineError);
      if (!files.length) throw new HostError(ERR.CANCELLED, t("ext.cancelled"));
      return files;
    },
    saveFile: async (ext, name, type, data) => {
      let downloads = false;
      if (!(await engineDialogs())) {
        const chosen = await confirmSave(ext, name);
        if (!chosen) throw new HostError(ERR.CANCELLED, t("ext.cancelled"));
        name = chosen;
        downloads = true;
      }
      const saved = await api<{ saved: boolean; name: string }>("/api/extensions/save", { name, type, data, downloads }).catch(engineError);
      if (!saved.saved) throw new HostError(ERR.CANCELLED, t("ext.cancelled"));
      return saved;
    },
    fetch: (_ext, req) => api("/api/extensions/fetch", req).catch(engineError),
    consent,
  });
}

function chip(text: string, cls = "ext-chip") {
  const node = document.createElement("span");
  node.className = cls;
  node.textContent = text;
  return node;
}

function setText(node: Element, text: string) {
  if (node.textContent !== text) node.textContent = text;
}

function buildRow(id: string): HTMLElement {
  const node = document.createElement("div");
  node.className = "ext-row";
  node.dataset.id = id;
  node.innerHTML = `<div class="ext-row-head"><span class="ext-name"></span><span class="ext-version"></span><span class="prov-badge ext-source"></span><span class="prov-badge ext-state"></span></div>
    <div class="ext-desc"></div><div class="ext-chips"></div><div class="ext-reason"></div><div class="ext-actions"></div><div class="ext-path"></div>`;
  return node;
}

function paintRow(node: HTMLElement, ext: Row) {
  const state = stateOf(ext);
  setText(node.querySelector(".ext-name")!, ext.name);
  setText(node.querySelector(".ext-version")!, ext.version);
  setText(node.querySelector(".ext-source")!, t(SOURCE_KEYS[ext.source] ?? ext.source));
  const badge = node.querySelector<HTMLElement>(".ext-state")!;
  setText(badge, t(`ext.state.${state}`));
  const tone = state === "ready" ? "set" : state === "refused" ? "bad" : "none";
  if (badge.dataset.state !== tone) badge.dataset.state = tone;
  if (node.dataset.state !== state) node.dataset.state = state;
  const desc = node.querySelector<HTMLElement>(".ext-desc")!;
  setText(desc, ext.description ?? "");
  desc.hidden = !ext.description;
  const chips = node.querySelector<HTMLElement>(".ext-chips")!;
  const chipKey = ext.permissions.join(",");
  if (chips.dataset.key !== chipKey) {
    chips.dataset.key = chipKey;
    chips.replaceChildren(...ext.permissions.map((p) => chip(t(`ext.perm.${p}`))));
  }
  chips.hidden = !ext.permissions.length;
  const reason = node.querySelector<HTMLElement>(".ext-reason")!;
  setText(reason, ext.reason ?? "");
  reason.hidden = state !== "refused";
  const actions = node.querySelector<HTMLElement>(".ext-actions")!;
  const actionKey = `${state}|${ext.panels.map((p) => p.id + p.title).join(",")}|${ext.commands.map((c) => c.id + c.title).join(",")}`;
  if (actions.dataset.key !== actionKey) {
    actions.dataset.key = actionKey;
    const buttons: HTMLElement[] = [];
    if (state === "needs-permission") {
      const allow = document.createElement("button");
      allow.className = "tool-chip is-primary";
      allow.dataset.act = "allow";
      allow.textContent = t("ext.allow");
      buttons.push(allow);
    }
    if (state !== "refused") {
      for (const panel of ext.panels) {
        const open = document.createElement("button");
        open.className = "tool-chip";
        open.dataset.act = "open";
        open.dataset.panel = panel.id;
        open.innerHTML = `${icon("open")}<span></span>`;
        open.querySelector("span")!.textContent = `${t("ext.open")} ${panel.title}`;
        buttons.push(open);
      }
      for (const command of ext.commands) {
        const run = document.createElement("button");
        run.className = "tool-chip";
        run.dataset.act = "run";
        run.dataset.command = command.id;
        run.innerHTML = `${icon("play")}<span></span>`;
        run.querySelector("span")!.textContent = command.title;
        buttons.push(run);
      }
    }
    actions.replaceChildren(...buttons);
  }
  actions.hidden = !actions.childElementCount;
  const path = node.querySelector<HTMLElement>(".ext-path")!;
  setText(path, ext.source === "development" && ext.path ? ext.path : "");
  path.hidden = !path.textContent;
  path.title = path.textContent ?? "";
}

function paintRows() {
  const list = view.querySelector<HTMLElement>('[data-ref="rows"]')!;
  for (const [id, node] of rowNodes) if (!rows.has(id)) { node.remove(); rowNodes.delete(id); }
  const shown = [...list.children].map((node) => rows.get((node as HTMLElement).dataset.id ?? "")).filter((ext): ext is Row => !!ext);
  const order = [...shown, ...[...rows.values()].filter((ext) => !rowNodes.has(ext.id))];
  order.forEach((ext, index) => {
    let node = rowNodes.get(ext.id);
    if (!node) { node = buildRow(ext.id); rowNodes.set(ext.id, node); }
    paintRow(node, ext);
    if (list.children[index] !== node) list.insertBefore(node, list.children[index] ?? null);
  });
  list.hidden = !order.length;
  view.querySelector<HTMLElement>('[data-ref="empty"]')!.hidden = order.length > 0;
  const folder = view.querySelector<HTMLElement>('[data-ref="root"]')!;
  setText(folder, root ? `${t("ext.root")}: ${root}` : "");
  paintMenu();
}

function paintMenu() {
  if (!menu) return;
  const holder = menu.querySelector<HTMLElement>('[data-ref="commands"]')!;
  const items: Array<{ key: string; label: string; ext: string; command: string; disabled: boolean }> = [];
  for (const ext of rows.values()) {
    if (ext.state === "refused") continue;
    for (const command of ext.commands) items.push({ key: `${ext.id}:${command.id}`, label: `${ext.name}: ${command.title}`, ext: ext.id, command: command.id, disabled: false });
  }
  const existing = new Map([...holder.children].map((node) => [(node as HTMLElement).dataset.key!, node as HTMLButtonElement]));
  items.forEach((item, index) => {
    let node = existing.get(item.key);
    if (!node) {
      node = document.createElement("button");
      node.className = "dropdown-item";
      node.dataset.key = item.key;
      node.dataset.ext = item.ext;
      node.dataset.command = item.command;
    }
    existing.delete(item.key);
    setText(node, item.label);
    if (holder.children[index] !== node) holder.insertBefore(node, holder.children[index] ?? null);
  });
  for (const node of existing.values()) node.remove();
  holder.hidden = !items.length;
  menu.querySelector<HTMLElement>('[data-ref="commands-divider"]')!.hidden = !items.length;
}

function signature(ext: Row) {
  return JSON.stringify(ext);
}

async function refresh(force = false) {
  let listing: Listing;
  try {
    listing = await api<Listing>(`/api/extensions${force ? "?reload=true" : ""}`);
  } catch {
    return;
  }
  stamp = listing.stamp.join(",");
  root = listing.root;
  const next = new Map(listing.extensions.map((ext) => [ext.id, ext]));
  const reopen: Array<{ id: string; panel: string }> = [];
  for (const [id, old] of rows) {
    const fresh = next.get(id);
    const changed = !fresh || signature(fresh) !== signature(old) || (force && old.source === "development");
    if (!changed) continue;
    for (const dock of [...docks.values()]) if (dock.ext.id === id) { reopen.push({ id, panel: dock.panel }); closeDock(dock.key); }
    host.disposeExtension(id);
  }
  rows.clear();
  for (const [id, ext] of next) rows.set(id, ext);
  paintRows();
  for (const again of reopen) {
    const ext = rows.get(again.id);
    if (ext && ext.state !== "refused" && ext.panels.some((p) => p.id === again.panel)) void openPanel(ext, again.panel);
  }
}

async function poll() {
  if (document.hasFocus() && document.visibilityState === "visible") {
    const now = await api<{ stamp: number[] }>("/api/extensions/stamp").catch(() => null);
    if (now && now.stamp.join(",") !== stamp) await refresh();
  }
  window.setTimeout(() => void poll(), POLL_MS);
}

function showTab() {
  document.querySelector<HTMLButtonElement>('.pane-media .pane-tab[data-tab="Extensions"]')?.click();
}

function selectDock(key: string | null) {
  activeDock = key;
  for (const dock of docks.values()) {
    const on = dock.key === key;
    if (dock.wrap.hidden === on) dock.wrap.hidden = !on;
    dock.tab.classList.toggle("is-active", on);
    dock.tab.setAttribute("aria-selected", String(on));
  }
  const area = view.querySelector<HTMLElement>('[data-ref="docks"]')!;
  area.hidden = docks.size === 0;
}

function closeDock(key: string) {
  const dock = docks.get(key);
  if (!dock) return;
  dock.frame.dispose();
  dock.wrap.remove();
  dock.tab.remove();
  docks.delete(key);
  selectDock(activeDock === key ? (docks.keys().next().value ?? null) : activeDock);
}

async function openPanel(ext: Row, panelId: string, activation?: { reason: "command"; command: string; args?: unknown }) {
  const panel = ext.panels.find((p) => p.id === panelId);
  if (!panel) throw new HostError(ERR.NOT_FOUND, `${ext.name} has no panel ${panelId}`);
  const title = `${ext.name}: ${panel.title}`;
  const key = `${ext.id}:${panel.id}`;
  let dock = panel.location === "dialog" ? undefined : docks.get(key);
  if (!dock) {
    const body = document.createElement("div");
    body.className = panel.location === "dialog" ? "ext-dialog-body" : "ext-dock-body";
    const frame = await host.open(ext, body, { onResize: (h) => { if (frame) frame.frame.style.height = `${h}px`; } });
    paintRows();
    if (!frame) {
      if (activation) throw new HostError(ERR.PERMISSION, `${ext.name} was not allowed to run`);
      return null;
    }
    if (panel.location === "dialog") return openDialog(frame, body, panel.id, title, activation);
    const again = docks.get(key);
    if (again) {
      frame.dispose();
      selectDock(key);
      showTab();
      return activation ? again.frame.activate({ ...activation, panel: panel.id }) : null;
    }
    const wrap = document.createElement("section");
    wrap.className = "ext-dock";
    wrap.hidden = true;
    wrap.innerHTML = `<div class="panel-section-head ext-dock-head"><span class="ext-dock-title"></span><button class="iconbtn" data-act="close" aria-label="${t("ext.close")}" title="${t("ext.close")}">${icon("close")}</button></div>`;
    wrap.append(body);
    const heading = wrap.querySelector<HTMLElement>(".ext-dock-title")!;
    heading.textContent = title;
    const tab = document.createElement("button");
    tab.className = "pane-stack-tab ext-dock-tab";
    tab.setAttribute("role", "tab");
    tab.textContent = title;
    tab.addEventListener("click", () => selectDock(key));
    view.querySelector('[data-ref="dock-tabs"]')!.append(tab);
    view.querySelector('[data-ref="dock-frames"]')!.append(wrap);
    dock = { key, ext, panel: panel.id, frame, wrap, tab, title: heading };
    docks.set(key, dock);
    wrap.querySelector('[data-act="close"]')!.addEventListener("click", () => closeDock(key));
    selectDock(key);
    showTab();
    void frame.activate({ reason: "panel", panel: panel.id }).catch(() => undefined);
  } else {
    selectDock(key);
    showTab();
  }
  const shown = dock;
  requestAnimationFrame(() => shown.wrap.scrollIntoView({ block: "nearest" }));
  if (activation) return dock.frame.activate({ ...activation, panel: panel.id });
  return null;
}

function openDialog(frame: Frame, body: HTMLElement, panelId: string, title: string, activation?: { reason: "command"; command: string; args?: unknown }) {
  const scrim = document.createElement("div");
  scrim.className = "modal-scrim";
  const panel = document.createElement("div");
  panel.className = "modal-panel ext-dialog";
  panel.setAttribute("role", "dialog");
  panel.innerHTML = `<div class="ext-dialog-head"><div class="modal-title"></div><button class="iconbtn" data-act="close" aria-label="${t("ext.close")}" title="${t("ext.close")}">${icon("close")}</button></div>`;
  panel.querySelector(".modal-title")!.textContent = title;
  panel.append(body);
  scrim.append(panel);
  document.body.append(scrim);
  const close = () => { frame.dispose(); scrim.remove(); document.removeEventListener("keydown", onKey, true); };
  const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { event.stopPropagation(); close(); } };
  document.addEventListener("keydown", onKey, true);
  panel.querySelector('[data-act="close"]')!.addEventListener("click", close);
  scrim.addEventListener("pointerdown", (event) => { if (event.target === scrim) close(); });
  if (activation) return frame.activate({ ...activation, panel: panelId });
  void frame.activate({ reason: "panel", panel: panelId }).catch(() => undefined);
  return null;
}

async function runExtensionCommand(id: string, commandId: string, args: unknown = {}): Promise<unknown> {
  const ext = rows.get(id);
  if (!ext) throw new HostError(ERR.NOT_FOUND, t("ext.missing").replace("{id}", id));
  if (ext.state === "refused") throw new HostError(ERR.REFUSED, `${ext.name}: ${ext.reason}`);
  const command = ext.commands.find((c) => c.id === commandId);
  if (!command) throw new HostError(ERR.NOT_FOUND, `${ext.name} has no command ${commandId}`);
  if (command.panel) return openPanel(ext, command.panel, { reason: "command", command: command.id, args });
  try {
    return await host.runCommand(ext, command.id, args, sandbox);
  } finally {
    paintRows();
  }
}

function report(error: unknown) {
  toast(error instanceof Error ? error.message : String(error));
}

async function manage() {
  const reply = await api<{ opened: boolean }>("/api/extensions/manage", {}).catch(() => ({ opened: false }));
  if (reply.opened) return;
  const link = document.createElement("a");
  link.href = MANAGE_URL;
  link.click();
}

function listForAgent() {
  return [...rows.values()].map((ext) => ({
    id: ext.id, name: ext.name, version: ext.version, source: ext.source, state: stateOf(ext), reason: ext.reason || "",
    commands: ext.commands.map((c) => ({ id: c.id, title: c.title })),
  }));
}

async function agentLoop() {
  type AgentRequest = { id: string; action: string; extension?: string; command?: string; args?: unknown };
  for (;;) {
    let request: AgentRequest | null;
    try {
      request = (await api<{ request: AgentRequest | null }>("/api/extensions/agent/next?wait=25")).request;
    } catch {
      await new Promise((resolve) => setTimeout(resolve, 3000));
      continue;
    }
    if (!request) continue;
    const ask: AgentRequest = request;
    const id = ask.id;
    const answer = async () => {
      try {
        if (ask.action === "list") return { result: listForAgent() };
        if (ask.action === "run") return { result: (await runExtensionCommand(ask.extension ?? "", ask.command ?? "", ask.args ?? {})) ?? null };
        return { error: { code: ERR.NOT_FOUND, message: `${ask.action} is not a window request` } };
      } catch (error) {
        const e = error as { code?: number; message?: string };
        return { error: { code: typeof e.code === "number" ? e.code : ERR.REFUSED, message: e.message ?? String(error) } };
      }
    };
    void answer().then((body) => api(`/api/extensions/agent/${id}`, body).catch(() => undefined));
  }
}

function watchTheme() {
  let last = JSON.stringify(theme());
  let queued = false;
  const check = () => {
    queued = false;
    const next = theme();
    const text = JSON.stringify(next);
    if (text === last) return;
    last = text;
    host.setTheme(next);
  };
  new MutationObserver(() => { if (!queued) { queued = true; requestAnimationFrame(check); } })
    .observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "style", "class", "data-appearance"] });
}

function watchEngine() {
  const pending = new Set<string>();
  let queued = false;
  const flush = () => {
    queued = false;
    const names = [...pending];
    pending.clear();
    const s = engineRef.snapshot;
    for (const name of names) {
      if (name === "selection") host.broadcast("selection.changed", { clipId: s.selectedClipId, clipIds: [...s.selection] });
      else if (name === "transport") host.broadcast("transport.changed", { playing: s.playing, playhead: s.playhead });
      else host.broadcast("document.changed", { changed: name });
    }
  };
  engineRef.subscribe((state, changed) => {
    const name = changed === "clip-selection" ? "selection" : changed === "transport" || (changed === "playhead" && !state.playing) ? "transport" : ["clips", "timeline", "project"].includes(changed) ? changed : null;
    if (!name) return;
    pending.add(name);
    if (!queued) { queued = true; requestAnimationFrame(flush); }
  });
}

export function buildExtensionsView(engine: ProjectEngine, bin: MediaBin) {
  engineRef = engine;
  binRef = bin;
  host = makeHost();
  view = document.createElement("div");
  view.className = "media-body ext-view";
  view.dataset.view = "extensions";
  view.hidden = true;
  view.innerHTML = `<div class="ext-main">
      <div class="panel-section ext-list">
        <div class="panel-section-head"><span>${t("ext.title")}</span><button class="tool-chip" data-act="reload" title="${t("ext.reload")}">${icon("reset")}${t("ext.reload.short")}</button></div>
        <div class="ext-rows" data-ref="rows" hidden></div>
        <div class="ext-empty" data-ref="empty" hidden><p class="panel-note">${t("ext.empty")}</p><button class="tool-chip is-primary" data-act="manage">${t("ext.manage")}</button></div>
        <small class="panel-note ext-root" data-ref="root"></small>
        <small class="panel-note">${t("ext.packagesNote")}</small>
      </div>
      <div class="ext-docks" data-ref="docks" hidden>
        <div class="ext-dock-tabs" role="tablist" data-ref="dock-tabs"></div>
        <div class="ext-dock-frames" data-ref="dock-frames"></div>
      </div>
    </div>`;
  sandbox = document.createElement("div");
  sandbox.className = "ext-sandbox";
  sandbox.setAttribute("aria-hidden", "true");
  document.body.append(sandbox);
  view.addEventListener("click", (event) => {
    const hit = (event.target as HTMLElement).closest<HTMLElement>("[data-act]");
    if (!hit) return;
    const id = hit.closest<HTMLElement>(".ext-row")?.dataset.id;
    const ext = id ? rows.get(id) : undefined;
    const act = hit.dataset.act;
    if (act === "reload") void refresh(true);
    else if (act === "manage") void manage();
    else if (act === "allow" && ext) void host.ensureConsent(ext).then(paintRows);
    else if (act === "open" && ext) void openPanel(ext, hit.dataset.panel!).catch(report);
    else if (act === "run" && ext) void runExtensionCommand(ext.id, hit.dataset.command!).catch(report);
  });
  watchEngine();
  watchTheme();
  void refresh().then(() => void poll());
  void agentLoop();
  window.addEventListener("focus", () => void api<{ stamp: number[] }>("/api/extensions/stamp").then((now) => { if (now.stamp.join(",") !== stamp) void refresh(); }, () => undefined));
  return { tab: "Extensions", el: view, pause() {}, async load() {} };
}

export function installExtensionsMenu(): void {
  const button = document.querySelector<HTMLButtonElement>('.titlebar-left .menu-item[data-ref="extensions"]');
  if (!button) return;
  menu = document.createElement("div");
  menu.className = "dropdown ext-menu";
  menu.hidden = true;
  menu.innerHTML = `<div data-ref="commands" hidden></div><div class="dropdown-divider" data-ref="commands-divider" hidden></div>
    <button class="dropdown-item" data-act="panel">${t("ext.menu.panel")}</button>
    <button class="dropdown-item" data-act="reload">${t("ext.reload")}</button>
    <button class="dropdown-item" data-act="manage">${t("ext.manage")}</button>`;
  document.body.append(menu);
  const shut = () => { if (menu && !menu.hidden) menu.hidden = true; };
  button.addEventListener("click", () => {
    if (!menu) return;
    const rect = button.getBoundingClientRect();
    menu.style.left = `${rect.left}px`;
    menu.style.top = `${rect.bottom}px`;
    menu.hidden = !menu.hidden;
  });
  document.addEventListener("pointerdown", (event) => { if (menu && !menu.contains(event.target as Node) && !button.contains(event.target as Node)) shut(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") shut(); });
  menu.addEventListener("click", (event) => {
    const hit = (event.target as HTMLElement).closest<HTMLElement>(".dropdown-item");
    if (!hit) return;
    shut();
    if (hit.dataset.command) void runExtensionCommand(hit.dataset.ext!, hit.dataset.command).catch(report);
    else if (hit.dataset.act === "panel") showTab();
    else if (hit.dataset.act === "reload") void refresh(true);
    else if (hit.dataset.act === "manage") void manage();
  });
  paintMenu();
}
