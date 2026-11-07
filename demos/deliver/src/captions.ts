import type { Clip, ProjectState } from "../../../frontend/src/engine/types";
import { CAPTIONS_TRACK } from "./render";

export const captionsOf = (state: ProjectState, timeline = state.activeTimeline): Clip[] => {
  const track = state.timelines[timeline]?.tracks.find((entry) => entry.name === CAPTIONS_TRACK);
  return track ? [...track.clips].filter((clip) => clip.kind === "text").sort((a, b) => a.start - b.start) : [];
};

export interface TimedWord {
  text: string;
  t: number;
  d: number;
}

export function wordTimes(text: string, span: number): TimedWord[] {
  const parts = text.trim().split(/\s+/).filter(Boolean);
  const total = parts.reduce((sum, word) => sum + word.length + 1, 0) || 1;
  const length = Math.max(0.05, span);
  let at = 0;
  return parts.map((part) => {
    const d = (length * (part.length + 1)) / total;
    const word = { text: part, t: Math.round(at * 1000) / 1000, d: Math.round(d * 1000) / 1000 };
    at += d;
    return word;
  });
}

const stamp = (value: number, comma: boolean): string => {
  const ms = Math.round(value * 1000);
  const p = (n: number, width = 2) => String(n).padStart(width, "0");
  return `${p(Math.floor(ms / 3600000))}:${p(Math.floor(ms / 60000) % 60)}:${p(Math.floor(ms / 1000) % 60)}${comma ? "," : "."}${p(ms % 1000, 3)}`;
};

const lineOf = (clip: Clip): string => clip.textStyle?.content ?? clip.label;

export const toSrt = (clips: Clip[]): string =>
  clips.map((clip, index) => `${index + 1}\n${stamp(clip.start, true)} --> ${stamp(clip.start + clip.duration, true)}\n${lineOf(clip)}\n`).join("\n");

export const toVtt = (clips: Clip[]): string =>
  `WEBVTT\n\n${clips.map((clip) => `${stamp(clip.start, false)} --> ${stamp(clip.start + clip.duration, false)}\n${lineOf(clip)}\n`).join("\n")}`;

const short = (value: number): string => `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}`;

export const chapterList = (marks: Array<{ t: number; note?: string }>): string => marks.map((mark) => `${short(mark.t)} ${mark.note ?? "Chapter"}`).join("\n") + "\n";

export const chapterVtt = (marks: Array<{ t: number; note?: string }>, length: number): string =>
  `WEBVTT\n\n${marks
    .map((mark, index) => `${index + 1}\n${stamp(mark.t, false)} --> ${stamp(index + 1 < marks.length ? marks[index + 1].t : length, false)}\n${mark.note ?? "Chapter"}\n`)
    .join("\n")}`;
