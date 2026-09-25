// Mirrors backend src/schemas/reading.py and models/reading.py

export type ReadingMode = "quick_read" | "balanced_read" | "deep_read";

export type ReadingFocus =
  | "executive_summary"
  | "key_ideas"
  | "key_arguments"
  | "practical_takeaways"
  | "examples"
  | "chapter_summary"
  | "concept_explanation"
  | "narrative_summary";

export interface ReadingGenerateRequest {
  book_id: string;
  chapter_id?: string | null;
  duration_minutes: number;
  mode: ReadingMode;
  focus?: ReadingFocus;
}

export interface ReadingSourceRef {
  chapter_title?: string | null;
  section?: string | null;
  page?: number | null;
}

export interface ReadingResult {
  reading_id: string;
  book_id: string;
  chapter_id?: string | null;
  mode: ReadingMode;
  focus: ReadingFocus;
  target_minutes: number;
  target_words: number;
  actual_words: number;
  content: string;
  source_refs: ReadingSourceRef[];
  created_at: string;
}

export const SUPPORTED_DURATIONS = [3, 5, 10] as const;

export const READING_MODES: { value: ReadingMode; label: string; minutes: number }[] = [
  { value: "quick_read", label: "Quick Read", minutes: 3 },
  { value: "balanced_read", label: "Balanced Read", minutes: 5 },
  { value: "deep_read", label: "Deep Read", minutes: 10 },
];

export const READING_FOCUSES: { value: ReadingFocus; label: string }[] = [
  { value: "key_ideas", label: "Key Ideas" },
  { value: "key_arguments", label: "Key Arguments" },
  { value: "executive_summary", label: "Executive Summary" },
  { value: "practical_takeaways", label: "Practical Takeaways" },
  { value: "examples", label: "Examples" },
  { value: "chapter_summary", label: "Chapter Summary" },
  { value: "concept_explanation", label: "Concept Explanation" },
  { value: "narrative_summary", label: "Narrative Summary" },
];
