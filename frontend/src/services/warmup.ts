import { apiFetch } from "@/services/api";

/**
 * Best-effort pre-warm of the agent runtimes, called once right after login so
 * the first real action lands on warm runtimes. Fire-and-forget: never blocks
 * the UI and never surfaces errors to the user.
 */
export function warmup(): void {
  void apiFetch("/api/v1/warmup", { method: "POST" }).catch(() => {});
}
