import { defaultTextStyle } from "../../../frontend/src/engine/types";
import type { Clip, ProjectState, TextStyle, Track } from "../../../frontend/src/engine/types";

export const FILM_LENGTH = 38.5;
export const FILM_OPEN_AT = 2.9;

const TRACKS = ["Titles", "Overlay", "Video", "Audio"];

const make = (kind: Clip["kind"], label: string, mediaId: string | undefined, start: number, duration: number, extra: Partial<Clip> = {}): Clip =>
  ({ id: crypto.randomUUID(), kind, label, mediaId, start, duration, ...extra });

const pos = (posX: number, posY: number): NonNullable<Clip["transform"]> =>
  ({ scale: 100, posX, posY, rotation: 0, width: 100, height: 100, opacity: 100, blendMode: "Normal", flipH: false });

const style = (content: string, size: number, extra: Partial<TextStyle> = {}): TextStyle =>
  ({ ...defaultTextStyle(content), size, shadowColor: "black", shadowBlur: 14, ...extra });

const tag = (heading: string, detail: string, start: number): Clip =>
  make("text", heading, undefined, start, 3.4, {
    fadeIn: 0.4, fadeOut: 0.5, transform: pos(0, 31),
    textStyle: style(`${heading}\n${detail}`, 3.2, { align: "left", bold: false, shadowBlur: 0, plateColor: "black", plateOpacity: 0.5 }),
  });

const key = (t: number, props: Record<string, number>, interp: "ease" | "linear" = "ease") => ({ t, props, interp });

export function filmTimelines(): ProjectState["timelines"] {
  const tracks: Track[] = TRACKS.map((name) => ({ id: crypto.randomUUID(), name, clips: [] }));
  tracks[0].clips.push(
    make("text", "Last Light", undefined, 0.7, 4.2, {
      fadeIn: 0.9, fadeOut: 0.9, transform: pos(0, -6),
      textStyle: style("LAST LIGHT", 10, { shadowBlur: 26 }),
    }),
    tag("GOLDEN HOUR", "Look, wheels and a speed ramp", 4.9),
    tag("TEAL ORANGE", "S curve and a window on the sun", 8.4),
    tag("BLUE HOUR", "Vignette keyed up over the shot", 14.6),
    tag("MOODY GREEN", "Iris in, cooler shadows", 20.4),
    tag("AUTUMN", "Warm gain, dip in from black", 26.5),
    tag("VIVID POP", "Lift and gain pushed apart", 32.2),
    make("text", "Credits", undefined, 35.9, 2.6, {
      fadeIn: 0.5, fadeOut: 0.6, transform: pos(0, 0),
      textStyle: style("Footage: Pexels creators, flattened here before grading. Music: Bach, Goldberg Variation 13, played by Kimiko Ishizaka (CC0).", 2.8, { bold: false, shadowBlur: 10 }),
    }),
  );
  const sun = make("video", "Open water window", "grade-02", 9.2, 4.2, {
    sourceIn: 1.7, fadeIn: 0.5, fadeOut: 0.5,
    mask: { shape: "ellipse", x: 28, y: 6, w: 44, h: 52, feather: 18, angle: 0 },
    colour: { exposure: 0.45, contrast: 10, saturation: 26, temperature: 5300, vignette: 0 },
    colorGrade: { gain: { r: 0.08, g: 0.02, b: -0.08 } },
    effectId: "golden-hour", lutIntensity: 0.7,
  });
  tracks[1].clips.push(sun);
  tracks[2].clips.push(
    make("video", "Last light", "grade-01", 0, 7.5, {
      sourceIn: 0.4,
      speedCurve: [{ t: 0, speed: 1.5 }, { t: 2.6, speed: 0.45 }, { t: 5.2, speed: 0.45 }, { t: 7.5, speed: 1.4 }],
      keyframes: [key(0, { scale: 100 }), key(7.5, { scale: 112 })],
      colour: { exposure: 0.05, contrast: 10, saturation: 6, temperature: 6300, highlights: -15, shadows: 12, vignette: 26 },
      colorGrade: { lift: { r: -0.02, b: 0.04 }, gain: { r: 0.02, b: -0.02 }, contrast: 1.05, boost: 0.1 },
      effectId: "golden-hour", lutIntensity: 0.35,
    }),
    make("video", "Open water", "grade-02", 7.5, 6, {
      transitionIn: { type: "crossfade", duration: 1.2 },
      colour: { contrast: 14, saturation: 26, exposure: 0.1, vignette: 18 },
      colorGrade: { curves: { y: [[0, 0], [0.25, 0.2], [0.75, 0.82], [1, 1]] }, lift: { b: 0.04 } },
      effectId: "teal-orange", lutIntensity: 0.9,
    }),
    make("video", "Warm peaks", "grade-03", 13.5, 6, {
      transitionIn: { type: "wipe-right", duration: 0.9 },
      effects: [{ id: "vignette", amount: 0 }],
      keyframes: [key(0, { "fx.0.amount": 0 }), key(6, { "fx.0.amount": 0.85 })],
      colour: { contrast: 10, saturation: 12, exposure: -0.05 },
      colorGrade: { lift: { b: 0.04 }, gain: { r: 0.02 } },
      effectId: "blue-hour", lutIntensity: 0.9,
    }),
    make("video", "Mist and pine", "grade-04", 19.5, 6, {
      transitionIn: { type: "iris", duration: 1 },
      colour: { contrast: 12, saturation: 22, vignette: 20, tint: -6 },
      colorGrade: { lift: { g: 0.03, b: 0.02 }, gamma: { b: 0.04 } },
      effectId: "moody-green", lutIntensity: 0.9,
    }),
    make("video", "Fire", "grade-05", 25.5, 5.5, {
      transitionIn: { type: "dip", duration: 1 },
      colour: { exposure: 0.6, contrast: 12, saturation: 6, vignette: 22 },
      effectId: "autumn", lutIntensity: 0.55,
    }),
    make("video", "Southern lights", "grade-06", 31, 7.5, {
      fadeOut: 1.6, transitionIn: { type: "blur-fade", duration: 1.2 },
      colour: { contrast: 12, saturation: 20, exposure: 0.15, vignette: 22 },
      colorGrade: { lift: { b: 0.06 }, gain: { g: 0.04, r: -0.04 }, boost: 0.2 },
      effectId: "vivid-pop", lutIntensity: 0.6,
    }),
  );
  tracks[3].clips.push(make("audio", "Goldberg Variation 13 (Bach)", "grade-music", 0, FILM_LENGTH, { sourceIn: 0, fadeIn: 1.5, fadeOut: 3.5, volume: 0.9 }));
  return [{ id: crypto.randomUUID(), name: "Last Light", tracks }];
}
