import type { ProjectEngine } from "../engine/project";
import { api } from "../engine/api";
import { t } from "../i18n";

export function installTracking(root: HTMLElement, engine: ProjectEngine): void {
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
      void api("/api/track/clip", { project, source: source.id, target: project.selectedClipId, time: project.playhead, point }).then(result => {
        if (engine.snapshot.timelines[engine.snapshot.activeTimeline].id !== timelineId || !engine.findClip(project.selectedClipId!)) throw new Error("The target timeline changed during tracking");
        engine.dispatch("clip.keyframes.set", { clipId: project.selectedClipId, keyframes: result.keyframes });
        say(`${result.keyframes.length} ${t("track.done")}`);
      }).catch(error => say(error.message || t("track.fail")));
    }, { once: true, signal: pick.signal });
    document.addEventListener("keydown", event => { if (event.key === "Escape") { pick?.abort(); say(t("track.hint")); } }, { signal: pick.signal });
  });
}
