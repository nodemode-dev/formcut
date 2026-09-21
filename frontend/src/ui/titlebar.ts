import { fileMenu } from "./file-menu";
import { text } from "../i18n/text";
import { escapeHtml } from "./safe-text";
import type { ProjectEngine } from "../engine/project";
import { listProjects, newProject, openProject, saveProject, installAutosave } from "../engine/persistence";
import { exportProject } from "./export-job";
import { api } from "../engine/api";
import { icon } from "./icons";
import { t } from "../i18n";
import { buildModePanel } from "./mode-popout";
import { openTikTok } from "./tiktok-dialog";
import { openInstagram } from "./instagram";
import { activeProfile, onInterfaceMode, type InterfaceProfile } from "./interface-mode";

export interface AppActions {
  save: () => void;
  newProject: () => void;
}

export function buildTitlebar(engine: ProjectEngine, actions?: AppActions): HTMLElement {
  const s = engine.snapshot;
  const el = document.createElement("header");
  el.className = "titlebar";
  el.innerHTML = `
    <div class="titlebar-left">
      <button class="titlebar-logo" data-ref="home" title="${t("home.title")}" aria-label="${t("home.title")}">${icon("logo")}</button>
      <button class="menu-item" data-ref="file" data-feature="menu.file">${t("menu.file")}</button>
      <button class="menu-item" data-ref="edit" data-feature="menu.edit">${t("menu.edit")}</button>
      <button class="menu-item" data-ref="view" data-feature="menu.view">${t("menu.view")}</button>
    </div>
    <div class="titlebar-center">
      <span class="project-title" data-ref="title" title="Click to rename">${escapeHtml(s.title)}</span>
      <input class="project-title-input" data-ref="title-input" hidden />
      <span class="save-state" data-ref="saved">${s.saved ? "saved" : "edited"}</span>
    </div>
    <div class="titlebar-right">
      <button class="iconbtn" title="${t('layout.focus')}" data-ref="focus-preview" data-feature="titlebar.focus">${icon("pip")}</button>
      <button class="iconbtn" title="${t('layout.panels')}" data-ref="panels" data-feature="titlebar.panels">${icon("sliders")}</button>
      <button class="iconbtn mode-chip" data-ref="mode" data-feature="titlebar.mode" aria-expanded="false" aria-label="${t("layout.mode")}">${icon("layout")}<span class="sr-only" data-ref="mode-name"></span></button>
      <button class="iconbtn" title="${t('set.title')}" data-ref="settings" data-feature="titlebar.settings">${icon("settings")}</button>
      <button class="btn-export" data-ref="export" data-feature="titlebar.export">${icon("export")}${t("btn.export")}</button>
    </div>`;
  const saved = el.querySelector<HTMLElement>('[data-ref="saved"]')!;
  const title = el.querySelector<HTMLElement>('[data-ref="title"]')!;
  const titleInput = el.querySelector<HTMLInputElement>('[data-ref="title-input"]')!;
  const modeChip = el.querySelector<HTMLButtonElement>('[data-ref="mode"]')!;
  const modeName = el.querySelector<HTMLElement>('[data-ref="mode-name"]')!;
  const modePopout = document.createElement("div");
  modePopout.className = "mode-popout";
  modePopout.hidden = true;
  modePopout.append(buildModePanel());
  el.append(modePopout);
  const paintMode = (profile: InterfaceProfile) => {
    const name = profile.id === "easy" ? t("mode.easy") : profile.id === "advanced" ? t("mode.advanced") : profile.name;
    if (modeName.textContent !== name) modeName.textContent = name;
    // The chip shows only its icon now, so the mode's name lives in the tooltip
    // and the accessible label rather than beside it.
    const label = `${t("layout.mode")}: ${name}`;
    if (modeChip.title !== label) { modeChip.title = label; modeChip.setAttribute("aria-label", label); }
  };
  paintMode(activeProfile());
  onInterfaceMode(paintMode);
  const closeMode = () => { if (!modePopout.hidden) { modePopout.hidden = true; modeChip.setAttribute("aria-expanded", "false"); } };
  modeChip.addEventListener("click", () => {
    const open = modePopout.hidden;
    modePopout.hidden = !open;
    modeChip.setAttribute("aria-expanded", String(open));
  });
  document.addEventListener("pointerdown", (event) => {
    if (modePopout.hidden) return;
    const target = event.target as HTMLElement;
    if (!modePopout.contains(target) && !modeChip.contains(target)) closeMode();
  });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape") closeMode(); });
  engine.subscribe((state) => {
    const next = text(state.saved ? "saved" : "edited");
    if (saved.textContent !== next) saved.textContent = next;
    if (title.textContent !== state.title) title.textContent = state.title;
  });
  const conflictBar = document.createElement("div");
  conflictBar.className = "conflict-bar";
  conflictBar.hidden = true;
  conflictBar.innerHTML = `<span>${t("save.conflict")}</span><button class="tool-chip" data-ref="conflict-reload">${t("save.reload")}</button><button class="tool-chip" data-ref="conflict-keep">${t("save.keep")}</button>`;
  el.append(conflictBar);
  conflictBar.querySelector('[data-ref="conflict-reload"]')!.addEventListener("click", () => {
    conflictBar.hidden = true;
    const id = engine.snapshot.projectId;
    if (id) void openProject(engine, id);
  });
  conflictBar.querySelector('[data-ref="conflict-keep"]')!.addEventListener("click", () => { conflictBar.hidden = true; });
  installAutosave(engine, (state) => {
    if (state === "conflict") { if (conflictBar.hidden) conflictBar.hidden = false; return; }
    if (state === "saving") { const label = text("Saving"); if (saved.textContent !== label) saved.textContent = label; }
  });
  title.addEventListener("click", () => {
    titleInput.value = engine.snapshot.title;
    title.hidden = true;
    titleInput.hidden = false;
    titleInput.focus();
    titleInput.select();
  });
  const closeRename = (commit: boolean) => {
    if (titleInput.hidden) return;
    if (commit) engine.dispatch("project.rename", titleInput.value);
    titleInput.hidden = true;
    title.hidden = false;
  };
  titleInput.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter") closeRename(true);
    if (ev.key === "Escape") closeRename(false);
  });
  titleInput.addEventListener("blur", () => closeRename(true));

  const toastRoot = document.createElement("div");
  toastRoot.className = "toast-root";
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.hidden = true;
  toastRoot.append(toast);
  document.body.append(toastRoot);
  const showToast = (text: string) => {
    if (toast.textContent !== text) toast.textContent = text;
    if (toast.hidden) toast.hidden = false;
  };
  let hideTimer = 0;
  const hideToastSoon = (ms: number) => {
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(() => {
      toast.hidden = true;
    }, ms);
  };

  const fileBtn = el.querySelector<HTMLElement>('[data-ref="file"]')!;
  const menu = document.createElement("div");
  menu.className = "dropdown";
  menu.hidden = true;
  document.body.append(menu);
  // The logo is the way back to the start screen.
  el.querySelector('[data-ref="home"]')!.addEventListener("click", () => {
    document.dispatchEvent(new CustomEvent("formcut:home"));
  });

  const doSave = async () => {
    const result = await saveProject(engine);
    showToast(result ? t("toast.saved") : t("toast.savefail"));
    hideToastSoon(2500);
  };
  if (actions) {
    actions.save = () => void doSave();
    actions.newProject = () => {
      newProject(engine, undefined, activeProfile().behaviour.magneticMain);
      showToast(t("toast.new"));
      hideToastSoon(2000);
    };
  }

  const fillMenu = async () => {
    const projects = await listProjects();
    fileMenu(menu, projects);
  };

  fileBtn.addEventListener("click", async (ev) => {
    ev.stopPropagation();
    if (!menu.hidden) {
      menu.hidden = true;
      return;
    }
    await fillMenu();
    const rect = fileBtn.getBoundingClientRect();
    menu.style.left = `${rect.left}px`;
    menu.style.top = `${rect.bottom + 4}px`;
    menu.hidden = false;
  });
  window.addEventListener("pointerdown", (ev) => {
    if (!menu.hidden && !menu.contains(ev.target as Node) && ev.target !== fileBtn) {
      menu.hidden = true;
    }
  });
  menu.addEventListener("click", async (ev) => {
    const hit = (ev.target as HTMLElement).closest<HTMLElement>(".dropdown-item");
    if (!hit) return;
    menu.hidden = true;
    if (hit.dataset.act === "new") {
      newProject(engine, undefined, activeProfile().behaviour.magneticMain);
      showToast(t("toast.new"));
      hideToastSoon(2000);
    } else if (hit.dataset.act === "save") {
      await doSave();
    } else if (hit.dataset.open) {
      const ok = await openProject(engine, hit.dataset.open);
      showToast(ok ? "Project opened" : "Open failed");
      hideToastSoon(2500);
    }
  });
  window.addEventListener("keydown", (ev) => {
    const target = ev.target as HTMLElement;
    if (target.tagName === "INPUT" || target.tagName === "TEXTAREA") return;
    if ((ev.metaKey || ev.ctrlKey) && ev.key.toLowerCase() === "s") {
      ev.preventDefault();
      void doSave();
    }
  });

  const exportBtn = el.querySelector<HTMLButtonElement>('[data-ref="export"]')!;
  const modal = document.createElement("div");
  modal.className = "modal-scrim";
  modal.hidden = true;
  modal.innerHTML = `
    <div class="modal-panel">
      <div class="modal-title">${t("export.title")}</div>
      <div class="modal-row">
        <span>${t("export.format")}</span>
        <div class="seg" data-ref="fmt">
          <button class="is-active" data-val="mp4">MP4</button>
          <button data-val="webm">WebM</button>
        </div>
      </div>
      <div class="modal-row">
        <span>${t("export.quality")}</span>
        <div class="seg" data-ref="quality">
          <button class="is-active" data-val="high">High</button>
          <button data-val="medium">Medium</button>
          <button data-val="low">Low</button>
        </div>
      </div>
      <div class="modal-row" data-ref="codec-row">
        <span>${t("export.codec")}</span>
        <div class="seg" data-ref="codec"><button class="is-active" data-val="">${t("export.codec.auto")}</button></div>
      </div>
      <div class="modal-row">
        <span>${t("export.size")}</span>
        <div class="seg" data-ref="size">
          <button class="is-active" data-val="">${t("export.size.timeline")}</button>
          <button data-val="720p">720p</button><button data-val="1080p">1080p</button>
          <button data-val="1440p">1440p</button><button data-val="2160p">2160p</button>
        </div>
      </div>
      <div class="modal-row">
        <span>${t("export.tenbit")}</span>
        <button class="toggle" data-ref="tenbit" aria-label="10-bit"></button>
      </div>
      <div class="modal-row export-estimate" data-ref="estimate"></div>
      <div class="modal-actions">
        <button class="tool-chip" data-ref="post" hidden>${icon("export")}${t("tiktok.lastExport")}</button>
        <button class="tool-chip" data-ref="post-ig" hidden>${icon("pip")}${t("instagram.lastExport")}</button>
        <button class="tool-chip" data-ref="cancel">${t("export.cancel")}</button>
        <button class="btn-export" data-ref="start">${icon("export")}${t("export.start")}</button>
      </div>
    </div>`;
  document.body.append(modal);
  const segValue = (ref: string): string =>
    modal.querySelector<HTMLElement>(`[data-ref="${ref}"] .is-active`)?.dataset.val ?? "";
  // X5: fill the codec choices this machine can actually encode, and keep a
  // live size estimate under the options as they change.
  const estimateRow = modal.querySelector<HTMLElement>('[data-ref="estimate"]')!;
  const codecSeg = modal.querySelector<HTMLElement>('[data-ref="codec"]')!;
  let available: Record<string, string[]> = {};
  void fetch("/api/render/status").then((r) => r.json()).then((status) => {
    available = status.encoders?.containers ?? {};
    paintCodecs();
    void refreshEstimate();
  }).catch(() => {});
  const paintCodecs = () => {
    const format = segValue("fmt");
    const list = available[format] ?? [];
    codecSeg.innerHTML = `<button class="is-active" data-val="">${t("export.codec.auto")}</button>` +
      list.map((codec) => `<button data-val="${codec}">${codec.toUpperCase()}</button>`).join("");
  };
  const refreshEstimate = async () => {
    // An empty project has nothing to estimate and the engine rightly refuses
    // to validate it, so asking would only log a 422 the person cannot act on.
    const hasClips = engine.snapshot.timelines.some((timeline) =>
      timeline.tracks.some((track) => track.clips.length > 0));
    if (!hasClips) { estimateRow.textContent = ""; return; }
    try {
      const body = {
        project: structuredClone(engine.snapshot),
        format: segValue("fmt"),
        quality: segValue("quality"),
        codec: segValue("codec") || null,
        size: segValue("size") || null,
      };
      const reply = await api("/api/render/estimate", body);
      const bytes = reply.tiers[segValue("quality")].bytes as number;
      const mb = bytes / (1024 * 1024);
      estimateRow.textContent = `${t("export.estimate")}: ${mb < 1 ? `${Math.round(bytes / 1024)} kB` : `${mb.toFixed(1)} MB`} · ${reply.width}x${reply.height}`;
    } catch {
      estimateRow.textContent = "";
    }
  };
  modal.querySelector('[data-ref="tenbit"]')?.addEventListener("click", (ev) => {
    (ev.currentTarget as HTMLElement).classList.toggle("is-on");
  });
  modal.addEventListener("click", (ev) => {
    if (!(ev.target as HTMLElement).closest(".seg, [data-ref=tenbit]")) return;
    if ((ev.target as HTMLElement).closest('[data-ref="fmt"]')) paintCodecs();
    void refreshEstimate();
  });

  for (const seg of modal.querySelectorAll<HTMLElement>(".seg")) {
    seg.addEventListener("click", (ev) => {
      const hit = (ev.target as HTMLElement).closest("button");
      if (!hit || !seg.contains(hit)) return;
      seg.querySelector(".is-active")?.classList.remove("is-active");
      hit.classList.add("is-active");
    });
  }
  modal.querySelector('[data-ref="cancel"]')!.addEventListener("click", () => {
    modal.hidden = true;
  });
  modal.addEventListener("pointerdown", (ev) => {
    if (ev.target === modal) modal.hidden = true;
  });

  let exporting = false;
  let exportController: AbortController;
  const cancelExport = document.createElement("button");
  cancelExport.className = "tool-chip export-cancel";
  cancelExport.textContent = t("export.cancel");
  cancelExport.hidden = true;
  cancelExport.addEventListener("click", () => exportController.abort());
  toastRoot.append(cancelExport);
  exportBtn.addEventListener("click", () => {
    if (exporting) return;
    const state = engine.snapshot;
    const hasClips = state.timelines[state.activeTimeline].tracks.some((track) =>
      track.clips.some((c) => c.mediaId || c.kind === "text"),
    );
    if (!hasClips) {
      showToast("Nothing to export: add media clips first");
      hideToastSoon(3000);
      return;
    }
    modal.hidden = false;
    // The estimate must reflect the project as it is when the sheet opens, not
    // as it was when the sheet was built.
    void refreshEstimate();
  });
  let lastExport: { jobId: string; name: string } | null = null;
  const postLast = modal.querySelector<HTMLButtonElement>('[data-ref="post"]')!;
  postLast.addEventListener("click", () => {
    if (!lastExport) return;
    modal.hidden = true;
    openTikTok(lastExport);
  });
  const postLastIg = modal.querySelector<HTMLButtonElement>('[data-ref="post-ig"]')!;
  postLastIg.addEventListener("click", () => {
    if (!lastExport) return;
    modal.hidden = true;
    openInstagram(lastExport);
  });
  modal.querySelector('[data-ref="start"]')!.addEventListener("click", async () => {
    if (exporting) return;
    modal.hidden = true;
    const format = segValue("fmt");
    const quality = segValue("quality");
    const state = engine.snapshot;
    exporting = true;
    exportController = new AbortController();
    cancelExport.hidden = false;
    showToast("Exporting 0%");
    try {
      const jobId = await exportProject(state, format, quality, showToast, exportController.signal, {
        codec: segValue("codec") || null,
        tenBit: modal.querySelector('[data-ref="tenbit"]')!.classList.contains("is-on"),
        size: segValue("size") || null,
      });
      showToast("Export complete");
      lastExport = { jobId, name: `formcut-export.${format}` };
      if (postLast.hidden) postLast.hidden = false;
      if (postLastIg.hidden) postLastIg.hidden = false;
    } catch (error) {
      showToast(error instanceof Error ? error.message : "Export failed");
    } finally {
      exporting = false;
      cancelExport.hidden = true;
      hideToastSoon(5000);
    }
  });
  return el;
}
