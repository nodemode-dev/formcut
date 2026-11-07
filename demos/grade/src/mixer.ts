import { Mixer } from "../../../demo/src/mixer";
import { speedAt } from "../../../frontend/src/engine/timing";
import type { ProjectState } from "../../../frontend/src/engine/types";

export class GradeMixer extends Mixer {
  syncVideos(state: ProjectState, t: number, playing: boolean): void {
    const timeline = state.timelines[state.activeTimeline];
    let curved = false;
    const tracks = timeline.tracks.map((track) => ({
      ...track,
      clips: track.clips.map((clip) => {
        if (clip.kind !== "video" || !clip.speedCurve?.length) return clip;
        curved = true;
        return { ...clip, speed: speedAt(clip, Math.max(0, t - clip.start)) };
      }),
    }));
    if (!curved) {
      super.syncVideos(state, t, playing);
      return;
    }
    super.syncVideos({ ...state, timelines: state.timelines.map((tl, i) => (i === state.activeTimeline ? { ...tl, tracks } : tl)) }, t, playing);
  }
}
