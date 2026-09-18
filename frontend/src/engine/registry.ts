export interface EffectEntry {
  id: string;
  name: string;
  category: string;
  group: "video" | "audio";
  css: string;
  ffmpeg: string;
}

const effects: EffectEntry[] = [];

export function registerEffect(entry: EffectEntry): void {
  if (!effects.some((e) => e.id === entry.id)) effects.push(entry);
}

export function listEffects(category?: string): EffectEntry[] {
  return category ? effects.filter((e) => e.category === category) : effects.slice();
}

export function findEffect(id: string): EffectEntry | undefined {
  return effects.find((e) => e.id === id);
}

export function effectCategories(group: "video" | "audio"): string[] {
  const seen: string[] = [];
  for (const e of effects) {
    if (e.group === group && !seen.includes(e.category)) seen.push(e.category);
  }
  return seen;
}
