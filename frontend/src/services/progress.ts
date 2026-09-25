import { ApiRequestError, apiFetch } from "@/services/api";
import type { ProgressResponse, ProgressUpdate } from "@/types/progress";

/** Returns saved progress, or null if none exists yet (404). */
export async function getProgress(
  bookId: string,
): Promise<ProgressResponse | null> {
  try {
    return await apiFetch<ProgressResponse>(
      `/api/v1/progress/${encodeURIComponent(bookId)}`,
    );
  } catch (err) {
    if (err instanceof ApiRequestError && err.status === 404) {
      return null;
    }
    throw err;
  }
}

export function saveProgress(
  bookId: string,
  update: ProgressUpdate,
): Promise<ProgressResponse> {
  return apiFetch<ProgressResponse>(
    `/api/v1/progress/${encodeURIComponent(bookId)}`,
    { method: "PUT", body: JSON.stringify(update) },
  );
}
