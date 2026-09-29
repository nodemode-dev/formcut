import { fileMenu } from "./file-menu";
import { text } from "../i18n/text";
import { escapeHtml } from "./safe-text";
import type { ProjectEngine } from "../engine/project";
import { listProjects, newProject, openProject, saveProject, installAutosave } from "../engine/persistence";
import { exportProject } from "./export-job";
import { api } from "../engine/api";
import { icon } from "./icons";
import { showMissingMedia, type MissingItem } from "./missing-media";
import { t } from "../i18n";
import { buildModePanel } from "./mode-popout";
import { openTikTok } from "./tiktok-dialog";
import { openInstagram } from "./instagram";
import { openCloudUpload } from "./cloud";
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

  // Save as project file: the project written to a .fmc of the person's choosing; every save after follows it there
  const saveAs = async () => {
    try {
      const saved = await saveProject(engine);
      if (!saved) { showToast(t("toast.savefail")); hideToastSoon(2500); return; }
      const chosen = await api<{ paths: string[] }>("/api/system/choose", { kind: "save", title: t("file.saveAs"), defaultName: `${saved.title || "Untitled"}.fmc` });
      if (!chosen.paths.length) return;
      const written = await api<{ path: string }>("/api/project-files/save", { projectId: saved.id, path: chosen.paths[0] });
      showToast(`${t("file.savedTo")} ${written.path}`);
    } catch (error) {
      showToast(error instanceof Error ? error.message : t("toast.savefail"));
    }
    hideToastSoon(4000);
  };
  const waitCollect = async (jobId: string) => {
    for (;;) {
      const status = await fetch(`/api/jobs/${jobId}`).then((r) => r.json());
      if (status.status === "done") return status.result as { path: string; folder: string; files: number; missing: string[] };
      if (status.status !== "running") throw new Error(status.error ?? status.status);
      await new Promise((resolve) => setTimeout(resolve, 500));
    }
  };
  // Save: to the store and, for a project kept in a .fmc, its file (the engine writes it); a project not yet in a file
  // is offered Save as once, as After Effects asks where an unsaved project goes
  const offered = new Set<string>();
  const doSave = async (fromKeys = false) => {
    const result = await saveProject(engine);
    if (result && fromKeys && !offered.has(result.id)) {
      offered.add(result.id);
      const kept = await fetch(`/api/project-files/of/${result.id}`).then((r) => r.json()).catch(() => ({ path: "unknown" }));
      if (!kept.path) {
        const dialogs = await fetch("/api/system/dialogs").then((r) => r.json()).catch(() => ({ available: false }));
        if (dialogs.available) { await saveAs(); return; }
      }
    }
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
  // Escape closes it, as it closes Edit and View, and focus returns to File.
  window.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && !menu.hidden) {
      menu.hidden = true;
      fileBtn.focus();
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
    } else if (hit.dataset.act === "save-as") {
      await saveAs();
    } else if (hit.dataset.act === "collect") {
      // Collect Files: a folder with the project file and a copy of all its footage, to move or hand over whole
      try {
        const saved = await saveProject(engine);
        if (!saved) { showToast(t("toast.savefail")); hideToastSoon(2500); return; }
        const chosen = await api<{ paths: string[] }>("/api/system/choose", { kind: "folder", title: t("file.collect") });
        if (!chosen.paths.length) return;
        showToast(t("file.collecting"));
        const started = await api<{ job_id: string }>("/api/project-files/collect", { projectId: saved.id, folder: chosen.paths[0] });
        const done = await waitCollect(started.job_id);
        showToast(`${t("file.collected")} ${done.folder}${done.missing.length ? ` (${done.missing.join(", ")}: ${t("missing.title").toLowerCase()})` : ""}`);
        void api("/api/project-files/reveal", { path: done.path });
      } catch (error) {
        showToast(error instanceof Error ? error.message : String(error));
      }
      hideToastSoon(5000);
    } else if (hit.dataset.act === "open-file") {
      // a .fmc file: its project into the editor, its media linked back where found, the rest offered to Locate
      try {
        const chosen = await api<{ paths: string[] }>("/api/system/choose", { kind: "open", title: t("file.openFile"), types: ["fmc"] });
        if (!chosen.paths.length) return;
        const opened = await api<{ project: { id: string }; missing: MissingItem[] }>("/api/project-files/open", { path: chosen.paths[0] });
        const ok = await openProject(engine, opened.project.id);
        showToast(ok ? t("file.opened") : "Open failed");
        hideToastSoon(2500);
        if (opened.missing.length) showMissingMedia(opened.missing, () => void openProject(engine, opened.project.id));
      } catch (error) {
        showToast(error instanceof Error ? error.message : "Open failed");
        hideToastSoon(4000);
      }
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
      void (ev.shiftKey ? saveAs() : doSave(true));  // Shift: Save as project file
    }
  });

  const exportBtn = el.querySelector<HTMLButtonElement>('[data-ref="export"]')!;
  const modal = document.createElement("div");
  modal.className = "modal-scrim";
  modal.hidden = true;
  modal.innerHTML = `
    <div class="modal-panel export-panel">
      <div class="modal-title">${t("export.title")}</div>
      <div class="modal-row">
        <span>${t("export.format")}</span>
        <div class="seg" data-ref="fmt">
          <button class="is-active" data-val="mp4">MP4</button>
          <button data-val="webm">WebM</button>
          <button data-val="gif">GIF</button>
        </div>
      </div>
      <p class="modal-note" data-ref="h264-note" hidden></p>
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
      <div class="modal-row export-estimate export-encoder" data-ref="encoder" aria-live="polite"></div>
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
      <div class="modal-row">
        <span>${text("Output colour")}</span>
        <div class="seg" data-ref="colour">
          <button class="is-active" data-val="bt709">Rec.709</button>
          <button data-val="hlg">HLG</button>
          <button data-val="pq">PQ (HDR10)</button>
        </div>
      </div>
      <p class="modal-note" data-ref="hdr-note" hidden>${text("HLG and PQ export in ten bits with the BT.2020 transform applied on the way out; they need an encoder that carries ten bits (HEVC, AV1 or VP9), and a Rec.709 file is written otherwise.")}</p>
      <div class="modal-row">
        <span>${t("export.exact")}</span>
        <button class="toggle" data-ref="exact" aria-label="${t("export.exact")}"></button>
      </div>
      <div class="modal-row export-estimate" data-ref="estimate"></div>
      <div class="modal-actions export-actions">
        <div class="export-share">
          <button class="tool-chip" data-ref="post" hidden title="${t("tiktok.lastExport")}" aria-label="${t("tiktok.lastExport")}">${icon("export")}TikTok</button>
          <button class="tool-chip" data-ref="post-ig" hidden title="${t("instagram.lastExport")}" aria-label="${t("instagram.lastExport")}">${icon("pip")}Instagram</button>
          <button class="tool-chip" data-ref="save-cloud" hidden title="${t("cloud.lastExport")}" aria-label="${t("cloud.lastExport")}">${icon("grid")}${t("share.cloud")}</button>
        </div>
        <button class="tool-chip" data-ref="cancel">${t("export.cancel")}</button>
        <button class="btn-export" data-ref="start">${icon("export")}${t("export.start")}</button>
      </div>
    </div>`;
  document.body.append(modal);
  const segValue = (ref: string): string =>
    modal.querySelector<HTMLElement>(`[data-ref="${ref}"] .is-active`)?.dataset.val ?? "";
  // the HLG/PQ note only when HLG or PQ is chosen: it says what they need, which Rec.709 does not
  modal.querySelector('[data-ref="colour"]')!.addEventListener("click", () => requestAnimationFrame(() => {
    modal.querySelector<HTMLElement>('[data-ref="hdr-note"]')!.hidden = segValue("colour") === "bt709";
  }));
  // X5: fill the codec choices this machine can actually encode, and keep a
  // live size estimate under the options as they change.
  const estimateRow = modal.querySelector<HTMLElement>('[data-ref="estimate"]')!;
  const codecSeg = modal.querySelector<HTMLElement>('[data-ref="codec"]')!;
  let available: Record<string, string[]> = {};
  let encoders: Record<string, { encoder?: string | null; installed?: boolean }> = {};
  void fetch("/api/render/status").then((r) => r.json()).then((status) => {
    available = status.encoders?.containers ?? {};
    encoders = status.encoders?.codecs ?? {};
    paintCodecs();
    void refreshEstimate();
  }).catch(() => {});
  const CODEC_NAMES: Record<string, string> = { h264: "H.264", hevc: "HEVC", av1: "AV1", vp9: "VP9", mpeg4: "MPEG-4 Part 2" };
  const encoderRow = modal.querySelector<HTMLElement>('[data-ref="encoder"]')!;
  // What Auto, or the codec picked, will actually encode with; and a warning
  // when MP4 can only be MPEG-4 Part 2 here, which Instagram refuses.
  const paintEncoder = () => {
    const list = available[segValue("fmt")] ?? [];
    const codec = segValue("codec") || list[0] || "";
    const encoder = encoders[codec]?.encoder;
    // No MP4 encoder here: Auto saves WebM (render_api), and MPEG-4 Part 2 only
    // when picked by name, which is when its own warning applies.
    const noMp4 = segValue("fmt") === "mp4" && !list.some((name) => name === "h264" || name === "hevc" || name === "av1");
    const fallback = noMp4 && codec === "mpeg4";
    const fetchesFirst = encoder === "libopenh264" && encoders[codec]?.installed === false;
    const text = noMp4 && !segValue("codec") ? t("export.webmWarning") : !codec || !encoder ? "" : fallback ? t("export.mpeg4Warning")
      : fetchesFirst ? t("export.openh264First")
      : t("export.encoderUses").replace("{codec}", CODEC_NAMES[codec] ?? codec.toUpperCase()).replace("{encoder}", encoder);
    if (encoderRow.textContent !== text) encoderRow.textContent = text;
    encoderRow.classList.toggle("is-warning", fallback);
  };
  const paintCodecs = () => {
    const format = segValue("fmt");
    // A GIF has no codec or bit depth to choose: its rows hide rather than
    // offering an empty choice, and the encoder note stays quiet.
    const isGif = format === "gif";
    modal.querySelector<HTMLElement>('[data-ref="codec-row"]')!.hidden = isGif;
    modal.querySelector<HTMLElement>('[data-ref="tenbit"]')!.closest<HTMLElement>(".modal-row")!.hidden = isGif;
    const list = available[format] ?? [];
    codecSeg.innerHTML = `<button class="is-active" data-val="">${t("export.codec.auto")}</button>` +
      list.map((codec) => `<button data-val="${codec}">${CODEC_NAMES[codec] ?? codec.toUpperCase()}</button>`).join("");
    paintEncoder();
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
  modal.querySelector('[data-ref="exact"]')?.addEventListener("click", (ev) => {
    (ev.currentTarget as HTMLElement).classList.toggle("is-on");
  });
  modal.addEventListener("click", (ev) => {
    if (!(ev.target as HTMLElement).closest(".seg, [data-ref=tenbit]")) return;
    if ((ev.target as HTMLElement).closest('[data-ref="fmt"]')) paintCodecs();
    else if ((ev.target as HTMLElement).closest('[data-ref="codec"]')) paintEncoder();
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
    // The H.264 situation on the sheet, the first time and every time: a
    // computer with no H.264 encoder either downloads Cisco's OpenH264 once
    // (its licence in Settings) or exports WebM when MP4 was asked for.
    void (async () => {
      const note = modal.querySelector<HTMLElement>('[data-ref="h264-note"]')!;
      try {
        const codec = await (await fetch("/api/codecs/openh264")).json() as { needed: boolean; installed: boolean; enabled: boolean; supported: boolean };
        let line = "";
        if (codec.needed && !(codec.installed && codec.enabled)) {
          line = codec.supported
            ? text("This computer has no H.264 encoder. MP4 will download Cisco's OpenH264 once on the first export (its licence is in Settings, Advanced); otherwise the file comes out as WebM.")
            : text("This computer has no H.264 encoder and OpenH264 is not available for it: an MP4 export comes out as WebM.");
        } else if (codec.needed && codec.installed && codec.enabled) {
          line = text("MP4 encodes through Cisco's OpenH264 on this computer (its licence is in Settings, Advanced).");
        }
        if (note.textContent !== line) note.textContent = line;
        if (note.hidden !== !line) note.hidden = !line;
      } catch { /* the note is a courtesy */ }
    })();
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
  const saveLast = modal.querySelector<HTMLButtonElement>('[data-ref="save-cloud"]')!;
  saveLast.addEventListener("click", () => {
    if (!lastExport) return;
    modal.hidden = true;
    openCloudUpload(lastExport);
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
      const colour = (segValue("colour") || "bt709") as "bt709" | "hlg" | "pq";
      const done = await exportProject({ ...state, outputColour: colour }, format, quality, showToast, exportController.signal, {
        codec: segValue("codec") || null,
        tenBit: modal.querySelector('[data-ref="tenbit"]')!.classList.contains("is-on"),
        exact: modal.querySelector('[data-ref="exact"]')!.classList.contains("is-on"),
        size: segValue("size") || null,
      });
      showToast(done.result?.fellBackTo === "webm" ? t("export.webmFallback") : "Export complete");
      lastExport = { jobId: done.jobId, name: done.result?.name ?? `formcut-export.${format}` };
      // TikTok and Instagram post the last export as a video, which a GIF is
      // not; the cloud takes any file, so its button stays.
      const isGif = format === "gif";
      postLast.hidden = isGif;
      postLastIg.hidden = isGif;
      saveLast.hidden = false;
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
