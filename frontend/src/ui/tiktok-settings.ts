import { api } from "../engine/api";
import { t } from "../i18n";
import { escapeHtml } from "./safe-text";
import { connectTikTok, type TikTokState } from "./tiktok-dialog";

const REDIRECT = "http://127.0.0.1:*/api/connect/tiktok/callback/";

type SettingsState = TikTokState & { clientKey?: string; relay?: string };

/**
 * Settings rows for TikTok: the client key, then either the client secret of a
 * person's own TikTok app or the address of a token relay the app's owner
 * hosts, the redirect to register in the TikTok app, and connect and
 * disconnect. A blank secret field keeps the stored secret; the engine never
 * sends it back.
 */
export function buildTikTokSettings(rows: HTMLElement): void {
  const line = document.createElement("div");
  line.className = "prov-state";
  line.innerHTML = `<span class="prov-badge" data-state="none">${escapeHtml(t("tiktok.notSet"))}</span><small class="panel-note"></small>`;
  const badge = line.querySelector<HTMLElement>(".prov-badge")!;
  const hint = line.querySelector<HTMLElement>("small")!;
  const fields = document.createElement("div");
  fields.className = "tiktok-fields";
  fields.innerHTML = `
    <input type="text" data-ref="key" autocomplete="off" spellcheck="false" placeholder="${escapeHtml(t("tiktok.clientKey"))}">
    <input type="password" data-ref="secret" autocomplete="off" placeholder="${escapeHtml(t("tiktok.clientSecret"))}">
    <input type="url" data-ref="relay" autocomplete="off" spellcheck="false" placeholder="${escapeHtml(t("tiktok.relay"))}">`;
  const entry = document.createElement("div");
  entry.className = "prov-entry";
  entry.innerHTML = `<button class="tool-chip" data-act="save">${escapeHtml(t("tiktok.save"))}</button><button class="tool-chip" data-act="connect">${escapeHtml(t("tiktok.connect"))}</button><button class="tool-chip" data-act="disconnect">${escapeHtml(t("tiktok.disconnect"))}</button>`;
  const redirect = document.createElement("small");
  redirect.className = "panel-note";
  redirect.innerHTML = `${escapeHtml(t("tiktok.redirect"))} <span class="tiktok-redirect">${REDIRECT}</span>`;
  rows.append(line, fields, entry, redirect);

  const input = (name: string) => fields.querySelector<HTMLInputElement>(`[data-ref="${name}"]`)!;
  const button = (act: string) => entry.querySelector<HTMLButtonElement>(`[data-act="${act}"]`)!;
  const say = (text: string) => {
    if (hint.textContent !== text) hint.textContent = text;
  };
  const draw = (state: SettingsState) => {
    const key = state.connected ? "tiktok.connected" : state.configured ? "tiktok.ready" : "tiktok.notSet";
    if (badge.textContent !== t(key)) badge.textContent = t(key);
    badge.dataset.state = state.connected ? "good" : state.configured ? "set" : "none";
    button("connect").disabled = !state.configured || state.connected;
    button("disconnect").disabled = !state.connected;
  };
  const explain = (error: unknown) => (error instanceof Error ? error.message : String(error));

  button("save").addEventListener("click", () => {
    const secret = input("secret").value.trim();
    const body = { clientKey: input("key").value.trim(), relay: input("relay").value.trim(), ...(secret ? { clientSecret: secret } : {}) };
    api<SettingsState>("/api/connect/tiktok/app", body, "PUT").then(
      (state) => {
        input("secret").value = "";
        say("");
        draw(state);
      },
      (error) => say(explain(error)),
    );
  });
  button("connect").addEventListener("click", () => {
    button("connect").disabled = true;
    connectTikTok((url) => say(`${t("tiktok.waiting")} ${url}`), () => !rows.isConnected).then(
      (state) => {
        say("");
        if (state) draw(state);
        else button("connect").disabled = false;
      },
      (error) => {
        say(explain(error));
        button("connect").disabled = false;
      },
    );
  });
  button("disconnect").addEventListener("click", () => {
    api<SettingsState>("/api/connect/tiktok", undefined, "DELETE").then(draw, (error) => say(explain(error)));
  });

  api<SettingsState>("/api/connect/tiktok", undefined, "GET").then(
    (state) => {
      input("key").value = state.clientKey ?? "";
      input("relay").value = state.relay ?? "";
      draw(state);
    },
    () => undefined, // the engine is unreachable; the rows keep their empty state
  );
}
