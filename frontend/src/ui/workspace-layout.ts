import { t } from "../i18n";

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
  let settings = {
    media: true, inspector: true, timeline: true, focus: false, height: 42,
    left: 340, right: 320, swap: false, timelineTop: false,
  };
  try { settings = { ...settings, ...JSON.parse(localStorage.getItem("formcut.layout") || "{}") }; } catch { /* defaults */ }
  const menu = document.createElement("div"); menu.className = "dropdown"; menu.hidden = true;
  const options = new Map<string, HTMLButtonElement>();
  // A divider sits on the gap between two panes, so its position is read from
  // the panes themselves rather than recomputed from the settings.
  const placeDividers = () => {
    const box = workspace.getBoundingClientRect();
    const paneOf = (name: string) => workspace.querySelector<HTMLElement>(`.pane-${name}`);
    const edge = (node: HTMLElement | null, side: "right" | "left") => {
      if (!node) return null;
      const rect = node.getBoundingClientRect();
      return (side === "right" ? rect.right : rect.left) - box.left;
    };
    const hide = (key: string, hidden: boolean) => {
      const handle = dividers.get(key);
      if (handle) handle.hidden = hidden;
    };
    const media = paneOf(settings.swap ? "inspector" : "media");
    const inspector = paneOf(settings.swap ? "media" : "inspector");
    const timeline = paneOf("timeline");
    const left = dividers.get("left"), right = dividers.get("right"), row = dividers.get("row");
    const showSides = !settings.focus;
    hide("left", !showSides || !settings.media);
    hide("right", !showSides || !settings.inspector);
    hide("row", !showSides || !settings.timeline);
    if (left && !left.hidden) left.style.left = `${(edge(media, "right") ?? 0) + 1}px`;
    if (right && !right.hidden) right.style.left = `${(edge(inspector, "left") ?? 0) - 7}px`;
    if (row && !row.hidden && timeline) {
      const rect = timeline.getBoundingClientRect();
      row.style.top = `${(settings.timelineTop ? rect.bottom : rect.top) - box.top - 7}px`;
    }
  };
  const apply = () => {
    workspace.dataset.focus = String(settings.focus);
    for (const part of ["media", "inspector", "timeline"] as const) { workspace.dataset[part + "Hidden"] = String(!settings[part]); options.get(part)?.setAttribute("aria-pressed", String(settings[part])); }
    const room = workspace.clientWidth || window.innerWidth;
    const widest = Math.max(MIN_SIDE, Math.round(room * 0.45));
    settings.left = Math.min(widest, Math.max(MIN_SIDE, Math.round(settings.left)));
    settings.right = Math.min(widest, Math.max(MIN_SIDE, Math.round(settings.right)));
    const leftTrack = settings.media ? `${settings.left}px` : "";
    const rightTrack = settings.inspector ? `${settings.right}px` : "";
    const tracks = settings.swap ? [rightTrack, "minmax(240px, 1fr)", leftTrack] : [leftTrack, "minmax(240px, 1fr)", rightTrack];
    workspace.style.gridTemplateColumns = settings.focus ? "minmax(0, 1fr)" : tracks.filter(Boolean).join(" ");
    workspace.style.gridTemplateRows = settings.focus || !settings.timeline
      ? "minmax(0, 1fr)"
      : settings.timelineTop
        ? `minmax(180px, ${settings.height}%) minmax(0, 1fr)`
        : `minmax(0, 1fr) minmax(180px, ${settings.height}%)`;
    // Slot moves are grid placement, not DOM moves: nothing is re-parented, so
    // no pane is rebuilt and nothing loses focus or scroll when slots change.
    workspace.dataset.swap = String(settings.swap);
    workspace.dataset.timelineTop = String(settings.timelineTop);
    placeDividers();
    focus.setAttribute("aria-pressed", String(settings.focus));
    try { localStorage.setItem("formcut.layout", JSON.stringify(settings)); } catch { /* settings remain active */ }
  };
  for (const [key, title] of [["media", "Media panel"], ["inspector", "Inspector panel"], ["timeline", "Timeline panel"]] as const) {
    const button = document.createElement("button"); button.className = "dropdown-item"; button.textContent = title;
    button.addEventListener("click", () => { settings[key] = !settings[key]; settings.focus = false; apply(); }); menu.append(button); options.set(key, button);
  }
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
  const reset = document.createElement("button"); reset.className = "dropdown-item"; reset.textContent = "Reset layout"; reset.addEventListener("click", () => { settings = { media: true, inspector: true, timeline: true, focus: false, height: 42, left: 340, right: 320, swap: false, timelineTop: false }; menu.hidden = true; apply(); }); menu.append(reset);
  document.body.append(menu);
  focus.title = "Focus preview"; focus.addEventListener("click", () => { settings.focus = !settings.focus; apply(); });
  panels.title = "Panels"; panels.addEventListener("click", () => { const box = panels.getBoundingClientRect(); menu.style.right = "12px"; menu.style.top = `${box.bottom}px`; menu.hidden = !menu.hidden; });
  document.addEventListener("pointerdown", event => { if (!menu.contains(event.target as Node) && !panels.contains(event.target as Node) && !menu.hidden) menu.hidden = true; });
  document.addEventListener("keydown", event => { if (event.key === "Escape") { menu.hidden = true; if (settings.focus) { settings.focus = false; apply(); } } });
  const size = workspace.querySelector<HTMLButtonElement>(".tl-tabs .select-chip");
  if (size) { size.title = "Change timeline height"; size.addEventListener("click", () => { settings.height = settings.height === 42 ? 65 : settings.height === 65 ? 25 : 42; apply(); }); }
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
      else if (key === "left") settings.left += amount * 8;
      else settings.right -= amount * 8;
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
        } else if ((key === "left") !== settings.swap) {
          settings.left = Math.round(fromLeft + (moveEvent.clientX - startX));
        } else {
          settings.right = Math.round(fromRight - (moveEvent.clientX - startX));
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
  new ResizeObserver(() => placeDividers()).observe(workspace);
  apply();
}
