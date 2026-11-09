// Pieces the demo films are built from, shared by the app (which opens each demo as a new project)
// and the browser demos in demo/ and demos/<name>/, which import them from here.

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

export interface Crop {
  t: number;
  x: number;
  w: number;
}

export function cropKeyframes(crops: Crop[], scalePercent: number, canvasW: number, imageW: number): Array<{ t: number; props: Record<string, number>; interp: "ease" }> {
  return crops.map((crop) => ({
    t: Math.round(crop.t * 0.5 * 100) / 100,
    props: { scale: scalePercent, posX: Math.round((0.5 - (crop.x + crop.w / 2)) * ((imageW * scalePercent) / 100 / canvasW) * 100 * 10) / 10 },
    interp: "ease" as const,
  }));
}
