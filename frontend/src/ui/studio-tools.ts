import { localizeElement } from "../i18n/text";
import { t } from "../i18n";
import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { api, waitJob } from "../engine/api";
import { buildCreatorPanel } from "./creator-panel";

export function installStudioTools(engine: ProjectEngine, bin: MediaBin): void {
  const inspector = buildCreatorPanel(engine);
  document.querySelector(".inspector-body")!.append(inspector);
  const opener = document.createElement("button"); opener.className = "tool-chip"; opener.textContent = "Studio";
  document.querySelector(".titlebar-right")!.prepend(opener);
  const modal = document.createElement("div"); modal.className = "modal-scrim studio-modal"; modal.hidden = true;
  modal.innerHTML = `<div class="studio-panel" role="dialog" aria-modal="true" aria-label="Studio tools"><div class="studio-heading"><strong>Studio</strong><button class="tool-chip" data-close>Close</button></div>
    <nav><button class="tool-chip" data-page="project">Project</button><button class="tool-chip" data-page="templates">Timeline templates</button><button class="tool-chip" data-page="speech">Local speech</button><button class="tool-chip" data-page="models">Local models</button></nav>
    <div class="studio-content">
    <section data-view="project"><h3>Project settings</h3><label>Width <input data-width type="number" min="16" max="7680"></label><label>Height <input data-height type="number" min="16" max="7680"></label><label>Frame rate <input data-fps type="number" min="1" max="120"></label><button class="tool-chip" data-settings>Apply settings</button><h3>Timeline structure</h3><label>Name <input data-structure-name value="New track"></label><button class="tool-chip" data-track-add>Add track</button><button class="tool-chip" data-timeline-add>Add timeline</button><label>Active timeline <select data-timeline></select></label><button class="tool-chip" data-timeline-remove>Remove active timeline</button><p>All settings and structure changes support Undo.</p></section>
    <section data-view="templates" hidden><h3>Reusable timeline templates</h3><label>Name <input data-template-name placeholder="Template name"></label><button class="tool-chip" data-template-save>Save current project as template</button><label>Import template <input type="file" accept=".fctemplate,.json" data-template-import></label><div data-template-list></div><div data-template-fill hidden><h3>Fill media slots</h3><div data-template-slots></div><label>New project title <input data-template-title value="Untitled from template"></label><label><input type="checkbox" data-template-fit checked> Fit replacement duration to each slot</label><button class="tool-chip" data-template-create>Create project</button></div></section>
    <section data-view="speech" hidden><h3>Local speech</h3><textarea data-speech-text rows="6" placeholder="Text to speak"></textarea><label>Voice <select data-speech-voice></select></label><label>Language <select data-speech-language><option value="en-us">English (US)</option><option value="en-gb">English (UK)</option><option value="es">Español</option><option value="fr-fr">Français</option><option value="it">Italiano</option><option value="pt-br">Português</option><option value="ja">日本語</option><option value="cmn">中文</option></select></label><label>Speed <input data-speech-speed type="number" min="0.5" max="2" step="0.1" value="1"></label><button class="tool-chip" data-speech-create>Generate and add to timeline</button><p>Install the local speech runtime once with backend/setup_local_ai.py. Download Kokoro under Local models. Synthesis then runs offline.</p></section>
    <section data-view="models" hidden><h3>Local models</h3><p>Download once, then process media locally. You can also import model files acquired separately.</p><div data-model-list></div></section>
    </div><div class="studio-footer"><span role="status" data-status></span><button class="tool-chip" data-cancel hidden>Cancel job</button></div></div>`;
  localizeElement(modal);
  document.body.append(modal);
  const q = <T extends HTMLElement = HTMLInputElement>(name: string) => modal.querySelector<T>(`[data-${name}]`)!;
  let activePage = "project", template: any, controller: AbortController | undefined;
  const say = (text: string) => { if (q("status").textContent !== text) q("status").textContent = text; };
  const run = async (work: () => unknown) => { try { await work(); } catch (error) { say(error instanceof Error ? error.message : String(error)); } };
  const job = async (path: string, data?: unknown) => {
    if (controller) throw new Error("Wait for the current job or cancel it");
    controller = new AbortController(); q("cancel").hidden = false;
    try {
      const started = await api(path, data ?? {});
      return await waitJob(started.job_id, say, controller.signal);
    } finally { q("cancel").hidden = true; controller = undefined; }
  };
  q("cancel").addEventListener("click", () => controller?.abort());
  const reconcileOptions = (select: HTMLSelectElement, entries: Array<{ id: string; name: string }>) => {
    const values = new Set(entries.map(e => e.id));
    for (const option of [...select.options]) if (!values.has(option.value)) option.remove();
    for (const entry of entries) {
      let option = [...select.options].find(o => o.value === entry.id);
      if (!option) { option = document.createElement("option"); option.value = entry.id; select.append(option); }
      if (option.textContent !== entry.name) option.textContent = entry.name;
    }
  };
  const structure = () => {
    const s = engine.snapshot;
    for (const key of ["width", "height", "fps"] as const) if (document.activeElement !== q(key)) q(key).value = String(s[key]);
    reconcileOptions(q<HTMLSelectElement>("timeline"), s.timelines.map((t, i) => ({ id: String(i), name: t.name })));
    q<HTMLSelectElement>("timeline").value = String(s.activeTimeline);
  };
  const templateRows = new Map<string, HTMLElement>();
  const refreshTemplates = async () => {
    const entries = await api<any[]>("/api/templates");
    for (const [id, row] of templateRows) if (!entries.some(e => e.id === id)) { row.remove(); templateRows.delete(id); }
    for (const entry of entries) {
      let row = templateRows.get(entry.id);
      if (!row) {
        row = document.createElement("div"); row.className = "studio-item";
        const label = document.createElement("span"); row.append(label);
        const fill = document.createElement("button"); fill.className = "tool-chip"; fill.textContent = "Fill slots";
        fill.addEventListener("click", () => void run(async () => {
          template = await api(`/api/templates/${entry.id}`);
          const root = q<HTMLElement>("template-slots");
          const live = new Set(template.slots.map((s: any) => s.id));
          for (const item of root.querySelectorAll<HTMLElement>("[data-slot]")) if (!live.has(item.dataset.slot)) item.remove();
          for (const slot of template.slots) {
            let label = [...root.querySelectorAll<HTMLLabelElement>("label")].find(l => l.dataset.slot === slot.id);
            if (!label) { label = document.createElement("label"); label.dataset.slot = slot.id; const name = document.createElement("span"); name.textContent = slot.name; label.append(name, document.createElement("select")); root.append(label); }
            reconcileOptions(label.querySelector("select")!, bin.all.filter(m => m.kind === slot.kind).map(m => ({ id: m.id, name: m.name })));
          }
          q("template-fill").hidden = false;
        }));
        const download = document.createElement("a"); download.className = "tool-chip"; download.textContent = "Export"; download.href = `/api/templates/${entry.id}/file`; download.download = "template.fctemplate";
        const remove = document.createElement("button"); remove.className = "tool-chip"; remove.textContent = "Delete"; remove.addEventListener("click", () => void run(async () => { await api(`/api/templates/${entry.id}`, undefined, "DELETE"); await refreshTemplates(); }));
        row.append(fill, download, remove); templateRows.set(entry.id, row); q("template-list").append(row);
      }
      row.querySelector("span")!.textContent = `${entry.name} · ${entry.slots.length} slots`;
    }
  };
  const modelRows = new Map<string, HTMLElement>();
  const refreshModels = async () => {
    const models = await api<any[]>("/api/models");
    for (const model of models) {
      let row = modelRows.get(model.id);
      if (!row) {
        row = document.createElement("div"); row.className = "studio-model";
        const name = document.createElement("strong"); name.textContent = model.name;
        const status = document.createElement("span"); status.dataset.ready = "";
        const download = document.createElement("button"); download.className = "tool-chip"; download.textContent = "Download";
        download.addEventListener("click", () => void run(async () => { await job(`/api/models/${model.id}/download`); await refreshModels(); say(model.id === "local-speech" ? t("models.readyspeech") : t("models.ready")); }));
        const files = document.createElement("span"); files.textContent = model.files.join(", ");
        const importer = document.createElement("input"); importer.type = "file"; importer.setAttribute("aria-label", `Import ${model.name}`);
        importer.addEventListener("change", () => void run(async () => { if (!importer.files?.[0]) return; const body = new FormData(); body.append("file", importer.files[0]); await api(`/api/models/${model.id}/import`, body); await refreshModels(); }));
        row.append(name, status, download, files, importer); modelRows.set(model.id, row); q("model-list").append(row);
        if (model.id === "local-speech") { const note = document.createElement("span"); note.className = "text-add-hint"; note.textContent = t("models.speechsetup"); row.append(note); }
      }
      row.querySelector<HTMLElement>("[data-ready]")!.textContent = model.ready ? "Ready offline" : "Not installed";
      row.querySelector("button")!.disabled = model.ready;
    }
  };
  const showPage = async () => {
    for (const section of modal.querySelectorAll<HTMLElement>("[data-view]")) section.hidden = section.dataset.view !== activePage;
    if (activePage === "project") structure();
    if (activePage === "templates") await refreshTemplates();
    if (activePage === "models") await refreshModels();
    if (activePage === "speech") {
      const voices = await api("/api/speech/voices"); reconcileOptions(q<HTMLSelectElement>("speech-voice"), voices.voices);
      if (!voices.ready) say(t("speech.needmodel"));
      else if (!voices.runtime) say(t("speech.needsetup"));
    }
  };
  opener.addEventListener("click", () => { modal.hidden = false; void run(showPage); q("close").focus(); });
  q("close").addEventListener("click", () => { modal.hidden = true; opener.focus(); });
  modal.addEventListener("keydown", event => { if (event.key === "Escape") { modal.hidden = true; opener.focus(); } });
  for (const button of modal.querySelectorAll<HTMLElement>("[data-page]")) button.addEventListener("click", () => { activePage = button.dataset.page!; say(""); void run(showPage); });
  q("settings").addEventListener("click", () => void run(() => { engine.dispatch("project.settings", { width: Number(q("width").value), height: Number(q("height").value), fps: Number(q("fps").value) }); say("Settings updated"); }));
  q("track-add").addEventListener("click", () => void run(() => { engine.dispatch("track.add", { name: q("structure-name").value }); say("Track added"); }));
  q("timeline-add").addEventListener("click", () => void run(() => { engine.dispatch("timeline.add", { name: q("structure-name").value }); structure(); }));
  q("timeline").addEventListener("change", () => engine.dispatch("timeline.activate", Number(q<HTMLSelectElement>("timeline").value)));
  q("timeline-remove").addEventListener("click", () => void run(() => { engine.dispatch("timeline.remove", { index: engine.snapshot.activeTimeline }); structure(); }));
  q("template-save").addEventListener("click", () => void run(async () => { await api("/api/templates", { name: q("template-name").value, project: engine.snapshot }); await refreshTemplates(); say("Template saved"); }));
  q("template-import").addEventListener("change", () => void run(async () => { const file = q("template-import").files?.[0]; if (!file) return; const body = new FormData(); body.append("file", file); await api("/api/templates/import", body); await refreshTemplates(); say("Template imported"); }));
  q("template-create").addEventListener("click", () => void run(async () => {
    const bindings = Object.fromEntries([...q("template-slots").querySelectorAll<HTMLElement>("[data-slot]")].map(row => [row.dataset.slot, row.querySelector("select")!.value]));
    const project = await api(`/api/templates/${template.id}/fill`, { bindings, title: q("template-title").value, fit: q("template-fit").checked });
    engine.dispatch("project.load", project); modal.hidden = true;
  }));
  q("speech-create").addEventListener("click", () => void run(async () => {
    const start = engine.snapshot.playhead;
    const timelineId = engine.snapshot.timelines[engine.snapshot.activeTimeline].id;
    const result = await job("/api/speech", { text: q<HTMLTextAreaElement>("speech-text").value, voice: q<HTMLSelectElement>("speech-voice").value, language: q<HTMLSelectElement>("speech-language").value, speed: Number(q("speech-speed").value) });
    await bin.load();
    if (engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timelineId) { say("Speech saved in Media; the active timeline changed"); return; }
    const tracks = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks;
    const trackIndex = Math.max(0, tracks.findIndex(t => /audio/i.test(t.name)));
    engine.dispatch("clip.add", { trackIndex, clip: { id: crypto.randomUUID(), kind: "audio", label: result.media.name, mediaId: result.media.id, start, duration: result.media.duration } });
    say("Speech added to the timeline");
  }));
  document.addEventListener("pointerdown", event => {
    const canvas = (event.target as HTMLElement).closest<HTMLCanvasElement>(".render-canvas");
    const mode = inspector.dataset.brush;
    const clip = engine.snapshot.selectedClipId ? engine.findClip(engine.snapshot.selectedClipId)?.clip : undefined;
    if (!canvas || (mode !== "keep" && mode !== "erase") || !clip?.cutout) return;
    engine.pause();
    const project = structuredClone(engine.snapshot), timelineId = project.timelines[project.activeTimeline].id;
    const radius = Number(inspector.querySelector<HTMLInputElement>("[data-brush-radius]")!.value);
    canvas.setPointerCapture(event.pointerId);
    const points: number[][] = [];
    const move = (ev: PointerEvent) => { const box = canvas.getBoundingClientRect(); if (points.length < 4096) points.push([(ev.clientX - box.left) / box.width, (ev.clientY - box.top) / box.height]); };
    const cleanup = () => { canvas.removeEventListener("pointermove", move); canvas.removeEventListener("pointerup", end); canvas.removeEventListener("pointercancel", cleanup); };
    const end = () => {
      cleanup();
      void run(async () => {
        const result = await api("/api/render/brush", { project, clipId: clip.id, time: project.playhead, points });
        const current = engine.findClip(clip.id)?.clip;
        if (!current?.cutout || current.mediaId !== clip.mediaId || engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timelineId) throw new Error("The brush target changed.");
        engine.dispatch("clip.creator", { clipId: clip.id, patch: { cutout: { ...current.cutout, strokes: [...current.cutout.strokes, { mode, radius, points: result.points }] } } });
      });
    };
    move(event);
    canvas.addEventListener("pointermove", move); canvas.addEventListener("pointerup", end, { once: true }); canvas.addEventListener("pointercancel", cleanup, { once: true });
  });
}
