import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";
import type { Clip, DeviceSettings, KeyframeProp } from "../engine/types";
import { api } from "../engine/api";
import { propPoints, samplePoints } from "../engine/keyframes";
import { icon } from "./icons";
import { t } from "../i18n";

// The Device section of the inspector, for clips of kind device (the device layer: backend/app/device_layer.py).
// Built once; the rows that depend on the model (screens, poses, backlight) are rebuilt only when the model changes,
// every value is written in place. Its own data attributes (data-dev...) keep it clear of the inspector's handlers.

interface Articulation { name: string; closedDeg: number; maxDeg: number; openDeg: number }
interface Screen { slot: string; pixels: [number, number] }
interface Device {
  id: string;
  kind: string;
  finish: string;
  finishes: Record<string, { frame: [number, number, number] }>;
  screens: Screen[];
  articulations: Articulation[];
  backlight: unknown;
}

// name -> [where it lives in the block, default, min, max, step, unit]
const NUMBERS: Record<string, [string | null, number, number, number, number, string]> = {
  yaw: ["camera", 25, -180, 180, 1, "°"],
  pitch: ["camera", 12, -60, 85, 1, "°"],
  distance: ["camera", 1, 0.1, 3, 0.01, "x"],
  fov: ["camera", 30, 10, 75, 1, "°"],
  roll: ["camera", 0, -180, 180, 1, "°"],
  backlight: [null, 0.6, 0, 2, 0.05, ""],
  exposure: [null, 1, 0.3, 2.5, 0.05, ""],
  shadow: [null, 0.6, 0, 1, 0.05, ""],
  light: [null, 0, -180, 180, 1, "°"],
};
const POSE_NAMES = ["lid", "fold", "stand"];
let library: Promise<Device[]> | null = null;

export function deviceLibrary(): Promise<Device[]> {
  library ??= api<{ devices: Device[] }>("/api/devices", undefined, "GET").then((r) => r.devices);
  return library;
}

const display = (c: number) => Math.round(255 * Math.min(1, c <= 0.0031308 ? c * 12.92 : 1.055 * Math.pow(c, 1 / 2.4) - 0.055));

function sliderRow(name: string, label: string, min: number, max: number, step: number, unit: string): string {
  return `
    <div class="prop-row has-slide" data-dev-row="${name}">
      <span>${label}</span>
      <span class="num-field"><input data-dev="${name}" /><span class="unit">${unit}</span></span>
      <span class="prop-aux"><button class="iconbtn kf-btn" data-dev-kf="${name}" title="${t("kf.at")}">${icon("diamond")}</button></span>
      <input class="prop-slide" type="range" data-dev-slide="${name}" min="${min}" max="${max}" step="${step}" aria-label="${label}" />
    </div>`;
}

/** Adds a device mockup clip at the playhead on a new top track, and selects it. */
export async function addDeviceClip(engine: ProjectEngine): Promise<void> {
  const devices = await deviceLibrary();
  const first = devices.find((d) => d.kind === "phone") ?? devices[0];
  if (!first) return;
  engine.dispatch("track.insert", { index: 0, name: t("dev.title") });
  const clip = {
    id: crypto.randomUUID(),
    kind: "device",
    label: first.id,
    start: engine.snapshot.playhead,
    duration: 5,
    device: { id: first.id, finish: first.finish },
  } as unknown as Clip;
  engine.dispatch("clip.add", { trackIndex: 0, clip });
  engine.dispatch("clip.select", clip.id);
}

export function mountDeviceSection(pane: HTMLElement, engine: ProjectEngine, bin: MediaBin): void {
  const body = pane.querySelector(".inspector-body");
  if (!body) return;
  const section = document.createElement("div");
  section.className = "section device-section";
  section.dataset.section = "device";
  section.hidden = true;
  section.innerHTML = `
    <div class="section-head">${t("dev.title")} ${icon("chevD")}</div>
    <div class="prop-row"><span>${t("dev.model")}</span><select class="mini-select" data-dev-model aria-label="${t("dev.model")}"></select><span class="prop-aux"></span></div>
    <div class="prop-row"><span>${t("dev.finish")}</span><span class="device-swatches" data-dev-finishes></span><span class="prop-aux"></span></div>
    <div data-dev-screens></div>
    <div data-dev-poses></div>
    ${["yaw", "pitch", "distance", "fov", "roll"].map((n) => sliderRow(n, t(`dev.${n}`), NUMBERS[n][2], NUMBERS[n][3], NUMBERS[n][4], NUMBERS[n][5])).join("")}
    ${["backlight", "exposure", "shadow", "light"].map((n) => sliderRow(n, t(`dev.${n}`), NUMBERS[n][2], NUMBERS[n][3], NUMBERS[n][4], NUMBERS[n][5])).join("")}`;
  body.querySelector(".inspector-empty")?.after(section);
  const model = section.querySelector<HTMLSelectElement>("[data-dev-model]")!;
  const finishes = section.querySelector<HTMLElement>("[data-dev-finishes]")!;
  const screensBox = section.querySelector<HTMLElement>("[data-dev-screens]")!;
  const posesBox = section.querySelector<HTMLElement>("[data-dev-poses]")!;
  let devices: Device[] = [];
  let builtFor = "";

  const selected = (): Clip | null => {
    const id = engine.snapshot.selectedClipId;
    const found = id ? engine.findClip(id) : null;
    return found && found.clip.kind === "device" && found.clip.device ? found.clip : null;
  };
  const info = (clip: Clip) => devices.find((d) => d.id === clip.device!.id);
  const local = (clip: Clip) => Math.max(0, Math.min(clip.duration, engine.snapshot.playhead - clip.start));
  const keyed = (clip: Clip, name: string) => propPoints(clip, `device.${name}` as KeyframeProp);
  const base = (clip: Clip, name: string): number | undefined => {
    const block = clip.device as unknown as Record<string, Record<string, number> | number | undefined>;
    if (POSE_NAMES.includes(name)) {
      return (block.pose as Record<string, number> | undefined)?.[name] ?? info(clip)?.articulations.find((a) => a.name === name)?.openDeg;
    }
    const [group, fallback] = NUMBERS[name];
    const value = group ? (block[group] as Record<string, number> | undefined)?.[name] : (block[name] as number | undefined);
    return value ?? fallback;
  };
  const value = (clip: Clip, name: string) => samplePoints(keyed(clip, name), local(clip)) ?? base(clip, name) ?? 0;

  const write = (clip: Clip, name: string, v: number) => {
    if (keyed(clip, name).length) {
      engine.dispatch("clip.keyframes.set", { clipId: clip.id, keyframes: [{ t: local(clip), props: { [`device.${name}`]: v } }] });
      return;
    }
    const patch = POSE_NAMES.includes(name)
      ? { pose: { [name]: v } }
      : NUMBERS[name][0]
        ? { [NUMBERS[name][0] as string]: { [name]: v } }
        : { [name]: v };
    engine.dispatch("clip.device", { clipId: clip.id, patch });
  };

  const sourceOptions = () => {
    const state = engine.snapshot;
    const media = bin.all.filter((m) => m.kind === "video" || m.kind === "image");
    const timelines = state.timelines.filter((_, i) => i !== state.activeTimeline);
    return `<option value="">${t("dev.none")}</option>`
      + media.map((m) => `<option value="media:${m.id}">${m.name}</option>`).join("")
      + timelines.map((tl) => `<option value="timeline:${tl.id}">${t("dev.timeline").replace("{name}", tl.name)}</option>`).join("");
  };

  const build = (clip: Clip) => {
    const device = info(clip);
    if (!device) return;
    builtFor = device.id;
    finishes.innerHTML = Object.entries(device.finishes)
      .map(([name, spec]) => `<button type="button" class="device-swatch" data-dev-finish="${name}" title="${name}" aria-label="${name}" style="background: rgb(${spec.frame.map(display).join(",")})"></button>`)
      .join("");
    screensBox.innerHTML = device.screens
      .map((s) => `
        <div class="prop-row"><span>${t(s.slot === "cover" ? "dev.cover" : "dev.inner")}</span><select class="mini-select" data-dev-source="${s.slot}" aria-label="${t(s.slot === "cover" ? "dev.cover" : "dev.inner")}">${sourceOptions()}</select>
          <span class="prop-aux"><select class="mini-select" data-dev-fit="${s.slot}" aria-label="${t("dev.fit")}"><option value="cover">${t("dev.fill")}</option><option value="contain">${t("dev.whole")}</option></select></span></div>`)
      .join("");
    posesBox.innerHTML = device.articulations.map((a) => sliderRow(a.name, t(`dev.${a.name}`), a.closedDeg, a.maxDeg, 1, "°")).join("");
    const backlightRow = section.querySelector<HTMLElement>('[data-dev-row="backlight"]');
    if (backlightRow) backlightRow.hidden = !device.backlight;
  };

  const sync = () => {
    const clip = selected();
    if (section.hidden !== !clip) section.hidden = !clip;
    if (!clip || !devices.length) return;
    if (model.options.length !== devices.length) {
      model.innerHTML = devices.map((d) => `<option value="${d.id}">${d.id}</option>`).join("");
    }
    if (builtFor !== clip.device!.id) build(clip);
    if (model.value !== clip.device!.id) model.value = clip.device!.id;
    const finish = clip.device!.finish ?? info(clip)?.finish;
    for (const swatch of finishes.querySelectorAll<HTMLElement>("[data-dev-finish]")) swatch.classList.toggle("is-on", swatch.dataset.devFinish === finish);
    for (const select of screensBox.querySelectorAll<HTMLSelectElement>("[data-dev-source]")) {
      const slot = select.dataset.devSource as "inner" | "cover";
      const shown = clip.device!.screens?.[slot];
      const wanted = shown?.mediaId ? `media:${shown.mediaId}` : shown?.timelineId ? `timeline:${shown.timelineId}` : "";
      if (document.activeElement !== select && select.value !== wanted) {
        if (![...select.options].some((o) => o.value === wanted)) select.innerHTML = sourceOptions();
        select.value = wanted;
      }
      const fit = section.querySelector<HTMLSelectElement>(`[data-dev-fit="${slot}"]`);
      if (fit && fit.value !== (shown?.fit ?? "cover")) fit.value = shown?.fit ?? "cover";
    }
    const at = local(clip);
    for (const input of section.querySelectorAll<HTMLInputElement>("input[data-dev]")) {
      const name = input.dataset.dev!;
      const v = Math.round(value(clip, name) * 100) / 100;
      if (document.activeElement !== input && input.value !== String(v)) input.value = String(v);
      const slide = section.querySelector<HTMLInputElement>(`[data-dev-slide="${name}"]`);
      if (slide && document.activeElement !== slide && slide.value !== String(v)) slide.value = String(v);
      const on = keyed(clip, name).some((k) => Math.abs(k.t - at) < 0.5 / engine.snapshot.fps);
      section.querySelector(`[data-dev-kf="${name}"]`)?.classList.toggle("is-on", on);
    }
  };

  section.addEventListener("change", (event) => {
    const clip = selected();
    const target = event.target as HTMLInputElement | HTMLSelectElement;
    if (!clip) return;
    if (target === model) {
      const next = devices.find((d) => d.id === model.value);
      if (!next) return;
      const cover = next.screens.some((s) => s.slot === "cover");
      engine.dispatch("clip.device", { clipId: clip.id, patch: { id: next.id, finish: next.finish, pose: null, ...(cover ? {} : { screens: { cover: null } }) } });
      return;
    }
    if (target.dataset.devSource || target.dataset.devFit) {
      const slot = (target.dataset.devSource ?? target.dataset.devFit) as "inner" | "cover";
      const select = section.querySelector<HTMLSelectElement>(`[data-dev-source="${slot}"]`)!;
      const fit = section.querySelector<HTMLSelectElement>(`[data-dev-fit="${slot}"]`)!.value;
      const [kind, id] = select.value.split(":");
      const source = !select.value ? null : kind === "media" ? { mediaId: id, fit } : { timelineId: id, fit };
      engine.dispatch("clip.device", { clipId: clip.id, patch: { screens: { [slot]: source } } });
      return;
    }
    const name = target.dataset.dev ?? target.dataset.devSlide;
    if (name) {
      const v = Number(target.value);
      if (Number.isFinite(v)) write(clip, name, v);
    }
  });
  section.addEventListener("input", (event) => {
    const target = event.target as HTMLInputElement;
    const name = target.dataset.devSlide;
    if (!name) return;
    const number = section.querySelector<HTMLInputElement>(`input[data-dev="${name}"]`);
    if (number && number.value !== target.value) number.value = target.value;
  });
  section.addEventListener("click", (event) => {
    const clip = selected();
    const target = event.target as HTMLElement;
    if (!clip) return;
    const swatch = target.closest<HTMLElement>("[data-dev-finish]");
    if (swatch) {
      engine.dispatch("clip.device", { clipId: clip.id, patch: { finish: swatch.dataset.devFinish } });
      return;
    }
    const key = target.closest<HTMLElement>("[data-dev-kf]")?.dataset.devKf;
    if (key) engine.dispatch("clip.keyframes.set", { clipId: clip.id, keyframes: [{ t: local(clip), props: { [`device.${key}`]: value(clip, key) } }] });
  });

  void deviceLibrary().then((list) => { devices = list; sync(); }).catch(() => {});
  engine.subscribe(() => sync());
  bin.subscribe(() => { builtFor = ""; sync(); });
}

export type { DeviceSettings };
