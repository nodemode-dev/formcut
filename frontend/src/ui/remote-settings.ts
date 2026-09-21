import { api } from "../engine/api";
import { t } from "../i18n";
import { escapeHtml } from "./safe-text";
import "../styles/webhooks.css";

interface Device {
  id: string;
  name: string;
  created: number;
}

interface RemoteState {
  enabled: boolean;
  port: number;
  addresses: string[];
  devices: Device[];
}

/**
 * Settings rows for phones and other computers on this network: a switch that
 * opens the engine's network listener, the address to open on the device, a
 * pairing code that counts down its five minutes, and the paired devices,
 * each removable. Only the desktop sees these rows; the engine refuses them to
 * paired devices.
 */
export function buildRemoteSettings(rows: HTMLElement): void {
  rows.insertAdjacentHTML(
    "beforeend",
    `<label class="post-toggle"><input type="checkbox" data-ref="on">${escapeHtml(t("remote.enable"))}</label>
    <div data-ref="details" hidden>
      <small class="panel-note">${escapeHtml(t("remote.open"))}</small>
      <div class="hook-url" data-ref="where"></div>
      <div class="prov-entry"><button class="tool-chip" data-ref="pair">${escapeHtml(t("remote.pair"))}</button></div>
      <div class="remote-code" data-ref="code" hidden></div>
      <small class="panel-note">${escapeHtml(t("remote.note"))}</small>
      <div class="hook-list" data-ref="devices"></div>
      <small class="panel-note" data-ref="none">${escapeHtml(t("remote.none"))}</small>
    </div>
    <small class="panel-note" data-ref="say"></small>`,
  );
  const ref = <T extends HTMLElement = HTMLElement>(name: string) => rows.querySelector<T>(`[data-ref="${name}"]`)!;
  const say = (text: string) => {
    if (ref("say").textContent !== text) ref("say").textContent = text;
  };
  const explain = (error: unknown) => (error instanceof Error ? error.message : String(error));
  let timer = 0;

  const row = (device: Device) =>
    `<div class="hook-row" data-id="${escapeHtml(device.id)}"><div class="hook-foot"><span class="hook-last">${escapeHtml(device.name)} · ${escapeHtml(new Date(device.created * 1000).toLocaleDateString())}</span><button class="tool-chip" data-remove="${escapeHtml(device.id)}">${escapeHtml(t("hooks.remove"))}</button></div></div>`;

  const draw = (state: RemoteState) => {
    ref<HTMLInputElement>("on").checked = state.enabled;
    ref("details").hidden = !state.enabled;
    const where = state.addresses.length ? state.addresses.map((address) => `http://${address}:${state.port}/pair`).join("  ") : t("remote.noAddress");
    if (ref("where").textContent !== where) ref("where").textContent = where;
    ref("devices").innerHTML = state.devices.map(row).join("");
    ref("none").hidden = state.devices.length > 0;
    if (!state.enabled) {
      window.clearInterval(timer);
      ref("code").hidden = true;
    }
  };

  ref<HTMLInputElement>("on").addEventListener("change", (event) => {
    const enabled = (event.target as HTMLInputElement).checked;
    api<RemoteState>("/api/remote", { enabled }, "PUT").then(draw, (error) => say(explain(error)));
  });
  ref("pair").addEventListener("click", () => {
    api<{ code: string; expiresIn: number }>("/api/remote/code", {}).then(
      (made) => {
        const until = Date.now() + made.expiresIn * 1000;
        const code = ref("code");
        const tick = () => {
          const left = Math.max(0, Math.round((until - Date.now()) / 1000));
          const text = left ? `${t("remote.code").replace("{code}", made.code)} · ${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}` : "";
          if (code.textContent !== text) code.textContent = text;
          code.hidden = left === 0;
          if (!left) window.clearInterval(timer);
        };
        window.clearInterval(timer);
        timer = window.setInterval(tick, 1000);
        tick();
      },
      (error) => say(explain(error)),
    );
  });
  ref("devices").addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-remove]");
    if (!button) return;
    api<RemoteState>(`/api/remote/devices/${button.dataset.remove}`, undefined, "DELETE").then(draw, (error) => say(explain(error)));
  });
  api<RemoteState>("/api/remote", undefined, "GET").then(draw, () => undefined);
}
