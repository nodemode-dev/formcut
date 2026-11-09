// The three repository demos (demo/, demos/grade, demos/deliver), opened inside the app as a new
// unsaved project. Each film is built by the same code its browser demo uses; the engine seeds the
// demo's media (shipped in the built interface under demos/<id>/) into the library once, and each
// clip's demo media id is swapped for the library item's id.
import { api } from "../engine/api";
import type { MediaBin, MediaItem } from "../engine/media";
import type { ProjectEngine } from "../engine/project";
import { blankProject } from "../engine/seed";
import type { ProjectState } from "../engine/types";
import * as edit from "./high-country";
import * as grade from "./last-light";
import * as deliver from "./woods";

export interface RepoDemo {
  id: "edit" | "grade" | "deliver";
  title: string;
  /** locale key of the one line saying what it shows */
  line: string;
  format: { width: number; height: number; fps: number };
  openAt: number;
  timelines: () => ProjectState["timelines"];
  /** the clip selected on open, as the browser demo selects it: [track, clip] */
  select?: [number, number];
}

export const REPO_DEMOS: RepoDemo[] = [
  { id: "edit", title: "High Country", line: "demos.edit.line", format: { width: 1280, height: 720, fps: 30 }, openAt: edit.FILM_OPEN_AT, timelines: edit.filmTimelines, select: [2, 1] },
  { id: "grade", title: "Last Light", line: "demos.grade.line", format: { width: 1280, height: 720, fps: 30 }, openAt: grade.FILM_OPEN_AT, timelines: grade.filmTimelines, select: [2, 0] },
  { id: "deliver", title: "Why I went to the woods", line: "demos.deliver.line", format: deliver.LANDSCAPE, openAt: 18, timelines: deliver.filmTimelines },
];

export async function openRepoDemo(engine: ProjectEngine, bin: MediaBin, id: string): Promise<void> {
  const demo = REPO_DEMOS.find((entry) => entry.id === id);
  if (!demo) throw new Error(`No demo called ${id}`);
  const { media } = await api<{ media: Record<string, MediaItem> }>(`/api/demo/${demo.id}`, {});
  await bin.load();
  const timelines = demo.timelines();
  for (const timeline of timelines) {
    for (const track of timeline.tracks) {
      for (const clip of track.clips) {
        if (!clip.mediaId) continue;
        const item = media[clip.mediaId];
        if (!item) throw new Error(`Demo media missing: ${clip.mediaId}`);
        clip.mediaId = item.id;
      }
    }
  }
  engine.dispatch("project.load", { ...blankProject(demo.format), projectId: null, title: demo.title, timelines, activeTimeline: 0, saved: false });
  engine.dispatch("transport.seek", demo.openAt);
  if (demo.select) {
    const clip = timelines[0].tracks[demo.select[0]]?.clips[demo.select[1]];
    if (clip) engine.dispatch("clip.select", clip.id);
  }
}
