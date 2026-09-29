// The full-screen viewer: a picture (or a video) on its own, above everything else in formcut, as the Studio image
// generator had it alone until 2.2.1. Used by the generator's results, the media library's cards and the start
// screen's media: a click on View (or Space on a focused card), Escape or a click outside the bar to close, the
// arrow keys through the pictures beside it. One element for the whole page, made on first use.

import { t } from "../i18n";

export type ViewItem = { src: string; kind: "image" | "video"; caption?: string };

let root: HTMLDivElement | null = null;
let items: ViewItem[] = [];
let at = 0;
let returnTo: HTMLElement | null = null;

function build(): HTMLDivElement {
  const viewer = document.createElement("div");
  viewer.className = "gen-viewer";
  viewer.hidden = true;
  viewer.setAttribute("role", "dialog");
  viewer.setAttribute("aria-modal", "true");
  viewer.innerHTML =
    `<img class="gen-viewer-image" alt=""><video class="gen-viewer-video" controls playsinline hidden></video>` +
    `<div class="gen-viewer-bar"><span class="gen-viewer-caption"></span><span class="gen-viewer-count"></span>` +
    `<button type="button" class="tool-chip gen-viewer-close">${t("gen.view.close")}</button></div>`;
  viewer.addEventListener("click", (event) => {
    const target = event.target as HTMLElement;
    if (target.closest(".gen-viewer-close") || !target.closest(".gen-viewer-bar, .gen-viewer-video")) closeViewer();
  });
  document.addEventListener(
    "keydown",
    (event) => {
      if (viewer.hidden) return;
      if (event.key === "Escape" || (event.key === " " && !(event.target as HTMLElement).closest("video"))) {
        event.preventDefault();
        event.stopPropagation();
        closeViewer();
      } else if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
        event.preventDefault();
        event.stopPropagation();
        show(at + (event.key === "ArrowRight" ? 1 : -1));
      }
    },
    true,
  );
  document.body.append(viewer);
  return viewer;
}

function show(index: number): void {
  if (!root || index < 0 || index >= items.length) return;
  at = index;
  const item = items[at];
  const image = root.querySelector<HTMLImageElement>(".gen-viewer-image")!;
  const video = root.querySelector<HTMLVideoElement>(".gen-viewer-video")!;
  image.hidden = item.kind !== "image";
  video.hidden = item.kind !== "video";
  if (item.kind === "image") {
    video.pause();
    video.removeAttribute("src");
    image.src = item.src;
  } else {
    image.removeAttribute("src");
    video.src = item.src;
    void video.play().catch(() => { /* a click plays it */ });
  }
  root.querySelector<HTMLElement>(".gen-viewer-caption")!.textContent = item.caption ?? "";
  root.querySelector<HTMLElement>(".gen-viewer-count")!.textContent = items.length > 1 ? `${at + 1} / ${items.length}` : "";
}

/** Opens the viewer on list[index]; the arrows move through the rest of the list. */
export function openViewer(list: ViewItem[], index = 0): void {
  if (!list.length) return;
  root ??= build();
  items = list;
  returnTo = document.activeElement instanceof HTMLElement ? document.activeElement : null;
  root.hidden = false;
  show(Math.max(0, Math.min(index, list.length - 1)));
  root.querySelector<HTMLButtonElement>(".gen-viewer-close")!.focus();
}

export function closeViewer(): void {
  if (!root || root.hidden) return;
  root.hidden = true;
  const video = root.querySelector<HTMLVideoElement>(".gen-viewer-video")!;
  video.pause();
  video.removeAttribute("src");
  root.querySelector<HTMLImageElement>(".gen-viewer-image")!.removeAttribute("src");
  returnTo?.focus();
  returnTo = null;
}

/** A media library item as the viewer shows it: the file itself, a picture or a video, with its name. */
export function mediaView(item: { id: string; kind: string; name: string }): ViewItem | null {
  if (item.kind !== "image" && item.kind !== "video") return null;
  return { src: `/api/media/${item.id}/file`, kind: item.kind, caption: item.name };
}
