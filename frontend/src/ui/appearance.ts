// Appearance: 30 profiles and a free accent, applied by writing custom
// properties on the root element. Nothing re-renders, so a theme change cannot
// flash, rebuild a container or lose focus. The palettes live in themes.css as
// [data-theme] blocks; this module owns the choice, its persistence and the two
// profiles that are behaviours rather than palettes.

export interface Profile {
  id: string;
  label: string;
  light?: boolean;
  behaviour?: "click" | "cycle";
}

export const PROFILES: Profile[] = [
  { id: "formcut-dark", label: "formcut Dark" },
  { id: "high-contrast", label: "High Contrast" },
  { id: "obsidian", label: "Obsidian" },
  { id: "graphite", label: "Graphite" },
  { id: "mono-ink", label: "Mono Ink" },
  { id: "github-dark", label: "GitHub Dark" },
  { id: "slate", label: "Slate" },
  { id: "rose-noir", label: "Rose Noir" },
  { id: "crimson", label: "Crimson" },
  { id: "ember", label: "Ember" },
  { id: "copper", label: "Copper" },
  { id: "amber", label: "Amber" },
  { id: "olive", label: "Olive" },
  { id: "forest", label: "Forest" },
  { id: "terminal-green", label: "Terminal Green" },
  { id: "aurora", label: "Aurora" },
  { id: "deep-ocean", label: "Deep Ocean" },
  { id: "arctic", label: "Arctic" },
  { id: "midnight-blue", label: "Midnight Blue" },
  { id: "indigo", label: "Indigo" },
  { id: "violet-haze", label: "Violet Haze" },
  { id: "plum", label: "Plum" },
  { id: "crazy-click-random", label: "Crazy Click Random", behaviour: "click" },
  { id: "crazy-cycle-random", label: "Crazy Cycle Random", behaviour: "cycle" },
  { id: "light", label: "Light", light: true },
  { id: "sand", label: "Sand", light: true },
  { id: "linen", label: "Linen", light: true },
  { id: "mist", label: "Mist", light: true },
  { id: "pearl", label: "Pearl", light: true },
  { id: "dove-grey", label: "Dove Grey", light: true },
];

export const ACCENTS = ["#ffae2b", "#f97316", "#ef4444", "#ec4899", "#a855f7", "#6366f1", "#3b82f6", "#22d3ee", "#14b8a6", "#22c55e", "#eab308", "#f5f5f7"];

const STORE = "formcut.appearance";
const PALETTES = PROFILES.filter((profile) => !profile.behaviour).map((profile) => profile.id);

export interface Appearance {
  theme: string;
  accent: string | null;
  derived: Record<string, string> | null;
}

const clamp = (value: number) => Math.max(0, Math.min(255, Math.round(value)));

function channels(hex: string): [number, number, number] {
  const value = hex.replace("#", "");
  const full = value.length === 3 ? value.split("").map((part) => part + part).join("") : value;
  return [parseInt(full.slice(0, 2), 16), parseInt(full.slice(2, 4), 16), parseInt(full.slice(4, 6), 16)];
}

// Derived values are computed once and stored, so the pre-paint boot script can
// apply them verbatim instead of repeating this arithmetic before first paint.
export function derive(hex: string): Record<string, string> {
  const [r, g, b] = channels(hex);
  const lift = (value: number) => clamp(value + (255 - value) * 0.22);
  const hover = `#${[lift(r), lift(g), lift(b)].map((value) => value.toString(16).padStart(2, "0")).join("")}`;
  const luminance = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255;
  return {
    "--cue": hex,
    "--cue-hover": hover,
    "--cue-wash": `rgb(${r} ${g} ${b} / 0.22)`,
    "--on-cue": luminance > 0.55 ? "#101014" : "#ffffff",
  };
}

export function read(): Appearance {
  try {
    const raw = localStorage.getItem(STORE);
    if (raw) {
      const parsed = JSON.parse(raw) as Partial<Appearance>;
      return {
        theme: typeof parsed.theme === "string" ? parsed.theme : "formcut-dark",
        accent: typeof parsed.accent === "string" ? parsed.accent : null,
        derived: parsed.derived && typeof parsed.derived === "object" ? parsed.derived as Record<string, string> : null,
      };
    }
  } catch {
    // A blocked or corrupt store must not stop the editor from opening.
  }
  return { theme: "formcut-dark", accent: null, derived: null };
}

function write(state: Appearance): void {
  try {
    localStorage.setItem(STORE, JSON.stringify(state));
  } catch {
    // Nothing to do: the choice simply does not survive the session.
  }
}

export function randomPalette(exclude?: string): string {
  const pool = PALETTES.filter((id) => id !== exclude);
  return pool[Math.floor(Math.random() * pool.length)];
}

let cycleTimer: number | undefined;

function stopCycle(): void {
  if (cycleTimer !== undefined) {
    window.clearInterval(cycleTimer);
    cycleTimer = undefined;
  }
}

function paint(themeId: string): void {
  if (document.documentElement.dataset.theme !== themeId) document.documentElement.dataset.theme = themeId;
}

function paintAccent(accent: string | null, derived: Record<string, string> | null): void {
  const style = document.documentElement.style;
  const values = accent ? (derived && derived["--cue"] ? derived : derive(accent)) : null;
  for (const name of ["--cue", "--cue-hover", "--cue-wash", "--on-cue"]) {
    if (values) style.setProperty(name, values[name]);
    else style.removeProperty(name);
  }
  for (const legacy of ["--accent", "--accent-hover", "--accent-soft", "--on-accent"]) style.removeProperty(legacy);
}

// Applying a behaviour profile keeps the stored choice as the behaviour, while
// what gets painted is a palette: the behaviour is how the palette is chosen.
export function apply(state: Appearance, persist = true): void {
  const profile = PROFILES.find((entry) => entry.id === state.theme);
  stopCycle();
  if (profile?.behaviour === "cycle") {
    paint(randomPalette());
    cycleTimer = window.setInterval(() => paint(randomPalette(document.documentElement.dataset.theme)), 20000);
  } else if (profile?.behaviour === "click") {
    paint(randomPalette());
  } else {
    paint(profile ? profile.id : "formcut-dark");
  }
  paintAccent(state.accent, state.derived);
  if (persist) write(state);
}

export function setTheme(themeId: string): Appearance {
  const current = read();
  const next: Appearance = { ...current, theme: themeId };
  apply(next);
  return next;
}

export function setAccent(hex: string | null): Appearance {
  const current = read();
  const next: Appearance = { ...current, accent: hex, derived: hex ? derive(hex) : null };
  apply(next);
  return next;
}

export function currentBehaviour(): Profile["behaviour"] {
  return PROFILES.find((entry) => entry.id === read().theme)?.behaviour;
}

// Crazy Click Random repaints on any click in the app, which is the behaviour
// its name promises; the listener is installed once and checks the stored
// choice, so switching away costs nothing.
export function installBehaviours(): void {
  document.addEventListener("click", () => {
    if (currentBehaviour() === "click") paint(randomPalette(document.documentElement.dataset.theme));
  });
  apply(read(), false);
}
