// Project frame rates, as the engine's rates.py reads them: a whole rate from 1 to 120, or one of the four NTSC
// rates, carried as the nearest number to the exact ratio (30000 / 1001, never 29.97).
export const NTSC_RATES = [24000 / 1001, 30000 / 1001, 60000 / 1001, 120000 / 1001];
const NTSC_LABELS = ["23.976", "29.97", "59.94", "119.88"];

/** The project rate a value stands for: an NTSC rate given to a hundredth (29.97) or exactly, as the exact ratio; a
 * whole rate from 1 to 120 as itself; NaN for anything else. */
export function exactRate(value: number): number {
  if (!Number.isFinite(value)) return NaN;
  const ntsc = NTSC_RATES.find((rate) => Math.abs(value - rate) < 0.01);
  if (ntsc !== undefined) return ntsc;
  return Number.isInteger(value) && value >= 1 && value <= 120 ? value : NaN;
}

/** How a rate reads: "30", "29.97", "23.976". */
export function rateLabel(fps: number): string {
  const index = NTSC_RATES.findIndex((rate) => Math.abs(fps - rate) < 0.01);
  return index >= 0 ? NTSC_LABELS[index] : String(Math.round(fps * 1000) / 1000);
}
