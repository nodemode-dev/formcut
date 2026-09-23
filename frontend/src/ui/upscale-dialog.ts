import { api } from "../engine/api";
import type { MediaBin, MediaItem } from "../engine/media";
import { t } from "../i18n";
import { icon } from "./icons";
import { escapeHtml } from "./safe-text";
import "../styles/upscale.css";

type Method = "lanczos" | "sharp" | "bicubic" | "ai" | "topaz";

interface JobState {
  status: string;
  progress?: number;
  error?: string;
  result?: { media?: { name: string } };
}

interface Estimate {
  request_id: string;
  credits?: number[] | null;
  seconds?: number[] | null;
}

const METHODS: Array<[Method, string]> = [
  ["lanczos", "upscale.lanczos"],
  ["sharp", "upscale.sharp"],
  ["bicubic", "upscale.bicubic"],
  ["ai", "upscale.ai"],
  ["topaz", "upscale.topaz"],
];
const FACTORS = [1.5, 2, 3, 4];
const LIMIT = 4096; // the engine's longest side for the methods that run here
const MODEL = "prob-4"; // Proteus, the model Topaz documents for enhancement

const fill = (text: string, values: Record<string, string>) => text.replace(/\{(\w+)\}/g, (whole, name: string) => values[name] ?? whole);
const even = (value: number) => Math.max(2, Math.round(value / 2) * 2);
const range = (pair?: number[] | null) => (pair && pair.length === 2 ? (pair[0] === pair[1] ? `${pair[0]}` : `${pair[0]}–${pair[1]}`) : "?");

/**
 * The upscale dialog for one bin item. The methods that run here start at once;
 * Topaz asks for an estimate first, which is free, and only the button that
 * names the credits starts the billed job. The result arrives in the bin as a
 * new item, even if the dialog was closed while it ran.
 */
export function openUpscale(item: MediaItem, bin: MediaBin): void {
  const picture = item as MediaItem & { width?: number; height?: number };
  const width = picture.width ?? 0;
  const height = picture.height ?? 0;
  const still = item.kind === "image";
  const dialog = document.createElement("dialog");
  dialog.className = "upscale-dialog";
  dialog.innerHTML = `
    <div class="upscale-head">
      <h3>${escapeHtml(t("upscale.title"))}</h3>
      <button type="button" class="upscale-x" data-ref="x" aria-label="${escapeHtml(t("btn.close"))}">${icon("close")}</button>
    </div>
    <p class="upscale-source">${escapeHtml(item.name)}${width ? ` · ${width} × ${height}` : ""}</p>
    <div class="upscale-group" role="radiogroup" aria-label="${escapeHtml(t("upscale.method"))}" data-ref="methods">
      <span class="upscale-label">${escapeHtml(t("upscale.method"))}</span>
      ${METHODS.map(([id, key]) => `<button type="button" class="upscale-choice" role="radio" data-method="${id}"${id === "topaz" && still ? ` disabled title="${escapeHtml(t("upscale.videoOnly"))}"` : ""}>${escapeHtml(t(key))}</button>`).join("")}
    </div>
    <div class="upscale-group" role="radiogroup" aria-label="${escapeHtml(t("upscale.size"))}" data-ref="factors">
      <span class="upscale-label">${escapeHtml(t("upscale.size"))}</span>
      ${FACTORS.map((factor) => `<button type="button" class="upscale-choice" role="radio" data-factor="${factor}">${factor}×</button>`).join("")}
    </div>
    <p class="upscale-result" data-ref="result"></p>
    <p class="upscale-hint" data-ref="hint"></p>
    <div class="upscale-bar" data-ref="bar" hidden><span data-ref="fill"></span></div>
    <p class="upscale-note" data-ref="note" aria-live="polite"></p>
    <div class="upscale-foot">
      <button type="button" class="upscale-button" data-ref="cancel">${escapeHtml(t("export.cancel"))}</button>
      <button type="button" class="upscale-button is-primary" data-ref="go"></button>
    </div>`;
  const ref = <T extends HTMLElement = HTMLElement>(name: string) => dialog.querySelector<T>(`[data-ref="${name}"]`)!;
  const setText = (el: HTMLElement, text: string) => {
    if (el.textContent !== text) el.textContent = text;
  };
  const note = (text: string) => setText(ref("note"), text);

  let method: Method = "lanczos";
  let factor = 2;
  let estimate: Estimate | null = null;
  let running: string | null = null;
  let finished = false;
  let shown = -1;
  let topazKey: boolean | null = null; // unknown until Topaz is picked
  let aiReady: boolean | null = null; // unknown until AI is picked

  const fits = (candidate: number) => method === "topaz" || Math.max(width, height) * candidate <= LIMIT;
  const blocked = () => method === "topaz" && topazKey === false && !finished;

  const progress = (value: number) => {
    const percent = Math.round(Math.min(1, Math.max(0, value)) * 100);
    if (percent === shown) return;
    shown = percent;
    ref("fill").style.width = `${percent}%`;
  };

  const refresh = () => {
    if (!fits(factor)) factor = FACTORS.filter(fits).pop() ?? factor;
    let limited = false;
    for (const button of ref("methods").querySelectorAll<HTMLButtonElement>("[data-method]")) {
      button.setAttribute("aria-checked", String(button.dataset.method === method));
      if (!(still && button.dataset.method === "topaz")) button.disabled = running !== null;
    }
    for (const button of ref("factors").querySelectorAll<HTMLButtonElement>("[data-factor]")) {
      const candidate = Number(button.dataset.factor);
      if (!fits(candidate)) limited = true;
      button.disabled = !fits(candidate) || running !== null;
      button.setAttribute("aria-checked", String(candidate === factor));
    }
    setText(ref("result"), width ? fill(t("upscale.result"), { size: `${even(width * factor)} × ${even(height * factor)}` }) : "");
    const topazHint = topazKey === false ? t("upscale.needKey") : t("upscale.topazNote");
    setText(ref("hint"), method === "topaz" ? topazHint : method === "ai" && !limited ? t("upscale.aiNote") : limited ? fill(t("upscale.limit"), { limit: String(LIMIT) }) : "");
    const go = ref<HTMLButtonElement>("go");
    let label = t("upscale.title");
    if (finished) label = t("btn.close");
    else if (method === "topaz") label = estimate ? fill(t("upscale.pay"), { credits: range(estimate.credits) }) : t("upscale.ask");
    else if (method === "ai" && aiReady === false) label = t("upscale.aiDownload");
    setText(go, label);
    go.disabled = running !== null || blocked() || (!finished && !fits(factor));
  };

  const checkKey = async () => {
    if (topazKey !== null) return;
    try {
      const listed = await api<Array<{ id: string; configured: boolean }>>("/api/providers", undefined, "GET");
      topazKey = listed.some((entry) => entry.id === "topaz" && entry.configured);
    } catch {
      topazKey = true; // the provider list is out of reach: let the engine answer instead
    }
    refresh();
  };

  const checkModel = async () => {
    if (aiReady !== null) return;
    try {
      const listed = await api<Array<{ id: string; ready?: boolean }>>("/api/models", undefined, "GET");
      aiReady = listed.some((entry) => entry.id === "ai-upscale" && entry.ready);
    } catch {
      aiReady = true; // the model list is out of reach: let the engine answer instead
    }
    refresh();
  };

  // The model is fetched here, with progress, and the dialog then upscales as usual.
  const fetchModel = async () => {
    const started = await api<{ job_id: string }>("/api/models/ai-upscale/download", {});
    running = started.job_id;
    progress(0);
    ref("bar").hidden = false;
    note(t("upscale.aiDownloading"));
    refresh();
    for (;;) {
      const state = await api<JobState>(`/api/jobs/${started.job_id}`, undefined, "GET");
      progress(state.progress ?? 0);
      if (state.status === "done" || state.status === "error" || state.status === "cancelled") {
        running = null;
        ref("bar").hidden = true;
        aiReady = state.status === "done";
        note(state.status === "done" ? "" : state.status === "error" ? (state.error ?? "") : t("upscale.cancelled"));
        refresh();
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
  };

  const watch = async (jobId: string) => {
    for (;;) {
      const state = await api<JobState>(`/api/jobs/${jobId}`, undefined, "GET");
      progress(state.progress ?? 0);
      if (state.status === "done") {
        await bin.load();
        running = null;
        finished = true;
        progress(1);
        note(`${t("library.added")}: ${state.result?.media?.name ?? ""}`);
        refresh();
        return;
      }
      if (state.status === "error" || state.status === "cancelled") {
        running = null;
        ref("bar").hidden = true;
        note(state.status === "error" ? (state.error ?? "") : t("upscale.cancelled"));
        refresh();
        return;
      }
      await new Promise((resolve) => window.setTimeout(resolve, 500));
    }
  };

  const start = async () => {
    if (finished) {
      dialog.close();
      return;
    }
    try {
      if (method === "ai" && aiReady === false) {
        await fetchModel();
        return;
      }
      if (method === "topaz" && !estimate) {
        const reply = await api<Estimate>(`/api/media/${item.id}/upscale/estimate`, { method, factor, model: MODEL });
        estimate = reply;
        const minutes = reply.seconds?.map((seconds) => Math.max(1, Math.ceil(seconds / 60)));
        note(fill(t("upscale.estimate"), { credits: range(reply.credits), minutes: range(minutes) }));
        refresh();
        return;
      }
      const started = await api<{ job_id: string }>(`/api/media/${item.id}/upscale`, { method, factor, model: MODEL, request_id: estimate?.request_id });
      running = started.job_id;
      shown = -1;
      progress(0);
      ref("bar").hidden = false;
      note(t("upscale.working"));
      refresh();
      await watch(started.job_id);
    } catch (error) {
      running = null;
      note(error instanceof Error ? error.message : String(error));
      refresh();
    }
  };

  ref("methods").addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-method]");
    if (!button || button.disabled || button.dataset.method === method) return;
    method = button.dataset.method as Method;
    estimate = null;
    note("");
    refresh();
    if (method === "topaz") void checkKey();
    if (method === "ai") void checkModel();
  });
  ref("factors").addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-factor]");
    if (!button || button.disabled || Number(button.dataset.factor) === factor) return;
    factor = Number(button.dataset.factor);
    estimate = null;
    note("");
    refresh();
  });
  ref("go").addEventListener("click", () => void start());
  ref("cancel").addEventListener("click", () => {
    if (running) void api(`/api/jobs/${running}`, undefined, "DELETE").catch(() => undefined);
    else dialog.close();
  });
  ref("x").addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => dialog.remove());

  refresh();
  document.body.append(dialog);
  dialog.showModal();
}
