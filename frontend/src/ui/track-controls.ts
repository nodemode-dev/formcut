import type { ProjectEngine } from "../engine/project";
import { text } from "../i18n/text";
import { icon } from "./icons";

export function trackControls(header: HTMLElement, index: number, engine: ProjectEngine): void {
  if (!header.dataset.controls) {
    header.dataset.controls = "ready";
    const buttons = [...header.querySelectorAll<HTMLButtonElement>("button")];
    const definitions = [["remove", "trash", text("Remove track")], ["locked", "lock", text("Lock track")], ["hidden", "eye", text("Hide track")], ["muted", "speaker", text("Mute track")], ["magnetic", "magnet", text("Magnetic track")]];
    definitions.forEach(([key, glyph, title], i) => {
      const button = buttons[i] ?? document.createElement("button");
      button.className = "iconbtn"; button.title = title; button.setAttribute("aria-label", title); button.dataset.trackAction = key;
      if (!buttons[i]) { button.innerHTML = icon(glyph); header.append(button); }
      button.addEventListener("click", () => {
        const track = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks[index];
        if (!track) return;
        if (key === "remove") { if (engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks.length > 1) engine.dispatch("track.remove", { index }); }
        else engine.dispatch("track.update", { index, patch: { [key]: !track[key as "locked" | "hidden" | "muted" | "magnetic"] } });
      });
    });
    const name = header.querySelector<HTMLElement>(".name")!;
    name.tabIndex = 0; name.title = text("Double-click to rename track");
    name.addEventListener("dblclick", () => { name.contentEditable = "true"; name.focus(); });
    name.addEventListener("keydown", event => { if (event.key === "Enter") { event.preventDefault(); name.blur(); } if (event.key === "Escape") { name.textContent = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks[index].name; name.blur(); } });
    name.addEventListener("blur", () => { if (name.contentEditable !== "true") return; name.contentEditable = "false"; engine.dispatch("track.update", { index, patch: { name: name.textContent?.trim() || "Track" } }); });
  }
  const track = engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks[index];
  for (const button of header.querySelectorAll<HTMLButtonElement>("[data-track-action]")) {
    const key = button.dataset.trackAction!;
    button.disabled = key === "remove" && engine.snapshot.timelines[engine.snapshot.activeTimeline].tracks.length < 2;
    const active = Boolean(track[key as "locked" | "hidden" | "muted" | "magnetic"]);
    if (key === "hidden" || key === "muted") {
      const glyph = key === "hidden" ? (active ? "eyeOff" : "eye") : (active ? "mute" : "speaker");
      if (button.dataset.glyph !== glyph) { button.dataset.glyph = glyph; button.innerHTML = icon(glyph); }
      button.classList.toggle("is-off", active);
    } else button.classList.toggle("is-accent", active);
    if (key !== "remove") button.setAttribute("aria-pressed", String(active));
  }
}
