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
  const signature = JSON.stringify([s.title, s.width, s.height, s.fps, s.timelines, s.activeTimeline]);
  const body = JSON.stringify({
    title: s.title,
    width: s.width,
    height: s.height,
    fps: s.fps,
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
      const unchanged = signature === JSON.stringify([current.title, current.width, current.height, current.fps, current.timelines, current.activeTimeline]);
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

export function newProject(engine: ProjectEngine, format?: ProjectFormat): void {
  const blank = blankProject(format);
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
