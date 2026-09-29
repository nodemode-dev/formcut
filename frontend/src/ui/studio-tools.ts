import { localizeElement, text } from "../i18n/text";
import { t } from "../i18n";
import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import { api, waitJob } from "../engine/api";
import { escapeHtml } from "./safe-text";
import { buildCreatorPanel } from "./creator-panel";
import { buildRecording } from "./recorder";
import { icon } from "./icons";
import { reconcile } from "./keyed-list";

export function installStudioTools(engine: ProjectEngine, bin: MediaBin): void {
  const inspector = buildCreatorPanel(engine);
  document.querySelector(".inspector-body")!.append(inspector);
  // Studio belongs with File, Edit and View: it opens a window of its own, like
  // they do, rather than sitting among the view controls on the right.
  const opener = document.createElement("button");
  opener.className = "menu-item";
  opener.textContent = text("Studio");
  opener.dataset.feature = "titlebar.studio";
  document.querySelector(".titlebar-left")!.append(opener);
  const modal = document.createElement("div"); modal.className = "set-scrim studio-modal"; modal.hidden = true;
  const tab = (page: string, glyph: string, label: string, active = false) => `<button class="set-tab${active ? " is-active" : ""}" data-page="${page}">${icon(glyph)}<span>${label}</span></button>`;
  modal.innerHTML = `<div class="set-pair studio-pair">
    <nav class="set-rail studio-rail" aria-label="Studio" data-collapsed="false">
      <div class="set-rail-head"><strong>Studio</strong></div>
      <div class="set-tabs">${tab("project", "clapperboard", "Project", true)}${tab("stock", "image", t("stock.title"))}${tab("urldl", "download", t("urldl.title"))}${tab("genimage", "image", t("gen.image"))}${tab("genvideo", "video", t("gen.video"))}${tab("genaudio", "tone", t("gen.audio"))}${tab("recording", "mic", text("Recording"))}${tab("templates", "template", "Timeline templates")}${tab("localmedia", "image", t("local.title"))}${tab("speech", "mic", "Local speech")}${tab("models", "box", "Local models")}${tab("terminal", "terminal", text("Agent terminal"))}</div>
      <button class="set-collapse" data-rail-toggle title="${t("set.collapse")}">${icon("chevL")}</button>
    </nav>
    <section class="set-window studio-panel" role="dialog" aria-modal="true" aria-label="Studio tools">
    <header class="set-head"><strong data-page-title>Project</strong><span class="set-head-actions"><button class="iconbtn" data-full title="${text("Fullscreen")}" aria-label="${text("Fullscreen")}" aria-pressed="false">${icon("fullscreen")}</button><button class="iconbtn" data-close title="Close" aria-label="Close">${icon("close")}</button></span></header>
    <div class="set-body studio-content">
    <section data-view="project" class="set-view">
      <div class="panel-section"><div class="panel-section-head"><span>Project settings</span></div><div class="panel-rows"><label>Width <input data-width type="number" min="16" max="7680"></label><label>Height <input data-height type="number" min="16" max="7680"></label><label>Frame rate <input data-fps type="number" min="1" max="120"></label><div class="studio-actions"><button class="tool-chip is-primary" data-settings>Apply settings</button></div></div></div>
      <div class="panel-section"><div class="panel-section-head"><span>Timeline structure</span><small>All settings and structure changes support Undo.</small></div><div class="panel-rows"><label>Name <input data-structure-name value="New track"></label><label>Active timeline <select data-timeline></select></label><div class="studio-actions"><button class="tool-chip" data-track-add>${icon("addTrack")}Add track</button><button class="tool-chip" data-timeline-add>${icon("plus")}Add timeline</button><button class="tool-chip" data-timeline-remove>${icon("trash")}Remove active timeline</button></div></div></div>
    </section>
    ${["image", "video", "audio"].map((kind) => `
    <section data-view="gen${kind}" class="set-view" hidden>
      <div class="panel-section">
        <div class="panel-section-head"><span>${t(`gen.${kind}`)}</span><small data-gen-ready="${kind}"></small></div>
        <div class="panel-rows">
          <label>${t("gen.model")} <select data-gen-model="${kind}"></select></label>
          <label>${t("gen.prompt")} <textarea data-gen-prompt="${kind}" rows="3" placeholder="${t(`gen.${kind}.hint`)}"></textarea></label>
          <label>${t("gen.negative")} <input data-gen-negative="${kind}" placeholder="${t("gen.negative.hint")}"></label>
          <div class="stock-row">
            <label data-gen-size-row="${kind}">${t("gen.size")} <select data-gen-size="${kind}"></select></label>
            <label data-gen-seconds-row="${kind}" hidden>${t("gen.seconds")} <input data-gen-seconds="${kind}" type="number" min="1" max="22" value="5"></label>
            <label data-gen-count-row="${kind}">${t("gen.count")} <input data-gen-count="${kind}" type="number" min="1" max="4" value="1"></label>
            <label data-gen-sampler-row="${kind}" hidden>${t("gen.sampler")} <select data-gen-sampler="${kind}"><option value="er_sde">ER-SDE</option><option value="euler">Euler</option></select></label>
            <label data-gen-memory-row="${kind}" hidden>${t("gen.memory")} <select data-gen-memory="${kind}"><option value="auto">${t("gen.memory.auto")}</option><option value="low">${t("gen.memory.low")}</option><option value="normal">${t("gen.memory.normal")}</option></select></label>
          </div>
          <small class="stock-note" data-gen-civitai="${kind}" hidden>${t("gen.civitai.hint")}</small>
          <div class="lora-stack" data-gen-loras="${kind}" hidden>
            <div class="lora-head"><strong>${t("gen.loras")}</strong><button type="button" class="tool-chip" data-lora-add="${kind}">${icon("plus")}${t("gen.loras.add")}</button></div>
            <div class="lora-rows" data-lora-rows="${kind}"></div>
            <div class="lora-library">
              <label class="tool-chip">${t("gen.loras.import")}<input type="file" accept=".safetensors" data-lora-file="${kind}" hidden></label>
              <input data-lora-url="${kind}" placeholder="https://huggingface.co/…/resolve/…/….safetensors · https://civitai.com/models/…" aria-label="${t("gen.loras.fetch")}">
              <button type="button" class="tool-chip" data-lora-fetch="${kind}">${t("gen.loras.fetch")}</button>
            </div>
            <small class="lora-folder"><span>${t("gen.loras.folder")}</span> <code data-lora-folder="${kind}"></code> <button type="button" class="tool-chip" data-lora-rescan="${kind}">${t("gen.loras.rescan")}</button></small>
          </div>
          <div class="studio-actions">
            <button class="tool-chip is-primary" data-gen-go="${kind}">${icon("diamond")}${t("gen.go")}</button>
            <button class="tool-chip" data-gen-cancel="${kind}" hidden>${t("cap.cancel")}</button>
          </div>
          <div class="gen-progress" data-gen-progress="${kind}" hidden><progress data-gen-bar="${kind}" max="1" value="0"></progress><small data-gen-stage="${kind}"></small></div>
          <p class="stock-note" data-gen-note="${kind}"></p>
        </div>
      </div>
      <div class="panel-section"><div class="panel-section-head"><span>${t("gen.results")}</span><small>${t("gen.results.hint")}</small></div>
        <div class="card-grid stock-grid" data-gen-grid="${kind}"></div></div>
    </section>`).join("")}
    <section data-view="recording" class="set-view" hidden></section>
    <section data-view="urldl" class="set-view" hidden>
      <div class="panel-section">
        <div class="panel-section-head"><span>${t("urldl.title")}</span><small>${t("urldl.hint")}</small></div>
        <div class="panel-rows">
          <div class="stock-row"><input data-stock-url type="url" placeholder="${t("urldl.placeholder")}" aria-label="${t("urldl.title")}"><button class="tool-chip is-primary" data-stock-url-go>${icon("download")}${t("stock.urlgo")}</button></div>
          <label>${t("urldl.quality")} <select data-url-quality><option value="best">${t("urldl.best")}</option><option value="1080">1080p</option><option value="720">720p</option><option value="audio">${t("urldl.audioonly")}</option></select></label>
          <p class="stock-note" data-stock-url-note></p>
        </div>
      </div>
    </section>
    <section data-view="localmedia" class="set-view" hidden>
      <div class="panel-section">
        <div class="panel-section-head"><span>${t("local.title")}</span><small>${t("local.inlibrary")}</small></div>
        <div class="panel-rows">
          <div class="stock-row">
            <div class="seg local-kinds" data-ref="local-kinds">
              <button class="is-active" data-kind="all">${t("local.all")}</button>
              <button data-kind="video">${t("local.video")}</button>
              <button data-kind="image">${t("local.image")}</button>
              <button data-kind="audio">${t("local.audio")}</button>
            </div>
            <input data-ref="local-search" type="search" placeholder="${t("local.search")}" aria-label="${t("local.search")}">
            <label>${t("local.sort")} <select data-ref="local-sort">
              <option value="added">${t("local.added")}</option>
              <option value="name">${t("local.name")}</option>
              <option value="duration">${t("local.duration")}</option>
            </select></label>
          </div>
          <p class="stock-note" data-ref="local-note"></p>
        </div>
      </div>
      <div class="panel-section">
        <div class="panel-section-head"><span data-ref="local-count"></span><small>${t("local.place.hint")}</small></div>
        <div class="local-grid" data-ref="local-grid"></div>
      </div>
      <div class="place-sheet" data-ref="place-sheet" hidden>
        <div class="place-card">
          <strong data-ref="place-name"></strong>
          <p>${t("local.place.where")}</p>
          <div class="place-rows" data-ref="place-tracks"></div>
          <label class="place-at">${t("local.place.at")}
            <select data-ref="place-at">
              <option value="playhead">${t("local.place.playhead")}</option>
              <option value="end">${t("local.place.end")}</option>
              <option value="start">${t("local.place.start")}</option>
            </select>
          </label>
          <div class="studio-actions">
            <button class="tool-chip is-primary" data-ref="place-go">${t("local.place.add")}</button>
            <button class="tool-chip" data-ref="place-cancel">${t("cap.cancel")}</button>
          </div>
        </div>
      </div>
    </section>
    <section data-view="stock" class="set-view" hidden>
      <div class="panel-section"><div class="panel-section-head"><span>Pexels</span><small><a class="stock-attrib" href="https://www.pexels.com" target="_blank" rel="noreferrer">Photos and videos provided by Pexels</a></small></div><div class="panel-rows">
        <div class="stock-row"><div class="seg" data-stock-kind><button class="is-active" data-val="video">${icon("video")}${t("stock.video")}</button><button data-val="photo">${icon("image")}${t("stock.photos")}</button></div><input data-stock-q type="search" placeholder="Search Pexels" aria-label="Search Pexels"><button class="tool-chip is-primary" data-stock-go>${icon("search")}${t("stock.search")}</button></div>
        <div class="stock-row stock-filters"><label>Orientation <select data-stock-orientation><option value="">Any</option><option value="landscape">Landscape</option><option value="portrait">Portrait</option><option value="square">Square</option></select></label><label>Size <select data-stock-size><option value="">Any</option><option value="large">Large</option><option value="medium">Medium</option><option value="small">Small</option></select></label><label data-stock-color-row>Colour <select data-stock-color><option value="">Any</option><option value="red">Red</option><option value="orange">Orange</option><option value="yellow">Yellow</option><option value="green">Green</option><option value="turquoise">Turquoise</option><option value="blue">Blue</option><option value="violet">Violet</option><option value="pink">Pink</option><option value="brown">Brown</option><option value="black">Black</option><option value="gray">Gray</option><option value="white">White</option></select></label></div>
        <p class="stock-note" data-stock-note></p>
      </div></div>

      <div class="panel-section stock-results"><div class="panel-section-head"><span>Results</span><small data-stock-page></small></div><div class="card-grid stock-grid" data-stock-grid></div><div class="stock-row stock-pager"><button class="tool-chip" data-stock-prev disabled>${icon("chevL")}${t("stock.prev")}</button><button class="tool-chip" data-stock-next disabled>${t("stock.next")}${icon("chevR")}</button></div></div>
      <div class="panel-section"><div class="panel-section-head"><span>Openverse</span><small><a class="stock-attrib" href="https://openverse.org" target="_blank" rel="noreferrer">${text("Openly licensed sounds, music and images; each carries its own licence and creator")}</a></small></div><div class="panel-rows">
        <div class="stock-row"><div class="seg" data-ov-kind><button class="is-active" data-val="audio">${icon("speaker")}${text("Sounds and music")}</button><button data-val="image">${icon("image")}${t("stock.photos")}</button></div><input data-ov-q type="search" placeholder="${text("Search Openverse")}" aria-label="${text("Search Openverse")}"><button class="tool-chip is-primary" data-ov-go>${icon("search")}${t("stock.search")}</button></div>
        <p class="stock-note" data-ov-note></p>
      </div></div>
      <div class="panel-section stock-results"><div class="panel-section-head"><span>${text("Openverse results")}</span><small data-ov-page></small></div><div class="card-grid stock-grid" data-ov-grid></div><div class="stock-row stock-pager"><button class="tool-chip" data-ov-prev disabled>${icon("chevL")}${t("stock.prev")}</button><button class="tool-chip" data-ov-next disabled>${t("stock.next")}${icon("chevR")}</button></div></div>
    </section>
    <section data-view="templates" class="set-view" hidden>
      <div class="panel-section"><div class="panel-section-head"><span>Reusable timeline templates</span></div><div class="panel-rows"><label>Name <input data-template-name placeholder="Template name"></label><label>Import template <input type="file" accept=".fctemplate,.json" data-template-import></label><div class="studio-actions"><button class="tool-chip is-primary" data-template-save>${icon("download")}Save current project as template</button></div><div data-template-list></div></div></div>
      <div class="panel-section" data-template-fill hidden><div class="panel-section-head"><span>Fill media slots</span></div><div class="panel-rows"><div data-template-slots></div><label>New project title <input data-template-title value="Untitled from template"></label><label><input type="checkbox" data-template-fit checked> Fit replacement duration to each slot</label><div class="studio-actions"><button class="tool-chip is-primary" data-template-create>Create project</button></div></div></div>
    </section>
    <section data-view="speech" class="set-view" hidden>
      <div class="panel-section"><div class="panel-section-head"><span>Local speech</span><small>Install the local speech runtime once with backend/setup_local_ai.py. Download Kokoro under Local models. Synthesis then runs offline.</small></div><div class="panel-rows"><textarea data-speech-text rows="6" placeholder="Text to speak"></textarea><label>Engine <select data-speech-engine><option value="kokoro">Kokoro</option><option value="pocket">Pocket TTS</option><option value="chatterbox">Chatterbox</option></select></label><small data-speech-engine-note></small><button class="tool-chip" type="button" data-speech-install hidden>Install</button><label>Voice <select data-speech-voice></select></label><label data-speech-clone hidden>Clone a voice from <select data-speech-reference><option value="">None</option></select></label><label data-speech-consent-row hidden><input type="checkbox" data-speech-consent> I have the speaker's permission</label><label data-speech-expression-row hidden>Expression <input data-speech-exaggeration type="range" min="0.25" max="1.5" step="0.05" value="0.5"></label><label>Language <select data-speech-language><option value="en-us">English (US)</option><option value="en-gb">English (UK)</option><option value="es">Español</option><option value="fr-fr">Français</option><option value="it">Italiano</option><option value="pt-br">Português</option><option value="ja">日本語</option><option value="cmn">中文</option></select></label><label data-speech-speed-row>Speed <input data-speech-speed type="number" min="0.5" max="2" step="0.1" value="1"></label><div class="studio-actions"><button class="tool-chip is-primary" data-speech-create>${icon("speak")}Generate and add to timeline</button></div></div></div>
    </section>
    <section data-view="models" class="set-view" hidden>
      <div class="panel-section"><div class="panel-section-head"><span>Local models</span><small>Download once, then process media locally. You can also import model files acquired separately.</small></div><div class="panel-rows"><small data-model-runtime hidden></small><div data-model-list></div></div></div>
      <div class="panel-section krea-card" data-krea-card>
        <div class="panel-section-head"><span>Krea 2 Turbo (optional)</span><small data-krea-state>Not installed</small></div>
        <div class="panel-rows">
          <small>A 12-billion-parameter image model from Krea, run on this computer. Nothing is downloaded until you install it here.</small>
          <details class="krea-terms"><summary>Krea 2 Community License Agreement</summary><ul data-krea-summary></ul><a data-krea-licence target="_blank" rel="noopener">Read the full agreement</a> · <a data-krea-policy target="_blank" rel="noopener">Acceptable Use Policy</a></details>
          <label class="krea-check"><input type="checkbox" data-krea-accept> I have read and accept the Krea 2 Community License Agreement</label>
          <div class="krea-filter"><strong>Content filter, installed with Krea 2</strong><small data-krea-filter-what></small></div>
          <label>Build <select data-krea-build></select></label>
          <div class="krea-actions"><button type="button" class="tool-chip" data-krea-install disabled>Install Krea 2</button><button type="button" class="tool-chip" data-krea-use hidden>Generate with Krea 2</button><button type="button" class="tool-chip" data-krea-reinstall-filter hidden>Reinstall the content filter</button></div>
          <div class="krea-removed" data-krea-removed role="alertdialog" aria-labelledby="krea-removed-title" hidden>
            <strong id="krea-removed-title">The content filter has been removed</strong>
            <p data-krea-removed-text></p>
            <div class="krea-actions"><button type="button" class="tool-chip" data-krea-removed-reinstall>Reinstall the content filter</button><button type="button" class="tool-chip" data-krea-removed-ack>I understand</button></div>
          </div>
        </div>
      </div>
    </section>
    ${["flux2-klein-4b"].map((variant) => `
      <div class="panel-section krea-card" data-klein-card="${variant}">
        <div class="panel-section-head"><span data-klein-title="${variant}">FLUX.2 [klein] 4B (optional)</span><small data-klein-state="${variant}">Not installed</small></div>
        <div class="panel-rows">
          <small>A 4-billion-parameter image model from Black Forest Labs, four steps a picture, under the Apache License 2.0 (commercial use allowed). Run on this computer through mflux, with LoRA stacks. Nothing is downloaded until you install it here.</small>
          <details class="krea-terms"><summary data-klein-licence-name="${variant}"></summary><ul data-klein-summary="${variant}"></ul><a data-klein-licence="${variant}" target="_blank" rel="noopener">Read the model card and licence</a></details>
          <label class="krea-check"><input type="checkbox" data-klein-accept="${variant}"> <span data-klein-accept-label="${variant}"></span></label>
          <label>Build <select data-klein-build="${variant}"></select></label>
          <div class="krea-actions"><button type="button" class="tool-chip" data-klein-install="${variant}" disabled>Install</button><button type="button" class="tool-chip" data-klein-use="${variant}" hidden>Generate with it</button></div>
        </div>
      </div>`).join("")}
      <div class="panel-section krea-card" data-ckpt-card>
        <div class="panel-section-head"><span>Your own checkpoints</span><small data-ckpt-state></small></div>
        <div class="panel-rows">
          <small>A Krea 2 or FLUX.2 [klein] 4B fine-tune converted to mflux's MLX format (the folder mflux-save writes: text_encoder/, tokenizer/, vae/ and the transformer's weights) runs here as a model of its own, with that model's LoRAs. Put each one's folder in:</small>
          <ul class="ckpt-folders" data-ckpt-folders></ul>
          <ul class="ckpt-list" data-ckpt-list></ul>
          <div class="krea-actions"><button type="button" class="tool-chip" data-ckpt-rescan>Look again</button></div>
        </div>
      </div>
    <section data-view="terminal" class="set-view" hidden>
      <div class="panel-section"><div class="panel-section-head"><span>${text("Agent terminal")}</span><small data-term-status></small></div><div class="panel-rows">
        <p class="stock-note">${text("A real shell inside formcut, started with this engine's MCP server in its environment. Connect a client once, then run claude or codex here and it drives the editor through the formcut tools while you watch.")}</p>
        <div class="stock-row"><button class="tool-chip" data-term-connect="claude-code">${icon("plus")}${text("Connect Claude Code")}</button><button class="tool-chip" data-term-connect="codex">${icon("plus")}${text("Connect Codex")}</button><button class="tool-chip" data-term-open>${icon("terminal")}${text("Open shell")}</button><button class="tool-chip" data-term-close hidden>${icon("close")}${text("Close shell")}</button></div>
        <p class="stock-note" data-term-note></p>
      </div></div>
      <div class="panel-section term-host" data-term-host hidden><div class="term-pane" data-term-pane></div></div>
    </section>
    </div><footer class="set-foot studio-footer"><span role="status" data-status></span><button class="tool-chip" data-cancel hidden>Cancel job</button></footer></section></div>`;
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
            if (!label) { label = document.createElement("label"); label.dataset.slot = slot.id; const name = document.createElement("span"); name.textContent = slot.nameKey ? t(slot.nameKey) : slot.name; label.append(name, document.createElement("select")); root.append(label); }
            reconcileOptions(label.querySelector("select")!, bin.all.filter(m => m.kind === slot.kind).map(m => ({ id: m.id, name: m.name })));
          }
          q("template-fill").hidden = false;
        }));
        const download = document.createElement("a"); download.className = "tool-chip"; download.textContent = "Export"; download.href = `/api/templates/${entry.id}/file`; download.download = "template.fctemplate";
        const remove = document.createElement("button"); remove.className = "tool-chip"; remove.textContent = "Delete"; remove.addEventListener("click", () => void run(async () => { await api(`/api/templates/${entry.id}`, undefined, "DELETE"); await refreshTemplates(); }));
        // formcut's own templates cannot be deleted, so they offer no Delete.
        if (entry.bundled) row.append(fill, download); else row.append(fill, download, remove);
        templateRows.set(entry.id, row); q("template-list").append(row);
      }
      const name = entry.nameKey ? t(entry.nameKey) : entry.name;
      row.querySelector("span")!.textContent = `${name} · ${entry.slots.length} slots${entry.bundled ? ` · ${t("tpl.builtin")}` : ""}`;
    }
  };
  // Krea 2: the card is built once in the markup above; a refresh writes only what changed.
  let kreaTerms: any;
  const kreaInstallReady = () => { q<HTMLButtonElement>("krea-install").disabled = !q("krea-accept").checked; };
  q("krea-accept").addEventListener("change", kreaInstallReady);
  const refreshKrea = async () => {
    if (!kreaTerms) {
      kreaTerms = await api<any>("/api/models/krea-2/terms", undefined, "GET");
      const list = q<HTMLUListElement>("krea-summary");
      for (const line of kreaTerms.licence.summary as string[]) { const item = document.createElement("li"); item.textContent = line; list.append(item); }
      q<HTMLAnchorElement>("krea-licence").href = kreaTerms.licence.url;
      q<HTMLAnchorElement>("krea-policy").href = kreaTerms.licence.usePolicy;
      q("krea-filter-what").textContent = `${kreaTerms.filter.what} ${kreaTerms.filter.licence}, ${Math.round(kreaTerms.filter.size / 1e6)} MB.`;
      q("krea-removed-text").textContent = kreaTerms.removedWarning;
      const select = q<HTMLSelectElement>("krea-build");
      for (const [key, build] of Object.entries<any>(kreaTerms.builds)) {
        const option = document.createElement("option"); option.value = key;
        option.textContent = `${build.label}, ${(build.size / 1e9).toFixed(1)} GB (${build.note})`;
        select.append(option);
      }
      if (kreaTerms.recommended) select.value = kreaTerms.recommended;
      if (!select.options.length) { q<HTMLButtonElement>("krea-install").hidden = true; }
    }
    const policy = await api<any>("/api/models/krea-2/status", undefined, "GET");
    const state = !Object.keys(kreaTerms.builds).length
      ? "No Krea 2 build for this computer"
      : policy.ready
        ? `Installed: ${kreaTerms.builds[policy.build]?.label ?? policy.build}, content filter ${policy.filterInstalled ? "on" : "removed"}`
        : policy.licenceAccepted ? `Not ready: ${policy.reason}` : "Not installed";
    if (q("krea-state").textContent !== state) q("krea-state").textContent = state;
    // the filter removed from an installed Krea 2: the warning, shown until acknowledged; the model still runs
    q("krea-reinstall-filter").hidden = !policy.filterRemoved;
    q("krea-removed").hidden = !policy.filterRemoved || policy.removalAcknowledged;
    q<HTMLButtonElement>("krea-install").textContent = policy.build ? "Installed" : "Install Krea 2";
    if (policy.build) q<HTMLButtonElement>("krea-install").disabled = true; else kreaInstallReady();
    q("krea-use").hidden = !policy.ready;
    // the generator's list follows: Krea 2 appears there the moment its licence is accepted and it is installed
    void refreshGenerators().catch(() => { /* offline engine */ });
  };
  // FLUX.2 [klein] 4B: licence, build, install, and the way into the generator (the 9B models' non-commercial
  // licence does not fit formcut, so they are not offered)
  let kleinTerms: any;
  const refreshKlein = async () => {
    kleinTerms = await api<any>("/api/models/klein/terms", undefined, "GET");
    for (const [variant, spec] of Object.entries<any>(kleinTerms.variants)) {
      const one = (name: string) => modal.querySelector<HTMLElement>(`[data-${name}="${variant}"]`)!;
      one("klein-licence-name").textContent = spec.licence.name;
      (one("klein-licence") as HTMLAnchorElement).href = spec.licence.url;
      one("klein-accept-label").textContent = `I have read the ${spec.licence.name} and accept it`;
      const list = one("klein-summary");
      if (!list.childElementCount) for (const line of spec.licence.summary as string[]) { const item = document.createElement("li"); item.textContent = line; list.append(item); }
      const builds = one("klein-build") as HTMLSelectElement;
      if (!builds.options.length) for (const [key, build] of Object.entries<any>(spec.builds)) {
        const option = document.createElement("option"); option.value = key;
        option.textContent = `${build.label}, ${(build.bytes / 1e9).toFixed(1)} GB (${build.note})`; builds.append(option);
      }
      const status = spec.status;
      const accept = one("klein-accept") as HTMLInputElement;
      if (status.licenceAccepted) { accept.checked = true; accept.disabled = true; }
      const install = one("klein-install") as HTMLButtonElement;
      install.textContent = status.build ? "Installed" : "Install";
      install.disabled = !!status.build || !accept.checked;
      one("klein-state").textContent = status.ready ? `Installed: ${spec.builds[status.build]?.label ?? status.build}` : status.licenceAccepted || status.build ? `Not ready: ${status.reason}` : "Not installed";
      one("klein-use").hidden = !status.ready;
    }
  };
  for (const variant of ["flux2-klein-4b"]) {
    const one = (name: string) => modal.querySelector<HTMLElement>(`[data-${name}="${variant}"]`)!;
    one("klein-accept").addEventListener("change", () => { (one("klein-install") as HTMLButtonElement).disabled = !(one("klein-accept") as HTMLInputElement).checked; });
    one("klein-install").addEventListener("click", () => void run(async () => {
      await api("/api/models/klein/consent", { variant, acceptLicence: (one("klein-accept") as HTMLInputElement).checked });
      await job("/api/models/klein/install", { variant, build: (one("klein-build") as HTMLSelectElement).value });
      await refreshKlein(); void refreshGenerators().catch(() => { /* offline engine */ });
      say(`${kleinTerms.variants[variant].label} is installed.`);
    }));
    one("klein-use").addEventListener("click", () => document.dispatchEvent(new CustomEvent("formcut:klein-use", { detail: variant })));
  }
  // The person's own checkpoints: the folders to drop them into, and each one found with what it lacks, if anything
  const refreshCheckpoints = async () => {
    const reply = await api<any>("/api/checkpoints", undefined, "GET");
    const folders = q<HTMLUListElement>("ckpt-folders"); folders.replaceChildren();
    for (const [base, path] of Object.entries<string>(reply.folders)) {
      const item = document.createElement("li"); const code = document.createElement("code");
      code.textContent = path; item.append(`${reply.bases[base]}: `, code); folders.append(item);
    }
    const list = q<HTMLUListElement>("ckpt-list"); list.replaceChildren();
    for (const entry of reply.checkpoints as Array<{ name: string; baseLabel: string; usable: boolean; problem?: string; bytes: number }>) {
      const item = document.createElement("li");
      item.textContent = `${entry.name} (${entry.baseLabel}, ${(entry.bytes / 1e9).toFixed(1)} GB): ${entry.usable ? "ready in the image generator" : entry.problem}`;
      list.append(item);
    }
    q("ckpt-state").textContent = reply.checkpoints.length ? `${reply.checkpoints.filter((c: { usable: boolean }) => c.usable).length} of ${reply.checkpoints.length} usable` : "None yet";
  };
  q("ckpt-rescan").addEventListener("click", () => void run(async () => { await refreshCheckpoints(); await refreshGenerators(); }));
  // Generate with Krea 2: the image generator, Krea 2 chosen, the prompt waiting
  q("krea-use").addEventListener("click", () => void run(async () => {
    activePage = "genimage";
    await showPage();
    await refreshGenerators();
    const select = pick<HTMLSelectElement>('[data-gen-model="image"]');
    select.value = "local:krea-2";
    select.dispatchEvent(new Event("change"));
    pick<HTMLTextAreaElement>('[data-gen-prompt="image"]').focus();
  }));
  q("krea-install").addEventListener("click", () => void run(async () => {
    await api("/api/models/krea-2/consent", { acceptLicence: q("krea-accept").checked });
    await job("/api/models/krea-2/install", { build: q<HTMLSelectElement>("krea-build").value });
    await refreshKrea();
    say("Krea 2 and its content filter are installed.");
  }));
  const reinstallFilter = () => void run(async () => {
    await job("/api/models/krea-2/filter");
    await refreshKrea();
    say("The content filter is installed again and runs on every Krea 2 picture.");
  });
  q("krea-reinstall-filter").addEventListener("click", reinstallFilter);
  q("krea-removed-reinstall").addEventListener("click", reinstallFilter);
  q("krea-removed-ack").addEventListener("click", () => void run(async () => {
    await api("/api/models/krea-2/acknowledge-removal", {});
    await refreshKrea();
  }));
  const modelRows = new Map<string, HTMLElement>();
  const refreshModels = async () => {
    // BG6: which processor the model sessions run on, shown where the models
    // are managed; written only when it changes, so a refresh mutates nothing.
    const runtime = await api<{ active: string }>("/api/models/runtime");
    const providerLabels: Record<string, string> = { CPUExecutionProvider: "CPU", CoreMLExecutionProvider: "Core ML", DmlExecutionProvider: "DirectML", CUDAExecutionProvider: "CUDA" };
    const runtimeLine = q("model-runtime");
    const wanted = `${text("Processor")}: ${providerLabels[runtime.active] ?? runtime.active.replace("ExecutionProvider", "")}`;
    if (runtimeLine.textContent !== wanted) runtimeLine.textContent = wanted;
    runtimeLine.hidden = false;
    const models = await api<any[]>("/api/models");
    for (const model of models) {
      if (model.managedBy === "krea-2") continue; // installed from the Krea 2 card, after its licence and filter choice
      let row = modelRows.get(model.id);
      if (!row) {
        row = document.createElement("div"); row.className = "studio-model";
        const name = document.createElement("strong"); name.textContent = text(model.name);
        const status = document.createElement("span"); status.dataset.ready = "";
        const download = document.createElement("button"); download.className = "tool-chip"; download.textContent = text("Download");
        download.addEventListener("click", () => void run(async () => { await job(`/api/models/${model.id}/download`); await refreshModels(); say(model.id === "local-speech" ? t("models.readyspeech") : t("models.ready")); }));
        const files = document.createElement("span"); files.textContent = model.files.join(", ");
        const importer = document.createElement("input"); importer.type = "file"; importer.setAttribute("aria-label", text(`Import ${model.name}`));
        importer.addEventListener("change", () => void run(async () => { if (!importer.files?.[0]) return; const body = new FormData(); body.append("file", importer.files[0]); await api(`/api/models/${model.id}/import`, body); await refreshModels(); }));
        row.append(name, status, download, files, importer); modelRows.set(model.id, row); q("model-list").append(row);
        if (model.id === "local-speech") { const note = document.createElement("span"); note.className = "text-add-hint"; note.textContent = t("models.speechsetup"); row.append(note); }
      }
      const readiness = text(model.ready ? "Ready offline" : "Not installed");
      const readyEl = row.querySelector<HTMLElement>("[data-ready]")!;
      if (readyEl.textContent !== readiness) readyEl.textContent = readiness;
      row.querySelector("button")!.disabled = model.ready;
    }
  };
  interface StockItem { id: number; type: string; preview: string | null; full: string | null; width?: number; height?: number; duration?: number; alt?: string | null; page_url: string | null; credit: string | null; credit_url?: string | null }
  const stockGrid = q<HTMLElement>("stock-grid");
  const stockNote = (message: string) => { const node = q<HTMLElement>("stock-note"); if (node.textContent !== message) node.textContent = message; };
  const stockCards = new Map<string, HTMLElement>();
  const stock = {
    loaded: false,
    page: 1,
    kind: "video",
    items: new Map<string, StockItem>(),
    async search(page: number) {
      stock.page = page;
      stockNote(t("stock.searching"));
      try {
        const data = await api<{ items: StockItem[]; page: number; has_next: boolean }>("/api/stock/search", {
          query: q("stock-q").value, kind: stock.kind, page, per_page: 24,
          orientation: q<HTMLSelectElement>("stock-orientation").value, size: q<HTMLSelectElement>("stock-size").value,
          color: stock.kind === "photo" ? q<HTMLSelectElement>("stock-color").value : "", locale: "",
        });
        stock.loaded = true;
        const items = data.items.filter(item => item.full && item.preview);
        stock.items = new Map(items.map(item => [`${item.type}-${item.id}`, item]));
        for (const [key, card] of stockCards) if (!stock.items.has(key)) { card.remove(); stockCards.delete(key); }
        let cursor: Element | null = null;
        for (const [key, item] of stock.items) {
          let card = stockCards.get(key);
          if (!card) {
            card = document.createElement("div"); card.className = "effect-card stock-card"; card.dataset.stock = key;
            card.innerHTML = `<div class="effect-thumb stock-thumb has-image"><img alt="" loading="lazy" draggable="false"><span class="stock-badge"></span></div><div class="effect-name stock-credit"><a target="_blank" rel="noreferrer noopener"></a></div><div class="stock-actions"><button class="iconbtn" data-stock-act="media" title="${text("Add to media")}">${icon("plus")}</button><button class="iconbtn" data-stock-act="track" title="${text("Place on a new track at the playhead")}">${icon("addToTrack")}</button><button class="iconbtn" data-stock-act="download" title="${text("Download")}">${icon("download")}</button><a class="iconbtn" data-stock-act="open" target="_blank" rel="noreferrer" title="${text("Open on Pexels")}">${icon("open")}</a></div>`;
            stockCards.set(key, card);
          }
          const img = card.querySelector<HTMLImageElement>("img")!;
          if (img.getAttribute("src") !== item.preview) img.src = item.preview!;
          const badge = card.querySelector<HTMLElement>(".stock-badge")!;
          // Pexels asks for the photographer by name, and a person choosing a
          // clip wants its length and its size, not one or the other.
          const badgeText = item.type === "video"
            ? `${Math.round(item.duration ?? 0)}s · ${item.width}x${item.height}`
            : `${item.width}x${item.height}`;
          if (badge.textContent !== badgeText) badge.textContent = badgeText;
          const credit = card.querySelector<HTMLAnchorElement>(".stock-credit a")!;
          const who = item.credit ?? "Pexels";
          if (credit.textContent !== who) credit.textContent = who;
          const whoUrl = (item as { credit_url?: string }).credit_url ?? item.page_url ?? "https://www.pexels.com";
          if (credit.getAttribute("href") !== whoUrl) credit.href = whoUrl;
          const open = card.querySelector<HTMLAnchorElement>("[data-stock-act=open]")!;
          if (open.href !== (item.page_url ?? "")) open.href = item.page_url ?? "";
          if (cursor ? card.previousElementSibling !== cursor : stockGrid.firstElementChild !== card) stockGrid.insertBefore(card, cursor ? cursor.nextElementSibling : stockGrid.firstElementChild);
          cursor = card;
        }
        q<HTMLButtonElement>("stock-prev").disabled = page <= 1;
        q<HTMLButtonElement>("stock-next").disabled = !data.has_next;
        const pageLabel = `${text("Page")} ${page}`; if (q<HTMLElement>("stock-page").textContent !== pageLabel) q<HTMLElement>("stock-page").textContent = pageLabel;
        stockNote(items.length ? "" : t("stock.noresults"));
      } catch (error) {
        stockNote(error instanceof Error ? error.message : String(error));
      }
    },
    async import(item: StockItem) {
      stockNote(t("stock.importing"));
      const media = await api<{ id: string; name: string; duration: number; kind: string }>("/api/stock/import", { url: item.full, kind: item.type, name: item.alt || item.credit || "pexels", credit: item.credit, page_url: item.page_url });
      await bin.load();
      stockNote(`${t("stock.imported")}: ${media.name}`);
      return media;
    },
  };
  q<HTMLElement>("stock-kind").addEventListener("click", event => {
    const hit = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-val]"); if (!hit) return;
    for (const other of q<HTMLElement>("stock-kind").querySelectorAll("button")) other.classList.toggle("is-active", other === hit);
    stock.kind = hit.dataset.val!;
    q<HTMLElement>("stock-color-row").hidden = stock.kind !== "photo";
    void stock.search(1);
  });
  q("stock-go").addEventListener("click", () => void stock.search(1));
  q("stock-q").addEventListener("keydown", event => { if (event.key === "Enter") void stock.search(1); });
  for (const name of ["stock-orientation", "stock-size", "stock-color"]) q<HTMLSelectElement>(name).addEventListener("change", () => void stock.search(1));
  q("stock-prev").addEventListener("click", () => { if (stock.page > 1) void stock.search(stock.page - 1); });
  q("stock-next").addEventListener("click", () => void stock.search(stock.page + 1));
  const urlNote = (message: string) => { const node = q<HTMLElement>("stock-url-note"); if (node.textContent !== message) node.textContent = message; };
  q("stock-url-go").addEventListener("click", () => void run(async () => {
    const url = q("stock-url").value.trim(); if (!url) return;
    urlNote(t("stock.downloading"));
    const started = await api<{ job_id: string }>("/api/stock/url", { url });
    const poll = async (): Promise<void> => {
      const status = await api<{ status: string; error?: string; media?: { name: string } }>(`/api/stock/url/${started.job_id}`, undefined, "GET");
      if (status.status === "done") { q("stock-url").value = ""; await bin.load(); urlNote(`${t("stock.imported")}: ${status.media?.name ?? ""}`); return; }
      if (status.status === "error") { urlNote(`${t("stock.importfail")}: ${status.error ?? "?"}`); return; }
      window.setTimeout(() => void poll(), 800);
    };
    await poll();
  }));
  stockGrid.addEventListener("click", event => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-stock-act]");
    const card = (event.target as HTMLElement).closest<HTMLElement>("[data-stock]");
    if (!button || !card || button.dataset.stockAct === "open") return;
    const item = stock.items.get(card.dataset.stock!); if (!item) return;
    void run(async () => {
      const media = await stock.import(item);
      if (button.dataset.stockAct === "download") {
        const link = document.createElement("a"); link.href = `/api/media/${media.id}/file`; link.download = media.name; link.click();
      }
      if (button.dataset.stockAct === "track") {
        const timeline = engine.snapshot.timelines[engine.snapshot.activeTimeline];
        engine.dispatch("track.add", { name: item.type === "video" ? text("Stock video") : text("Stock image") });
        const trackIndex = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks.length - 1;
        if (engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timeline.id) return;
        engine.dispatch("clip.add", { trackIndex, clip: { id: crypto.randomUUID(), kind: media.kind, label: media.name, mediaId: media.id, start: engine.snapshot.playhead, duration: Math.max(0.5, media.duration || 5), filmstrip: media.kind === "video" } });
        stockNote(`${text("Placed on the timeline")}: ${media.name}`);
      }
    });
  });
  // Openverse: openly licensed sounds, music and images without a key. The
  // card shows the licence beside the creator, because the licence is what a
  // person must carry into the credits; import goes by the record's id and
  // the engine reads the file URL back from Openverse itself.
  interface OpenverseItem { id: string; type: string; preview: string | null; full: string | null; title: string; width?: number | null; height?: number | null; duration?: number | null; page_url: string | null; credit: string | null; credit_url?: string | null; license: string; license_url?: string | null; source?: string | null }
  const ovGrid = q<HTMLElement>("ov-grid");
  const ovNote = (message: string) => { const node = q<HTMLElement>("ov-note"); if (node.textContent !== message) node.textContent = message; };
  const ovCards = new Map<string, HTMLElement>();
  const ov = {
    page: 1,
    kind: "audio",
    items: new Map<string, OpenverseItem>(),
    async search(page: number) {
      ov.page = page;
      ovNote(t("stock.searching"));
      try {
        const data = await api<{ items: OpenverseItem[]; page: number; total: number }>("/api/stock/openverse/search", { query: q("ov-q").value, kind: ov.kind, page, per_page: 20 });
        const items = data.items ?? [];
        const wanted = new Set<string>();
        let cursor: HTMLElement | null = null;
        for (const item of items) {
          const key = `${item.type}-${item.id}`;
          wanted.add(key);
          ov.items.set(key, item);
          let card = ovCards.get(key);
          if (!card) {
            card = document.createElement("div"); card.className = "effect-card stock-card ov-card"; card.dataset.ov = key;
            card.innerHTML = `<div class="effect-thumb stock-thumb"><img alt="" loading="lazy" draggable="false" hidden><span class="ov-title"></span><span class="stock-badge"></span></div><div class="effect-name stock-credit"><a target="_blank" rel="noreferrer noopener"></a><span class="ov-licence"></span></div><div class="stock-actions"><button class="iconbtn" data-ov-act="media" title="${text("Add to media")}">${icon("plus")}</button><a class="iconbtn" data-ov-act="open" target="_blank" rel="noreferrer" title="${text("Open the source page")}">${icon("open")}</a></div>`;
            ovCards.set(key, card);
          }
          const img = card.querySelector<HTMLImageElement>("img")!;
          if (item.preview) { if (img.getAttribute("src") !== item.preview) img.src = item.preview; if (img.hidden) img.hidden = false; }
          else if (!img.hidden) img.hidden = true;
          const thumb = card.querySelector<HTMLElement>(".effect-thumb")!;
          if (thumb.classList.contains("has-image") !== Boolean(item.preview)) thumb.classList.toggle("has-image", Boolean(item.preview));
          const titleNode = card.querySelector<HTMLElement>(".ov-title")!;
          const titleText = item.preview ? "" : item.title;
          if (titleNode.textContent !== titleText) titleNode.textContent = titleText;
          const badge = card.querySelector<HTMLElement>(".stock-badge")!;
          const badgeText = item.type === "audio" ? `${Math.round(item.duration ?? 0)}s${item.source ? ` · ${item.source}` : ""}` : `${item.width ?? "?"}x${item.height ?? "?"}`;
          if (badge.textContent !== badgeText) badge.textContent = badgeText;
          const credit = card.querySelector<HTMLAnchorElement>(".stock-credit a")!;
          const who = item.credit || item.title || "Openverse";
          if (credit.textContent !== who) credit.textContent = who;
          const whoUrl = item.credit_url ?? item.page_url ?? "https://openverse.org";
          if (credit.getAttribute("href") !== whoUrl) credit.href = whoUrl;
          const licence = card.querySelector<HTMLElement>(".ov-licence")!;
          if (licence.textContent !== item.license) licence.textContent = item.license;
          const open = card.querySelector<HTMLAnchorElement>("[data-ov-act=open]")!;
          if (open.getAttribute("href") !== (item.page_url ?? "")) open.href = item.page_url ?? "";
          if (cursor ? card.previousElementSibling !== cursor : ovGrid.firstElementChild !== card) ovGrid.insertBefore(card, cursor ? cursor.nextElementSibling : ovGrid.firstElementChild);
          cursor = card;
        }
        for (const [key, card] of ovCards) if (!wanted.has(key)) { card.remove(); ovCards.delete(key); ov.items.delete(key); }
        q<HTMLButtonElement>("ov-prev").disabled = page <= 1;
        q<HTMLButtonElement>("ov-next").disabled = page * 20 >= data.total;
        const pageLabel = `${text("Page")} ${page} · ${data.total}`; if (q<HTMLElement>("ov-page").textContent !== pageLabel) q<HTMLElement>("ov-page").textContent = pageLabel;
        ovNote(items.length ? "" : t("stock.noresults"));
      } catch (error) {
        ovNote(error instanceof Error ? error.message : String(error));
      }
    },
  };
  q<HTMLElement>("ov-kind").addEventListener("click", event => {
    const hit = (event.target as HTMLElement).closest<HTMLButtonElement>("[data-val]"); if (!hit) return;
    for (const other of q<HTMLElement>("ov-kind").querySelectorAll("button")) other.classList.toggle("is-active", other === hit);
    ov.kind = hit.dataset.val!;
    void ov.search(1);
  });
  q("ov-go").addEventListener("click", () => void ov.search(1));
  q("ov-q").addEventListener("keydown", event => { if (event.key === "Enter") void ov.search(1); });
  q("ov-prev").addEventListener("click", () => { if (ov.page > 1) void ov.search(ov.page - 1); });
  q("ov-next").addEventListener("click", () => void ov.search(ov.page + 1));
  ovGrid.addEventListener("click", event => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-ov-act]");
    const card = (event.target as HTMLElement).closest<HTMLElement>("[data-ov]");
    if (!button || !card || button.dataset.ovAct === "open") return;
    const item = ov.items.get(card.dataset.ov!); if (!item) return;
    void run(async () => {
      ovNote(t("stock.importing"));
      const media = await api<{ id: string; name: string }>("/api/stock/openverse/import", { id: item.id, kind: item.type });
      await bin.load();
      ovNote(`${t("stock.imported")}: ${media.name} (${item.license})`);
    });
  });
  // The agent terminal: xterm.js over the engine's PTY socket. One terminal
  // is built the first time the shell opens and reused after; a socket per
  // shell; the fit addon sizes the PTY to the pane. The connect chips write
  // the client's MCP config through the engine, so the agent started here
  // finds formcut's tools.
  const termNote = (message: string) => { const node = q<HTMLElement>("term-note"); if (node.textContent !== message) node.textContent = message; };
  const termHost = q<HTMLElement>("term-host");
  let term: import("@xterm/xterm").Terminal | null = null;
  let fit: import("@xterm/addon-fit").FitAddon | null = null;
  let termSocket: WebSocket | null = null;
  const termStatus = async () => {
    try {
      const status = await api<{ pty: boolean; shell: string; claude: boolean; codex: boolean; mcp: string }>("/api/terminal/status", undefined, "GET");
      const line = `${status.shell}${status.pty ? "" : ` (${text("no pseudo-terminal on this platform")})`} · claude ${status.claude ? text("found") : text("not found")} · codex ${status.codex ? text("found") : text("not found")}`;
      if (q<HTMLElement>("term-status").textContent !== line) q<HTMLElement>("term-status").textContent = line;
    } catch { /* the status is a convenience */ }
  };
  const closeShell = () => {
    termSocket?.close();
    termSocket = null;
    q<HTMLButtonElement>("term-close").hidden = true;
    q<HTMLButtonElement>("term-open").hidden = false;
  };
  q("term-open").addEventListener("click", () => void run(async () => {
    if (termSocket) return;
    const [{ Terminal }, { FitAddon }] = await Promise.all([import("@xterm/xterm"), import("@xterm/addon-fit")]);
    await import("@xterm/xterm/css/xterm.css");
    termHost.hidden = false;
    if (!term) {
      const styles = getComputedStyle(document.documentElement);
      term = new Terminal({
        cursorBlink: true,
        fontFamily: styles.getPropertyValue("--font-mono").trim() || "ui-monospace, SFMono-Regular, Menlo, monospace",
        fontSize: 13,
        theme: { background: styles.getPropertyValue("--ground").trim() || "#121617", foreground: styles.getPropertyValue("--ink").trim() || "#f4f5f6", cursor: styles.getPropertyValue("--cue").trim() || "#ffae2b" },
      });
      fit = new FitAddon();
      term.loadAddon(fit);
      term.open(q<HTMLElement>("term-pane"));
      term.onData((data) => { termSocket?.send(data); });
      term.onResize(({ cols, rows }) => { termSocket?.send(JSON.stringify({ resize: [cols, rows] })); });
      new ResizeObserver(() => fit?.fit()).observe(q<HTMLElement>("term-pane"));
    }
    fit?.fit();
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const socket = new WebSocket(`${protocol}://${location.host}/api/terminal/ws?cols=${term.cols}&rows=${term.rows}`);
    termSocket = socket;
    socket.onopen = () => { termNote(""); q<HTMLButtonElement>("term-close").hidden = false; q<HTMLButtonElement>("term-open").hidden = true; term?.focus(); };
    socket.onmessage = (event) => { term?.write(String(event.data)); };
    socket.onclose = () => { if (termSocket === socket) closeShell(); term?.write("\r\n[" + text("shell closed") + "]\r\n"); };
    socket.onerror = () => { termNote(text("The shell could not be opened")); };
  }));
  q("term-close").addEventListener("click", closeShell);
  for (const chip of modal.querySelectorAll<HTMLButtonElement>("[data-term-connect]")) {
    chip.addEventListener("click", () => void (async () => {
      termNote(text("Connecting"));
      try {
        const made = await api<{ client: string; written: string; present: boolean; backup?: string | null }>("/api/agents/install", { client: chip.dataset.termConnect });
        termNote(`${made.present ? text("Already connected") : text("Connected")}: ${made.written}${made.backup ? ` (${text("previous config kept at")} ${made.backup})` : ""}`);
      } catch (error) {
        termNote(error instanceof Error ? error.message : String(error));
      }
      await termStatus();
    })());
  }
  void termStatus();
  const showPage = async () => {
    // a generator page asks the engine again what it can run: a model installed since (Krea 2) is offered at once
    if (activePage.startsWith("gen")) void refreshGenerators().catch(() => { /* offline engine */ });
    for (const section of modal.querySelectorAll<HTMLElement>("[data-view]")) section.hidden = section.dataset.view !== activePage;
    for (const button of modal.querySelectorAll<HTMLElement>("[data-page]")) {
      button.classList.toggle("is-active", button.dataset.page === activePage);
      if (button.dataset.page === activePage) { const title = button.querySelector("span")?.textContent ?? ""; const slot = q<HTMLElement>("page-title"); if (slot.textContent !== title) slot.textContent = title; }
    }
    if (activePage === "project") structure();
    if (activePage === "stock" && !stock.loaded) await stock.search(1);
    if (activePage === "templates") await refreshTemplates();
    if (activePage === "models") { await refreshModels(); await refreshKrea(); await refreshKlein().catch(() => { /* offline engine */ }); await refreshCheckpoints().catch(() => { /* offline engine */ }); }
    if (activePage === "speech") await loadSpeechEngine();
  };
  opener.addEventListener("click", () => { modal.hidden = false; void run(showPage); q("close").focus(); });
  // The local video and local image sections are a view of the library itself,
  // so what is already imported is findable without leaving the studio.
  // F13: one section for everything already in the library, with a type toggle,
  // cards that show what the media actually is, and a prompt asking where a
  // chosen item should land rather than guessing a track.
  let localKind = "all";
  let pending: { id: string; name: string; kind: string; duration?: number } | null = null;
  const localRef = <T extends HTMLElement>(name: string) => modal.querySelector<T>(`[data-ref="${name}"]`);
  const secondsLabel = (value?: number) => {
    if (!value) return "";
    const minutes = Math.floor(value / 60);
    const seconds = Math.round(value % 60);
    return minutes ? `${minutes}:${String(seconds).padStart(2, "0")}` : `${seconds}s`;
  };
  const localCards = new Map<string, HTMLButtonElement>();
  const localItems = new Map<string, (typeof bin.all)[number]>();
  const paintLocal = () => {
    const grid = localRef<HTMLElement>("local-grid");
    if (!grid) return;
    const query = (localRef<HTMLInputElement>("local-search")?.value ?? "").toLowerCase();
    const sort = localRef<HTMLSelectElement>("local-sort")?.value ?? "added";
    let items = bin.all.filter((item) => localKind === "all" || item.kind === localKind);
    if (query) items = items.filter((item) => item.name.toLowerCase().includes(query));
    if (sort === "name") items = [...items].sort((a, b) => a.name.localeCompare(b.name));
    else if (sort === "duration") items = [...items].sort((a, b) => (b.duration ?? 0) - (a.duration ?? 0));
    const count = localRef<HTMLElement>("local-count");
    if (count) count.textContent = `${items.length} ${t("local.items")}`;
    const present = new Set(bin.all.map((item) => item.id));
    for (const id of localCards.keys()) {
      if (present.has(id)) continue;
      localCards.delete(id);
      localItems.delete(id);
    }
    const ordered: HTMLElement[] = [];
    for (const item of items) {
      localItems.set(item.id, item);
      let card = localCards.get(item.id);
      if (!card) {
        card = document.createElement("button");
        card.className = `local-card k-${item.kind}`;
        card.dataset.media = item.id;
        const art = item.kind === "audio"
          ? `<span class="local-wave">${icon("speaker")}</span>`
          : `<img src="/api/media/${item.id}/thumb" alt="" loading="lazy">`;
        card.innerHTML =
          `<span class="local-art">${art}` +
          `<span class="local-kind">${t(`local.${item.kind}`)}</span>` +
          (item.duration ? `<span class="local-dur">${secondsLabel(item.duration)}</span>` : "") +
          `</span><span class="local-name">${escapeHtml(item.name)}</span>` +
          `<span class="local-meta">${item.width ? `${item.width}x${item.height}` : ""}</span>`;
        card.addEventListener("click", () => { const current = localItems.get(item.id); if (current) openPlace(current); });
        localCards.set(item.id, card);
      } else {
        const name = card.querySelector<HTMLElement>(".local-name");
        if (name && name.textContent !== item.name) name.textContent = item.name;
      }
      ordered.push(card);
    }
    reconcile(grid, ordered);
  };
  const openPlace = (item: { id: string; name: string; kind: string; duration?: number }) => {
    pending = item;
    const sheet = localRef<HTMLElement>("place-sheet");
    const name = localRef<HTMLElement>("place-name");
    const tracks = localRef<HTMLElement>("place-tracks");
    if (!sheet || !tracks || !name) return;
    name.textContent = item.name;
    const timeline = engine.snapshot.timelines[engine.snapshot.activeTimeline];
    tracks.replaceChildren(...timeline.tracks.map((track, index) => {
      const choice = document.createElement("button");
      choice.className = "tool-chip place-track";
      choice.dataset.track = String(index);
      choice.textContent = track.name;
      choice.addEventListener("click", () => {
        for (const other of tracks.querySelectorAll(".place-track")) other.classList.remove("is-on");
        choice.classList.add("is-on");
      });
      return choice;
    }));
    // A sensible track is chosen for them, and they can say otherwise.
    const guess = timeline.tracks.findIndex((track) =>
      item.kind === "audio" ? /audio/i.test(track.name) : !/audio/i.test(track.name));
    const first = tracks.querySelector<HTMLElement>(`[data-track="${Math.max(0, guess)}"]`);
    first?.classList.add("is-on");
    sheet.hidden = false;
  };
  localRef<HTMLButtonElement>("place-cancel")?.addEventListener("click", () => {
    localRef<HTMLElement>("place-sheet")!.hidden = true;
    pending = null;
  });
  localRef<HTMLButtonElement>("place-go")?.addEventListener("click", () => {
    const sheet = localRef<HTMLElement>("place-sheet");
    const chosen = modal.querySelector<HTMLElement>(".place-track.is-on");
    if (!pending || !sheet || !chosen) return;
    const state = engine.snapshot;
    const timeline = state.timelines[state.activeTimeline];
    const trackIndex = Number(chosen.dataset.track);
    const where = localRef<HTMLSelectElement>("place-at")?.value ?? "playhead";
    const track = timeline.tracks[trackIndex];
    const end = track.clips.reduce((furthest, clip) => Math.max(furthest, clip.start + clip.duration), 0);
    const start = where === "playhead" ? state.playhead : where === "end" ? end : 0;
    engine.dispatch("clip.add", {
      trackIndex,
      clip: {
        id: crypto.randomUUID(), kind: pending.kind, label: pending.name,
        mediaId: pending.id, start, duration: pending.duration || 4,
      },
    });
    const note = localRef<HTMLElement>("local-note");
    if (note) note.textContent = `${t("local.placed")} ${track.name}`;
    sheet.hidden = true;
    pending = null;
  });
  // Capture phase on the modal: a shared handler for .seg rows stops these
  // clicks before they reach anything bound on the row or the button, which is
  // why choosing a type appeared to do nothing at all.
  modal.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>('[data-ref="local-kinds"] [data-kind]');
    if (!button) return;
    localKind = button.dataset.kind ?? "all";
    for (const other of modal.querySelectorAll('[data-ref="local-kinds"] [data-kind]')) {
      other.classList.toggle("is-active", other === button);
    }
    paintLocal();
  }, true);
  modal.querySelector('[data-ref="local-search"]')?.addEventListener("input", paintLocal);
  modal.querySelector('[data-ref="local-sort"]')?.addEventListener("change", paintLocal);
  bin.subscribe(() => paintLocal());

  modal.querySelector('[data-view="recording"]')!.append(buildRecording(engine, bin));

  // The rail collapses to icons, like the settings popout, and remembers it.
  const rail = modal.querySelector<HTMLElement>(".studio-rail")!;
  const railToggle = modal.querySelector<HTMLButtonElement>("[data-rail-toggle]")!;
  const setRail = (collapsed: boolean) => {
    rail.classList.toggle("is-collapsed", collapsed);
    rail.dataset.collapsed = String(collapsed);
    railToggle.setAttribute("aria-expanded", String(!collapsed));
    railToggle.title = collapsed ? "Expand" : "Collapse";
    try { localStorage.setItem("formcut.studio.rail", collapsed ? "collapsed" : "open"); } catch { /* ignore */ }
  };
  railToggle.addEventListener("click", () => setRail(!rail.classList.contains("is-collapsed")));
  const fullButton = modal.querySelector<HTMLButtonElement>("[data-full]")!;
  fullButton.addEventListener("click", () => {
    // Fullscreen takes the section's own container over the window, leaving the
    // rail behind, rather than stretching the whole popout.
    const full = modal.classList.toggle("is-full");
    fullButton.setAttribute("aria-pressed", String(full));
    try { localStorage.setItem("formcut.studio.full", full ? "on" : "off"); } catch { /* ignore */ }
  });
  try {
    if (localStorage.getItem("formcut.studio.full") === "on") { modal.classList.add("is-full"); fullButton.setAttribute("aria-pressed", "true"); }
  } catch { /* ignore */ }
  try { setRail(localStorage.getItem("formcut.studio.rail") === "collapsed"); } catch { setRail(false); }

  // Generation: the sheet builds itself from what the engine says it can do, so
  // a provider that is not configured is visible as such rather than failing
  // only when the button is pressed.
  let generators: Array<{ id: string; label: string; kind: string; providerLabel: string; sizes: string[]; options: Record<string, unknown>; ready: boolean; reason?: string }> = [];
  const kleinUse = (variant: string) => void run(async () => {
    activePage = "genimage";
    await showPage();
    await refreshGenerators();
    const select = pick<HTMLSelectElement>('[data-gen-model="image"]');
    select.value = `local:${variant}`;
    select.dispatchEvent(new Event("change"));
    pick<HTMLTextAreaElement>('[data-gen-prompt="image"]').focus();
  });
  document.addEventListener("formcut:klein-use", (event) => kleinUse((event as CustomEvent<string>).detail));
  const genJobs = new Map<string, AbortController>();
  const genJobIds = new Map<string, string>();
  const pick = <T extends HTMLElement>(sel: string) => modal.querySelector<T>(sel)!;
  const paintGenerators = () => {
    for (const kind of ["image", "video", "audio"] as const) {
      const select = pick<HTMLSelectElement>(`[data-gen-model="${kind}"]`);
      const mine = generators.filter((g) => g.kind === kind);
      const chosen = select.value;
      // a local model not ready says why (its reason); a provider says it wants its key
      select.innerHTML = mine.map((g) => `<option value="${g.id}">${escapeHtml(g.label)} · ${escapeHtml(g.providerLabel)}${g.ready ? "" : " — " + escapeHtml(g.reason ?? t("gen.needkey"))}</option>`).join("")
        || `<option value="">${t("gen.none")}</option>`;
      if (chosen && mine.some((g) => g.id === chosen)) select.value = chosen;
      const refresh = () => {
        const entry = mine.find((g) => g.id === select.value);
        const ready = pick<HTMLElement>(`[data-gen-ready="${kind}"]`);
        ready.textContent = entry ? (entry.ready ? t("gen.ready") : (entry.reason ?? t("gen.needkey"))) : t("gen.none");
        const sizes = pick<HTMLSelectElement>(`[data-gen-size="${kind}"]`);
        sizes.innerHTML = (entry?.sizes ?? []).map((size) => `<option value="${size}">${size}</option>`).join("");
        pick<HTMLElement>(`[data-gen-size-row="${kind}"]`).hidden = !(entry?.sizes ?? []).length;
        const wantsSeconds = !!entry && "seconds" in (entry.options ?? {});
        pick<HTMLElement>(`[data-gen-seconds-row="${kind}"]`).hidden = !wantsSeconds;
        pick<HTMLElement>(`[data-gen-count-row="${kind}"]`).hidden = !(entry && "count" in (entry.options ?? {}));
        // a local model that takes LoRAs shows its stack, one that plans its memory the memory choice
        const base = entry?.options?.loras as string | undefined;
        pick<HTMLElement>(`[data-gen-loras="${kind}"]`).hidden = !base;
        pick<HTMLElement>(`[data-gen-civitai="${kind}"]`).hidden = !base;
        pick<HTMLElement>(`[data-gen-memory-row="${kind}"]`).hidden = !(entry && "memory" in (entry.options ?? {}));
        pick<HTMLElement>(`[data-gen-sampler-row="${kind}"]`).hidden = !(entry && "scheduler" in (entry.options ?? {}));
        if (base) void paintLoras(kind, base).catch(() => { /* offline engine */ });
      };
      select.onchange = refresh;
      refresh();
    }
  };
  // asked when Studio is built, again whenever a generator page opens and whenever a local model's state changes
  const refreshGenerators = async () => {
    const reply = await fetch("/api/generate").then((r) => r.json());
    generators = reply.generators ?? [];
    paintGenerators();
  };
  void refreshGenerators().catch(() => { /* offline engine */ });

  // LoRA stacks: one per model (a LoRA made for one does not load on another), each LoRA with its strength
  type LoraEntry = { id: string; name: string; base: string; scale: number; triggers?: string; format?: string; usable?: boolean; problem?: string };
  type StackItem = { id: string; scale: number; enabled: boolean };
  const stacks = new Map<string, StackItem[]>();
  const libraries = new Map<string, LoraEntry[]>();
  const baseOf = (kind: string) => generators.find((g) => g.id === pick<HTMLSelectElement>(`[data-gen-model="${kind}"]`).value)?.options?.loras as string | undefined;
  const paintLoras = async (kind: string, base: string) => {
    const reply = await fetch(`/api/loras?base=${encodeURIComponent(base)}`).then((r) => r.json());
    const library: LoraEntry[] = reply.loras ?? [];
    libraries.set(base, library);
    // the folder a person drops .safetensors files into for this model; Look again reads it afresh
    pick<HTMLElement>(`[data-lora-folder="${kind}"]`).textContent = reply.folders?.[base] ?? "";
    const stack = (stacks.get(base) ?? []).filter((item) => library.some((entry) => entry.id === item.id));
    stacks.set(base, stack);
    const rows = pick<HTMLElement>(`[data-lora-rows="${kind}"]`);
    rows.replaceChildren();
    if (!stack.length) {
      const empty = document.createElement("small");
      empty.textContent = library.length ? t("gen.loras.none") : t("gen.loras.empty");
      rows.append(empty);
    }
    stack.forEach((item, index) => {
      const row = document.createElement("div");
      row.className = "lora-row";
      const on = document.createElement("input");
      on.type = "checkbox"; on.checked = item.enabled; on.setAttribute("aria-label", t("gen.loras.on"));
      on.onchange = () => { item.enabled = on.checked; };
      const choice = document.createElement("select");
      for (const entry of library) {
        const option = document.createElement("option");
        option.value = entry.id; option.textContent = entry.usable === false ? `${entry.name} (${entry.problem})` : entry.name;
        option.title = entry.triggers ? `${t("gen.loras.triggers")}: ${entry.triggers}` : "";
        option.disabled = entry.usable === false;
        choice.append(option);
      }
      choice.value = item.id;
      choice.onchange = () => { item.id = choice.value; };
      const slider = document.createElement("input");
      slider.type = "range"; slider.min = "-2"; slider.max = "2"; slider.step = "0.05"; slider.value = String(item.scale);
      slider.setAttribute("aria-label", t("gen.loras.strength"));
      const number = document.createElement("input");
      number.type = "number"; number.min = "-2"; number.max = "2"; number.step = "0.05"; number.value = String(item.scale);
      number.className = "lora-scale"; number.setAttribute("aria-label", t("gen.loras.strength"));
      slider.oninput = () => { item.scale = Number(slider.value); number.value = slider.value; };
      number.onchange = () => { item.scale = Math.max(-2, Math.min(2, Number(number.value) || 0)); number.value = String(item.scale); slider.value = number.value; };
      const remove = document.createElement("button");
      remove.type = "button"; remove.className = "tool-chip"; remove.textContent = t("gen.loras.remove");
      remove.onclick = () => { stack.splice(index, 1); void paintLoras(kind, base); };
      row.append(on, choice, slider, number, remove);
      rows.append(row);
    });
  };
  const addToStack = (kind: string, base: string, entry?: LoraEntry) => {
    const library = libraries.get(base) ?? [];
    const chosen = entry ?? library.find((candidate) => candidate.usable !== false);
    if (!chosen) { pick<HTMLElement>(`[data-gen-note="${kind}"]`).textContent = t("gen.loras.empty"); return; }
    const stack = stacks.get(base) ?? [];
    if (stack.length >= 8) return;
    stack.push({ id: chosen.id, scale: chosen.scale ?? 1, enabled: true });
    stacks.set(base, stack);
    void paintLoras(kind, base);
  };

  for (const kind of ["image", "video", "audio"] as const) {
    const note = pick<HTMLElement>(`[data-gen-note="${kind}"]`);
    pick<HTMLButtonElement>(`[data-lora-add="${kind}"]`).addEventListener("click", () => { const base = baseOf(kind); if (base) addToStack(kind, base); });
    pick<HTMLButtonElement>(`[data-lora-rescan="${kind}"]`).addEventListener("click", () => { const base = baseOf(kind); if (base) void paintLoras(kind, base); });
    pick<HTMLInputElement>(`[data-lora-file="${kind}"]`).addEventListener("change", () => void (async () => {
      const input = pick<HTMLInputElement>(`[data-lora-file="${kind}"]`);
      const file = input.files?.[0]; const base = baseOf(kind);
      if (!file || !base) return;
      const form = new FormData(); form.append("file", file); form.append("base", base); form.append("name", file.name.replace(/\.safetensors$/i, ""));
      note.textContent = t("gen.loras.adding");
      const res = await fetch("/api/loras/import", { method: "POST", body: form, headers: { "x-formcut-local": "1" } });
      const reply = await res.json().catch(() => ({}));
      input.value = "";
      if (!res.ok) { note.textContent = String(reply.detail ?? res.status); return; }
      note.textContent = `${t("gen.loras.added")}: ${reply.name}`;
      await paintLoras(kind, base); addToStack(kind, base, reply);
    })());
    pick<HTMLButtonElement>(`[data-lora-fetch="${kind}"]`).addEventListener("click", () => void (async () => {
      const url = pick<HTMLInputElement>(`[data-lora-url="${kind}"]`).value.trim(); const base = baseOf(kind);
      if (!url || !base) return;
      try {
        note.textContent = t("gen.loras.adding");
        const started = await api("/api/loras/fetch", { url, base });
        for (;;) {
          const status = await fetch(`/api/jobs/${started.job_id}`).then((r) => r.json());
          if (status.status === "done") { note.textContent = `${t("gen.loras.added")}: ${status.result.lora.name}`; await paintLoras(kind, base); addToStack(kind, base, status.result.lora); break; }
          if (status.status === "error" || status.status === "cancelled") { note.textContent = String(status.error ?? t("gen.failed")); break; }
          note.textContent = `${t("gen.loras.adding")} ${Math.round((status.progress ?? 0) * 100)}%`;
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      } catch (error) { note.textContent = error instanceof Error ? error.message : t("gen.failed"); }
    })());
    const grid = pick<HTMLElement>(`[data-gen-grid="${kind}"]`);
    const cancel = pick<HTMLButtonElement>(`[data-gen-cancel="${kind}"]`);
    cancel.addEventListener("click", () => {
      // the engine's job is ended too (the model's process with it), not only the page's asking
      const id = genJobIds.get(kind);
      if (id) void fetch(`/api/jobs/${id}`, { method: "DELETE", headers: { "x-formcut-local": "1" } });
      genJobs.get(kind)?.abort(); genJobs.delete(kind); cancel.hidden = true; note.textContent = t("cap.cancelled");
    });
    pick<HTMLButtonElement>(`[data-gen-go="${kind}"]`).addEventListener("click", () => void (async () => {
      const generator = pick<HTMLSelectElement>(`[data-gen-model="${kind}"]`).value;
      const prompt = pick<HTMLTextAreaElement>(`[data-gen-prompt="${kind}"]`).value.trim();
      if (!generator) { note.textContent = t("gen.none"); return; }
      if (!prompt) { note.textContent = t("gen.needprompt"); return; }
      const body = {
        generator, prompt,
        negative: pick<HTMLInputElement>(`[data-gen-negative="${kind}"]`).value,
        size: pick<HTMLSelectElement>(`[data-gen-size="${kind}"]`).value || null,
        seconds: Number(pick<HTMLInputElement>(`[data-gen-seconds="${kind}"]`).value) || null,
        count: Number(pick<HTMLInputElement>(`[data-gen-count="${kind}"]`).value) || 1,
        options: {} as Record<string, unknown>,
      };
      const base = baseOf(kind);
      if (base) body.options.loras = (stacks.get(base) ?? []).filter((item) => item.enabled).map((item) => ({ id: item.id, scale: item.scale }));
      if (!pick<HTMLElement>(`[data-gen-memory-row="${kind}"]`).hidden) body.options.memory = pick<HTMLSelectElement>(`[data-gen-memory="${kind}"]`).value;
      if (!pick<HTMLElement>(`[data-gen-sampler-row="${kind}"]`).hidden) body.options.scheduler = pick<HTMLSelectElement>(`[data-gen-sampler="${kind}"]`).value;
      const progress = pick<HTMLElement>(`[data-gen-progress="${kind}"]`);
      const bar = pick<HTMLProgressElement>(`[data-gen-bar="${kind}"]`);
      const stage = pick<HTMLElement>(`[data-gen-stage="${kind}"]`);
      bar.value = 0; stage.textContent = t("gen.working"); progress.hidden = false;
      note.textContent = t("gen.working");
      cancel.hidden = false;
      const controller = new AbortController();
      genJobs.set(kind, controller);
      try {
        const started = await api("/api/generate", body);
        genJobIds.set(kind, started.job_id);
        note.textContent = "";
        for (let waited = 0; waited < 3600 && !controller.signal.aborted; waited += 1) {
          const status = await fetch(`/api/jobs/${started.job_id}`).then((r) => r.json());
          if (status.status === "done") {
            const made = status.result?.media ?? [];
            grid.insertAdjacentHTML("afterbegin", made.map((item: { id: string; name: string }) =>
              `<div class="effect-card stock-card"><div class="effect-thumb has-image"><img src="/api/media/${item.id}/thumb" alt="" loading="lazy"></div><div class="effect-name">${escapeHtml(item.name)}</div></div>`).join(""));
            // what the model's licence sends with its pictures: Krea 2's warning when its content filter was removed
            const warning = status.result?.warning as string | undefined;
            // what the generator read from a Civitai-style prompt, and what these models do not take
            const notes = ((status.result?.notes ?? []) as string[]).join(" · ");
            note.textContent = [`${t("gen.done")}: ${made.length}`, notes, warning].filter(Boolean).join(". ");
            await bin.load();
            break;
          }
          if (status.status === "error" || status.status === "failed") { note.textContent = String(status.error ?? t("gen.failed")); break; }
          if (status.status === "cancelled") { note.textContent = t("cap.cancelled"); break; }
          bar.value = status.progress ?? 0;
          stage.textContent = `${status.message ?? t("gen.working")} · ${Math.round((status.progress ?? 0) * 100)}%`;
          await new Promise((resolve) => setTimeout(resolve, 1000));
        }
      } catch (error) {
        note.textContent = error instanceof Error ? error.message : t("gen.failed");
      } finally {
        cancel.hidden = true;
        progress.hidden = true;
        genJobs.delete(kind);
        genJobIds.delete(kind);
      }
    })());
  }

  document.addEventListener("formcut:studio", event => {
    const page = (event as CustomEvent<{ page?: string }>).detail?.page;
    if (page && modal.querySelector(`[data-view="${page}"]`)) activePage = page;
    say(""); modal.hidden = false; void run(showPage); q("close").focus();
  });
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
  // Local speech engines: Kokoro, and Pocket TTS and Chatterbox installed into the speech runtime on request.
  const ENGINE_NOTES: Record<string, string> = {
    kokoro: "Kokoro, Apache-2.0: many voices and languages, fast.",
    pocket: "Pocket TTS by Kyutai, CC-BY-4.0: small and quick on a CPU; built-in voices, or clone one with permission.",
    chatterbox: "Chatterbox by Resemble AI, MIT: expressive, multilingual, clones a voice from seconds of audio. Its audio carries an inaudible watermark.",
  };
  const loadSpeechEngine = async () => {
    const engineId = q<HTMLSelectElement>("speech-engine").value;
    const voices = await api(`/api/speech/voices?engine=${engineId}`);
    reconcileOptions(q<HTMLSelectElement>("speech-voice"), voices.voices);
    const cloning = engineId !== "kokoro";
    q<HTMLElement>("speech-clone").hidden = !cloning;
    q<HTMLElement>("speech-consent-row").hidden = !cloning;
    q<HTMLElement>("speech-expression-row").hidden = engineId !== "chatterbox";
    q<HTMLElement>("speech-speed-row").hidden = cloning;
    q<HTMLElement>("speech-engine-note").textContent = text(ENGINE_NOTES[engineId]);
    const references = bin.all.filter((m) => m.kind === "audio" || m.kind === "video").map((m) => ({ id: m.id, name: m.name }));
    reconcileOptions(q<HTMLSelectElement>("speech-reference"), [{ id: "", name: text("None") }, ...references]);
    const missing = cloning && voices.runtime && !voices.installed;
    q<HTMLButtonElement>("speech-install").hidden = !missing;
    if (engineId === "kokoro" && !voices.ready) say(t("speech.needmodel"));
    else if (!voices.runtime) say(t("speech.needsetup"));
    else if (missing) say(text("Install this engine to use it; it downloads PyTorch and its model once."));
    else say("");
  };
  q<HTMLSelectElement>("speech-engine").addEventListener("change", () => void run(loadSpeechEngine));
  q("speech-install").addEventListener("click", () => void run(async () => {
    say(text("Installing; this can take several minutes."));
    await job(`/api/speech/engines/${q<HTMLSelectElement>("speech-engine").value}/install`, {});
    await loadSpeechEngine();
  }));
  q("speech-create").addEventListener("click", () => void run(async () => {
    const start = engine.snapshot.playhead;
    const timelineId = engine.snapshot.timelines[engine.snapshot.activeTimeline].id;
    const result = await job("/api/speech", {
      text: q<HTMLTextAreaElement>("speech-text").value,
      voice: q<HTMLSelectElement>("speech-voice").value,
      language: q<HTMLSelectElement>("speech-language").value,
      speed: Number(q("speech-speed").value),
      engine: q<HTMLSelectElement>("speech-engine").value,
      reference: q<HTMLSelectElement>("speech-reference").value || null,
      consent: q<HTMLInputElement>("speech-consent").checked,
      exaggeration: Number(q("speech-exaggeration").value),
    });
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
    if (!canvas || (mode !== "keep" && mode !== "erase" && mode !== "smart-keep" && mode !== "smart-erase") || !clip?.cutout) return;
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
        // A smart stroke is resolved once, here, into the region the
        // segmenter found under it; a painted stroke stays geometry. Either
        // way the result is one stroke, so one undo step.
        const smart = mode === "smart-keep" || mode === "smart-erase";
        const result = await api<{ points?: number[][]; region?: number[][]; t?: number }>(smart ? "/api/render/smart-brush" : "/api/render/brush", { project, clipId: clip.id, time: project.playhead, points });
        const current = engine.findClip(clip.id)?.clip;
        if (!current?.cutout || current.mediaId !== clip.mediaId || engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timelineId) throw new Error("The brush target changed.");
        const stroke = smart
          ? { mode: mode === "smart-keep" ? "keep" as const : "erase" as const, radius, points: [], region: result.region, t: result.t }
          : { mode, radius, points: result.points ?? [] };
        engine.dispatch("clip.creator", { clipId: clip.id, patch: { cutout: { ...current.cutout, strokes: [...current.cutout.strokes, stroke] } } });
      });
    };
    move(event);
    canvas.addEventListener("pointermove", move); canvas.addEventListener("pointerup", end, { once: true }); canvas.addEventListener("pointercancel", cleanup, { once: true });
  });
}
