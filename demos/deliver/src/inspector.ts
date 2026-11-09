import type { ProjectEngine } from "../../../frontend/src/engine/project";
import type { Clip, KeyframeProp } from "../../../frontend/src/engine/types";
import { getSource, onSources } from "../../../demo/src/media";
import { DeliverMixer, ducking, gainFor, measure, meterOf, renderMix, toDb } from "./audio";
import type { Loudness } from "./audio";
import { captionsOf } from "./captions";
import { COVER_SCALE, VERTICAL } from "../../../frontend/src/demos/woods";
import { PATHS } from "../../../frontend/src/demos/woods-paths";
import { analyseVideo, cropKeyframes } from "./reframe";
import type { Crop } from "./reframe";

export const TARGETS: Array<[string, string, number, number]> = [
  ["stream", "Streaming, -16 LUFS", -16, -1],
  ["shorts", "Shorts and reels, -14 LUFS", -14, -1],
  ["ebu", "EBU R128 broadcast, -23 LUFS", -23, -1],
  ["atsc", "ATSC A/85, -24 LKFS", -24, -2],
];

const TABS: Array<[string, string]> = [["mix", "Mix"], ["frame", "Frame"], ["caption", "Caption"]];
const VOLUME = "volume" as KeyframeProp;

export interface InspectorHooks {
  mixer: DeliverMixer;
  say: (text: string) => void;
  activate: (index: number) => void;
}

export interface MixApi {
  element: HTMLElement;
  target: () => [number, number];
  duck: () => boolean;
  setTarget: (id: string) => void;
  lastLoudness: () => Loudness | null;
  measure: () => Promise<Loudness>;
}

export function buildInspector(engine: ProjectEngine, hooks: InspectorHooks): MixApi {
  const { mixer, say } = hooks;
  const element = document.createElement("section");
  element.className = "pane pane-inspector";
  element.innerHTML = `
    <div class="inspector-head"><div class="seg">${TABS.map(([key, label], i) => `<button class="${i === 0 ? "is-active" : ""}" data-tab="${key}">${label}</button>`).join("")}</div></div>
    <div class="inspector-body">
      <div class="section" data-tab="mix"><div class="section-head">Levels</div>
        <div class="dl-body">
          ${["Voice", "Music"].map((name) => `<div class="dl-level" data-track="${name}"><span class="dl-name">${name}</span>
            <input class="prop-slide" type="range" min="-30" max="6" step="0.5" aria-label="${name} level" />
            <span class="dl-db"></span>
            <div class="dl-meter" aria-hidden="true"><span class="dl-rms"></span><span class="dl-peak"></span></div></div>`).join("")}
          <div class="dl-level" data-track="Master"><span class="dl-name">Master</span><span class="dl-fill"></span><span class="dl-db"></span>
            <div class="dl-meter" aria-hidden="true"><span class="dl-rms"></span><span class="dl-peak"></span></div></div>
        </div></div>
      <div class="section" data-tab="mix"><div class="section-head">Duck under speech</div>
        <div class="dl-body">
          <div class="dl-envelope"><canvas data-ref="envelope" aria-label="Music level over the film"></canvas></div>
          ${[["depth", "Music drops to", 5, 80, 5, 25, "%"], ["attack", "Attack", 0.05, 0.6, 0.05, 0.15, "s"], ["release", "Release", 0.1, 1.2, 0.1, 0.4, "s"], ["threshold", "Speech threshold", 0.005, 0.08, 0.005, 0.02, ""]]
            .map(([id, label, min, max, step, value, unit]) => `<label class="dl-slide"><span>${label}</span><input class="prop-slide" data-duck="${id}" type="range" min="${min}" max="${max}" step="${step}" value="${value}" /><output data-out="${id}">${value}${unit}</output></label>`).join("")}
          <div class="demo-row"><button class="tool-chip is-primary" data-ref="duck-apply">Duck the music</button><button class="tool-chip" data-ref="duck-clear">Remove</button></div>
          <div class="fx-status" data-ref="duck-note">Reads the voice clip, writes volume keyframes on the music clip.</div>
        </div></div>
      <div class="section" data-tab="mix"><div class="section-head">Loudness</div>
        <div class="dl-body">
          <label class="dl-field"><span>Target</span><select class="mini-select" data-ref="target" aria-label="Loudness target">${TARGETS.map(([id, name]) => `<option value="${id}">${name}</option>`).join("")}</select></label>
          <div class="dl-stats" data-ref="stats"><span>Integrated</span><b data-stat="integrated">not measured</b><span>True peak</span><b data-stat="truePeak"></b><span>Range</span><b data-stat="range"></b><span>Master trim</span><b data-stat="trim">0.0 dB</b></div>
          <div class="demo-row"><button class="tool-chip" data-ref="measure">Measure the mix</button><button class="tool-chip is-primary" data-ref="normalise">Normalise to target</button></div>
          <div class="fx-status" data-ref="loud-note">Measured offline on the rendered mix, K-weighted and gated as BS.1770 describes.</div>
        </div></div>
      <div class="section" data-tab="frame"><div class="section-head">Timeline format</div>
        <div class="dl-body">
          <div class="dl-stats"><span>Active</span><b data-ref="fmt-name"></b><span>Size</span><b data-ref="fmt-size"></b></div>
          <div class="demo-row"><button class="tool-chip" data-ref="go-talk">Talk 16:9</button><button class="tool-chip" data-ref="go-vertical">Vertical 9:16</button></div>
        </div></div>
      <div class="section" data-tab="frame"><div class="section-head">Reframe for vertical</div>
        <div class="dl-body">
          <p class="demo-hint" data-ref="reframe-hint"></p>
          <div class="demo-row"><button class="tool-chip is-primary" data-ref="reframe-engine">Engine path, all clips</button><button class="tool-chip" data-ref="reframe-clip">Analyse selected clip</button><button class="tool-chip" data-ref="reframe-all">Analyse all clips</button></div>
          <div class="dl-path"><canvas data-ref="path" aria-label="Crop position over the selected clip"></canvas></div>
          <div class="fx-status" data-ref="reframe-note"></div>
        </div></div>
      <div class="section" data-tab="caption"><div class="section-head">Caption text</div>
        <div class="dl-body">
          <div class="inspector-empty" data-ref="cap-empty">Select a caption on the timeline or in the Captions list.</div>
          <textarea class="demo-input dl-text-edit" data-ref="cap-text" rows="3" aria-label="Caption text" hidden></textarea>
          <div class="fx-status" data-ref="cap-note"></div>
        </div></div>
    </div>`;
  const ref = <T extends HTMLElement>(name: string) => element.querySelector<T>(`[data-ref="${name}"]`)!;
  const sections = element.querySelectorAll<HTMLElement>(".section");
  const setText = (node: HTMLElement, value: string) => {
    if (node.textContent !== value) node.textContent = value;
  };
  let tab = "mix";
  const showTab = () => sections.forEach((node) => {
    const hidden = node.dataset.tab !== tab;
    if (node.hidden !== hidden) node.hidden = hidden;
  });
  element.querySelector(".seg")!.addEventListener("click", (event) => {
    const button = (event.target as HTMLElement).closest<HTMLElement>("[data-tab]");
    if (!button) return;
    tab = button.dataset.tab!;
    element.querySelectorAll<HTMLElement>(".seg button").forEach((node) => node.classList.toggle("is-active", node === button));
    showTab();
    paintAll();
  });
  showTab();

  const timeline = () => engine.snapshot.timelines[engine.snapshot.activeTimeline];
  const trackClips = (name: string): Clip[] => timeline().tracks.find((track) => track.name === name)?.clips.filter((clip) => clip.kind === "audio") ?? [];
  const videoClips = (): Clip[] => timeline().tracks.find((track) => track.name === "Video")?.clips ?? [];

  const levelRow = (name: string) => element.querySelector<HTMLElement>(`.dl-level[data-track="${name}"]`)!;
  const dbOf = (name: string): number => {
    const first = trackClips(name)[0];
    return first ? Math.round(toDb(first.volume ?? 1) * 2) / 2 : 0;
  };
  const paintLevels = () => {
    for (const name of ["Voice", "Music"]) {
      const row = levelRow(name);
      const slider = row.querySelector<HTMLInputElement>("input")!;
      const value = dbOf(name);
      if (document.activeElement !== slider && slider.value !== String(value)) slider.value = String(value);
      setText(row.querySelector<HTMLElement>(".dl-db")!, `${value > 0 ? "+" : ""}${value.toFixed(1)} dB`);
    }
  };
  for (const name of ["Voice", "Music"]) {
    const slider = levelRow(name).querySelector<HTMLInputElement>("input")!;
    slider.addEventListener("input", () => {
      const volume = 10 ** (Number(slider.value) / 20);
      for (const clip of trackClips(name)) {
        const fresh = engine.findClip(clip.id)?.clip;
        if (fresh) engine.dispatch("clip.style", { clipId: clip.id, style: { ...structuredClone(fresh), volume } });
      }
      setText(levelRow(name).querySelector<HTMLElement>(".dl-db")!, `${Number(slider.value) > 0 ? "+" : ""}${Number(slider.value).toFixed(1)} dB`);
    });
  }

  const meterBuffer = new Float32Array(2048);
  const paintMeter = (row: HTMLElement, peak: number, rms: number) => {
    const scaleOf = (linear: number) => Math.max(0, Math.min(1, (toDb(linear) + 60) / 60));
    const rmsEl = row.querySelector<HTMLElement>(".dl-rms")!;
    const peakEl = row.querySelector<HTMLElement>(".dl-peak")!;
    const a = `scaleX(${scaleOf(rms).toFixed(3)})`;
    const b = `${(scaleOf(peak) * 100).toFixed(1)}%`;
    if (rmsEl.style.transform !== a) rmsEl.style.transform = a;
    if (peakEl.style.left !== b) peakEl.style.left = b;
  };
  const loop = () => {
    const state = engine.snapshot;
    if (state.playing) {
      const names = new Map(timeline().tracks.map((track) => [track.id, track.name]));
      let mix = 0;
      let mixRms = 0;
      for (const tap of mixer.taps) {
        const name = names.get(tap.trackId);
        const m = meterOf(tap.analyser, meterBuffer);
        mix = Math.max(mix, m.peak);
        mixRms = Math.sqrt(mixRms * mixRms + m.rms * m.rms);
        if (name === "Voice" || name === "Music") paintMeter(levelRow(name), m.peak, m.rms);
      }
      const gain = mixer.trim;
      paintMeter(levelRow("Master"), mix * gain, mixRms * gain);
    } else for (const name of ["Voice", "Music", "Master"]) paintMeter(levelRow(name), 0, 0);
    requestAnimationFrame(loop);
  };
  requestAnimationFrame(loop);

  const envelope = ref<HTMLCanvasElement>("envelope");
  const paintEnvelope = () => {
    const music = trackClips("Music")[0];
    const voice = trackClips("Voice")[0];
    const g = envelope.getContext("2d")!;
    const w = envelope.clientWidth || 280;
    const h = 56;
    const ratio = window.devicePixelRatio || 1;
    if (envelope.width !== Math.round(w * ratio) || envelope.height !== Math.round(h * ratio)) {
      envelope.width = Math.round(w * ratio);
      envelope.height = Math.round(h * ratio);
    }
    g.setTransform(ratio, 0, 0, ratio, 0, 0);
    g.clearRect(0, 0, w, h);
    const style = getComputedStyle(envelope);
    const line = style.getPropertyValue("--cue").trim() || "#ff7a1a";
    const faint = style.getPropertyValue("--ink-faint").trim() || "#888";
    const length = Math.max(1, engine.snapshot.duration);
    if (voice) {
      const source = getSource(voice.mediaId);
      if (source?.peaks) {
        g.fillStyle = faint;
        g.globalAlpha = 0.35;
        const per = 50;
        for (let x = 0; x < w; x += 1) {
          const t = (x / w) * length - voice.start;
          const i = Math.floor((t + (voice.sourceIn ?? 0)) * per);
          if (t < 0 || t > voice.duration || i < 0 || i >= source.peaks.length) continue;
          const amp = Math.min(1, source.peaks[i] * 1.6) * h * 0.45;
          g.fillRect(x, h - amp, 1, amp);
        }
        g.globalAlpha = 1;
      }
    }
    if (music) {
      g.strokeStyle = line;
      g.lineWidth = 1.6;
      g.beginPath();
      for (let x = 0; x <= w; x += 1) {
        const t = (x / w) * length;
        const local = t - music.start;
        const level = local < 0 || local > music.duration ? 0 : Math.min(1, (music.volume ?? 1) * keyedVolume(music, local));
        const y = 4 + (1 - level) * (h - 8);
        if (x) g.lineTo(x, y);
        else g.moveTo(x, y);
      }
      g.stroke();
    }
  };
  const keyedVolume = (clip: Clip, local: number): number => {
    const points = (clip.keyframes ?? []).filter((k) => k.props[VOLUME] !== undefined).sort((a, b) => a.t - b.t);
    if (!points.length) return 1;
    if (local <= points[0].t) return points[0].props[VOLUME]!;
    const last = points[points.length - 1];
    if (local >= last.t) return last.props[VOLUME]!;
    for (let i = 0; i < points.length - 1; i += 1) {
      const a = points[i];
      const b = points[i + 1];
      if (local >= a.t && local < b.t) {
        const p = b.t === a.t ? 0 : (local - a.t) / (b.t - a.t);
        return a.props[VOLUME]! + (b.props[VOLUME]! - a.props[VOLUME]!) * p;
      }
    }
    return 1;
  };

  const duckValue = (id: string): number => Number(element.querySelector<HTMLInputElement>(`[data-duck="${id}"]`)!.value);
  const units: Record<string, string> = { depth: "%", attack: "s", release: "s", threshold: "" };
  element.querySelectorAll<HTMLInputElement>("[data-duck]").forEach((input) => {
    input.addEventListener("input", () => setText(element.querySelector<HTMLElement>(`[data-out="${input.dataset.duck}"]`)!, `${input.value}${units[input.dataset.duck!]}`));
  });
  const applyDuck = (): boolean => {
    const music = trackClips("Music")[0];
    const voice = trackClips("Voice")[0];
    const buffer = getSource(voice?.mediaId)?.buffer;
    if (!music || !voice || !buffer) {
      say("The voice is still loading");
      return false;
    }
    const result = ducking(buffer, voice.sourceIn ?? 0, voice.duration, duckValue("depth") / 100, duckValue("attack"), duckValue("release"), duckValue("threshold"));
    const shift = voice.start - music.start;
    const frames = result.keyframes.map((frame) => ({ ...frame, t: Math.round((frame.t + shift) * 1000) / 1000 })).filter((frame) => frame.t <= music.duration);
    engine.dispatch("clip.keyframes.replace", { clipId: music.id, keyframes: frames });
    setText(ref("duck-note"), `${result.regions.length} stretches of speech found, ${frames.length} volume keyframes written on the music`);
    say("Music ducked under the voice");
    return true;
  };
  ref("duck-apply").addEventListener("click", applyDuck);
  ref("duck-clear").addEventListener("click", () => {
    const music = trackClips("Music")[0];
    if (!music) return;
    engine.dispatch("clip.keyframes.replace", { clipId: music.id, keyframes: [] });
    setText(ref("duck-note"), "Ducking removed");
  });

  let loudness: Loudness | null = null;
  const targetSelect = ref<HTMLSelectElement>("target");
  const target = (): [number, number] => {
    const found = TARGETS.find(([id]) => id === targetSelect.value) ?? TARGETS[0];
    return [found[2], found[3]];
  };
  const stat = (name: string) => element.querySelector<HTMLElement>(`[data-stat="${name}"]`)!;
  const paintLoudness = () => {
    setText(stat("integrated"), loudness ? `${loudness.integrated.toFixed(1)} LUFS` : "not measured");
    setText(stat("truePeak"), loudness ? `${loudness.truePeak.toFixed(1)} dBTP` : "");
    setText(stat("range"), loudness ? `${loudness.range.toFixed(1)} LU` : "");
    setText(stat("trim"), `${toDb(mixer.trim).toFixed(1)} dB`);
  };
  const run = async (): Promise<Loudness> => {
    setText(ref("loud-note"), "Rendering the mix");
    const rendered = await renderMix(engine.snapshot, engine.snapshot.duration, mixer.trim);
    loudness = measure(rendered);
    paintLoudness();
    const [goal, ceiling] = target();
    const need = gainFor(goal, ceiling, loudness);
    setText(ref("loud-note"), Math.abs(need) < 0.1 ? "On target" : `${need > 0 ? "Raise" : "Lower"} by ${Math.abs(need).toFixed(1)} dB to reach ${goal} LUFS within ${ceiling} dBTP`);
    return loudness;
  };
  ref("measure").addEventListener("click", () => void run());
  ref("normalise").addEventListener("click", () => void (async () => {
    mixer.trim = 1;
    const before = await run();
    const [goal, ceiling] = target();
    mixer.trim = 10 ** (gainFor(goal, ceiling, before) / 20);
    const after = await run();
    setText(ref("loud-note"), `Master trim ${toDb(mixer.trim).toFixed(1)} dB: ${after.integrated.toFixed(1)} LUFS, ${after.truePeak.toFixed(1)} dBTP`);
    say(`Mix normalised to ${goal} LUFS`);
  })());
  targetSelect.addEventListener("change", () => {
    if (loudness) {
      const [goal, ceiling] = target();
      const need = gainFor(goal, ceiling, { ...loudness, integrated: loudness.integrated - toDb(1), truePeak: loudness.truePeak });
      setText(ref("loud-note"), `Target ${goal} LUFS within ${ceiling} dBTP: trim ${need.toFixed(1)} dB from the current measurement`);
    }
  });

  const paintFormat = () => {
    const s = engine.snapshot;
    setText(ref("fmt-name"), timeline().name);
    setText(ref("fmt-size"), `${s.width} x ${s.height}`);
    const vertical = s.height > s.width;
    ref("go-talk").classList.toggle("is-primary", !vertical);
    ref("go-vertical").classList.toggle("is-primary", vertical);
    for (const name of ["reframe-engine", "reframe-clip", "reframe-all"]) ref<HTMLButtonElement>(name).disabled = !vertical;
    setText(ref("reframe-hint"), vertical
      ? "A 16:9 shot is shown through a 9:16 window. The window follows motion and detail, smoothed forward and backward so it lags rather than twitches."
      : "Open the vertical timeline to reframe: the 16:9 clips are cropped to 9:16 there, and the Talk timeline is left as it is.");
  };
  ref("go-talk").addEventListener("click", () => hooks.activate(0));
  ref("go-vertical").addEventListener("click", () => hooks.activate(1));

  const apply = (clip: Clip, crops: Crop[]) => {
    const frames = cropKeyframes(crops.filter((crop) => crop.t * 0.5 < clip.duration), COVER_SCALE, VERTICAL.width, VERTICAL.width);
    engine.dispatch("clip.keyframes.replace", { clipId: clip.id, keyframes: frames });
  };
  const pathOf = (clip: Clip): Crop[] => (PATHS[clip.mediaId ?? ""] ?? []).map(([t, x, w]) => ({ t: t * 2, x, w }));
  ref("reframe-engine").addEventListener("click", () => {
    for (const clip of videoClips()) apply(clip, pathOf(clip));
    setText(ref("reframe-note"), "Paths from the engine's own reframe function, written as scale and position keyframes");
  });
  const analyse = async (clips: Clip[]) => {
    for (const [index, clip] of clips.entries()) {
      const source = getSource(clip.mediaId);
      if (!source?.url) continue;
      const crops = await analyseVideo(source.url, source.duration, (f) => setText(ref("reframe-note"), `Clip ${index + 1} of ${clips.length}: ${Math.round(f * 100)}%`));
      apply(clip, crops);
    }
    setText(ref("reframe-note"), `Analysed ${clips.length} clip${clips.length === 1 ? "" : "s"} in this page`);
  };
  ref("reframe-clip").addEventListener("click", () => {
    const id = engine.snapshot.selectedClipId;
    const clip = id ? engine.findClip(id)?.clip : null;
    if (!clip || clip.kind !== "video") {
      say("Select a video clip first");
      return;
    }
    void analyse([clip]);
  });
  ref("reframe-all").addEventListener("click", () => void analyse(videoClips()));

  const pathCanvas = ref<HTMLCanvasElement>("path");
  const paintPath = () => {
    const id = engine.snapshot.selectedClipId;
    const clip = id ? engine.findClip(id)?.clip : null;
    const g = pathCanvas.getContext("2d")!;
    const w = pathCanvas.clientWidth || 280;
    const h = 40;
    const ratio = window.devicePixelRatio || 1;
    if (pathCanvas.width !== Math.round(w * ratio) || pathCanvas.height !== Math.round(h * ratio)) {
      pathCanvas.width = Math.round(w * ratio);
      pathCanvas.height = Math.round(h * ratio);
    }
    g.setTransform(ratio, 0, 0, ratio, 0, 0);
    g.clearRect(0, 0, w, h);
    const style = getComputedStyle(pathCanvas);
    g.strokeStyle = style.getPropertyValue("--edge-strong").trim() || "#444";
    g.strokeRect(0.5, 0.5, w - 1, h - 1);
    if (!clip || clip.kind !== "video" || !clip.keyframes?.length) return;
    const cue = style.getPropertyValue("--cue").trim() || "#ff7a1a";
    g.strokeStyle = cue;
    g.lineWidth = 1.6;
    g.beginPath();
    const points = clip.keyframes.filter((k) => k.props.posX !== undefined).sort((a, b) => a.t - b.t);
    points.forEach((k, i) => {
      const centre = 0.5 - (k.props.posX! / (k.props.scale ?? COVER_SCALE));
      const x = (k.t / clip.duration) * w;
      const y = 4 + centre * (h - 8);
      if (i) g.lineTo(x, y);
      else g.moveTo(x, y);
    });
    g.stroke();
  };

  const capText = ref<HTMLTextAreaElement>("cap-text");
  const paintCaption = () => {
    const id = engine.snapshot.selectedClipId;
    const clip = id ? engine.findClip(id)?.clip : null;
    const isCaption = !!clip && clip.kind === "text" && captionsOf(engine.snapshot).some((c) => c.id === clip.id);
    if (ref("cap-empty").hidden !== isCaption) ref("cap-empty").hidden = isCaption;
    if (capText.hidden !== !isCaption) capText.hidden = !isCaption;
    if (!isCaption || !clip) return;
    const text = clip.textStyle?.content ?? clip.label;
    if (document.activeElement !== capText && capText.value !== text) capText.value = text;
    setText(ref("cap-note"), `${clip.start.toFixed(2)} s for ${clip.duration.toFixed(2)} s, ${clip.words?.length ?? 0} words timed by the engine's rule`);
  };
  capText.addEventListener("input", () => {
    const id = engine.snapshot.selectedClipId;
    if (id) engine.dispatch("clip.text", { clipId: id, patch: { content: capText.value } });
  });

  const paintAll = () => {
    paintLevels();
    paintFormat();
    paintLoudness();
    if (tab === "mix") paintEnvelope();
    if (tab === "frame") paintPath();
    if (tab === "caption") paintCaption();
  };
  engine.subscribe((_s, changed) => {
    if (changed === "playhead" || changed === "transport") return;
    paintAll();
  });
  window.addEventListener("resize", paintAll);
  onSources(paintAll);
  document.addEventListener("deliver-demo:theme", paintAll);
  paintAll();

  return {
    element,
    target,
    duck: applyDuck,
    setTarget: (id) => {
      targetSelect.value = id;
    },
    lastLoudness: () => loudness,
    measure: run,
  };
}
