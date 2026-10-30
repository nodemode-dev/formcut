import { installWorkspaceLayout } from "./ui/workspace-layout";
import { loadExtraLocales, applyDirection } from "./i18n";
import { LiveMixer } from "./engine/live-mix";
import { primeInterfaceMode, applyInterfaceProfile, observeInterfaceFeatures, activeProfile } from "./ui/interface-mode";
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
import "./styles/focus.css";
import "./styles/device.css";
import "./styles/settings.css";
import { ProjectEngine } from "./engine/project";
import { MediaBin } from "./engine/media";
import { newProject, saveProject } from "./engine/persistence";
import { buildTitlebar } from "./ui/titlebar";
import { buildMediaPane } from "./ui/media-pane";
import { buildPreviewPane } from "./ui/render-preview";
import { buildInspectorPane } from "./ui/inspector-pane";
import { t } from "./i18n";
import { buildTimelinePane } from "./ui/timeline-pane";
import { buildToolTray } from "./ui/tool-tray";
import { buildStartScreen } from "./ui/start-screen";

if ("serviceWorker" in navigator) {
  void navigator.serviceWorker.register("/sw.js").catch(() => {});
}

const engine = new ProjectEngine();
const bin = new MediaBin();
document.addEventListener("formcut:media-changed", () => void bin.load());

const app = document.getElementById("app")!;
const workspace = document.createElement("main");
workspace.className = "workspace";
const timelinePane = buildTimelinePane(engine, bin);
timelinePane.prepend(buildToolTray(engine));
workspace.append(
  buildMediaPane(bin, engine),
  buildPreviewPane(engine, bin),
  buildInspectorPane(engine, bin),
  timelinePane,
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

applyDirection();
const liveMix = new LiveMixer();
const actions = {
  save: () => void saveProject(engine),
  newProject: () => newProject(engine, undefined, activeProfile().behaviour.magneticMain),
};
const titlebar = buildTitlebar(engine, actions);
localizeElement(titlebar);
localizeElement(workspace);
const modeProfile = primeInterfaceMode();
applyInterfaceProfile(titlebar, modeProfile);
applyInterfaceProfile(workspace, modeProfile);
app.append(titlebar, workspace);
observeInterfaceFeatures(app);
installStudioTools(engine, bin);
installBehaviours();
const settingsButton = titlebar.querySelector<HTMLElement>('[data-ref="settings"]');
if (settingsButton) installSettingsPopout(engine, bin, settingsButton);
installEditorActions(engine, bin);
installWorkspaceLayout();
installAccordions(workspace);
workspace.querySelector(".pane-inspector")?.dispatchEvent(new Event("formcut:fit-tabs"));
app.append(buildStartScreen(engine, bin));
localizeElement(document.body);
// Arabic, Persian, Hebrew and Croatian ship as locale files, loaded here: until
// this call they never loaded at all. A saved choice among them takes effect,
// right to left included, as its file arrives (loadExtraLocales).
void loadExtraLocales().then(() => document.dispatchEvent(new CustomEvent("formcut:locales")));
void bin.load();
Object.defineProperty(window, "formcut", { value: { engine, bin, actions, liveMix, loadExtraLocales } });
