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

export function getReading(readingId: string): Promise<ReadingResult> {
  return apiFetch<ReadingResult>(
    `/api/v1/reading/${encodeURIComponent(readingId)}`,
  );
}
