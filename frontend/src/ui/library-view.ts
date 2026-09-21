import { api } from "../engine/api";
import type { MediaBin } from "../engine/media";
import { t } from "../i18n";
import { icon } from "./icons";
import { escapeHtml } from "./safe-text";
import "../styles/library.css";

type Kind = "stickers" | "music" | "sounds";

interface LibraryItem {
  id: string;
  name: string;
  category: string;
  url: string;
  seconds?: number;
  bpm?: number;
}

export interface LibraryView {
  tab: string;
  el: HTMLElement;
  load(): Promise<void>;
  pause(): void;
}

const TAB_FOR: Record<Kind, string> = { stickers: "Stickers", music: "Music", sounds: "Sounds" };

/** Seconds as m:ss, as the bin shows durations; under ten seconds in seconds, so a pop is not 0:00. */
function clock(seconds = 0): string {
  if (seconds < 10) return `${seconds.toFixed(seconds < 1 ? 2 : 1)} s`;
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/**
 * One of the library's tabs: stickers as a grid, music and sounds as rows that
 * preview in place. Adding copies the item into the media bin, where it is used
 * like anything imported. The catalogue loads the first time the tab opens.
 */
export function buildLibraryView(kind: Kind, bin: MediaBin): LibraryView {
  const el = document.createElement("div");
  el.className = `library-view library-${kind}`;
  el.hidden = true;
  el.innerHTML = `<p class="library-note" data-ref="note" aria-live="polite"></p><div data-ref="groups"></div><p class="library-licence">${escapeHtml(t("library.licence"))}</p>`;
  const noteEl = el.querySelector<HTMLElement>('[data-ref="note"]')!;
  const groups = el.querySelector<HTMLElement>('[data-ref="groups"]')!;
  const items = new Map<string, LibraryItem>();
  let started: Promise<void> | null = null;
  let player: HTMLAudioElement | null = null;
  let playing: HTMLButtonElement | null = null;

  const note = (message: string) => {
    if (noteEl.textContent !== message) noteEl.textContent = message;
  };
  const label = (item: LibraryItem) => (kind === "sounds" ? t(`library.sound.${item.id}`) : item.name);

  const pause = () => {
    player?.pause();
    player = null;
    if (playing) {
      playing.innerHTML = icon("play");
      playing.setAttribute("aria-label", t("library.play"));
      playing.classList.remove("is-playing");
      playing = null;
    }
  };

  const sticker = (item: LibraryItem) =>
    `<button type="button" class="library-sticker" data-add="${escapeHtml(item.id)}" title="${escapeHtml(`${t("library.add")}: ${item.name}`)}" aria-label="${escapeHtml(item.name)}"><img src="${escapeHtml(item.url)}" alt="" loading="lazy" draggable="false"></button>`;

  const row = (item: LibraryItem) => {
    const meta = [clock(item.seconds), item.bpm ? `${item.bpm} BPM` : ""].filter(Boolean).join(" · ");
    return `<li class="library-row"><button type="button" class="library-play" data-play="${escapeHtml(item.id)}" aria-label="${escapeHtml(t("library.play"))}">${icon("play")}</button><span class="library-name">${escapeHtml(label(item))}</span><span class="library-meta">${escapeHtml(meta)}</span><button type="button" class="library-add" data-add="${escapeHtml(item.id)}" aria-label="${escapeHtml(t("library.add"))}" title="${escapeHtml(t("library.add"))}">${icon("plus")}</button></li>`;
  };

  const render = (list: LibraryItem[]) => {
    const byCategory = new Map<string, LibraryItem[]>();
    for (const item of list) byCategory.set(item.category, [...(byCategory.get(item.category) ?? []), item]);
    const html: string[] = [];
    for (const [category, members] of byCategory) {
      html.push(`<h4 class="library-heading">${escapeHtml(t(`library.cat.${category}`))}</h4>`);
      html.push(kind === "stickers" ? `<div class="library-grid">${members.map(sticker).join("")}</div>` : `<ul class="library-list">${members.map(row).join("")}</ul>`);
    }
    groups.innerHTML = html.join("");
  };

  const add = async (button: HTMLButtonElement) => {
    const item = items.get(button.dataset.add ?? "");
    if (!item) return;
    button.disabled = true;
    try {
      await api(`/api/library/${kind}/${item.id}/import`, {});
      await bin.load();
      note(`${t("library.added")}: ${label(item)}`);
    } catch (error) {
      note(error instanceof Error ? error.message : String(error));
    } finally {
      button.disabled = false;
    }
  };

  el.addEventListener("click", (event) => {
    const target = event.target as HTMLElement;
    const play = target.closest<HTMLButtonElement>("[data-play]");
    if (play) {
      const again = play === playing;
      pause();
      const item = items.get(play.dataset.play ?? "");
      if (again || !item) return;
      const audio = new Audio(item.url);
      player = audio;
      playing = play;
      play.innerHTML = icon("pause");
      play.setAttribute("aria-label", t("library.stop"));
      play.classList.add("is-playing");
      audio.addEventListener("ended", () => {
        if (player === audio) pause();
      });
      audio.play().catch(() => {
        if (player === audio) pause();
      });
      return;
    }
    const adding = target.closest<HTMLButtonElement>("[data-add]");
    if (adding) void add(adding);
  });

  const load = () => {
    started ??= (async () => {
      note(t("library.preparing"));
      try {
        const data = await api<{ items: LibraryItem[] }>(`/api/library/${kind}`, undefined, "GET");
        for (const item of data.items) items.set(item.id, item);
        render(data.items);
        note("");
      } catch (error) {
        started = null;
        note(error instanceof Error ? error.message : String(error));
      }
    })();
    return started;
  };

  return { tab: TAB_FOR[kind], el, load, pause };
}
