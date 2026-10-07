import type { ProjectEngine } from "../engine/project";
import { api } from "../engine/api";
import { addDeviceClip, deviceLibrary } from "./device-inspector";
import { t } from "../i18n";

// The library panel's Browser tab: the browser window's movement presets (the window itself moves before a still
// camera, as in Promocut's and UltraMock's browser templates), each a picture rendered by the engine mid-move. A click
// adds a browser window at the playhead for the preset's length with its movement and finish.

const DEVICE = "browser-window";
const SECONDS = 4;
const GENERIC = new Set(["hero", "push"]);

export function buildBrowserView(engine: ProjectEngine) {
  const el = document.createElement("div");
  el.className = "devices-view";
  el.dataset.view = "browser";
  el.hidden = true;
  el.innerHTML = `<p class="devices-hint">${t("dev.browserhint")}</p><div class="devices-grid" data-browser></div>`;
  const grid = el.querySelector<HTMLElement>("[data-browser]")!;
  let built = false;
  grid.addEventListener("click", (event) => {
    const card = (event.target as HTMLElement).closest<HTMLElement>("[data-preset]");
    if (!card) return;
    const preset = card.dataset.preset!;
    void (async () => {
      const clipId = await addDeviceClip(engine, DEVICE, SECONDS);
      if (!clipId) return;
      const made = await api<{ keyframes: unknown[]; finish?: string }>("/api/devices/template", { device: DEVICE, template: preset, duration: SECONDS });
      engine.dispatch("clip.keyframes.replace", { clipId, keyframes: made.keyframes });
      if (made.finish) engine.dispatch("clip.device", { clipId, patch: { finish: made.finish } });
    })().catch((error) => window.alert((error as Error).message));
  });
  return {
    tab: "Browser",
    el,
    pause() {},
    async load() {
      if (built) return;
      built = true;
      const browser = (await deviceLibrary()).find((d) => d.id === DEVICE);
      const presets = (browser?.templates ?? []).filter((name) => !GENERIC.has(name));
      grid.innerHTML = presets
        .map((name) => `<button type="button" class="device-card" data-preset="${name}" title="${t(`dev.tpl.${name}`)}">
            <img src="/api/devices/${DEVICE}/templates/${name}/thumbnail" alt="" loading="lazy" draggable="false" />
            <span class="device-name">${t(`dev.tpl.${name}`)}</span><span class="device-style">${SECONDS}s</span>
          </button>`)
        .join("");
    },
  };
}
