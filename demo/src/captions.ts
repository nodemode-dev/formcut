import { defaultTextStyle } from "../../frontend/src/engine/types";
import type { Clip, ProjectState } from "../../frontend/src/engine/types";

import type { Cue } from "../../frontend/src/demos/film-kit";

export { parseCaptions } from "../../frontend/src/demos/film-kit";
export type { Cue } from "../../frontend/src/demos/film-kit";

export function captionClips(cues: Cue[]): Clip[] {
  return cues.map((cue) => ({
    id: crypto.randomUUID(),
    kind: "text",
    label: cue.text.replace(/\n/g, " "),
    start: Math.round(cue.start * 100) / 100,
    duration: Math.max(0.2, Math.round((cue.end - cue.start) * 100) / 100),
    transform: { scale: 100, posX: 0, posY: 36, rotation: 0, width: 100, height: 100, opacity: 100, blendMode: "Normal", flipH: false },
    textStyle: { ...defaultTextStyle(cue.text), size: 5.4, outlineColor: "black", outlineWidth: 6, shadowBlur: 6, shadowColor: "black" },
  }));
}

const stamp = (value: number): string => {
  const ms = Math.round(value * 1000);
  const p = (n: number, width = 2) => String(n).padStart(width, "0");
  return `${p(Math.floor(ms / 3600000))}:${p(Math.floor(ms / 60000) % 60)}:${p(Math.floor(ms / 1000) % 60)},${p(ms % 1000, 3)}`;
};

export function toSrt(state: ProjectState): string {
  const clips = state.timelines[state.activeTimeline].tracks
    .flatMap((track) => track.clips)
    .filter((clip) => clip.kind === "text")
    .sort((a, b) => a.start - b.start);
  return clips
    .map((clip, index) => `${index + 1}\n${stamp(clip.start)} --> ${stamp(clip.start + clip.duration)}\n${clip.textStyle?.content ?? clip.label}\n`)
    .join("\n");
}

export const SAMPLE_CAPTIONS = `1
00:00:00.600 --> 00:00:03.200
Local first. No upload, no account.

2
00:00:03.600 --> 00:00:06.400
Cut, grade and caption in the page.

3
00:00:07.000 --> 00:00:10.200
One renderer draws the preview and the file.
`;
