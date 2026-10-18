// Mirrors backend src/schemas/jobs.py and models/job.py

export type JobType = "BOOK_INGESTION" | "ADAPTIVE_READING";
export type JobStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export interface JobResponse {
  job_id: string;
  job_type: JobType;
  status: JobStatus;
  book_id?: string | null;
  progress: number;
  result_location?: string | null;
  error_code?: string | null;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
}

export interface JobCreatedResponse {
  job_id: string;
  status: JobStatus;
}
