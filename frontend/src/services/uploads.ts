import { apiFetch } from "@/services/api";
import type { JobCreatedResponse } from "@/types/jobs";
import type {
  IngestRequest,
  PresignUploadRequest,
  PresignUploadResponse,
} from "@/types/uploads";

export function presignUpload(
  request: PresignUploadRequest,
): Promise<PresignUploadResponse> {
  return apiFetch<PresignUploadResponse>("/api/v1/uploads/presign", {
    method: "POST",
    body: JSON.stringify(request),
  });
}

/** Upload the file bytes directly to S3 via the presigned URL (not through the API). */
export async function uploadToS3(
  presigned: PresignUploadResponse,
  file: File,
): Promise<void> {
  const response = await fetch(presigned.upload_url, {
    method: presigned.method,
    headers: presigned.required_headers,
    body: file,
  });
  if (!response.ok) {
    throw new Error(`Upload to storage failed (${response.status})`);
  }
}

export function ingestBook(
  bookId: string,
  request: IngestRequest,
): Promise<JobCreatedResponse> {
  return apiFetch<JobCreatedResponse>(
    `/api/v1/books/${encodeURIComponent(bookId)}/ingest`,
    { method: "POST", body: JSON.stringify(request) },
  );
}
