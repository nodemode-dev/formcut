import { api } from "../engine/api";
import { t } from "../i18n";
import { icon } from "./icons";
import { escapeHtml } from "./safe-text";
import { openSettings } from "./settings-link";
import type { PostTarget } from "./tiktok-dialog";
import "../styles/tiktok.css";

interface InstagramState {
  connected: boolean;
  userId: string | null;
  username: string | null;
}

interface JobState {
  status: string;
  error?: string;
}

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
const explain = (error: unknown) => (error instanceof Error ? error.message : String(error));
// The engine refuses video Instagram cannot take before sending anything; that refusal is shown translated.
const friendly = (error: unknown) => (explain(error).includes("H.264") ? t("instagram.codec") : explain(error));

/** The Reel post dialog for one export or bin video. */
export function openInstagram(target: PostTarget): void {
  const dialog = document.createElement("dialog");
  dialog.className = "post-dialog";
  dialog.innerHTML = `
    <div class="post-head">
      <h3>${escapeHtml(t("instagram.title"))}</h3>
      <button type="button" class="post-x" data-ref="x" aria-label="${escapeHtml(t("btn.close"))}">${icon("close")}</button>
    </div>
    <p class="post-source">${escapeHtml(target.name)}</p>
    <div class="post-body" data-ref="form" hidden>
      <p class="post-as" data-ref="as"></p>
      <label class="post-label" for="ig-caption">${escapeHtml(t("tiktok.caption"))}</label>
      <textarea id="ig-caption" class="post-caption" data-ref="caption" maxlength="2200" rows="3"></textarea>
      <label class="post-toggle"><input type="checkbox" data-ref="feed" checked>${escapeHtml(t("instagram.feed"))}</label>
    </div>
    <p class="post-note" data-ref="note" aria-live="polite"></p>
    <div class="post-foot">
      <button type="button" class="post-button" data-ref="cancel">${escapeHtml(t("btn.close"))}</button>
      <button type="button" class="post-button is-primary" data-ref="settings" hidden>${escapeHtml(t("set.title"))}</button>
      <button type="button" class="post-button is-primary" data-ref="go" hidden></button>
    </div>`;
  const ref = <T extends HTMLElement = HTMLElement>(name: string) => dialog.querySelector<T>(`[data-ref="${name}"]`)!;
  ref("settings").addEventListener("click", () => {
    dialog.close();
    openSettings("providers", "Instagram");
  });
  const setText = (el: HTMLElement, text: string) => {
    if (el.textContent !== text) el.textContent = text;
  };
  const show = (el: HTMLElement, visible: boolean) => {
    if (el.hidden === visible) el.hidden = !visible;
  };
  let phase: "loading" | "setup" | "form" | "sending" | "done" = "loading";

  const refresh = () => {
    show(ref("form"), phase === "form" || phase === "sending" || phase === "done");
    const go = ref<HTMLButtonElement>("go");
    setText(go, phase === "done" ? t("btn.close") : t("tiktok.send"));
    show(go, phase === "form" || phase === "sending" || phase === "done");
    show(ref("settings"), phase === "setup");
    show(ref("cancel"), phase !== "done");
    go.disabled = phase === "sending";
    ref<HTMLTextAreaElement>("caption").disabled = phase !== "form";
    ref<HTMLInputElement>("feed").disabled = phase !== "form";
  };

  const send = async () => {
    phase = "sending";
    setText(ref("note"), t("instagram.sending"));
    refresh();
    const source = "jobId" in target ? { jobId: target.jobId } : { mediaId: target.mediaId };
    const body = { ...source, caption: ref<HTMLTextAreaElement>("caption").value, shareToFeed: ref<HTMLInputElement>("feed").checked };
    try {
      const job = await api<{ job_id: string }>("/api/publish/instagram", body);
      for (;;) {
        const state = await api<JobState>(`/api/jobs/${job.job_id}`, undefined, "GET");
        if (state.status === "done") {
          phase = "done";
          setText(ref("note"), t("instagram.posted"));
          break;
        }
        if (state.status === "error" || state.status === "cancelled") {
          phase = "form";
          setText(ref("note"), state.error ?? "");
          break;
        }
        await wait(800);
      }
    } catch (error) {
      phase = "form";
      setText(ref("note"), friendly(error));
    }
    refresh();
  };

  ref("go").addEventListener("click", () => {
    if (phase === "form") void send();
    else if (phase === "done") dialog.close();
  });
  ref("cancel").addEventListener("click", () => dialog.close());
  ref("x").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => dialog.remove());

  refresh();
  document.body.append(dialog);
  dialog.showModal();
  api<InstagramState>("/api/connect/instagram", undefined, "GET").then(
    (state) => {
      if (state.connected) {
        phase = "form";
        setText(ref("as"), t("instagram.as").replace("{name}", state.username ?? ""));
      } else {
        phase = "setup";
        setText(ref("note"), t("instagram.setup"));
      }
      refresh();
    },
    (error) => {
      phase = "setup";
      setText(ref("note"), explain(error));
      refresh();
    },
  );
}

/**
 * Settings rows for Instagram: paste an access token from the owner's Meta app
 * and connect; the engine finds the Instagram professional account behind it
 * and never sends the token back.
 */
export function buildInstagramSettings(rows: HTMLElement): void {
  const line = document.createElement("div");
  line.className = "prov-state";
  line.innerHTML = `<span class="prov-badge" data-state="none">${escapeHtml(t("tiktok.notSet"))}</span><small class="panel-note"></small>`;
  const badge = line.querySelector<HTMLElement>(".prov-badge")!;
  const note = line.querySelector<HTMLElement>("small")!;
  const fields = document.createElement("div");
  fields.className = "tiktok-fields";
  fields.innerHTML = `<input type="password" autocomplete="off" placeholder="${escapeHtml(t("instagram.token"))}">`;
  const entry = document.createElement("div");
  entry.className = "prov-entry";
  entry.innerHTML = `<button class="tool-chip" data-act="connect">${escapeHtml(t("instagram.connect"))}</button><button class="tool-chip" data-act="disconnect">${escapeHtml(t("tiktok.disconnect"))}</button>`;
  const hint = document.createElement("small");
  hint.className = "panel-note";
  hint.textContent = t("instagram.hint");
  rows.append(line, fields, entry, hint);
  const input = fields.querySelector("input")!;
  const button = (act: string) => entry.querySelector<HTMLButtonElement>(`[data-act="${act}"]`)!;
  const say = (text: string) => {
    if (note.textContent !== text) note.textContent = text;
  };
  const draw = (state: InstagramState) => {
    const label = state.connected ? t("tiktok.connected") : t("tiktok.notSet");
    if (badge.textContent !== label) badge.textContent = label;
    badge.dataset.state = state.connected ? "good" : "none";
    say(state.connected && state.username ? `@${state.username}` : "");
    button("disconnect").disabled = !state.connected;
  };

  button("connect").addEventListener("click", () => {
    const token = input.value.trim();
    if (!token) return;
    button("connect").disabled = true;
    api<InstagramState>("/api/connect/instagram", { token }, "PUT").then(
      (state) => {
        input.value = "";
        button("connect").disabled = false;
        draw(state);
      },
      (error) => {
        button("connect").disabled = false;
        say(explain(error));
      },
    );
  });
  button("disconnect").addEventListener("click", () => {
    api<InstagramState>("/api/connect/instagram", undefined, "DELETE").then(draw, (error) => say(explain(error)));
  });
  api<InstagramState>("/api/connect/instagram", undefined, "GET").then(draw, () => undefined);
}
