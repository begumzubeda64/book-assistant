import { useEffect, useState } from "react";

import { getHealth } from "@/services/health";
import type { HealthStatus } from "@/types/health";

type BackendState =
  | { kind: "loading" }
  | { kind: "ok"; health: HealthStatus }
  | { kind: "error"; message: string };

export function App() {
  const [state, setState] = useState<BackendState>({ kind: "loading" });

  useEffect(() => {
    let cancelled = false;
    getHealth()
      .then((health) => {
        if (!cancelled) setState({ kind: "ok", health });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          const message =
            err instanceof Error ? err.message : "Unable to reach the backend";
          setState({ kind: "error", message });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="min-h-screen bg-slate-50 text-slate-900 flex items-center justify-center p-6">
      <div className="max-w-md w-full rounded-xl border border-slate-200 bg-white p-8 shadow-sm">
        <h1 className="text-2xl font-semibold">Book Companion</h1>
        <p className="mt-2 text-slate-600">
          Read a book in 3, 5, or 10 minutes without losing its meaning.
        </p>

        <div className="mt-6 rounded-lg bg-slate-50 p-4">
          <h2 className="text-sm font-medium text-slate-500">Backend status</h2>
          {state.kind === "loading" && (
            <p className="mt-1 text-slate-500">Checking…</p>
          )}
          {state.kind === "ok" && (
            <p className="mt-1 font-medium text-emerald-600">
              {state.health.status} · {state.health.service} (
              {state.health.environment})
            </p>
          )}
          {state.kind === "error" && (
            <p className="mt-1 font-medium text-rose-600">{state.message}</p>
          )}
        </div>
      </div>
    </main>
  );
}
