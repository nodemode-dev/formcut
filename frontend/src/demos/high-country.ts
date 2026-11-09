import { defaultTextStyle } from "../engine/types";
import type { Clip, ProjectState, TextStyle, Track } from "../engine/types";

const FILM_TRACKS = ["Captions", "Titles", "Video", "Audio"];
export const FILM_LENGTH = 48;
const FILM_MUSIC_IN = 0;
export const FILM_OPEN_AT = 8.2;

export function filmTimelines(): ProjectState["timelines"] {
  const make = (kind: Clip["kind"], label: string, mediaId: string | undefined, start: number, duration: number, extra: Partial<Clip> = {}): Clip =>
    ({ id: crypto.randomUUID(), kind, label, mediaId, start, duration, ...extra });
  const pos = (posX: number, posY: number): NonNullable<Clip["transform"]> =>
    ({ scale: 100, posX, posY, rotation: 0, width: 100, height: 100, opacity: 100, blendMode: "Normal", flipH: false });
  const style = (content: string, size: number, extra: Partial<TextStyle> = {}): TextStyle =>
    ({ ...defaultTextStyle(content), size, shadowColor: "black", shadowBlur: 14, ...extra });
  const caption = (text: string, start: number, duration: number): Clip =>
    make("text", text, undefined, start, duration, {
      fadeIn: 0.5, fadeOut: 0.5, transform: pos(0,38),
      textStyle: style(text, 5, { bold: false, outlineColor: "black", outlineWidth: 6, shadowBlur: 8 }),
    });
  const tag = (heading: string, detail: string, start: number): Clip =>
    make("text", heading, undefined, start, 3.6, {
      fadeIn: 0.4, fadeOut: 0.5, transform: pos(0,27),
      textStyle: style(`${heading}\n${detail}`, 3.3, { align: "left", bold: false, shadowBlur: 0, plateColor: "black", plateOpacity: 0.5 }),
    });
  const tracks: Track[] = FILM_TRACKS.map((name) => ({ id: crypto.randomUUID(), name, clips: [] }));
  tracks[0].clips.push(
    make("text", "A day, dark to dark", undefined, 7.2, 3.6, {
      fadeIn: 0.8, fadeOut: 0.8, transform: pos(0,7),
      textStyle: style("A day in the mountains, from dark to dark", 3.6, { bold: false, shadowBlur: 12 }),
    }),
    caption("Before the light, the sky is crowded.", 1.2, 3.6),
    caption("The first warm light finds the ridges.", 13, 3.6),
    caption("Fog fills the valleys like water.", 17.8, 3.8),
    caption("Snowmelt takes the long way down.", 23.2, 3.8),
    caption("Above it all, a sea of cloud.", 29.2, 4.4),
    caption("A fire to hold the dark back.", 35.8, 3.6),
    caption("And then the sky lights up.", 41.4, 4.4),
  );
  tracks[1].clips.push(
    tag("BEFORE DAWN", "Milky Way over the ridge", 0.9),
    make("text", "High Country", undefined, 6.2, 4.6, {
      fadeIn: 0.9, fadeOut: 0.9, transform: pos(0,-6),
      textStyle: style("HIGH COUNTRY", 11, { shadowBlur: 26 }),
    }),
    tag("MORNING LIGHT", "Snow peaks in amber haze", 12.6),
    tag("ABOVE THE FOG", "Forest ridge, early blue", 17.6),
    tag("MELTWATER", "A stream down a bare slope", 23),
    tag("CLOUD SEA", "Sun over the cloud tops", 28.8),
    tag("NIGHT FIRE", "Embers and flame", 35.6),
    tag("AURORA", "Southern lights over a lake town", 41.1),
    make("text", "Credits", undefined, 45.4, 2.6, {
      fadeIn: 0.5, fadeOut: 0.6, transform: pos(0,0),
      textStyle: style("Footage: Pexels creators. Music: Bach, Goldberg Aria, played by Kimiko Ishizaka (CC0).", 3, { bold: false, shadowBlur: 10 }),
    }),
  );
  tracks[2].clips.push(
    make("video", "Milky Way", "film-01", 0, 5.5, { fadeIn: 1, colour: { exposure: 0.55, contrast: 14, saturation: 14, temperature: 6000, vignette: 28 } }),
    make("video", "Sunrise ridge", "film-02", 5.5, 6.5, { transitionIn: { type: "crossfade", duration: 1.4 }, colour: { contrast: 8, saturation: 12, temperature: 7000, vignette: 22 } }),
    make("video", "Snow peaks", "film-03", 12, 5, { transitionIn: { type: "wipe-right", duration: 0.9 }, colour: { contrast: 6, saturation: 10, vignette: 25 } }),
    make("video", "Fog and forest", "film-04", 17, 5.5, { transitionIn: { type: "crossfade", duration: 1 }, colour: { contrast: 10, saturation: 8, temperature: 6200, vignette: 18 } }),
    make("video", "Waterfall slope", "film-05", 22.5, 5.5, { transitionIn: { type: "zoom", duration: 0.9 }, colour: { contrast: 10, saturation: 12, vignette: 20 } }),
    make("video", "Cloud sea", "film-06", 28, 7, { transitionIn: { type: "crossfade", duration: 1.2 }, colour: { exposure: 0.25, contrast: 10, saturation: 14, vignette: 25 } }),
    make("video", "Campfire", "film-07", 35, 5.5, { transitionIn: { type: "dip", duration: 1 }, colour: { exposure: 0.5, contrast: 6, saturation: 8, vignette: 30 } }),
    make("video", "Aurora", "film-08", 40.5, 7.5, { fadeOut: 1.5, transitionIn: { type: "crossfade", duration: 1.2 }, colour: { contrast: 6, saturation: 8, vignette: 20 } }),
  );
  tracks[3].clips.push(make("audio", "Goldberg Aria (Bach)", "film-music", 0, FILM_LENGTH, { sourceIn: FILM_MUSIC_IN, fadeIn: 1.5, fadeOut: 3.5, volume: 0.9 }));
  return [{ id: crypto.randomUUID(), name: "High Country", tracks }];
}
