import { effectParameters, type ParamDeclaration } from "./effect-parameters";
import { localizeElement, text as phrase } from "../i18n/text";
import type { ProjectEngine } from "../engine/project";
import type { Clip, KeyframeProp } from "../engine/types";
import { SPEED_PRESETS } from "../engine/timing";
import { MOTION_PRESETS } from "../engine/motion";
import { api } from "../engine/api";

const TRANSITIONS = ["crossfade", "dip", "wipe-left", "wipe-right", "wipe-up", "wipe-down", "slide-left", "slide-right", "zoom", "iris", "dissolve", "push-up"];

export function buildCreatorPanel(engine: ProjectEngine): HTMLElement {
  const root = document.createElement("section");
  root.className = "section creator-panel";
  root.innerHTML = `<div class="section-head">Creator tools</div>
    <select class="wide-select" data-page data-feature="creator.page" aria-label="Creator tool"><option value="speed" data-feature="creator.speed">Speed curve</option><option value="motion" data-feature="creator.motion">Motion presets</option><option value="effects" data-feature="creator.effects">Visual effects</option><option value="audio" data-feature="creator.audio">Audio processing</option><option value="transition" data-feature="creator.transition">Transitions</option><option value="cutout" data-feature="creator.cutout">Cutout and brushes</option><option value="advanced" data-feature="creator.advanced">LUT, shader and expressions</option></select>
    <div data-group="speed"><label>Preset <select data-speed-preset>${Object.keys(SPEED_PRESETS).map(k => `<option value="${k}">${k[0].toUpperCase() + k.slice(1)}</option>`).join("")}</select></label><button class="tool-chip" data-action="speed-preset">Apply curve</button>
    <div class="speed-points"></div><button class="tool-chip" data-action="speed-add">Add point at playhead</button><button class="tool-chip" data-action="speed-clear">Constant speed</button>
    <svg class="speed-graph" viewBox="0 0 240 90" aria-label="Speed curve"><path fill="none" stroke="currentColor" stroke-width="2"/></svg></div>
    <div data-group="motion" hidden><label>Motion <select data-motion>${MOTION_PRESETS.map(k => `<option value="${k}">${k[0].toUpperCase() + k.slice(1).replace(/-/g, " ")}</option>`).join("")}</select></label><label>Seconds <input data-motion-duration type="number" value="1" min="0.1" step="0.1"></label><button class="tool-chip" data-action="motion">Apply keyframes</button></div>
    <div data-group="effects" hidden><label>Effect <select data-effect></select></label><button class="tool-chip" data-action="effect-add">Add effect</button><div data-effect-list></div></div>
    <div data-group="audio" hidden><label>Volume <input data-volume type="range" min="0" max="2" step="0.01" value="1"></label><label>Pan <input data-pan type="range" min="-1" max="1" step="0.01" value="0"></label><label>Processor <select data-audio></select></label><button class="tool-chip" data-action="audio-add">Add processor</button><div data-audio-list></div></div>
    <div data-group="transition" hidden><label>Transition <select data-transition><option value="">None</option>${TRANSITIONS.map(k => `<option value="${k}">${k === "crossfade" ? "Crossfade" : k === "dip" ? "Dip to black" : k.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}</option>`).join("")}</select></label><label>Seconds <input data-transition-duration type="number" value="0.6" min="0.1" step="0.1"></label><button class="tool-chip" data-action="transition">Apply transition</button></div>
    <div data-group="cutout" hidden><label>Model <select data-cutout-model><option value="object-cutout">Object cutout</option><option value="person-cutout">Person cutout</option></select></label><label>Threshold <input data-cutout-threshold type="range" min="0" max="1" step="0.01" value="0.5"></label><label>Edge softness <input data-cutout-feather type="range" min="0.005" max="0.5" step="0.005" value="0.1"></label><button class="tool-chip" data-action="cutout">Enable cutout</button><button class="tool-chip" data-action="cutout-clear">Remove cutout</button><label>Brush <select data-brush><option value="off">Off</option><option value="keep">Restore</option><option value="erase">Erase</option></select></label><label>Brush radius <input data-brush-radius type="range" min="0.005" max="0.15" step="0.005" value="0.02"></label><button class="tool-chip" data-action="brush-undo">Remove last stroke</button><p>Paint on the preview. Brush edits use source coordinates and are saved with the clip.</p></div>
    <div data-group="advanced" hidden><label>3D LUT <input data-lut type="file" accept=".cube"></label><button class="tool-chip" data-action="lut-clear">Remove LUT</button><label>WGSL shader <input data-shader type="file" accept=".wgsl"></label><button class="tool-chip" data-action="shader-clear">Remove shader</button><label>Animated property <select data-expression-prop>${[["posX", "Position X"], ["posY", "Position Y"], ["scale", "Scale"], ["rotation", "Rotation"], ["opacity", "Opacity"]].map(([k, label]) => `<option value="${k}">${label}</option>`).join("")}</select></label><textarea data-expression rows="3" placeholder="value + 10 * sin(t * 2 * pi)"></textarea><button class="tool-chip" data-action="expression">Apply expression</button><p>Variables: t, duration, value, pi. Arithmetic and sin, cos, tan, abs, min, max, sqrt, floor, ceil.</p></div>
    <p class="creator-status" role="status"></p>`;
  const status = root.querySelector<HTMLElement>(".creator-status")!;
  const selected = () => engine.snapshot.selectedClipId ? engine.findClip(engine.snapshot.selectedClipId)?.clip : undefined;
  const query = <T extends HTMLElement = HTMLInputElement>(key: string) => root.querySelector<T>(`[data-${key}]`)!;
  const patch = (values: Partial<Clip>, clipId = selected()?.id) => { if (!clipId) throw new Error("Select a clip first"); engine.dispatch("clip.creator", { clipId, patch: values }); };
  const show = (message: string) => { const next = phrase(message); if (status.textContent !== next) status.textContent = next; };
  const safe = async (operation: () => unknown) => { try { await operation(); show(""); } catch (error) { show(error instanceof Error ? error.message : String(error)); } };
  const points = root.querySelector<HTMLElement>(".speed-points")!;
  const pointRows: HTMLElement[] = [];
  const stacks = new Map<string, HTMLElement[]>();
  let catalog: { video: Array<{ id: string; name: string; parameters?: Record<string, number>; declarations?: ParamDeclaration[] }>; audio: Array<{ id: string; name: string }> } = { video: [], audio: [] };
  const choosePage = () => {
    for (const page of root.querySelectorAll<HTMLElement>("[data-group]")) page.hidden = page.dataset.group !== query<HTMLSelectElement>("page").value;
  };
  query("page").addEventListener("change", choosePage);
  const setValue = (input: HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement, value: string) => { if (document.activeElement !== input && input.value !== value) input.value = value; };
  const renderStack = (kind: "effects" | "audioEffects", clip?: Clip) => {
    const entries = clip?.[kind] ?? [];
    const target = query<HTMLElement>(kind === "effects" ? "effect-list" : "audio-list");
    const rows = stacks.get(kind) ?? [];
    while (rows.length > entries.length) rows.pop()!.remove();
    entries.forEach((entry, index) => {
      if (!rows[index]) {
        const row = document.createElement("div"); row.className = "processor-row";
        row.innerHTML = `<span></span><input type="range" min="0" max="1" step="0.01" aria-label="Strength"><button class="tool-chip" title="Move earlier">Up</button><button class="tool-chip">Remove</button>`;
        row.querySelector("input")!.addEventListener("change", event => void safe(() => {
          const next = structuredClone(selected()?.[kind] ?? []); next[index].amount = Number((event.target as HTMLInputElement).value); patch({ [kind]: next });
        }));
        const buttons = row.querySelectorAll("button");
        buttons[0].addEventListener("click", () => void safe(() => { const next = structuredClone(selected()?.[kind] ?? []); if (index) [next[index - 1], next[index]] = [next[index], next[index - 1]]; patch({ [kind]: next }); }));
        buttons[1].addEventListener("click", () => void safe(() => { const next = structuredClone(selected()?.[kind] ?? []); next.splice(index, 1); patch({ [kind]: next }); }));
        rows[index] = row; target.append(row);
      }
      const name = rows[index].querySelector("span")!;
      if (name.textContent !== entry.id) name.textContent = entry.id;
      setValue(rows[index].querySelector("input")!, String(entry.amount));
      if (kind === "effects") effectParameters(rows[index], entry, catalog.video.find(e => e.id === entry.id)?.declarations ?? [], (name, value) => void safe(() => {
        const next = structuredClone(selected()?.effects ?? []);
        if (!next[index]) return;
        next[index].params = { ...next[index].params, [name]: value };
        patch({ effects: next });
      }));
    });
    stacks.set(kind, rows);
  };
  const refill = () => {
    const clip = selected();
    const curve = clip?.speedCurve ?? [];
    while (pointRows.length > curve.length) pointRows.pop()!.remove();
    curve.forEach((point, index) => {
      if (!pointRows[index]) {
        const row = document.createElement("div"); row.className = "curve-point";
        row.innerHTML = `<input type="number" min="0" step="0.01" aria-label="Time in seconds"><input type="number" min="0.05" max="16" step="0.05" aria-label="Speed"><button class="tool-chip">Remove</button>`;
        row.addEventListener("change", () => void safe(() => {
          const current = selected(); if (!current) return;
          const next = structuredClone(current.speedCurve ?? []), inputs = row.querySelectorAll("input");
          next[index] = { t: Number(inputs[0].value), speed: Number(inputs[1].value) };
          engine.dispatch("clip.speed-curve", { clipId: current.id, points: next });
        }));
        row.querySelector("button")!.addEventListener("click", () => void safe(() => {
          const current = selected(); if (!current) return;
          const next = structuredClone(current.speedCurve ?? []); next.splice(index, 1);
          engine.dispatch("clip.speed-curve", { clipId: current.id, points: next });
        }));
        pointRows[index] = row; points.append(row);
      }
      const inputs = pointRows[index].querySelectorAll("input");
      setValue(inputs[0], String(point.t)); setValue(inputs[1], String(point.speed));
    });
    const max = Math.max(4, ...curve.map(p => p.speed));
    const path = curve.map((p, i) => `${i ? "L" : "M"}${p.t / (clip?.duration || 1) * 240},${90 - p.speed / max * 85}`).join(" ");
    const graph = root.querySelector(".speed-graph path")!;
    if (graph.getAttribute("d") !== path) graph.setAttribute("d", path);
    renderStack("effects", clip); renderStack("audioEffects", clip);
    setValue(query("volume"), String(clip?.volume ?? 1)); setValue(query("pan"), String(clip?.pan ?? 0));
    setValue(query<HTMLSelectElement>("transition"), clip?.transitionIn?.type ?? "");
    setValue(query("transition-duration"), String(clip?.transitionIn?.duration ?? 0.6));
    setValue(query<HTMLSelectElement>("cutout-model"), clip?.cutout?.model ?? "object-cutout");
    setValue(query("cutout-threshold"), String(clip?.cutout?.threshold ?? 0.5));
    setValue(query("cutout-feather"), String(clip?.cutout?.feather ?? 0.1));
    const prop = query<HTMLSelectElement>("expression-prop").value as KeyframeProp;
    setValue(query<HTMLTextAreaElement>("expression"), clip?.expressions?.[prop] ?? "");
    if (!clip) show("Select a clip to edit its tools");
  };
  query("expression-prop").addEventListener("change", refill);
  for (const key of ["volume", "pan"] as const) query(key).addEventListener("change", () => void safe(() => patch({ [key]: Number(query(key).value) })));
  root.addEventListener("click", event => {
    const action = (event.target as HTMLElement).closest<HTMLElement>("[data-action]")?.dataset.action;
    if (!action) return;
    void safe(async () => {
      const clip = selected(); if (!clip) throw new Error("Select a clip first");
      if (action === "speed-preset") engine.dispatch("clip.speed-curve", { clipId: clip.id, preset: query<HTMLSelectElement>("speed-preset").value });
      if (action === "speed-clear") engine.dispatch("clip.speed-curve", { clipId: clip.id, points: [] });
      if (action === "speed-add") engine.dispatch("clip.speed-curve", { clipId: clip.id, points: [...(clip.speedCurve ?? []), { t: Math.max(0, Math.min(clip.duration, engine.snapshot.playhead - clip.start)), speed: 1 }] });
      if (action === "motion") engine.dispatch("clip.motion", { clipId: clip.id, preset: query<HTMLSelectElement>("motion").value, duration: Number(query("motion-duration").value) });
      if (action === "effect-add") patch({ effects: [...(clip.effects ?? []), { id: query<HTMLSelectElement>("effect").value, amount: 1 }] });
      if (action === "audio-add") patch({ audioEffects: [...(clip.audioEffects ?? []), { id: query<HTMLSelectElement>("audio").value, amount: 1 }] });
      if (action === "transition") engine.dispatch("clip.transition", { clipId: clip.id, transition: query<HTMLSelectElement>("transition").value ? { type: query<HTMLSelectElement>("transition").value, duration: Number(query("transition-duration").value) } : null });
      if (action === "cutout") {
        const model = query<HTMLSelectElement>("cutout-model").value;
        const models = await api<Array<{ id: string; ready: boolean }>>("/api/models");
        if (!models.find(m => m.id === model)?.ready) throw new Error("Download this model using Studio > Local models first");
        patch({ cutout: { model, threshold: Number(query("cutout-threshold").value), feather: Number(query("cutout-feather").value), strokes: clip.cutout?.strokes ?? [] } }, clip.id);
      }
      if (action === "cutout-clear") patch({ cutout: undefined });
      if (action === "brush-undo" && clip.cutout) patch({ cutout: { ...clip.cutout, strokes: clip.cutout.strokes.slice(0, -1) } });
      if (action === "lut-clear") patch({ lutId: undefined });
      if (action === "shader-clear") patch({ shaderId: undefined });
      if (action === "expression") {
        const prop = query<HTMLSelectElement>("expression-prop").value as KeyframeProp;
        patch({ expressions: { ...clip.expressions, [prop]: query<HTMLTextAreaElement>("expression").value.trim() } });
      }
    });
  });
  query("lut").addEventListener("change", () => void safe(async () => {
    const file = query("lut").files?.[0], clipId = selected()?.id; if (!file || !clipId) return;
    const body = new FormData(); body.append("file", file);
    patch({ lutId: (await api("/api/assets/lut", body)).id }, clipId);
  }));
  query("shader").addEventListener("change", () => void safe(async () => {
    const file = query("shader").files?.[0], clipId = selected()?.id; if (!file || !clipId) return;
    patch({ shaderId: (await api("/api/assets/shader", { name: file.name, source: await file.text() })).id }, clipId);
  }));
  void api<typeof catalog>("/api/catalogue").then(result => {
    catalog = result;
    for (const [key, entries] of [["effect", catalog.video], ["audio", catalog.audio]] as const) {
      for (const entry of entries) { const option = document.createElement("option"); option.value = entry.id; option.textContent = phrase(entry.name); query<HTMLSelectElement>(key).append(option); }
    }
  }).catch(error => show(error.message));
  root.dataset.brush = "off";
  query("brush").addEventListener("change", () => { root.dataset.brush = query<HTMLSelectElement>("brush").value; });
  engine.subscribe((_state, changed) => { if (["clips", "clip-selection", "timeline"].includes(changed)) refill(); });
  refill();
  localizeElement(root);
  return root;
}
