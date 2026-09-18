import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import type { Clip } from "../engine/types";
import { api } from "../engine/api";

export function installEditorActions(engine: ProjectEngine, bin: MediaBin): void {
  let copied: Clip | undefined;
  const selection = () => engine.snapshot.selectedClipId ? engine.findClip(engine.snapshot.selectedClipId) : null;
  const duplicate = () => { const found = selection(); if (!found) return; const clip = structuredClone(found.clip); clip.id = crypto.randomUUID(); clip.start += clip.duration; engine.dispatch("clip.add", { trackIndex: found.trackIndex, clip }); engine.dispatch("clip.select", clip.id); };
  const copy = () => { const found = selection(); if (found) copied = structuredClone(found.clip); };
  const paste = () => { if (!copied) return; const clip = structuredClone(copied); clip.id = crypto.randomUUID(); clip.start = engine.snapshot.playhead; engine.dispatch("clip.add", { trackIndex: selection()?.trackIndex ?? 0, clip }); engine.dispatch("clip.select", clip.id); };
  const detach = async () => {
    const found = selection(); if (!found?.clip.mediaId || found.clip.kind !== "video") return;
    const source = found.clip;
    const item = await api(`/api/media/${source.mediaId}/detach`, {});
    await bin.load();
    if (!engine.findClip(source.id)) return;
    engine.dispatch("clip.detach", { clipId: source.id, mediaId: item.id, label: item.name });
  };
  const actions: Array<[string, () => unknown]> = [
    ["Undo", () => engine.dispatch("history.undo")], ["Redo", () => engine.dispatch("history.redo")],
    ["Copy clip", copy], ["Paste clip", paste], ["Duplicate clip", duplicate],
    ["Split at playhead", () => { const f = selection(); if (f) engine.dispatch("clip.split", { clipId: f.clip.id, time: engine.snapshot.playhead }); }],
    ["Detach audio", detach], ["Delete clip", () => { const f = selection(); if (f) engine.dispatch("clip.remove", f.clip.id); }],
  ];
  const bindMenu = (button: HTMLButtonElement, entries: Array<[string, () => unknown]>) => {
    const menu = document.createElement("div"); menu.className = "dropdown"; menu.hidden = true;
    for (const [name, action] of entries) { const item = document.createElement("button"); item.className = "dropdown-item"; item.textContent = name; item.addEventListener("click", () => { menu.hidden = true; void Promise.resolve().then(action).catch(error => window.alert(error.message)); }); menu.append(item); }
    document.body.append(menu);
    button.addEventListener("click", () => { const rect = button.getBoundingClientRect(); menu.style.left = `${rect.left}px`; menu.style.top = `${rect.bottom}px`; menu.hidden = !menu.hidden; });
    document.addEventListener("pointerdown", event => { if (!menu.contains(event.target as Node) && !button.contains(event.target as Node) && !menu.hidden) menu.hidden = true; });
    document.addEventListener("keydown", event => { if (event.key === "Escape") menu.hidden = true; });
  };
  const editBtn = document.querySelector<HTMLButtonElement>('.titlebar-left .menu-item[data-ref="edit"]');
  const viewBtn = document.querySelector<HTMLButtonElement>('.titlebar-left .menu-item[data-ref="view"]');
  if (editBtn) bindMenu(editBtn, actions);
  if (viewBtn) bindMenu(viewBtn, [["Fullscreen", () => document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen()], ["Start", () => engine.dispatch("transport.home")], ["End", () => engine.dispatch("transport.end")]]);
  document.addEventListener("keydown", event => {
    const target = event.target as HTMLElement;
    if (target.closest("input,textarea,select,[contenteditable=true]") || document.querySelector(".modal-scrim:not([hidden]),.start-overlay:not([hidden])")) return;
    const modifier = event.metaKey || event.ctrlKey;
    const key = event.key.toLowerCase();
    if (modifier && ["c", "v", "d"].includes(key)) { event.preventDefault(); ({ c: copy, v: paste, d: duplicate })[key as "c" | "v" | "d"](); }
    if (!modifier && [" ", "k", "j", "l", "arrowleft", "arrowright", "home", "end"].includes(key)) {
      event.preventDefault();
      if (key === " " || key === "k") engine.dispatch("transport.toggle");
      if (key === "l") engine.play();
      if (key === "j" || key === "arrowleft") { engine.pause(); engine.dispatch("transport.step", event.shiftKey ? -10 : -1); }
      if (key === "arrowright") { engine.pause(); engine.dispatch("transport.step", event.shiftKey ? 10 : 1); }
      if (key === "home" || key === "end") engine.dispatch(`transport.${key}`);
    }
  });
  const toolbar = document.querySelector(".tl-toolbar")!;
  const control = (ref: string) => toolbar.querySelector<HTMLButtonElement>(`[data-ref="${ref}"]`);
  control("act-ripple")?.addEventListener("click", () => { const found = selection(); if (found) engine.dispatch("clip.ripple-delete", { clipId: found.clip.id }); });
  control("act-detach")?.addEventListener("click", () => { void detach().catch(error => window.alert(error.message)); });
  control("chip-captions")?.addEventListener("click", () => { document.querySelector<HTMLButtonElement>('[data-tab="Text"]')?.click(); document.querySelector<HTMLElement>('[data-ref="transcribe"]')?.focus(); });
  const speak = control("chip-speak");
  if (speak) { speak.disabled = false; speak.addEventListener("click", () => { document.querySelector<HTMLButtonElement>(".titlebar-right .tool-chip")?.click(); document.querySelector<HTMLButtonElement>('[data-page="speech"]')?.click(); }); }
  control("chip-detach")?.addEventListener("click", () => { void detach().catch(error => window.alert(error.message)); });
}
