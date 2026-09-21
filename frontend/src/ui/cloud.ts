import { api } from "../engine/api";
import type { MediaBin } from "../engine/media";
import { t } from "../i18n";
import { icon } from "./icons";
import { escapeHtml } from "./safe-text";
import type { PostTarget } from "./tiktok-dialog";
import "../styles/tiktok.css";
import "../styles/cloud.css";

type Service = "google" | "dropbox";

interface ServiceState {
  configured: boolean;
  connected: boolean;
  clientId: string;
  fullDrive: boolean;
}

interface Entry {
  id: string;
  name: string;
  folder: boolean;
  size: number;
}

interface JobState {
  status: string;
  error?: string;
  result?: { name?: string; media?: { name: string } };
}

const SERVICES: Service[] = ["google", "dropbox"];
const LABEL: Record<Service, string> = { google: "Google Drive", dropbox: "Dropbox" }; // product names, kept as they are
const wait = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms));
const explain = (error: unknown) => (error instanceof Error ? error.message : String(error));
const fill = (text: string, values: Record<string, string>) => text.replace(/\{(\w+)\}/g, (whole, name: string) => values[name] ?? whole);

function bytes(count: number): string {
  if (count >= 1e9) return `${(count / 1e9).toFixed(1)} GB`;
  if (count >= 1e6) return `${(count / 1e6).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(count / 1e3))} KB`;
}

async function finish(jobId: string): Promise<JobState> {
  for (;;) {
    const state = await api<JobState>(`/api/jobs/${jobId}`, undefined, "GET");
    if (state.status === "done" || state.status === "error" || state.status === "cancelled") return state;
    await wait(600);
  }
}

function shell(title: string): { dialog: HTMLDialogElement; body: HTMLElement; note: (text: string) => void } {
  const dialog = document.createElement("dialog");
  dialog.className = "post-dialog cloud-dialog";
  dialog.innerHTML = `
    <div class="post-head">
      <h3>${escapeHtml(title)}</h3>
      <button type="button" class="post-x" aria-label="${escapeHtml(t("btn.close"))}">${icon("close")}</button>
    </div>
    <div class="cloud-body"></div>
    <p class="post-note" aria-live="polite"></p>`;
  const noteEl = dialog.querySelector<HTMLElement>(".post-note")!;
  dialog.querySelector(".post-x")!.addEventListener("click", () => dialog.close());
  dialog.addEventListener("close", () => dialog.remove());
  document.body.append(dialog);
  dialog.showModal();
  return {
    dialog,
    body: dialog.querySelector<HTMLElement>(".cloud-body")!,
    note: (text) => {
      if (noteEl.textContent !== text) noteEl.textContent = text;
    },
  };
}

/** Browse Google Drive or Dropbox and add files to the bin. */
export function openCloudBrowser(bin: MediaBin): void {
  const { body, note } = shell(t("cloud.title"));
  body.innerHTML = `
    <div class="post-group" role="radiogroup">${SERVICES.map((service) => `<button type="button" class="post-choice" role="radio" data-service="${service}">${LABEL[service]}</button>`).join("")}</div>
    <div class="cloud-path"><button type="button" class="post-button" data-ref="back" hidden>${escapeHtml(t("cloud.back"))}</button><span data-ref="where"></span></div>
    <ul class="cloud-list" data-ref="list"></ul>
    <button type="button" class="post-button" data-ref="more" hidden>${escapeHtml(t("cloud.more"))}</button>`;
  const ref = <T extends HTMLElement = HTMLElement>(name: string) => body.querySelector<T>(`[data-ref="${name}"]`)!;
  let states: Record<string, ServiceState> = {};
  let service: Service = "google";
  let trail: Entry[] = [];
  let cursor = "";

  const row = (entry: Entry) => {
    const kind = entry.folder ? `<span class="cloud-kind">${icon("grid")}</span>` : `<span class="cloud-kind">${icon("pip")}</span>`;
    const action = entry.folder ? "" : `<button type="button" class="post-button" data-add="${escapeHtml(entry.id)}">${escapeHtml(t("library.add"))}</button>`;
    const size = entry.folder ? "" : bytes(entry.size);
    return `<li class="cloud-row${entry.folder ? " is-folder" : ""}" data-id="${escapeHtml(entry.id)}" data-name="${escapeHtml(entry.name)}" data-folder="${entry.folder}">${kind}<span class="cloud-name">${escapeHtml(entry.name)}</span><span class="cloud-size">${size}</span>${action}</li>`;
  };

  const load = async (reset: boolean) => {
    if (reset) {
      cursor = "";
      ref("list").innerHTML = "";
    }
    for (const button of body.querySelectorAll<HTMLButtonElement>("[data-service]")) button.setAttribute("aria-checked", String(button.dataset.service === service));
    ref("back").hidden = trail.length === 0;
    ref("where").textContent = [LABEL[service], ...trail.map((entry) => entry.name)].join(" / ");
    if (!states[service]?.connected) {
      ref("more").hidden = true;
      note(fill(t("cloud.setup"), { service: LABEL[service] }));
      return;
    }
    note("");
    const folder = trail.length ? trail[trail.length - 1].id : "";
    try {
      const page = await api<{ entries: Entry[]; cursor: string }>(`/api/cloud/${service}/files?${new URLSearchParams({ folder, cursor })}`, undefined, "GET");
      ref("list").insertAdjacentHTML("beforeend", page.entries.map(row).join(""));
      cursor = page.cursor;
      ref("more").hidden = !cursor;
      if (!ref("list").children.length) note(t("cloud.empty"));
    } catch (error) {
      note(explain(error));
    }
  };

  body.addEventListener("click", (event) => {
    const target = event.target as HTMLElement;
    const choice = target.closest<HTMLButtonElement>("[data-service]");
    if (choice && choice.dataset.service !== service) {
      service = choice.dataset.service as Service;
      trail = [];
      void load(true);
      return;
    }
    const adding = target.closest<HTMLButtonElement>("[data-add]");
    if (adding) {
      const item = adding.closest<HTMLElement>(".cloud-row")!;
      adding.disabled = true;
      note(t("cloud.importing"));
      api<{ job_id: string }>(`/api/cloud/${service}/import`, { id: item.dataset.id, name: item.dataset.name })
        .then((job) => finish(job.job_id))
        .then(async (state) => {
          if (state.status !== "done") throw new Error(state.error ?? state.status);
          await bin.load();
          note(`${t("library.added")}: ${state.result?.media?.name ?? item.dataset.name}`);
        })
        .catch((error) => note(explain(error)))
        .finally(() => {
          adding.disabled = false;
        });
      return;
    }
    const folder = target.closest<HTMLElement>(".cloud-row.is-folder");
    if (folder) {
      trail = [...trail, { id: folder.dataset.id!, name: folder.dataset.name!, folder: true, size: 0 }];
      void load(true);
    }
  });
  ref("back").addEventListener("click", () => {
    trail = trail.slice(0, -1);
    void load(true);
  });
  ref("more").addEventListener("click", () => void load(false));

  api<Record<string, ServiceState>>("/api/cloud", undefined, "GET").then(
    (found) => {
      states = found;
      service = SERVICES.find((name) => found[name]?.connected) ?? "google";
      void load(true);
    },
    (error) => note(explain(error)),
  );
}

/** Save an export or a bin item to Google Drive or Dropbox. */
export function openCloudUpload(target: PostTarget): void {
  const { body, note } = shell(t("cloud.saveTitle"));
  body.innerHTML = `<p class="post-source">${escapeHtml(target.name)}</p><ul class="cloud-list">${SERVICES.map((service) => `<li class="cloud-row"><span class="cloud-name">${LABEL[service]}</span><span class="cloud-size" data-state="${service}"></span><button type="button" class="post-button is-primary" data-upload="${service}" disabled>${escapeHtml(t("cloud.upload"))}</button></li>`).join("")}</ul>`;
  api<Record<string, ServiceState>>("/api/cloud", undefined, "GET").then(
    (states) => {
      for (const service of SERVICES) {
        const connected = Boolean(states[service]?.connected);
        body.querySelector<HTMLElement>(`[data-state="${service}"]`)!.textContent = connected ? t("tiktok.connected") : t("cloud.notConnected");
        body.querySelector<HTMLButtonElement>(`[data-upload="${service}"]`)!.disabled = !connected;
      }
    },
    (error) => note(explain(error)),
  );
  body.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-upload]");
    if (!button || button.disabled) return;
    const service = button.dataset.upload as Service;
    const source = "jobId" in target ? { jobId: target.jobId } : { mediaId: target.mediaId };
    for (const other of body.querySelectorAll<HTMLButtonElement>("[data-upload]")) other.disabled = true;
    note(t("cloud.uploading"));
    api<{ job_id: string }>(`/api/cloud/${service}/upload`, source)
      .then((job) => finish(job.job_id))
      .then((state) => {
        if (state.status !== "done") throw new Error(state.error ?? state.status);
        note(fill(t("cloud.saved"), { service: LABEL[service], name: state.result?.name ?? target.name }));
      })
      .catch((error) => {
        note(explain(error));
        button.disabled = false;
      });
  });
}

/**
 * Settings rows for one service: the client ID, Google's desktop secret and
 * the opt-in to browse all of Drive, or Dropbox's app key and the pasted code.
 * A blank secret field keeps the stored secret; the engine never sends it back.
 */
export function buildCloudSettings(rows: HTMLElement, service: Service): void {
  const google = service === "google";
  rows.insertAdjacentHTML(
    "beforeend",
    `<div class="prov-state"><span class="prov-badge" data-state="none">${escapeHtml(t("tiktok.notSet"))}</span><small class="panel-note" data-ref="say"></small></div>
    <div class="tiktok-fields">
      <input type="text" data-ref="id" autocomplete="off" spellcheck="false" placeholder="${escapeHtml(google ? t("cloud.clientId") : t("cloud.appKey"))}">
      ${google ? `<input type="password" data-ref="secret" autocomplete="off" placeholder="${escapeHtml(t("cloud.clientSecret"))}">` : ""}
    </div>
    ${google ? `<label class="post-toggle"><input type="checkbox" data-ref="full">${escapeHtml(t("cloud.fullDrive"))}</label><small class="panel-note">${escapeHtml(t("cloud.driveNote"))}</small>` : ""}
    <div class="prov-entry"><button class="tool-chip" data-act="save">${escapeHtml(t("tiktok.save"))}</button><button class="tool-chip" data-act="connect">${escapeHtml(t("instagram.connect"))}</button><button class="tool-chip" data-act="disconnect">${escapeHtml(t("tiktok.disconnect"))}</button></div>
    ${google ? "" : `<div class="prov-entry" data-ref="paste" hidden><input type="text" data-ref="code" autocomplete="off" spellcheck="false" placeholder="${escapeHtml(t("cloud.paste"))}"><button class="tool-chip" data-act="finish">${escapeHtml(t("cloud.finish"))}</button></div>`}`,
  );
  const ref = <T extends HTMLElement = HTMLElement>(name: string) => rows.querySelector<T>(`[data-ref="${name}"]`);
  const button = (act: string) => rows.querySelector<HTMLButtonElement>(`[data-act="${act}"]`)!;
  const badge = rows.querySelector<HTMLElement>(".prov-badge")!;
  const say = (text: string) => {
    const el = ref("say")!;
    if (el.textContent !== text) el.textContent = text;
  };
  const draw = (state: ServiceState) => {
    const key = state.connected ? "tiktok.connected" : state.configured ? "tiktok.ready" : "tiktok.notSet";
    if (badge.textContent !== t(key)) badge.textContent = t(key);
    badge.dataset.state = state.connected ? "good" : state.configured ? "set" : "none";
    button("connect").disabled = !state.configured || state.connected;
    button("disconnect").disabled = !state.connected;
  };
  const refresh = () => api<Record<string, ServiceState>>("/api/cloud", undefined, "GET").then((states) => states[service]);

  button("save").addEventListener("click", () => {
    const secret = ref<HTMLInputElement>("secret")?.value.trim() ?? "";
    const body = { clientId: ref<HTMLInputElement>("id")!.value.trim(), fullDrive: Boolean(ref<HTMLInputElement>("full")?.checked), ...(secret ? { clientSecret: secret } : {}) };
    api<ServiceState>(`/api/cloud/${service}/app`, body, "PUT").then(
      (state) => {
        const field = ref<HTMLInputElement>("secret");
        if (field) field.value = "";
        say("");
        draw(state);
      },
      (error) => say(explain(error)),
    );
  });
  button("connect").addEventListener("click", () => {
    button("connect").disabled = true;
    api<{ url: string; paste: boolean }>(`/api/cloud/${service}/start`, { open: true }).then(
      async (started) => {
        say(`${t("tiktok.waiting")} ${started.url}`);
        if (started.paste) {
          ref("paste")!.hidden = false;
          return;
        }
        const deadline = Date.now() + 600_000;
        while (Date.now() < deadline && rows.isConnected) {
          await wait(1500);
          const state = await refresh();
          if (state.connected) {
            say("");
            draw(state);
            return;
          }
        }
        button("connect").disabled = false;
      },
      (error) => {
        say(explain(error));
        button("connect").disabled = false;
      },
    );
  });
  if (!google) {
    button("finish").addEventListener("click", () => {
      api<ServiceState>("/api/cloud/dropbox/code", { code: ref<HTMLInputElement>("code")!.value }).then(
        (state) => {
          ref("paste")!.hidden = true;
          ref<HTMLInputElement>("code")!.value = "";
          say("");
          draw(state);
        },
        (error) => say(explain(error)),
      );
    });
  }
  button("disconnect").addEventListener("click", () => {
    api<ServiceState>(`/api/cloud/${service}`, undefined, "DELETE").then(draw, (error) => say(explain(error)));
  });
  refresh().then(
    (state) => {
      ref<HTMLInputElement>("id")!.value = state.clientId;
      const full = ref<HTMLInputElement>("full");
      if (full) full.checked = state.fullDrive;
      draw(state);
    },
    () => undefined,
  );
}
