import type { MediaKind } from "./types";

export interface MediaItem {
  id: string;
  name: string;
  kind: MediaKind;
  size: number;
  thumb: boolean;
  duration: number;
  width: number;
  height: number;
  fps: number;
  /** X8: present when the file keeps more than one audio stream. */
  audioStreams?: Array<{ index: number; channels: number; language: string; title: string }>;
  /** The colour-managed pipeline: the source's space (Rec.709, HLG, PQ (HDR10), BT.2020 SDR) and what the decode does with it. */
  colour?: string;
  colourHandling?: "as decoded" | "tone-mapped to Rec.709" | "converted to Rec.709";
}

type BinListener = (items: MediaItem[], added?: MediaItem) => void;

const API = "/api/media";

export class MediaBin {
  private items: MediaItem[] = [];
  private listeners = new Set<BinListener>();

  get all(): MediaItem[] {
    return this.items;
  }

  find(id: string): MediaItem | undefined {
    return this.items.find((m) => m.id === id);
  }

  count(kind?: MediaKind): number {
    return kind ? this.items.filter((m) => m.kind === kind).length : this.items.length;
  }

  subscribe(fn: BinListener): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  private emit(added?: MediaItem) {
    for (const fn of this.listeners) fn(this.items, added);
  }

  async load(): Promise<void> {
    try {
      const res = await fetch(API);
      if (!res.ok) return;
      this.items = (await res.json()) as MediaItem[];
      this.emit();
    } catch {
      this.items = [];
    }
  }

  async upload(file: File): Promise<MediaItem | null> {
    const body = new FormData();
    body.append("file", file);
    try {
      const res = await fetch(API, { method: "POST", body });
      if (!res.ok) return null;
      const item = (await res.json()) as MediaItem;
      this.items.push(item);
      this.emit(item);
      return item;
    } catch {
      return null;
    }
  }
}

export function thumbUrl(item: MediaItem): string {
  return `${API}/${item.id}/thumb`;
}

export function fileUrl(mediaId: string): string {
  return `${API}/${mediaId}/file`;
}
