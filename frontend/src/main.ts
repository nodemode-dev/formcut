import { installWorkspaceLayout } from "./ui/workspace-layout";
import { installAccordions } from "./ui/accordion";
import { installEditorActions } from "./ui/editor-actions";
import "./engine/local-transport";
import { localizeElement } from "./i18n/text";
import "./styles/tokens.css";
import "./styles/creator.css";
import { installStudioTools } from "./ui/studio-tools";
import { installSettingsPopout } from "./ui/settings-popout";
import { installBehaviours } from "./ui/appearance";
import "./styles/app.css";
import "./styles/themes.css";
import "./styles/containers.css";
import "./styles/settings.css";
import "./engine/effects/blur";
import "./engine/effects/stylize";
import { ProjectEngine } from "./engine/project";
import { MediaBin } from "./engine/media";
import { newProject, saveProject } from "./engine/persistence";
import { buildTitlebar } from "./ui/titlebar";
import { buildMediaPane } from "./ui/media-pane";
import { buildPreviewPane } from "./ui/render-preview";
import { buildInspectorPane } from "./ui/inspector-pane";
import { t } from "./i18n";
import { buildTimelinePane } from "./ui/timeline-pane";
import { buildStartScreen } from "./ui/start-screen";

if ("serviceWorker" in navigator) {
  void navigator.serviceWorker.register("/sw.js").catch(() => {});
}

const engine = new ProjectEngine();
const bin = new MediaBin();

const app = document.getElementById("app")!;
const workspace = document.createElement("main");
workspace.className = "workspace";
workspace.append(
  buildMediaPane(bin, engine),
  buildPreviewPane(engine, bin),
  buildInspectorPane(engine, bin),
  buildTimelinePane(engine, bin),
);
const mobileBar = document.createElement("nav");
mobileBar.className = "mobile-bar";
mobileBar.innerHTML = `
  <button data-sheet="media">${t("mobile.media")}</button>
  <button data-sheet="inspector">${t("mobile.edit")}</button>`;
mobileBar.addEventListener("click", (ev) => {
  const btn = (ev.target as HTMLElement).closest<HTMLElement>("[data-sheet]");
  if (!btn) return;
  const pane = document.querySelector<HTMLElement>(`.pane-${btn.dataset.sheet}`);
  if (!pane) return;
  const open = pane.classList.toggle("is-mobile-open");
  for (const other of document.querySelectorAll<HTMLElement>(".pane.is-mobile-open")) {
    if (other !== pane) other.classList.remove("is-mobile-open");
  }
  for (const b of mobileBar.querySelectorAll("button")) {
    b.classList.toggle("is-on", b === btn && open);
  }
});
app.append(mobileBar);

const actions = {
  save: () => void saveProject(engine),
  newProject: () => newProject(engine),
};
const titlebar = buildTitlebar(engine, actions);
localizeElement(titlebar);
localizeElement(workspace);
app.append(titlebar, workspace);
installStudioTools(engine, bin);
installBehaviours();
const settingsButton = titlebar.querySelector<HTMLElement>('[data-ref="settings"]');
if (settingsButton) installSettingsPopout(engine, bin, settingsButton);
installEditorActions(engine, bin);
installWorkspaceLayout();
installAccordions(workspace);
app.append(buildStartScreen(engine, bin));
void bin.load();
Object.defineProperty(window, "formcut", { value: { engine, bin, actions } });
