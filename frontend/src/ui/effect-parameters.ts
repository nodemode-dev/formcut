import type { Clip } from "../engine/types";
import { t } from "../i18n";
import { icon } from "./icons";

export interface ParamDeclaration {
  key: string;
  labelKey: string;
  min: number;
  max: number;
  default: number;
  step: number;
  unit: string;
  group: string;
}

const fmt = (value: number, step: number) => step >= 1 ? String(Math.round(value)) : String(Math.round(value * 1000) / 1000);

/** How a parameter row keys itself: whether the parameter has keys, whether one sits at the playhead, its value there, and the toggle. */
export interface ParamKeying {
  state: (key: string) => "none" | "keyed" | "here";
  value: (key: string, base: number) => number;
  toggle: (key: string, value: number) => void;
}

export function effectParameters(
  row: HTMLElement,
  entry: NonNullable<Clip["effects"]>[number],
  declarations: ParamDeclaration[],
  update: (name: string, value: number) => void,
  keying?: ParamKeying,
): void {
  let panel = row.querySelector<HTMLDetailsElement>("details");
  if (!panel) {
    panel = document.createElement("details");
    panel.className = "effect-parameters";
    // Open from the start: an effect's controls are what someone adds it to reach.
    panel.open = true;
    const summary = document.createElement("summary");
    summary.textContent = t("fx.parameters");
    panel.append(summary);
    row.append(panel);
  }
  panel.hidden = !declarations.length;
  const keys = declarations.map((d) => d.key);
  for (const line of panel.querySelectorAll<HTMLElement>("[data-parameter]")) if (!keys.includes(line.dataset.parameter!)) line.remove();
  for (const decl of declarations) {
    let line = panel.querySelector<HTMLLabelElement>(`label[data-parameter="${decl.key}"]`);
    if (!line) {
      line = document.createElement("label");
      line.className = "param-row";
      line.dataset.parameter = decl.key;
      const text = document.createElement("span");
      text.className = "param-name";
      text.textContent = t(decl.labelKey);
      const slider = document.createElement("input");
      slider.type = "range";
      slider.className = "value-slider";
      slider.min = String(decl.min);
      slider.max = String(decl.max);
      slider.step = String(decl.step);
      const readout = document.createElement("span");
      readout.className = "param-value";
      const reset = document.createElement("button");
      reset.type = "button";
      reset.className = "param-reset";
      reset.title = t("fx.reset");
      reset.textContent = "\u21ba";
      slider.addEventListener("input", () => {
        const value = Number(slider.value);
        readout.textContent = fmt(value, decl.step) + (decl.unit ? ` ${decl.unit}` : "");
        update(decl.key, value);
      });
      reset.addEventListener("click", (event) => {
        event.preventDefault();
        update(decl.key, decl.default);
      });
      line.append(text, slider, readout, reset);
      if (keying) {
        // A keyframe on the parameter at the playhead: the same diamond the
        // transform rows carry, so a keyed effect reads like a keyed move.
        const diamond = document.createElement("button");
        diamond.type = "button";
        diamond.className = "iconbtn kf-btn param-key";
        diamond.title = t("kf.at");
        diamond.setAttribute("aria-label", t("kf.at"));
        diamond.innerHTML = icon("diamond");
        diamond.addEventListener("click", (event) => {
          event.preventDefault();
          keying.toggle(decl.key, Number(slider.value));
        });
        line.append(diamond);
      }
      panel.append(line);
    }
    const slider = line.querySelector<HTMLInputElement>("input")!;
    const readout = line.querySelector<HTMLElement>(".param-value")!;
    const state = keying?.state(decl.key) ?? "none";
    const base = entry.params?.[decl.key] ?? decl.default;
    const value = state === "none" ? base : keying!.value(decl.key, base);
    if (document.activeElement !== slider && Number(slider.value) !== value) slider.value = String(value);
    const shown = fmt(value, decl.step) + (decl.unit ? ` ${decl.unit}` : "");
    if (readout.textContent !== shown) readout.textContent = shown;
    const diamond = line.querySelector<HTMLElement>(".param-key");
    if (diamond) {
      if (diamond.classList.contains("is-accent") !== (state === "here")) diamond.classList.toggle("is-accent", state === "here");
      if (diamond.classList.contains("is-keyed") !== (state !== "none")) diamond.classList.toggle("is-keyed", state !== "none");
    }
  }
}
