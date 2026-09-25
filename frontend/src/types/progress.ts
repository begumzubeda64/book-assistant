// Mirrors backend src/schemas/progress.py

import type { ReadingMode } from "./reading";

export interface ProgressUpdate {
  chapter_id?: string | null;
  position?: number;
  selected_duration?: number | null;
  selected_mode?: ReadingMode | null;
  completed?: boolean;
}

export interface ProgressResponse {
  book_id: string;
  chapter_id?: string | null;
  position: number;
  selected_duration?: number | null;
  selected_mode?: ReadingMode | null;
  completed: boolean;
  updated_at: string;
}
