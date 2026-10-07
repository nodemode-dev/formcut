import type { ProjectEngine } from "../engine/project";
import { addDeviceClip, deviceLibrary } from "./device-inspector";
import { t } from "../i18n";

// The library panel's Devices tab: every device model as a picture rendered by the engine's own 3D pass, named by
// kind and style; a click adds that device at the playhead on a new top track. Before it, devices could only be added
// from a chip in the timeline toolbar, which Easy mode does not show, so many people never found them.

export function buildDevicesView(engine: ProjectEngine) {
  const el = document.createElement("div");
  el.className = "devices-view";
  el.dataset.view = "devices";
  el.hidden = true;
  el.innerHTML = `<p class="devices-hint">${t("dev.libhint")}</p><div class="devices-grid" data-devices></div>`;
  const grid = el.querySelector<HTMLElement>("[data-devices]")!;
  let built = false;
  grid.addEventListener("click", (event) => {
    const card = (event.target as HTMLElement).closest<HTMLElement>("[data-device]");
    if (card) void addDeviceClip(engine, card.dataset.device).catch((error) => window.alert((error as Error).message));
  });
  return {
    tab: "Devices",
    el,
    pause() {},
    async load() {
      if (built) return;
      built = true;
      const devices = await deviceLibrary();
      grid.innerHTML = devices
        .map((d) => {
          const kind = t(`dev.kind.${d.kind}`);
          const style = t(d.id.endsWith("minimal") ? "dev.style.minimal" : "dev.style.open");
          return `<button type="button" class="device-card" data-device="${d.id}" title="${kind} · ${style}">
            <img src="/api/devices/${d.id}/thumbnail" alt="" loading="lazy" draggable="false" />
            <span class="device-name">${kind}</span><span class="device-style">${style}</span>
          </button>`;
        })
        .join("");
    },
  };
}
