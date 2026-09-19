import { trackControls } from "./track-controls";
import { installTrackHeightGrip } from "./track-height";
import type { ProjectEngine } from "../engine/project";
import type { MediaBin } from "../engine/media";

export function reconcileTimelineStructure(root: HTMLElement, engine: ProjectEngine, bin: MediaBin, lanes: HTMLElement[], width: number, scale: number): void {
  const state = engine.snapshot;
  const tracks = state.timelines[state.activeTimeline].tracks;
  const grid = root.querySelector<HTMLElement>('[data-ref="grid"]')!;
  while (lanes.length > tracks.length) {
    const lane = lanes.pop()!; lane.previousElementSibling?.remove(); lane.remove();
  }
  while (lanes.length < tracks.length) {
    const index = lanes.length;
    const header = document.createElement("div"); header.className = "track-head";
    const name = document.createElement("span"); name.className = "name"; header.append(name);
    const lane = document.createElement("div"); lane.className = "lane"; lane.style.width = `${width}px`;
    lane.addEventListener("dragover", event => { if (event.dataTransfer?.types.includes("application/x-formcut-media")) { event.preventDefault(); event.dataTransfer.dropEffect = "copy"; } });
    lane.addEventListener("drop", event => {
      const id = event.dataTransfer?.getData("application/x-formcut-media");
      const media = id ? bin.find(id) : undefined; if (!media) return;
      event.preventDefault();
      const start = Math.max(0, (event.clientX - lane.getBoundingClientRect().left) / Number(root.dataset.scale || scale));
      engine.dispatch("clip.add", { trackIndex: index, clip: { id: crypto.randomUUID(), kind: media.kind, label: media.name, start, duration: Math.max(0.1, media.duration), mediaId: media.id } });
    });
    grid.append(header, lane); lanes.push(lane);
  }
  tracks.forEach((track, index) => {
    const header = lanes[index].previousElementSibling as HTMLElement;
    if (!header.querySelector(".track-grip")) installTrackHeightGrip(header, lanes[index], index);
    const name = header.querySelector(".name");
    trackControls(lanes[index].previousElementSibling as HTMLElement, index, engine);
    if (name && name.textContent !== track.name) name.textContent = track.name;
  });
  // Tabs live in the scrolling strip, not in the row beside it; appending them
  // to the row left every new timeline outside the strip, which collapsed the
  // strip to nothing and defeated its scrolling.
  const tabs = root.querySelector<HTMLElement>('[data-ref="tab-strip"]')
    ?? root.querySelector<HTMLElement>('[data-ref="tabs"]')!;
  const existing = [...tabs.querySelectorAll<HTMLElement>(".tl-tab")];
  while (existing.length > state.timelines.length) existing.pop()!.remove();
  state.timelines.forEach((timeline, index) => {
    let button = existing[index];
    if (!button) { button = document.createElement("button"); button.className = "tl-tab"; button.dataset.tl = String(index); tabs.append(button); }
    if (button.querySelector("input")) return;   // a rename is in progress
    if (button.textContent !== timeline.name) button.textContent = timeline.name;
    if (button.title !== timeline.name) button.title = timeline.name;
    button.classList.toggle("is-active", index === state.activeTimeline);
  });
}
