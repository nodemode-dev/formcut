// What a clip shows. An audio clip draws the envelope of the audio it actually
// plays, and a video or image clip draws frames from the media it points at.
//
// Both come from endpoints that describe the whole media, not the clip, and are
// cached per media item here as well as on disk. That matters because a clip is
// a window onto its media: trimming, moving, restretching or zooming changes
// which part of a cached whole is drawn, and must never trigger a new render.
// Source time is resolved through the engine's own speed mapping, so a clip with
// a speed curve shows the frames and samples it will really play.
import { sourceTime } from "../engine/timing";
import type { Clip } from "../engine/types";
import type { MediaBin } from "../engine/media";

interface Peaks {
  duration: number;
  buckets: number;
  low: number[];
  high: number[];
}

// The strip is requested with an explicit frame count, so its geometry is known
// exactly rather than inferred from the image's aspect ratio.
const STRIP_FRAMES = 40;

const peaks = new Map<string, Promise<Peaks | null>>();
const strips = new Map<string, Promise<HTMLImageElement | null>>();

function loadPeaks(mediaId: string): Promise<Peaks | null> {
  let pending = peaks.get(mediaId);
  if (!pending) {
    pending = fetch(`/api/media/${mediaId}/peaks`)
      .then((response) => (response.ok ? (response.json() as Promise<Peaks>) : null))
      .catch(() => null);
    peaks.set(mediaId, pending);
  }
  return pending;
}

function loadStrip(mediaId: string): Promise<HTMLImageElement | null> {
  let pending = strips.get(mediaId);
  if (!pending) {
    pending = new Promise<HTMLImageElement | null>((resolve) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => resolve(null);
      image.src = `/api/media/${mediaId}/filmstrip?frames=${STRIP_FRAMES}`;
    });
    strips.set(mediaId, pending);
  }
  return pending;
}

// Geometry plus everything that can change what is drawn. Repainting is skipped
// when this has not moved, so a reconcile that only shifts a clip sideways costs
// one string comparison per clip.
function signature(clip: Clip, width: number, height: number): string {
  return [
    clip.mediaId ?? "", clip.kind, Math.round(width), Math.round(height),
    clip.sourceIn ?? 0, clip.duration, clip.speed ?? 1,
    clip.speedCurve ? JSON.stringify(clip.speedCurve) : "",
  ].join("|");
}

export function paintClipBody(node: HTMLElement, clip: Clip, bin: MediaBin): void {
  if (clip.kind !== "audio" && clip.kind !== "video" && clip.kind !== "image") return;
  const body = node.querySelector<HTMLElement>(".body");
  if (!body || !clip.mediaId) return;
  const width = body.clientWidth;
  const height = body.clientHeight;
  if (width < 2 || height < 2) return;

  let canvas = body.querySelector<HTMLCanvasElement>("canvas.clip-canvas");
  if (!canvas) {
    canvas = document.createElement("canvas");
    canvas.className = "clip-canvas";
    body.append(canvas);
  }
  const sig = signature(clip, width, height);
  if (canvas.dataset.sig === sig) return;
  canvas.dataset.sig = sig;

  const ratio = Math.min(2, window.devicePixelRatio || 1);
  const pixelWidth = Math.max(1, Math.round(width * ratio));
  const pixelHeight = Math.max(1, Math.round(height * ratio));
  if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
  if (canvas.height !== pixelHeight) canvas.height = pixelHeight;

  const media = bin.find(clip.mediaId);
  const mediaDuration = Math.max(0.001, media?.duration ?? clip.duration);
  const context = canvas.getContext("2d");
  if (!context) return;

  if (clip.kind === "audio") {
    void loadPeaks(clip.mediaId).then((data) => {
      if (canvas!.dataset.sig !== sig || !data) return;
      drawWave(canvas!, context, clip, data);
    });
    return;
  }
  void loadStrip(clip.mediaId).then((image) => {
    if (canvas!.dataset.sig !== sig || !image) return;
    drawStrip(canvas!, context, clip, image, mediaDuration);
  });
}

function drawWave(canvas: HTMLCanvasElement, context: CanvasRenderingContext2D, clip: Clip, data: Peaks): void {
  const { width, height } = canvas;
  context.clearRect(0, 0, width, height);
  // currentColor, so the waveform follows the clip's own ink token and every
  // appearance profile recolours it without this module knowing a colour.
  context.fillStyle = getComputedStyle(canvas).color;
  const middle = height / 2;
  const scale = height / 2 - 1;

  // Bucket for a given column, resolved through the engine's speed mapping so a
  // retimed clip shows the samples it will actually play.
  const bucketAt = (x: number) => {
    const source = sourceTime(clip, (x / width) * clip.duration);
    return Math.min(data.buckets - 1, Math.max(0, Math.round((source / data.duration) * data.buckets)));
  };

  // Normalise to the loudest point in view: absolute level in a 26 px lane is
  // unreadable for a quiet recording, and the point of a waveform here is the
  // shape of what is on the clip. Gain is capped so silence does not turn into
  // amplified noise.
  let loudest = 0;
  for (let x = 0; x < width; x++) {
    const bucket = bucketAt(x);
    loudest = Math.max(loudest, Math.abs(data.high[bucket] ?? 0), Math.abs(data.low[bucket] ?? 0));
  }
  const gain = loudest > 0.005 ? Math.min(8, 0.92 / loudest) : 0;

  for (let x = 0; x < width; x++) {
    const bucket = bucketAt(x);
    const high = (data.high[bucket] ?? 0) * gain;
    const low = (data.low[bucket] ?? 0) * gain;
    const top = middle - high * scale;
    const bottom = middle - low * scale;
    context.fillRect(x, top, 1, Math.max(1, bottom - top));
  }
}

function drawStrip(canvas: HTMLCanvasElement, context: CanvasRenderingContext2D, clip: Clip, image: HTMLImageElement, mediaDuration: number): void {
  const { width, height } = canvas;
  context.clearRect(0, 0, width, height);
  // One row of STRIP_FRAMES equal frames, so each frame's slice is exact.
  const count = clip.kind === "image" ? 1 : STRIP_FRAMES;
  const frameWidth = image.naturalWidth / count;
  const frameHeight = image.naturalHeight;
  const drawWidth = Math.max(18, Math.round(height * (frameWidth / Math.max(1, frameHeight))));
  for (let x = 0; x < width; x += drawWidth) {
    const local = (x / width) * clip.duration;
    const source = sourceTime(clip, local);
    const index = Math.min(count - 1, Math.max(0, Math.floor((source / mediaDuration) * count)));
    const slice = Math.min(frameWidth, Math.max(1, ((width - x) / drawWidth) * frameWidth));
    context.drawImage(image, index * frameWidth, 0, slice, frameHeight, x, 0, (slice / frameWidth) * drawWidth, height);
  }
}
