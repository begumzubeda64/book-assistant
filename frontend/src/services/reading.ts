import { apiFetch } from "@/services/api";
import type { JobCreatedResponse } from "@/types/jobs";
import type { ReadingGenerateRequest, ReadingResult } from "@/types/reading";

export function generateReading(
  request: ReadingGenerateRequest,
): Promise<JobCreatedResponse> {
  return apiFetch<JobCreatedResponse>("/api/v1/reading/generate", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

// A reading is immutable once generated, so cache fetched results for the
// session to avoid re-fetching the same object on every view/navigation.
const readingCache = new Map<string, ReadingResult>();

export async function getReading(readingId: string): Promise<ReadingResult> {
  const cached = readingCache.get(readingId);
  if (cached) return cached;
  const result = await apiFetch<ReadingResult>(
    `/api/v1/reading/${encodeURIComponent(readingId)}`,
  );
  readingCache.set(readingId, result);
  return result;
}
