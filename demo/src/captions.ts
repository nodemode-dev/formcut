import { defaultTextStyle } from "../../frontend/src/engine/types";
import type { Clip, ProjectState } from "../../frontend/src/engine/types";

export interface Cue {
  start: number;
  end: number;
  text: string;
}

const STAMP = /(?:(\d+):)?(\d{1,2}):(\d{2})[.,](\d{1,3})/;

const seconds = (match: RegExpMatchArray): number =>
  Number(match[1] ?? 0) * 3600 + Number(match[2]) * 60 + Number(match[3]) + Number(match[4].padEnd(3, "0")) / 1000;

export function parseCaptions(text: string): Cue[] {
  const cues: Cue[] = [];
  for (const block of text.replace(/\r/g, "").split(/\n{2,}/)) {
    const lines = block.split("\n").filter((line) => line.trim() !== "");
    const at = lines.findIndex((line) => line.includes("-->"));
    if (at < 0) continue;
    const [from, to] = lines[at].split("-->");
    const a = from.trim().match(STAMP);
    const b = to.trim().match(STAMP);
    if (!a || !b) continue;
    const body = lines.slice(at + 1).join("\n").replace(/<[^>]+>/g, "").trim();
    if (!body) continue;
    cues.push({ start: seconds(a), end: seconds(b), text: body });
  }
  return cues.filter((cue) => cue.end > cue.start).sort((x, y) => x.start - y.start);
}

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
