import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import type { Clip } from "../engine/types";
import { api } from "../engine/api";
import { rejoinEligibility } from "../engine/creator-commands";
import { sourceTime } from "../engine/timing";
import { t } from "../i18n";

export const editorVerbs: Record<string, () => void> = {};

export function installEditorActions(engine: ProjectEngine, bin: MediaBin): void {
  let copied: Array<{ trackIndex: number; clip: Clip }> = [];
  const selection = () => engine.snapshot.selectedClipId ? engine.findClip(engine.snapshot.selectedClipId) : null;
  const selectedSet = (): string[] => {
    const s = engine.snapshot;
    return s.selection.length ? s.selection : s.selectedClipId ? [s.selectedClipId] : [];
  };
  const duplicate = () => {
    const ids = selectedSet();
    if (ids.length > 1) { engine.dispatch("clips.duplicate", ids); return; }
    const found = selection(); if (!found) return;
    const clip = structuredClone(found.clip); clip.id = crypto.randomUUID(); clip.start += clip.duration;
    engine.dispatch("clip.add", { trackIndex: found.trackIndex, clip });
    engine.dispatch("clip.select", clip.id);
  };
  const copy = () => {
    copied = selectedSet()
      .map((id) => engine.findClip(id))
      .filter((m): m is NonNullable<typeof m> => !!m)
      .map((m) => ({ trackIndex: m.trackIndex, clip: structuredClone(m.clip) }));
  };
  const paste = () => {
    if (!copied.length) return;
    const anchor = Math.min(...copied.map((entry) => entry.clip.start));
    const at = engine.snapshot.playhead;
    const entries = copied.map((entry) => {
      const clip = structuredClone(entry.clip);
      clip.id = crypto.randomUUID();
      clip.start = at + (entry.clip.start - anchor);
      return { trackIndex: entry.trackIndex, clip };
    });
    engine.dispatch("clips.add", { entries });
  };
  const freeze = async () => {
    const s = engine.snapshot;
    const found = s.selectedClipId ? engine.findClip(s.selectedClipId) : null;
    const source = found?.clip;
    if (!source || source.kind !== "video" || !source.mediaId) throw new Error("Select a video clip first");
    const at = s.playhead;
    if (at <= source.start + 0.1 || at >= source.start + source.duration - 0.1) throw new Error("Place the playhead inside the clip");
    const item = await api(`/api/media/${source.mediaId}/freeze`, { time: sourceTime(source, at - source.start) });
    await bin.load();
    if (!engine.findClip(source.id)) return;
    engine.dispatch("clip.freeze-insert", { clipId: source.id, time: at, mediaId: item.id, label: item.name, hold: 3 });
  };
  editorVerbs.freeze = () => void freeze().catch(error => window.alert(error instanceof Error ? error.message : String(error)));
  editorVerbs.split = () => {
    const s = engine.snapshot;
    const ids = selectedSet();
    engine.dispatch("clips.split", { clipIds: ids, time: s.playhead });
  };
  editorVerbs.duplicate = () => duplicate();
  editorVerbs.remove = () => { const ids = selectedSet(); if (ids.length > 1) engine.dispatch("clips.remove", ids); else if (ids[0]) engine.dispatch("clip.remove", ids[0]); };

  const detach = async () => {
    const found = selection(); if (!found?.clip.mediaId || found.clip.kind !== "video") return;
    const source = found.clip;
    const item = await api(`/api/media/${source.mediaId}/detach`, {});
    await bin.load();
    if (!engine.findClip(source.id)) return;
    engine.dispatch("clip.detach", { clipId: source.id, mediaId: item.id, label: item.name });
  };
  const actions: Array<[string, () => unknown, (() => string | null)?]> = [
    ["Undo", () => engine.dispatch("history.undo")], ["Redo", () => engine.dispatch("history.redo")],
    ["Copy clip", copy], ["Paste clip", paste], ["Duplicate clip", duplicate],
    ["Split at playhead", () => { const ids = selectedSet(); if (ids.length) engine.dispatch("clips.split", { clipIds: ids, time: engine.snapshot.playhead }); }],
    ["Rejoin", () => engine.dispatch("clip.rejoin", { clipIds: selectedSet() }), () => {
      const verdict = rejoinEligibility(engine.snapshot, selectedSet());
      return verdict.ok ? null : t(verdict.reason);
    }],
    ["Freeze frame", () => void freeze().catch(error => window.alert(error.message))],
    ["Detach audio", detach],
    ["Reattach audio", () => { const id = engine.snapshot.selectedClipId; if (id) engine.dispatch("clip.reattach", { clipId: id }); }, () => {
      const id = engine.snapshot.selectedClipId;
      const found = id ? engine.findClip(id) : null;
      if (!found) return t("rejoin.need-two");
      const clips = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks.flatMap((track) => track.clips);
      const paired = found.clip.detachedFrom ? clips.some((c) => c.id === found.clip.detachedFrom) : clips.some((c) => c.detachedFrom === found.clip.id);
      return paired ? null : t("reattach.no-partner");
    }],
    ["Delete clip", () => { const ids = selectedSet(); if (ids.length > 1) engine.dispatch("clips.remove", ids); else if (ids[0]) engine.dispatch("clip.remove", ids[0]); }],
  ];
  const bindMenu = (button: HTMLButtonElement, entries: Array<[string, () => unknown, (() => string | null)?]>) => {
    const menu = document.createElement("div"); menu.className = "dropdown"; menu.hidden = true;
    const probes: Array<() => void> = [];
    for (const [name, action, ready] of entries) {
      const item = document.createElement("button"); item.className = "dropdown-item"; item.textContent = name;
      item.addEventListener("click", () => { menu.hidden = true; void Promise.resolve().then(action).catch(error => window.alert(error.message)); });
      if (ready) probes.push(() => { const reason = ready(); item.disabled = !!reason; item.title = reason ?? ""; });
      menu.append(item);
    }
    document.body.append(menu);
    button.addEventListener("click", () => { const rect = button.getBoundingClientRect(); menu.style.left = `${rect.left}px`; menu.style.top = `${rect.bottom}px`; if (menu.hidden) for (const probe of probes) probe(); menu.hidden = !menu.hidden; });
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
    const underPlayhead = (): string[] => {
      const s = engine.snapshot;
      const tracks = s.timelines[s.activeTimeline].tracks;
      return tracks.filter((track) => !track.locked).flatMap((track) => track.clips.filter((c) => s.playhead > c.start && s.playhead < c.start + c.duration).map((c) => c.id));
    };
    if (modifier && key === "b") {
      event.preventDefault();
      engine.dispatch("clips.split", { clipIds: underPlayhead(), time: engine.snapshot.playhead });
      return;
    }
    if (!modifier && key === "s") {
      event.preventDefault();
      const ids = selectedSet();
      engine.dispatch("clips.split", { clipIds: ids.length ? ids : underPlayhead().slice(0, 1), time: engine.snapshot.playhead });
      return;
    }
    if (!modifier && key === "f") {
      event.preventDefault();
      void freeze().catch(error => window.alert(error instanceof Error ? error.message : String(error)));
      return;
    }
    if (!modifier && [" ", "k", "j", "l", "arrowleft", "arrowright", "home", "end"].includes(key)) {
      event.preventDefault();
      if (key === " " || key === "k") engine.dispatch("transport.toggle");
      if (key === "l") engine.play();
      if (key === "j" || key === "arrowleft") { engine.pause(); engine.dispatch("transport.step", event.shiftKey ? -10 : -1); }
      if (key === "arrowright") { engine.pause(); engine.dispatch("transport.step", event.shiftKey ? 10 : 1); }
      if (key === "home" || key === "end") engine.dispatch(`transport.${key}`);
    }
  });
  const toolbar = document.querySelector(".pane-timeline") ?? document;
  const control = (ref: string) => toolbar.querySelector<HTMLButtonElement>(`[data-ref="${ref}"]`);
  control("act-ripple")?.addEventListener("click", () => { const found = selection(); if (found) engine.dispatch("clip.ripple-delete", { clipId: found.clip.id }); });
  control("act-detach")?.addEventListener("click", () => { void detach().catch(error => window.alert(error.message)); });
  control("chip-captions")?.addEventListener("click", () => { document.querySelector<HTMLButtonElement>('[data-tab="Text"]')?.click(); document.querySelector<HTMLElement>('[data-ref="transcribe"]')?.focus(); });
  const speak = control("chip-speak");
  if (speak) { speak.disabled = false; speak.addEventListener("click", () => { document.querySelector<HTMLButtonElement>(".titlebar-right .tool-chip")?.click(); document.querySelector<HTMLButtonElement>('[data-page="speech"]')?.click(); }); }
  control("chip-detach")?.addEventListener("click", () => { void detach().catch(error => window.alert(error.message)); });
}
