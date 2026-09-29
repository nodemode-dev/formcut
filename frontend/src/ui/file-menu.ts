import { t } from "../i18n";

export function fileMenu(menu: HTMLElement, projects: Array<{ id: string; title: string }>): void {
  if (!menu.dataset.initialized) {
    menu.dataset.initialized = "true";
    // Open project file and Save as: a project kept in a .fmc file anywhere on disk (project_files.py)
    for (const [action, label] of [["new", "file.new"], ["open-file", "file.openFile"], ["save", "file.save"], ["save-as", "file.saveAs"], ["collect", "file.collect"]]) { const item = document.createElement("button"); item.className = "dropdown-item"; item.dataset.act = action; item.textContent = t(label); menu.append(item); }
    const title = document.createElement("div"); title.className = "dropdown-label"; title.textContent = t("start.recent"); menu.append(title);
  }
  const ids = new Set(projects.map(p => p.id));
  for (const item of menu.querySelectorAll<HTMLElement>("[data-open]")) if (!ids.has(item.dataset.open!)) item.remove();
  for (const project of projects) {
    let item = [...menu.querySelectorAll<HTMLButtonElement>("[data-open]")].find(i => i.dataset.open === project.id);
    if (!item) { item = document.createElement("button"); item.className = "dropdown-item"; item.dataset.open = project.id; menu.append(item); }
    if (item.textContent !== project.title) item.textContent = project.title;
  }
}
