import type { Clip } from "../engine/types";

export function effectParameters(row: HTMLElement, entry: NonNullable<Clip["effects"]>[number], defaults: Record<string, number>, update: (name: string, value: number) => void): void {
  let panel = row.querySelector<HTMLDetailsElement>("details");
  if (!panel) { panel = document.createElement("details"); panel.className = "effect-parameters"; const summary = document.createElement("summary"); summary.textContent = "Parameters"; panel.append(summary); row.append(panel); }
  const keys = Object.keys(defaults);
  panel.hidden = !keys.length;
  for (const label of panel.querySelectorAll<HTMLElement>("[data-parameter]")) if (!keys.includes(label.dataset.parameter!)) label.remove();
  for (const name of keys) {
    let label = [...panel.querySelectorAll<HTMLLabelElement>("label")].find(l => l.dataset.parameter === name);
    if (!label) {
      label = document.createElement("label"); label.dataset.parameter = name;
      const text = document.createElement("span"); text.textContent = name.replaceAll("_", " ");
      const input = document.createElement("input"); input.type = "number"; input.step = name === "size" || name === "levels" ? "1" : "0.01";
      input.addEventListener("change", () => { const value = Number(input.value); if (Number.isFinite(value)) update(name, value); });
      label.append(text, input); panel.append(label);
    }
    const input = label.querySelector("input")!;
    const value = String(entry.params?.[name] ?? defaults[name]);
    if (document.activeElement !== input && input.value !== value) input.value = value;
  }
}
