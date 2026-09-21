import { api, waitJob } from "../engine/api";
import type { ProjectState } from "../engine/types";

export interface ExportOptions {
  codec?: string | null;
  tenBit?: boolean;
  size?: string | null;
  rate?: string | null;
}

export async function exportProject(project: ProjectState, format: string, quality: string, status: (text: string) => void, signal: AbortSignal, options: ExportOptions = {}): Promise<string> {
  const created = await api("/api/render/export", {
    project: structuredClone(project), format, quality,
    codec: options.codec || null, tenBit: Boolean(options.tenBit),
    size: options.size || null, rate: options.rate || null,
  });
  await waitJob(created.job_id, status, signal);
  const link = document.createElement("a");
  link.href = `/api/jobs/${created.job_id}/file`;
  link.download = `formcut-export.${format}`;
  link.click();
  return created.job_id;
}
