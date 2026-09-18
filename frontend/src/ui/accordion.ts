const STORE = "formcut.accordion";

function readState(): Record<string, true> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(STORE) ?? "{}");
    return parsed && typeof parsed === "object" ? (parsed as Record<string, true>) : {};
  } catch {
    return {};
  }
}

export function installAccordions(root: HTMLElement): void {
  const collapsed = readState();
  const save = () => {
    try {
      localStorage.setItem(STORE, JSON.stringify(collapsed));
    } catch {
      return;
    }
  };
  for (const head of root.querySelectorAll<HTMLElement>(".section-head, .cat-group")) {
    const chevron = head.querySelector<SVGElement>(":scope > svg");
    if (!chevron) continue;
    const group = head.classList.contains("cat-group");
    const label = (head.textContent ?? "").trim();
    const owner = head.closest<HTMLElement>("[data-section], [data-ref]");
    const key = `${group ? "group" : "section"}:${owner?.dataset.section ?? owner?.dataset.ref ?? ""}:${label}`;
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "iconbtn acc-toggle";
    toggle.setAttribute("aria-label", label);
    toggle.append(chevron);
    head.append(toggle);
    const apply = () => {
      const shut = collapsed[key] === true;
      toggle.setAttribute("aria-expanded", String(!shut));
      if (group) {
        for (let node = head.nextElementSibling; node && !node.classList.contains("cat-group"); node = node.nextElementSibling) {
          (node as HTMLElement).dataset.groupCollapsed = String(shut);
        }
      } else if (head.parentElement) {
        head.parentElement.dataset.collapsed = String(shut);
      }
    };
    apply();
    head.addEventListener("click", (event) => {
      const hit = (event.target as Element).closest("button, input, select, a");
      if (hit && hit !== toggle) return;
      if (collapsed[key]) delete collapsed[key];
      else collapsed[key] = true;
      apply();
      save();
    });
  }
}
