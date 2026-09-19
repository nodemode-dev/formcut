import advancedProfile from "../modes/advanced.json";
import easyProfile from "../modes/easy.json";

export interface InterfaceProfile {
  format: string;
  id: string;
  name: string;
  description: string;
  panes: Record<string, { shown: boolean; width?: number; height?: number }>;
  tabs: string[];
  inspector: { groups: string[]; subtabs: string[]; views: Record<string, string[]> };
  tools: { labels: boolean; shown: string[] };
  behaviour: { snapping: boolean; magneticMain: boolean; autosave: boolean };
  exportPresets: string[];
  features: Record<string, boolean>;
}

const STORE = "formcut.interface";
const PROFILES_STORE = "formcut.interface.profiles";
const BUILT_IN: Record<string, InterfaceProfile> = {
  advanced: advancedProfile as InterfaceProfile,
  easy: easyProfile as InterfaceProfile,
};

export const KNOWN_FEATURES: string[] = Array.from(new Set([...Object.keys(BUILT_IN.advanced.features), ...Object.keys(BUILT_IN.easy.features)]));

let active: InterfaceProfile = BUILT_IN.advanced;
const listeners = new Set<(profile: InterfaceProfile) => void>();

function userProfiles(): Record<string, InterfaceProfile> {
  try {
    const raw = localStorage.getItem(PROFILES_STORE);
    return raw ? (JSON.parse(raw) as Record<string, InterfaceProfile>) : {};
  } catch {
    return {};
  }
}

export function allProfiles(): InterfaceProfile[] {
  return [BUILT_IN.easy, BUILT_IN.advanced, ...Object.values(userProfiles())];
}

export function profileById(id: string): InterfaceProfile | null {
  return BUILT_IN[id] ?? userProfiles()[id] ?? null;
}

export function activeProfile(): InterfaceProfile {
  return active;
}

export function storedModeId(): string | null {
  try {
    return localStorage.getItem(STORE);
  } catch {
    return null;
  }
}

/** Runs before any pane is appended: the root carries the mode so the first paint is already the stored mode. */
export function primeInterfaceMode(): InterfaceProfile {
  const id = storedModeId();
  active = (id && profileById(id)) || BUILT_IN.advanced;
  document.documentElement.dataset.mode = active.id;
  return active;
}

/** Sets attributes on mounted nodes. Never creates, moves or removes a container. */
export function applyInterfaceProfile(root: ParentNode, profile: InterfaceProfile): void {
  active = profile;
  if (document.documentElement.dataset.mode !== profile.id) document.documentElement.dataset.mode = profile.id;
  for (const node of root.querySelectorAll<HTMLElement>("[data-feature]")) {
    const id = node.dataset.feature!;
    const shown = profile.features[id] !== false;
    if (node.hidden === shown) node.hidden = !shown;
    const off = String(!shown);
    if (node.dataset.featureOff !== off) node.dataset.featureOff = off;
  }
  const tabs = root.querySelector<HTMLElement>(".pane-media .pane-tabs");
  if (tabs) {
    profile.tabs.forEach((key, index) => {
      const tab = tabs.querySelector<HTMLElement>(`[data-tab="${key}"]`);
      if (tab && tab.style.order !== String(index)) tab.style.order = String(index);
    });
  }
  const toolbar = root.querySelector<HTMLElement>(".pane-timeline .tl-toolbar");
  if (toolbar) {
    const labels = profile.tools.labels ? "true" : "false";
    if (toolbar.dataset.labels !== labels) toolbar.dataset.labels = labels;
  }
  for (const listener of listeners) listener(profile);
}

function pushLayout(profile: InterfaceProfile): void {
  const layout: Record<string, boolean | number> = {};
  for (const [name, pane] of Object.entries(profile.panes)) {
    layout[name] = pane.shown;
    if (name === "media" && pane.width) layout.left = pane.width;
    if (name === "inspector" && pane.width) layout.right = pane.width;
    if (name === "timeline" && pane.height) layout.height = pane.height;
  }
  document.dispatchEvent(new CustomEvent("formcut:layout", { detail: layout }));
}

export function switchInterfaceMode(id: string): boolean {
  const profile = profileById(id);
  if (!profile) return false;
  try {
    localStorage.setItem(STORE, id);
  } catch {
    return false;
  }
  applyInterfaceProfile(document, profile);
  pushLayout(profile);
  return true;
}

export function observeInterfaceFeatures(root: Node): void {
  const applyTo = (node: HTMLElement) => {
    const id = node.dataset.feature!;
    const shown = active.features[id] !== false;
    if (node.hidden === shown) node.hidden = !shown;
    const off = String(!shown);
    if (node.dataset.featureOff !== off) node.dataset.featureOff = off;
  };
  new MutationObserver((records) => {
    for (const record of records) {
      for (const added of record.addedNodes) {
        if (!(added instanceof HTMLElement)) continue;
        if (added.dataset.feature) applyTo(added);
        for (const inner of added.querySelectorAll<HTMLElement>("[data-feature]")) applyTo(inner);
      }
    }
  }).observe(root, { childList: true, subtree: true });
}

export function onInterfaceMode(listener: (profile: InterfaceProfile) => void): void {
  listeners.add(listener);
}

export type ImportReport = { ok: true; profile: InterfaceProfile; unknown: string[] } | { ok: false; reason: string };

/** Checks the shape of a .fcui file, drops unknown feature ids and reports them. */
export function parseProfile(text: string, fallbackId?: string): ImportReport {
  let raw: unknown;
  try {
    raw = JSON.parse(text);
  } catch {
    return { ok: false, reason: "not JSON" };
  }
  if (!raw || typeof raw !== "object") return { ok: false, reason: "not an object" };
  const candidate = raw as Partial<InterfaceProfile>;
  if (candidate.format !== "fcui/1") return { ok: false, reason: "format is not fcui/1" };
  if (typeof candidate.name !== "string" || !candidate.name.trim()) return { ok: false, reason: "name missing" };
  if (!candidate.features || typeof candidate.features !== "object") return { ok: false, reason: "features missing" };
  const base = BUILT_IN.advanced;
  const features: Record<string, boolean> = {};
  const unknown: string[] = [];
  for (const [id, value] of Object.entries(candidate.features)) {
    if (KNOWN_FEATURES.includes(id)) features[id] = Boolean(value);
    else unknown.push(id);
  }
  const id = (typeof candidate.id === "string" && candidate.id.trim() ? candidate.id : fallbackId ?? candidate.name).toLowerCase().replace(/[^a-z0-9-]+/g, "-");
  const profile: InterfaceProfile = {
    format: "fcui/1",
    id: BUILT_IN[id] ? `${id}-copy` : id,
    name: candidate.name,
    description: typeof candidate.description === "string" ? candidate.description : "",
    panes: candidate.panes && typeof candidate.panes === "object" ? { ...base.panes, ...candidate.panes } : base.panes,
    tabs: Array.isArray(candidate.tabs) ? candidate.tabs.filter((tab): tab is string => typeof tab === "string") : base.tabs,
    inspector: candidate.inspector && typeof candidate.inspector === "object" ? { ...base.inspector, ...candidate.inspector } : base.inspector,
    tools: candidate.tools && typeof candidate.tools === "object" ? { ...base.tools, ...candidate.tools } : base.tools,
    behaviour: candidate.behaviour && typeof candidate.behaviour === "object" ? { ...base.behaviour, ...candidate.behaviour } : base.behaviour,
    exportPresets: Array.isArray(candidate.exportPresets) ? candidate.exportPresets.filter((preset): preset is string => typeof preset === "string") : base.exportPresets,
    features: { ...base.features, ...features },
  };
  return { ok: true, profile, unknown };
}

export function saveUserProfile(profile: InterfaceProfile): void {
  const all = userProfiles();
  all[profile.id] = profile;
  try {
    localStorage.setItem(PROFILES_STORE, JSON.stringify(all));
  } catch {
    return;
  }
}

export function removeUserProfile(id: string): void {
  const all = userProfiles();
  delete all[id];
  try {
    localStorage.setItem(PROFILES_STORE, JSON.stringify(all));
  } catch {
    return;
  }
  if (active.id === id) switchInterfaceMode("advanced");
}

export function exportProfile(profile: InterfaceProfile): string {
  return JSON.stringify(profile, null, 2);
}
