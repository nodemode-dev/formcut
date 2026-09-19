import type { ProjectEngine } from "./project";
import type { Timeline } from "./types";
import { blankProject, type ProjectFormat } from "./seed";

const API = "/api/projects";

export interface ProjectSummary {
  id: string;
  title: string;
}

interface ProjectRecord {
  revision?: number;
  id: string;
  title: string;
  width: number;
  height: number;
  fps: number;
  timelines: Timeline[];
  activeTimeline?: number;
}

export async function saveProject(engine: ProjectEngine): Promise<ProjectSummary | null> {
  const s = engine.snapshot;
  const origin = s.timelines;
  const signature = JSON.stringify([s.title, engine.baseFormat, s.timelines, s.activeTimeline]);
  const body = JSON.stringify({
    title: s.title,
    width: engine.baseFormat.width,
    height: engine.baseFormat.height,
    fps: engine.baseFormat.fps,
    timelines: s.timelines,
    activeTimeline: s.activeTimeline,
    revision: s.revision ?? 0,
  });
  const url = s.projectId ? `${API}/${s.projectId}` : API;
  try {
    const res = await fetch(url, {
      method: s.projectId ? "PUT" : "POST",
      headers: { "Content-Type": "application/json" },
      body,
    });
    if (!res.ok) return null;
    const record = (await res.json()) as ProjectRecord;
    if (engine.snapshot.timelines === origin) {
      const current = engine.snapshot;
      const unchanged = signature === JSON.stringify([current.title, engine.baseFormat, current.timelines, current.activeTimeline]);
      engine.dispatch("project.saved", { id: record.id, revision: record.revision, unchanged });
    }
    return { id: record.id, title: record.title };
  } catch {
    return null;
  }
}

export async function listProjects(): Promise<ProjectSummary[]> {
  try {
    const res = await fetch(API);
    if (!res.ok) return [];
    const records = (await res.json()) as ProjectRecord[];
    return records.map((r) => ({ id: r.id, title: r.title }));
  } catch {
    return [];
  }
}

export async function openProject(engine: ProjectEngine, id: string): Promise<boolean> {
  try {
    const res = await fetch(`${API}/${id}`);
    if (!res.ok) return false;
    const record = (await res.json()) as ProjectRecord;
    engine.dispatch("project.load", {
      projectId: record.id,
      revision: record.revision ?? 0,
      title: record.title,
      width: record.width,
      height: record.height,
      fps: record.fps,
      timelines: record.timelines,
      activeTimeline: record.activeTimeline ?? 0,
    });
    return true;
  } catch {
    return false;
  }
}

export function newProject(engine: ProjectEngine, format?: ProjectFormat, magneticMain?: boolean): void {
  const blank = blankProject(format);
  if (magneticMain) {
    const main = blank.timelines[0]?.tracks.find((track) => /video/i.test(track.name)) ?? blank.timelines[0]?.tracks[0];
    if (main) main.magnetic = true;
  }
  engine.dispatch("project.load", {
    projectId: null,
    title: blank.title,
    width: blank.width,
    height: blank.height,
    fps: blank.fps,
    timelines: blank.timelines,
    duration: blank.duration,
  });
}

// --- autosave and the recovery journal (S1, S2) --------------------------------

const AUTOSAVE_STORE = "formcut.autosave";
const AUTOSAVE_DEBOUNCE_MS = 2000;
const AUTOSAVE_MAX_WAIT_MS = 30000;

export const autosaveEnabled = (): boolean => {
  try { return localStorage.getItem(AUTOSAVE_STORE) !== "off"; } catch { return true; }
};
export const setAutosaveEnabled = (on: boolean): void => {
  try { localStorage.setItem(AUTOSAVE_STORE, on ? "on" : "off"); } catch { return; }
};

export interface JournalSummary { key: string; written: number; revision: number; title: string }

const journalKey = (engine: ProjectEngine) => engine.snapshot.projectId ?? "unsaved";

function journalDocument(engine: ProjectEngine) {
  const s = engine.snapshot;
  return { title: s.title, width: engine.baseFormat.width, height: engine.baseFormat.height, fps: engine.baseFormat.fps, timelines: s.timelines, activeTimeline: s.activeTimeline };
}

export async function listJournals(): Promise<JournalSummary[]> {
  try {
    const res = await fetch("/api/recovery");
    return res.ok ? ((await res.json()) as JournalSummary[]) : [];
  } catch {
    return [];
  }
}

export async function clearJournal(key: string): Promise<void> {
  try { await fetch(`/api/recovery/${key}`, { method: "DELETE", headers: { "x-formcut-local": "1" } }); } catch { return; }
}

export async function restoreJournal(engine: ProjectEngine, key: string): Promise<boolean> {
  try {
    const res = await fetch(`/api/recovery/${key}`);
    if (!res.ok) return false;
    const record = (await res.json()) as { revision: number; document: ProjectRecord };
    const doc = record.document;
    engine.dispatch("project.load", {
      projectId: key === "unsaved" ? null : key,
      revision: record.revision,
      title: doc.title,
      width: doc.width,
      height: doc.height,
      fps: doc.fps,
      timelines: doc.timelines,
      activeTimeline: doc.activeTimeline ?? 0,
      saved: false,
    });
    return true;
  } catch {
    return false;
  }
}

/** Watches the engine: journals every change, autosaves quietly, and reports state for the titlebar. */
export function installAutosave(engine: ProjectEngine, onState: (state: "idle" | "saving" | "saved" | "conflict") => void): void {
  let debounce = 0;
  let oldest = 0;
  let saving = false;
  let dirtyWhileSaving = false;

  const writeJournal = () => {
    void fetch("/api/recovery", {
      method: "PUT",
      headers: { "Content-Type": "application/json", "x-formcut-local": "1" },
      body: JSON.stringify({ key: journalKey(engine), revision: engine.snapshot.revision ?? 0, document: journalDocument(engine) }),
    }).catch(() => undefined);
  };

  const run = async () => {
    debounce = 0;
    oldest = 0;
    if (saving) { dirtyWhileSaving = true; return; }
    saving = true;
    onState("saving");
    const result = await saveProjectChecked(engine);
    saving = false;
    if (result === "conflict") { onState("conflict"); return; }
    if (result === "saved") {
      void clearJournal(journalKey(engine));
      onState("saved");
    } else {
      onState("idle");
    }
    if (dirtyWhileSaving) { dirtyWhileSaving = false; schedule(); }
  };

  const schedule = () => {
    if (!autosaveEnabled()) return;
    const now = performance.now();
    if (!oldest) oldest = now;
    window.clearTimeout(debounce);
    const wait = Math.min(AUTOSAVE_DEBOUNCE_MS, Math.max(0, oldest + AUTOSAVE_MAX_WAIT_MS - now));
    debounce = window.setTimeout(() => void run(), wait);
  };

  engine.subscribe((state, changed) => {
    if (changed !== "clips" && changed !== "timeline" && changed !== "project") return;
    if (state.saved) return;
    writeJournal();
    schedule();
  });
}

/** The save path with the conflict made visible: "saved", "conflict" (local copy kept) or "failed". */
export async function saveProjectChecked(engine: ProjectEngine): Promise<"saved" | "conflict" | "failed"> {
  const s = engine.snapshot;
  const origin = s.timelines;
  const signature = JSON.stringify([s.title, engine.baseFormat, s.timelines, s.activeTimeline]);
  const body = JSON.stringify({
    title: s.title, width: engine.baseFormat.width, height: engine.baseFormat.height, fps: engine.baseFormat.fps,
    timelines: s.timelines, activeTimeline: s.activeTimeline, revision: s.revision ?? 0,
  });
  const url = s.projectId ? `${API}/${s.projectId}` : API;
  try {
    const res = await fetch(url, { method: s.projectId ? "PUT" : "POST", headers: { "Content-Type": "application/json" }, body });
    if (res.status === 409) return "conflict";
    if (!res.ok) return "failed";
    const record = (await res.json()) as ProjectRecord;
    if (engine.snapshot.timelines === origin) {
      const current = engine.snapshot;
      const unchanged = signature === JSON.stringify([current.title, engine.baseFormat, current.timelines, current.activeTimeline]);
      engine.dispatch("project.saved", { id: record.id, revision: record.revision, unchanged });
    }
    return "saved";
  } catch {
    return "failed";
  }
}
