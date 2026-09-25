// Mirrors backend src/schemas/uploads.py

export interface PresignUploadRequest {
  filename: string;
  content_type?: string;
  size_bytes: number;
  authorized_confirmation: boolean;
}

export interface PresignUploadResponse {
  book_id: string;
  upload_url: string;
  object_key: string;
  method: string;
  required_headers: Record<string, string>;
  expires_in_seconds: number;
}

export interface IngestRequest {
  object_key: string;
}
