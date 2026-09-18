export async function api<T = any>(path: string, body?: unknown, method?: string): Promise<T> {
  const multipart = body instanceof FormData;
  const response = await fetch(path, {
    method: method ?? (body === undefined ? "GET" : "POST"),
    headers: body === undefined || multipart ? undefined : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : multipart ? body : JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : `Request failed (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json();
}

export async function waitJob(id: string, report?: (text: string) => void, signal?: AbortSignal): Promise<any> {
  for (;;) {
    if (signal?.aborted) {
      await api(`/api/jobs/${id}`, undefined, "DELETE");
      throw new Error("Cancelled");
    }
    const job = await api(`/api/jobs/${id}`);
    if (job.status === "done") return job.result;
    if (job.status === "error") throw new Error(job.error || "Processing failed");
    if (job.status === "cancelled") throw new Error("Cancelled");
    report?.(`${job.kind}: ${Math.round(job.progress * 100)}%`);
    await new Promise(resolve => window.setTimeout(resolve, 350));
  }
}
