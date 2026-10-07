import type { ProjectEngine } from "../engine/project";

// The Pro tab's keyboard layouts (FilmCraft offers Premiere, Final Cut and Avid ones): a layer in front of formcut's
// own keys (editor-actions.ts). With a layout chosen, its keys run first and stop there; any key it leaves free falls
// through to formcut's, so nothing is lost. Only defaults each application is known to ship are listed. Marks and the
// three-point edits go to the Pro tab (source monitor when it holds a source and is open, else the timeline range).

export type KeyAction =
  | "play"
  | "markIn"
  | "markOut"
  | "insert"
  | "overwrite"
  | "append"
  | "lift"
  | "extract"
  | "addEdit"
  | "rippleDelete"
  | "prevEdit"
  | "nextEdit";

export const LAYOUTS: Record<string, { name: string; keys: Partial<Record<KeyAction, string[]>> }> = {
  formcut: { name: "formcut", keys: {} },
  premiere: {
    name: "Premiere Pro",
    keys: {
      play: ["space"],
      markIn: ["i"],
      markOut: ["o"],
      insert: [","],
      overwrite: ["."],
      lift: [";"],
      extract: ["'"],
      addEdit: ["mod+k"],
      rippleDelete: ["shift+backspace", "shift+delete", "alt+backspace", "alt+delete"],
      prevEdit: ["arrowup"],
      nextEdit: ["arrowdown"],
    },
  },
  finalcut: {
    name: "Final Cut Pro",
    keys: {
      play: ["space"],
      markIn: ["i"],
      markOut: ["o"],
      insert: ["w"],
      overwrite: ["d"],
      append: ["e"],
      addEdit: ["mod+b"],
      rippleDelete: ["backspace", "delete"],
      prevEdit: ["arrowup"],
      nextEdit: ["arrowdown"],
    },
  },
  avid: {
    name: "Avid Media Composer",
    keys: {
      play: ["space"],
      markIn: ["i", "e"],
      markOut: ["o", "r"],
      insert: ["v"],
      overwrite: ["b"],
      lift: ["z"],
      extract: ["x"],
      prevEdit: ["a"],
      nextEdit: ["s"],
    },
  },
};

const STORE = "formcut.keys.layout";

export function currentLayout(): string {
  try {
    const kept = localStorage.getItem(STORE);
    return kept && LAYOUTS[kept] ? kept : "formcut";
  } catch {
    return "formcut";
  }
}

export function chooseLayout(id: string): void {
  try {
    localStorage.setItem(STORE, LAYOUTS[id] ? id : "formcut");
  } catch {
    // a layout that cannot be kept still applies for this session through the picker's value
  }
}

/** A key as the layouts write it: modifiers first (mod is Command or Control), then the key, lower case. */
export function keyName(event: KeyboardEvent): string {
  const key = event.key === " " ? "space" : event.key.toLowerCase();
  return [event.metaKey || event.ctrlKey ? "mod" : "", event.shiftKey && key.length > 1 ? "shift" : "", event.altKey ? "alt" : "", key].filter(Boolean).join("+");
}

/** How a key reads in the Keys list. */
export function keyLabel(name: string): string {
  const mac = /Mac|iPhone|iPad/.test(navigator.platform);
  const words: Record<string, string> = {
    mod: mac ? "⌘" : "Ctrl",
    shift: "Shift",
    alt: mac ? "⌥" : "Alt",
    space: "Space",
    backspace: mac ? "Delete" : "Backspace",
    delete: "Del",
    arrowup: "↑",
    arrowdown: "↓",
    arrowleft: "←",
    arrowright: "→",
  };
  return name
    .split("+")
    .map((part) => words[part] ?? part.toUpperCase())
    .join(mac ? "" : "+");
}

function run(action: KeyAction, engine: ProjectEngine): void {
  const s = engine.snapshot;
  const tracks = s.timelines[s.activeTimeline].tracks;
  if (action === "play") engine.dispatch("transport.toggle");
  else if (action === "addEdit") {
    const under = tracks.filter((track) => !track.locked).flatMap((track) => track.clips.filter((c) => s.playhead > c.start && s.playhead < c.start + c.duration).map((c) => c.id));
    if (under.length) engine.dispatch("clips.split", { clipIds: under, time: s.playhead });
  } else if (action === "rippleDelete") {
    if (s.selectedClipId) engine.dispatch("clip.ripple-delete", { clipId: s.selectedClipId });
  } else if (action === "prevEdit" || action === "nextEdit") {
    const points = [...new Set(tracks.flatMap((track) => track.clips.flatMap((c) => [c.start, c.start + c.duration])))].sort((a, b) => a - b);
    const target = action === "nextEdit" ? points.find((p) => p > s.playhead + 1e-3) : [...points].reverse().find((p) => p < s.playhead - 1e-3);
    if (target !== undefined) engine.dispatch("transport.seek", target);
  } else {
    document.dispatchEvent(new CustomEvent("formcut:pro", { detail: action }));
  }
}

export function installKeymap(engine: ProjectEngine): void {
  window.addEventListener(
    "keydown",
    (event) => {
      const layout = LAYOUTS[currentLayout()];
      if (!Object.keys(layout.keys).length) return;
      const target = event.target as HTMLElement;
      if (target.closest?.("input,textarea,select,[contenteditable=true]") || document.querySelector(".modal-scrim:not([hidden]),.start-overlay:not([hidden])")) return;
      const name = keyName(event);
      const action = (Object.entries(layout.keys) as Array<[KeyAction, string[]]>).find(([, keys]) => keys.includes(name))?.[0];
      if (!action) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      run(action, engine);
    },
    true,
  );
}
