import { api } from "../engine/api";
import { t } from "../i18n";
import { escapeHtml } from "./safe-text";
import "../styles/webhooks.css";

interface Outcome {
  status: string;
  detail: string;
}

interface Webhook {
  id: string;
  url: string;
  secret: string;
  sendFile: boolean;
  last: Outcome | null;
}

const ADDRESS = /^https?:\/\/[^\s/]+/i;

const explain = (error: unknown) => (error instanceof Error ? error.message : String(error));

const outcome = (last: Outcome | null) => {
  if (!last) return t("hooks.never");
  return last.status === "delivered" ? t("hooks.ok") : `${t("hooks.bad")}: ${last.detail}`;
};

/**
 * Settings rows for webhooks: every finished export is sent, signed, to these
 * addresses. A row shows the address, its signing secret with a copy button,
 * whether the video goes too, the last delivery, and test and remove buttons.
 * Rows are added and removed one at a time; the list is never redrawn whole.
 */
export function buildWebhooks(rows: HTMLElement): void {
  const list = document.createElement("div");
  list.className = "hook-list";
  const entry = document.createElement("div");
  entry.className = "prov-entry hook-entry";
  entry.innerHTML = `<input type="url" autocomplete="off" spellcheck="false" placeholder="${escapeHtml(t("hooks.url"))}"><button class="tool-chip">${escapeHtml(t("hooks.add"))}</button>`;
  const note = document.createElement("small");
  note.className = "panel-note";
  rows.append(list, entry, note);
  const input = entry.querySelector("input")!;
  const say = (text: string) => {
    if (note.textContent !== text) note.textContent = text;
  };

  const row = (hook: Webhook) => {
    const item = document.createElement("div");
    item.className = "hook-row";
    item.dataset.id = hook.id;
    item.innerHTML = `
      <div class="hook-url" title="${escapeHtml(hook.url)}">${escapeHtml(hook.url)}</div>
      <label class="hook-file"><input type="checkbox"${hook.sendFile ? " checked" : ""}>${escapeHtml(t("hooks.file"))}</label>
      <div class="hook-secret"><span>${escapeHtml(t("hooks.secret"))}</span><code>${escapeHtml(hook.secret)}</code><button class="tool-chip" data-act="copy">${escapeHtml(t("hooks.copy"))}</button></div>
      <div class="hook-foot"><small class="hook-last" data-state="${hook.last?.status ?? "none"}">${escapeHtml(outcome(hook.last))}</small><button class="tool-chip" data-act="test">${escapeHtml(t("prov.test"))}</button><button class="tool-chip" data-act="remove">${escapeHtml(t("hooks.remove"))}</button></div>`;
    return item;
  };

  const add = async () => {
    const url = input.value.trim();
    if (!url) return;
    if (!ADDRESS.test(url)) {
      say(t("hooks.invalid"));
      return;
    }
    try {
      list.append(row(await api<Webhook>("/api/webhooks", { url })));
      input.value = "";
      say("");
    } catch (error) {
      say(explain(error));
    }
  };

  list.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-act]");
    const item = button?.closest<HTMLElement>(".hook-row");
    if (!button || !item) return;
    const id = item.dataset.id!;
    const secret = item.querySelector("code")!.textContent ?? "";
    if (button.dataset.act === "copy") {
      navigator.clipboard.writeText(secret).then(
        () => say(t("hooks.copied")),
        () => say(secret),
      );
    } else if (button.dataset.act === "remove") {
      api(`/api/webhooks/${id}`, undefined, "DELETE").then(
        () => item.remove(),
        (error) => say(explain(error)),
      );
    } else {
      const last = item.querySelector<HTMLElement>(".hook-last")!;
      last.textContent = t("prov.testing");
      api<Outcome>(`/api/webhooks/${id}/test`, {}).then(
        (result) => {
          last.dataset.state = result.status;
          last.textContent = outcome(result);
        },
        (error) => {
          last.textContent = explain(error);
        },
      );
    }
  });
  list.addEventListener("change", (event) => {
    const box = event.target as HTMLInputElement;
    if (box.type !== "checkbox") return;
    const id = box.closest<HTMLElement>(".hook-row")!.dataset.id!;
    api(`/api/webhooks/${id}`, { sendFile: box.checked }, "PATCH").catch((error) => {
      box.checked = !box.checked;
      say(explain(error));
    });
  });
  entry.querySelector("button")!.addEventListener("click", () => void add());
  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter") void add();
  });

  api<Webhook[]>("/api/webhooks", undefined, "GET").then(
    (hooks) => list.append(...hooks.map(row)),
    () => undefined, // the engine is unreachable; the section stays empty until it is back
  );
}
