import type { ProjectEngine } from "../engine/project";
import { api } from "../engine/api";
import { t } from "../i18n";
import { openPlanarWorkspace } from "./planar-workspace";

// Whether a pinned clip also grows and turns with the subject; kept while the
// inspector redraws, so the choice holds from one clip to the next.
const follow = { scale: false, rotation: false };

export function installTracking(root: HTMLElement, engine: ProjectEngine): void {
  for (const [key, ref] of [["scale", "track-scale"], ["rotation", "track-rotation"]] as const) {
    const toggle = root.querySelector<HTMLElement>(`[data-ref="${ref}"]`);
    if (!toggle) continue;
    toggle.classList.toggle("is-on", follow[key]);
    toggle.addEventListener("click", () => { follow[key] = toggle.classList.toggle("is-on"); });
  }
  root.querySelector<HTMLElement>('[data-ref="matte-remove"]')?.addEventListener("click", () => {
    const id = engine.snapshot.selectedClipId;
    if (id) engine.dispatch("clip.planarMatte", { clipId: id, planarMatte: null });
  });
  // a clip's corner pin (from a planar layer, P3) taken off: its own place, size and turn back in charge
  root.querySelector<HTMLElement>('[data-ref="pin-remove"]')?.addEventListener("click", () => {
    const id = engine.snapshot.selectedClipId;
    if (id) engine.dispatch("clip.cornerPin", { clipId: id, cornerPin: null });
  });
  // the Track workspace: planar tracking of the selected video clip (planar-workspace.ts)
  root.querySelector<HTMLElement>('[data-ref="planar-btn"]')?.addEventListener("click", () => {
    const project = engine.snapshot;
    const clip = project.selectedClipId ? engine.findClip(project.selectedClipId)?.clip : undefined;
    const hint = root.querySelector<HTMLElement>('[data-ref="track-hint"]');
    if (!clip || clip.kind !== "video" || !clip.mediaId) { if (hint) hint.textContent = t("planar.needVideo"); return; }
    engine.pause();
    openPlanarWorkspace(engine, clip.id);
  });
  const button = root.querySelector<HTMLElement>('[data-ref="track-btn"]')!;
  const hint = root.querySelector<HTMLElement>('[data-ref="track-hint"]')!;
  let pick: AbortController | undefined;
  const say = (text: string) => { if (hint.textContent !== text) hint.textContent = text; };
  button.addEventListener("click", () => {
    pick?.abort(); engine.pause();
    const project = structuredClone(engine.snapshot), timelineId = project.timelines[project.activeTimeline].id;
    if (!project.selectedClipId) { say(t("track.needclip")); return; }
    const source = project.timelines[project.activeTimeline].tracks.filter(track => !track.hidden).flatMap(track => track.clips).find(c => c.kind === "video" && c.mediaId && c.start <= project.playhead && c.start + c.duration > project.playhead);
    if (!source) { say(t("track.nosource")); return; }
    const canvas = document.querySelector<HTMLCanvasElement>(".render-canvas"); if (!canvas) return;
    const creator = document.querySelector<HTMLElement>(".creator-panel");
    if (creator) { creator.dataset.brush = "off"; creator.querySelector<HTMLSelectElement>("[data-brush]")!.value = "off"; }
 
    pick = new AbortController();
    const stage = canvas.parentElement!;
    stage.dataset.picking = "true";
    pick.signal.addEventListener("abort", () => { delete stage.dataset.picking; }, { once: true });
    say(t("track.pick"));
    canvas.addEventListener("click", event => {
      pick?.abort();
      const box = canvas.getBoundingClientRect();
      const point = [(event.clientX - box.left) / box.width, (event.clientY - box.top) / box.height];
      say(t("track.running"));
      void api("/api/track/clip", { project, source: source.id, target: project.selectedClipId, time: project.playhead, point,
        follow: ["position", ...(follow.scale ? ["scale"] : []), ...(follow.rotation ? ["rotation"] : [])] }).then(result => {
        if (engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timelineId || !engine.findClip(project.selectedClipId!)) throw new Error("The target timeline changed during tracking");
        engine.dispatch("clip.keyframes.set", { clipId: project.selectedClipId, keyframes: result.keyframes });
        say(`${result.keyframes.length} ${t("track.done")}`);
      }).catch(error => say(error.message || t("track.fail")));
    }, { once: true, signal: pick.signal });
    document.addEventListener("keydown", event => { if (event.key === "Escape") { pick?.abort(); say(t("track.hint")); } }, { signal: pick.signal });
  });
}
