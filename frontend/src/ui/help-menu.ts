// Help in the titlebar: the three demo films, each opened as a new unsaved project. The desktop
// app's native Help menu calls the same window.formcut.actions.openDemo.
import { REPO_DEMOS } from "../demos";
import { t } from "../i18n";

export function installHelpMenu(openDemo: (id: string) => Promise<void>): void {
  const button = document.querySelector<HTMLButtonElement>('.titlebar-left .menu-item[data-ref="help"]');
  if (!button) return;
  const menu = document.createElement("div");
  menu.className = "dropdown";
  menu.dataset.ref = "help-menu";
  menu.hidden = true;
  menu.innerHTML = `<div class="dropdown-label">${t("demos.title")}</div>` +
    REPO_DEMOS.map((demo) => `<button class="dropdown-item" data-demo="${demo.id}">${demo.title}</button>`).join("");
  document.body.append(menu);
  const shut = () => { if (!menu.hidden) menu.hidden = true; };
  button.addEventListener("click", () => {
    const rect = button.getBoundingClientRect();
    menu.style.left = `${rect.left}px`;
    menu.style.top = `${rect.bottom}px`;
    menu.hidden = !menu.hidden;
  });
  document.addEventListener("pointerdown", (event) => { if (!menu.contains(event.target as Node) && !button.contains(event.target as Node)) shut(); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") shut(); });
  menu.addEventListener("click", (event) => {
    const hit = (event.target as HTMLElement).closest<HTMLElement>("[data-demo]");
    if (!hit) return;
    shut();
    void openDemo(hit.dataset.demo!);
  });
}
