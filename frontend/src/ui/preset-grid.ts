import { icon } from "./icons";
import { t } from "../i18n";

export function reconcilePresets(root: HTMLElement, entries: Array<{ id: string; name: string }>): void {
  const live = new Set(entries.map(e => e.id));
  for (const row of root.querySelectorAll<HTMLElement>("[data-preset]")) if (!live.has(row.dataset.preset!)) row.remove();
  for (const entry of entries) {
    let row = [...root.querySelectorAll<HTMLElement>("[data-preset]")].find(node => node.dataset.preset === entry.id);
    if (!row) {
      row = document.createElement("div"); row.className = "effect-card preset-card"; row.dataset.preset = entry.id;
      const thumb = document.createElement("div"); thumb.className = "effect-thumb"; thumb.dataset.fx = "plain";
      const name = document.createElement("div"); name.className = "effect-name";
      const actions = document.createElement("div"); actions.className = "preset-actions";
      const download = document.createElement("a"); download.className = "iconbtn"; download.href = `/api/presets/${entry.id}/file`; download.download = "style.fcpreset"; download.title = t("preset.export"); download.innerHTML = icon("export");
      const remove = document.createElement("button"); remove.className = "iconbtn preset-del"; remove.title = t("preset.delete"); remove.innerHTML = icon("trash");
      actions.append(download, remove); row.append(thumb, name, actions); root.append(row);
    }
    const name = row.querySelector(".effect-name")!; if (name.textContent !== entry.name) name.textContent = entry.name;
  }
}
