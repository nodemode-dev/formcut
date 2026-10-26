import { t } from "../i18n";
import { activeProfile, onInterfaceMode } from "./interface-mode";

const MIN_SIDE = 240;

export function installWorkspaceLayout(): void {
  const dividers = new Map<string, HTMLElement>();
  const workspace = document.querySelector<HTMLElement>(".workspace")!;
  const focus = document.querySelector<HTMLButtonElement>('.titlebar-right [data-ref="focus-preview"]');
  const panels = document.querySelector<HTMLButtonElement>('.titlebar-right [data-ref="panels"]');
  if (!focus || !panels) return;
  // Sizes are pixels because a divider drag is a pixel gesture: storing a
  // percentage would make the same drag mean different things at different
  // window widths. Clamped on apply, so a narrow window cannot strand a pane.
  type Slot = "left" | "right" | "bottom";
  const DEFAULTS = {
    media: true, inspector: true, timeline: true, focus: false, height: 42,
    left: 340, right: 344, swap: false, timelineTop: false,
    // P7: where each pane lives, and which pane is in front when two share a
    // slot. Stored per interface profile, so Easy and Advanced keep their own
    // arrangement rather than fighting over one.
    slots: { media: "left" as Slot, inspector: "right" as Slot, timeline: "bottom" as Slot },
    front: { left: "media", right: "inspector", bottom: "timeline" } as Record<Slot, string>,
  };
  const layoutKey = () => `formcut.layout.${activeProfile().id}`;
  const readLayout = (): typeof DEFAULTS => {
    for (const key of [layoutKey(), "formcut.layout"]) {
      try {
        const raw = localStorage.getItem(key);
        if (!raw) continue;
        const parsed = JSON.parse(raw);
        return {
          ...DEFAULTS, ...parsed,
          slots: { ...DEFAULTS.slots, ...(parsed.slots ?? {}) },
          front: { ...DEFAULTS.front, ...(parsed.front ?? {}) },
        };
      } catch { /* try the next key */ }
    }
    return { ...DEFAULTS, slots: { ...DEFAULTS.slots }, front: { ...DEFAULTS.front } };
  };
  let settings = readLayout();
  const menu = document.createElement("div"); menu.className = "dropdown"; menu.hidden = true;
  const options = new Map<string, HTMLButtonElement>();
  const sideOf = (key: "left" | "right") => {
    const pane: "media" | "inspector" = (key === "left") !== settings.swap ? "media" : "inspector";
    return { pane, width: pane === "media" ? ("left" as const) : ("right" as const), sign: key === "left" ? 1 : -1 };
  };
  const placeDividers = () => {
    const box = workspace.getBoundingClientRect();
    const paneOf = (name: string) => workspace.querySelector<HTMLElement>(`.pane-${name}`);
    const hide = (key: string, hidden: boolean) => {
      const handle = dividers.get(key);
      if (handle) handle.hidden = hidden;
    };
    const showSides = !settings.focus;
    hide("left", !showSides || !settings[sideOf("left").pane]);
    hide("right", !showSides || !settings[sideOf("right").pane]);
    hide("row", !showSides || !settings.timeline);
    for (const key of ["left", "right"] as const) {
      const handle = dividers.get(key), pane = paneOf(sideOf(key).pane);
      if (!handle || handle.hidden || !pane) continue;
      const rect = pane.getBoundingClientRect();
      handle.style.left = `${(key === "left" ? rect.right + 1 : rect.left - 7) - box.left}px`;
      handle.style.top = `${rect.top - box.top}px`;
      handle.style.height = `${rect.height}px`;
    }
    const row = dividers.get("row"), timeline = paneOf("timeline");
    if (row && !row.hidden && timeline) {
      const rect = timeline.getBoundingClientRect();
      row.style.top = `${(settings.timelineTop ? rect.bottom : rect.top - 7) - box.top}px`;
      row.style.left = `${rect.left - box.left}px`;
      row.style.width = `${rect.width}px`;
    }
  };
  // P7: one tab strip per slot that holds more than one pane, positioned over
  // the slot the same way the dividers are, so no pane markup has to change.
  const tabStrips = new Map<string, HTMLElement>();
  const placeTabs = (left: string[], right: string[], bottom: string[]) => {
    const box = workspace.getBoundingClientRect();
    for (const [slot, members] of [["left", left], ["right", right], ["bottom", bottom]] as const) {
      let strip = tabStrips.get(slot);
      if (members.length < 2) {
        if (strip) strip.hidden = true;
        continue;
      }
      if (!strip) {
        strip = document.createElement("div");
        strip.className = "pane-stack-tabs";
        strip.dataset.slot = slot;
        workspace.append(strip);
        tabStrips.set(slot, strip);
      }
      strip.hidden = false;
      strip.replaceChildren(...members.map((pane) => {
        const tab = document.createElement("button");
        tab.className = "pane-stack-tab" + (settings.front[slot as Slot] === pane ? " is-active" : "");
        tab.textContent = t(`layout.pane.${pane}`);
        tab.dataset.pane = pane;
        tab.addEventListener("click", () => { settings.front[slot as Slot] = pane; apply(); });
        return tab;
      }));
      const front = workspace.querySelector<HTMLElement>(`.pane-${settings.front[slot as Slot]}`);
      if (!front) continue;
      const rect = front.getBoundingClientRect();
      strip.style.left = `${rect.left - box.left}px`;
      strip.style.top = `${rect.top - box.top}px`;
      strip.style.width = `${rect.width}px`;
    }
  };
  const apply = () => {
    workspace.dataset.focus = String(settings.focus);
    for (const part of ["media", "inspector", "timeline"] as const) { workspace.dataset[part + "Hidden"] = String(!settings[part]); options.get(part)?.setAttribute("aria-pressed", String(settings[part])); }
    const room = workspace.clientWidth || window.innerWidth;
    const widest = Math.max(MIN_SIDE, Math.round(room * 0.45));
    settings.left = Math.min(widest, Math.max(MIN_SIDE, Math.round(settings.left)));
    settings.right = Math.min(widest, Math.max(MIN_SIDE, Math.round(settings.right)));
    // Which panes sit in each slot, in a stable order, hidden panes excluded.
    const inSlot = (slot: Slot) => (["media", "inspector", "timeline"] as const)
      .filter((pane) => settings.slots[pane] === slot && settings[pane] && !settings.focus);
    const left = inSlot("left"), right = inSlot("right"), bottom = inSlot("bottom");
    for (const slot of ["left", "right", "bottom"] as const) {
      const members = slot === "left" ? left : slot === "right" ? right : bottom;
      if (members.length && !members.includes(settings.front[slot] as typeof members[number])) {
        settings.front[slot] = members[0];
      }
    }
    // A pane is placed by its slot; when a slot holds more than one, only the
    // front pane shows, and the others stay in the DOM so their node identity
    // and their state survive the move.
    for (const pane of ["media", "inspector", "timeline"] as const) {
      const node = workspace.querySelector<HTMLElement>(`.pane-${pane}`);
      if (!node) continue;
      const slot = settings.slots[pane];
      const members = slot === "left" ? left : slot === "right" ? right : bottom;
      const shown = settings[pane] && !settings.focus && settings.front[slot] === pane;
      node.style.gridArea = members.length ? slot : "";
      node.dataset.slot = slot;
      node.dataset.stacked = String(members.length > 1);
      if (node.hidden !== !shown) node.hidden = !shown;
    }
    const columnNames = settings.swap
      ? [right.length ? "right" : "", "preview", left.length ? "left" : ""]
      : [left.length ? "left" : "", "preview", right.length ? "right" : ""];
    const slots = columnNames.filter(Boolean);
    const columns = slots.map((name) => (name === "preview" ? "minmax(240px, 1fr)"
      : `${name === "left" ? settings.left : settings.right}px`));
    const band = bottom.length ? `"${slots.map(() => "bottom").join(" ")}"` : "";
    const panes = `"${slots.join(" ")}"`;
    workspace.style.gridTemplateColumns = settings.focus ? "minmax(0, 1fr)" : columns.join(" ");
    workspace.style.gridTemplateAreas = !band ? panes : settings.timelineTop ? `${band} ${panes}` : `${panes} ${band}`;
    workspace.style.gridTemplateRows = !band
      ? "minmax(0, 1fr)"
      : settings.timelineTop
        ? `minmax(180px, ${settings.height}%) minmax(0, 1fr)`
        : `minmax(0, 1fr) minmax(180px, ${settings.height}%)`;
    workspace.dataset.swap = String(settings.swap);
    workspace.dataset.timelineTop = String(settings.timelineTop);
    placeTabs(left, right, bottom);
    placeDividers();
    focus.setAttribute("aria-pressed", String(settings.focus));
    try { localStorage.setItem(layoutKey(), JSON.stringify(settings)); } catch { /* settings remain active */ }
  };
  for (const [key, title] of [["media", "Media panel"], ["inspector", "Inspector panel"], ["timeline", "Timeline panel"]] as const) {
    const button = document.createElement("button"); button.className = "dropdown-item"; button.textContent = title;
    button.addEventListener("click", () => { settings[key] = !settings[key]; settings.focus = false; apply(); }); menu.append(button); options.set(key, button);
  }
  document.addEventListener("formcut:layout", (event) => {
    const detail = (event as CustomEvent<Partial<typeof settings>>).detail;
    if (!detail || typeof detail !== "object") return;
    settings = { ...settings, ...detail };
    apply();
  });
  // Slot moves live in the same menu as pane visibility, so they are reachable
  // without a drag for anyone who cannot make one.
  for (const [key, labelKey] of [["swap", "layout.swap"], ["timelineTop", "layout.timelinetop"]] as const) {
    const button = document.createElement("button");
    button.className = "dropdown-item";
    button.textContent = t(labelKey);
    button.setAttribute("aria-pressed", String(settings[key]));
    button.dataset.ref = key;
    button.addEventListener("click", () => {
      settings[key] = !settings[key];
      button.setAttribute("aria-pressed", String(settings[key]));
      apply();
    });
    menu.append(button);
  }
  // Moving a pane is a menu action as well as a drag, so it is reachable
  // without a pointer gesture.
  for (const pane of ["media", "inspector", "timeline"] as const) {
    for (const slot of ["left", "right", "bottom"] as const) {
      const item = document.createElement("button");
      item.className = "dropdown-item";
      item.dataset.move = `${pane}:${slot}`;
      item.textContent = `${t(`layout.pane.${pane}`)} → ${t(`layout.slot.${slot}`)}`;
      item.addEventListener("click", () => {
        settings.slots[pane] = slot;
        settings.front[slot] = pane;
        settings[pane] = true;
        apply();
      });
      menu.append(item);
    }
  }
  onInterfaceMode(() => { settings = readLayout(); apply(); });
  const reset = document.createElement("button"); reset.className = "dropdown-item"; reset.textContent = "Reset layout"; reset.addEventListener("click", () => { settings = { ...DEFAULTS, slots: { ...DEFAULTS.slots }, front: { ...DEFAULTS.front } }; menu.hidden = true; apply(); }); menu.append(reset);
  document.body.append(menu);
  focus.title = "Focus preview"; focus.addEventListener("click", () => { settings.focus = !settings.focus; apply(); });
  panels.title = "Panels"; panels.addEventListener("click", () => { const box = panels.getBoundingClientRect(); menu.style.right = "12px"; menu.style.top = `${box.bottom}px`; menu.hidden = !menu.hidden; });
  document.addEventListener("pointerdown", event => { if (!menu.contains(event.target as Node) && !panels.contains(event.target as Node) && !menu.hidden) menu.hidden = true; }, true);
  document.addEventListener("keydown", event => { if (event.key === "Escape") { menu.hidden = true; if (settings.focus) { settings.focus = false; apply(); } } });
  const size = workspace.querySelector<HTMLButtonElement>(".tl-tabs .select-chip");
  if (size) {
    const heights = document.createElement("div"); heights.className = "dropdown"; heights.hidden = true; heights.setAttribute("role", "menu");
    for (const [label, value] of [["Short timeline", 25], ["Medium timeline", 42], ["Tall timeline", 65]] as const) {
      const item = document.createElement("button"); item.className = "dropdown-item"; item.textContent = label; item.dataset.height = String(value); item.setAttribute("role", "menuitemradio");
      item.addEventListener("click", () => { settings.height = value; heights.hidden = true; size.setAttribute("aria-expanded", "false"); apply(); });
      heights.append(item);
    }
    document.body.append(heights);
    size.title = "Timeline height"; size.setAttribute("aria-haspopup", "menu"); size.setAttribute("aria-expanded", "false");
    size.addEventListener("click", () => {
      const box = size.getBoundingClientRect(); heights.style.left = `${box.left}px`; heights.style.top = `${box.bottom + 4}px`;
      for (const item of heights.querySelectorAll<HTMLElement>("[data-height]")) item.setAttribute("aria-pressed", String(Number(item.dataset.height) === settings.height));
      heights.hidden = !heights.hidden; size.setAttribute("aria-expanded", String(!heights.hidden));
    });
    document.addEventListener("pointerdown", event => { if (!heights.hidden && !heights.contains(event.target as Node) && !size.contains(event.target as Node)) { heights.hidden = true; size.setAttribute("aria-expanded", "false"); } }, true);
    document.addEventListener("keydown", event => { if (event.key === "Escape" && !heights.hidden) { heights.hidden = true; size.setAttribute("aria-expanded", "false"); } });
  }
  // --- dividers -------------------------------------------------------------
  // Absolutely positioned over the grid gaps rather than added as grid tracks,
  // so the template stays the three panes it always was and a divider cannot
  // change what is placed where.
  for (const [key, orientation] of [["left", "vertical"], ["right", "vertical"], ["row", "horizontal"]] as const) {
    const handle = document.createElement("div");
    handle.className = `pane-divider is-${orientation}`;
    handle.dataset.divider = key;
    handle.tabIndex = 0;
    handle.setAttribute("role", "separator");
    handle.setAttribute("aria-orientation", orientation);
    handle.setAttribute("aria-label", t(key === "row" ? "layout.divider.timeline" : key === "left" ? "layout.divider.media" : "layout.divider.inspector"));
    const nudge = (amount: number) => {
      if (key === "row") settings.height = Math.min(80, Math.max(15, settings.height + amount));
      else { const side = sideOf(key); settings[side.width] += side.sign * amount * 8; }
      apply();
    };
    handle.addEventListener("keydown", (event) => {
      const horizontal = orientation === "vertical";
      const step = horizontal
        ? (event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0)
        : (event.key === "ArrowDown" ? -1 : event.key === "ArrowUp" ? 1 : 0);
      if (step) { event.preventDefault(); nudge(step); return; }
      if (event.key === "Home" || event.key === "End") { event.preventDefault(); nudge(event.key === "Home" ? -40 : 40); }
    });
    handle.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      event.preventDefault();
      handle.setPointerCapture(event.pointerId);
      handle.classList.add("is-dragging");
      const box = workspace.getBoundingClientRect();
      // Track the offset between the pointer and the edge it grabbed, so the
      // divider follows the gesture instead of snapping under the cursor.
      const startX = event.clientX, startY = event.clientY;
      const fromLeft = settings.left, fromRight = settings.right, fromHeight = settings.height;
      const move = (moveEvent: PointerEvent) => {
        if (key === "row") {
          const delta = (settings.timelineTop ? moveEvent.clientY - startY : startY - moveEvent.clientY) / box.height * 100;
          settings.height = Math.min(80, Math.max(15, Math.round(fromHeight + delta)));
        } else {
          const side = sideOf(key);
          settings[side.width] = Math.round((side.width === "left" ? fromLeft : fromRight) + side.sign * (moveEvent.clientX - startX));
        }
        apply();
      };
      const end = (endEvent: PointerEvent) => {
        handle.releasePointerCapture(endEvent.pointerId);
        handle.classList.remove("is-dragging");
        handle.removeEventListener("pointermove", move);
        handle.removeEventListener("pointerup", end);
        handle.removeEventListener("pointercancel", end);
      };
      handle.addEventListener("pointermove", move);
      handle.addEventListener("pointerup", end);
      handle.addEventListener("pointercancel", end);
    });
    workspace.append(handle);
    dividers.set(key, handle);
  }
  // Everything that is positioned over the grid has to follow a resize: the
  // dividers and, since P7, the stack tab strips, which were left behind.
  const replace = () => {
    const inSlot = (slot: "left" | "right" | "bottom") => (["media", "inspector", "timeline"] as const)
      .filter((pane) => settings.slots[pane] === slot && settings[pane] && !settings.focus);
    placeTabs(inSlot("left"), inSlot("right"), inSlot("bottom"));
    placeDividers();
  };
  const observer = new ResizeObserver(() => replace());
  observer.observe(workspace);
  for (const pane of ["media", "inspector", "timeline", "preview"]) {
    const node = workspace.querySelector(`.pane-${pane}`);
    if (node) observer.observe(node);
  }
  window.addEventListener("resize", replace);
  apply();
}
