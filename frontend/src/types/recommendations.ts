// Mirrors backend src/schemas/recommendations.py

import type { BookMetadata } from "./books";

export interface RecommendationItem {
  book: BookMetadata;
  score: number;
  reason: string;
}

export interface RecommendationsResponse {
  items: RecommendationItem[];
}
