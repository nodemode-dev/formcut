import { t } from "../i18n";

export type AccessState = { choice: string; stored: string; seal: string; sealBroken: boolean; notice: string };
type Answer = "deny" | "once" | "always";

const GLYPH = `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="8" width="14" height="11" rx="2"/><path d="M12 8V5"/><circle cx="12" cy="4" r="1"/><circle cx="9.5" cy="13" r="1"/><circle cx="14.5" cy="13" r="1"/><path d="M9.5 16.5h5"/></svg>`;

let dialog: { scrim: HTMLElement; note: HTMLElement; notice: HTMLElement; deny: HTMLButtonElement; once: HTMLButtonElement; always: HTMLButtonElement } | null = null;
let queue: Promise<unknown> = Promise.resolve();

function build() {
  const scrim = document.createElement("div");
  scrim.className = "modal-scrim agent-access";
  scrim.hidden = true;
  scrim.innerHTML = `
    <div class="modal-panel" role="alertdialog" aria-modal="true" aria-labelledby="agent-access-title">
      <div class="modal-title agent-access-title" id="agent-access-title">${GLYPH}<span></span></div>
      <p class="modal-note" data-note></p>
      <p class="modal-note agent-access-notice" data-notice hidden></p>
      <div class="modal-actions">
        <button type="button" class="tool-chip" data-deny></button>
        <button type="button" class="tool-chip" data-once></button>
        <button type="button" class="tool-chip is-primary" data-always></button>
      </div>
    </div>`;
  scrim.querySelector<HTMLElement>(".agent-access-title span")!.textContent = t("access.dialog.title");
  const pick = <T extends HTMLElement>(name: string) => scrim.querySelector<T>(`[data-${name}]`)!;
  const parts = { scrim, note: pick("note"), notice: pick("notice"), deny: pick<HTMLButtonElement>("deny"), once: pick<HTMLButtonElement>("once"), always: pick<HTMLButtonElement>("always") };
  parts.deny.textContent = t("access.deny");
  parts.once.textContent = t("access.once");
  parts.always.textContent = t("access.always");
  document.body.append(scrim);
  return parts;
}

function show(tool: string, agent: string, notice: string): Promise<Answer> {
  dialog ??= build();
  const parts = dialog;
  const note = t("access.dialog.note").replace("{agent}", agent || t("access.someone")).replace("{tool}", tool);
  if (parts.note.textContent !== note) parts.note.textContent = note;
  if (parts.notice.textContent !== notice) parts.notice.textContent = notice;
  parts.notice.hidden = !notice;
  return new Promise<Answer>((resolve) => {
    const done = (answer: Answer) => {
      parts.scrim.hidden = true;
      parts.deny.onclick = parts.once.onclick = parts.always.onclick = null;
      document.removeEventListener("keydown", onKey, true);
      resolve(answer);
    };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") { event.stopPropagation(); done("deny"); } };
    parts.deny.onclick = () => done("deny");
    parts.once.onclick = () => done("once");
    parts.always.onclick = () => done("always");
    document.addEventListener("keydown", onKey, true);
    parts.scrim.hidden = false;
    parts.deny.focus();
  });
}

/** The window's answer to one outside agent's request; one question at a time. */
export function askAgentAccess(request: { tool?: string; agent?: string; notice?: string }): Promise<Answer> {
  const next = queue.then(() => show(request.tool ?? "", request.agent ?? "", request.notice ?? ""));
  queue = next.catch(() => undefined);
  return next;
}

/** Builds the dialog ahead of the first question, so showing it adds nothing to the page. */
export function installAgentAccess(): void {
  dialog ??= build();
}
