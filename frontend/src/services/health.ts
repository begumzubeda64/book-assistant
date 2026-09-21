import { apiFetch } from "@/services/api";
import type { HealthStatus } from "@/types/health";

export function getHealth(): Promise<HealthStatus> {
  return apiFetch<HealthStatus>("/health");
}
