export type MediaKind = "video" | "audio" | "image" | "text" | "filter";

export interface TextStyle {
  fontId?: string;
  content: string;
  size: number;
  color: string;
  bold: boolean;
  align: "left" | "center" | "right";
}

export function defaultTextStyle(content = "Title"): TextStyle {
  return { content, size: 8, color: "#ffffff", bold: true, align: "center" };
}

export const KEYFRAME_PROPS = ["posX", "posY", "scale", "rotation", "opacity"] as const;
export type KeyframeProp = (typeof KEYFRAME_PROPS)[number];

export type KeyframeInterp = "linear" | "ease" | "easeIn" | "easeOut" | "hold";
export const KEYFRAME_INTERPS: KeyframeInterp[] = ["linear", "ease", "easeIn", "easeOut", "hold"];

export interface Keyframe {
  t: number;
  props: Partial<Record<KeyframeProp, number>>;
  interp?: KeyframeInterp;
}

export interface ClipTransition {
  type: "crossfade" | "dip" | "wipe-left" | "wipe-right" | "wipe-up" | "wipe-down" | "slide-left" | "slide-right" | "zoom" | "iris" | "dissolve" | "push-up";
  duration: number;
}

export interface ClipMask {
  shape: "rect" | "ellipse";
  x: number;
  y: number;
  w: number;
  h: number;
  feather: number;
}

export interface ClipKey {
  color: string;
  similarity: number;
  blend: number;
}

export interface Clip {
  id: string;
  kind: MediaKind;
  label: string;
  start: number;
  duration: number;
  mediaId?: string;
  transform?: ClipTransform;
  effectId?: string;
  speed?: number;
  sourceIn?: number;
  speedCurve?: Array<{ t: number; speed: number }>;
  effects?: Array<{ id: string; amount: number; params?: Record<string, number> }>;
  lutId?: string;
  shaderId?: string;
  expressions?: Partial<Record<KeyframeProp, string>>;
  cutout?: { model: string; threshold: number; feather: number; strokes: Array<{ mode: "keep" | "erase"; radius: number; points: number[][] }> };
  volume?: number;
  pan?: number;
  audioEffects?: Array<{ id: string; amount: number }>;

  fadeIn?: number;
  fadeOut?: number;
  textStyle?: TextStyle;
  transitionIn?: ClipTransition;
  keyframes?: Keyframe[];
  key?: ClipKey;
  muted?: boolean;
  reversed?: boolean;
  mask?: ClipMask;
  audioFx?: string;
  fx?: boolean;
  filmstrip?: boolean;
}

export interface Track {
  locked?: boolean;
  hidden?: boolean;
  muted?: boolean;
  id: string;
  name: string;
  clips: Clip[];
}

export interface Timeline {
  id: string;
  name: string;
  tracks: Track[];
}

export interface ClipTransform {
  scale: number;
  posX: number;
  posY: number;
  rotation: number;
  width: number;
  height: number;
  opacity: number;
  blendMode: string;
  flipH: boolean;
}

export interface ProjectState {
  revision?: number;
  projectId: string | null;
  title: string;
  saved: boolean;
  width: number;
  height: number;
  fps: number;
  playhead: number;
  duration: number;
  playing: boolean;
  aspect: string;
  activeTimeline: number;
  selectedClipId: string | null;
  selection: string[];
  timelines: Timeline[];
}

export function defaultTransform(): ClipTransform {
  return {
    scale: 100,
    posX: 0,
    posY: 0,
    rotation: 0,
    width: 100,
    height: 100,
    opacity: 100,
    blendMode: "Normal",
    flipH: false,
  };
}
