export type MediaKind = "video" | "audio" | "image" | "text" | "filter" | "timeline";

export interface TextStyle {
  fontId?: string;
  content: string;
  size: number;
  color: string;
  bold: boolean;
  align: "left" | "center" | "right";
  weight?: number;
  italic?: boolean;
  outlineColor?: string;
  outlineWidth?: number;
  shadowColor?: string;
  shadowBlur?: number;
  shadowX?: number;
  shadowY?: number;
  plateColor?: string;
  plateOpacity?: number;
  platePadding?: number;
  plateRadius?: number;
  lineHeight?: number;
  letterSpacing?: number;
  wrapWidth?: number;
  textOpacity?: number;
  /** How the word being spoken is drawn when the clip carries words: coloured, popped larger, or on a box. */
  wordStyle?: { mode: "highlight" | "pop" | "box" | "reveal" | "rise"; colour: string };
}

export function defaultTextStyle(content = "Title"): TextStyle {
  return { content, size: 8, color: "#ffffff", bold: true, align: "center" };
}

export const KEYFRAME_PROPS = ["posX", "posY", "scale", "rotation", "opacity"] as const;
export type TransformProp = (typeof KEYFRAME_PROPS)[number];
/** An effect's amount or one of its parameters, keyed on the clip as fx.<effect index>.<name>. */
export type EffectProp = `fx.${number}.${string}`;
export type KeyframeProp = TransformProp | EffectProp;
export const isEffectProp = (prop: string): prop is EffectProp => /^fx\.\d+\.[^.]+$/.test(prop);

export type KeyframeInterp = "linear" | "ease" | "easeIn" | "easeOut" | "easeInOut" | "smooth" | "snap" | "overshoot" | "anticipate" | "hold" | "bezier";
export const KEYFRAME_INTERPS: KeyframeInterp[] = ["linear", "ease", "easeIn", "easeOut", "easeInOut", "smooth", "snap", "overshoot", "anticipate", "hold", "bezier"];

/** Named easings are handle positions, so every preset is a curve you can drag. */
export const EASING_HANDLES: Record<string, [number, number, number, number]> = {
  linear: [0, 0, 1, 1], ease: [0.25, 0.1, 0.25, 1], easeIn: [0.42, 0, 1, 1],
  easeOut: [0, 0, 0.58, 1], easeInOut: [0.42, 0, 0.58, 1], smooth: [0.45, 0.05, 0.55, 0.95],
  snap: [0.9, 0, 1, 0.4], overshoot: [0.34, 1.56, 0.64, 1], anticipate: [0.36, -0.36, 0.66, 1],
};

export interface Keyframe {
  t: number;
  props: Partial<Record<KeyframeProp, number>>;
  interp?: KeyframeInterp;
  handles?: [number, number, number, number];
}

export interface ClipTransition {
  type: "crossfade" | "dip" | "wipe-left" | "wipe-right" | "wipe-up" | "wipe-down" | "slide-left" | "slide-right" | "zoom" | "iris" | "dissolve" | "push-up" | "push-down" | "cover-left" | "cover-up" | "clock-wipe" | "blinds" | "diagonal-wipe" | "pixel-dissolve" | "blur-fade" | "spin" | "diamond" | "barn-door";
  duration: number;
}

/** Shapes a mask may take, plus a drawn path with its own anchors. */
export const MASK_SHAPES = ["rect", "ellipse", "triangle", "diamond", "pentagon", "hexagon",
  "octagon", "star", "star6", "heart", "cross", "arrow", "chevron", "trapezoid", "linear", "path"] as const;
export type MaskShape = typeof MASK_SHAPES[number];

/** One anchor of a drawn mask; handles are offsets from the anchor, 0..1 of the frame. */
export interface MaskPoint {
  x: number;
  y: number;
  inX?: number;
  inY?: number;
  outX?: number;
  outY?: number;
}

export interface ClipMask {
  /** The mask's anchors over time, when it has been tracked to a moving subject. */
  track?: Array<{ t: number; points: MaskPoint[] }>;
  shape: MaskShape;
  points?: MaskPoint[];
  x: number;
  y: number;
  w: number;
  h: number;
  feather: number;
  angle?: number;
  invert?: boolean;
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
  // enabled: false switches an effect off without losing its settings; absent means on.
  effects?: Array<{ id: string; amount: number; params?: Record<string, number>; enabled?: boolean }>;
  lutId?: string;
  shaderId?: string;
  expressions?: Partial<Record<KeyframeProp, string>>;
  cutout?: { model: string; threshold: number; feather: number; strokes: Array<{ mode: "keep" | "erase"; radius: number; points: number[][]; region?: number[][]; t?: number }>; point?: { x: number; y: number; t?: number }; box?: { x0: number; y0: number; x1: number; y1: number; t?: number } };
  volume?: number;
  pan?: number;
  audioEffects?: Array<{ id: string; amount: number; enabled?: boolean }>;

  fadeIn?: number;
  fadeOut?: number;
  textStyle?: TextStyle;
  /** For a timeline clip: the id of the timeline of this project it plays, as one clip. */
  timelineId?: string;
  /** Multicam: the index of the one track of that timeline this cut shows; absent, the compound shows every track. */
  angle?: number;
  /** Multicam: the track whose sound this cut carries; absent, the picture's angle sounds. */
  audioAngle?: number;
  /** The caption's words, each with its start and length in seconds from the clip's start (from transcription); a word may carry its own colour (emphasis). */
  words?: Array<{ t: number; d: number; text: string; colour?: string }>;
  transitionIn?: ClipTransition;
  keyframes?: Keyframe[];
  key?: ClipKey;
  // the Track workspace's layers (planar tracking): shapes, the frame they are drawn on, settings, a surface; the
  // per-frame track itself is kept by the engine per layer (planar-tracks/<layer id>.json)
  planar?: ClipPlanar;
  muted?: boolean;
  extendOut?: number;
  colour?: ColourPanel;
  colorGrade?: ColorGrade;
  pitchFollowsSpeed?: boolean;
  /** Which of the media's audio streams this clip plays (X8); 0, the default stream, when absent. */
  audioStream?: number;
  lutIntensity?: number;
  volumeKeys?: ValueKey[];
  animations?: ClipAnimations;
  reversed?: boolean;
  detachedFrom?: string;
  crop?: { left?: number; top?: number; right?: number; bottom?: number };
  mask?: ClipMask;
  /** Camera-shake correction, measured once per source and applied per frame. */
  stabilise?: { smoothing: number; crop: number };
  /** Frames between source frames are made rather than repeated. */
  smoothSlow?: boolean;
  audioFx?: string;
  fx?: boolean;
  filmstrip?: boolean;
}

export interface Track {
  locked?: boolean;
  hidden?: boolean;
  muted?: boolean;
  magnetic?: boolean;
  id: string;
  name: string;
  clips: Clip[];
}

export interface Timeline {
  id: string;
  name: string;
  width?: number;
  height?: number;
  fps?: number;
  tracks: Track[];
  /** Notes at times: shown on the ruler, snapped to, left by people and agents alike. */
  markers?: TimelineMarker[];
}

export interface TimelineMarker {
  id: string;
  t: number;
  colour?: string;
  note?: string;
}

/** K3 and K4: a keyed value point, the same easing modes as transform keys. */
export interface ValueKey {
  t: number;
  value: number;
  interp?: KeyframeInterp;
}

/** K6: animation slots stored by preset name, rescaled when a clip is trimmed. */
export const IN_ANIMATIONS = ["fade", "zoom-in", "zoom-out", "slide-up", "slide-down", "slide-left", "slide-right", "spin", "pop"] as const;
export const COMBO_ANIMATIONS = ["pulse", "shake", "sway", "float", "bounce", "drift", "swing"] as const;

export interface ClipAnimations {
  in?: { preset: string; seconds: number };
  out?: { preset: string; seconds: number };
  combo?: { preset: string };
}

/** K1: the colour panel. Every field neutral at its default; absent means off. */
export interface ColourPanel {
  temperature?: number;
  tint?: number;
  saturation?: number;
  exposure?: number;
  brightness?: number;
  contrast?: number;
  highlights?: number;
  shadows?: number;
  whites?: number;
  blacks?: number;
  sharpen?: number;
  fade?: number;
  vignette?: number;
}

/** The Color section's grade: wheels, primaries and curves, run after the colour panel. Absent means neutral. */
export type WheelLevels = { r?: number; g?: number; b?: number; y?: number };
export interface ColorGrade {
  lift?: WheelLevels;
  gamma?: WheelLevels;
  gain?: WheelLevels;
  offset?: WheelLevels;
  contrast?: number;
  pivot?: number;
  boost?: number;
  hue?: number;
  curves?: { y?: number[][]; r?: number[][]; g?: number[][]; b?: number[][] };
  hueHue?: number[][];
  hueSat?: number[][];
  lumSat?: number[][];
}

export const COLOUR_NEUTRAL: Required<ColourPanel> = {
  temperature: 6500, tint: 0, saturation: 0, exposure: 0, brightness: 0, contrast: 0,
  highlights: 0, shadows: 0, whites: 0, blacks: 0, sharpen: 0, fade: 0, vignette: 0,
};

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
  flipV?: boolean;
}

export interface ProjectState {
  revision?: number;
  projectId: string | null;
  /** The export's colour: Rec.709 as the working space is, or an HLG or PQ output transform in ten bits. */
  outputColour?: "bt709" | "hlg" | "pq";
  /** Opt-in sync: a folder on this computer the person's own sync client carries; the package is written there on save. */
  syncFolder?: string;
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
    flipV: false,
  };
}

export interface PlanarShape {
  points: number[][];  // x, y in the frame's unit square, on the layer's reference frame
  mode: "add" | "subtract";
}

export interface PlanarLayer {
  id: string;
  name: string;
  color: string;
  shapes: PlanarShape[];
  reference: number;  // source seconds: the frame the shapes are drawn on
  settings: Record<string, unknown>;  // as planar.Settings names them
  surface?: number[][];  // four corners in the reference frame's unit square
  visible: boolean;
  tracking: boolean;
  locked: boolean;
}

export interface ClipPlanar {
  version: 1;
  layers: PlanarLayer[];
}

