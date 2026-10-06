import { t } from "../i18n";

// A guided tour: each step rings a control and explains it in a card beside it. Steps whose control is not on screen
// are skipped. The ring and card are built once per tour and moved in place (no rebuild per step), on formcut's
// tokens and its overlay layer; Escape or Done ends it.

export interface TourStep {
  target: string;
  title: string;
  body: string;
}

const DEVICE_TOUR: TourStep[] = [
  { target: '[data-ref="chip-device"]', title: "tour.d1.title", body: "tour.d1.body" },
  { target: ".device-section [data-dev-model]", title: "tour.d2.title", body: "tour.d2.body" },
  { target: ".device-section [data-dev-screens]", title: "tour.d3.title", body: "tour.d3.body" },
  { target: ".stage", title: "tour.d4.title", body: "tour.d4.body" },
  { target: ".device-section [data-dev-template]", title: "tour.d5.title", body: "tour.d5.body" },
  { target: '[data-ref="chip-focus"]', title: "tour.d6.title", body: "tour.d6.body" },
  { target: '[data-ref="export"]', title: "tour.d7.title", body: "tour.d7.body" },
];
const SEEN = "formcut.tour.devices";
let active: (() => void) | null = null;

const visible = (selector: string) => {
  const el = document.querySelector<HTMLElement>(selector);
  if (!el) return null;
  const box = el.getBoundingClientRect();
  return box.width > 0 && box.height > 0 ? el : null;
};

export function runTour(all: TourStep[]): void {
  active?.();
  const steps = all.filter((step) => visible(step.target));
  if (!steps.length) return;
  const ring = document.createElement("div");
  ring.className = "tour-ring";
  const card = document.createElement("div");
  card.className = "tour-card";
  card.setAttribute("role", "dialog");
  card.innerHTML = `
    <div class="tour-count" data-tour="count"></div>
    <div class="tour-title" data-tour="title"></div>
    <p class="tour-body" data-tour="body"></p>
    <div class="tour-actions">
      <button class="tool-chip" data-tour="back">${t("tour.back")}</button>
      <button class="tool-chip is-primary" data-tour="next">${t("tour.next")}</button>
    </div>`;
  document.body.append(ring, card);
  const part = (name: string) => card.querySelector<HTMLElement>(`[data-tour="${name}"]`)!;
  let index = 0;

  const place = () => {
    const target = visible(steps[index].target);
    if (!target) return;
    const box = target.getBoundingClientRect();
    const pad = 6;
    Object.assign(ring.style, { left: `${box.left - pad}px`, top: `${box.top - pad}px`, width: `${box.width + pad * 2}px`, height: `${box.height + pad * 2}px` });
    const width = card.offsetWidth || 300;
    const height = card.offsetHeight || 140;
    const below = box.bottom + 14 + height < window.innerHeight;
    const top = below ? box.bottom + 14 : Math.max(8, box.top - 14 - height);
    const left = Math.min(window.innerWidth - width - 8, Math.max(8, box.left + box.width / 2 - width / 2));
    Object.assign(card.style, { left: `${left}px`, top: `${top}px` });
  };
  const show = () => {
    const step = steps[index];
    part("count").textContent = t("tour.step").replace("{n}", String(index + 1)).replace("{total}", String(steps.length));
    part("title").textContent = t(step.title);
    part("body").textContent = t(step.body);
    part("back").hidden = index === 0;
    part("next").textContent = index === steps.length - 1 ? t("tour.done") : t("tour.next");
    visible(step.target)?.scrollIntoView({ block: "nearest", inline: "nearest" });
    place();
  };
  const end = () => {
    window.removeEventListener("resize", place);
    window.removeEventListener("keydown", keys, true);
    ring.remove();
    card.remove();
    active = null;
  };
  const keys = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      end();
    }
  };
  part("back").addEventListener("click", () => { index = Math.max(0, index - 1); show(); });
  part("next").addEventListener("click", () => {
    if (index === steps.length - 1) end();
    else { index += 1; show(); }
  });
  window.addEventListener("resize", place);
  window.addEventListener("keydown", keys, true);
  active = end;
  show();
}

/** The device tour; with firstTime, only if this browser has not seen it. */
export function deviceTour(firstTime = false): void {
  try {
    if (firstTime && localStorage.getItem(SEEN)) return;
    localStorage.setItem(SEEN, "1");
  } catch {
    if (firstTime) return;
  }
  runTour(DEVICE_TOUR);
}
