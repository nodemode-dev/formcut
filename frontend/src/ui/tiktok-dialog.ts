import { api } from "../engine/api";
import { t } from "../i18n";
import { icon } from "./icons";
import { escapeHtml } from "./safe-text";
import { openSettings } from "./settings-link";
import "../styles/tiktok.css";

export interface TikTokState {
  configured: boolean;
  connected: boolean;
  mode: string | null;
  account: { openId: string } | null;
}

interface Creator {
  creator_nickname?: string;
  creator_username?: string;
  privacy_level_options?: string[];
  comment_disabled?: boolean;
  duet_disabled?: boolean;
  stitch_disabled?: boolean;
}

interface JobState {
  status: string;
  error?: string;
  result?: { status?: string };
}

export type PostTarget = { jobId: string; name: string } | { mediaId: string; name: string };

const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
const explain = (error: unknown) => (error instanceof Error ? error.message : String(error));

/**
 * Start TikTok's sign-in in the system browser, which the engine opens, and wait
 * until the engine reports the account connected. The address is handed to
 * `showLink` in case no browser could be opened. Gives up after ten minutes.
 */
export async function connectTikTok(showLink: (url: string) => void, stopped: () => boolean): Promise<TikTokState | null> {
  const started = await api<{ url: string; opened: boolean }>("/api/connect/tiktok/start", { open: true });
  showLink(started.url);
  const deadline = Date.now() + 600_000;
  while (Date.now() < deadline && !stopped()) {
    await wait(1500);
    const state = await api<TikTokState>("/api/connect/tiktok", undefined, "GET");
    if (state.connected) return state;
  }
  return null;
}

/** The post dialog for one export or bin video. */
export function openTikTok(target: PostTarget): void {
  const dialog = document.createElement("dialog");
  dialog.className = "post-dialog";
  dialog.innerHTML = `
    <div class="post-head">
      <h3>${escapeHtml(t("tiktok.title"))}</h3>
      <button type="button" class="post-x" data-ref="x" aria-label="${escapeHtml(t("btn.close"))}">${icon("close")}</button>
    </div>
    <p class="post-source">${escapeHtml(target.name)}</p>
    <div class="post-body" data-ref="form" hidden>
      <p class="post-as" data-ref="as"></p>
      <div class="post-group" role="radiogroup" data-ref="modes">
        <button type="button" class="post-choice" role="radio" data-mode="draft">${escapeHtml(t("tiktok.draft"))}</button>
        <button type="button" class="post-choice" role="radio" data-mode="direct">${escapeHtml(t("tiktok.direct"))}</button>
      </div>
      <p class="post-hint" data-ref="modeNote"></p>
      <div data-ref="direct" hidden>
        <label class="post-label" for="post-caption">${escapeHtml(t("tiktok.caption"))}</label>
        <textarea id="post-caption" class="post-caption" data-ref="caption" maxlength="2200" rows="3"></textarea>
        <span class="post-label">${escapeHtml(t("tiktok.who"))}</span>
        <div class="post-group" role="radiogroup" data-ref="privacy"></div>
        <label class="post-toggle"><input type="checkbox" data-ref="comments" checked>${escapeHtml(t("tiktok.comments"))}</label>
        <label class="post-toggle"><input type="checkbox" data-ref="duet" checked>${escapeHtml(t("tiktok.duet"))}</label>
        <label class="post-toggle"><input type="checkbox" data-ref="stitch" checked>${escapeHtml(t("tiktok.stitch"))}</label>
        <p class="post-hint">${escapeHtml(t("tiktok.music"))}</p>
      </div>
    </div>
    <p class="post-note" data-ref="note" aria-live="polite"></p>
    <a class="post-link" data-ref="link" target="_blank" rel="noopener" hidden></a>
    <div class="post-foot">
      <button type="button" class="post-button" data-ref="cancel">${escapeHtml(t("btn.close"))}</button>
      <button type="button" class="post-button is-primary" data-ref="settings" hidden>${escapeHtml(t("set.title"))}</button>
      <button type="button" class="post-button is-primary" data-ref="go" disabled></button>
    </div>`;
  const ref = <T extends HTMLElement = HTMLElement>(name: string) => dialog.querySelector<T>(`[data-ref="${name}"]`)!;
  const setText = (el: HTMLElement, text: string) => {
    if (el.textContent !== text) el.textContent = text;
  };
  const show = (el: HTMLElement, visible: boolean) => {
    if (el.hidden === visible) el.hidden = !visible;
  };
  const note = (text: string) => setText(ref("note"), text);

  let phase: "loading" | "setup" | "connect" | "waiting" | "form" | "sending" | "done" = "loading";
  let mode: "draft" | "direct" = "draft";
  let privacy: string | null = null;
  let creator: Creator | null = null;
  let closed = false;

  const refresh = () => {
    show(ref("form"), phase === "form" || phase === "sending" || phase === "done");
    for (const button of ref("modes").querySelectorAll<HTMLButtonElement>("[data-mode]")) {
      button.setAttribute("aria-checked", String(button.dataset.mode === mode));
      button.disabled = phase !== "form";
    }
    show(ref("direct"), mode === "direct" && creator !== null);
    setText(ref("modeNote"), mode === "draft" ? t("tiktok.draftNote") : t("tiktok.directNote"));
    for (const button of ref("privacy").querySelectorAll<HTMLButtonElement>("[data-privacy]")) {
      button.setAttribute("aria-checked", String(button.dataset.privacy === privacy));
      button.disabled = phase !== "form";
    }
    const go = ref<HTMLButtonElement>("go");
    const labels = { loading: "", setup: "", connect: t("tiktok.connect"), waiting: t("tiktok.connect"), form: t("tiktok.send"), sending: t("tiktok.send"), done: t("btn.close") };
    setText(go, labels[phase]);
    show(go, phase !== "loading" && phase !== "setup");
    show(ref("settings"), phase === "setup");
    show(ref("cancel"), phase !== "done");
    go.disabled = phase === "waiting" || phase === "sending" || (phase === "form" && mode === "direct" && (!creator || !privacy));
  };
  ref("settings").addEventListener("click", () => {
    dialog.close();
    openSettings("providers", "TikTok");
  });

  const loadCreator = async () => {
    try {
      creator = await api<Creator>("/api/publish/tiktok/creator", undefined, "GET");
    } catch (error) {
      note(explain(error));
      return;
    }
    const name = creator.creator_nickname || creator.creator_username || "";
    setText(ref("as"), name ? t("tiktok.as").replace("{name}", name) : "");
    ref("privacy").innerHTML = (creator.privacy_level_options ?? [])
      .map((level) => `<button type="button" class="post-choice" role="radio" data-privacy="${escapeHtml(level)}">${escapeHtml(t(`tiktok.privacy.${level}`))}</button>`)
      .join("");
    for (const [refName, off] of [["comments", creator.comment_disabled], ["duet", creator.duet_disabled], ["stitch", creator.stitch_disabled]] as const) {
      const box = ref<HTMLInputElement>(refName);
      box.disabled = Boolean(off);
      if (off) box.checked = false;
    }
    refresh();
  };

  const enterForm = async () => {
    phase = "form";
    note("");
    refresh();
    if (mode === "direct" && !creator) await loadCreator();
  };

  const send = async () => {
    phase = "sending";
    note(t("tiktok.sending"));
    refresh();
    const body: Record<string, unknown> = { ...("jobId" in target ? { jobId: target.jobId } : { mediaId: target.mediaId }), mode };
    if (mode === "direct") {
      body.title = ref<HTMLTextAreaElement>("caption").value;
      body.privacyLevel = privacy;
      body.disableComment = !ref<HTMLInputElement>("comments").checked;
      body.disableDuet = !ref<HTMLInputElement>("duet").checked;
      body.disableStitch = !ref<HTMLInputElement>("stitch").checked;
    }
    try {
      const job = await api<{ job_id: string }>("/api/publish/tiktok", body);
      for (;;) {
        const state = await api<JobState>(`/api/jobs/${job.job_id}`, undefined, "GET");
        if (state.status === "done") {
          phase = "done";
          note(state.result?.status === "SEND_TO_USER_INBOX" ? t("tiktok.inbox") : t("tiktok.posted"));
          break;
        }
        if (state.status === "error" || state.status === "cancelled") {
          phase = "form";
          note(state.error ?? "");
          break;
        }
        await wait(800);
      }
    } catch (error) {
      phase = "form";
      note(explain(error));
    }
    refresh();
  };

  const connect = async () => {
    phase = "waiting";
    refresh();
    try {
      const state = await connectTikTok((url) => {
        note(t("tiktok.waiting"));
        const link = ref<HTMLAnchorElement>("link");
        link.href = url;
        setText(link, url);
        show(link, true);
      }, () => closed);
      show(ref("link"), false);
      if (state) await enterForm();
      else if (!closed) {
        phase = "connect";
        refresh();
      }
    } catch (error) {
      phase = "connect";
      note(explain(error));
      refresh();
    }
  };

  ref("modes").addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-mode]");
    if (!button || button.disabled || button.dataset.mode === mode) return;
    mode = button.dataset.mode as "draft" | "direct";
    refresh();
    if (mode === "direct" && !creator) void loadCreator();
  });
  ref("privacy").addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-privacy]");
    if (!button || button.disabled) return;
    privacy = button.dataset.privacy ?? null;
    refresh();
  });
  ref("go").addEventListener("click", () => {
    if (phase === "connect") void connect();
    else if (phase === "form") void send();
    else if (phase === "done") dialog.close();
  });
  ref("cancel").addEventListener("click", () => dialog.close());
  ref("x").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => {
    closed = true;
    dialog.remove();
  });

  refresh();
  document.body.append(dialog);
  dialog.showModal();
  void (async () => {
    try {
      const state = await api<TikTokState>("/api/connect/tiktok", undefined, "GET");
      if (!state.configured) {
        phase = "setup";
        note(t("tiktok.setup"));
        refresh();
      } else if (!state.connected) {
        phase = "connect";
        refresh();
      } else await enterForm();
    } catch (error) {
      phase = "setup";
      note(explain(error));
      refresh();
    }
  })();
}
