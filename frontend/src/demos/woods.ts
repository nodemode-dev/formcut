import { defaultTextStyle } from "../engine/types";
import type { Clip, ProjectState, TextStyle, Track } from "../engine/types";
import { cropKeyframes, parseCaptions, wordTimes } from "./film-kit";
import type { Crop } from "./film-kit";
import { CHAPTERS, FILM_LENGTH, SRT, VOICE_START } from "./woods-data";
import { PATHS } from "./woods-paths";

export const LANDSCAPE = { width: 1280, height: 720, fps: 30 };
export const VERTICAL = { width: 540, height: 960, fps: 30 };
export const TRACK_NAMES = ["Captions", "Titles", "Video", "Voice", "Music"];
export const COVER_SCALE = ((VERTICAL.height * 16) / 9 / VERTICAL.width) * 100;

const SCENES: Array<[string, string]> = [
  ["talk-01", "First light"], ["talk-02", "Mist and pine"], ["talk-03", "The stream"], ["talk-04", "Open water"],
  ["talk-05", "Peaks"], ["talk-06", "Fire"], ["talk-07", "Above the clouds"], ["talk-08", "Night sky"],
];
const STEP = 10.5;

const make = (kind: Clip["kind"], label: string, mediaId: string | undefined, start: number, duration: number, extra: Partial<Clip> = {}): Clip =>
  ({ id: crypto.randomUUID(), kind, label, mediaId, start, duration, ...extra });

const pos = (posX: number, posY: number): NonNullable<Clip["transform"]> =>
  ({ scale: 100, posX, posY, rotation: 0, width: 100, height: 100, opacity: 100, blendMode: "Normal", flipH: false });

const style = (content: string, size: number, extra: Partial<TextStyle> = {}): TextStyle =>
  ({ ...defaultTextStyle(content), size, shadowColor: "black", shadowBlur: 14, ...extra });

export const CAPTION_STYLE = { size: 4.6, outlineColor: "black", outlineWidth: 6, shadowBlur: 6 };

export function captionClips(text: string, vertical: boolean, mode: NonNullable<TextStyle["wordStyle"]>["mode"] = "highlight"): Clip[] {
  return parseCaptions(text).map((cue) => {
    const duration = Math.max(0.2, Math.round((cue.end - cue.start) * 100) / 100);
    const line = cue.text.replace(/\n/g, " ");
    return {
      id: crypto.randomUUID(), kind: "text", label: line, start: Math.round(cue.start * 100) / 100, duration,
      words: wordTimes(line, duration),
      transform: pos(0, vertical ? 21 : 35),
      textStyle: { ...defaultTextStyle(line), ...CAPTION_STYLE, size: vertical ? 3.4 : CAPTION_STYLE.size, wordStyle: { mode, colour: "#ffd23f" } },
    } satisfies Clip;
  });
}

function titles(vertical: boolean): Clip[] {
  const size = vertical ? 7.2 : 8.6;
  return [
    make("text", "Why I went to the woods", undefined, 0.5, 3.4, {
      fadeIn: 0.9, fadeOut: 0.8, transform: pos(0, vertical ? -4 : -4),
      textStyle: style("WHY I WENT TO THE WOODS", size, { shadowBlur: 24 }),
    }),
    make("text", "Byline", undefined, 4.6, 5, {
      fadeIn: 0.5, fadeOut: 0.5, transform: pos(0, vertical ? -36 : -34),
      textStyle: style("Henry David Thoreau, Walden (1854)\nRead by Gord Mackenzie for LibriVox", vertical ? 2.6 : 3.2, { bold: false, shadowBlur: 0, plateColor: "black", plateOpacity: 0.5 }),
    }),
    make("text", "Credits", undefined, 81.2, 4.4, {
      fadeIn: 0.6, fadeOut: 0.7, transform: pos(0, 0),
      textStyle: style("Footage: Pexels creators. Reading: LibriVox, public domain. Music: Bach, Goldberg Variation 13, Kimiko Ishizaka, CC0.", vertical ? 3.2 : 3.2, { bold: false, shadowBlur: 10 }),
    }),
  ];
}

function video(vertical: boolean): Clip[] {
  return SCENES.map(([id, name], index) => {
    const last = index === SCENES.length - 1;
    const duration = last ? 12.5 : STEP;
    const crops: Crop[] = (PATHS[id] ?? []).filter((entry) => entry[0] < duration).map(([t, x, w]) => ({ t: t * 2, x, w }));
    return make("video", name, id, Math.round(index * STEP * 100) / 100, duration, {
      transitionIn: index ? { type: "crossfade", duration: 1 } : undefined,
      fadeIn: index ? undefined : 1.2, fadeOut: last ? 2.5 : undefined,
      ...(vertical ? { transform: { ...pos(0, 0), scale: COVER_SCALE }, keyframes: cropKeyframes(crops, COVER_SCALE, VERTICAL.width, VERTICAL.width) } : {}),
    });
  });
}

function markers() {
  return CHAPTERS.map((chapter) => ({ id: crypto.randomUUID(), t: chapter.t, note: chapter.title, colour: "accent" }));
}

function timeline(name: string, vertical: boolean): ProjectState["timelines"][number] {
  const tracks: Track[] = TRACK_NAMES.map((trackName) => ({ id: crypto.randomUUID(), name: trackName, clips: [] }));
  tracks[0].clips.push(...captionClips(SRT, vertical));
  tracks[1].clips.push(...titles(vertical));
  tracks[2].clips.push(...video(vertical));
  tracks[3].clips.push(make("audio", "Walden, read", "talk-voice", VOICE_START, 77.9, { sourceIn: 0, fadeIn: 0.05, fadeOut: 0.3, volume: 1 }));
  tracks[4].clips.push(make("audio", "Goldberg Variation 13", "talk-music", 0, FILM_LENGTH, { sourceIn: 0, fadeIn: 1.5, fadeOut: 4.5, volume: 1 }));
  const format = vertical ? VERTICAL : LANDSCAPE;
  return { id: crypto.randomUUID(), name, width: format.width, height: format.height, fps: format.fps, tracks, markers: markers() };
}

export const filmTimelines = (): ProjectState["timelines"] => [timeline("Talk 16:9", false), timeline("Vertical 9:16", true)];
