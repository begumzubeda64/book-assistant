import { apiFetch } from "@/services/api";
import type { JobResponse } from "@/types/jobs";

export function getJob(jobId: string): Promise<JobResponse> {
  return apiFetch<JobResponse>(`/api/v1/jobs/${encodeURIComponent(jobId)}`);
}

/**
 * Poll a job until it reaches a terminal state (COMPLETED/FAILED) or the
 * attempt limit is hit. Calls `onUpdate` with each status snapshot.
 */
export async function pollJob(
  jobId: string,
  {
    intervalMs = 2000,
    maxAttempts = 60,
    onUpdate,
    signal,
  }: {
    intervalMs?: number;
    maxAttempts?: number;
    onUpdate?: (job: JobResponse) => void;
    signal?: AbortSignal;
  } = {},
): Promise<JobResponse> {
  for (let attempt = 0; attempt < maxAttempts; attempt += 1) {
    if (signal?.aborted) throw new DOMException("aborted", "AbortError");
    const job = await getJob(jobId);
    onUpdate?.(job);
    if (job.status === "COMPLETED" || job.status === "FAILED") {
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, intervalMs));
  }
  throw new Error("Job polling timed out");
}
