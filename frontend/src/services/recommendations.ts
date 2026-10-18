import { apiFetch } from "@/services/api";
import type { RecommendationsResponse } from "@/types/recommendations";

export function getRecommendations(
  limit = 10,
): Promise<RecommendationsResponse> {
  const params = new URLSearchParams({ limit: String(limit) });
  return apiFetch<RecommendationsResponse>(`/api/v1/recommendations?${params}`);
}
