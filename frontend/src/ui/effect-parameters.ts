import type { Clip } from "../engine/types";
import { t } from "../i18n";

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

export function effectParameters(
  row: HTMLElement,
  entry: NonNullable<Clip["effects"]>[number],
  declarations: ParamDeclaration[],
  update: (name: string, value: number) => void,
): void {
  let panel = row.querySelector<HTMLDetailsElement>("details");
  if (!panel) {
    panel = document.createElement("details");
    panel.className = "effect-parameters";
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
      panel.append(line);
    }
    const slider = line.querySelector<HTMLInputElement>("input")!;
    const readout = line.querySelector<HTMLElement>(".param-value")!;
    const value = entry.params?.[decl.key] ?? decl.default;
    if (document.activeElement !== slider && Number(slider.value) !== value) slider.value = String(value);
    const shown = fmt(value, decl.step) + (decl.unit ? ` ${decl.unit}` : "");
    if (readout.textContent !== shown) readout.textContent = shown;
  }
}
