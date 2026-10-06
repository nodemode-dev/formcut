import { api, waitJob } from "../engine/api";
import type { ProjectState } from "../engine/types";

export interface ExportOptions {
  codec?: string | null;
  tenBit?: boolean;
  /** Render every frame as the preview shows it: slower, colours exactly as previewed. */
  exact?: boolean;
  size?: string | null;
  rate?: string | null;
  /** No background, alpha kept: the format is then mov (ProRes 4444), webm (VP9 with alpha) or png (a zip of frames). */
  transparent?: boolean;
}

export async function exportProject(project: ProjectState, format: string, quality: string, status: (text: string) => void, signal: AbortSignal, options: ExportOptions = {}): Promise<{ jobId: string; result: any }> {
  const created = await api("/api/render/export", {
    project: structuredClone(project), format, quality,
    codec: options.codec || null, tenBit: Boolean(options.tenBit), exact: Boolean(options.exact),
    size: options.size || null, rate: options.rate || null, transparent: Boolean(options.transparent),
  });
  // The engine names the file: an MP4 export saved as WebM on a computer with no
  // H.264 encoder must not be downloaded as .mp4.
  const result = await waitJob(created.job_id, status, signal);
  const link = document.createElement("a");
  link.href = `/api/jobs/${created.job_id}/file`;
  link.download = result?.name ?? `formcut-export.${format}`;
  link.click();
  return { jobId: created.job_id as string, result };
}
