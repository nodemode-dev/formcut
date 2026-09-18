import type { ProjectState, Track } from "./types";

function track(id: string, name: string, clips: Track["clips"]): Track {
  return { id, name, clips };
}

export function seedProject(): ProjectState {
  const tracks: Track[] = [
    track("t1", "Titles", []),
    track("t2", "Overlay", []),
    track("t3", "Video", []),
    track("t4", "Audio", []),
  ];

  return {
    projectId: null,
    title: "Untitled project",
    saved: true,
    width: 1080,
    height: 1920,
    fps: 30,
    playhead: 0,
    duration: 0.1,
    playing: false,
    aspect: "9:16",
    activeTimeline: 0,
    selectedClipId: null,
    timelines: [
      { id: "tl1", name: "Timeline 1", tracks },
    ],
  };
}

export function blankProject(): ProjectState {
  const state = seedProject();
  for (const timeline of state.timelines) {
    for (const t of timeline.tracks) t.clips = [];
  }
  state.selectedClipId = null;
  state.playhead = 0;
  state.duration = 12;
  return state;
}
