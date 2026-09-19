import { text } from "../i18n/text";

const STORE = "formcut.trackHeights";
const MIN = 32;
const MAX = 240;
const DEFAULT = 56;

function readAll(): Record<string, number> {
  try {
    const raw = localStorage.getItem(STORE);
    return raw ? (JSON.parse(raw) as Record<string, number>) : {};
  } catch {
    return {};
  }
}

function writeOne(index: number, height: number): void {
  try {
    const all = readAll();
    all[String(index)] = height;
    localStorage.setItem(STORE, JSON.stringify(all));
  } catch {
    return;
  }
}

export function trackHeight(index: number): number {
  const stored = readAll()[String(index)];
  return typeof stored === "number" ? Math.min(MAX, Math.max(MIN, stored)) : DEFAULT;
}

export function installTrackHeightGrip(header: HTMLElement, lane: HTMLElement, index: number): void {
  const apply = (height: number) => {
    const value = `${height}px`;
    const targets = [header, lane];
    const kfHead = lane.nextElementSibling;
    if (kfHead instanceof HTMLElement && kfHead.classList.contains("kfb-head")) {
      targets.push(kfHead);
      if (kfHead.nextElementSibling instanceof HTMLElement && kfHead.nextElementSibling.classList.contains("kfb-body")) targets.push(kfHead.nextElementSibling);
    }
    for (const node of targets) if (node.style.getPropertyValue("--track-h") !== value) node.style.setProperty("--track-h", value);
    lane.dispatchEvent(new CustomEvent("formcut:track-height", { bubbles: true, detail: { height } }));
  };
  apply(trackHeight(index));
  const grip = document.createElement("div");
  grip.className = "track-grip";
  grip.dataset.feature = "tl.heights";
  grip.title = text("Drag to change the track height");
  grip.setAttribute("role", "separator");
  grip.setAttribute("aria-orientation", "horizontal");
  header.append(grip);
  grip.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    const startY = event.clientY;
    const from = header.getBoundingClientRect().height;
    let height = from;
    grip.setPointerCapture(event.pointerId);
    header.classList.add("is-resizing");
    const move = (moveEvent: PointerEvent) => {
      height = Math.min(MAX, Math.max(MIN, Math.round(from + moveEvent.clientY - startY)));
      apply(height);
    };
    const end = () => {
      grip.removeEventListener("pointermove", move);
      grip.removeEventListener("pointerup", end);
      grip.removeEventListener("pointercancel", end);
      header.classList.remove("is-resizing");
      writeOne(index, height);
    };
    grip.addEventListener("pointermove", move);
    grip.addEventListener("pointerup", end);
    grip.addEventListener("pointercancel", end);
  });
  grip.addEventListener("dblclick", () => {
    apply(DEFAULT);
    writeOne(index, DEFAULT);
  });
}
