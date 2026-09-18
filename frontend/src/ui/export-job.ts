import { api, waitJob } from "../engine/api";
import type { ProjectState } from "../engine/types";

export async function exportProject(project: ProjectState, format: string, quality: string, status: (text: string) => void, signal: AbortSignal): Promise<void> {
  const created = await api("/api/render/export", { project: structuredClone(project), format, quality });
  await waitJob(created.job_id, status, signal);
  const link = document.createElement("a");
  link.href = `/api/jobs/${created.job_id}/file`;
  link.download = `formcut-export.${format}`;
  link.click();
}
