import { api } from "./api";
import type { MediaBin, MediaItem } from "./media";
import type { ProjectEngine } from "./project";
import { defaultTextStyle, defaultTransform, type Clip } from "./types";

export async function loadDemoProject(engine: ProjectEngine, bin: MediaBin): Promise<void> {
  const { media } = await api<{ media: MediaItem[] }>("/api/demo", {});
  await bin.load();
  const byName = (name: string): MediaItem => {
    const item = media.find(m => m.name === name);
    if (!item) throw new Error(`Demo media missing: ${name}`);
    return item;
  };
  const clipMedia = byName("input-clip-example.mp4");
  const video = byName("model-drop-MV.mp4");
  const voice = byName("a-sample.wav");
  const still = byName("effect-example-image.jpg");
  const id = () => crypto.randomUUID();
  const place = (item: MediaItem, start: number, duration: number, extra: Partial<Clip> = {}): Clip => ({
    id: id(), kind: item.kind, label: item.name, mediaId: item.id, start, duration, ...extra,
  });
  const title: Clip = {
    id: id(), kind: "text", label: "formcut demo", start: 0.5, duration: 3, fadeIn: 0.4, fadeOut: 0.4,
    textStyle: { ...defaultTextStyle("formcut demo"), size: 9 },
  };
  const overlay = place(still, 9, 6, {
    transform: { ...defaultTransform(), scale: 42, posX: 27 },
    effects: [{ id: "teal-amber", amount: 1 }],
    fadeIn: 0.5,
    fadeOut: 0.5,
  });
  const footage = [
    place(clipMedia, 0, 8, { sourceIn: 2 }),
    place(video, 8, 8, { sourceIn: 1, muted: true, transitionIn: { type: "crossfade", duration: 0.8 } }),
  ];
  // The spoken line plays with the title, whole: a fade would swallow a line this short.
  const line = place(voice, 0.5, voice.duration);
  engine.dispatch("project.load", {
    projectId: null,
    title: "Demo project",
    width: 1920,
    height: 1080,
    fps: 30,
    aspect: "16:9",
    saved: false,
    activeTimeline: 0,
    timelines: [{
      id: id(),
      name: "Timeline 1",
      tracks: [
        { id: id(), name: "Titles", clips: [title] },
        { id: id(), name: "Overlay", clips: [overlay] },
        { id: id(), name: "Video", clips: footage },
        { id: id(), name: "Audio", clips: [line] },
      ],
    }],
  });
}
