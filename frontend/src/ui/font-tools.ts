import type { ProjectEngine } from "../engine/project";
import { api } from "../engine/api";

export function installFontTools(root: HTMLElement, engine: ProjectEngine): void {
  const section = root.querySelector<HTMLElement>('[data-ref="text-section"]'); if (!section) return;
  const tools = document.createElement("div"); tools.className = "font-tools";
  const label = document.createElement("label"); label.textContent = "Font";
  const select = document.createElement("select"); select.className = "mini-select";
  const defaultOption = document.createElement("option"); defaultOption.value = ""; defaultOption.textContent = "System default"; select.append(defaultOption); label.append(select);
  const upload = document.createElement("input"); upload.type = "file"; upload.accept = ".ttf,.otf,.ttc"; upload.setAttribute("aria-label", "Import a font");
  const status = document.createElement("span"); status.className = "creator-status"; status.setAttribute("role", "status");
  tools.append(label, upload, status); section.append(tools);
  const refresh = async () => {
    const fonts = (await api<Array<{ id: string; kind: string; name: string }>>("/api/assets")).filter(a => a.kind === "font");
    for (const font of fonts) if (![...select.options].some(o => o.value === font.id)) { const option = document.createElement("option"); option.value = font.id; option.textContent = font.name; select.append(option); }
  };
  select.addEventListener("change", () => { const clipId = engine.snapshot.selectedClipId; if (clipId) engine.dispatch("clip.text", { clipId, patch: { fontId: select.value || undefined } }); });
  upload.addEventListener("change", () => {
    const file = upload.files?.[0], clipId = engine.snapshot.selectedClipId; if (!file || !clipId) return;
    const data = new FormData(); data.append("file", file);
    void api("/api/assets/font", data).then(async font => { await refresh(); engine.dispatch("clip.text", { clipId, patch: { fontId: font.id } }); status.textContent = "Font imported"; }).catch(error => status.textContent = error.message);
  });
  engine.subscribe((_state, changed) => { if (changed === "clips" || changed === "clip-selection") { const clip = engine.snapshot.selectedClipId ? engine.findClip(engine.snapshot.selectedClipId)?.clip : null; if (document.activeElement !== select) select.value = clip?.textStyle?.fontId ?? ""; } });
  void refresh().catch(error => status.textContent = error.message);
}
