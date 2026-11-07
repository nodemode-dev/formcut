const GREY_W = 480;

export interface Crop {
  t: number;
  x: number;
  w: number;
}

function laplacian(grey: Uint8ClampedArray | Uint8Array, w: number, h: number): Float32Array {
  const out = new Float32Array(w * h);
  const at = (x: number, y: number): number => {
    let xx = x;
    let yy = y;
    if (xx < 0) xx = -xx;
    if (xx >= w) xx = 2 * w - 2 - xx;
    if (yy < 0) yy = -yy;
    if (yy >= h) yy = 2 * h - 2 - yy;
    return grey[yy * w + xx];
  };
  for (let y = 0; y < h; y += 1) {
    for (let x = 0; x < w; x += 1) {
      out[y * w + x] = Math.abs(at(x - 1, y) + at(x + 1, y) + at(x, y - 1) + at(x, y + 1) - 4 * at(x, y));
    }
  }
  return out;
}

export function reframe(frames: Uint8ClampedArray[], width: number, height: number, aspect = 9 / 16, smoothing = 0.8): Crop[] {
  if (!frames.length) return [];
  const cropW = Math.min(width, Math.round(height * aspect));
  const half = cropW / 2;
  const centres: number[] = [];
  frames.forEach((frame, index) => {
    const detail = laplacian(frame, width, height);
    const columns = new Float64Array(width);
    for (let y = 0; y < height; y += 1) {
      for (let x = 0; x < width; x += 1) {
        let value = detail[y * width + x];
        if (index > 0) value += Math.abs(frame[y * width + x] - frames[index - 1][y * width + x]) * 3;
        columns[x] += value;
      }
    }
    let total = 0;
    let weighted = 0;
    for (let x = 0; x < width; x += 1) {
      total += columns[x];
      weighted += columns[x] * x;
    }
    centres.push(total > 0 ? weighted / total : width / 2);
  });
  const s = Math.max(0, Math.min(0.99, smoothing));
  const smooth: number[] = [];
  let value = centres[0];
  for (const centre of centres) {
    value = value * s + centre * (1 - s);
    smooth.push(value);
  }
  value = smooth[smooth.length - 1];
  for (let i = smooth.length - 1; i >= 0; i -= 1) {
    value = value * s + smooth[i] * (1 - s);
    smooth[i] = value;
  }
  return smooth.map((centre, index) => {
    const left = Math.max(0, Math.min(width - cropW, centre - half));
    return { t: index, x: Math.round((left / width) * 1e5) / 1e5, w: Math.round((cropW / width) * 1e5) / 1e5 };
  });
}

const seek = (video: HTMLVideoElement, time: number): Promise<void> =>
  new Promise((resolve) => {
    if (Math.abs(video.currentTime - time) < 0.001 && video.readyState >= 2) {
      resolve();
      return;
    }
    video.addEventListener("seeked", () => resolve(), { once: true });
    video.currentTime = time;
  });

export async function analyseVideo(url: string, duration: number, progress: (fraction: number) => void): Promise<Crop[]> {
  const video = document.createElement("video");
  video.muted = true;
  video.preload = "auto";
  video.src = url;
  await new Promise<void>((resolve, reject) => {
    video.addEventListener("loadeddata", () => resolve(), { once: true });
    video.addEventListener("error", () => reject(new Error("The clip could not be read")), { once: true });
  });
  const ratio = video.videoHeight / video.videoWidth;
  const h = Math.max(1, Math.round(GREY_W * ratio));
  const canvas = document.createElement("canvas");
  canvas.width = GREY_W;
  canvas.height = h;
  const g = canvas.getContext("2d", { willReadFrequently: true })!;
  const frames: Uint8ClampedArray[] = [];
  const count = Math.max(2, Math.floor(duration * 2));
  for (let i = 0; i < count; i += 1) {
    await seek(video, Math.min(duration - 0.05, i * 0.5));
    g.drawImage(video, 0, 0, GREY_W, h);
    const rgba = g.getImageData(0, 0, GREY_W, h).data;
    const grey = new Uint8ClampedArray(GREY_W * h);
    for (let p = 0; p < grey.length; p += 1) grey[p] = Math.round(0.299 * rgba[p * 4] + 0.587 * rgba[p * 4 + 1] + 0.114 * rgba[p * 4 + 2]);
    frames.push(grey);
    progress((i + 1) / count);
  }
  video.removeAttribute("src");
  video.load();
  return reframe(frames, GREY_W, h);
}

export function cropKeyframes(crops: Crop[], scalePercent: number, canvasW: number, imageW: number): Array<{ t: number; props: Record<string, number>; interp: "ease" }> {
  return crops.map((crop) => ({
    t: Math.round(crop.t * 0.5 * 100) / 100,
    props: { scale: scalePercent, posX: Math.round((0.5 - (crop.x + crop.w / 2)) * ((imageW * scalePercent) / 100 / canvasW) * 100 * 10) / 10 },
    interp: "ease" as const,
  }));
}
