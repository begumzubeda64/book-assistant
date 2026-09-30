import { useCallback, useEffect, useState } from "react";

import { EmptyState, ErrorState, Spinner } from "@/components/states";
import { BookCard } from "@/features/books/BookCard";
import { getRecommendations } from "@/services/recommendations";
import type { RecommendationItem } from "@/types/recommendations";

type State =
  | { kind: "loading" }
  | { kind: "loaded"; items: RecommendationItem[] }
  | { kind: "error"; message: string };

export function RecommendationsPage() {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback(async () => {
    setState({ kind: "loading" });
    try {
      const res = await getRecommendations();
      setState({ kind: "loaded", items: res.items });
    } catch (err) {
      setState({
        kind: "error",
        message: err instanceof Error ? err.message : "Failed to load recommendations",
      });
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <h1 className="text-xl font-semibold">Recommendations</h1>
      <p className="mt-1 text-slate-500">
        Book suggestions based on your reading activity and saved concepts.
      </p>

      <div className="mt-4">
        {state.kind === "loading" && <Spinner label="Finding books for you…" />}
        {state.kind === "error" && (
          <ErrorState message={state.message} onRetry={() => void load()} />
        )}
        {state.kind === "loaded" && state.items.length === 0 && (
          <EmptyState title="No recommendations yet">
            Read and discuss a few books, and suggestions will appear here.
          </EmptyState>
        )}
        {state.kind === "loaded" && state.items.length > 0 && (
          <ul className="space-y-3">
            {state.items.map((item) => (
              <li key={item.book.book_id}>
                <BookCard book={item.book} />
                <p className="mt-1 pl-1 text-sm text-slate-500">
                  <span className="font-medium text-slate-600">Why: </span>
                  {item.reason}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
