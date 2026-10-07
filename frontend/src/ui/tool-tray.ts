import type { ProjectEngine } from "../engine/project";
import { t } from "../i18n";
import { editorVerbs } from "./editor-actions";

type Ready = string | null;

interface Tool {
  id: string;
  label: string;
  run: () => void;
  ready?: () => Ready;
}

/** Click an existing control so the tray takes the same path a user would. */
function press(...selectors: string[]): boolean {
  for (const selector of selectors) {
    const node = document.querySelector<HTMLElement>(selector);
    if (node) { node.click(); return true; }
  }
  return false;
}

function openCreatorPage(page: string): void {
  const select = document.querySelector<HTMLSelectElement>(".creator-panel select[data-page], select[data-page]");
  if (!select) return;
  select.value = page;
  select.dispatchEvent(new Event("change", { bubbles: true }));
}

export function buildToolTray(engine: ProjectEngine): HTMLElement {
  const tray = document.createElement("div");
  tray.className = "tool-tray";
  tray.dataset.feature = "easy.tray";
  tray.setAttribute("role", "toolbar");
  tray.setAttribute("aria-label", "Tools");

  const selectionKind = (): "none" | "visual" | "text" | "audio" => {
    const s = engine.snapshot;
    const found = s.selectedClipId ? engine.findClip(s.selectedClipId) : null;
    if (!found) return "none";
    if (found.clip.kind === "text") return "text";
    if (found.clip.kind === "audio") return "audio";
    return "visual";
  };

  const insidePlayhead = (): Ready => {
    const s = engine.snapshot;
    const found = s.selectedClipId ? engine.findClip(s.selectedClipId) : null;
    if (!found) return t("tray.select");
    const c = found.clip;
    return s.playhead > c.start + 0.1 && s.playhead < c.start + c.duration - 0.1 ? null : t("tray.playhead");
  };
  const unlocked = (): Ready => {
    const s = engine.snapshot;
    const found = s.selectedClipId ? engine.findClip(s.selectedClipId) : null;
    if (!found) return t("tray.select");
    return s.timelines[s.activeTimeline].tracks[found.trackIndex].locked ? t("tray.locked") : null;
  };
  const videoOnly = (): Ready => {
    const s = engine.snapshot;
    const found = s.selectedClipId ? engine.findClip(s.selectedClipId) : null;
    if (!found) return t("tray.select");
    return found.clip.kind === "video" ? null : t("tray.video-only");
  };
  const anchored = (...selectors: string[]) => (): Ready =>
    selectors.some((selector) => document.querySelector(selector)) ? null : t("tray.missing");

  const TOOLS: Record<ReturnType<typeof selectionKind>, Tool[]> = {
    none: [
      { id: "add", label: "tray.addmedia", run: () => { press('.pane-tab[data-tab="Media"]'); press('[data-ref="file"]'); }, ready: anchored('[data-ref="file"]') },
      { id: "text", label: "tray.text", run: () => press('.pane-tab[data-tab="Text"]'), ready: anchored('.pane-tab[data-tab="Text"]') },
      { id: "devices", label: "tab.devices", run: () => press('.pane-tab[data-tab="Devices"]'), ready: anchored('.pane-tab[data-tab="Devices"]') },
      { id: "focus", label: "focus.title", run: () => press('[data-ref="chip-focus"]'), ready: anchored('[data-ref="chip-focus"]') },
      { id: "captions", label: "tray.captions", run: () => press('[data-feature="chip.captions"]'), ready: anchored('[data-feature="chip.captions"]') },
      { id: "voice", label: "tray.voice", run: () => press('[data-feature="chip.speak"]', '[data-feature="titlebar.studio"]'), ready: anchored('[data-feature="chip.speak"]', '[data-feature="titlebar.studio"]') },
      { id: "stock", label: "tray.stock", run: () => press('.pane-media [data-ref="stock"]', '[data-feature="titlebar.studio"]'), ready: anchored('.pane-media [data-ref="stock"]', '[data-feature="titlebar.studio"]') },
    ],
    visual: [
      { id: "split", label: "tray.split", run: () => editorVerbs.split(), ready: () => unlocked() ?? insidePlayhead() },
      { id: "delete", label: "tray.delete", run: () => editorVerbs.remove(), ready: unlocked },
      { id: "duplicate", label: "tray.duplicate", run: () => editorVerbs.duplicate(), ready: unlocked },
      { id: "speed", label: "tray.speed", run: () => openCreatorPage("speed"), ready: videoOnly },
      { id: "volume", label: "tray.volume", run: () => openCreatorPage("audio"), ready: videoOnly },
      { id: "animate", label: "tray.animate", run: () => openCreatorPage("motion") },
      { id: "adjust", label: "tray.adjust", run: () => openCreatorPage("effects") },
      { id: "filters", label: "tray.filters", run: () => press('.pane-tab[data-tab="Filters"]'), ready: anchored('.pane-tab[data-tab="Filters"]') },
      { id: "removebg", label: "tray.removebg", run: () => openCreatorPage("cutout") },
      { id: "crop", label: "tray.crop", run: () => press('[data-ref="crop-mode"]'), ready: anchored('[data-ref="crop-mode"]') },
      { id: "freeze", label: "tray.freeze", run: () => editorVerbs.freeze(), ready: () => videoOnly() ?? unlocked() ?? insidePlayhead() },
      { id: "reverse", label: "tray.reverse", run: () => press('[data-ref="reverse"]'), ready: () => videoOnly() ?? (anchored('[data-ref="reverse"]'))() },
    ],
    text: [
      { id: "edittext", label: "tray.edittext", run: () => { press('[data-section="text"] .section-head'); document.querySelector<HTMLElement>('[data-ref="text-content"], [data-section="text"] textarea, [data-section="text"] input')?.focus(); } },
      { id: "style", label: "tray.style", run: () => press('[data-section="text"] .section-head') },
      { id: "animate", label: "tray.animate", run: () => openCreatorPage("motion") },
      { id: "duplicate", label: "tray.duplicate", run: () => editorVerbs.duplicate(), ready: unlocked },
      { id: "delete", label: "tray.delete", run: () => editorVerbs.remove(), ready: unlocked },
    ],
    audio: [
      { id: "split", label: "tray.split", run: () => editorVerbs.split(), ready: () => unlocked() ?? insidePlayhead() },
      { id: "volume", label: "tray.volume", run: () => openCreatorPage("audio") },
      { id: "fade", label: "tray.fade", run: () => openCreatorPage("audio") },
      { id: "voicefx", label: "tray.voicefx", run: () => openCreatorPage("audio") },
      { id: "denoise", label: "tray.denoise", run: () => openCreatorPage("audio") },
      { id: "delete", label: "tray.delete", run: () => editorVerbs.remove(), ready: unlocked },
    ],
  };

  let painted = "";
  let paintedKind = "";
  const paint = () => {
    const kind = selectionKind();
    const tools = TOOLS[kind];
    const reasons = tools.map((tool) => (tool.ready ? tool.ready() : null));
    const stamp = kind + ":" + tools.map((tool, index) => `${tool.id}=${reasons[index] ?? ""}`).join("|");
    if (stamp === painted) return;
    painted = stamp;
    const state = (button: HTMLButtonElement, tool: Tool, reason: Ready) => {
      const title = reason ?? t(tool.label);
      if (button.title !== title) button.title = title;
      if (reason) {
        if (button.getAttribute("aria-disabled") !== "true") button.setAttribute("aria-disabled", "true");
      } else if (button.hasAttribute("aria-disabled")) {
        button.removeAttribute("aria-disabled");
      }
    };
    if (kind === paintedKind && tray.children.length === tools.length) {
      tools.forEach((tool, index) => state(tray.children[index] as HTMLButtonElement, tool, reasons[index]));
      return;
    }
    paintedKind = kind;
    tray.replaceChildren(...tools.map((tool, index) => {
      const button = document.createElement("button");
      button.className = "tray-tool";
      button.dataset.tool = tool.id;
      button.textContent = t(tool.label);
      state(button, tool, reasons[index]);
      button.addEventListener("click", () => { if (!button.getAttribute("aria-disabled")) tool.run(); });
      return button;
    }));
  };

  engine.subscribe((_state, event) => {
    if (["clips", "timeline", "clip-selection", "playhead", "project"].includes(event)) paint();
  });
  paint();
  return tray;
}
