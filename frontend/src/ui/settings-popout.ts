// Settings popout. Anatomy follows the platform pattern this project matches:
// a scrim, a centred pair of a tab rail and a window, sectioned groups inside
// the window with heads and separators, and native controls tinted by the
// accent. The rail collapses to icons. Content is built once and switched by
// hidden, never rebuilt, so a tab change keeps scroll and focus.
import { t } from "../i18n";
import { localizeElement } from "../i18n/text";
import { icon } from "./icons";
import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { ACCENTS, PROFILES, apply, read, setAccent, setTheme } from "./appearance";
import { api } from "../engine/api";
import { buildModePanel } from "./mode-popout";
import { buildWebhooks } from "./webhooks-settings";
import { buildTikTokSettings } from "./tiktok-settings";
import { buildInstagramSettings } from "./instagram";
import { buildCloudSettings } from "./cloud";
import { buildRemoteSettings } from "./remote-settings";
import { autosaveEnabled, setAutosaveEnabled } from "../engine/persistence";

const PAGES = [
  ["project", "set.project", "sliders"],
  ["playback", "set.playback", "play"],
  ["appearance", "set.appearance", "palette"],
  ["interface", "mode.title", "layout"],
  ["providers", "set.providers", "key"],
  ["connections", "set.connections", "link"],
  ["advanced", "set.advanced", "box"],
] as const;

export function installSettingsPopout(engine: ProjectEngine, bin: MediaBin, opener: HTMLElement): void {
  const scrim = document.createElement("div");
  scrim.className = "set-scrim";
  scrim.hidden = true;
  scrim.innerHTML = `
    <div class="set-pair">
      <nav class="set-rail" aria-label="${t("set.title")}">
        <div class="set-rail-head"><strong>${t("set.title")}</strong></div>
        <div class="set-tabs" data-tabs></div>
        <button class="set-collapse" data-collapse title="${t("set.collapse")}">${icon("chevL")}</button>
      </nav>
      <section class="set-window" role="dialog" aria-modal="true" aria-label="${t("set.title")}">
        <header class="set-head"><strong data-page-title>${t("set.appearance")}</strong><button class="iconbtn" data-close title="${t("btn.close")}">${icon("close")}</button></header>
        <div class="set-body" data-body></div>
      </section>
    </div>`;
  document.body.append(scrim);

  const q = <T extends HTMLElement = HTMLElement>(name: string) => scrim.querySelector<T>(`[data-${name}]`)!;
  const body = q("body");
  const tabs = q("tabs");
  let page: string = "appearance";

  const views = new Map<string, HTMLElement>();
  const view = (id: string) => {
    const section = document.createElement("div");
    section.className = "set-view";
    section.dataset.view = id;
    section.hidden = true;
    views.set(id, section);
    body.append(section);
    return section;
  };

  const group = (parent: HTMLElement, titleKey: string, hintKey?: string) => {
    const section = document.createElement("section");
    section.className = "panel-section";
    const head = document.createElement("div");
    head.className = "panel-section-head";
    head.innerHTML = `<span>${t(titleKey)}</span>${hintKey ? `<small>${t(hintKey)}</small>` : ""}`;
    const rows = document.createElement("div");
    rows.className = "panel-rows";
    section.append(head, rows);
    parent.append(section);
    return rows;
  };

  const row = (parent: HTMLElement, labelKey: string, control: HTMLElement) => {
    const line = document.createElement("label");
    line.className = "panel-row";
    const text = document.createElement("span");
    text.textContent = t(labelKey);
    line.append(text, control);
    parent.append(line);
    return line;
  };

  const numberField = (value: number, min: number, max: number, step = 1) => {
    const input = document.createElement("input");
    input.type = "number";
    input.value = String(value);
    input.min = String(min);
    input.max = String(max);
    input.step = String(step);
    return input;
  };

  // --- project ---------------------------------------------------------------
  const project = view("project");
  const size = group(project, "set.frame", "set.frame.hint");
  const width = numberField(engine.snapshot.width, 16, 7680);
  const height = numberField(engine.snapshot.height, 16, 4320);
  const fps = numberField(engine.snapshot.fps, 1, 240);
  row(size, "set.width", width);
  row(size, "set.height", height);
  row(size, "set.fps", fps);
  const commit = () => engine.dispatch("project.settings", { width: Number(width.value), height: Number(height.value), fps: Number(fps.value) });
  for (const field of [width, height, fps]) field.addEventListener("change", commit);
  const saving = group(project, "save.autosave", "save.autosave.hint");
  const autosaveBox = document.createElement("input");
  autosaveBox.type = "checkbox";
  autosaveBox.checked = autosaveEnabled();
  autosaveBox.addEventListener("change", () => setAutosaveEnabled(autosaveBox.checked));
  row(saving, "save.autosave", autosaveBox);

  // --- playback --------------------------------------------------------------
  const playback = view("playback");
  const preview = group(playback, "set.preview", "set.preview.hint");
  const previewSize = document.createElement("select");
  for (const value of [480, 640, 854, 1280]) {
    const option = document.createElement("option");
    option.value = String(value);
    option.textContent = `${value} px`;
    previewSize.append(option);
  }
  previewSize.value = String(localStorage.getItem("formcut.previewWidth") ?? 640);
  previewSize.addEventListener("change", () => {
    try {
      localStorage.setItem("formcut.previewWidth", previewSize.value);
    } catch {
      // Not persisting is acceptable; the running session still uses the value.
    }
    document.dispatchEvent(new CustomEvent("formcut:preview-width", { detail: Number(previewSize.value) }));
  });
  row(preview, "set.previewsize", previewSize);

  // --- appearance ------------------------------------------------------------
  const appearance = view("appearance");
  const themes = group(appearance, "set.profiles", "set.profiles.hint");
  const grid = document.createElement("div");
  grid.className = "theme-grid";
  themes.append(grid);
  const cards = new Map<string, HTMLElement>();
  for (const profile of PROFILES) {
    const card = document.createElement("button");
    card.className = "theme-card";
    card.dataset.theme = profile.id;
    card.innerHTML = `<span class="theme-swatch" data-theme-preview="${profile.id}"><i></i><i></i><i></i></span><span class="theme-name">${profile.label}</span>`;
    card.addEventListener("click", () => {
      setTheme(profile.id);
      markTheme();
    });
    cards.set(profile.id, card);
    grid.append(card);
  }

  const accentRows = group(appearance, "set.accent", "set.accent.hint");
  const swatches = document.createElement("div");
  swatches.className = "accent-row";
  const accentButtons = new Map<string, HTMLElement>();
  for (const hex of ACCENTS) {
    const swatch = document.createElement("button");
    swatch.className = "accent-swatch";
    swatch.style.background = hex;
    swatch.dataset.accent = hex;
    swatch.title = hex;
    swatch.addEventListener("click", () => {
      setAccent(hex);
      markAccent();
    });
    accentButtons.set(hex, swatch);
    swatches.append(swatch);
  }
  const custom = document.createElement("input");
  custom.type = "color";
  custom.className = "accent-custom";
  custom.addEventListener("input", () => {
    setAccent(custom.value);
    markAccent();
  });
  const reset = document.createElement("button");
  reset.className = "tool-chip";
  reset.textContent = t("set.accent.default");
  reset.addEventListener("click", () => {
    setAccent(null);
    markAccent();
  });
  swatches.append(custom, reset);
  accentRows.append(swatches);

  // --- AI providers ----------------------------------------------------------
  // One panel per provider, all state from the engine: the key lives there, so
  // the interface is told whether one is configured and its last four
  // characters, never the key itself.
  const providersView = view("providers");
  const providerPanels = new Map<string, { status: HTMLElement; hint: HTMLElement; input: HTMLInputElement }>();

  const drawProviderState = (state: { id: string; label: string; configured: boolean; source: string; hint: string; envName: string; ok?: boolean; detail?: string }) => {
    const panel = providerPanels.get(state.id);
    if (!panel) return;
    const key = !state.configured ? "prov.nokey" : state.ok === false ? "prov.failed" : state.ok ? "prov.connected" : "prov.configured";
    panel.status.textContent = t(key);
    panel.status.dataset.state = !state.configured ? "none" : state.ok === false ? "bad" : state.ok ? "good" : "set";
    panel.hint.textContent = state.detail
      ? state.detail
      : state.configured
        ? `${t("prov.source." + state.source)}${state.hint ? ` (…${state.hint})` : ""}`
        : `${t("prov.setenv")} ${state.envName}`;
  };

  const refreshProviders = async () => {
    try {
      const list = await api("/api/providers", undefined, "GET") as Array<Parameters<typeof drawProviderState>[0]>;
      for (const state of list) drawProviderState(state);
    } catch {
      // The engine is unreachable; the panels keep their last known state.
    }
  };

  for (const [id, label] of [["pexels", "Pexels"], ["elevenlabs", "ElevenLabs"], ["topaz", "Topaz Labs"]] as const) {
    const rows = group(providersView, label, `prov.${id}.use`);
    const stateLine = document.createElement("div");
    stateLine.className = "prov-state";
    stateLine.innerHTML = `<span class="prov-badge" data-state="none">${t("prov.nokey")}</span><small class="panel-note"></small>`;
    const status = stateLine.querySelector<HTMLElement>(".prov-badge")!;
    const hint = stateLine.querySelector<HTMLElement>("small")!;
    const entry = document.createElement("div");
    entry.className = "prov-entry";
    const input = document.createElement("input");
    input.type = "password";
    input.autocomplete = "off";
    input.placeholder = t("prov.placeholder");
    const save = document.createElement("button");
    save.className = "tool-chip";
    save.textContent = t("prov.save");
    const test = document.createElement("button");
    test.className = "tool-chip";
    test.textContent = t("prov.test");
    const clear = document.createElement("button");
    clear.className = "tool-chip";
    clear.textContent = t("prov.clear");
    entry.append(input, save, test, clear);
    rows.append(stateLine, entry);
    providerPanels.set(id, { status, hint, input });

    save.addEventListener("click", () => void (async () => {
      if (!input.value.trim()) return;
      try {
        drawProviderState(await api(`/api/providers/${id}/key`, { key: input.value.trim() }) as Parameters<typeof drawProviderState>[0]);
        input.value = "";
      } catch (error) {
        hint.textContent = error instanceof Error ? error.message : t("prov.failed");
      }
    })());
    test.addEventListener("click", () => void (async () => {
      hint.textContent = t("prov.testing");
      try {
        drawProviderState(await api(`/api/providers/${id}/test`, {}) as Parameters<typeof drawProviderState>[0]);
      } catch (error) {
        hint.textContent = error instanceof Error ? error.message : t("prov.failed");
      }
    })());
    clear.addEventListener("click", () => void (async () => {
      try {
        drawProviderState(await api(`/api/providers/${id}/key`, undefined, "DELETE") as Parameters<typeof drawProviderState>[0]);
      } catch (error) {
        hint.textContent = error instanceof Error ? error.message : t("prov.failed");
      }
    })());
  }

  // Hosted speech has a generate action here, because a provider panel that can
  // only be tested is not much use: the same path the Studio speech page takes
  // for the local runtime, through the hosted endpoint.
  buildWebhooks(group(providersView, "hooks.title", "hooks.use"));
  buildTikTokSettings(group(providersView, "TikTok", "prov.tiktok.use"));
  buildInstagramSettings(group(providersView, "Instagram", "prov.instagram.use"));
  buildCloudSettings(group(providersView, "Google Drive", "prov.google.use"), "google");
  buildCloudSettings(group(providersView, "Dropbox", "prov.dropbox.use"), "dropbox");
  buildRemoteSettings(group(providersView, "remote.title", "prov.remote.use"));
  const speechRows = group(providersView, "prov.generate", "prov.generate.hint");
  const speechText = document.createElement("input");
  speechText.type = "text";
  speechText.placeholder = t("prov.generate.placeholder");
  const speechGo = document.createElement("button");
  speechGo.className = "tool-chip";
  speechGo.textContent = t("prov.generate.go");
  const speechNote = document.createElement("small");
  speechNote.className = "panel-note";
  const speechLine = document.createElement("div");
  speechLine.className = "prov-entry";
  speechLine.append(speechText, speechGo);
  speechRows.append(speechLine, speechNote);
  speechGo.addEventListener("click", () => void (async () => {
    const phrase = speechText.value.trim();
    if (!phrase) return;
    speechNote.textContent = t("prov.generate.working");
    const start = engine.snapshot.playhead;
    const timelineId = engine.snapshot.timelines[engine.snapshot.activeTimeline].id;
    try {
      const media = await api("/api/tts/speak", { text: phrase }) as { id: string; name: string; duration: number };
      await bin.load();
      if (engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timelineId) {
        speechNote.textContent = t("prov.generate.moved");
        return;
      }
      const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
      const trackIndex = Math.max(0, tracks.findIndex((track) => /audio/i.test(track.name)));
      engine.dispatch("clip.add", { trackIndex, clip: { id: crypto.randomUUID(), kind: "audio", label: media.name, mediaId: media.id, start, duration: media.duration } });
      speechNote.textContent = t("prov.generate.added");
    } catch (error) {
      speechNote.textContent = error instanceof Error ? error.message : t("prov.failed");
    }
  })());

  // --- connections -----------------------------------------------------------
  // What the orchestration surface looks like from inside the app: who is
  // driving, what they last asked for, and live job activity from the event
  // stream. Cancellation is available here too, so either side can stop a job.
  const connectionsView = view("connections");
  const sessionRows = group(connectionsView, "conn.sessions", "conn.sessions.hint");
  const sessionList = document.createElement("div");
  sessionList.className = "conn-list";
  sessionRows.append(sessionList);
  const activityRows = group(connectionsView, "conn.activity", "conn.activity.hint");
  const activityList = document.createElement("div");
  activityList.className = "conn-list conn-activity";
  activityRows.append(activityList);

  const live = new Map<string, { status: string; progress: number; kind: string }>();

  const drawSessions = async () => {
    try {
      const sessions = await api("/api/orchestration/sessions", undefined, "GET") as Array<{
        id: string; name: string; agent: string; operations: Array<{ method: string }>;
      }>;
      sessionList.replaceChildren();
      if (!sessions.length) {
        const note = document.createElement("p");
        note.className = "panel-note";
        note.textContent = t("conn.none");
        sessionList.append(note);
        return;
      }
      for (const session of sessions) {
        const row = document.createElement("div");
        row.className = "panel-row";
        const last = session.operations.at(-1)?.method ?? "";
        row.innerHTML = `<span>${session.name}${session.agent ? ` · ${session.agent}` : ""}</span><span>${session.operations.length} ${t("conn.calls")}${last ? ` · ${last}` : ""}</span>`;
        sessionList.append(row);
      }
    } catch {
      // The engine is unreachable; the list keeps what it had.
    }
  };

  const drawActivity = () => {
    activityList.replaceChildren();
    if (!live.size) {
      const note = document.createElement("p");
      note.className = "panel-note";
      note.textContent = t("conn.idle");
      activityList.append(note);
      return;
    }
    for (const [id, job] of [...live].reverse().slice(0, 6)) {
      const row = document.createElement("div");
      row.className = "panel-row";
      const percent = Math.round(job.progress * 100);
      row.innerHTML = `<span>${job.kind} · ${t("conn.status." + job.status) || job.status}${job.status === "running" ? ` ${percent}%` : ""}</span>`;
      if (job.status === "running") {
        const stop = document.createElement("button");
        stop.className = "tool-chip";
        stop.textContent = t("conn.cancel");
        stop.addEventListener("click", () => void api(`/api/jobs/${id}`, undefined, "DELETE").catch(() => {}));
        row.append(stop);
      }
      activityList.append(row);
    }
  };

  // One stream for the whole app, opened when the tab is first shown and left
  // open: the engine keeps it warm and a reconnect would lose backlog position.
  let stream: EventSource | undefined;
  const openStream = () => {
    if (stream) return;
    stream = new EventSource("/api/orchestration/events");
    stream.addEventListener("message", (event) => {
      try {
        const payload = JSON.parse((event as MessageEvent<string>).data) as Record<string, unknown>;
        if (payload.kind === "job" && typeof payload.job === "string") {
          live.set(payload.job, {
            status: String(payload.status ?? "running"),
            progress: Number(payload.progress ?? 0),
            kind: String(payload.job_kind ?? "job"),
          });
          drawActivity();
        }
        if (String(payload.kind).startsWith("session") || payload.kind === "operation") void drawSessions();
      } catch {
        // A malformed frame is skipped rather than breaking the listener.
      }
    });
  };

  const providerNote = document.createElement("p");
  providerNote.className = "panel-note";
  providerNote.textContent = t("prov.note");
  providersView.append(providerNote);

  // --- advanced --------------------------------------------------------------
  const advanced = view("advanced");
  view("interface").append(buildModePanel());
  const keys = group(advanced, "set.keys", "set.keys.hint");
  const keysNote = document.createElement("p");
  keysNote.className = "panel-note";
  keysNote.textContent = t("set.keys.note");
  keys.append(keysNote);
  const reseter = group(advanced, "set.reset", "set.reset.hint");
  const clearAppearance = document.createElement("button");
  clearAppearance.className = "tool-chip";
  clearAppearance.textContent = t("set.reset.appearance");
  clearAppearance.addEventListener("click", () => {
    setTheme("formcut-dark");
    setAccent(null);
    markTheme();
    markAccent();
  });
  reseter.append(clearAppearance);

  // --- chrome ----------------------------------------------------------------
  for (const [id, labelKey, glyph] of PAGES) {
    const tab = document.createElement("button");
    tab.className = "set-tab";
    tab.dataset.page = id;
    tab.dataset.feature = `set.${id}`;
    tab.innerHTML = `${icon(glyph)}<span>${t(labelKey)}</span>`;
    tab.addEventListener("click", () => {
      page = id;
      showPage();
    });
    tabs.append(tab);
  }

  function markTheme(): void {
    const active = read().theme;
    for (const [id, card] of cards) card.classList.toggle("is-active", id === active);
  }
  function markAccent(): void {
    const accent = read().accent;
    for (const [hex, swatch] of accentButtons) swatch.classList.toggle("is-active", hex === accent);
    if (accent) custom.value = accent;
  }
  function showPage(): void {
    for (const [id, section] of views) section.hidden = id !== page;
    for (const tab of tabs.querySelectorAll<HTMLElement>("[data-page]")) tab.classList.toggle("is-active", tab.dataset.page === page);
    const entry = PAGES.find(([id]) => id === page);
    if (entry) q("page-title").textContent = t(entry[1]);
    if (page === "project") {
      const state = engine.snapshot;
      for (const [field, value] of [[width, state.width], [height, state.height], [fps, state.fps]] as const) {
        if (document.activeElement !== field) field.value = String(value);
      }
    }
    if (page === "providers") void refreshProviders();
    if (page === "connections") {
      openStream();
      void drawSessions();
      drawActivity();
    }
    if (page === "appearance") {
      markTheme();
      markAccent();
    }
  }

  const close = () => {
    if (scrim.hidden) return;
    scrim.hidden = true;
    opener.focus();
  };
  q("close").addEventListener("click", close);
  q("collapse").addEventListener("click", () => scrim.querySelector(".set-rail")!.classList.toggle("is-collapsed"));
  scrim.addEventListener("pointerdown", (event) => {
    if (event.target === scrim) close();
  });
  scrim.addEventListener("keydown", (event) => {
    if (event.key === "Escape") close();
  });
  opener.addEventListener("click", () => {
    scrim.hidden = false;
    showPage();
    q("close").focus();
  });
  localizeElement(scrim);
  apply(read(), false);
  showPage();
}
